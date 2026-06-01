#!/bin/bash

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="${INSTALL_DIR:-/opt/ansible-update-manager}"
CONFIG_DIR="${CONFIG_DIR:-/etc/ansible-updater}"
SERVICE_NAME="ansible-updater"

# Helper functions
print_header() {
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"

    local missing_tools=()

    # Check Docker
    if ! command -v docker &> /dev/null; then
        missing_tools+=("docker")
    else
        print_success "Docker installed: $(docker --version)"
    fi

    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null; then
        missing_tools+=("docker-compose")
    else
        print_success "Docker Compose installed: $(docker-compose --version)"
    fi

    # Check sudo
    if ! command -v sudo &> /dev/null; then
        missing_tools+=("sudo")
    else
        print_success "sudo available"
    fi

    if [ ${#missing_tools[@]} -gt 0 ]; then
        print_error "Missing required tools: ${missing_tools[*]}"
        echo ""
        echo "Installation instructions:"
        echo "  Ubuntu/Debian:"
        echo "    sudo apt-get update"
        echo "    sudo apt-get install -y docker.io docker-compose"
        echo "    sudo usermod -aG docker \$USER"
        echo ""
        echo "  CentOS/RHEL:"
        echo "    sudo dnf install -y docker docker-compose"
        echo "    sudo usermod -aG docker \$USER"
        return 1
    fi

    print_success "All prerequisites met"
}

# Create installation directories
setup_directories() {
    print_header "Setting Up Directories"

    print_info "Creating installation directory: $INSTALL_DIR"
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$USER:$USER" "$INSTALL_DIR"

    print_info "Creating config directory: $CONFIG_DIR"
    sudo mkdir -p "$CONFIG_DIR"
    sudo chown "$USER:$USER" "$CONFIG_DIR"

    print_info "Creating reports directory"
    mkdir -p "$INSTALL_DIR/reports"

    print_success "Directories created"
}

# Copy project files
copy_project_files() {
    print_header "Installing Project Files"

    # Check if running from project directory
    if [ ! -f "docker-compose.yml" ]; then
        print_error "Not in project directory (docker-compose.yml not found)"
        return 1
    fi

    print_info "Copying project files to $INSTALL_DIR"
    cp -r Dockerfile docker-compose.yml nginx.conf .env.example \
          ansible scripts "$INSTALL_DIR/"

    # Create .env if it doesn't exist
    if [ ! -f "$INSTALL_DIR/.env" ]; then
        cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
        print_warning ".env created from template - please configure it"
    fi

    print_success "Project files installed"
}

# Setup SSH keys
setup_ssh_keys() {
    print_header "Setting Up SSH Keys"

    if [ ! -f ~/.ssh/id_rsa ]; then
        print_warning "No SSH key found at ~/.ssh/id_rsa"
        print_info "Generating SSH key pair..."

        mkdir -p ~/.ssh
        ssh-keygen -t ed25519 -f ~/.ssh/id_rsa -N "" -C "ansible-updater"

        print_success "SSH key generated: ~/.ssh/id_rsa"
        print_info "Public key: ~/.ssh/id_rsa.pub"
    else
        print_success "SSH key already exists: ~/.ssh/id_rsa"
    fi

    print_info ""
    print_info "Next steps to enable access to target servers:"
    print_info "  For each target server, run:"
    print_info "    ssh-copy-id -i ~/.ssh/id_rsa root@<target-ip>"
    print_info ""
}

# Configure environment
configure_environment() {
    print_header "Configuring Environment"

    local env_file="$INSTALL_DIR/.env"

    print_info "Current configuration in $env_file:"
    grep -v "^#" "$env_file" | grep -v "^$" || true

    read -p "Edit .env file now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} "$env_file"
    fi

    # Validate network range
    local network_range=$(grep "NETWORK_RANGE" "$env_file" | cut -d= -f2 | tr -d ' ')
    if [ -z "$network_range" ]; then
        print_warning "NETWORK_RANGE not configured"
    else
        print_success "NETWORK_RANGE: $network_range"
    fi

    # Validate Slack webhook
    local slack_url=$(grep "SLACK_WEBHOOK_URL" "$env_file" | cut -d= -f2 | tr -d ' ')
    if [ -z "$slack_url" ] || [ "$slack_url" = "" ]; then
        print_warning "SLACK_WEBHOOK_URL not configured (optional)"
    else
        print_success "SLACK_WEBHOOK_URL configured"
    fi
}

# Install systemd service
install_systemd_service() {
    print_header "Installing Systemd Service"

    print_info "Installing service file..."
    sudo cp ansible-updater.service /etc/systemd/system/

    # Update paths in service file
    sudo sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g" \
              /etc/systemd/system/ansible-updater.service

    print_info "Reloading systemd daemon..."
    sudo systemctl daemon-reload

    print_info "Enabling service to start on boot..."
    sudo systemctl enable ansible-updater.service

    print_success "Systemd service installed"

    print_info ""
    print_info "Service management:"
    print_info "  Start:   sudo systemctl start $SERVICE_NAME"
    print_info "  Stop:    sudo systemctl stop $SERVICE_NAME"
    print_info "  Restart: sudo systemctl restart $SERVICE_NAME"
    print_info "  Status:  sudo systemctl status $SERVICE_NAME"
    print_info "  Logs:    sudo journalctl -u $SERVICE_NAME -f"
    print_info ""
}

# Build Docker images
build_docker_images() {
    print_header "Building Docker Images"

    cd "$INSTALL_DIR"

    print_info "Building containers (this may take a few minutes)..."
    docker-compose build

    if [ $? -eq 0 ]; then
        print_success "Docker images built successfully"
    else
        print_error "Failed to build Docker images"
        return 1
    fi

    cd - > /dev/null
}

# Test deployment
test_deployment() {
    print_header "Testing Deployment"

    cd "$INSTALL_DIR"

    print_info "Starting containers..."
    docker-compose up -d

    print_info "Waiting for services to start..."
    sleep 5

    print_info "Checking container status..."
    docker-compose ps

    print_info "Testing web interface..."
    if curl -s http://localhost > /dev/null; then
        print_success "Web interface responding"
    else
        print_warning "Web interface not responding yet (may take longer)"
    fi

    print_info "Dashboard URL: http://localhost"
    print_info "API: http://localhost:8080/api/results"

    cd - > /dev/null
}

# Print final instructions
print_final_instructions() {
    print_header "Installation Complete!"

    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Configure SSH access to target servers:"
    echo "   ssh-copy-id -i ~/.ssh/id_rsa root@<target-ip>"
    echo ""
    echo "2. Start the service:"
    echo "   sudo systemctl start $SERVICE_NAME"
    echo ""
    echo "3. View logs:"
    echo "   sudo journalctl -u $SERVICE_NAME -f"
    echo ""
    echo "4. Access dashboard:"
    echo "   Open http://localhost in your browser"
    echo ""
    echo "5. Manage updates:"
    echo "   cd $INSTALL_DIR"
    echo "   docker-compose logs -f  # View logs"
    echo "   docker-compose down     # Stop service"
    echo ""
    echo "For more information, see:"
    echo "   README.md in the installation directory"
    echo "   $CONFIG_DIR for configuration files"
    echo ""
}

# Main installation flow
main() {
    print_header "Ansible Update Manager - Installation Script"

    # Run installation steps
    check_prerequisites || exit 1
    setup_directories
    copy_project_files || exit 1
    setup_ssh_keys
    configure_environment
    build_docker_images || exit 1

    # Ask to install systemd service
    echo ""
    read -p "Install as systemd service? (recommended for production) (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        install_systemd_service
    else
        print_info "Skipping systemd service installation"
        print_info "You can start the service manually:"
        print_info "  cd $INSTALL_DIR"
        print_info "  docker-compose up -d"
    fi

    # Ask to test deployment
    echo ""
    read -p "Start service now for testing? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        test_deployment
    fi

    print_final_instructions
}

# Run main
main "$@"
