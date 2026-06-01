#!/usr/bin/env bash

# Backup and Restore Script for Ansible Update System

set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Logging functions
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Create backup
backup() {
    echo "Creating backup..."
    
    # Check what to backup
    local items_to_backup=()
    
    if [ -f ".env" ]; then
        items_to_backup+=(".env")
    fi
    
    if [ -d "ansible" ]; then
        items_to_backup+=("ansible")
    fi
    
    if [ -d "reports" ]; then
        items_to_backup+=("reports")
    fi
    
    if [ -d "environments" ]; then
        items_to_backup+=("environments")
    fi
    
    if [ ${#items_to_backup[@]} -eq 0 ]; then
        log_warn "Nothing to backup"
        return 1
    fi
    
    # Create backup archive
    tar -czf "$BACKUP_FILE" "${items_to_backup[@]}" 2>/dev/null
    
    local size=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "Backup created: $BACKUP_FILE ($size)"
    
    # Keep only last 10 backups
    cleanup_old_backups
}

# Cleanup old backups
cleanup_old_backups() {
    local backup_count=$(ls -1 "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | wc -l)
    
    if [ "$backup_count" -gt 10 ]; then
        log_warn "Cleaning up old backups (keeping last 10)..."
        ls -1t "$BACKUP_DIR"/backup_*.tar.gz | tail -n +11 | xargs -r rm
    fi
}

# List backups
list_backups() {
    echo "Available backups:"
    ls -1h "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | while read file; do
        size=$(du -h "$file" | cut -f1)
        date=$(basename "$file" .tar.gz | sed 's/backup_//')
        printf "  %-20s %s\n" "$size" "$date"
    done
    
    if [ ! -d "$BACKUP_DIR" ] || [ -z "$(ls -1 "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null)" ]; then
        echo "  (no backups found)"
    fi
}

# Restore backup
restore() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Please specify a backup file"
        echo "Usage: $0 restore <file>"
        echo ""
        list_backups
        return 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    # Ask for confirmation
    read -p "Restore from $backup_file? This will overwrite current files. (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warn "Restore cancelled"
        return 0
    fi
    
    # Create safety backup first
    backup
    log_info "Safety backup created"
    
    # Restore files
    tar -xzf "$backup_file"
    log_info "Restore completed from $backup_file"
}

# Export configuration
export_config() {
    local export_file="config_export_$TIMESTAMP.json"
    
    if [ ! -f ".env" ]; then
        log_error ".env file not found"
        return 1
    fi
    
    # Create JSON export
    cat > "$export_file" << EOF
{
    "exported_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
    "configuration": {
EOF
    
    # Add .env variables as JSON
    while IFS= read -r line; do
        if [ ! -z "$line" ] && [[ ! $line =~ ^# ]]; then
            key=$(echo "$line" | cut -d= -f1)
            value=$(echo "$line" | cut -d= -f2-)
            echo "        \"$key\": \"$value\"," >> "$export_file"
        fi
    done < .env
    
    # Remove trailing comma and close JSON
    sed -i '$ s/,$//' "$export_file"
    echo "    }" >> "$export_file"
    echo "}" >> "$export_file"
    
    log_info "Configuration exported to: $export_file"
}

# Import configuration
import_config() {
    local import_file="$1"
    
    if [ ! -f "$import_file" ]; then
        log_error "Import file not found: $import_file"
        return 1
    fi
    
    # Extract values from JSON and create .env
    cat > ".env.imported" << EOF
# Imported configuration from $import_file
# $(date)

EOF
    
    # Parse JSON and extract key-value pairs
    python3 << 'PYTHON_EOF'
import json
import sys

try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
        for key, value in data.get('configuration', {}).items():
            print(f"{key}={value}")
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_EOF sys.argv[1] >> ".env.imported" 2>/dev/null || true
    
    # Ask for confirmation
    echo ""
    echo "Imported configuration:"
    cat ".env.imported"
    echo ""
    read -p "Apply this configuration? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        mv ".env.imported" ".env"
        log_info "Configuration imported and applied"
    else
        rm -f ".env.imported"
        log_warn "Import cancelled"
    fi
}

# Archive old reports
archive_reports() {
    if [ ! -d "reports" ]; then
        log_warn "No reports directory found"
        return 0
    fi
    
    local archive_file="$BACKUP_DIR/reports_archive_$TIMESTAMP.tar.gz"
    tar -czf "$archive_file" reports/
    
    local size=$(du -h "$archive_file" | cut -f1)
    log_info "Reports archived to: $archive_file ($size)"
    
    # Clear old reports
    read -p "Clear reports older than 7 days? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        find reports -name "*.json" -mtime +7 -delete
        log_info "Old reports cleaned up"
    fi
}

# Verify backup integrity
verify_backup() {
    local backup_file="$1"
    
    if [ -z "$backup_file" ]; then
        log_error "Please specify a backup file"
        return 1
    fi
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    echo "Verifying backup integrity..."
    if tar -tzf "$backup_file" > /dev/null 2>&1; then
        log_info "Backup integrity verified"
        echo ""
        echo "Contents:"
        tar -tzf "$backup_file" | head -20
        local count=$(tar -tzf "$backup_file" | wc -l)
        echo "  ... and $((count-20)) more files"
        return 0
    else
        log_error "Backup is corrupted"
        return 1
    fi
}

# Usage
usage() {
    cat << 'EOF'
Backup and Restore Script for Ansible Update System

Usage:
  ./backup.sh backup              # Create new backup
  ./backup.sh list                # List all backups
  ./backup.sh restore <file>      # Restore from backup
  ./backup.sh verify <file>       # Verify backup integrity
  ./backup.sh export              # Export configuration as JSON
  ./backup.sh import <file>       # Import configuration from JSON
  ./backup.sh archive-reports     # Archive and clean reports

Examples:
  ./backup.sh backup              # Create backup
  ./backup.sh restore backups/backup_20240115_120000.tar.gz
  ./backup.sh export              # Export current config
  ./backup.sh import config.json  # Import config from file
EOF
}

# Main
case "${1:-}" in
    backup)
        backup
        ;;
    list)
        list_backups
        ;;
    restore)
        restore "${2:-}"
        ;;
    verify)
        verify_backup "${2:-}"
        ;;
    export)
        export_config
        ;;
    import)
        import_config "${2:-}"
        ;;
    archive-reports)
        archive_reports
        ;;
    *)
        usage
        ;;
esac
