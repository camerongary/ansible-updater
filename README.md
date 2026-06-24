# Ansible Linux Update Manager

A containerized system for discovering Linux servers on your network, **listing the
available updates per host**, and applying them **only after you approve them** from a web
dashboard. Supports Debian and RedHat-based systems (Fedora/dnf5 and yum-based CentOS 7 / XCP-ng), with
authentication, an audit trail, and Slack notifications.

## How it works

The system runs a **check → approve/reject → apply** workflow instead of blindly applying
updates:

1. **Check (automatic, read-only):** every cycle, nmap discovers hosts and an Ansible
   playbook gathers the list of upgradable packages on each one (matching what `dnf upgrade`
   / `apt upgrade` would actually do). **Nothing is installed.**
2. **Review & approve (you):** the dashboard lists every available package per host. You
   pick which packages to install (security updates are pre-selected) and click **Approve**,
   or **Reject** the host's updates entirely.
3. **Apply (automatic, on approval):** a background poller installs **only the approved
   packages** on that host, re-checks it, and records the result.
4. **Reboot (separately approved):** if a host needs a reboot, a **Reboot** button appears.
   Reboots never happen automatically.

Every action — approve, reject, apply, reboot, recheck — is written to an append-only audit
log and shown in the dashboard's "Recent Activity" panel.

> **Per-host auto-update / auto-reboot:** you can flag individual trusted hosts to install
> **all** their available updates automatically each cycle (Enable auto-update in the host's
> panel), and optionally to **reboot automatically** when an update requires it (Enable
> auto-reboot) — while every other host still requires manual approval.
>
> **Legacy global auto-apply:** set `REQUIRE_APPROVAL=false` to auto-apply on *every* host
> each cycle. Reboots still require approval (per-host auto-reboot aside).

## Features

- **Multi-distribution** — Debian/Ubuntu (apt), RedHat/Fedora (dnf/dnf5), and yum-based (CentOS 7 / XCP-ng)
- **Automatic discovery & onboarding** — periodic nmap scans; new hosts are bootstrapped
  (SSH key + passwordless sudo) automatically where possible
- **Per-package approval** — choose exactly which packages to install on each host
- **Per-host auto-update / auto-reboot** — flag trusted hosts to patch (and optionally reboot) themselves
- **Separate reboot approval** — reboot a host only when you say so
- **Accurate state** — a host that can't be checked (e.g. unregistered RHEL / no repos)
  shows **Check Failed** instead of a misleading "up to date"; a reachable-but-unprivileged
  host shows **Action Required** with the exact fix commands
- **Per-host rescan** — re-check a single host on demand (e.g. right after fixing it)
- **Release-upgrade detection** — flags Ubuntu hosts with a new OS release / EOL (the upgrade itself stays manual)
- **Dashboard authentication** — viewing is open; actions require login (Basic Auth)
- **Audit log** — append-only JSONL trail of every action, surfaced in the UI
- **Slack integration** — cycle summaries plus per-host apply/reboot notifications
- **Dashboard niceties** — sortable columns, copy-to-clipboard IPs, signed-in indicator
- **Containerized** — single Docker Compose service (Ansible + dashboard)

## Architecture

Everything runs in one container. The Flask dashboard and the Ansible runner share the
`/reports` volume and coordinate through files there (work orders + results) — no extra
service or database. The dashboard only writes work orders; the orchestrator does the
privileged SSH/Ansible work, so the web layer stays unprivileged.

```
┌──────────────────────────────────────────────┐
│  Docker Host (192.168.12.30)                   │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │  ansible-updater container                 │ │
│  │  ├─ start.sh        orchestrator           │ │
│  │  │   ├─ nmap discovery + bootstrap         │ │
│  │  │   ├─ CHECK playbook (gather updates)    │ │
│  │  │   └─ poller → APPLY / REBOOT / RECHECK  │ │
│  │  └─ web_server.py   dashboard :8080        │ │
│  │         (approve / reject / reboot, audit) │ │
│  └──────────────────────────────────────────┘ │
│                  │  shared /reports volume      │
└──────────────────┼────────────┬────────────────┘
                   ↓            ↓
            [Linux Servers]  [Slack API]
```

## Prerequisites

- Docker and Docker Compose
- Passwordless SSH access (keys) from the Docker host to the target servers
- Root/sudo on target servers to install updates
- (Optional) Slack incoming webhook URL

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
nano .env
```

```bash
NETWORK_RANGE=192.168.12.0/24
UPDATE_INTERVAL=3600
REQUIRE_APPROVAL=true                 # check-only until you approve; false = legacy auto-apply
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
DASHBOARD_USER=admin                  # login for dashboard actions
DASHBOARD_PASSWORD=<choose-a-strong-password>
DASHBOARD_URL=http://192.168.12.30:8080   # used in Slack "View Full Report" links
TZ=America/Los_Angeles
BOOTSTRAP_PASSWORD=                   # optional: auto-onboard new hosts (see below)
```

### 2. Set up SSH keys

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519     # if you don't have one
ssh-copy-id -i ~/.ssh/id_ed25519 cameron@<server-ip>
```

