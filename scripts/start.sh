#!/bin/bash

set -e

# Configuration
NETWORK_RANGE="${NETWORK_RANGE:-192.168.1.0/24}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-3600}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-https://hooks.slack.com/services/YOUR/WEBHOOK/URL}"
BOOTSTRAP_PASSWORD="${BOOTSTRAP_PASSWORD:-}"
REPORTS_DIR="/reports"
ANSIBLE_DIR="/ansible"
LOG_FILE="/var/log/ansible/updater.log"

echo "[$(date)] Starting Ansible Update Manager" | tee -a "$LOG_FILE"
echo "[$(date)] Configuration: NETWORK_RANGE=$NETWORK_RANGE, UPDATE_INTERVAL=${UPDATE_INTERVAL}s" | tee -a "$LOG_FILE"
echo "[$(date)] Slack webhook configured: $([ -n "$SLACK_WEBHOOK_URL" ] && echo 'YES' || echo 'NO')" | tee -a "$LOG_FILE"

# Create necessary directories
mkdir -p "$REPORTS_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Start web dashboard in the background
python3 /scripts/web_server.py &
WEB_PID=$!
echo "[$(date)] Web dashboard started on port 8080 (pid $WEB_PID)" | tee -a "$LOG_FILE"

# Function to log messages (stderr only so stdout can carry data)
log() {
    echo "[$(date)] $1" | tee -a "$LOG_FILE" >&2
}

# Function to run nmap discovery
discover_systems() {
    log "Starting network discovery on $NETWORK_RANGE..."
    
    nmap -sn "$NETWORK_RANGE" -oG - | grep "Up" | awk '{print $2}' > /tmp/live_hosts.txt

    # Filter out excluded hosts if exclude list exists
    EXCLUDE_FILE="$ANSIBLE_DIR/exclude_hosts.txt"
    if [ -f "$EXCLUDE_FILE" ]; then
        grep -vxFf "$EXCLUDE_FILE" /tmp/live_hosts.txt > /tmp/filtered_hosts.txt || true
        mv /tmp/filtered_hosts.txt /tmp/live_hosts.txt
    fi

    HOSTS=$(cat /tmp/live_hosts.txt | tr '\n' ',' | sed 's/,$//')
    
    if [ -z "$HOSTS" ]; then
        log "No hosts discovered"
        return 1
    fi
    
    log "Discovered hosts: $HOSTS"
    echo "$HOSTS"
}

# Check whether SSH key auth works for a host
check_ssh() {
    local host=$1
    local user=${2:-cameron}
    ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no \
        -i /root/.ssh/id_ed25519 "${user}@${host}" true 2>/dev/null
}

# Bootstrap a new host: copy SSH key then install passwordless sudo
bootstrap_host() {
    local host=$1
    if [ -z "$BOOTSTRAP_PASSWORD" ]; then
        return 1
    fi

    log "Bootstrapping new host $host..."

    # Copy SSH key using password auth
    if ! sshpass -p "$BOOTSTRAP_PASSWORD" ssh-copy-id \
            -i /root/.ssh/id_ed25519.pub \
            -o StrictHostKeyChecking=no \
            -o PreferredAuthentications=password \
            "cameron@${host}" 2>/dev/null; then
        log "Bootstrap failed for $host — could not copy SSH key"
        return 1
    fi

    # Install passwordless sudo via Ansible (use password for become)
    if ! ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook \
            "$ANSIBLE_DIR/bootstrap.yml" \
            -i "${host}," \
            -e "ansible_user=cameron" \
            -e "ansible_ssh_pass=$BOOTSTRAP_PASSWORD" \
            -e "ansible_become_pass=$BOOTSTRAP_PASSWORD" 2>/dev/null; then
        log "Bootstrap warning: sudo setup failed for $host — key copied but sudo may require password"
    fi

    log "Bootstrap complete for $host"
    return 0
}

# Function to generate Ansible inventory (only includes reachable hosts)
generate_inventory() {
    local hosts=$1
    local inventory_file="$ANSIBLE_DIR/hosts.yml"
    local reachable=0

    printf 'all:\n  hosts:\n' > "$inventory_file"

    for host in $(echo "$hosts" | tr ',' '\n'); do
        # Determine the expected user for this host (honour host_vars override)
        local user=cameron
        local host_vars_file="$ANSIBLE_DIR/host_vars/${host}.yml"
        if [ -f "$host_vars_file" ] && grep -q 'ansible_user: root' "$host_vars_file"; then
            user=root
        fi

        if check_ssh "$host" "$user"; then
            printf '    %s:\n      ansible_user: %s\n' "$host" "$user" >> "$inventory_file"
            reachable=$((reachable + 1))
        elif bootstrap_host "$host"; then
            printf '    %s:\n      ansible_user: cameron\n' "$host" >> "$inventory_file"
            reachable=$((reachable + 1))
        else
            log "Skipping $host — not reachable via SSH"
        fi
    done

    if [ "$reachable" -eq 0 ]; then
        log "No reachable hosts found"
        return 1
    fi

    log "Generated inventory at $inventory_file ($reachable hosts)"
}

# Function to run updates and capture results
run_updates() {
    log "Running system updates..."
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    RESULT_FILE="$REPORTS_DIR/updates_${TIMESTAMP}.json"
    
    # Run the Ansible playbook and capture output
    ansible-playbook \
        "$ANSIBLE_DIR/update-playbook.yml" \
        -i "$ANSIBLE_DIR/hosts.yml" \
        -e "result_file=$RESULT_FILE" \
        --extra-vars="timestamp=$TIMESTAMP" \
        2>&1 | tee -a "$LOG_FILE"
    
    log "Update completed. Results saved to $RESULT_FILE"
    
    # If result file exists, generate reports
    if [ -f "$RESULT_FILE" ]; then
        python3 /scripts/generate_reports.py "$RESULT_FILE"
        python3 /scripts/slack_notifier.py "$RESULT_FILE"
    fi
}

TRIGGER_FILE="/tmp/trigger_scan"
LOCK_FILE="/tmp/scan_running"

run_cycle() {
    touch "$LOCK_FILE"
    log "================================"
    log "Starting update cycle"
    log "================================"

    if HOSTS=$(discover_systems); then
        generate_inventory "$HOSTS"
        run_updates
    else
        log "Skipping updates - no hosts discovered"
    fi

    rm -f "$LOCK_FILE"
    log "Update cycle completed. Next cycle in $UPDATE_INTERVAL seconds"
}

# Main loop
while true; do
    rm -f "$TRIGGER_FILE"
    run_cycle

    # Sleep, but wake early if the web UI drops a trigger file
    elapsed=0
    while [ "$elapsed" -lt "$UPDATE_INTERVAL" ]; do
        sleep 10
        elapsed=$((elapsed + 10))
        if [ -f "$TRIGGER_FILE" ]; then
            log "Manual scan triggered via web UI"
            break
        fi
    done
done
