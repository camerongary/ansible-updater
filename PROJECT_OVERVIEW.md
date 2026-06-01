# Ansible Linux Update Manager - Complete Project Overview

## 📦 What You're Getting

A production-ready, containerized Linux update management system that:

1. ✅ **Discovers Linux servers** on your network using nmap
2. ✅ **Applies updates** to both Debian (apt) and RedHat (dnf) systems
3. ✅ **Runs periodically** on a configurable schedule
4. ✅ **Generates beautiful dashboards** showing update status
5. ✅ **Posts to Slack** with summary notifications
6. ✅ **Runs in Docker** for easy deployment

---

## 📁 Complete File Structure

```
ansible-updater/
├── README.md                      # Comprehensive documentation
├── QUICKSTART.md                 # 30-second setup guide
├── Makefile                       # Common tasks (build, run, test, etc.)
├── .env.example                   # Environment configuration template
├── docker-compose.yml             # Multi-container orchestration
├── Dockerfile                     # Container image definition
├── nginx.conf                     # Web server configuration
│
├── ansible/
│   ├── ansible.cfg               # Ansible configuration
│   ├── hosts.yml                 # Generated inventory (auto-created)
│   └── update-playbook.yml       # Main Ansible playbook
│
├── scripts/
│   ├── start.sh                  # Main orchestration script (entry point)
│   ├── generate_reports.py       # HTML report generator
│   ├── slack_notifier.py         # Slack notification sender
│   └── web_server.py             # Flask dashboard server
│
└── reports/                       # Output directory (created at runtime)
    ├── index.html                # Main dashboard page
    ├── *.json                    # Per-host update results
    └── *.json                    # Aggregate results
```

---

## 🔧 Core Components

### 1. **Docker Compose Configuration** (`docker-compose.yml`)
   - **ansible-updater**: Main container running orchestration
   - **ansible-web**: Nginx web server for dashboard
   - Shared volume for reports
   - SSH key mounting for authentication

### 2. **Dockerfile**
   - Ubuntu 22.04 base image
   - Ansible, nmap, Python, Flask
   - All required tools pre-installed
   - Lightweight and efficient

### 3. **Orchestration Script** (`scripts/start.sh`)
   - Runs at container startup
   - Discovers systems with nmap
   - Generates Ansible inventory
   - Runs update playbook
   - Generates reports and Slack notifications
   - Loops with configurable interval

### 4. **Ansible Playbook** (`ansible/update-playbook.yml`)
   - **Debian/Ubuntu tasks**: apt update, dist-upgrade
   - **RedHat/CentOS tasks**: dnf update
   - Security update tracking
   - Reboot requirement detection
   - Per-host statistics collection
   - JSON result generation

### 5. **Web Dashboard** (`scripts/web_server.py`)
   - Flask HTTP server on port 8080
   - Beautiful, responsive HTML interface
   - Auto-refreshing statistics
   - Host-by-host update details
   - REST API endpoints (`/api/results`, `/api/stats`)
   - Nginx serves static files on port 80

### 6. **Report Generator** (`scripts/generate_reports.py`)
   - Creates HTML dashboard from results
   - Aggregate statistics calculation
   - Color-coded host status
   - Professional styling and layout

### 7. **Slack Notifier** (`scripts/slack_notifier.py`)
   - Posts to Slack webhook
   - Beautiful formatted messages
   - Summary statistics
   - Per-host update details
   - Status indicators

---

## 🚀 Quick Start (3 Steps)

### 1. Configure
```bash
cp .env.example .env
# Edit .env - set NETWORK_RANGE and optional SLACK_WEBHOOK_URL
```

### 2. SSH Setup
```bash
# Ensure SSH key access to target servers
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.1.10
```

### 3. Deploy
```bash
docker-compose build
docker-compose up -d
```

**Dashboard**: http://localhost

---

## 📊 How It Works

```
┌─────────────────────────────────────────────┐
│  Container Startup (scripts/start.sh)       │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Network Discovery (nmap)                   │
│  - Scans NETWORK_RANGE                      │
│  - Identifies live Linux servers            │
│  - Generates hosts list                     │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Generate Inventory (ansible/hosts.yml)     │
│  - Categorizes by OS family                 │
│  - Prepares for Ansible                     │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Run Ansible Playbook                       │
│  ├─ Debian Systems: apt update/upgrade      │
│  ├─ RedHat Systems: dnf update              │
│  ├─ Collect statistics                      │
│  └─ Save per-host JSON results              │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│  Generate Reports                           │
│  ├─ HTML Dashboard (index.html)             │
│  ├─ API endpoints (/api/*)                  │
│  └─ Performance metrics                     │
└──────────────┬──────────────────────────────┘
               │
        ┌──────┴──────┐
        ▼             ▼
   [Dashboard]   [Slack Channel]
   (Port 80)      (Webhook)
```

---

## 🔌 API Endpoints

```
GET /                    # HTML dashboard
GET /api/results        # JSON array of all host results
GET /api/stats          # Summary statistics
GET /health             # Health check endpoint
```

### Example Requests

