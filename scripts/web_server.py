#!/usr/bin/env python3
"""Interactive update-approval dashboard.

Reads per-host check results from $REPORTS_DIR, lists the available packages per
host, and lets the operator approve specific packages, reject a host's updates,
or approve a reboot. Approvals are written as work-order files that the start.sh
poller picks up and executes with Ansible. Every action is recorded to the audit
log (see audit.py). A "Scan Now" button triggers an immediate check cycle.
"""

import hmac
import json
import os
import glob
import re
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request, abort

import audit

app = Flask(__name__)
REPORTS_DIR = os.environ.get("REPORTS_DIR", "/reports")
# Hosts added manually from the dashboard. start.sh merges these into every
# discovery cycle so they're always managed, even if nmap can't see them.
MANUAL_HOSTS_FILE = os.path.join(REPORTS_DIR, "manual_hosts.txt")

# Files used to coordinate manual scans with the start.sh loop.
TRIGGER_FILE = "/tmp/trigger_scan"
LOCK_FILE = "/tmp/scan_running"

# Auth: reading the dashboard is always open; actions (approve / reject / reboot
# / recheck / scan) require Basic Auth. If no password is configured, actions are
# disabled entirely (the dashboard stays viewable).
DASHBOARD_USER = os.environ.get("DASHBOARD_USER", "admin")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "")

# Small inline clipboard icon for the per-IP copy button.
COPY_ICON = ('<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
             '<rect x="9" y="9" width="11" height="11" rx="2"/>'
             '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>')

# Host names are IPs/hostnames used in filenames; keep them filesystem-safe.
SAFE_HOST_RE = re.compile(r"^[A-Za-z0-9._-]+$")


@app.errorhandler(400)
@app.errorhandler(404)
def _json_error(err):
    return jsonify({"ok": False, "description": getattr(err, "description", str(err))}), err.code


def require_auth():
    """Gate a mutating action. Returns an error response if not allowed, else None."""
    if not DASHBOARD_PASSWORD:
        return jsonify({
            "ok": False,
            "description": "Actions are disabled: no dashboard password is set. "
                           "Set DASHBOARD_PASSWORD in .env to enable approvals and reboots.",
        }), 403
    auth = request.authorization
    ok = bool(auth) and auth.username == DASHBOARD_USER and \
        hmac.compare_digest(auth.password or "", DASHBOARD_PASSWORD)
    if not ok:
        resp = jsonify({"ok": False, "description": "Authentication required."})
        resp.headers["WWW-Authenticate"] = 'Basic realm="Update dashboard"'
        return resp, 401
    return None


# --------------------------------------------------------------------------- #
# Data access
# --------------------------------------------------------------------------- #
def result_path(host):
    return os.path.join(REPORTS_DIR, f"{host}_update_result.json")


def workorder_path(host):
    return os.path.join(REPORTS_DIR, f"{host}.workorder.json")


AUTO_FILE = os.path.join(REPORTS_DIR, "auto_update.json")


def load_settings():
    """Return (auto_update_hosts, auto_reboot_hosts) as sets."""
    try:
        with open(AUTO_FILE) as f:
            d = json.load(f)
        # "hosts" is the legacy key for the auto-update list.
        return set(d.get("update", d.get("hosts", []))), set(d.get("reboot", []))
    except Exception:
        return set(), set()


def save_settings(update_hosts, reboot_hosts):
    try:
        with open(AUTO_FILE, "w") as f:
            json.dump({"update": sorted(update_hosts), "reboot": sorted(reboot_hosts)}, f, indent=2)
    except Exception as e:
        print(f"Error writing {AUTO_FILE}: {e}")


def load_manual_hosts():
    try:
        with open(MANUAL_HOSTS_FILE) as f:
            return [ln.strip() for ln in f if ln.strip()]
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Error reading {MANUAL_HOSTS_FILE}: {e}")
        return []


def save_manual_hosts(hosts):
    try:
        with open(MANUAL_HOSTS_FILE, "w") as f:
            for h in sorted(set(hosts)):
                f.write(h + "\n")
    except Exception as e:
        print(f"Error writing {MANUAL_HOSTS_FILE}: {e}")


def load_results():
    """Load all per-host check results."""
    results = []
    for path in sorted(glob.glob(os.path.join(REPORTS_DIR, "*_update_result.json"))):
        try:
            with open(path) as f:
                results.append(json.load(f))
        except Exception as e:
            print(f"Error loading {path}: {e}")
    results.sort(key=lambda r: r.get("hostname", ""))
    return results


def load_host(host):
    """Load one host's result, or None. Validates the host name first."""
    if not SAFE_HOST_RE.match(host or ""):
        return None
    path = result_path(host)
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def save_host(host, data):
    with open(result_path(host), "w") as f:
        json.dump(data, f, indent=2)


def compute_stats(results):
    return {
        "total_hosts": len(results),
        "total_updates": sum(r.get("updates_available", 0) for r in results),
        "total_security": sum(r.get("security_updates", 0) for r in results),
        "hosts_needing_reboot": sum(1 for r in results if r.get("reboot_required")),
    }


