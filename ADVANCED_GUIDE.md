# Advanced Configuration Guide

## Table of Contents
1. [Monitoring Stack](#monitoring-stack)
2. [Scaling for Large Deployments](#scaling)
3. [Production Deployment](#production)
4. [High Availability](#high-availability)
5. [Security Hardening](#security)
6. [Performance Tuning](#performance)
7. [Troubleshooting](#troubleshooting)

---

## Monitoring Stack {#monitoring-stack}

### Overview
Integrate with Prometheus and Grafana for comprehensive monitoring and visualization.

### Quick Start

```bash
# 1. Start base deployment
docker-compose up -d

# 2. Start monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d

# 3. Access services
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
# - AlertManager: http://localhost:9093
```

### Metrics Available

**System-wide metrics:**
- `ansible_updater_hosts_total` - Number of hosts scanned
- `ansible_updater_updates_total` - Total updates applied
- `ansible_updater_security_updates_total` - Security updates available
- `ansible_updater_hosts_needing_reboot` - Hosts requiring reboot

**Per-host metrics:**
- `ansible_updater_host_updates_installed` - Updates per host
- `ansible_updater_host_security_updates` - Security updates per host
- `ansible_updater_host_reboot_required` - Reboot status per host
- `ansible_updater_host_last_scan_age_seconds` - Time since last scan

### Custom Alerts

Edit `prometheus-rules.yml` to add custom alert rules:

```yaml
groups:
  - name: ansible_updater
    interval: 30s
    rules:
      # Alert if many hosts need updates
      - alert: ManyUpdatesAvailable
        expr: ansible_updater_updates_total > 50
        for: 1h
        annotations:
          summary: "{{ $value }} updates available"
      
      # Alert if hosts need reboot
      - alert: HostsNeedingReboot
        expr: ansible_updater_hosts_needing_reboot > 2
        for: 30m
        annotations:
          summary: "{{ $value }} hosts need reboot"
      
      # Alert if no recent scans
      - alert: NoRecentScans
        expr: max(ansible_updater_host_last_scan_age_seconds) > 7200
        for: 10m
        annotations:
          summary: "No updates in last 2 hours"
```

---

## Scaling for Large Deployments {#scaling}

### Handling 100+ Servers

#### 1. Increase Parallelism

Edit `ansible/ansible.cfg`:
```ini
[defaults]
forks = 50  # Increase from default 10
```

#### 2. Optimize Network Discovery

Edit `scripts/start.sh`:
```bash
# Faster scanning for known subnets
nmap -sn --min-hostgroup 128 "$NETWORK_RANGE"

# Or split into multiple scans
for subnet in 192.168.{1..10}.0/24; do
    nmap -sn "$subnet" >> /tmp/live_hosts.txt
done
```

#### 3. Batch Updates

Split updates into batches using Ansible serial execution:

```yaml
- name: Update systems in batches
  hosts: all
  serial: 5  # Update 5 hosts at a time
  tasks:
    - name: Update system
      apt:
        upgrade: dist
```

#### 4. Distribute Across Multiple Runners

Run multiple containers with different network ranges:

```yaml
# docker-compose.yml
services:
  runner-1:
    build: .
    environment:
      - NETWORK_RANGE=192.168.1.0/25
  
  runner-2:
    build: .
    environment:
      - NETWORK_RANGE=192.168.1.128/25
```

### Performance Optimization

```ini
# ansible/ansible.cfg
[defaults]
# Parallel execution
forks = 30
max_diff_size = 0

# Connection optimization
connection_timeout = 10
[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
pipelining = True
```

---

## Production Deployment {#production}

### Using Systemd Service

```bash
# 1. Run installation script
sudo bash install.sh

# 2. Configure
sudo nano /opt/ansible-update-manager/.env

# 3. Start service
sudo systemctl start ansible-updater
sudo systemctl status ansible-updater

# 4. View logs
sudo journalctl -u ansible-updater -f
```

### Docker Swarm Deployment

```bash
# Initialize swarm
docker swarm init

# Create service
docker service create \
  --name ansible-updater \
  --replicas 1 \
  --env-file .env \
  --mount type=bind,source=$HOME/.ssh,destination=/root/.ssh,readonly \
  --publish 80:80 \
  --publish 8080:8080 \
  ansible-updater-image
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ansible-updater
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ansible-updater
  template:
    metadata:
      labels:
        app: ansible-updater
    spec:
      containers:
      - name: ansible-updater
        image: ansible-updater:latest
        env:
        - name: NETWORK_RANGE
          value: "192.168.1.0/24"
        - name: UPDATE_INTERVAL
          value: "3600"
        ports:
        - containerPort: 80
        - containerPort: 8080
        volumeMounts:
        - name: ssh-keys
          mountPath: /root/.ssh
          readOnly: true
        - name: reports
          mountPath: /reports
      volumes:
      - name: ssh-keys
        secret:
          secretName: ansible-ssh-key
      - name: reports
        emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: ansible-updater
spec:
  selector:
    app: ansible-updater
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: LoadBalancer
```

---

## High Availability {#high-availability}

### Multi-Container Setup

```yaml
version: '3.8'

services:
  # Primary scanner
  scanner-primary:
    build: .
    environment:
      - NETWORK_RANGE=192.168.1.0/24
      - UPDATE_INTERVAL=3600
    volumes:
      - shared-reports:/reports
      - ~/.ssh:/root/.ssh:ro
    restart: unless-stopped

  # Backup scanner (different network range)
  scanner-secondary:
    build: .
    environment:
      - NETWORK_RANGE=10.0.0.0/24
      - UPDATE_INTERVAL=3600
    volumes:
      - shared-reports:/reports
      - ~/.ssh:/root/.ssh:ro
    restart: unless-stopped

  # Shared web interface
  web:
    image: nginx:latest
    ports:
      - "80:80"
    volumes:
      - shared-reports:/usr/share/nginx/html:ro
    depends_on:
      - scanner-primary
      - scanner-secondary

volumes:
  shared-reports:
```

### Load Balancing

Use HAProxy for load distribution:

```ini
global
    maxconn 2048

frontend ansible_web
    bind 0.0.0.0:80
    mode http
    default_backend web_backends

backend web_backends
    mode http
    balance roundrobin
    server web1 localhost:8080 check
    server web2 localhost:8081 check
    server web3 localhost:8082 check
```

---

## Security Hardening {#security}

### Network Security

```bash
# Firewall rules (UFW)
sudo ufw default deny incoming
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 3000/tcp      # Grafana
sudo ufw enable
```

### SSH Security

```bash
# Generate strong SSH key
ssh-keygen -t ed25519 -f ~/.ssh/ansible \
  -N "strong_passphrase" \
  -C "ansible-updater"

# Set strict permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/ansible
chmod 644 ~/.ssh/ansible.pub
```

### Container Security

```dockerfile
# In Dockerfile - run as non-root
RUN useradd -m -s /bin/bash ansible
USER ansible
```

```yaml
# docker-compose.yml
services:
  ansible-updater:
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    tmpfs:
      - /tmp
      - /var/tmp
```

### Data Protection

```bash
# Encrypt sensitive data
ansible-vault create group_vars/all/vault.yml

# Store credentials securely
export SLACK_WEBHOOK_URL=$(cat /etc/ansible-updater/secrets/slack-webhook)
```

---

## Performance Tuning {#performance}

### Disk I/O Optimization

```ini
# ansible/ansible.cfg
[defaults]
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /dev/shm/ansible_facts
fact_caching_timeout = 86400
```

### Network Optimization

```bash
# In scripts/start.sh
# Use async scanning for faster discovery
nmap -sn --max-retries 1 --initial-rtt-timeout 100ms "$NETWORK_RANGE"
```

### Memory Optimization

```ini
# ansible/ansible.cfg
[defaults]
module_compression = 'gzip'
control_path = /tmp/ansible/control-%l-%r@%h-%p
```

### CPU Optimization

```bash
# Limit parallel processes based on CPU count
CORES=$(nproc)
FORKS=$((CORES * 2))  # 2x CPU cores
```

---

## Troubleshooting {#troubleshooting}

### High CPU Usage

```bash
# Check which process uses CPU
docker stats ansible-updater

# Reduce parallelism
# Edit ansible/ansible.cfg, set forks = 5
```

### High Memory Usage

```bash
# Check memory consumption
docker exec ansible-updater free -h

# Clear old reports
find /reports -name "*.json" -mtime +7 -delete

# Reduce fact caching
echo "" > /dev/shm/ansible_facts/*
```

### Slow Network Discovery

```bash
# Test network connectivity
docker exec ansible-updater nmap --version
docker exec ansible-updater nmap -sn --max-retries 1 192.168.1.0/24

# Use smaller subnets
NETWORK_RANGE="192.168.1.0/25"  # Smaller subnet = faster scan
```

### Playbook Hangs

```bash
# Add timeout to tasks
- name: Update system
  apt:
    upgrade: dist
  timeout: 600  # 10 minutes

# Increase SSH timeout
# Edit ansible/ansible.cfg
timeout = 60
```

### Report Generation Fails

```bash
# Check disk space
docker exec ansible-updater df -h

# Check file permissions
docker exec ansible-updater ls -la /reports

# Clear old reports
docker exec ansible-updater rm -f /reports/*.json
```

---

## Monitoring Commands

```bash
# Real-time metrics
watch -n 5 'curl -s http://localhost:8081/metrics | grep ansible_updater'

# Prometheus queries
# - Hosts with pending updates: ansible_updater_host_updates_installed > 0
# - Hosts needing reboot: ansible_updater_host_reboot_required == 1
# - Last scan age: max(ansible_updater_host_last_scan_age_seconds)

# Export metrics
curl http://localhost:8081/metrics > metrics_backup.txt
```

---

## References

- [Ansible Documentation](https://docs.ansible.com)
- [Prometheus Monitoring](https://prometheus.io/docs)
- [Grafana Dashboards](https://grafana.com/grafana/dashboards)
- [Docker Security Best Practices](https://docs.docker.com/engine/security)
- [AlertManager Configuration](https://prometheus.io/docs/alerting/latest/configuration)