```bash
# Get all results
curl http://localhost:8080/api/results | jq

# Get statistics
curl http://localhost:8080/api/stats | jq

# Response example:
{
  "total_hosts": 5,
  "total_updates": 23,
  "total_security": 8,
  "hosts_needing_reboot": 2,
  "last_updated": "2024-01-15T10:30:00"
}
```

---

## 🎯 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NETWORK_RANGE` | `192.168.1.0/24` | CIDR network to scan |
| `UPDATE_INTERVAL` | `3600` | Seconds between scans |
| `SLACK_WEBHOOK_URL` | (empty) | Slack webhook for notifications |

---

## 🛠️ Common Tasks

### Using Makefile
```bash
make build              # Build containers
make up                 # Start containers
make logs              # View logs
make test-nmap         # Test discovery
make test-ssh          # Test connectivity
make test-slack        # Test Slack
make playbook          # Run updates now
make clean             # Stop and cleanup
```

### Manual Commands
```bash
# View logs
docker-compose logs -f

# Run playbook immediately
docker-compose exec ansible-updater \
  ansible-playbook ansible/update-playbook.yml -i ansible/hosts.yml -v

# Generate report
docker-compose exec ansible-updater python3 /scripts/generate_reports.py

# Test Slack
docker-compose exec ansible-updater python3 /scripts/slack_notifier.py
```

---

## 🔒 Security Notes

1. **SSH Keys**: Use strong passphrases, restrict permissions (600)
2. **Container Access**: Only expose port 80 on trusted networks
3. **Slack Webhooks**: Treat as secrets, rotate periodically
4. **Ansible Privileges**: Requires root/sudo on targets
5. **Network Scanning**: Use appropriate NETWORK_RANGE
6. **Logs**: Check `/var/log/ansible/ansible.log` for audit trail

---

## 📈 Monitoring & Maintenance

### Check Status
```bash
docker-compose ps
docker-compose logs
```

### Restart
```bash
docker-compose restart
```

### View Reports
```bash
ls -la reports/
cat reports/index.html
```

### Clean Old Reports
```bash
find reports -name "*.json" -mtime +30 -delete
```

---

## 🔧 Customization Examples

### Change Update Frequency
In `.env`:
```bash
UPDATE_INTERVAL=1800   # Every 30 minutes
UPDATE_INTERVAL=86400  # Once daily
```

### Scan Multiple Networks
Modify `scripts/start.sh`:
```bash
discover_systems "192.168.1.0/24"
discover_systems "10.0.0.0/24"
```

### Exclude Specific Hosts
Modify `ansible/update-playbook.yml`:
```yaml
pre_tasks:
  - meta: end_host
    when: inventory_hostname in ['192.168.1.100', '192.168.1.101']
```

### Custom SSH Port
Modify `ansible/ansible.cfg`:
```ini
remote_user = root
private_key_file = ~/.ssh/id_rsa
ssh_common_args = -p 2222
```

---

## 🐛 Troubleshooting

### No hosts discovered
```bash
docker-compose exec ansible-updater nmap -sn 192.168.1.0/24
```

### SSH connection fails
```bash
docker-compose exec ansible-updater ssh -v root@192.168.1.10
```

### Ansible playbook errors
```bash
docker-compose logs ansible-updater | grep -i error
```

### Check Slack integration
```bash
docker-compose exec ansible-updater python3 /scripts/slack_notifier.py
```

---

## 📚 File Descriptions

| File | Purpose |
|------|---------|
| `Dockerfile` | Container image with Ansible, nmap, Python |
| `docker-compose.yml` | Multi-container orchestration |
| `scripts/start.sh` | Main loop: discover → scan → report |
| `ansible/update-playbook.yml` | Debian + RedHat update logic |
| `scripts/web_server.py` | Flask dashboard HTTP server |
| `scripts/generate_reports.py` | HTML report generator |
| `scripts/slack_notifier.py` | Slack webhook integration |
| `ansible/ansible.cfg` | Ansible configuration |
| `nginx.conf` | Web server configuration |
| `.env.example` | Environment template |

---

## ✨ Features at a Glance

- ✅ **Multi-distro** - Debian/Ubuntu and RedHat/CentOS/Fedora
- ✅ **Auto-discovery** - nmap-based network scanning
- ✅ **Periodic execution** - Configurable scan intervals
- ✅ **Beautiful dashboard** - Responsive web UI
- ✅ **Slack integration** - Automatic notifications
- ✅ **Containerized** - Docker & Docker Compose
- ✅ **JSON reporting** - Structured data export
- ✅ **REST API** - Programmatic access
- ✅ **Security tracking** - Security updates identified
- ✅ **Reboot detection** - Identifies systems needing restart
- ✅ **High performance** - Parallel execution
- ✅ **Comprehensive logs** - Full audit trail

---

## 🚀 Next Steps

1. Read `QUICKSTART.md` for 30-second setup
2. Review `.env.example` and create `.env`
3. Setup SSH key authentication to targets
4. Run `docker-compose up -d`
5. Access dashboard at http://localhost
6. Configure Slack webhook (optional)
7. Customize as needed

---

**Ready to deploy?** Start with:
```bash
cp .env.example .env
docker-compose up -d
```
