# ADVANCED FEATURES GUIDE

## Overview of New Capabilities

This guide documents the advanced features added to the Ansible Linux Update Manager.

---

## 1. Configuration Management (`config.sh`)

Manage multiple environments (dev, staging, production) easily.

### Usage

```bash
# Initialize default environments
./config.sh init

# Load an environment
./config.sh load dev
./config.sh load prod

# List available environments
./config.sh list

# Create custom environment
./config.sh create testing

# View current configuration
./config.sh show

# Edit environment config
./config.sh edit dev
```

### Environment Files

Located in `environments/` directory:
- `dev.env` - Development (short intervals, verbose)
- `staging.env` - Staging (longer intervals, moderate logging)
- `prod.env` - Production (hourly checks, minimal logging)

---

## 2. Health Checks (`health_check.py`)

Comprehensive system diagnostics and health verification.

### Usage

```bash
# Full system check
python3 health_check.py

# Check specific component
python3 health_check.py --check containers
python3 health_check.py --check ansible
python3 health_check.py --check services

# Export results
python3 health_check.py --export health_report.json

# Verbose output
python3 health_check.py --verbose
```

### What It Checks

- Docker installation and daemon
- Container status and logs
- Network connectivity
- SSH configuration
- Ansible setup
- File structure
- Configuration validity
- Report generation
- Service health (web, API)

---

## 3. Backup and Restore (`backup.sh`)

Manage configurations and report backups.

### Usage

```bash
# Create backup
./backup.sh backup

# List backups
./backup.sh list

# Restore from backup
./backup.sh restore backups/backup_20240115_120000.tar.gz

# Verify backup integrity
./backup.sh verify backups/backup_20240115_120000.tar.gz

# Export configuration
./backup.sh export

# Import configuration
./backup.sh import config.json

# Archive old reports
./backup.sh archive-reports
```

### What Gets Backed Up

- `.env` configuration
- `ansible/` directory
- `reports/` directory
- `environments/` directory

### Automatic Cleanup

- Keeps last 10 backups automatically
- Old backups older than 30 days can be manually archived

---

## 4. Diagnostics (`diagnose.sh`)

Detailed troubleshooting and diagnostic information.

### Usage

```bash
# Full diagnostics
./diagnose.sh full

# Specific diagnostics
./diagnose.sh system
./diagnose.sh containers
./diagnose.sh network
./diagnose.sh config
./diagnose.sh ansible
./diagnose.sh ssh
./diagnose.sh services

# View common issues
./diagnose.sh issues

# Generate diagnostic report
./diagnose.sh report
```

### Output

- System information
- Container status
- Network configuration
- Resource usage
- Ansible setup
- SSH configuration
- Service health
- Common solutions

---

## 5. Multi-Channel Notifications (`scripts/multi_notifier.py`)

Send notifications to multiple channels simultaneously.

### Supported Channels

1. **Slack** - Block-formatted messages
2. **Email** - HTML formatted reports
3. **Discord** - Embed messages with color coding
4. **Custom Webhooks** - Generic JSON payloads

### Configuration

```bash
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Email
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SMTP_PORT=587
EMAIL_SENDER=your-email@gmail.com
EMAIL_PASSWORD=your-password
EMAIL_RECIPIENTS=admin@example.com,ops@example.com

# Discord
DISCORD_WEBHOOK_URL=https://discordapp.com/api/webhooks/...

# Custom Webhooks
WEBHOOK_URLS=https://example.com/webhook1,https://example.com/webhook2
```

### Usage

```bash
# Send to all configured channels
python3 scripts/multi_notifier.py

# Test specific channel
python3 scripts/slack_notifier.py
```

---

## 6. Advanced Ansible Playbook

The `ansible/advanced-playbook.yml` includes:

### Features

- **Extended metrics** - System load, disk usage, service failures
- **Kernel tracking** - Detects kernel updates
- **Security updates** - Separate security update counting
- **Pre/post comparisons** - System state before and after
- **Automatic reboots** - Optional automatic reboot on critical updates
- **Error handling** - Graceful failure handling
- **Detailed reporting** - Comprehensive JSON output

### Usage

```bash
# Run with auto-reboot disabled (default)
ansible-playbook ansible/advanced-playbook.yml -i ansible/hosts.yml

# Run with auto-reboot enabled
ansible-playbook ansible/advanced-playbook.yml -i ansible/hosts.yml -e "auto_reboot=true"

# Verbose output
ansible-playbook ansible/advanced-playbook.yml -i ansible/hosts.yml -v
ansible-playbook ansible/advanced-playbook.yml -i ansible/hosts.yml -vvv
```

---

## 7. Docker Deployment Scenarios

Reference guide in `DOCKER_DEPLOYMENT.md`:

### Deployment Options

1. **Local Development** - Single container setup
2. **Production** - Optimized with persistent volumes
3. **High Availability** - Multiple instances with shared storage
4. **Kubernetes** - Helm charts and manifests
5. **Docker Swarm** - Swarm-mode deployment
6. **Container Registry** - Build and push to registry

---

## 8. Makefile Targets

Extended build and operations targets.

### New Targets

```makefile
make build              # Build containers
make up                 # Start containers
make down               # Stop containers
make logs              # View logs
make shell             # SSH into container
make health            # Run health checks
make test-all          # Run all tests
make backup            # Create backup
make config            # Manage configurations
make diagnose          # Run diagnostics
make version           # Show versions
```

---