### 3. Build and start

```bash
docker compose build
docker compose up -d
```

### 4. Open the dashboard

Browse to **`http://<docker-host>:8080`** (e.g. `http://192.168.12.30:8080`).
Click a host row to expand its package list, then **Approve selected** / **Reject** /
**Reboot**. The first action prompts you to log in (see Authentication).

### 5. View logs

```bash
docker compose logs -f ansible-updater
```

## Authentication

Viewing the dashboard is always open; **actions** (approve, reject, reboot, recheck, scan)
require Basic Auth.

- Credentials come from `DASHBOARD_USER` / `DASHBOARD_PASSWORD` in `.env`.
- The UI shows **"Signed in as &lt;user&gt;"** with a **Log out** button; a login modal
  prompts for the password (masked, with a Show/Hide toggle). Credentials are held per
  browser session.
- If `DASHBOARD_PASSWORD` is **empty**, the dashboard is still viewable but every action is
  disabled with a clear message — so you can't accidentally run it wide open.

> Note: Basic Auth over plain HTTP sends credentials base64-encoded (not encrypted). It's
> intended for a trusted LAN. For exposure beyond the LAN, put it behind HTTPS.

## Configuration

| Variable             | Default                          | Purpose                                                          |
|----------------------|----------------------------------|------------------------------------------------------------------|
| `NETWORK_RANGE`      | `192.168.1.0/24`                 | CIDR range nmap scans for hosts                                  |
| `UPDATE_INTERVAL`    | `3600`                           | Seconds between check cycles                                     |
| `REQUIRE_APPROVAL`   | `true`                           | `true` = check-only until approved; `false` = legacy auto-apply  |
| `SLACK_WEBHOOK_URL`  | _(empty)_                        | Incoming webhook; leave empty to disable Slack                   |
| `DASHBOARD_USER`     | `admin`                          | Username for dashboard actions                                   |
| `DASHBOARD_PASSWORD` | _(empty)_                        | Password for actions; empty = actions disabled (view-only)       |
| `DASHBOARD_URL`      | `http://192.168.12.30:8080`      | Base URL used in Slack "View Full Report" links                  |
| `TZ`                 | `America/Los_Angeles`            | Container timezone (for dashboard/Slack timestamps)              |
| `BOOTSTRAP_PASSWORD` | _(empty)_                        | Password used to auto-onboard new hosts (copy key + set sudo)    |

### Slack webhook

1. Create one at https://api.slack.com/messaging/webhooks (Create New App → enable Incoming
   Webhooks → copy the URL).
2. Put it in `.env` as `SLACK_WEBHOOK_URL`.

## Host onboarding & states

New hosts are discovered automatically. A host is managed once it's reachable by the SSH key
**and** has passwordless sudo. Hosts the system can't fully use are surfaced on the dashboard
rather than hidden:

| Status            | Meaning                                                                          |
|-------------------|----------------------------------------------------------------------------------|
| **Up to Date / Updates Available** | Checked normally; ready to approve.                             |
| **Action Required** (`needs_setup`) | Reachable by SSH key but passwordless sudo isn't set up. The detail panel shows the one-time fix commands; run them, then click **Rescan this host**. |
| **Check Failed**  | The update check couldn't run — e.g. an unregistered RHEL box with no enabled repos. Shown red with the reason, so it isn't mistaken for "up to date". |
| **Reboot Needed** | Updates applied; a reboot is pending (click **Reboot**).                          |

`BOOTSTRAP_PASSWORD` lets the system auto-copy the SSH key and configure passwordless sudo
on a freshly discovered host. To skip a host entirely, add its IP to
`ansible/exclude_hosts.txt`.

### RedHat / dnf notes

- The check uses `dnf` in check mode, so it reflects the real upgrade transaction (including
  obsoletes/replacements and dependency installs that `dnf check-update` misses).
- The apply imports the distro GPG keys (`/etc/pki/rpm-gpg/*`) first, so signed packages
  validate without disabling `gpgcheck`. (If a host's packages are signed by a key it doesn't
  have — e.g. an unregistered RHEL pulling from a mirror — import the correct key or register
  the system.)

## API endpoints

The dashboard is served on port `8080`. `GET` endpoints are open; `POST` actions require
Basic Auth.

| Method & path                | Description                                             |
|------------------------------|---------------------------------------------------------|
| `GET  /`                     | HTML dashboard                                          |
| `GET  /api/results`          | All per-host check results (incl. `available_packages`)|
| `GET  /api/stats`            | Aggregate statistics                                   |
| `GET  /api/audit?limit=N`    | Recent audit-log entries, newest first                 |
| `POST /api/approve/<host>`   | `{ "packages": ["openssl", ...] }` → queue an apply    |
| `POST /api/reject/<host>`    | Mark the host's updates rejected                       |
| `POST /api/reboot/<host>`    | Queue a reboot for the host                            |
| `POST /api/autoupdate/<host>`| `{ "enabled": true\|false }` → toggle auto-update      |
| `POST /api/autoreboot/<host>`| `{ "enabled": true\|false }` → toggle auto-reboot      |
| `POST /api/recheck/<host>`   | Re-check a single host now (re-evaluates SSH/sudo too) |
| `POST /api/scan`             | Trigger an immediate full discovery + check cycle      |
| `GET  /api/scan/status`      | Whether a scan is queued/running                       |
| `POST /api/whoami`           | Validate credentials (used by the login UI)            |
| `GET  /health`               | Health check                                           |

