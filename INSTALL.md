# Cross-Tool Memory MCP Server Installation Guide

This guide provides comprehensive instructions for installing and deploying the Cross-Tool Memory MCP Server locally.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Installation](#quick-installation)
- [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [MCP Client Setup](#mcp-client-setup)
- [Backup and Restore](#backup-and-restore)
- [Troubleshooting](#troubleshooting)
- [Uninstallation](#uninstallation)

## Prerequisites

### System Requirements

- **Operating System**: Linux, macOS, or Windows 10/11
- **Memory**: Minimum 2GB RAM, 4GB recommended
- **Storage**: 5GB free space (more if including AI models)
- **Network**: Local network access

### Required Software

1. **Docker** (version 20.10 or later)
   - Linux: Follow [Docker Engine installation](https://docs.docker.com/engine/install/)
   - macOS: Install [Docker Desktop](https://docs.docker.com/desktop/mac/)
   - Windows: Install [Docker Desktop](https://docs.docker.com/desktop/windows/)

2. **Docker Compose** (version 2.0 or later)
   - Usually included with Docker Desktop
   - Linux: May need separate installation

### Optional Software

- **Python 3.11+** (for running backup/restore scripts directly)
- **Git** (for cloning the repository)

## Quick Installation

### Using Installation Scripts

#### Linux/macOS

```bash
# Clone the repository
git clone <repository-url>
cd cross-tool-memory-mcp

# Run the installation script
chmod +x scripts/install.sh
./scripts/install.sh
```

#### Windows (PowerShell)

```powershell
# Clone the repository
git clone <repository-url>
cd cross-tool-memory-mcp

# Run the installation script
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\install.ps1
```

The installation script will:
- Check system requirements
- Create necessary directories
- Copy configuration files
- Build the Docker image
- Create management scripts
- Set up systemd service (Linux only)

### Using Docker Compose (Alternative)

```bash
# Clone the repository
git clone <repository-url>
cd cross-tool-memory-mcp

# Create data directories
mkdir -p data models logs

# Start the server
docker-compose up -d
```

## Manual Installation

### Step 1: Prepare Directories

```bash
# Create installation directory
mkdir -p ~/.cross-tool-memory/{data,models,logs,backups,ssl}
cd ~/.cross-tool-memory
```

### Step 2: Copy Configuration Files

```bash
# Copy from the repository
cp /path/to/repo/docker-compose.yml .
cp /path/to/repo/config.yml .
cp /path/to/repo/.env.example .env
cp /path/to/repo/nginx.conf .  # Optional, for HTTPS
```

### Step 3: Customize Configuration

Edit the `.env` file to match your setup:

```bash
# Database configuration
DATABASE_PATH=/home/user/.cross-tool-memory/data/memory.db
MODELS_PATH=/home/user/.cross-tool-memory/models

# Server configuration
MEMORY_SERVER_HOST=127.0.0.1
MEMORY_SERVER_PORT=8000

# Logging
LOG_FILE=/home/user/.cross-tool-memory/logs/memory-server.log
LOG_LEVEL=INFO
```

### Step 4: Build and Start

```bash
# Build the Docker image
docker build -t cross-tool-memory-mcp /path/to/repo

# Start the services
docker-compose up -d
```

## Configuration

### Basic Configuration

The main configuration file is `config.yml`. Key sections include:

```yaml
# Server settings
server:
  host: "127.0.0.1"
  port: 8000
  cors_origins: ["*"]

# Database settings
database:
  path: "./data/memory.db"
  backup_interval: 3600  # seconds

# AI Models settings
models:
  embedding_model: "all-MiniLM-L6-v2"
  path: "./models"
  auto_download: true

# Security settings
security:
  enable_encryption: true
  rate_limit: 100  # requests per minute
```

### Environment Variables

You can override configuration using environment variables:

```bash
# Server configuration
export MEMORY_SERVER_HOST=0.0.0.0
export MEMORY_SERVER_PORT=8000

# Database configuration
export DATABASE_PATH=/app/data/memory.db

# Model configuration
export MODELS_PATH=/app/models
export EMBEDDING_MODEL=all-MiniLM-L6-v2

# Security
export ENABLE_ENCRYPTION=true
export API_KEY=your-optional-api-key
```

### HTTPS Configuration (Optional)

To enable HTTPS with nginx:

1. Generate SSL certificates:
```bash
# Self-signed certificate (for development)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ~/.cross-tool-memory/ssl/server.key \
  -out ~/.cross-tool-memory/ssl/server.crt
```

2. Enable nginx in docker-compose:
```bash
docker-compose --profile with-nginx up -d
```

## MCP Client Setup

### Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "cross-tool-memory": {
      "command": "curl",
      "args": [
        "-X", "POST",
        "http://localhost:8000/mcp",
        "-H", "Content-Type: application/json",
        "-d", "@-"
      ]
    }
  }
}
```

### Cursor

Add to your Cursor MCP configuration:

```json
{
  "mcpServers": {
    "cross-tool-memory": {
      "command": "python",
      "args": ["-m", "mcp_client", "--server", "http://localhost:8000/mcp"]
    }
  }
}
```

### Kiro

Configure in Kiro's MCP settings:

```json
{
  "mcpServers": {
    "cross-tool-memory": {
      "command": "uvx",
      "args": ["cross-tool-memory-mcp@latest"],
      "env": {
        "MEMORY_SERVER_URL": "http://localhost:8000"
      }
    }
  }
}
```

## Management Commands

### Using Management Scripts

After installation, you can use the provided scripts:

```bash
# Start the server
~/.cross-tool-memory/start.sh

# Stop the server
~/.cross-tool-memory/stop.sh

# Check status
~/.cross-tool-memory/status.sh

# Update the server
~/.cross-tool-memory/update.sh
```

### Using Docker Compose Directly

```bash
cd ~/.cross-tool-memory

# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Update images
docker-compose pull && docker-compose up -d
```

### Using Systemd (Linux)

If you installed the systemd service:

```bash
# Start the service
sudo systemctl start cross-tool-memory

# Enable auto-start on boot
sudo systemctl enable cross-tool-memory

# Check status
sudo systemctl status cross-tool-memory

# View logs
sudo journalctl -u cross-tool-memory -f
```

## Backup and Restore

### Using the Backup Script

The server includes a comprehensive backup and restore utility:

```bash
# Create a backup
python scripts/backup_restore.py backup

# Create a backup with custom name
python scripts/backup_restore.py backup --name my-backup

# Create a backup without AI models (faster)
python scripts/backup_restore.py backup --no-models

# List available backups
python scripts/backup_restore.py list

# Restore from backup
python scripts/backup_restore.py restore backup_name

# Restore specific components only
python scripts/backup_restore.py restore backup_name --no-models

# Clean up old backups (keep last 5)
python scripts/backup_restore.py cleanup --keep 5
```

### Manual Backup

```bash
# Stop the server
docker-compose down

# Create backup directory
mkdir -p ~/memory-backups/$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=~/memory-backups/$(date +%Y%m%d_%H%M%S)

# Copy data
cp -r ~/.cross-tool-memory/data $BACKUP_DIR/
cp -r ~/.cross-tool-memory/models $BACKUP_DIR/
cp ~/.cross-tool-memory/config.yml $BACKUP_DIR/
cp ~/.cross-tool-memory/.env $BACKUP_DIR/

# Create archive
tar -czf $BACKUP_DIR.tar.gz -C ~/memory-backups $(basename $BACKUP_DIR)

# Restart server
docker-compose up -d
```

### Automated Backups

Set up automated backups using cron:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /usr/bin/python3 /path/to/scripts/backup_restore.py backup --no-models

# Add weekly full backup on Sundays at 3 AM
0 3 * * 0 /usr/bin/python3 /path/to/scripts/backup_restore.py backup

# Clean up old backups monthly
0 4 1 * * /usr/bin/python3 /path/to/scripts/backup_restore.py cleanup --keep 10
```

## Health Checks and Monitoring

### Health Check Endpoint

The server provides a health check endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.0.0",
  "database": "connected",
  "models": "loaded"
}
```

### Log Monitoring

View server logs:

```bash
# Docker logs
docker-compose logs -f cross-tool-memory

# Log files (if file logging is enabled)
tail -f ~/.cross-tool-memory/logs/memory-server.log
```

### Performance Monitoring

Monitor resource usage:

```bash
# Docker stats
docker stats cross-tool-memory-mcp

# System resources
htop
```

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Check what's using the port
lsof -i :8000

# Change port in docker-compose.yml
ports:
  - "8001:8000"  # Use port 8001 instead
```

#### Permission Denied

```bash
# Fix directory permissions
sudo chown -R $USER:$USER ~/.cross-tool-memory
chmod -R 755 ~/.cross-tool-memory
```

#### Database Locked

```bash
# Stop all services
docker-compose down

# Check for stale lock files
rm ~/.cross-tool-memory/data/*.lock

# Restart services
docker-compose up -d
```

#### Models Not Downloading

```bash
# Check internet connection
curl -I https://huggingface.co

# Manually download models
docker-compose exec cross-tool-memory python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
"
```

### Log Analysis

Check logs for specific issues:

```bash
# Database errors
docker-compose logs cross-tool-memory | grep -i "database\|sqlite"

# Model loading errors
docker-compose logs cross-tool-memory | grep -i "model\|embedding"

# Network errors
docker-compose logs cross-tool-memory | grep -i "connection\|network"
```

### Performance Issues

If the server is slow:

1. **Check available memory**:
   ```bash
   free -h
   docker stats
   ```

2. **Optimize database**:
   ```bash
   # Connect to database and run VACUUM
   sqlite3 ~/.cross-tool-memory/data/memory.db "VACUUM;"
   ```

3. **Use smaller AI models**:
   ```yaml
   # In config.yml
   models:
     embedding_model: "all-MiniLM-L6-v2"  # Smaller, faster model
   ```

## Uninstallation

### Complete Removal

```bash
# Stop services
docker-compose down

# Remove Docker images
docker rmi cross-tool-memory-mcp
docker system prune -f

# Remove installation directory
rm -rf ~/.cross-tool-memory

# Remove systemd service (if installed)
sudo systemctl stop cross-tool-memory
sudo systemctl disable cross-tool-memory
sudo rm /etc/systemd/system/cross-tool-memory.service
sudo systemctl daemon-reload
```

### Keep Data Only

```bash
# Stop services
docker-compose down

# Remove Docker images
docker rmi cross-tool-memory-mcp

# Keep only data and backups
cd ~/.cross-tool-memory
rm -rf models logs ssl
rm docker-compose.yml config.yml .env nginx.conf
rm *.sh *.bat
```

## Security Considerations

### Network Security

- The server binds to `127.0.0.1` by default (localhost only)
- For network access, change to `0.0.0.0` but ensure firewall protection
- Use HTTPS in production environments

### Data Security

- Database is encrypted at rest when encryption is enabled
- Backup files should be stored securely
- Consider using API keys for additional authentication

### Updates

- Regularly update Docker images
- Monitor for security updates
- Keep backup before major updates

## Support

For issues and questions:

1. Check the [troubleshooting section](#troubleshooting)
2. Review server logs for error messages
3. Check the project's issue tracker
4. Ensure you're using the latest version

## Next Steps

After installation:

1. Configure your MCP clients to connect to the server
2. Test the connection with a simple query
3. Set up automated backups
4. Configure monitoring and alerting
5. Customize the configuration for your needs