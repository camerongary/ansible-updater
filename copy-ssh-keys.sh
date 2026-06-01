#!/bin/bash

set -e

# SSH Key Distribution Script
# This script copies SSH keys to all discovered servers in the network

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
NETWORK_RANGE="${1:-192.168.12.0/24}"
SSH_USER="${2:-root}"
SSH_KEY="${3:-$HOME/.ssh/id_rsa}"
SSH_KEY_PUB="${SSH_KEY}.pub"
TIMEOUT=5
RETRIES=3

# Helper functions
print_header() {
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════${NC}"
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

    # Check if SSH key exists
    if [ ! -f "$SSH_KEY" ]; then
        print_error "SSH private key not found: $SSH_KEY"
        print_info "Generate SSH key with:"
        echo "  ssh-keygen -t ed25519 -f $SSH_KEY -N \"\""
        exit 1
    fi
    print_success "SSH private key found: $SSH_KEY"

    # Check if public key exists
    if [ ! -f "$SSH_KEY_PUB" ]; then
        print_error "SSH public key not found: $SSH_KEY_PUB"
        print_info "Public key should be generated automatically with private key"
        exit 1
    fi
    print_success "SSH public key found: $SSH_KEY_PUB"

    # Check if nmap is installed
    if ! command -v nmap &> /dev/null; then
        print_error "nmap is not installed"
        print_info "Install with: sudo apt-get install nmap"
        exit 1
    fi
    print_success "nmap is installed"

    # Check if ssh-copy-id is available
    if ! command -v ssh-copy-id &> /dev/null; then
        print_error "ssh-copy-id is not installed"
        print_info "Install with: sudo apt-get install openssh-client"
        exit 1
    fi
    print_success "ssh-copy-id is available"

    echo ""
}

# Discover servers with OS detection
discover_servers() {
    print_header "Discovering Servers in $NETWORK_RANGE"

    print_info "Running nmap scan with OS detection..."
    print_info "This detects the operating system of each server (may take 2-3 minutes)"
    echo ""
    
    # Run nmap with OS detection using TCP SYN scan
    # -O enables OS detection
    # -sS uses TCP SYN scan (more reliable for OS detection)
    # -sV attempts to determine service versions
    local nmap_output
    
    # First try with full OS detection (requires root and takes longer)
    if timeout 180 sudo nmap -O -sS "$NETWORK_RANGE" -oG - 2>/dev/null > /tmp/nmap_output.txt; then
        print_success "OS detection scan completed"
        nmap_output=$(cat /tmp/nmap_output.txt)
    else
        # Fallback: Try basic OS detection without sudo
        print_warning "Full OS detection not available, using basic detection..."
        if timeout 120 nmap -O "$NETWORK_RANGE" -oG - 2>/dev/null > /tmp/nmap_output.txt; then
            print_success "OS detection scan completed (basic)"
            nmap_output=$(cat /tmp/nmap_output.txt)
        else
            # Final fallback: Just find hosts without OS detection
            print_warning "OS detection unavailable, using simple host discovery..."
            if timeout 60 nmap -sn "$NETWORK_RANGE" -oG - 2>/dev/null > /tmp/nmap_output.txt; then
                nmap_output=$(cat /tmp/nmap_output.txt)
            else
                print_error "Network scan failed"
                exit 1
            fi
        fi
    fi
    
    # Extract IPs and OS info
    local servers_with_os=""
    while IFS= read -r line; do
        if [[ $line =~ "Up" ]]; then
            # Extract IP address
            local ip=$(echo "$line" | awk '{print $2}')
            
            # Try to extract OS info from various nmap output formats
            local os_info="Unknown"
            
            # Look for OS detection in the line
            if [[ $line =~ "OS:" ]]; then
                os_info=$(echo "$line" | sed -n 's/.*OS: *\([^|]*\).*/\1/p')
            fi
            
            # Alternative format: extracts from parentheses
            if [ "$os_info" = "Unknown" ] && [[ $line =~ \(.*\) ]]; then
                os_info=$(echo "$line" | sed 's/.*(\([^)]*\)).*/\1/')
            fi
            
            # Clean up OS string - remove extra spaces and special characters
            os_info=$(echo "$os_info" | xargs | cut -c1-50)  # Limit to 50 chars
            
            servers_with_os+="$ip|$os_info"$'\n'
        fi
    done < /tmp/nmap_output.txt
    
    if [ -z "$servers_with_os" ]; then
        print_error "No servers discovered in $NETWORK_RANGE"
        exit 1
    fi

    # Convert to array
    mapfile -t SERVER_ARRAY <<< "$servers_with_os"
    
    print_success "Discovered ${#SERVER_ARRAY[@]} server(s) with OS info:"
    echo ""
    
    # Display servers with OS info
    declare -gA SERVERS_MAP
    declare -gA SERVERS_OS
    
    for server_entry in "${SERVER_ARRAY[@]}"; do
        if [ -n "$server_entry" ]; then
            local ip=$(echo "$server_entry" | cut -d'|' -f1)
            local os=$(echo "$server_entry" | cut -d'|' -f2)
            
            # Display with OS information
            if [ "$os" != "Unknown" ] && [ -n "$os" ]; then
                printf "  • %-18s  →  %s\n" "$ip" "$os"
            else
                printf "  • %-18s  →  OS detection unavailable\n" "$ip"
            fi
            
            # Store for later use
            SERVERS_MAP["$ip"]=0
            SERVERS_OS["$ip"]="$os"
        fi
    done
    echo ""
}

