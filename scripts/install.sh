#!/bin/bash

# Cross-Tool Memory MCP Server Installation Script
# This script sets up the Cross-Tool Memory MCP Server for local deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DEFAULT_INSTALL_DIR="$HOME/.cross-tool-memory"
DEFAULT_PORT=8000
DEFAULT_HOST="127.0.0.1"

# Functions
print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}Cross-Tool Memory MCP Server${NC}"
    echo -e "${BLUE}Installation Script${NC}"
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

check_requirements() {
    print_info "Checking system requirements..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        echo "Visit: https://docs.docker.com/get-docker/"
        exit 1
    fi
    print_success "Docker found"
    
    # Check Docker Compose
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        echo "Visit: https://docs.docker.com/compose/install/"
        exit 1
    fi
    print_success "Docker Compose found"
    
    # Check if port is available
    if lsof -Pi :$DEFAULT_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
        print_warning "Port $DEFAULT_PORT is already in use. You may need to change the port in docker-compose.yml"
    else
        print_success "Port $DEFAULT_PORT is available"
    fi
}

create_directories() {
    print_info "Creating installation directories..."
    
    mkdir -p "$DEFAULT_INSTALL_DIR"/{data,models,logs,backups,ssl}
    print_success "Created directory structure at $DEFAULT_INSTALL_DIR"
}

copy_files() {
    print_info "Copying configuration files..."
    
    # Copy docker-compose.yml
    cp docker-compose.yml "$DEFAULT_INSTALL_DIR/"
    print_success "Copied docker-compose.yml"
    
    # Copy and customize config.yml
    if [ -f "config.yml" ]; then
        cp config.yml "$DEFAULT_INSTALL_DIR/"
        print_success "Copied config.yml"
    else
        print_warning "config.yml not found, you'll need to create one"
    fi
    
    # Copy nginx config if it exists
    if [ -f "nginx.conf" ]; then
        cp nginx.conf "$DEFAULT_INSTALL_DIR/"
        print_success "Copied nginx.conf"
    fi
    
    # Copy environment example
    if [ -f ".env.example" ]; then
        cp .env.example "$DEFAULT_INSTALL_DIR/.env"
        print_success "Copied .env.example as .env"
    fi
}

setup_environment() {
    print_info "Setting up environment configuration..."
    
    # Update paths in .env file
    if [ -f "$DEFAULT_INSTALL_DIR/.env" ]; then
        sed -i.bak "s|DATABASE_PATH=.*|DATABASE_PATH=$DEFAULT_INSTALL_DIR/data/memory.db|g" "$DEFAULT_INSTALL_DIR/.env"
        sed -i.bak "s|MODELS_PATH=.*|MODELS_PATH=$DEFAULT_INSTALL_DIR/models|g" "$DEFAULT_INSTALL_DIR/.env"
        sed -i.bak "s|LOG_FILE=.*|LOG_FILE=$DEFAULT_INSTALL_DIR/logs/memory-server.log|g" "$DEFAULT_INSTALL_DIR/.env"
        rm "$DEFAULT_INSTALL_DIR/.env.bak"
        print_success "Updated environment configuration"
    fi
}

build_image() {
    print_info "Building Docker image..."
    
    cd "$DEFAULT_INSTALL_DIR"
    docker build -t cross-tool-memory-mcp .
    print_success "Docker image built successfully"
}

create_systemd_service() {
    if command -v systemctl &> /dev/null; then
        print_info "Creating systemd service..."
        
        cat > "$DEFAULT_INSTALL_DIR/cross-tool-memory.service" << EOF
[Unit]
Description=Cross-Tool Memory MCP Server
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$DEFAULT_INSTALL_DIR
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
EOF
        
        print_success "Systemd service file created at $DEFAULT_INSTALL_DIR/cross-tool-memory.service"
        print_info "To install the service, run:"
        echo "  sudo cp $DEFAULT_INSTALL_DIR/cross-tool-memory.service /etc/systemd/system/"
        echo "  sudo systemctl daemon-reload"
        echo "  sudo systemctl enable cross-tool-memory"
        echo "  sudo systemctl start cross-tool-memory"
    fi
}

create_management_scripts() {
    print_info "Creating management scripts..."
    
    # Start script
    cat > "$DEFAULT_INSTALL_DIR/start.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "Starting Cross-Tool Memory MCP Server..."
docker-compose up -d
echo "Server started. Check status with: docker-compose ps"
echo "View logs with: docker-compose logs -f"
EOF
    chmod +x "$DEFAULT_INSTALL_DIR/start.sh"
    
    # Stop script
    cat > "$DEFAULT_INSTALL_DIR/stop.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "Stopping Cross-Tool Memory MCP Server..."
docker-compose down
echo "Server stopped."
EOF
    chmod +x "$DEFAULT_INSTALL_DIR/stop.sh"
    
    # Status script
    cat > "$DEFAULT_INSTALL_DIR/status.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "Cross-Tool Memory MCP Server Status:"
docker-compose ps
echo
echo "Recent logs:"
docker-compose logs --tail=20
EOF
    chmod +x "$DEFAULT_INSTALL_DIR/status.sh"
    
    # Update script
    cat > "$DEFAULT_INSTALL_DIR/update.sh" << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
echo "Updating Cross-Tool Memory MCP Server..."
docker-compose pull
docker-compose up -d
echo "Update complete."
EOF
    chmod +x "$DEFAULT_INSTALL_DIR/update.sh"
    
    print_success "Created management scripts"
}

print_completion() {
    echo
    print_success "Installation completed successfully!"
    echo
    print_info "Installation directory: $DEFAULT_INSTALL_DIR"
    print_info "To start the server:"
    echo "  cd $DEFAULT_INSTALL_DIR && ./start.sh"
    echo
    print_info "To stop the server:"
    echo "  cd $DEFAULT_INSTALL_DIR && ./stop.sh"
    echo
    print_info "To check status:"
    echo "  cd $DEFAULT_INSTALL_DIR && ./status.sh"
    echo
    print_info "Server will be available at: http://$DEFAULT_HOST:$DEFAULT_PORT"
    print_info "Health check: http://$DEFAULT_HOST:$DEFAULT_PORT/health"
    echo
    print_warning "Don't forget to:"
    echo "  1. Review and customize $DEFAULT_INSTALL_DIR/config.yml"
    echo "  2. Set up your MCP client configuration"
    echo "  3. Configure SSL certificates if using HTTPS"
}

# Main installation flow
main() {
    print_header
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root. Consider running as a regular user."
    fi
    
    check_requirements
    create_directories
    copy_files
    setup_environment
    build_image
    create_systemd_service
    create_management_scripts
    print_completion
}

# Run main function
main "$@"