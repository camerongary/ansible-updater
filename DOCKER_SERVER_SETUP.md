# Setup Guide - Docker Server at 192.168.12.104

## 📍 Your Setup

- **Docker Server IP**: 192.168.12.104
- **Network to Scan**: 192.168.12.0/24
- **Target Servers**: Other systems in 192.168.12.0/24

---

## 🚀 3-Step Deployment on 192.168.12.104

### Step 1: Deploy on Docker Server (SSH into 192.168.12.104)

```bash
# SSH into Docker server
ssh root@192.168.12.104

# Navigate to project directory (or clone/download files)
cd ansible-updater

# Verify .env configuration
cat .env

# Should show:
# NETWORK_RANGE=192.168.12.0/24
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL...
```

### Step 2: Setup SSH Access (On 192.168.12.104)

You need passwordless SSH from the Docker server to target servers:

```bash
# Generate SSH key on Docker server (if not exists)
ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""

# Copy key to EACH target server
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.11
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.15
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.20
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.25
# ... repeat for all target servers

# Or use a loop
for i in {10..50}; do
  ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.$i 2>/dev/null && echo "✓ 192.168.12.$i"
done
```

### Step 3: Start Docker Container (On 192.168.12.104)

```bash
# Build container
docker-compose build

# Start services
docker-compose up -d

# Monitor
docker-compose logs -f

# Wait for first scan cycle (~1-5 minutes)
```

---

## ✅ Verification Checklist

### On Docker Server (192.168.12.104):

```bash
# 1. Can you ping the network gateway?
ping 192.168.12.1
# Should get response

# 2. Can you reach target servers?
ping 192.168.12.10
ping 192.168.12.15
# Should get responses

# 3. Can you SSH to a target?
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "hostname"
# Should show target hostname

# 4. Is Docker running?
docker-compose ps
# Should show: ansible-updater  Up

# 5. Check logs
docker-compose logs | tail -30
# Should show discovery and playbook activity
```

---

## 📊 Network Diagram

```
┌────────────────────────────────────────────────┐
│         192.168.12.0/24 Network               │
├────────────────────────────────────────────────┤
│                                                │
│  192.168.12.1 (Gateway)                       │
│  192.168.12.10 (Server A - Ubuntu)           │
│  192.168.12.11 (Server B - CentOS)           │
│  192.168.12.15 (Server C - Debian)           │
│  192.168.12.20 (Server D - Ubuntu)           │
│  192.168.12.25 (Server E - Ubuntu)           │
│                                                │
│  📦 192.168.12.104 (Docker Server)           │
│     ├─ nmap scans network                    │
│     ├─ SSH to each target                    │
│     ├─ Runs Ansible playbooks                │
│     └─ Posts to Slack ✅                     │
│                                                │
└────────────────────────────────────────────────┘
```

---

## 🔄 How It Works from 192.168.12.104

```
Every UPDATE_INTERVAL seconds:

1. Docker container on 192.168.12.104 starts
2. Runs: nmap -sn 192.168.12.0/24
3. Discovers all live hosts
4. SSH connects to each host from 192.168.12.104
5. Runs: apt update (Debian) or dnf update (RedHat)
6. Collects results
7. Posts to Slack with summaries
8. Sleeps for UPDATE_INTERVAL
9. Repeats
```

---

## ⚠️ Important Notes

### SSH Keys Must Be On 192.168.12.104

```bash
# These commands run ON the Docker server (192.168.12.104)
# NOT on your local machine

# Copy FROM 192.168.12.104 TO target servers
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10

# The SSH key must exist at: /root/.ssh/id_rsa on 192.168.12.104
```

### Network Access

- Docker container has full network access to 192.168.12.0/24
- nmap can scan all hosts
- SSH must be able to reach all targets
- No firewall should block ports 22 (SSH) or 7 (ping)

### Docker Server Doesn't Need Updates

