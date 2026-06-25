#!/bin/bash
#
# Orchestrator for the Ansible Update Manager (approval workflow).
#
#   * launches the Flask approval dashboard
#   * main loop: discover hosts -> bootstrap/inventory -> CHECK for updates (no
#     changes) -> report.  Wakes early when the dashboard requests a scan.
#   * poller:    apply / reboot work orders approved via the dashboard
#
# REQUIRE_APPROVAL=true  (default): each cycle only CHECKS; nothing is installed
#                                   until approved in the dashboard.
# REQUIRE_APPROVAL=false          : legacy behaviour — auto-apply everything each
#                                   cycle.  (Reboots always require approval.)

set -e

# Configuration
NETWORK_RANGE="${NETWORK_RANGE:-192.168.1.0/24}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-3600}"
REQUIRE_APPROVAL="${REQUIRE_APPROVAL:-true}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
BOOTSTRAP_PASSWORD="${BOOTSTRAP_PASSWORD:-}"
REPORTS_DIR="/reports"
ANSIBLE_DIR="/ansible"
LOG_FILE="/var/log/ansible/updater.log"
POLL_INTERVAL=15

TRIGGER_FILE="/tmp/trigger_scan"   # dashboard "Scan Now" drops this
LOCK_FILE="/tmp/scan_running"       # UI busy flag (dashboard reads it)
ANSIBLE_LOCK="/tmp/ansible.lock"    # mutex dir: only one playbook at a time

mkdir -p "$REPORTS_DIR" "$(dirname "$LOG_FILE")"

echo "[$(date)] Starting Ansible Update Manager" | tee -a "$LOG_FILE"
echo "[$(date)] NETWORK_RANGE=$NETWORK_RANGE UPDATE_INTERVAL=${UPDATE_INTERVAL}s REQUIRE_APPROVAL=$REQUIRE_APPROVAL" | tee -a "$LOG_FILE"
echo "[$(date)] Slack webhook configured: $([ -n "$SLACK_WEBHOOK_URL" ] && echo 'YES' || echo 'NO')" | tee -a "$LOG_FILE"

# Start web dashboard in the background
python3 /scripts/web_server.py &
WEB_PID=$!
echo "[$(date)] Web dashboard started on port 8080 (pid $WEB_PID)" | tee -a "$LOG_FILE"

# Log to stderr so stdout can carry data returned by functions
log() {
    echo "[$(date)] $1" | tee -a "$LOG_FILE" >&2
}

# --------------------------------------------------------------------------- #
# Mutex so the check cycle and the apply poller never run a playbook at once.
# --------------------------------------------------------------------------- #
acquire_lock() {
    local waited=0
    while ! mkdir "$ANSIBLE_LOCK" 2>/dev/null; do
        sleep 1
        waited=$((waited + 1))
        if [ "$waited" -ge 1800 ]; then
            log "WARN: stale ansible lock, reclaiming"
            rmdir "$ANSIBLE_LOCK" 2>/dev/null || true
        fi
    done
}
release_lock() { rmdir "$ANSIBLE_LOCK" 2>/dev/null || true; }