## 9. Testing Framework

Comprehensive test suite in `test.sh`.

### Test Categories

- Environment verification
- File structure validation
- Script syntax checking
- Python code validation
- Docker configuration
- Ansible playbook syntax
- Configuration parsing
- Code quality checks
- Integration tests

### Usage

```bash
# Run all tests
./test.sh

# Run with Docker tests
./test.sh --docker

# Generate test report
./test.sh > test_results.txt
```

---

## 10. Workflow Examples

### Example 1: Setup New Environment

```bash
# Initialize
./config.sh init

# Create custom environment
./config.sh create production

# Edit configuration
nano environments/production.env

# Load environment
./config.sh load production

# Verify setup
python3 health_check.py

# Deploy
docker-compose build
docker-compose up -d
```

### Example 2: Backup and Migration

```bash
# Create backup
./backup.sh backup

# Export configuration
./backup.sh export

# Move to new server and restore
./backup.sh import config.json
./backup.sh restore backups/backup_*.tar.gz

# Verify
./diagnose.sh full
```

### Example 3: Troubleshooting

```bash
# Run diagnostics
./diagnose.sh full

# Check specific issues
./diagnose.sh ansible
./diagnose.sh ssh
./diagnose.sh services

# Generate report
./diagnose.sh report

# Health check with export
python3 health_check.py --export health.json
```

### Example 4: Multi-Channel Notification Setup

```bash
# Add to .env
SLACK_WEBHOOK_URL=https://...
DISCORD_WEBHOOK_URL=https://...
EMAIL_SMTP_SERVER=smtp.gmail.com
EMAIL_SENDER=alerts@example.com

# Send notifications
python3 scripts/multi_notifier.py
```

---

## Integration Points

### With Existing Tools

- **Prometheus**: Custom metrics endpoint possible
- **ELK Stack**: Send logs to Elasticsearch
- **Grafana**: Dashboard integration
- **PagerDuty**: Alert critical failures
- **ServiceNow**: Create tickets on issues

### Custom Integrations

Edit `scripts/multi_notifier.py` to add:
- Microsoft Teams
- Telegram
- SMS alerts
- Log aggregation services

---

## Best Practices

### 1. Configuration Management
- Use `config.sh` for environment switching
- Keep `.env` files in `environments/`
- Use version control (but ignore `.env`)

### 2. Monitoring
- Run `health_check.py` regularly
- Export reports for auditing
- Monitor container logs

### 3. Backup Strategy
- Daily backups: `0 0 * * * cd /ansible-updater && ./backup.sh backup`
- Weekly exports: `0 2 * * 0 cd /ansible-updater && ./backup.sh export`
- Archive reports: `0 3 * * * cd /ansible-updater && ./backup.sh archive-reports`

### 4. Disaster Recovery
- Maintain backup copies off-site
- Test restore procedures regularly
- Document configuration changes

---

## Troubleshooting Commands

```bash
# Quick health check
python3 health_check.py

# Detailed diagnostics
./diagnose.sh full

# Check specific service
./diagnose.sh services

# View container logs
docker-compose logs -f

# SSH connectivity test
./diagnose.sh ssh

# Generate diagnostic report
./diagnose.sh report > diagnostics_$(date +%s).txt

# Verify backup
./backup.sh verify <backup_file>
```

---

## Performance Optimization

### Container Settings
```yaml
# In docker-compose.yml
resources:
  limits:
    cpus: '1'
    memory: 1G
  reservations:
    cpus: '0.5'
    memory: 512M
```

### Playbook Tuning
```bash
# Increase parallel execution in ansible.cfg
forks = 20

# Reduce gathering overhead
gather_subset: min

# Cache facts
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
```

---

## Security Hardening

### SSH Keys
```bash
# Generate strong key
ssh-keygen -t ed25519 -f ~/.ssh/ansible -C "ansible-manager"

# Set proper permissions
chmod 700 ~/.ssh
chmod 600 ~/.ssh/ansible*
```

### Container Security
```bash
# Run as non-root
docker run --user 1000:1000 ...

# Use read-only filesystem
docker run --read-only --tmpfs /tmp ...

# Drop capabilities
docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE ...
```

### Network Security
```bash
# Firewall rules
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw limit 22/tcp
```

---

## Maintenance Checklist

- [ ] Weekly: Run `health_check.py`
- [ ] Weekly: Review container logs
- [ ] Monthly: Create full backup
- [ ] Monthly: Update Docker images
- [ ] Quarterly: Review and update .env configs
- [ ] Quarterly: Test restore procedures
- [ ] Annually: Security audit

---

## Support and Debugging

### Enable Debug Logging
```bash
# In .env
ANSIBLE_VERBOSITY=3
DEBUG=true

# In container
docker-compose exec ansible-updater tail -f /var/log/ansible/ansible.log
```

### Collect Information for Support
```bash
# Generate diagnostic bundle
./diagnose.sh report > diagnostics.txt
python3 health_check.py --export health.json
./backup.sh export > config.json

# Share relevant logs
docker-compose logs > logs.txt
```

---

## Roadmap for Future Enhancements

- [ ] Web UI for configuration
- [ ] Advanced alerting rules
- [ ] Patch rollback capability
- [ ] Compliance reporting
- [ ] Multi-tenant support
- [ ] Metrics and monitoring integration
- [ ] API authentication layer
- [ ] Rate limiting and throttling

---

**Last Updated**: 2024
**Version**: 2.0+
