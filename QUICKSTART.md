# Quick Start Guide

## 30-Second Setup

### Step 1: Create `.env` file

```bash
cat > .env << 'EOF'
NETWORK_RANGE=192.168.1.0/24
UPDATE_INTERVAL=3600
SLACK_WEBHOOK_URL=
EOF
```

### Step 2: Setup SSH Access

```bash
# Your public key needs to be on target servers
ssh-copy-id -i ~/.ssh/id_rsa root@192.168.1.10
```

### Step 3: Start Containers

```bash
docker-compose build
docker-compose up -d
```

### Step 4: View Dashboard

Open: **http://localhost**

---

## Testing Without Real Systems

To test without actual servers:

### Option 1: Create Docker Test Servers

```bash
# Create test Debian container
docker run -d --name test-debian \
  -e root_password=test \
  ubuntu:22.04 sleep infinity

# Create test RedHat container  
docker run -d --name test-redhat \
  redhat/ubi9 sleep infinity
```

### Option 2: Modify ansible/hosts.yml

Edit for testing:
```yaml
all:
  children:
    debian:
      hosts:
        192.168.1.10:
    redhat:
      hosts:
        192.168.1.20:
```

---

## Common Tasks

### View Live Logs

```bash
docker-compose logs -f ansible-updater
```

### Check Discovery Results

```bash
docker-compose exec ansible-updater cat /tmp/live_hosts.txt
```

### Force Update Cycle

```bash
docker-compose exec ansible-updater bash /scripts/start.sh
```

### View Generated Reports

```bash
ls -la reports/
cat reports/index.html
```

### Test Slack Integration

```bash
docker-compose exec ansible-updater python3 /scripts/slack_notifier.py
```

---

## Troubleshooting

### Container won't start

```bash
docker-compose up --build  # Rebuild
docker-compose logs        # Check errors
```

### No hosts discovered

```bash
# Is your network correct?
docker-compose exec ansible-updater nmap -sn 192.168.1.0/24

# Do you have network access?
docker-compose exec ansible-updater ping 8.8.8.8
```

### SSH connection refused

```bash
# Test SSH from container
docker-compose exec ansible-updater ssh -v root@192.168.1.10

# Check SSH key permissions
ls -la ~/.ssh/id_rsa   # Should be 600
ls -la ~/.ssh          # Should be 700
```

---

## Next Steps

1. ✅ Set network range in `.env`
2. ✅ Configure SSH key access
3. ✅ (Optional) Add Slack webhook URL
4. ✅ Start with `docker-compose up -d`
5. ✅ Monitor with `docker-compose logs -f`
6. ✅ View at http://localhost

**Questions?** Check `README.md` for detailed documentation.