```bash
curl http://192.168.12.30:8080/api/stats
# { "total_hosts": 5, "total_updates": 23, "total_security": 8,
#   "hosts_needing_reboot": 2, "last_updated": "..." }

# An action requires credentials:
curl -u admin:<password> -X POST http://192.168.12.30:8080/api/recheck/192.168.12.10
```

## Directory structure

```
├── Dockerfile                       # Container image (ansible-core, nmap, sshpass, flask)
├── docker-compose.yml               # Compose service (publishes :8080)
├── .env.example                     # Environment template
├── DEPLOY.md                        # Update / rollback / host-onboarding notes
├── ansible/
│   ├── ansible.cfg                  # become=True (sudo), id_ed25519, etc.
│   ├── check-updates-playbook.yml   # Gather available updates (no changes)
│   ├── apply-updates-playbook.yml   # Install approved packages on one host
│   ├── reboot-playbook.yml          # Reboot one approved host
│   ├── bootstrap.yml                # Sudo/key bootstrap helper
│   ├── exclude_hosts.txt            # IPs to skip during discovery
│   ├── host_vars/                   # Per-host overrides (e.g. ansible_user: root)
│   ├── templates/
│   │   └── host_result.json.j2      # Renders per-host check result JSON
│   └── hosts.yml                    # Inventory (generated at runtime)
├── scripts/
│   ├── start.sh                     # Orchestrator: dashboard + check loop + poller
│   ├── web_server.py                # Flask dashboard (auth, sorting, login modal, etc.)
│   ├── audit.py                     # Append-only audit log (import + CLI)
│   ├── generate_reports.py          # Static HTML report generator
│   └── slack_notifier.py            # Slack notifications
└── reports/                         # Shared volume (git-ignored)
    ├── <host>_update_result.json    # Per-host check result
    ├── <host>.workorder.json        # Pending approve/reboot/recheck work order
    ├── audit_log.jsonl              # Append-only audit trail
    └── <host>_apply_<ts>.json       # Apply history records
```

## Deploying / updating

The app is tracked in git; deploy by pulling and rebuilding on the Docker host (see
`DEPLOY.md` for the full flow, rollback, and host onboarding):

```bash
ssh <docker-host>
cd <repo>/ansible-updater
git pull
docker compose build && docker compose up -d
```

`.env` (secrets) and `reports/` (runtime data) are git-ignored, so they survive updates.

## Maintenance

```bash
docker compose ps
docker compose logs ansible-updater -n 50
docker compose restart
docker compose down

# prune old report artifacts (keeps audit_log.jsonl)
find ./reports -name "*_update_result.json" -mtime +30 -delete
```

## Troubleshooting

**No hosts discovered**
```bash
docker compose exec ansible-updater nmap -sn 192.168.12.0/24
```

**SSH / connectivity**
```bash
docker compose exec ansible-updater ansible all -i /ansible/hosts.yml -m ping
```

**A host shows "Action Required"** — it needs passwordless sudo. Expand the row for the exact
commands, run them on the host, then click **Rescan this host**.

**A host shows "Check Failed"** — the check couldn't run (often an unregistered RHEL box with
no repos). The detail panel shows the reason. Fix repos/registration on the host, then rescan.

**Approvals not applying** — check the poller picked up the work order:
```bash
docker compose logs ansible-updater | grep -i "work order"
ls reports/*.workorder.json          # pending orders waiting to be processed
cat reports/audit_log.jsonl          # what actually ran, with results
```

**RedHat apply fails on GPG ("Public key … is not installed")** — the package-signing key
isn't trusted on the host. Import the correct key (or register the system), then re-approve.

**Slack not working**
```bash
docker compose exec ansible-updater curl -X POST \
  -H 'Content-type: application/json' --data '{"text":"test"}' "$SLACK_WEBHOOK_URL"
```

## Security considerations

⚠️ This tool has privileged SSH access to your systems.

1. **Dashboard password** — set `DASHBOARD_PASSWORD`; without it, actions are disabled. Basic
   Auth is plain-HTTP, so keep the dashboard on a trusted LAN (or front it with HTTPS).
2. **SSH keys** — protect with a passphrase; restrict access.
3. **Network** — keep it on an isolated/management network.
4. **Secrets** — `.env` holds the Slack webhook, dashboard and bootstrap passwords, and is
   git-ignored; rotate credentials periodically.
5. **Audit** — review `reports/audit_log.jsonl` and `/var/log/ansible/updater.log`.

## License

MIT License — feel free to use and modify.
