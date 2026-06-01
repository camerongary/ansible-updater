#!/usr/bin/env bash

# Diagnostic and Troubleshooting Script
# Helps identify and resolve common issues

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════${NC}"
}

print_section() {
    echo ""
    echo -e "${YELLOW}→ $1${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo "  ℹ $1"
}

# System diagnostics
system_diagnostics() {
    print_header "SYSTEM DIAGNOSTICS"
    
    print_section "System Information"
    uname -a
    
    print_section "Docker Status"
    if command -v docker &> /dev/null; then
        print_success "Docker installed"
        docker --version
        if docker ps &> /dev/null; then
            print_success "Docker daemon running"
        else
            print_error "Docker daemon not accessible"
        fi
    else
        print_error "Docker not found"
    fi
    
    print_section "Docker Compose"
    if command -v docker-compose &> /dev/null; then
        print_success "Docker Compose installed"
        docker-compose --version
    else
        print_error "Docker Compose not found"
    fi
    
    print_section "Resource Usage"
    docker system df
}

# Container diagnostics
container_diagnostics() {
    print_header "CONTAINER DIAGNOSTICS"
    
    print_section "Running Containers"
    docker-compose ps || print_error "Could not list containers"
    
    print_section "Container Logs - ansible-updater"
    docker-compose logs --tail=50 ansible-updater 2>/dev/null || print_error "Could not get logs"
    
    print_section "Container Logs - ansible-web"
    docker-compose logs --tail=20 ansible-web 2>/dev/null || print_error "Could not get logs"
}

# Network diagnostics
network_diagnostics() {
    print_header "NETWORK DIAGNOSTICS"
    
    print_section "Network Configuration"
    docker network ls
    
    print_section "Container Networking"
    docker-compose exec -T ansible-updater ifconfig 2>/dev/null || \
    docker-compose exec -T ansible-updater ip addr 2>/dev/null || \
    print_error "Could not get network configuration"
    
    print_section "DNS Resolution"
    docker-compose exec -T ansible-updater nslookup google.com 2>/dev/null || \
    print_error "DNS resolution failed"
    
    print_section "Internet Connectivity"
    if docker-compose exec -T ansible-updater ping -c 1 8.8.8.8 &> /dev/null; then
        print_success "Internet connectivity OK"
    else
        print_error "Cannot reach internet"
    fi
}

# Configuration diagnostics
config_diagnostics() {
    print_header "CONFIGURATION DIAGNOSTICS"
    
    print_section "Environment Variables"
    if [ -f ".env" ]; then
        print_success ".env file exists"
        echo "  Configuration:"
        grep -v "^#" .env | grep -v "^$" | sed 's/^/    /'
    else
        print_error ".env file not found"
        print_info "Create one with: cp .env.example .env"
    fi
    
    print_section "File Structure"
    if [ -f "docker-compose.yml" ]; then
        print_success "docker-compose.yml exists"
    else
        print_error "docker-compose.yml not found"
    fi
    
    if [ -f "Dockerfile" ]; then
        print_success "Dockerfile exists"
    else
        print_error "Dockerfile not found"
    fi
    
    if [ -d "ansible" ]; then
        print_success "ansible directory exists"
        [ -f "ansible/update-playbook.yml" ] && print_success "update-playbook.yml exists"
    else
        print_error "ansible directory not found"
    fi
    
    if [ -d "scripts" ]; then
        print_success "scripts directory exists"
    else
        print_error "scripts directory not found"
    fi
}

# Ansible diagnostics
ansible_diagnostics() {
    print_header "ANSIBLE DIAGNOSTICS"
    
    print_section "Ansible Version"
    docker-compose exec -T ansible-updater ansible --version 2>/dev/null || \
    print_error "Could not get Ansible version"
    
    print_section "Inventory"
    if [ -f "ansible/hosts.yml" ]; then
        print_success "Inventory file exists"
        echo "  Contents:"
        head -20 ansible/hosts.yml | sed 's/^/    /'
    else
        print_info "Inventory will be generated on first run"
    fi
    
    print_section "SSH Configuration"
    if [ -f "ansible/ansible.cfg" ]; then
        print_success "ansible.cfg exists"
    fi
    
    if [ -d "$HOME/.ssh" ]; then
        print_success "SSH directory exists"
        [ -f "$HOME/.ssh/id_rsa" ] && print_success "Private key exists"
        [ -f "$HOME/.ssh/id_rsa.pub" ] && print_success "Public key exists"
    else
        print_error "SSH directory not found"
    fi
}

