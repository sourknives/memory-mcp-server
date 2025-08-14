#!/bin/bash

# Cross-Tool Memory MCP Server Uninstallation Script
# This script removes the Cross-Tool Memory MCP Server installation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEFAULT_INSTALL_DIR="$HOME/.cross-tool-memory"

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}Cross-Tool Memory MCP Server${NC}"
    echo -e "${BLUE}Uninstallation Script${NC}"
    echo -e "${BLUE}================================${NC}"
    echo
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

confirm_uninstall() {
    echo -e "${YELLOW}WARNING: This will remove the Cross-Tool Memory MCP Server and all its data.${NC}"
    echo
    echo "This will remove:"
    echo "  - Docker containers and images"
    echo "  - Installation directory: $DEFAULT_INSTALL_DIR"
    echo "  - All stored conversations and data"
    echo "  - Downloaded AI models"
    echo "  - Configuration files"
    echo "  - Systemd service (if installed)"
    echo
    
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
    
    echo
    read -p "Type 'DELETE' to confirm complete removal: " -r
    if [[ $REPLY != "DELETE" ]]; then
        echo "Uninstallation cancelled."
        exit 0
    fi
}

stop_services() {
    print_info "Stopping services..."
    
    # Stop systemd service if it exists
    if systemctl is-active --quiet cross-tool-memory 2>/dev/null; then
        sudo systemctl stop cross-tool-memory
        print_success "Stopped systemd service"
    fi
    
    # Stop docker-compose services
    if [ -f "$DEFAULT_INSTALL_DIR/docker-compose.yml" ]; then
        cd "$DEFAULT_INSTALL_DIR"
        if command -v docker-compose &> /dev/null; then
            docker-compose down -v 2>/dev/null || true
        elif docker compose version &> /dev/null 2>&1; then
            docker compose down -v 2>/dev/null || true
        fi
        print_success "Stopped Docker services"
    fi
}

remove_docker_resources() {
    print_info "Removing Docker resources..."
    
    # Remove containers
    docker rm -f cross-tool-memory-mcp cross-tool-memory-nginx 2>/dev/null || true
    
    # Remove images
    docker rmi -f cross-tool-memory-mcp 2>/dev/null || true
    docker rmi -f $(docker images -q --filter "reference=cross-tool-memory*") 2>/dev/null || true
    
    # Remove volumes
    docker volume rm -f cross-tool-memory_memory-data cross-tool-memory_memory-models 2>/dev/null || true
    
    # Clean up unused resources
    docker system prune -f 2>/dev/null || true
    
    print_success "Removed Docker resources"
}

remove_systemd_service() {
    print_info "Removing systemd service..."
    
    if [ -f "/etc/systemd/system/cross-tool-memory.service" ]; then
        sudo systemctl stop cross-tool-memory 2>/dev/null || true
        sudo systemctl disable cross-tool-memory 2>/dev/null || true
        sudo rm -f /etc/systemd/system/cross-tool-memory.service
        sudo systemctl daemon-reload
        print_success "Removed systemd service"
    else
        print_info "No systemd service found"
    fi
}

remove_installation_directory() {
    print_info "Removing installation directory..."
    
    if [ -d "$DEFAULT_INSTALL_DIR" ]; then
        # Create a final backup if user wants
        read -p "Create a final backup before removal? (y/n): " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            BACKUP_FILE="$HOME/cross-tool-memory-final-backup-$(date +%Y%m%d_%H%M%S).tar.gz"
            tar -czf "$BACKUP_FILE" -C "$(dirname "$DEFAULT_INSTALL_DIR")" "$(basename "$DEFAULT_INSTALL_DIR")" 2>/dev/null || true
            if [ -f "$BACKUP_FILE" ]; then
                print_success "Final backup created: $BACKUP_FILE"
            fi
        fi
        
        rm -rf "$DEFAULT_INSTALL_DIR"
        print_success "Removed installation directory"
    else
        print_info "Installation directory not found"
    fi
}

remove_mcp_configurations() {
    print_info "Checking for MCP client configurations..."
    
    # Claude Desktop configuration
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
    if [ -f "$CLAUDE_CONFIG" ]; then
        print_warning "Found Claude Desktop configuration at: $CLAUDE_CONFIG"
        print_warning "You may want to manually remove the 'cross-tool-memory' server entry"
    fi
    
    # Kiro configuration
    KIRO_CONFIG="$HOME/.kiro/settings/mcp.json"
    if [ -f "$KIRO_CONFIG" ]; then
        print_warning "Found Kiro MCP configuration at: $KIRO_CONFIG"
        print_warning "You may want to manually remove the 'cross-tool-memory' server entry"
    fi
    
    print_info "MCP client configurations need to be updated manually"
}

cleanup_logs() {
    print_info "Cleaning up system logs..."
    
    # Clean up systemd logs
    if command -v journalctl &> /dev/null; then
        sudo journalctl --vacuum-time=1d --unit=cross-tool-memory 2>/dev/null || true
    fi
    
    # Clean up Docker logs
    docker system prune --volumes -f 2>/dev/null || true
    
    print_success "Cleaned up logs"
}

print_completion() {
    echo
    print_success "Uninstallation completed successfully!"
    echo
    print_info "The following items have been removed:"
    echo "  ✓ Docker containers and images"
    echo "  ✓ Installation directory"
    echo "  ✓ Systemd service (if present)"
    echo "  ✓ System logs"
    echo
    print_warning "Manual cleanup may be needed for:"
    echo "  - MCP client configurations (Claude, Kiro, etc.)"
    echo "  - Custom backup files"
    echo "  - Firewall rules (if configured)"
    echo
    print_info "Thank you for using Cross-Tool Memory MCP Server!"
}

# Main uninstallation flow
main() {
    print_header
    
    # Check if installation exists
    if [ ! -d "$DEFAULT_INSTALL_DIR" ] && ! docker images | grep -q cross-tool-memory; then
        print_warning "Cross-Tool Memory MCP Server doesn't appear to be installed."
        echo "Installation directory not found: $DEFAULT_INSTALL_DIR"
        echo "No Docker images found matching 'cross-tool-memory'"
        exit 0
    fi
    
    confirm_uninstall
    stop_services
    remove_docker_resources
    remove_systemd_service
    remove_installation_directory
    remove_mcp_configurations
    cleanup_logs
    print_completion
}

# Run main function
main "$@"