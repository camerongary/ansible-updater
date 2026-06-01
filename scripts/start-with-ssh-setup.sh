#!/bin/bash

set -e

# Ansible Update Manager - With SSH Key Setup
# Main orchestration script that can setup SSH keys before running updates

# Configuration
NETWORK_RANGE="${NETWORK_RANGE:-192.168.12.0/24}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-3600}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-https://hooks.slack.com/services/YOUR/WEBHOOK/URL}"
REPORTS_DIR="/reports"
ANSIBLE_DIR="/ansible"
LOG_FILE="/var/log/ansible/updater.log"
SSH_KEY_SETUP="${SSH_KEY_SETUP:-false}"
SSH_USER="${SSH_USER:-root}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_rsa}"

echo "[$(date)] Starting Ansible Update Manager" | tee -a "$LOG_FILE"
echo "[$(date)] Configuration: NETWORK_RANGE=$NETWORK_RANGE, UPDATE_INTERVAL=${UPDATE_INTERVAL}s" | tee -a "$LOG_FILE"
echo "[$(date)] Slack webhook configured: $([ -n "$SLACK_WEBHOOK_URL" ] && echo 'YES' || echo 'NO')" | tee -a "$LOG_FILE"
echo "[$(date)] SSH Key Setup: $SSH_KEY_SETUP" | tee -a "$LOG_FILE"

# Create necessary directories
mkdir -p "$REPORTS_DIR"
mkdir -p "$(dirname "$LOG_FILE")"

# Function to log messages
log() {
    echo "[$(date)] $1" | tee -a "$LOG_FILE"
}

# Function to setup SSH keys
setup_ssh_keys() {
    log "Starting SSH key setup..."
    
    if [ "$SSH_KEY_SETUP" != "true" ] && [ "$SSH_KEY_SETUP" != "1" ]; then
        log "SSH key setup disabled (SSH_KEY_SETUP=$SSH_KEY_SETUP)"
        return 0
    fi

    # Check if SSH key exists
    if [ ! -f "$SSH_KEY" ]; then
        log "ERROR: SSH key not found at $SSH_KEY"
        log "Generate SSH key with: ssh-keygen -t ed25519 -f $SSH_KEY -N \"\""
        return 1
    fi

    log "Discovered servers in $NETWORK_RANGE..."
    
    # Get list of live hosts
    SERVERS=$(nmap -sn "$NETWORK_RANGE" -oG - 2>/dev/null | grep "Up" | awk '{print $2}' | sort -V)
    
    if [ -z "$SERVERS" ]; then
        log "No servers discovered in $NETWORK_RANGE"
        return 1
    fi

    # Copy keys to each server
    local success=0
    local failed=0
    
    while IFS= read -r server; do
        log "Setting up SSH key on $server..."
        
        # Check if key already works
        if timeout 5 ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no -i "$SSH_KEY" "$SSH_USER@$server" "echo ok" &>/dev/null; then
            log "✓ SSH key already works on $server"
            ((success++))
            continue
        fi
        
        # Try to copy key
        if timeout 5 ssh-copy-id -i "$SSH_KEY" -o ConnectTimeout=3 -o StrictHostKeyChecking=no "$SSH_USER@$server" &>/dev/null 2>&1; then
            log "✓ SSH key copied to $server"
            ((success++))
        else
            log "✗ Failed to copy SSH key to $server"
            ((failed++))
        fi
    done <<< "$SERVERS"

    log "SSH key setup complete: $success successful, $failed failed"
    
    if [ $failed -gt 0 ]; then
        log "WARNING: Some servers failed. You may need to set up SSH manually for those servers."
        return 1
    fi
    
    return 0
}

# Function to run nmap discovery
discover_systems() {
    log "Starting network discovery on $NETWORK_RANGE..."
    
    nmap -sn "$NETWORK_RANGE" -oG - | grep "Up" | awk '{print $2}' > /tmp/live_hosts.txt
    
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
    
    cat > "$inventory_file" << 'EOF'
all:
  children:
    debian:
      hosts:
EOF
    
    for host in $(echo "$hosts" | tr ',' '\n'); do
        echo "        $host:" >> "$inventory_file"
        echo "          ansible_user: $SSH_USER" >> "$inventory_file"
    done
    
    cat >> "$inventory_file" << 'EOF'
    
    redhat:
      hosts:
EOF
    
    for host in $(echo "$hosts" | tr ',' '\n'); do
        echo "        $host:" >> "$inventory_file"
        echo "          ansible_user: $SSH_USER" >> "$inventory_file"
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
        python3 /scripts/generate_reports.py "$RESULT_FILE" 2>&1 | tee -a "$LOG_FILE"
        python3 /scripts/slack_notifier.py "$RESULT_FILE" 2>&1 | tee -a "$LOG_FILE"
    fi
}

# Main loop
if [ "$SSH_KEY_SETUP" == "true" ] || [ "$SSH_KEY_SETUP" == "1" ]; then
    log "SSH key setup mode enabled"
    if setup_ssh_keys; then
        log "SSH keys setup completed successfully"
    else
        log "WARNING: SSH key setup encountered issues"
    fi
    exit 0
fi

log "Starting main update cycle"

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
