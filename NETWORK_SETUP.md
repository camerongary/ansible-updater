# Setup Guide for 192.168.12.0/24 Network

## ✅ Network Configuration Complete

Your system is now configured for your actual network:
- **Network**: 192.168.12.0/24
- **Subnet Mask**: 255.255.255.0
- **Gateway**: 192.168.12.1 (typical)
- **Host Range**: 192.168.12.2 to 192.168.12.254
- **Broadcast**: 192.168.12.255

---

## 🚀 Quick Start (5 Minutes)

### Step 1: Verify Configuration (1 minute)

```bash
# Check your configuration
cat .env
```

You should see:
```
NETWORK_RANGE=192.168.12.0/24
UPDATE_INTERVAL=3600
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Step 2: Setup SSH Access (2 minutes)

The system needs SSH access to your servers. Configure passwordless authentication:

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""

# Copy key to EACH server in your network
# Replace with actual IP addresses from your 192.168.12.0/24 range
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.10
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.11
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.12
# ... repeat for all servers

# Or use a loop for multiple servers
for i in {10..20}; do
  ssh-copy-id -i ~/.ssh/id_rsa root@192.168.12.$i
done
```

### Step 3: Start the System (1 minute)

```bash
# Build container
docker-compose build

# Start all services
docker-compose up -d

# Verify running
docker-compose ps
```

### Step 4: Monitor (1 minute)

```bash
# Watch logs
docker-compose logs -f

# Or view specific logs
docker-compose logs ansible-updater | tail -20
```

---

## 🔍 Network Discovery Process

Here's what happens when the system starts:

```
Step 1: Network Scan
├─ Runs: nmap -sn 192.168.12.0/24
├─ Finds: All live hosts in your network
└─ Result: List of IP addresses

Step 2: Host Identification
├─ Attempts SSH connection to each host
├─ Checks OS (Debian vs RedHat)
└─ Result: Categorized inventory

Step 3: Update Execution
├─ Debian hosts: apt update && apt upgrade
├─ RedHat hosts: dnf upgrade
└─ Result: Statistics per host

Step 4: Slack Notification
├─ Collects results
├─ Formats message
├─ Sends to Slack webhook
└─ Result: Message in your workspace

Step 5: Dashboard Update
├─ Generates HTML report
├─ Saves JSON results
├─ Updates API endpoints
└─ Result: View at http://localhost
```

---

## 📝 Your Network Hosts

### Find All Hosts in 192.168.12.0/24

```bash
# Quick scan to see what's on your network
nmap -sn 192.168.12.0/24

# Or use the container to scan
docker-compose exec ansible-updater nmap -sn 192.168.12.0/24
```

### Expected Output
```
Host discovery
Nmap scan report for 192.168.12.1
Host is up (0.001s latency).
Nmap scan report for 192.168.12.10
Host is up (0.005s latency).
Nmap scan report for 192.168.12.15
Host is up (0.003s latency).
...
```

### Common Hosts in Your Network

| IP Address | Typical Host |
|------------|--------------|
| 192.168.12.1 | Router/Gateway |
| 192.168.12.2-9 | Reserved |
| 192.168.12.10+ | Servers/Workstations |

---

## 🔧 SSH Setup Details

### For Each Server You Want to Update

```bash
# 1. Verify SSH access
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo Connected"

# 2. Allow Ansible (passwordless sudo if not root)
# On the server:
sudo visudo
# Add this line:
# ansible ALL=(ALL) NOPASSWD: ALL

# 3. Test Ansible connectivity
docker-compose exec ansible-updater \
  ansible all -m ping -i ansible/hosts.yml
```

### SSH Troubleshooting

```bash
# Test connection
ssh -v -i ~/.ssh/id_rsa root@192.168.12.10

# Common issues:
# - Connection refused: SSH not running on target
# - Permission denied: Wrong key or user
# - Network unreachable: Host offline or firewall blocking

# Check if SSH is running
ssh root@192.168.12.10 "systemctl status ssh"

# Check if firewall allows SSH
ssh root@192.168.12.10 "ufw status"
```

---

## 🎯 First Run - What to Expect

### Timeline

| Time | Event | Where to Check |
|------|-------|----------------|
| T+0s | Docker starts | `docker-compose ps` |
| T+5s | Services ready | `curl http://localhost` |
| T+30s | Discovery starts | `docker-compose logs` |
| T+60s | nmap completes | Logs show host count |
| T+60-300s | Updates run | Logs show "Running playbook" |
| T+300s+ | Slack message | Check Slack workspace |
| T+3600s | Next cycle | Repeats (UPDATE_INTERVAL) |

