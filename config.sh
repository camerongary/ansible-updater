#!/usr/bin/env bash

# Configuration Manager for Ansible Update System
# Allows quick switching between different environments

set -e

CONFIG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENVIRONMENTS_DIR="$CONFIG_DIR/environments"

# Create environments directory if it doesn't exist
mkdir -p "$ENVIRONMENTS_DIR"

# Default environment templates
create_default_environments() {
    
    # Development environment
    cat > "$ENVIRONMENTS_DIR/dev.env" << 'EOF'
# Development Environment Configuration
ENVIRONMENT=development
NETWORK_RANGE=192.168.1.0/24
UPDATE_INTERVAL=300
SLACK_WEBHOOK_URL=
ANSIBLE_VERBOSITY=3
DOCKER_COMPOSE_PROJECT=ansible-updater-dev
EOF

    # Staging environment
    cat > "$ENVIRONMENTS_DIR/staging.env" << 'EOF'
# Staging Environment Configuration
ENVIRONMENT=staging
NETWORK_RANGE=10.0.1.0/24
UPDATE_INTERVAL=1800
SLACK_WEBHOOK_URL=
ANSIBLE_VERBOSITY=1
DOCKER_COMPOSE_PROJECT=ansible-updater-staging
EOF

    # Production environment
    cat > "$ENVIRONMENTS_DIR/prod.env" << 'EOF'
# Production Environment Configuration
ENVIRONMENT=production
NETWORK_RANGE=10.0.0.0/16
UPDATE_INTERVAL=3600
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
ANSIBLE_VERBOSITY=0
DOCKER_COMPOSE_PROJECT=ansible-updater-prod
EOF

    echo "✓ Default environments created"
}

# Load environment
load_environment() {
    local env=$1
    local env_file="$ENVIRONMENTS_DIR/$env.env"
    
    if [ ! -f "$env_file" ]; then
        echo "✗ Environment file not found: $env_file"
        return 1
    fi
    
    # Load variables
    set -a
    source "$env_file"
    set +a
    
    # Copy to .env
    cp "$env_file" .env
    
    echo "✓ Loaded environment: $env"
    echo "  Network: $NETWORK_RANGE"
    echo "  Interval: ${UPDATE_INTERVAL}s"
    echo "  Project: $DOCKER_COMPOSE_PROJECT"
}

# List environments
list_environments() {
    echo "Available environments:"
    ls -1 "$ENVIRONMENTS_DIR"/*.env 2>/dev/null | xargs -I {} basename {} .env | sed 's/^/  - /'
}

# Create custom environment
create_environment() {
    local name=$1
    
    if [ -z "$name" ]; then
        echo "Usage: create_environment <name>"
        return 1
    fi
    
    local env_file="$ENVIRONMENTS_DIR/$name.env"
    
    if [ -f "$env_file" ]; then
        echo "✗ Environment already exists: $name"
        return 1
    fi
    
    cat > "$env_file" << EOF
# Custom Environment: $name
ENVIRONMENT=$name
NETWORK_RANGE=192.168.1.0/24
UPDATE_INTERVAL=3600
SLACK_WEBHOOK_URL=
ANSIBLE_VERBOSITY=1
DOCKER_COMPOSE_PROJECT=ansible-updater-$name
EOF
    
    echo "✓ Created environment: $name"
    echo "  File: $env_file"
    echo "  Edit with: nano $env_file"
}

# Show usage
usage() {
    cat << 'EOF'
Configuration Manager for Ansible Update System

Usage:
  ./config.sh init              # Initialize default environments
  ./config.sh load <env>        # Load environment (dev/staging/prod)
  ./config.sh list              # List all environments
  ./config.sh create <name>     # Create new environment
  ./config.sh show              # Show current environment
  ./config.sh edit <env>        # Edit environment config

Examples:
  ./config.sh load dev          # Switch to development
  ./config.sh load prod         # Switch to production
  ./config.sh create testing    # Create testing environment
EOF
}

case "${1:-}" in
    init)
        create_default_environments
        ;;
    load)
        load_environment "${2:-}"
        ;;
    list)
        list_environments
        ;;
    create)
        create_environment "${2:-}"
        ;;
    show)
        if [ -f .env ]; then
            echo "Current environment (.env):"
            cat .env
        else
            echo "No .env file found"
        fi
        ;;
    edit)
        if [ -z "$2" ]; then
            echo "Usage: $0 edit <env>"
            exit 1
        fi
        nano "$ENVIRONMENTS_DIR/$2.env"
        ;;
    *)
        usage
        ;;
esac