def status_badge(host):
    """Return (css_class, label) for a host's current status."""
    status = host.get("status", "checked")
    if status == "needs_setup":
        return "status-danger", "Action Required"
    if status == "check_failed":
        return "status-danger", "Check Failed"
    if status == "applying":
        return "status-info", "Applying"
    if status == "applied":
        return "status-success", "Applied"
    if status == "rejected":
        return "status-muted", "Rejected"
    if status == "error":
        return "status-danger", "Error"
    # checked
    if host.get("reboot_required"):
        return "status-danger", "Reboot Needed"
    if host.get("updates_available", 0) > 0:
        return "status-warning", "Updates Available"
    return "status-success", "Up to Date"


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    results = load_results()
    stats = compute_stats(results)
    update_interval = os.environ.get("UPDATE_INTERVAL", "3600")
    require_approval = os.environ.get("REQUIRE_APPROVAL", "true").lower() != "false"
    auto_hosts, autoreboot_hosts = load_settings()

    rows = ""
    pkg_data = {}   # hostname -> compact package list, rendered lazily in JS
    for host in results:
        hostname = host.get("hostname", "Unknown")
        display = host.get("display_name") or hostname
        cls, label = status_badge(host)
        packages = host.get("available_packages", [])
        reboot = host.get("reboot_required", False)
        is_auto = hostname in auto_hosts
        is_autoreboot = hostname in autoreboot_hosts
        auto_badge = (
            ('<span class="status-badge status-auto" title="Updates install automatically">Auto-update</span> ' if is_auto else "")
            + ('<span class="status-badge status-autoreboot" title="Reboots automatically after updates">Auto-reboot</span>' if is_autoreboot else "")
        )
        relup = (host.get("release_upgrade") or "").strip()
        relup_badge = f'<span class="status-badge status-relup" title="{relup}">Release upgrade</span> ' if relup else ""
        ip = host.get("ip_address", "N/A")
        copy_btn = (
            f'<button class="copy-btn" title="Copy IP" aria-label="Copy IP" '
            f'onclick="copyIp(event,this,\'{ip}\')">{COPY_ICON}</button>'
            if ip and ip != "N/A" else ""
        )

        if host.get("status") == "needs_setup":
            # Reachable but can't escalate — show the host and how to fix it.
            reason = host.get("setup_reason", "passwordless sudo is not configured")
            cmds = ("# Run as the cameron user (you'll be prompted for cameron's password):\n"
                    "echo 'cameron ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/ansible-cameron\n"
                    "sudo chmod 440 /etc/sudoers.d/ansible-cameron\n"
                    "\n"
                    "# If sudo isn't installed yet, first become root and install it:\n"
                    "#   su -    (then: apt-get install -y sudo || dnf install -y sudo ; exit)")
            detail = f"""
            <tr class="detail-row" id="detail-{hostname}" style="display:none;">
                <td colspan="7">
                    <p style="margin-bottom:8px;color:#c62828;"><strong>Action required:</strong> {reason}.</p>
                    <p style="margin-bottom:10px;color:#666;font-size:13px;">Run on this host's console (or <code>su -</code> from an SSH session). It will be onboarded automatically on the next scan:</p>
                    <button class="copy-cmds-btn" onclick="copyCmds(this,'cmds-{hostname}')">{COPY_ICON} Copy commands</button>
                    <pre id="cmds-{hostname}" style="background:#2d2d2d;color:#eee;padding:14px;border-radius:8px;overflow:auto;font-size:12px;line-height:1.5;">{cmds}</pre>
                    <button class="btn btn-rescan" onclick="recheck('{hostname}')">Rescan this host</button>
                    <button class="btn btn-remove" onclick="removeHost('{hostname}')">Remove from dashboard</button>
                </td>
            </tr>"""
        elif host.get("status") == "check_failed":
            # The update check couldn't run — don't pretend it's up to date.
            reason = host.get("setup_reason") or "dnf could not query updates"
            detail = f"""
            <tr class="detail-row" id="detail-{hostname}" style="display:none;">
                <td colspan="7">
                    <p style="margin-bottom:8px;color:#c62828;"><strong>Update check failed</strong> — this host is not confirmed up to date.</p>
                    <p style="margin-bottom:10px;color:#666;font-size:13px;">Reason: <code>{reason}</code></p>
                    <p style="margin-bottom:12px;color:#666;font-size:13px;">A common cause is no enabled repositories (e.g. a RHEL host that isn't registered). Fix it on the host, then rescan.</p>
                    <button class="btn btn-rescan" onclick="recheck('{hostname}')">Rescan this host</button>
                    <button class="btn btn-remove" onclick="removeHost('{hostname}')">Remove from dashboard</button>
                </td>
            </tr>"""
        else:
            # Package checkboxes are rendered lazily in the browser (on expand) to
            # keep the DOM light when many hosts have large update lists.
            if packages:
                pkg_data[hostname] = [
                    {"n": p.get("name", ""), "c": p.get("current_version", ""),
                     "v": p.get("new_version", ""), "s": 1 if p.get("security") else 0}
                    for p in packages
                ]
                pkg_rows = ""  # filled by renderPkgs() on first expand
            else:
                pkg_rows = '<p class="empty">No packages to update.</p>'

            reboot_btn = (
                f'<button class="btn btn-reboot" onclick="reboot(\'{hostname}\')">Reboot</button>'
                if reboot else ""
            )
            auto_btn = (
                f'<button class="btn {"btn-auto-on" if is_auto else "btn-auto-off"}" '
                f'onclick="setAuto(\'{hostname}\',{str(not is_auto).lower()})">'
                f'{"Auto-update: ON" if is_auto else "Enable auto-update"}</button>'
            )
            autoreboot_btn = (
                f'<button class="btn {"btn-autoreboot-on" if is_autoreboot else "btn-autoreboot-off"}" '
                f'onclick="setAutoReboot(\'{hostname}\',{str(not is_autoreboot).lower()})">'
                f'{"Auto-reboot: ON" if is_autoreboot else "Enable auto-reboot"}</button>'
            )
            auto_note = (
                '<p style="margin-top:10px;color:#1a9d6e;font-size:12px;">'
                + ('Auto-update: installs all available updates automatically each cycle. ' if is_auto else '')
                + ('Auto-reboot: reboots automatically when an update requires it.' if is_autoreboot else '')
                + '</p>'
                if (is_auto or is_autoreboot) else ""
            )
            actions_html = (
                f'<div class="actions">'
                f'<button class="btn btn-approve" onclick="approve(\'{hostname}\')"'
                f'{" disabled" if not packages else ""}>Approve selected</button>'
                f'<button class="btn btn-reject" onclick="reject(\'{hostname}\')">Reject</button>'
                f'{reboot_btn}'
                f'<button class="btn btn-rescan" onclick="recheck(\'{hostname}\')">Rescan</button>'
                f'{auto_btn}'
                f'{autoreboot_btn}'
                f'<button class="btn btn-remove" onclick="removeHost(\'{hostname}\')">Remove</button>'
                f'</div>{auto_note}'
            )
            # For long lists, repeat the actions at the top so you don't have to
            # scroll to the bottom to approve.
            top_actions = f'<div style="margin-bottom:14px;">{actions_html}</div>' if len(packages) > 25 else ""
            relup_note = (
                f'<p style="margin-bottom:8px;color:#a15c00;font-size:13px;"><strong>OS release upgrade available:</strong> '
                f'{relup}. This is a major, manual upgrade (not automated here) — run it on the host:</p>'
                f'<button class="copy-cmds-btn" onclick="copyCmds(this,\'relup-{hostname}\')">{COPY_ICON} Copy command</button>'
                f'<pre id="relup-{hostname}" style="background:#2d2d2d;color:#eee;padding:12px 14px;border-radius:8px;font-size:13px;margin-bottom:12px;">sudo do-release-upgrade</pre>'
                if relup else ""
            )
            detail = f"""
            <tr class="detail-row" id="detail-{hostname}" style="display:none;">
                <td colspan="7">
                    {relup_note}
                    <div class="pkg-toolbar">
                        <button class="link" onclick="selectAll('{hostname}', true)">Select all</button>
                        <button class="link" onclick="selectAll('{hostname}', false)">Clear</button>
                    </div>
                    {top_actions}
                    <div class="pkg-list" id="pkgs-{hostname}">{pkg_rows}</div>
                    {actions_html}
                </td>
            </tr>"""

        rows += f"""
            <tr class="host-row" onclick="toggle('{hostname}')" data-host="{hostname}"
                data-name="{display}" data-os="{host.get('os_name','Unknown')}" data-ip="{ip}"
                data-updates="{host.get('updates_available',0)}" data-security="{host.get('security_updates',0)}"
                data-reboot="{1 if reboot else 0}" data-status="{label}">
                <td><strong>{display}</strong></td>
                <td>{host.get('os_name','Unknown')}</td>
                <td><span class="ip-cell">{ip}</span>{copy_btn}</td>
                <td><span class="number-badge">{host.get('updates_available',0)}</span></td>
                <td><span class="number-badge">{host.get('security_updates',0)}</span></td>
                <td><span class="status-badge {'status-danger' if reboot else 'status-success'}">{'Yes' if reboot else 'No'}</span></td>
                <td><span class="status-badge {cls}">{label}</span> {relup_badge}{auto_badge}</td>
            </tr>{detail}"""

    if not results:
        rows = '<tr><td colspan="7" class="empty">No hosts have been scanned yet</td></tr>'

    mode_banner = (
        "Approval required — nothing is installed until you approve."
        if require_approval
        else "AUTO-APPLY mode — updates are applied automatically each cycle."
    )

    return PAGE.format(
        rows=rows,
        stats=stats,
        mode_banner=mode_banner,
        update_interval=update_interval,
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        auth_enabled="true" if DASHBOARD_PASSWORD else "false",
        pkg_data_json=json.dumps(pkg_data, separators=(",", ":")),
    )