# Report diagnostics
report_diagnostics() {
    print_header "REPORT DIAGNOSTICS"
    
    print_section "Reports Directory"
    if [ -d "reports" ]; then
        print_success "Reports directory exists"
        local count=$(find reports -name "*.json" 2>/dev/null | wc -l)
        print_info "JSON reports: $count"
        
        if [ -f "reports/index.html" ]; then
            print_success "Dashboard HTML exists"
            local size=$(wc -c < reports/index.html)
            print_info "Dashboard size: $size bytes"
        else
            print_info "Dashboard HTML not yet generated"
        fi
        
        print_section "Recent Reports"
        ls -lt reports/*.json 2>/dev/null | head -5 | sed 's/^/    /'
    else
        print_info "Reports directory will be created on first run"
    fi
}

# Service diagnostics
service_diagnostics() {
    print_header "SERVICE DIAGNOSTICS"
    
    print_section "Web Dashboard (port 80)"
    if curl -s -o /dev/null -w "%{http_code}" http://localhost/ 2>/dev/null | grep -q "200\|301\|302"; then
        print_success "Dashboard accessible"
    else
        print_error "Dashboard not responding"
    fi
    
    print_section "Flask API (port 8080)"
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/health 2>/dev/null | grep -q "200"; then
        print_success "API health check passed"
    else
        print_error "API health check failed"
    fi
    
    print_section "API Endpoints"
    for endpoint in "/api/stats" "/api/results"; do
        status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080$endpoint 2>/dev/null)
        [ "$status" = "200" ] && print_success "$endpoint (HTTP $status)" || print_error "$endpoint (HTTP $status)"
    done
}

# SSH diagnostics
ssh_diagnostics() {
    print_header "SSH DIAGNOSTICS"
    
    print_section "SSH Key Information"
    if [ -f "$HOME/.ssh/id_rsa" ]; then
        print_success "Private key exists"
        local perms=$(stat -f "%OLp" "$HOME/.ssh/id_rsa" 2>/dev/null || stat -c "%a" "$HOME/.ssh/id_rsa" 2>/dev/null)
        print_info "Permissions: $perms (should be 600)"
    else
        print_error "Private key not found"
    fi
    
    print_section "Known Hosts"
    if [ -f "$HOME/.ssh/known_hosts" ]; then
        print_info "Known hosts file exists ($(wc -l < "$HOME/.ssh/known_hosts") entries)"
    else
        print_info "No known_hosts file yet"
    fi
}

# Slack diagnostics
slack_diagnostics() {
    print_header "SLACK DIAGNOSTICS"
    
    print_section "Webhook Configuration"
    if grep -q "SLACK_WEBHOOK_URL=" .env 2>/dev/null; then
        local webhook=$(grep "SLACK_WEBHOOK_URL=" .env | cut -d= -f2)
        if [ -z "$webhook" ] || [ "$webhook" = "" ]; then
            print_info "Slack webhook not configured"
        else
            # Mask the URL for security
            local masked="${webhook:0:40}..."
            print_success "Webhook configured: $masked"
        fi
    else
        print_info "SLACK_WEBHOOK_URL not in .env"
    fi
}

# Generate report
generate_diagnostic_report() {
    local report_file="diagnostic_report_$(date +%Y%m%d_%H%M%S).txt"
    
    print_header "GENERATING DIAGNOSTIC REPORT"
    {
        echo "Diagnostic Report - $(date)"
        echo ""
        system_diagnostics
        echo ""
        config_diagnostics
        echo ""
        container_diagnostics
        echo ""
        ansible_diagnostics
        echo ""
        report_diagnostics
    } | tee "$report_file"
    
    print_success "Report saved to: $report_file"
}

# Common issues
show_common_issues() {
    print_header "COMMON ISSUES & SOLUTIONS"
    
    cat << 'EOF'

1. "docker-compose: command not found"
   Solution: Install Docker Compose
   $ sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
   $ sudo chmod +x /usr/local/bin/docker-compose

2. ".env file not found"
   Solution: Create configuration file
   $ cp .env.example .env
   $ nano .env

3. "Cannot connect to Docker daemon"
   Solution: Start Docker
   $ sudo systemctl start docker

4. "No hosts discovered"
   Solution: Check network range and connectivity
   $ docker-compose exec ansible-updater nmap -sn 192.168.1.0/24

5. "SSH connection refused"
   Solution: Setup SSH keys
   $ ssh-copy-id -i ~/.ssh/id_rsa root@192.168.1.10

6. "Permission denied (publickey)"
   Solution: Fix SSH key permissions
   $ chmod 700 ~/.ssh
   $ chmod 600 ~/.ssh/id_rsa

7. "Dashboard shows no data"
   Solution: Wait for first scan and check logs
   $ docker-compose logs -f ansible-updater

8. "Slack notifications not working"
   Solution: Verify webhook URL and test
   $ docker-compose exec ansible-updater python3 /scripts/slack_notifier.py

EOF
}

# Usage
usage() {
    cat << 'EOF'
Diagnostic and Troubleshooting Script

Usage:
  ./diagnose.sh system          # System diagnostics
  ./diagnose.sh containers      # Container status
  ./diagnose.sh network         # Network connectivity
  ./diagnose.sh config          # Configuration check
  ./diagnose.sh ansible         # Ansible setup
  ./diagnose.sh reports         # Report files
  ./diagnose.sh services        # Service health
  ./diagnose.sh ssh             # SSH configuration
  ./diagnose.sh slack           # Slack integration
  ./diagnose.sh issues          # Common issues
  ./diagnose.sh full            # Full diagnostic (all checks)
  ./diagnose.sh report          # Generate diagnostic report

Examples:
  ./diagnose.sh full            # Run all diagnostics
  ./diagnose.sh containers      # Check container status
  ./diagnose.sh ssh             # Check SSH setup
EOF
}

# Main
case "${1:-}" in
    system)
        system_diagnostics
        ;;
    containers)
        container_diagnostics
        ;;
    network)
        network_diagnostics
        ;;
    config)
        config_diagnostics
        ;;
    ansible)
        ansible_diagnostics
        ;;
    reports)
        report_diagnostics
        ;;
    services)
        service_diagnostics
        ;;
    ssh)
        ssh_diagnostics
        ;;
    slack)
        slack_diagnostics
        ;;
    issues)
        show_common_issues
        ;;
    full)
        system_diagnostics
        config_diagnostics
        ansible_diagnostics
        container_diagnostics
        network_diagnostics
        service_diagnostics
        ssh_diagnostics
        slack_diagnostics
        ;;
    report)
        generate_diagnostic_report
        ;;
    *)
        usage
        ;;
esac