### View Progress

```bash
# Real-time logs
docker-compose logs -f ansible-updater

# Look for:
# ✓ "Starting network discovery"
# ✓ "Discovered hosts: [IP addresses]"
# ✓ "Running playbook"
# ✓ "Update completed"
# ✓ "Slack notification sent"
```

---

## 📊 What You'll See

### In Your Browser (http://localhost)

```
🔄 System Update Report
━━━━━━━━━━━━━━━━━━━━━━━━
Hosts Scanned:      5
Total Updates:      23
Security Updates:   8
Reboot Required:    2

[Table showing each host]
192.168.12.10  Ubuntu 22.04  5 updates  2 security  NO
192.168.12.11  CentOS 8      12 updates 4 security  YES
192.168.12.15  Debian 11     0 updates  0 security  NO
192.168.12.20  Ubuntu 20.04  6 updates  2 security  YES
192.168.12.25  Ubuntu 22.04  0 updates  0 security  NO
```

### In Your Slack Channel

```
🔄 System Update Report
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Hosts Scanned:     5
Total Updates:     23
Security Updates:  8
Reboot Required:   2

🟡 192.168.12.10
    Ubuntu 22.04 | Updates: 5 | Security: 2 | Reboot: NO

🔴 192.168.12.11
    CentOS 8 | Updates: 12 | Security: 4 | Reboot: YES

🟢 192.168.12.15
    Debian 11 | Updates: 0 | Security: 0 | Reboot: NO

🟡 192.168.12.20
    Ubuntu 20.04 | Updates: 6 | Security: 2 | Reboot: YES

🟢 192.168.12.25
    Ubuntu 22.04 | Updates: 0 | Security: 0 | Reboot: NO
```

---

## 🛠️ Configuration Options

### Change Scan Frequency

Edit `.env`:
```bash
UPDATE_INTERVAL=1800    # Every 30 minutes
UPDATE_INTERVAL=900     # Every 15 minutes  
UPDATE_INTERVAL=86400   # Once daily
```

Then restart:
```bash
docker-compose restart
```

### Scan Different Network

If you have multiple subnets, edit `scripts/start.sh`:

```bash
# Scan multiple networks
discover_systems "192.168.12.0/24"
discover_systems "192.168.13.0/24"
discover_systems "10.0.0.0/24"
```

### Exclude Specific Hosts

Edit `ansible/update-playbook.yml`:

```yaml
pre_tasks:
  - name: Skip excluded hosts
    meta: end_host
    when: inventory_hostname in ['192.168.12.50', '192.168.12.100']
```

---

## 🔐 Security for Your Network

### 1. SSH Key Setup
```bash
# Restrict key permissions
chmod 600 ~/.ssh/id_rsa
chmod 700 ~/.ssh
```

### 2. Firewall Rules
```bash
# On your network, allow:
# - Port 22 (SSH) to Ansible host from 192.168.12.0/24
# - Port 80 (Dashboard) for dashboard access
# - Port 8080 (API) if accessing externally
```

### 3. Network Segmentation
```bash
# Consider running on bastion/admin host
# Don't expose dashboard to untrusted networks
# Use VPN or internal network only
```

---

## 🧪 Testing Your Network Configuration

### Test 1: Can you reach the network?

```bash
# Ping gateway
ping 192.168.12.1

# Scan network
nmap -sn 192.168.12.0/24

# Check SSH to one host
ssh root@192.168.12.10 "hostname"
```

### Test 2: Does Docker have network access?

```bash
# From container
docker-compose exec ansible-updater ping 192.168.12.1
docker-compose exec ansible-updater nmap -sn 192.168.12.0/24
```

### Test 3: Can Ansible reach hosts?

```bash
# Test connectivity
docker-compose exec ansible-updater \
  ansible all -m ping -i ansible/hosts.yml

# Should show each host with "pong" response
```

### Test 4: Manual update on one host

```bash
# Test on 192.168.12.10
docker-compose exec ansible-updater \
  ansible-playbook ansible/update-playbook.yml \
  -i 192.168.12.10, -v
```

---

## 📊 Expected Results

### After First Scan (Success Scenario)