# --------------------------------------------------------------------------- #
# Discovery + inventory (unchanged from the host's bootstrap-aware version)
# --------------------------------------------------------------------------- #
discover_systems() {
    log "Starting network discovery on $NETWORK_RANGE..."

    nmap -sn "$NETWORK_RANGE" -oG - | grep "Up" | awk '{print $2}' > /tmp/live_hosts.txt

    # Merge manually-added hosts (added from the dashboard). This ensures hosts
    # outside the scan range, or that don't answer the nmap ping sweep, are still
    # managed on every cycle.
    MANUAL_FILE="$REPORTS_DIR/manual_hosts.txt"
    if [ -f "$MANUAL_FILE" ]; then
        grep -vE '^[[:space:]]*$' "$MANUAL_FILE" >> /tmp/live_hosts.txt || true
    fi

    # Filter out excluded hosts if exclude list exists
    EXCLUDE_FILE="$ANSIBLE_DIR/exclude_hosts.txt"
    if [ -f "$EXCLUDE_FILE" ]; then
        grep -vxFf "$EXCLUDE_FILE" /tmp/live_hosts.txt > /tmp/filtered_hosts.txt || true
        mv /tmp/filtered_hosts.txt /tmp/live_hosts.txt
    fi

    # De-duplicate (manual hosts may overlap discovered ones) and drop blanks.
    sort -u /tmp/live_hosts.txt | grep -vE '^[[:space:]]*$' > /tmp/live_hosts.dedup || true
    mv /tmp/live_hosts.dedup /tmp/live_hosts.txt

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

# Check whether passwordless sudo works (not needed for root-access hosts)
check_sudo() {
    local host=$1
    ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no \
        -i /root/.ssh/id_ed25519 "cameron@${host}" "sudo -n true" 2>/dev/null
}

# Install sudo and configure passwordless sudoers for cameron.
setup_sudo() {
    local host=$1
    local pub_key
    pub_key=$(cat /root/.ssh/id_ed25519.pub)
    local sudoers_cmd="apt-get install -y sudo 2>/dev/null || yum install -y sudo 2>/dev/null; echo 'cameron ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/ansible-cameron && chmod 440 /etc/sudoers.d/ansible-cameron"
    local root_key_cmd="mkdir -p /root/.ssh && chmod 700 /root/.ssh && grep -qxF '$pub_key' /root/.ssh/authorized_keys 2>/dev/null || echo '$pub_key' >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"

    if sshpass -p "$BOOTSTRAP_PASSWORD" ssh \
            -o StrictHostKeyChecking=no \
            -o PreferredAuthentications=password \
            "root@${host}" "true" 2>/dev/null; then
        sshpass -p "$BOOTSTRAP_PASSWORD" ssh \
            -o StrictHostKeyChecking=no \
            -o PreferredAuthentications=password \
            "root@${host}" "$sudoers_cmd && $root_key_cmd" 2>/dev/null \
            && log "Passwordless sudo configured on $host (via root)" \
            || log "Bootstrap warning: root sudoers write failed on $host"
    else
        if ! sshpass -p "$BOOTSTRAP_PASSWORD" ssh \
                -o StrictHostKeyChecking=no \
                -o PreferredAuthentications=password \
                "cameron@${host}" "which sudo" 2>/dev/null; then
            log "ACTION REQUIRED — $host: sudo not installed and root SSH is disabled."
            log "  SSH in and run: su -c 'apt-get install -y sudo && echo cameron ALL=\(ALL\) NOPASSWD: ALL > /etc/sudoers.d/ansible-cameron && chmod 440 /etc/sudoers.d/ansible-cameron'"
            return 1
        fi

        log "$host: root login unavailable, trying sudo -S via cameron"
        sshpass -p "$BOOTSTRAP_PASSWORD" ssh \
            -o StrictHostKeyChecking=no \
            -o PreferredAuthentications=password \
            "cameron@${host}" \
            "echo '$BOOTSTRAP_PASSWORD' | sudo -S bash -c '$sudoers_cmd'" 2>/dev/null \
            && log "Passwordless sudo configured on $host (via sudo -S)" \
            || log "Bootstrap warning: sudo -S setup failed on $host — password may differ from SSH password"
    fi
}

# Bootstrap a new host: copy SSH key then set up sudo
bootstrap_host() {
    local host=$1
    if [ -z "$BOOTSTRAP_PASSWORD" ]; then
        return 1
    fi

    log "Bootstrapping new host $host..."

    local pub_key
    pub_key=$(cat /root/.ssh/id_ed25519.pub)
    if ! sshpass -p "$BOOTSTRAP_PASSWORD" ssh \
            -o StrictHostKeyChecking=no \
            -o PreferredAuthentications=password \
            "cameron@${host}" \
            "mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -qxF '$pub_key' ~/.ssh/authorized_keys 2>/dev/null || echo '$pub_key' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys" 2>/dev/null; then
        log "Bootstrap failed for $host — could not copy SSH key"
        return 1
    fi

    setup_sudo "$host"
    log "Bootstrap complete for $host"
    return 0
}

# Write a "needs setup" result so a reachable-but-unprivileged host still shows
# on the dashboard (with its hostname) instead of being silently skipped.
write_needs_setup() {
    local host=$1 name
    local reason="${2:-passwordless sudo is not configured (sudo missing and root SSH disabled)}"
    name=$(ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no \
        -i /root/.ssh/id_ed25519 "cameron@${host}" hostname 2>/dev/null)
    [ -z "$name" ] && name="$host"
    jq -n --arg h "$host" --arg n "$name" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --arg r "$reason" \
        '{hostname:$h, display_name:$n, ip_address:$h, os_name:"—", kernel:"",
          timestamp:$ts, updates_available:0, security_updates:0,
          reboot_required:false, status:"needs_setup", last_applied:null,
          applied_packages:[], available_packages:[], setup_reason:$r}' \
        > "$REPORTS_DIR/${host}_update_result.json"
    log "$host ($name): flagged as needs_setup on dashboard"
}

