#!/bin/bash

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
PASS=0
FAIL=0
SKIP=0

# Test functions
test_header() {
    echo -e "\n${BLUE}==== $1 ====${NC}"
}

test_pass() {
    echo -e "${GREEN}✓ $1${NC}"
    ((PASS++))
}

test_fail() {
    echo -e "${RED}✗ $1${NC}"
    ((FAIL++))
}

test_skip() {
    echo -e "${YELLOW}⊘ $1${NC}"
    ((SKIP++))
}

test_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Tests

test_header "Docker Environment"

if command -v docker &> /dev/null; then
    test_pass "Docker is installed"
    DOCKER_VERSION=$(docker --version)
    test_info "Version: $DOCKER_VERSION"
else
    test_fail "Docker is not installed"
fi

if command -v docker-compose &> /dev/null; then
    test_pass "Docker Compose is installed"
    COMPOSE_VERSION=$(docker-compose --version)
    test_info "Version: $COMPOSE_VERSION"
else
    test_fail "Docker Compose is not installed"
fi

test_header "Project Structure"

FILES=(
    "Dockerfile"
    "docker-compose.yml"
    "docker-compose.dev.yml"
    "docker-compose.monitoring.yml"
    "nginx.conf"
    ".env.example"
    "README.md"
    "QUICKSTART.md"
    "ADVANCED_GUIDE.md"
    "Makefile"
    "install.sh"
    "ansible-updater.service"
    "prometheus.yml"
    "alertmanager.yml"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        test_pass "File exists: $file"
    else
        test_fail "File missing: $file"
    fi
done

DIRS=(
    "ansible"
    "scripts"
)

for dir in "${DIRS[@]}"; do
    if [ -d "$dir" ]; then
        test_pass "Directory exists: $dir"
    else
        test_fail "Directory missing: $dir"
    fi
done

test_header "Critical Files in Subdirectories"

CRITICAL_FILES=(
    "ansible/ansible.cfg"
    "ansible/update-playbook.yml"
    "ansible/advanced-playbook.yml"
    "ansible/hosts.yml"
    "scripts/start.sh"
    "scripts/web_server.py"
    "scripts/generate_reports.py"
    "scripts/slack_notifier.py"
    "scripts/prometheus_exporter.py"
)

for file in "${CRITICAL_FILES[@]}"; do
    if [ -f "$file" ]; then
        test_pass "File exists: $file"
    else
        test_fail "File missing: $file"
    fi
done

test_header "Script Executability"

if [ -x "scripts/start.sh" ]; then
    test_pass "start.sh is executable"
else
    test_fail "start.sh is not executable"
fi

if [ -x "install.sh" ]; then
    test_pass "install.sh is executable"
else
    test_fail "install.sh is not executable"
fi

test_header "YAML Syntax Validation"

if command -v yamllint &> /dev/null; then
    YAML_FILES=("docker-compose.yml" "prometheus.yml" "alertmanager.yml" "ansible/ansible.cfg")
    for yaml_file in "${YAML_FILES[@]}"; do
        if [ -f "$yaml_file" ]; then
            if yamllint "$yaml_file" > /dev/null 2>&1; then
                test_pass "$yaml_file is valid YAML"
            else
                test_fail "$yaml_file has syntax errors"
            fi
        fi
    done
else
    test_skip "yamllint not installed (skipping YAML validation)"
fi

test_header "Python Syntax Validation"

PYTHON_FILES=(
    "scripts/web_server.py"
    "scripts/generate_reports.py"
    "scripts/slack_notifier.py"
    "scripts/prometheus_exporter.py"
)

if command -v python3 &> /dev/null; then
    for py_file in "${PYTHON_FILES[@]}"; do
        if [ -f "$py_file" ]; then
            if python3 -m py_compile "$py_file" 2>/dev/null; then
                test_pass "$py_file has valid Python syntax"
            else
                test_fail "$py_file has syntax errors"
            fi
        fi
    done
else
    test_skip "Python 3 not installed (skipping Python validation)"
fi

test_header "Configuration Files"

if [ -f ".env.example" ]; then
    if grep -q "NETWORK_RANGE" .env.example; then
        test_pass ".env.example has NETWORK_RANGE"
    else
        test_fail ".env.example missing NETWORK_RANGE"
    fi
    
    if grep -q "UPDATE_INTERVAL" .env.example; then
        test_pass ".env.example has UPDATE_INTERVAL"
    else
        test_fail ".env.example missing UPDATE_INTERVAL"
    fi
fi

test_header "Docker Build Test"

if command -v docker &> /dev/null; then
    test_info "Testing Docker image build (this may take a minute)..."
    if docker-compose build --no-cache > /tmp/docker_build.log 2>&1; then
        test_pass "Docker image builds successfully"
    else
        test_fail "Docker image build failed"
        test_info "Check /tmp/docker_build.log for details"
    fi
else
    test_skip "Docker not available (skipping Docker build test)"
fi

test_header "Network Connectivity"

if command -v nmap &> /dev/null; then
    test_pass "nmap is available"
else
    test_fail "nmap not found (required for network discovery)"
fi

if command -v ssh &> /dev/null; then
    test_pass "ssh client is available"
else
    test_fail "ssh client not found"
fi

test_header "SSH Key Setup"

if [ -f ~/.ssh/id_rsa ]; then
    test_pass "SSH private key exists: ~/.ssh/id_rsa"
    
    if [ -f ~/.ssh/id_rsa.pub ]; then
        test_pass "SSH public key exists: ~/.ssh/id_rsa.pub"
    else
        test_fail "SSH public key missing: ~/.ssh/id_rsa.pub"
    fi
    
    # Check permissions
    PERMS=$(stat -c %a ~/.ssh/id_rsa 2>/dev/null || stat -f %OLp ~/.ssh/id_rsa 2>/dev/null)
    if [ "$PERMS" = "600" ] || [ "$PERMS" = "-rw-------" ]; then
        test_pass "SSH key has correct permissions (600)"
    else
        test_fail "SSH key has incorrect permissions (should be 600, is $PERMS)"
    fi
else
    test_skip "SSH key not found (not required for testing, but needed for production)"
fi

test_header "Documentation"

DOCS=(
    "README.md"
    "QUICKSTART.md"
    "ADVANCED_GUIDE.md"
    "PROJECT_OVERVIEW.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        LINES=$(wc -l < "$doc")
        test_pass "$doc exists ($LINES lines)"
    else
        test_fail "$doc missing"
    fi
done

test_header "Makefile Commands"

if [ -f "Makefile" ]; then
    test_pass "Makefile exists"
    
    # Check for essential targets
    TARGETS=("help" "build" "up" "down" "logs" "test-all")
    for target in "${TARGETS[@]}"; do
        if grep -q "^$target:" Makefile; then
            test_pass "Makefile has '$target' target"
        else
            test_fail "Makefile missing '$target' target"
        fi
    done
else
    test_fail "Makefile not found"
fi

test_header "Summary"

echo ""
echo -e "${GREEN}Passed:  $PASS${NC}"
echo -e "${RED}Failed:  $FAIL${NC}"
echo -e "${YELLOW}Skipped: $SKIP${NC}"

TOTAL=$((PASS + FAIL + SKIP))
echo ""
echo "Total: $TOTAL tests"

if [ $FAIL -eq 0 ]; then
    echo -e "\n${GREEN}✓ All tests passed!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Configure .env: cp .env.example .env && nano .env"
    echo "  2. Setup SSH: ssh-copy-id -i ~/.ssh/id_rsa root@<target-ip>"
    echo "  3. Build and deploy: docker-compose up -d"
    echo "  4. View dashboard: http://localhost"
    exit 0
else
    echo -e "\n${RED}✗ Some tests failed. Please review the errors above.${NC}"
    exit 1
fi