# --------------------------------------------------------------------------- #
# JSON API
# --------------------------------------------------------------------------- #
@app.route("/api/results")
def api_results():
    upd, rbt = load_settings()
    results = load_results()
    for r in results:
        r["auto_update"] = r.get("hostname") in upd
        r["auto_reboot"] = r.get("hostname") in rbt
    return jsonify(results)


@app.route("/api/stats")
def api_stats():
    stats = compute_stats(load_results())
    stats["last_updated"] = datetime.now().isoformat()
    return jsonify(stats)


@app.route("/api/audit")
def api_audit():
    try:
        limit = int(request.args.get("limit", 50))
    except ValueError:
        limit = 50
    records = audit.read(limit=max(1, min(limit, 500)))
    # Enrich each record with the host's friendly name so the activity log can
    # show hostname + IP (the audit log only stores the IP/inventory name).
    namemap = {}
    for r in load_results():
        dn = r.get("display_name")
        if not dn:
            continue
        for key in (r.get("hostname"), r.get("ip_address")):
            if key:
                namemap[key] = dn
    for rec in records:
        dn = namemap.get(rec.get("host", ""))
        if dn:
            rec["display_name"] = dn
    return jsonify(records)


@app.route("/api/approve/<host>", methods=["POST"])
def api_approve(host):
    denied = require_auth()
    if denied:
        return denied
    data = load_host(host)
    if data is None:
        abort(404, description="Unknown host")

    body = request.get_json(silent=True) or {}
    requested = body.get("packages")
    if not isinstance(requested, list) or not requested:
        abort(400, description="Provide a non-empty 'packages' list")

    available = {p.get("name") for p in data.get("available_packages", [])}
    invalid = [p for p in requested if p not in available]
    if invalid:
        abort(400, description=f"Not available on this host: {', '.join(invalid)}")

    with open(workorder_path(host), "w") as f:
        json.dump({
            "hostname": host,
            "action": "apply",
            "packages": requested,
            "requested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": "pending",
            "source": "dashboard",
        }, f, indent=2)

    data["status"] = "applying"
    save_host(host, data)
    audit.append("approve", host, packages=requested, source="dashboard", result="requested",
                 detail=f"{len(requested)} package(s) queued for apply")
    return jsonify({"ok": True, "queued": requested})


@app.route("/api/reject/<host>", methods=["POST"])
def api_reject(host):
    denied = require_auth()
    if denied:
        return denied
    data = load_host(host)
    if data is None:
        abort(404, description="Unknown host")
    data["status"] = "rejected"
    save_host(host, data)
    audit.append("reject", host, packages=[p.get("name") for p in data.get("available_packages", [])],
                 source="dashboard", result="requested", detail="updates rejected by operator")
    return jsonify({"ok": True})


@app.route("/api/reboot/<host>", methods=["POST"])
def api_reboot(host):
    denied = require_auth()
    if denied:
        return denied
    data = load_host(host)
    if data is None:
        abort(404, description="Unknown host")
    with open(workorder_path(host), "w") as f:
        json.dump({
            "hostname": host,
            "action": "reboot",
            "packages": [],
            "requested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": "pending",
            "source": "dashboard",
        }, f, indent=2)
    audit.append("reboot", host, source="dashboard", result="requested", detail="reboot queued")
    return jsonify({"ok": True})


@app.route("/api/remove/<host>", methods=["POST"])
def api_remove(host):
    """Forget a host (e.g. a decommissioned VM): drop its result + work order +
    auto-update settings so it stops showing on the dashboard."""
    denied = require_auth()
    if denied:
        return denied
    if not SAFE_HOST_RE.match(host or ""):
        abort(400, description="Invalid host")
    removed = False
    paths = [result_path(host), workorder_path(host)]
    # also drop apply-history records for this host so it's fully forgotten
    paths += glob.glob(os.path.join(REPORTS_DIR, f"{host}_apply_*.json"))
    for p in paths:
        try:
            if os.path.exists(p):
                os.remove(p)
                removed = True
        except Exception as e:
            print(f"remove: {e}")
    upd, rbt = load_settings()
    if host in upd or host in rbt:
        upd.discard(host)
        rbt.discard(host)
        save_settings(upd, rbt)
    # drop from manually-added hosts too, or it would return on the next cycle
    manual = load_manual_hosts()
    if host in manual:
        save_manual_hosts([h for h in manual if h != host])
    audit.append("remove", host, source="dashboard", result="success", detail="removed from dashboard")
    return jsonify({"ok": True, "removed": removed})


@app.route("/api/addhost", methods=["POST"])
def api_addhost():
    """Manually add one or more hosts (IPs/hostnames). They're persisted to
    manual_hosts.txt (so every cycle checks them) and a check is queued for each
    so they appear within ~15s."""
    denied = require_auth()
    if denied:
        return denied
    body = request.get_json(silent=True) or {}
    raw = body.get("hosts", "")
    tokens = raw if isinstance(raw, list) else re.split(r"[\s,]+", str(raw))
    candidates = [t.strip() for t in tokens if t and t.strip()]
    if not candidates:
        abort(400, description="No hosts provided")
    valid, invalid, seen = [], [], set()
    for c in candidates:
        if not SAFE_HOST_RE.match(c):
            invalid.append(c)
        elif c not in seen:
            seen.add(c)
            valid.append(c)
    if not valid:
        abort(400, description="No valid hosts (use IP addresses or hostnames)")
    existing = set(load_manual_hosts())
    added = [h for h in valid if h not in existing]
    save_manual_hosts(existing | set(valid))
    # queue an immediate check for each so they show up without waiting a cycle
    for h in valid:
        with open(workorder_path(h), "w") as f:
            json.dump({
                "hostname": h, "action": "recheck", "packages": [],
                "requested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "status": "pending", "source": "dashboard",
            }, f, indent=2)
    audit.append("addhost", ",".join(valid), source="dashboard", result="requested",
                 detail=f"added {len(added)} new, queued {len(valid)} check(s)"
                        + (f", ignored {len(invalid)} invalid" if invalid else ""))
    return jsonify({"ok": True, "added": added, "queued": valid, "invalid": invalid,
                    "already_present": [h for h in valid if h not in added]})