# Re-evaluate and check a single host (dashboard "Rescan"). Works even if the
# host isn't currently in the inventory (e.g. it was needs_setup until fixed):
# re-runs the SSH/sudo decision, then checks it via a one-host inventory.
recheck_host() {
    local host=$1 user=cameron
    local hv="$ANSIBLE_DIR/host_vars/${host}.yml"
    [ -f "$hv" ] && grep -q 'ansible_user: root' "$hv" && user=root

    if check_ssh "$host" "$user"; then
        if [ "$user" = "cameron" ] && ! check_sudo "$host"; then
            setup_sudo "$host"
            if ! check_sudo "$host"; then
                write_needs_setup "$host"
                return 1
            fi
        fi
    elif bootstrap_host "$host"; then
        user=cameron
        if ! check_sudo "$host"; then
            write_needs_setup "$host" "SSH key is set up but passwordless sudo is not configured for cameron"
            return 1
        fi
    else
        write_needs_setup "$host" "host is not reachable over SSH"
        return 1
    fi

    local inv="/tmp/recheck_${host}.yml"
    printf 'all:\n  hosts:\n    %s:\n      ansible_user: %s\n' "$host" "$user" > "$inv"
    acquire_lock
    ansible-playbook "$ANSIBLE_DIR/check-updates-playbook.yml" -i "$inv" -l "$host" \
        2>&1 | tee -a "$LOG_FILE"
    local rc=${PIPESTATUS[0]}
    release_lock
    rm -f "$inv"
    return "$rc"
}

