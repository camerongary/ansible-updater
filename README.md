# Ansible Linux Update Manager

Containerized Linux patch management that discovers servers on your local network, applies updates, and reports results via a web dashboard and Slack.

## What it does

1. Runs **nmap** to discover live hosts on a configurable subnet
2. Generates an Ansible inventory and runs `update-playbook.yml`
3. Handles both **Debian/Ubuntu** (`apt dist-upgrade`) and **RedHat/CentOS** (`dnf update`)
4. Saves per-host JSON results and serves a web dashboard (port 8080)
5. Posts a Slack notification summary after each cycle
6. Repeats on a configurable interval (default: 1 hour)

## Requirements

- Docker and Docker Compose on the host machine
- SSH key access (`cameron` user with passwordless sudo) on each target Linux server
- XCP-ng/CentOS targets: root SSH access

## Quick start

```bash
cp .env.example .env
# Edit .env — set NETWORK_RANGE and optionally SLACK_WEBHOOK_URL

docker compose build
docker compose up -d
```

Dashboard: `http://<docker-host>:8080`

## Configuration

All settings live in `.env`:

| Variable | Default | Description |
|---|---|---|
| `NETWORK_RANGE` | `192.168.1.0/24` | CIDR range to scan for hosts |
| `UPDATE_INTERVAL` | `3600` | Seconds between update cycles |
| `SLACK_WEBHOOK_URL` | _(empty)_ | Slack incoming webhook URL |

## SSH key setup

The container mounts `~/.ssh` from the Docker host. Copy the Docker host's public key to each target server:

```bash
# For hosts where you connect as a regular user with sudo:
ssh-copy-id -i ~/.ssh/id_ed25519 cameron@192.168.x.x

# Ensure passwordless sudo on each target:
echo 'cameron ALL=(ALL) NOPASSWD: ALL' | sudo tee /etc/sudoers.d/ansible-cameron
sudo chmod 440 /etc/sudoers.d/ansible-cameron

# For XCP-ng / root-only hosts:
ssh-copy-id -i ~/.ssh/id_ed25519 root@192.168.x.x
```

For hosts that need `root` as the SSH user, create a file in `ansible/host_vars/<ip>.yml`:

```yaml
ansible_user: root
```

## Excluding hosts

Add IPs (one per line) to `ansible/exclude_hosts.txt` to prevent them from entering the inventory. Useful for Mac Minis, routers, or other non-Linux devices that nmap discovers:

```
192.168.1.1
192.168.1.50
```

## Project layout

```
ansible/
  ansible.cfg          # Ansible config (remote user, key, timeouts)
  update-playbook.yml  # Main playbook — Debian + RedHat update logic
  hosts.yml            # Auto-generated inventory (overwritten each cycle)
  exclude_hosts.txt    # IPs to skip during discovery
  host_vars/           # Per-host variable overrides (e.g. ansible_user: root)

scripts/
  start.sh             # Entry point: discover → update → report → sleep → repeat
  web_server.py        # Flask dashboard on port 8080
  generate_reports.py  # HTML report generator
  slack_notifier.py    # Slack webhook notifier

tests/
  conftest.py          # Shared fixtures
  test_generate_reports.py
  test_slack_notifier.py
  test_web_server.py

Dockerfile
docker-compose.yml
.env.example
```

## API endpoints

The Flask server (port 8080) exposes:

| Endpoint | Description |
|---|---|
| `GET /` | HTML dashboard |
| `GET /api/results` | Per-host update results (JSON) |
| `GET /api/stats` | Aggregate statistics (JSON) |
| `GET /health` | Health check |

## Running the tests

```bash
pip install pytest pytest-mock flask
pytest tests/ -v
```

## Common tasks

```bash
# Trigger an update cycle immediately
docker exec ansible-updater ansible-playbook /ansible/update-playbook.yml -i /ansible/hosts.yml

# Run against specific hosts only
docker exec ansible-updater ansible-playbook /ansible/update-playbook.yml \
  -i /ansible/hosts.yml --limit 192.168.1.10,192.168.1.20

# View logs
docker compose logs -f

# Restart
docker compose restart
```

## Notes

- `ansible-core` is pinned to `>=2.14,<2.15` — this version works with both Python 3.6 (XCP-ng/CentOS 8) and Python 3.12 (Debian 13)
- The inventory is regenerated each cycle; manual edits to `hosts.yml` will be overwritten
- Per-host overrides in `ansible/host_vars/` and `ansible/exclude_hosts.txt` persist across cycles