@app.route("/api/autoupdate/<host>", methods=["POST"])
def api_autoupdate(host):
    """Enable/disable automatic updates for a host. Body: {"enabled": true|false}."""
    denied = require_auth()
    if denied:
        return denied
    data = load_host(host)
    if data is None:
        abort(404, description="Unknown host")
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    upd, rbt = load_settings()
    if enabled:
        upd.add(host)
    else:
        upd.discard(host)
    save_settings(upd, rbt)
    audit.append("autoupdate", host, source="dashboard", result="requested",
                 detail="auto-update " + ("enabled" if enabled else "disabled"))
    return jsonify({"ok": True, "enabled": enabled})


@app.route("/api/autoreboot/<host>", methods=["POST"])
def api_autoreboot(host):
    """Enable/disable automatic reboot after updates. Body: {"enabled": true|false}."""
    denied = require_auth()
    if denied:
        return denied
    data = load_host(host)
    if data is None:
        abort(404, description="Unknown host")
    enabled = bool((request.get_json(silent=True) or {}).get("enabled"))
    upd, rbt = load_settings()
    if enabled:
        rbt.add(host)
    else:
        rbt.discard(host)
    save_settings(upd, rbt)
    audit.append("autoreboot", host, source="dashboard", result="requested",
                 detail="auto-reboot " + ("enabled" if enabled else "disabled"))
    return jsonify({"ok": True, "enabled": enabled})


@app.route("/api/recheck/<host>", methods=["POST"])
def api_recheck(host):
    """Re-evaluate and re-check a single host (e.g. after enabling sudo)."""
    denied = require_auth()
    if denied:
        return denied
    data = load_host(host)
    if data is None:
        abort(404, description="Unknown host")
    with open(workorder_path(host), "w") as f:
        json.dump({
            "hostname": host,
            "action": "recheck",
            "packages": [],
            "requested_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "status": "pending",
            "source": "dashboard",
        }, f, indent=2)
    audit.append("recheck", host, source="dashboard", result="requested", detail="rescan requested")
    return jsonify({"ok": True})


@app.route("/api/scan", methods=["POST"])
def trigger_scan():
    """Trigger an immediate check cycle (picked up by the start.sh loop)."""
    denied = require_auth()
    if denied:
        return denied
    if os.path.exists(LOCK_FILE):
        return jsonify({"status": "already_running"}), 409
    Path(TRIGGER_FILE).touch()
    return jsonify({"status": "triggered"}), 202


@app.route("/api/scan/status")
def scan_status():
    return jsonify({
        "running": os.path.exists(LOCK_FILE),
        "queued": os.path.exists(TRIGGER_FILE),
    })


@app.route("/api/whoami", methods=["POST"])
def api_whoami():
    """Validate credentials and return the username (used by the login UI)."""
    denied = require_auth()
    if denied:
        return denied
    return jsonify({"ok": True, "user": DASHBOARD_USER})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