- 192.168.12.104 is excluded from scanning (it won't try to SSH to itself)
- It acts as the scanner/controller
- It only INITIATES updates on other servers

---

## 🧪 Test Before Full Deployment

### Test 1: Network Discovery

```bash
# SSH to Docker server
ssh root@192.168.12.104

# Run nmap manually
nmap -sn 192.168.12.0/24

# Or from inside Docker container:
docker-compose exec ansible-updater nmap -sn 192.168.12.0/24
```

### Test 2: SSH Access

```bash
# From Docker server, test each target
for ip in 192.168.12.{10,11,15,20,25}; do
  echo "Testing $ip:"
  ssh -i ~/.ssh/id_rsa root@$ip "echo OK" && echo "✓ Success" || echo "✗ Failed"
done
```

### Test 3: Ansible Connectivity

```bash
# Run inside container
docker-compose exec ansible-updater \
  ansible all -m ping -i ansible/hosts.yml

# Should show "pong" for each host
```

### Test 4: Manual Update

```bash
# Run playbook immediately
docker-compose exec ansible-updater \
  ansible-playbook ansible/update-playbook.yml \
  -i ansible/hosts.yml -v

# Watch output
```

---

## 📋 SSH Setup Summary

| Step | Location | Command |
|------|----------|---------|
| 1 | 192.168.12.104 | `ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""` |
| 2 | 192.168.12.104 | `ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10` |
| 3 | 192.168.12.104 | `ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.11` |
| 4 | 192.168.12.104 | Repeat for all target servers |
| 5 | 192.168.12.104 | `docker-compose up -d` |

---

## 🔍 Troubleshooting

### Problem: "No hosts discovered"

```bash
# On 192.168.12.104:

# 1. Can you ping the network?
ping 192.168.12.1
ping 192.168.12.10

# 2. Run nmap manually
nmap -sn 192.168.12.0/24

# 3. Check if hosts are actually online
for i in {10..30}; do
  timeout 1 bash -c "echo >/dev/tcp/192.168.12.$i/22" && echo "192.168.12.$i is up"
done
```

### Problem: "SSH connection refused"

```bash
# On 192.168.12.104:

# 1. Test SSH directly
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo OK"

# 2. If fails, copy key again
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10

# 3. Check SSH is running on target
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "systemctl status ssh"

# 4. Check firewall on target
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "ufw status"
```

### Problem: "No Slack messages"

```bash
# On 192.168.12.104:

# 1. Check webhook
grep SLACK .env

# 2. Test webhook manually
python3 test_slack_webhook.py

# 3. Check logs
docker-compose logs | grep -i slack

# 4. View latest report
cat reports/*.json | jq
```

### Problem: "Ansible playbook fails"

```bash
# On 192.168.12.104:

# 1. Test Ansible connectivity
docker-compose exec ansible-updater \
  ansible all -m ping -i ansible/hosts.yml

# 2. Run playbook with verbose output
docker-compose exec ansible-updater \
  ansible-playbook ansible/update-playbook.yml \
  -i ansible/hosts.yml -v

# 3. Check specific host
docker-compose exec ansible-updater \
  ssh -i ~/.ssh/id_rsa root@192.168.12.10 "apt update"
```

---

## 📝 Configuration Files

Your setup:

```
/root/ansible-updater/          (on 192.168.12.104)
├── .env                         (network range + webhook)
├── docker-compose.yml           (1 service)
├── Dockerfile
├── ansible/
│   ├── update-playbook.yml
│   └── ansible.cfg
├── scripts/
│   ├── start.sh
│   ├── slack_notifier.py
│   └── ...
└── reports/                     (results saved here)
```

---

## 🎯 First Run Expected Output

### In Terminal (docker-compose logs -f):
```
ansible-updater | [2024-03-23 10:30:00] Starting Ansible Update Manager
ansible-updater | [2024-03-23 10:30:00] Configuration: NETWORK_RANGE=192.168.12.0/24
ansible-updater | [2024-03-23 10:30:00] Slack webhook configured: YES
ansible-updater | [2024-03-23 10:30:10] Starting network discovery on 192.168.12.0/24...
ansible-updater | [2024-03-23 10:30:15] Discovered hosts: 192.168.12.10,192.168.12.11,192.168.12.15,192.168.12.20,192.168.12.25
ansible-updater | [2024-03-23 10:30:20] Generated inventory
ansible-updater | [2024-03-23 10:30:20] Running update playbook...
ansible-updater | [2024-03-23 10:30:45] PLAY [Update Linux Systems]
ansible-updater | [2024-03-23 10:31:30] Update completed
ansible-updater | [2024-03-23 10:31:35] Report generated
ansible-updater | [2024-03-23 10:31:40] Slack notification sent successfully
```

### In Slack Workspace:
```
🔄 System Update Report
━━━━━━━━━━━━━━━━━━━━━━━
Hosts Scanned:     5
Total Updates:     23
Security Updates:  8
Reboot Required:   2

192.168.12.10  Ubuntu 22.04  5 updates  ✓
192.168.12.11  CentOS 8      12 updates ⚠️
[... more hosts ...]
```

---

## ✅ Quick Checklist

On Docker Server (192.168.12.104):

- [ ] SSH keys generated: `ls ~/.ssh/id_rsa`
- [ ] SSH keys copied to at least 1 target: `ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10`
- [ ] Can SSH without password: `ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo OK"`
- [ ] Can ping targets: `ping 192.168.12.10`
- [ ] Docker installed: `docker --version`
- [ ] Docker Compose installed: `docker-compose --version`
- [ ] Files downloaded
- [ ] .env configured
- [ ] Ready to deploy: `docker-compose up -d`

---

## 🚀 Deployment Command

On Docker Server (192.168.12.104):

```bash
# Navigate to project
cd ansible-updater/

# Build
docker-compose build

# Start
docker-compose up -d

# Monitor
docker-compose logs -f

# Watch for success:
# - "Discovered hosts: X.X.X.X, X.X.X.X, ..."
# - "Running update playbook"
# - "Slack notification sent"
```

---

## 📞 Need Help?

Check these files:
- **NO_DASHBOARD_GUIDE.md** - Monitoring without dashboard
- **NETWORK_SETUP.md** - Network-specific setup
- **DEPLOYMENT_CHECKLIST.md** - Full checklist
- Container logs: `docker-compose logs -f`

---

**You're ready to deploy on 192.168.12.104!** 🚀