# Test SSH connection
test_ssh_connection() {
    local ip=$1
    
    timeout "$TIMEOUT" ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no -i "$SSH_KEY" "$SSH_USER@$ip" "echo ok" &>/dev/null
    return $?
}

# Copy SSH key to server
copy_ssh_key() {
    local ip=$1
    local attempt=$2
    
    print_info "Copying SSH key to $ip (attempt $attempt/$RETRIES)..."
    
    # Use ssh-copy-id
    if timeout "$TIMEOUT" ssh-copy-id -i "$SSH_KEY" -o ConnectTimeout=3 -o StrictHostKeyChecking=no "$SSH_USER@$ip" &>/dev/null; then
        print_success "SSH key copied to $ip"
        SERVERS_MAP["$ip"]=1
        return 0
    else
        return 1
    fi
}

# Interactive SSH key copy
interactive_ssh_copy() {
    local ip=$1
    
    print_warning "Could not copy SSH key to $ip automatically"
    print_info "Please copy SSH key manually or enter password when prompted:"
    echo ""
    
    # Run ssh-copy-id interactively
    ssh-copy-id -i "$SSH_KEY" "$SSH_USER@$ip"
    
    if [ $? -eq 0 ]; then
        print_success "SSH key copied to $ip interactively"
        SERVERS_MAP["$ip"]=1
        return 0
    else
        print_error "Failed to copy SSH key to $ip"
        return 1
    fi
}

# Copy keys to all servers
copy_keys_to_all() {
    print_header "Copying SSH Keys to All Servers"

    local success_count=0
    local failed_servers=()
    local skipped_servers=()

    for ip in "${!SERVERS_MAP[@]}"; do
        echo ""
        print_info "Processing $ip..."
        
        # Check if key already exists
        if test_ssh_connection "$ip"; then
            print_success "SSH key already works on $ip (no action needed)"
            SERVERS_MAP["$ip"]=1
            ((success_count++))
            continue
        fi

        # Try to copy key with retries
        local copied=0
        for attempt in $(seq 1 "$RETRIES"); do
            if copy_ssh_key "$ip" "$attempt"; then
                ((success_count++))
                copied=1
                break
            fi
            
            if [ $attempt -lt "$RETRIES" ]; then
                print_warning "Retry in 2 seconds..."
                sleep 2
            fi
        done

        # If still failed, offer interactive copy
        if [ $copied -eq 0 ]; then
            read -p "Would you like to try interactive copy for $ip? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                if interactive_ssh_copy "$ip"; then
                    ((success_count++))
                else
                    failed_servers+=("$ip")
                fi
            else
                skipped_servers+=("$ip")
            fi
        fi
    done

    echo ""
}

