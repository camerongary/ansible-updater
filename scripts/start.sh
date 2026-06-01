#!/bin/bash

set -e

# Configuration
NETWORK_RANGE="${NETWORK_RANGE:-192.168.1.0/24}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-3600}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-https://hooks.slack.com/services/YOUR/WEBHOOK/URL}"
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

# Function to generate Ansible inventory
generate_inventory() {
    local hosts=$1
    local inventory_file="$ANSIBLE_DIR/hosts.yml"

    printf 'all:\n  hosts:\n' > "$inventory_file"

    for host in $(echo "$hosts" | tr ',' '\n'); do
        printf '    %s:\n      ansible_user: cameron\n' "$host" >> "$inventory_file"
    done

    log "Generated inventory at $inventory_file"
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

# Main loop
while true; do
    log "================================"
    log "Starting update cycle"
    log "================================"
    
    # Discover systems
    if HOSTS=$(discover_systems); then
        # Generate inventory
        generate_inventory "$HOSTS"
        
        # Run updates
        run_updates
    else
        log "Skipping updates - no hosts discovered"
    fi
    
    log "Update cycle completed. Next cycle in $UPDATE_INTERVAL seconds"
    sleep "$UPDATE_INTERVAL"
done
