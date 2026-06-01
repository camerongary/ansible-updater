# Automatic SSH Key Distribution Guide

## Overview

Your system now has **two methods** to automatically copy SSH keys to all discovered servers:

1. **Standalone Script** - `copy-ssh-keys.sh` (Run anytime)
2. **Integrated Setup** - Automatic SSH key setup before updates start

---

## Method 1: Standalone SSH Key Copy Script

### Quick Start

```bash
# Run with defaults (192.168.12.0/24, root user, ~/.ssh/id_rsa)
bash copy-ssh-keys.sh

# Or with custom parameters
bash copy-ssh-keys.sh 192.168.12.0/24 root ~/.ssh/id_rsa

# Help
bash copy-ssh-keys.sh --help
```

### What It Does

1. **Discovers** all servers in your network using nmap
2. **Verifies** SSH key exists
3. **Tests** existing SSH connections
4. **Copies** SSH key to each server (with retries)
5. **Verifies** SSH access works
6. **Reports** results

### Example Run

```
════════════════════════════════════════════════════
Checking Prerequisites
════════════════════════════════════════════════════
✓ SSH private key found: /root/.ssh/id_rsa
✓ SSH public key found: /root/.ssh/id_rsa.pub
✓ nmap is installed
✓ ssh-copy-id is available

════════════════════════════════════════════════════
Discovering Servers in 192.168.12.0/24
════════════════════════════════════════════════════
ℹ Running nmap scan (this may take a minute)...
✓ Discovered 5 server(s):
  • 192.168.12.10
  • 192.168.12.11
  • 192.168.12.15
  • 192.168.12.20
  • 192.168.12.25

Continue? (y/n) y

════════════════════════════════════════════════════
Copying SSH Keys to All Servers
════════════════════════════════════════════════════
ℹ Processing 192.168.12.10...
✓ SSH key copied to 192.168.12.10

ℹ Processing 192.168.12.11...
✓ SSH key copied to 192.168.12.11

[... more servers ...]

════════════════════════════════════════════════════
Verifying SSH Access
════════════════════════════════════════════════════
✓ SSH access verified: 192.168.12.10
✓ SSH access verified: 192.168.12.11
✓ SSH access verified: 192.168.12.15
✓ SSH access verified: 192.168.12.20
✓ SSH access verified: 192.168.12.25

Verification complete:
  • Verified: 5
  • Failed: 0

════════════════════════════════════════════════════
Summary Report
════════════════════════════════════════════════════
Network Range:     192.168.12.0/24
SSH User:          root
SSH Key:           /root/.ssh/id_rsa

Status:
  ✓ 192.168.12.10
  ✓ 192.168.12.11
  ✓ 192.168.12.15
  ✓ 192.168.12.20
  ✓ 192.168.12.25
```

---

## Method 2: Automatic SSH Setup on Docker Server Startup

### Setup for Automatic SSH Key Distribution

On your Docker server (192.168.12.104), you can enable automatic SSH key setup:

```bash
# Option A: Setup SSH keys on first run
SSH_KEY_SETUP=true docker-compose up -d

# Option B: Add to .env
echo "SSH_KEY_SETUP=true" >> .env
docker-compose up -d

# Option C: Set custom SSH user and key location
SSH_KEY_SETUP=true SSH_USER=ubuntu SSH_KEY=/root/.ssh/custom_key docker-compose up -d
```

### How It Works

1. Container starts
2. Discovers all servers in 192.168.12.0/24
3. Copies SSH key to each discovered server
4. Verifies SSH access
5. Starts normal update cycles (if successful)

### Environment Variables

```bash
# Enable SSH key setup
SSH_KEY_SETUP=true

# SSH username (default: root)
SSH_USER=root

# Path to SSH private key (default: ~/.ssh/id_rsa)
SSH_KEY=/root/.ssh/id_rsa

# Network to scan (inherited from NETWORK_RANGE)
NETWORK_RANGE=192.168.12.0/24

# Update interval (normal operation)
UPDATE_INTERVAL=3600
```

### Complete Docker Compose Setup

```bash
# Create .env file with SSH setup
cat > .env << 'EOF'
NETWORK_RANGE=192.168.12.0/24
UPDATE_INTERVAL=3600
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
SSH_KEY_SETUP=true
SSH_USER=root
SSH_KEY=/root/.ssh/id_rsa
EOF

# Build and start
docker-compose build
docker-compose up -d

# Watch setup progress
docker-compose logs -f
```

---

## Pre-requisites

### On Docker Server (192.168.12.104)

1. **SSH key must exist**:
   ```bash
   # Generate if needed
   ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""
   ```

2. **nmap must be installed**:
   ```bash
   # On Ubuntu/Debian
   sudo apt-get install nmap
   
   # On CentOS/RHEL
   sudo dnf install nmap
   ```

3. **SSH client must be available**:
   ```bash
   # Usually pre-installed
   which ssh
   which ssh-copy-id
   ```

### On Target Servers

1. **SSH server running** (usually default)
2. **User account exists** (typically `root` or `ubuntu`)
3. **Network access** from Docker server (port 22)

---

## Troubleshooting

### Problem: "nmap not found"

```bash
# Solution: Install nmap
sudo apt-get update
sudo apt-get install nmap
```

### Problem: "ssh-copy-id not found"