```
✅ Discovered 5 hosts:
   - 192.168.12.10 (Ubuntu 22.04 LTS)
   - 192.168.12.11 (CentOS 8)
   - 192.168.12.15 (Debian 11)
   - 192.168.12.20 (Ubuntu 20.04 LTS)
   - 192.168.12.25 (Ubuntu 22.04 LTS)

✅ Updates completed:
   - 192.168.12.10: 5 updates (2 security)
   - 192.168.12.11: 12 updates (4 security)
   - 192.168.12.15: 0 updates (up to date)
   - 192.168.12.20: 6 updates (2 security)
   - 192.168.12.25: 0 updates (up to date)

✅ Summary:
   - Total updates: 23
   - Security updates: 8
   - Hosts needing reboot: 2

✅ Slack message posted successfully
✅ Dashboard updated: http://localhost
```

---

## ⚠️ Common Issues & Solutions

### Issue 1: "No hosts discovered"

**Cause**: Network unreachable or scan timeout

**Solution**:
```bash
# 1. Test network access
ping 192.168.12.1
ping 192.168.12.10

# 2. Run nmap manually
nmap -sn 192.168.12.0/24

# 3. Check network range
# Make sure 192.168.12.0/24 is correct for your network

# 4. Check container has network access
docker-compose exec ansible-updater ping 192.168.12.1
```

### Issue 2: "SSH connection refused"

**Cause**: SSH not running or firewall blocking

**Solution**:
```bash
# 1. Check SSH is running on target
ssh root@192.168.12.10 "systemctl status ssh"

# 2. Check SSH key works
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo OK"

# 3. Check firewall
ssh root@192.168.12.10 "sudo ufw status"
ssh root@192.168.12.10 "sudo iptables -L | grep 22"
```

### Issue 3: "Updates won't run"

**Cause**: Insufficient permissions or package manager issues

**Solution**:
```bash
# 1. Test sudo access
ssh root@192.168.12.10 "sudo apt update"

# 2. Check if other installs are running
ssh root@192.168.12.10 "ps aux | grep apt"

# 3. Check package manager is not locked
ssh root@192.168.12.10 "sudo lsof /var/lib/apt/lists/lock"
```

### Issue 4: "No Slack messages"

**Solution**:
```bash
# 1. Check webhook URL
grep SLACK .env

# 2. Test webhook manually
python3 test_slack_webhook.py

# 3. Check logs
docker-compose logs | grep -i slack
```

---

## 🎯 Next Steps

### Immediate (Today)
1. ✅ Verify network configuration: `.env` shows 192.168.12.0/24
2. ✅ Setup SSH keys to servers in your network
3. ✅ Start: `docker-compose up -d`
4. ✅ Monitor: `docker-compose logs -f`

### First Week
1. ✅ Run first full cycle (check Slack)
2. ✅ Verify dashboard (http://localhost)
3. ✅ Review update reports
4. ✅ Adjust UPDATE_INTERVAL if needed

### Ongoing
1. ✅ Monitor Slack for alerts
2. ✅ Check dashboard regularly
3. ✅ Review system logs weekly
4. ✅ Add new servers to network as needed

---

## 📋 Network Checklist

Before deploying on 192.168.12.0/24:

- [ ] Network range verified: 192.168.12.0/24
- [ ] Slack webhook configured: ✅ Done
- [ ] SSH keys generated: `ssh-keygen -t ed25519`
- [ ] SSH keys copied to servers: `ssh-copy-id`
- [ ] Can ping gateway: `ping 192.168.12.1`
- [ ] Can ping at least one server: `ping 192.168.12.10`
- [ ] Docker installed locally
- [ ] Docker Compose installed locally
- [ ] Ready to deploy: `docker-compose up -d`

---

## 🚀 Ready to Deploy!

Your system is now configured for your 192.168.12.0/24 network with:
- ✅ Correct network range
- ✅ Your Slack webhook integrated
- ✅ SSH keys ready
- ✅ Dashboard enabled
- ✅ API endpoints active

**Start with:**
```bash
docker-compose up -d
```

**Then:**
1. Wait for first scan (~1-5 minutes)
2. Check Slack for first report
3. View dashboard at http://localhost
4. Monitor logs: `docker-compose logs -f`

---

**Questions?** Check:
- SLACK_SETUP.md - Slack configuration
- README.md - Full documentation
- ADVANCED_GUIDE.md - Advanced topics

Good luck! 🎉