# Verify SSH access
verify_ssh_access() {
    print_header "Verifying SSH Access"

    local verified=0
    local failed=0

    for ip in "${!SERVERS_MAP[@]}"; do
        if [ "${SERVERS_MAP[$ip]}" -eq 1 ]; then
            if test_ssh_connection "$ip"; then
                print_success "SSH access verified: $ip"
                ((verified++))
            else
                print_error "SSH access verification failed: $ip"
                ((failed++))
            fi
        fi
    done

    echo ""
    print_info "Verification complete:"
    echo "  • Verified: $verified"
    echo "  • Failed: $failed"
    echo ""
}

# Summary report
print_summary() {
    print_header "Summary Report"

    echo "Network Range:     $NETWORK_RANGE"
    echo "SSH User:          $SSH_USER"
    echo "SSH Key:           $SSH_KEY"
    echo ""
    echo "SSH Key Distribution Status:"
    echo ""
    
    for ip in $(printf '%s\n' "${!SERVERS_MAP[@]}" | sort -V); do
        local status_icon
        local status_text
        
        if [ "${SERVERS_MAP[$ip]}" -eq 1 ]; then
            status_icon="${GREEN}✓${NC}"
            status_text="SSH Key Copied"
        else
            status_icon="${RED}✗${NC}"
            status_text="Failed"
        fi
        
        local os="${SERVERS_OS[$ip]:-Unknown}"
        
        # Display: ✓ IP → OS | Status
        printf "  %b %-18s → %-40s | %s\n" "$status_icon" "$ip" "$os" "$status_text"
    done

    echo ""
    print_info "Next steps:"
    echo "  1. Test with: ssh -i $SSH_KEY $SSH_USER@<ip>"
    echo "  2. Deploy with: docker-compose up -d"
    echo "  3. Monitor with: docker-compose logs -f"
    echo ""
    
    # Show OS summary
    echo ""
    print_info "Operating Systems detected:"
    local os_list=$(for ip in "${!SERVERS_OS[@]}"; do echo "${SERVERS_OS[$ip]}"; done | sort | uniq -c)
    echo "$os_list" | while read count os; do
        if [ -n "$os" ] && [ "$os" != "Unknown" ]; then
            printf "  • %s: %d server(s)\n" "$os" "$count"
        fi
    done
    echo ""
}

# Cleanup on exit
cleanup() {
    # Remove temporary files if any
    :
}

trap cleanup EXIT

# Main execution
main() {
    print_header "SSH Key Distribution Tool"
    echo ""
    echo "This tool will copy your SSH public key to all discovered servers"
    echo "Network Range: $NETWORK_RANGE"
    echo "SSH User: $SSH_USER"
    echo "SSH Key: $SSH_KEY"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_warning "Cancelled by user"
        exit 0
    fi

    check_prerequisites
    discover_servers
    copy_keys_to_all
    verify_ssh_access
    print_summary
}

# Show usage
if [ "$1" == "-h" ] || [ "$1" == "--help" ]; then
    echo "Usage: $0 [NETWORK_RANGE] [SSH_USER] [SSH_KEY_PATH]"
    echo ""
    echo "Parameters:"
    echo "  NETWORK_RANGE - Network to scan (default: 192.168.12.0/24)"
    echo "  SSH_USER      - SSH username (default: root)"
    echo "  SSH_KEY_PATH  - Path to SSH private key (default: ~/.ssh/id_rsa)"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Uses defaults"
    echo "  $0 192.168.12.0/24 root ~/.ssh/id_rsa"
    echo "  $0 10.0.0.0/24 ubuntu ~/.ssh/deploy_key"
    exit 0
fi

# Run main
main