# Generate Ansible inventory (only hosts that are fully reachable/ready)
generate_inventory() {
    local hosts=$1
    local inventory_file="$ANSIBLE_DIR/hosts.yml"
    local reachable=0

    printf 'all:\n  hosts:\n' > "$inventory_file"

    for host in $(echo "$hosts" | tr ',' '\n'); do
        local user=cameron
        local host_vars_file="$ANSIBLE_DIR/host_vars/${host}.yml"
        if [ -f "$host_vars_file" ] && grep -q 'ansible_user: root' "$host_vars_file"; then
            user=root
        fi

        if check_ssh "$host" "$user"; then
            if [ "$user" = "cameron" ] && ! check_sudo "$host"; then
                log "$host: SSH key works but sudo not ready — running sudo setup"
                setup_sudo "$host"
                if ! check_sudo "$host"; then
                    log "Skipping $host — sudo setup failed"
                    write_needs_setup "$host"
                    continue
                fi
            fi
            # Host is fully ready; the check playbook will (over)write its result.
            printf '    %s:\n      ansible_user: %s\n' "$host" "$user" >> "$inventory_file"
            reachable=$((reachable + 1))
        elif bootstrap_host "$host"; then
            # Key copied — but only add it if passwordless sudo actually works,
            # otherwise the check would fail with "Missing sudo password".
            if check_sudo "$host"; then
                printf '    %s:\n      ansible_user: cameron\n' "$host" >> "$inventory_file"
                reachable=$((reachable + 1))
            else
                write_needs_setup "$host" "SSH key is set up but passwordless sudo is not configured for cameron"
            fi
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

# --------------------------------------------------------------------------- #
# CHECK phase: gather available updates (no changes). Optional host limit.
# --------------------------------------------------------------------------- #
run_check() {
    local host=$1 inv="$ANSIBLE_DIR/hosts.yml" limit_arg="" tmp=""
    if [ -n "$host" ]; then
        # Single-host check (e.g. post-apply refresh): use a one-host inventory so
        # it works even if the host isn't in the main hosts.yml yet.
        tmp="/tmp/check_${host}.yml"
        write_host_inventory "$host" "$tmp"
        inv="$tmp"; limit_arg="-l $host"
    fi
    log "Checking for available updates ${host:+on $host}..."
    acquire_lock
    ansible-playbook "$ANSIBLE_DIR/check-updates-playbook.yml" -i "$inv" $limit_arg \
        2>&1 | tee -a "$LOG_FILE"
    local rc=${PIPESTATUS[0]}
    release_lock
    [ -n "$tmp" ] && rm -f "$tmp"
    return "$rc"
}

# --------------------------------------------------------------------------- #
# Approval poller: consumes <host>.workorder.json files
# --------------------------------------------------------------------------- #

# Write a one-host inventory (honouring a host_vars root override). Used by
# apply/reboot/recheck so they don't depend on the main hosts.yml being current
# — a host onboarded via Rescan isn't in hosts.yml until the next full cycle.
write_host_inventory() {
    local host=$1 inv=$2 user=cameron
    local hv="$ANSIBLE_DIR/host_vars/${host}.yml"
    [ -f "$hv" ] && grep -q 'ansible_user: root' "$hv" && user=root
    printf 'all:\n  hosts:\n    %s:\n      ansible_user: %s\n' "$host" "$user" > "$inv"
}

set_host_error() {
    local host=$1 f="$REPORTS_DIR/${1}_update_result.json"
    [ -f "$f" ] || return 0
    local tmp; tmp=$(jq '.status="error"' "$f" 2>/dev/null) && echo "$tmp" > "$f"
}

process_workorder() {
    local wo=$1
    local host action packages source rc queue_reboot=0
    host=$(jq -r '.hostname' "$wo")
    action=$(jq -r '.action' "$wo")
    packages=$(jq -r '(.packages // []) | join(",")' "$wo")
    source=$(jq -r '.source // "dashboard"' "$wo")

    if [ -z "$host" ] || [ "$host" = "null" ]; then
        log "Skipping malformed work order $wo"; rm -f "$wo"; return
    fi

    if [ "$action" = "recheck" ]; then
        log "Rechecking $host (requested via dashboard)"
        touch "$LOCK_FILE"
        if recheck_host "$host"; then
            log "Recheck succeeded for $host"
            python3 /scripts/audit.py --action recheck --host "$host" \
                --source "$source" --result success --detail "rescanned" || true
        else
            log "Recheck for $host: host still not ready (see needs_setup)"
            python3 /scripts/audit.py --action recheck --host "$host" \
                --source "$source" --result failure --detail "still not ready" || true
        fi
        rm -f "$LOCK_FILE"
        rm -f "$wo"
        return
    fi

    log "Processing $action work order for $host (packages: ${packages:-none})"
    local inv="/tmp/wo_${host}.yml"
    write_host_inventory "$host" "$inv"
    touch "$LOCK_FILE"
    acquire_lock
    if [ "$action" = "apply" ]; then
        ansible-playbook "$ANSIBLE_DIR/apply-updates-playbook.yml" -i "$inv" \
            -l "$host" -e "packages=$packages" 2>&1 | tee -a "$LOG_FILE"
        rc=${PIPESTATUS[0]}
    elif [ "$action" = "reboot" ]; then
        ansible-playbook "$ANSIBLE_DIR/reboot-playbook.yml" -i "$inv" \
            -l "$host" 2>&1 | tee -a "$LOG_FILE"
        rc=${PIPESTATUS[0]}
    else
        log "Unknown action '$action' in $wo"; release_lock; rm -f "$LOCK_FILE" "$inv"; rm -f "$wo"; return
    fi
    release_lock
    rm -f "$inv"

    if [ "$rc" -eq 0 ]; then
        log "$action succeeded for $host"
        python3 /scripts/audit.py --action "$action" --host "$host" \
            --packages "$packages" --source "$source" --result success --detail "rc=0" || true
        python3 /scripts/slack_notifier.py --action "$action" --host "$host" \
            --packages "$packages" --result success 2>&1 | tee -a "$LOG_FILE" || true
        run_check "$host" || true   # refresh this host's available-updates list
        # Auto-reboot: if this host is flagged and the fresh check says a reboot is
        # needed, remember to queue one (written below, after this work order is
        # removed, since both share the <host>.workorder.json path).
        if [ "$action" = "apply" ] && is_auto_reboot "$host" \
           && [ "$(jq -r '.reboot_required' "$REPORTS_DIR/${host}_update_result.json" 2>/dev/null)" = "true" ]; then
            queue_reboot=1
        fi
    else
        log "$action FAILED for $host (rc=$rc)"
        python3 /scripts/audit.py --action "$action" --host "$host" \
            --packages "$packages" --source "$source" --result failure --detail "rc=$rc" || true
        python3 /scripts/slack_notifier.py --action "$action" --host "$host" \
            --packages "$packages" --result failure 2>&1 | tee -a "$LOG_FILE" || true
        set_host_error "$host"
    fi
    rm -f "$LOCK_FILE"
    rm -f "$wo"
    if [ "${queue_reboot:-0}" = "1" ]; then
        log "Auto-reboot: queuing reboot for $host"
        jq -n --arg h "$host" \
            '{hostname:$h, action:"reboot", packages:[], requested_at:(now|todate), status:"pending", source:"auto"}' \
            > "$REPORTS_DIR/${host}.workorder.json"
    fi
}

poller_loop() {
    set +e   # a failed work order must never kill the poller
    log "Approval poller started (every ${POLL_INTERVAL}s)"
    while true; do
        for wo in "$REPORTS_DIR"/*.workorder.json; do
            [ -e "$wo" ] || continue
            [ "$(jq -r '.status' "$wo" 2>/dev/null)" = "pending" ] || continue
            process_workorder "$wo"
        done
        sleep "$POLL_INTERVAL"
    done
}

# Queue an apply of all available packages for one host.
autoqueue_host() {
    local host=$1 reason=$2 f="$REPORTS_DIR/${1}_update_result.json"
    [ -e "$f" ] || return 0
    local pkgs
    pkgs=$(jq -r '[.available_packages[].name] | join(",")' "$f")
    [ -z "$pkgs" ] && return 0
    log "Auto-queuing $host ($reason)"
    jq -n --arg h "$host" --arg p "$pkgs" \
        '{hostname:$h, action:"apply", packages:($p|split(",")), requested_at:(now|todate), status:"pending", source:"auto"}' \
        > "$REPORTS_DIR/${host}.workorder.json"
}

# When approval is disabled globally, auto-queue every host.
autoqueue_all() {
    for f in "$REPORTS_DIR"/*_update_result.json; do
        [ -e "$f" ] || continue
        autoqueue_host "$(jq -r '.hostname' "$f")" "REQUIRE_APPROVAL=false"
    done
}

AUTO_FILE="$REPORTS_DIR/auto_update.json"

# Auto-queue only the hosts the operator flagged for automatic updates.
autoqueue_marked() {
    [ -f "$AUTO_FILE" ] || return 0
    local host
    # ".update" is the current key; ".hosts" is the legacy one.
    for host in $(jq -r '(.update // .hosts // [])[]?' "$AUTO_FILE" 2>/dev/null); do
        autoqueue_host "$host" "auto-update enabled"
    done
}

# Is this host flagged for automatic reboot after updates?
is_auto_reboot() {
    [ -f "$AUTO_FILE" ] || return 1
    jq -e --arg h "$1" '(.reboot // []) | index($h)' "$AUTO_FILE" >/dev/null 2>&1
}

# --------------------------------------------------------------------------- #
# A single check cycle (discover -> inventory -> check -> report)
# --------------------------------------------------------------------------- #
run_cycle() {
    touch "$LOCK_FILE"
    log "================================"
    log "Starting check cycle"
    log "================================"

    if HOSTS=$(discover_systems); then
        if generate_inventory "$HOSTS"; then
            run_check "" || log "Check playbook returned non-zero"
            if [ "$REQUIRE_APPROVAL" = "false" ]; then
                autoqueue_all
            else
                autoqueue_marked
            fi
            python3 /scripts/generate_reports.py 2>&1 | tee -a "$LOG_FILE" || true
            python3 /scripts/slack_notifier.py 2>&1 | tee -a "$LOG_FILE" || true
        else
            log "No reachable hosts after inventory generation"
        fi
    else
        log "Skipping check - no hosts discovered"
    fi

    rm -f "$LOCK_FILE"
    log "Check cycle completed. Next cycle in $UPDATE_INTERVAL seconds"
}

# --------------------------------------------------------------------------- #
# Boot: poller in background, then the check loop (early-wake on Scan Now)
# --------------------------------------------------------------------------- #
poller_loop &

while true; do
    rm -f "$TRIGGER_FILE"
    run_cycle

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