# --------------------------------------------------------------------------- #
# HTML template (kept as a module-level string to avoid Flask templates dir)
# --------------------------------------------------------------------------- #
PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>System Update Approvals</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
       background:linear-gradient(135deg,#667eea 0%,#764ba2 100%); min-height:100vh; padding:20px; }}
.container {{ max-width:1200px; margin:0 auto; }}
.banner {{ background:rgba(255,255,255,0.15); color:#fff; padding:12px; border-radius:8px;
          margin-bottom:20px; text-align:center; font-size:13px; }}
header {{ background:#fff; padding:30px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,.1); margin-bottom:30px; }}
header h1 {{ color:#333; margin-bottom:8px; }}
header p {{ color:#666; font-size:14px; }}
.scan-btn {{ background:#667eea; color:#fff; border:none; padding:10px 22px; border-radius:8px;
            font-size:14px; font-weight:600; cursor:pointer; margin-top:12px; }}
.scan-btn:hover:not(:disabled) {{ background:#5a6fd6; }}
.scan-btn:disabled {{ opacity:.6; cursor:not-allowed; }}
.scan-btn.running {{ background:#f39c12; }}
.stats-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:20px; margin-bottom:30px; }}
.stat-card {{ background:#fff; padding:25px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,.1); text-align:center; }}
.stat-card h3 {{ color:#666; font-size:13px; text-transform:uppercase; letter-spacing:.5px; margin-bottom:10px; }}
.stat-card .value {{ font-size:34px; font-weight:bold; color:#667eea; }}
.panel {{ background:#fff; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,.1); overflow:hidden; margin-bottom:30px; }}
.panel-header {{ background:#f8f9fa; padding:18px 30px; border-bottom:1px solid #e9ecef; }}
.panel-header h2 {{ color:#333; font-size:17px; }}
table {{ width:100%; border-collapse:collapse; }}
thead {{ background:#f8f9fa; }}
th {{ padding:14px 30px; text-align:left; font-weight:600; color:#666; font-size:12px;
     text-transform:uppercase; letter-spacing:.5px; border-bottom:2px solid #e9ecef; }}
td {{ padding:14px 30px; border-bottom:1px solid #e9ecef; color:#555; }}
.host-row {{ cursor:pointer; }}
.host-row:hover {{ background:#f8f9fa; }}
.sortable {{ cursor:pointer; user-select:none; white-space:nowrap; }}
.sortable:hover {{ color:#667eea; }}
.sort-ind {{ margin-left:5px; font-size:10px; color:#667eea; }}
.detail-row td {{ background:#fbfbfd; }}
.status-badge {{ display:inline-block; padding:5px 11px; border-radius:20px; font-size:11px;
                font-weight:600; text-transform:uppercase; letter-spacing:.4px; }}
.status-success {{ background:#e8f9f0; color:#1a9d6e; }}
.status-warning {{ background:#fff8e1; color:#f39c12; }}
.status-danger {{ background:#ffebee; color:#c62828; }}
.status-info {{ background:#e7f1ff; color:#2563eb; }}
.status-auto {{ background:#e8f9f0; color:#1a9d6e; }}
.status-autoreboot {{ background:#fff8e1; color:#b8860b; }}
.status-relup {{ background:#fde7d3; color:#a15c00; }}
.status-muted {{ background:#eceff1; color:#607d8b; }}
.number-badge {{ background:#f0f0f0; padding:4px 8px; border-radius:4px; font-weight:600; color:#333; }}
.ip-cell {{ font-variant-numeric:tabular-nums; }}
.copy-btn {{ background:none; border:none; cursor:pointer; color:#aaa; padding:2px 5px; margin-left:6px; vertical-align:middle; border-radius:4px; }}
.copy-btn:hover {{ color:#667eea; background:#f0f0f0; }}
.copy-btn.copied {{ color:#1a9d6e; }}
.pkg-toolbar {{ margin-bottom:10px; }}
.pkg-list {{ display:flex; flex-direction:column; gap:6px; margin-bottom:14px; }}
.pkg {{ display:flex; align-items:center; gap:10px; font-size:13px; }}
.pkg-name {{ font-weight:600; color:#333; min-width:160px; }}
.pkg-ver {{ color:#888; font-family:monospace; font-size:12px; }}
.actions {{ display:flex; gap:10px; flex-wrap:wrap; }}
.btn {{ border:none; padding:8px 16px; border-radius:6px; font-size:13px; font-weight:600; cursor:pointer; color:#fff; }}
.btn-approve {{ background:#1a9d6e; }}
.btn-reject {{ background:#c62828; }}
.btn-reboot {{ background:#f39c12; }}
.btn-rescan {{ background:#667eea; }}
.btn-remove {{ background:#fff; color:#c62828; border:1px solid #c62828; }}
.btn-auto-on {{ background:#1a9d6e; }}
.btn-auto-off {{ background:#fff; color:#1a9d6e; border:1px solid #1a9d6e; }}
.btn-autoreboot-on {{ background:#b8860b; }}
.btn-autoreboot-off {{ background:#fff; color:#b8860b; border:1px solid #b8860b; }}
.btn:disabled {{ opacity:.5; cursor:not-allowed; }}
.link {{ background:none; border:none; color:#667eea; cursor:pointer; font-size:12px; margin-right:12px; }}
.empty {{ text-align:center; padding:30px; color:#999; }}
.audit-item {{ display:flex; gap:14px; align-items:center; padding:10px 30px; border-bottom:1px solid #f0f0f0; font-size:13px; }}
.audit-ts {{ color:#999; font-family:monospace; font-size:12px; min-width:150px; }}
.audit-host {{ font-weight:600; color:#333; min-width:200px; }}
.audit-ip {{ font-weight:400; color:#888; font-family:monospace; font-size:12px; }}
.audit-item.expandable {{ cursor:pointer; }}
.audit-item.expandable:hover {{ background:#fafafa; }}
.audit-caret {{ color:#bbb; width:12px; display:inline-block; }}
.audit-pkgs {{ padding:8px 30px 12px 56px; background:#fafafa; border-bottom:1px solid #f0f0f0; font-size:12px; color:#444; line-height:1.7; }}
.audit-pkgs .pk {{ display:inline-block; background:#eef; border:1px solid #dde; border-radius:4px; padding:1px 7px; margin:2px 4px 2px 0; font-family:monospace; }}
.audit-date {{ cursor:pointer; padding:9px 30px; background:#f3f4f8; border-bottom:1px solid #e6e8ef; font-weight:600; color:#444; font-size:13px; user-select:none; }}
.audit-date:hover {{ background:#eceef5; }}
.audit-date-caret {{ color:#888; display:inline-block; width:12px; }}
.audit-date-count {{ color:#999; font-weight:400; font-size:12px; margin-left:6px; }}
.footer {{ text-align:center; margin-top:10px; color:#fff; font-size:13px; }}
.auth-area {{ float:right; font-size:13px; }}
.auth-area .signed {{ color:#666; margin-right:10px; }}
.auth-area button {{ background:none; border:1px solid #667eea; color:#667eea; border-radius:6px; padding:4px 12px; font-size:12px; cursor:pointer; }}
.auth-area button:hover {{ background:#667eea; color:#fff; }}
.copy-btn.copied {{ color:#1a9d6e; background:#e8f9f0; }}
.copy-tip {{ color:#1a9d6e; font-size:12px; font-weight:500; margin-left:4px; }}
.copy-cmds-btn {{ display:inline-flex; align-items:center; gap:5px; background:#f5f5f5; border:1px solid #ccc; color:#555; border-radius:6px; padding:5px 12px; font-size:12px; cursor:pointer; margin-bottom:8px; }}
.copy-cmds-btn:hover {{ background:#ececec; }}
.copy-cmds-btn.copied {{ color:#1a9d6e; border-color:#1a9d6e; background:#e8f9f0; }}
.login-overlay {{ display:none; position:fixed; inset:0; background:rgba(0,0,0,0.45); align-items:center; justify-content:center; z-index:1000; }}
.login-box {{ background:#fff; padding:28px 30px; border-radius:12px; width:340px; max-width:90vw; box-shadow:0 10px 30px rgba(0,0,0,.25); }}
.login-label {{ display:block; font-size:12px; color:#666; margin:10px 0 4px; text-transform:uppercase; letter-spacing:.4px; }}
.login-input {{ width:100%; padding:9px 10px; border:1px solid #ccc; border-radius:6px; font-size:14px; }}
.pass-row {{ display:flex; gap:8px; }}
.pass-row .login-input {{ flex:1; }}
.show-btn {{ border:1px solid #ccc; background:#f5f5f5; border-radius:6px; padding:0 12px; font-size:12px; cursor:pointer; color:#555; }}
.show-btn:hover {{ background:#ececec; }}
.login-err {{ color:#c62828; font-size:13px; min-height:18px; margin-top:8px; }}
.login-actions {{ display:flex; gap:10px; margin-top:8px; }}
</style>
</head>
<body>
<div class="container">
  <div class="banner">{mode_banner} &nbsp;|&nbsp; Check cycle: {update_interval}s</div>
  <header>
    <div id="authArea" class="auth-area"></div>
    <h1>System Update Approvals</h1>
    <p>Last rendered: {now}</p>
    <button id="scanBtn" class="scan-btn">Scan Now</button>
    <button id="addHostBtn" class="scan-btn" style="background:#1a9d6e;" onclick="showAddHost()">Add Host</button>
  </header>
  <div class="stats-grid">
    <div class="stat-card"><h3>Total Hosts</h3><div class="value">{stats[total_hosts]}</div></div>
    <div class="stat-card"><h3>Updates Available</h3><div class="value">{stats[total_updates]}</div></div>
    <div class="stat-card"><h3>Security Updates</h3><div class="value">{stats[total_security]}</div></div>
    <div class="stat-card"><h3>Reboot Required</h3><div class="value">{stats[hosts_needing_reboot]}</div></div>
  </div>
  <div class="panel">
    <div class="panel-header"><h2>Hosts &mdash; click a row to review packages</h2></div>
    <table>
      <thead><tr>
        <th class="sortable" onclick="sortBy('name','text')">Hostname<span class="sort-ind" data-k="name"></span></th>
        <th class="sortable" onclick="sortBy('os','text')">OS<span class="sort-ind" data-k="os"></span></th>
        <th class="sortable" onclick="sortBy('ip','ip')">IP<span class="sort-ind" data-k="ip"></span></th>
        <th class="sortable" onclick="sortBy('updates','num')">Updates<span class="sort-ind" data-k="updates"></span></th>
        <th class="sortable" onclick="sortBy('security','num')">Security<span class="sort-ind" data-k="security"></span></th>
        <th class="sortable" onclick="sortBy('reboot','num')">Reboot<span class="sort-ind" data-k="reboot"></span></th>
        <th class="sortable" onclick="sortBy('status','text')">Status<span class="sort-ind" data-k="status"></span></th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
  <div class="panel">
    <div class="panel-header"><h2>Recent Activity</h2></div>
    <div id="audit"><p class="empty">Loading&hellip;</p></div>
  </div>
  <div class="footer"><p>Automated System Update Monitor</p></div>
</div>
<div id="loginOverlay" class="login-overlay">
  <div class="login-box">
    <h3 style="margin-bottom:14px;color:#333;">Dashboard login</h3>
    <label class="login-label">Username</label>
    <input id="loginUser" class="login-input" type="text" value="admin" autocomplete="username" onkeydown="loginKey(event)">
    <label class="login-label">Password</label>
    <div class="pass-row">
      <input id="loginPass" class="login-input" type="password" autocomplete="current-password" onkeydown="loginKey(event)">
      <button type="button" id="loginShow" class="show-btn" onclick="toggleLoginPass()">Show</button>
    </div>
    <div id="loginErr" class="login-err"></div>
    <div class="login-actions">
      <button class="btn btn-approve" onclick="loginSubmit()">Log in</button>
      <button class="btn" style="background:#9aa0a6;" onclick="hideLogin(false)">Cancel</button>
    </div>
  </div>
</div>
<div id="addHostOverlay" class="login-overlay">
  <div class="login-box" style="width:420px;">
    <h3 style="margin-bottom:6px;color:#333;">Add host(s)</h3>
    <p style="color:#666;font-size:13px;margin-bottom:6px;">Enter one or more IP addresses or hostnames — one per line (or separated by spaces/commas). Each is checked over SSH within ~15s and added to every scan cycle.</p>
    <textarea id="addHostInput" class="login-input" rows="6" placeholder="192.168.12.50&#10;192.168.12.51&#10;server.local" style="resize:vertical;font-family:monospace;" onkeydown="addHostKey(event)"></textarea>
    <div id="addHostErr" class="login-err"></div>
    <div class="login-actions">
      <button class="btn btn-approve" onclick="addHostSubmit()">Add</button>
      <button class="btn" style="background:#9aa0a6;" onclick="hideAddHost()">Cancel</button>
    </div>
  </div>
</div>
<script>
var PKGDATA = {pkg_data_json};
function renderPkgs(h) {{
  var c = document.getElementById('pkgs-' + h);
  if (!c || c.dataset.loaded === '1' || !PKGDATA[h]) return;
  c.innerHTML = PKGDATA[h].map(function(p) {{
    return '<label class="pkg"><input type="checkbox" value="' + p.n + '"' + (p.s ? ' checked' : '') +
      '><span class="pkg-name">' + p.n + '</span>' +
      '<span class="pkg-ver">' + p.c + ' \\u2192 ' + p.v + '</span>' +
      (p.s ? '<span class="status-badge status-danger">security</span>' : '') + '</label>';
  }}).join('');
  c.dataset.loaded = '1';
}}
function toggle(h) {{
  var el = document.getElementById('detail-' + h);
  var showing = el.style.display === 'none';
  if (showing) renderPkgs(h);
  el.style.display = showing ? 'table-row' : 'none';
}}
var sortState = {{key:null, dir:1, type:'text'}};
function ipKey(s) {{
  var p = (s || '').split('.');
  if (p.length === 4 && p.every(function(o){{ return /^[0-9]+$/.test(o); }}))
    return p.map(function(o){{ return ('00' + o).slice(-3); }}).join('');
  return (s || '').toLowerCase();
}}
function sortBy(key, type, forceDir) {{
  if (forceDir !== undefined) sortState = {{key:key, dir:forceDir, type:type}};
  else {{ sortState.dir = (sortState.key === key && sortState.dir === 1) ? -1 : 1; sortState.key = key; sortState.type = type; }}
  try {{ sessionStorage.setItem('sort', JSON.stringify(sortState)); }} catch(e) {{}}
  var tbody = document.querySelector('.panel table tbody');
  if (!tbody) return;
  var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr.host-row'));
  if (!rows.length) return;
  var dir = sortState.dir;
  rows.sort(function(a, b) {{
    var av = a.dataset[key] || '', bv = b.dataset[key] || '', c;
    if (type === 'num') c = (parseFloat(av) || 0) - (parseFloat(bv) || 0);
    else if (type === 'ip') {{ var ak = ipKey(av), bk = ipKey(bv); c = ak < bk ? -1 : ak > bk ? 1 : 0; }}
    else c = av.toLowerCase().localeCompare(bv.toLowerCase());
    return c * dir;
  }});
  rows.forEach(function(hr) {{
    tbody.appendChild(hr);
    var d = document.getElementById('detail-' + hr.dataset.host);
    if (d) tbody.appendChild(d);
  }});
  var arrow = dir === 1 ? '▲' : '▼';
  document.querySelectorAll('.sort-ind').forEach(function(s) {{ s.textContent = (s.dataset.k === key) ? arrow : ''; }});
}}
function restoreSort() {{
  try {{ var s = JSON.parse(sessionStorage.getItem('sort')); if (s && s.key) sortBy(s.key, s.type, s.dir); }} catch(e) {{}}
}}
restoreSort();
var CHECK_SVG = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12l5 5 9-11"/></svg>';
function copyIp(ev, btn, ip) {{
  ev.stopPropagation();
  function flash() {{
    if (btn.dataset.busy) return;
    btn.dataset.busy = '1';
    var orig = btn.innerHTML;
    btn.classList.add('copied');
    btn.innerHTML = CHECK_SVG + '<span class="copy-tip">Copied!</span>';
    setTimeout(function(){{ btn.innerHTML = orig; btn.classList.remove('copied'); delete btn.dataset.busy; }}, 1200);
  }}
  // navigator.clipboard only works in secure contexts (https/localhost); fall
  // back to execCommand for plain-HTTP LAN access.
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(ip).then(flash).catch(function(){{ if (fallbackCopy(ip)) flash(); }});
  }} else {{
    if (fallbackCopy(ip)) flash();
  }}
}}
function fallbackCopy(text) {{
  var ta = document.createElement('textarea');
  ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta); ta.focus(); ta.select();
  var ok = false; try {{ ok = document.execCommand('copy'); }} catch (e) {{}}
  document.body.removeChild(ta); return ok;
}}
function copyCmds(btn, id) {{
  var el = document.getElementById(id);
  if (!el) return;
  var text = el.textContent;
  function done() {{
    if (btn.dataset.busy) return;
    btn.dataset.busy = '1';
    var orig = btn.innerHTML;
    btn.classList.add('copied');
    btn.innerHTML = CHECK_SVG + ' Copied!';
    setTimeout(function(){{ btn.innerHTML = orig; btn.classList.remove('copied'); delete btn.dataset.busy; }}, 1200);
  }}
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(text).then(done).catch(function(){{ if (fallbackCopy(text)) done(); }});
  }} else {{
    if (fallbackCopy(text)) done();
  }}
}}
function selectAll(h, val) {{
  var c = document.getElementById('pkgs-' + h);
  if (c) c.querySelectorAll('input[type=checkbox]').forEach(function(x){{ x.checked = val; }});
  event.stopPropagation();
}}
function selected(h) {{
  var c = document.getElementById('pkgs-' + h);
  if (!c) return [];
  return Array.from(c.querySelectorAll('input:checked')).map(function(x){{ return x.value; }});
}}
var AUTH_ENABLED = ({auth_enabled});
function authHeader() {{
  var a = sessionStorage.getItem('auth');
  return a ? {{'Authorization': a}} : {{}};
}}
var _loginResolve = null;
function showLogin() {{
  return new Promise(function(resolve) {{
    _loginResolve = resolve;
    document.getElementById('loginUser').value = sessionStorage.getItem('authUser') || 'admin';
    var pf = document.getElementById('loginPass');
    pf.value = ''; pf.type = 'password';
    document.getElementById('loginShow').textContent = 'Show';
    document.getElementById('loginErr').textContent = '';
    document.getElementById('loginOverlay').style.display = 'flex';
    pf.focus();
  }});
}}
function hideLogin(ok) {{
  document.getElementById('loginOverlay').style.display = 'none';
  renderAuth();
  var r = _loginResolve; _loginResolve = null;
  if (r) r(!!ok);
}}
function toggleLoginPass() {{
  var f = document.getElementById('loginPass'), b = document.getElementById('loginShow');
  if (f.type === 'password') {{ f.type = 'text'; b.textContent = 'Hide'; }}
  else {{ f.type = 'password'; b.textContent = 'Show'; }}
}}
function loginKey(ev) {{ if (ev.key === 'Enter') loginSubmit(); }}
function loginSubmit() {{
  var u = document.getElementById('loginUser').value;
  var p = document.getElementById('loginPass').value;
  var hdr = 'Basic ' + btoa(u + ':' + p);
  document.getElementById('loginErr').textContent = 'Checking\\u2026';
  fetch('/api/whoami', {{method:'POST', headers: {{'Authorization': hdr}}}}).then(function(r){{
    if (r.ok) {{
      sessionStorage.setItem('auth', hdr);
      sessionStorage.setItem('authUser', u);
      hideLogin(true);
    }} else {{
      document.getElementById('loginErr').textContent = (r.status === 401) ? 'Invalid username or password.' : 'Login failed.';
    }}
  }}).catch(function(){{ document.getElementById('loginErr').textContent = 'Login failed.'; }});
}}
function renderAuth() {{
  var el = document.getElementById('authArea');
  if (!el) return;
  if (!AUTH_ENABLED) {{ el.innerHTML = ''; return; }}
  if (sessionStorage.getItem('auth')) {{
    var u = sessionStorage.getItem('authUser') || 'admin';
    el.innerHTML = '<span class="signed">Signed in as <strong>' + u + '</strong></span>' +
                   '<button onclick="logout()">Log out</button>';
  }} else {{
    el.innerHTML = '<button onclick="showLogin()">Log in</button>';
  }}
}}
function logout() {{
  sessionStorage.removeItem('auth'); sessionStorage.removeItem('authUser'); renderAuth();
}}
function post(url, body, retried) {{
  var headers = Object.assign({{'Content-Type':'application/json'}}, authHeader());
  return fetch(url, {{method:'POST', headers: headers, body: JSON.stringify(body||{{}})}})
    .then(function(r){{
      if (r.status === 401 && !retried) {{
        sessionStorage.removeItem('auth'); sessionStorage.removeItem('authUser'); renderAuth();
        return showLogin().then(function(ok){{
          if (ok) return post(url, body, true);
          return {{ok:false, status:401, body:{{description:'Login required.'}}}};
        }});
      }}
      if (r.ok) renderAuth();   // a successful action means we're authenticated
      return r.json().then(function(j){{ return {{ok:r.ok, status:r.status, body:j}}; }})
        .catch(function(){{ return {{ok:r.ok, status:r.status, body:{{}}}}; }});
    }});
}}
function approve(h) {{
  var pkgs = selected(h);
  if (!pkgs.length) {{ alert('Select at least one package.'); return; }}
  post('/api/approve/' + h, {{packages: pkgs}}).then(function(res){{
    if (!res.ok) {{ alert('Error: ' + (res.body.description || JSON.stringify(res.body))); return; }}
    location.reload();
  }});
}}
function reject(h) {{
  if (!confirm('Reject all updates for ' + h + '?')) return;
  post('/api/reject/' + h, {{}}).then(function(){{ location.reload(); }});
}}
function reboot(h) {{
  if (!confirm('Queue a reboot for ' + h + '?')) return;
  post('/api/reboot/' + h, {{}}).then(function(){{ location.reload(); }});
}}
function recheck(h) {{
  post('/api/recheck/' + h, {{}}).then(function(res){{
    if (!res.ok) {{ alert('Error: ' + (res.body.description || JSON.stringify(res.body))); return; }}
    alert('Rescan queued for ' + h + '. It runs within ~15s — refresh shortly.');
  }});
}}
function removeHost(h) {{
  if (!confirm('Remove ' + h + ' from the dashboard?\\n\\nUse this for a decommissioned host. If the host still exists and is reachable, it will reappear on the next scan.')) return;
  post('/api/remove/' + h, {{}}).then(function(res){{
    if (!res.ok) {{ alert('Error: ' + (res.body.description || JSON.stringify(res.body))); return; }}
    location.reload();
  }});
}}
function showAddHost() {{
  document.getElementById('addHostErr').textContent = '';
  document.getElementById('addHostInput').value = '';
  document.getElementById('addHostOverlay').style.display = 'flex';
  document.getElementById('addHostInput').focus();
}}
function hideAddHost() {{ document.getElementById('addHostOverlay').style.display = 'none'; }}
function addHostKey(e) {{
  if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {{ addHostSubmit(); }}
  else if (e.key === 'Escape') {{ hideAddHost(); }}
}}
function addHostSubmit() {{
  var val = document.getElementById('addHostInput').value.trim();
  if (!val) {{ document.getElementById('addHostErr').textContent = 'Enter at least one host.'; return; }}
  post('/api/addhost', {{hosts: val}}).then(function(res){{
    if (!res.ok) {{ document.getElementById('addHostErr').textContent = 'Error: ' + (res.body.description || JSON.stringify(res.body)); return; }}
    var b = res.body || {{}};
    var q = (b.queued || []).length;
    var msg = 'Queued ' + q + ' host(s) for checking.';
    if (b.invalid && b.invalid.length) msg += '\\nIgnored invalid: ' + b.invalid.join(', ');
    hideAddHost();
    alert(msg + '\\nThey will appear within ~15s — refresh shortly.');
  }});
}}
function setAuto(h, enabled) {{
  if (enabled && !confirm('Automatically install ALL available updates on ' + h + ' every cycle?')) return;
  post('/api/autoupdate/' + h, {{enabled: enabled}}).then(function(res){{
    if (!res.ok) {{ alert('Error: ' + (res.body.description || JSON.stringify(res.body))); return; }}
    location.reload();
  }});
}}
function setAutoReboot(h, enabled) {{
  if (enabled && !confirm('Automatically REBOOT ' + h + ' when an update requires it?')) return;
  post('/api/autoreboot/' + h, {{enabled: enabled}}).then(function(res){{
    if (!res.ok) {{ alert('Error: ' + (res.body.description || JSON.stringify(res.body))); return; }}
    location.reload();
  }});
}}
function badge(result) {{
  var cls = result === 'success' ? 'status-success' : result === 'failure' ? 'status-danger' : 'status-info';
  return '<span class="status-badge ' + cls + '">' + result + '</span>';
}}
function toggleAudit(idx) {{
  var el = document.getElementById('audit-pkgs-' + idx);
  if (!el) return;
  var open = el.style.display === 'none';
  el.style.display = open ? 'block' : 'none';
  var caret = el.previousElementSibling.querySelector('.audit-caret');
  if (caret) caret.innerHTML = open ? '&#9662;' : '&#9656;';
}}
function toggleDate(gidx) {{
  var el = document.getElementById('audit-group-' + gidx);
  if (!el) return;
  var open = el.style.display === 'none';
  el.style.display = open ? 'block' : 'none';
  var caret = el.previousElementSibling.querySelector('.audit-date-caret');
  if (caret) caret.innerHTML = open ? '&#9662;' : '&#9656;';
}}
function auditRow(it, idx) {{
  var hasPkgs = it.packages && it.packages.length;
  var pk = hasPkgs ? (it.packages.length + ' pkg') : '';
  // Show hostname and IP when we know the friendly name; fall back to IP only.
  var nameHtml = (it.display_name && it.display_name !== it.host)
    ? (it.display_name + ' <span class="audit-ip">' + it.host + '</span>')
    : it.host;
  var caret = hasPkgs ? '<span class="audit-caret">&#9656;</span>' : '<span class="audit-caret"></span>';
  // Show time-of-day within a date group (the date is in the group header).
  var tod = (it.ts || '').indexOf('T') >= 0 ? it.ts.split('T')[1].slice(0,8) : it.ts;
  var row = '<div class="audit-item' + (hasPkgs ? ' expandable" onclick="toggleAudit(' + idx + ')"' : '"') + '>' +
    caret +
    '<span class="audit-ts">' + tod + '</span>' +
    '<span class="status-badge status-info">' + it.action + '</span>' +
    '<span class="audit-host">' + nameHtml + '</span>' +
    '<span>' + pk + '</span>' + badge(it.result) +
    '<span style="color:#999;">' + (it.detail || '') + '</span></div>';
  if (hasPkgs) {{
    var label = it.action === 'apply' ? (it.result === 'success' ? 'Applied' : 'Attempted') : 'Packages';
    var chips = it.packages.map(function(p){{ return '<span class="pk">' + p + '</span>'; }}).join('');
    row += '<div class="audit-pkgs" id="audit-pkgs-' + idx + '" style="display:none;">' +
           '<strong>' + label + ' (' + it.packages.length + '):</strong> ' + chips + '</div>';
  }}
  return row;
}}
function loadAudit() {{
  fetch('/api/audit?limit=50').then(function(r){{ return r.json(); }}).then(function(items){{
    var c = document.getElementById('audit');
    if (!items.length) {{ c.innerHTML = '<p class="empty">No activity yet.</p>'; return; }}
    // API returns oldest-first; show newest first, grouped by date.
    var rev = items.slice().reverse();
    var groups = [];
    rev.forEach(function(it){{
      var d = (it.ts || '').slice(0, 10) || 'unknown';
      if (!groups.length || groups[groups.length - 1].date !== d) groups.push({{date: d, items: []}});
      groups[groups.length - 1].items.push(it);
    }});
    var html = '', idx = 0;
    groups.forEach(function(g, gidx){{
      var collapsed = gidx !== 0;   // newest day open, older days collapsed
      html += '<div class="audit-date" onclick="toggleDate(' + gidx + ')">' +
        '<span class="audit-date-caret">' + (collapsed ? '&#9656;' : '&#9662;') + '</span> ' +
        g.date + '<span class="audit-date-count">' + g.items.length + ' event' + (g.items.length === 1 ? '' : 's') + '</span></div>';
      html += '<div class="audit-group" id="audit-group-' + gidx + '"' + (collapsed ? ' style="display:none;"' : '') + '>';
      g.items.forEach(function(it){{ html += auditRow(it, idx++); }});
      html += '</div>';
    }});
    c.innerHTML = html;
  }});
}}
// Poll the audit log only while the tab is visible — a backgrounded tab left
// open for a long time shouldn't keep working (and accumulating memory).
var auditTimer = null;
function startAudit() {{ if (!auditTimer) {{ loadAudit(); auditTimer = setInterval(loadAudit, 15000); }} }}
function stopAudit() {{ if (auditTimer) {{ clearInterval(auditTimer); auditTimer = null; }} }}
document.addEventListener('visibilitychange', function() {{ if (document.hidden) stopAudit(); else startAudit(); }});
if (!document.hidden) startAudit();

// ---- Auth indicator ----
// If we have stored credentials, validate them once so the indicator is accurate.
if (AUTH_ENABLED && sessionStorage.getItem('auth')) {{
  fetch('/api/whoami', {{method:'POST', headers: authHeader()}}).then(function(r){{
    if (!r.ok) {{ sessionStorage.removeItem('auth'); sessionStorage.removeItem('authUser'); }}
    renderAuth();
  }}).catch(renderAuth);
}} else {{
  renderAuth();
}}

// ---- Scan Now ----
var scanBtn = document.getElementById('scanBtn');
var pollInterval = null, wasActive = false;
function setScanState(s) {{
  if (s === 'idle')   {{ scanBtn.textContent = 'Scan Now'; scanBtn.disabled = false; scanBtn.classList.remove('running'); }}
  if (s === 'queued') {{ scanBtn.textContent = 'Queued...'; scanBtn.disabled = true; scanBtn.classList.add('running'); }}
  if (s === 'running'){{ scanBtn.textContent = 'Scanning...'; scanBtn.disabled = true; scanBtn.classList.add('running'); }}
}}
function pollScan() {{
  fetch('/api/scan/status').then(function(r){{ return r.json(); }}).then(function(d){{
    if (d.running) {{ wasActive = true; setScanState('running'); }}
    else if (d.queued) {{ wasActive = true; setScanState('queued'); }}
    else {{
      setScanState('idle'); clearInterval(pollInterval); pollInterval = null;
      if (wasActive) {{ wasActive = false; location.reload(); }}
    }}
  }});
}}
scanBtn.addEventListener('click', function() {{
  wasActive = true; setScanState('queued');
  post('/api/scan', {{}}).then(function(res){{
    if (!res.ok && res.status !== 409) {{
      wasActive = false; setScanState('idle');
      alert('Error: ' + (res.body.description || 'could not start scan'));
      return;
    }}
    if (res.status === 409) setScanState('running');
    if (!pollInterval) pollInterval = setInterval(pollScan, 3000);
  }});
}});
pollScan();
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"Starting dashboard on 0.0.0.0:8080 (REPORTS_DIR={REPORTS_DIR})")
    app.run(host="0.0.0.0", port=8080, debug=False)