```bash
# Solution: Install SSH tools
sudo apt-get install openssh-client
```

### Problem: "No servers discovered"

```bash
# Solution: Verify network
ping 192.168.12.1          # Test gateway
ping 192.168.12.10         # Test specific server
nmap -sn 192.168.12.0/24   # Manual scan
```

### Problem: "SSH key copy fails"

This usually means:

1. **SSH not running on target**:
   ```bash
   # On target server
   systemctl status ssh
   systemctl start ssh
   ```

2. **Firewall blocking SSH**:
   ```bash
   # On target server
   sudo ufw allow 22
   # or
   sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
   ```

3. **User doesn't exist**:
   ```bash
   # On target server, create user if needed
   sudo useradd -m -s /bin/bash ubuntu
   # or just use 'root' user
   ```

### Problem: "Permission denied"

```bash
# Fix SSH key permissions
chmod 600 ~/.ssh/id_rsa
chmod 700 ~/.ssh

# Verify key works
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo OK"
```

---

## Step-by-Step Deployment with Automatic SSH Setup

### On Your Local Machine

```bash
# 1. Download files
# Download ansible-updater-complete.zip

# 2. Extract
unzip ansible-updater-complete.zip

# 3. Copy to Docker server
scp -r * root@192.168.12.104:/root/ansible-updater/
```

### On Docker Server (192.168.12.104)

```bash
# 1. SSH to server
ssh root@192.168.12.104

# 2. Navigate to project
cd /root/ansible-updater

# 3. Verify SSH key exists
ls -la ~/.ssh/id_rsa

# 4. If not, generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N ""

# 5. Enable SSH setup in .env
echo "SSH_KEY_SETUP=true" >> .env

# 6. Build container
docker-compose build

# 7. Start with SSH setup (will run once)
SSH_KEY_SETUP=true docker-compose up -d

# 8. Watch progress
docker-compose logs -f

# Output will show:
# [timestamp] SSH key setup mode enabled
# [timestamp] Starting SSH key setup...
# [timestamp] Discovered servers in 192.168.12.0/24
# [timestamp] Setting up SSH key on 192.168.12.10...
# [timestamp] ✓ SSH key copied to 192.168.12.10
# ... more servers ...
# [timestamp] SSH keys setup completed successfully

# 9. Restart to begin normal update cycles
docker-compose restart

# 10. Now monitor normal operation
docker-compose logs -f
```

---

## Comparison: Standalone vs Integrated

| Feature | Standalone Script | Integrated Setup |
|---------|-------------------|------------------|
| **When** | Anytime, manual | Container startup |
| **Command** | `bash copy-ssh-keys.sh` | Docker environment variable |
| **Requires** | SSH access to Docker server | SSH access + Docker |
| **Output** | Detailed report | Container logs |
| **Retry Logic** | Yes (3 attempts) | Basic (1 attempt per server) |
| **Interactive Mode** | Yes (asks if failed) | No (logs failures) |
| **Verification** | Full post-copy test | Yes |

---

## Best Practices

### 1. Generate Strong SSH Key

```bash
ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -C "ansible-updater" -N "strong-passphrase"
```

### 2. Verify SSH Works

```bash
# Test after setup
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "hostname"
ssh -i ~/.ssh/id_rsa root@192.168.12.11 "hostname"
# ... etc
```

### 3. Check Network Access

```bash
# Before running setup
nmap -sn 192.168.12.0/24

# Or simpler
for i in {10..30}; do
  timeout 1 bash -c "echo >/dev/tcp/192.168.12.$i/22" && echo "192.168.12.$i is up"
done
```

### 4. Verify SSH on All Servers

```bash
# After setup
for server in 192.168.12.{10,11,15,20,25}; do
  ssh -i ~/.ssh/id_rsa root@$server "echo $server OK" || echo "$server FAILED"
done
```

---

## Monitoring SSH Setup

### Check Logs

```bash
# During/after setup
docker-compose logs

# Filter for SSH setup
docker-compose logs | grep -i "ssh\|key"

# Real-time
docker-compose logs -f
```

### Verify Individual Servers

```bash
# After setup, test SSH to each server
ssh -i ~/.ssh/id_rsa root@192.168.12.10 "apt update"
ssh -i ~/.ssh/id_rsa root@192.168.12.11 "dnf check-update"

# Or use Ansible to test
docker-compose exec ansible-updater ansible all -m ping -i ansible/hosts.yml
```

---

## Files Included

- **copy-ssh-keys.sh** - Standalone SSH key distribution script
- **start-with-ssh-setup.sh** - Enhanced start script with SSH setup
- Updated **docker-compose.yml** - Supports SSH setup environment variables
- This guide

---

## Next Steps

1. **Option A**: Run standalone script
   ```bash
   bash copy-ssh-keys.sh
   ```

2. **Option B**: Use Docker with automatic setup
   ```bash
   SSH_KEY_SETUP=true docker-compose up -d
   ```

3. **Verify**: Test SSH works
   ```bash
   ssh -i ~/.ssh/id_rsa root@192.168.12.10 "echo OK"
   ```

4. **Deploy**: Start normal update cycles
   ```bash
   docker-compose up -d
   docker-compose logs -f
   ```

---

**Your SSH key distribution system is ready!** 🚀
