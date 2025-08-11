# Cross-Tool Memory MCP Server

A locally-hosted Model Context Protocol (MCP) server that provides intelligent, persistent memory storage across AI development tools like Claude, Cursor, and Kiro.

## Features

- **Cross-Tool Memory**: Maintain context and conversation history across different AI tools
- **Semantic Search**: Find relevant information using AI-powered semantic similarity
- **Local & Private**: Runs entirely on your local network with encrypted storage
- **MCP Compatible**: Works seamlessly with Claude, Cursor, Kiro, and other MCP-enabled tools
- **Intelligent Categorization**: Automatically tags and organizes conversations by project and topic
- **Learning System**: Improves suggestions over time based on your patterns and preferences

## Quick Start

### Automated Installation (Recommended)

#### Linux/macOS
```bash
git clone <repository-url>
cd cross-tool-memory-mcp
chmod +x scripts/install.sh
./scripts/install.sh
```

#### Windows (PowerShell)
```powershell
git clone <repository-url>
cd cross-tool-memory-mcp
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\scripts\install.ps1
```

The installation script will:
- Check system requirements
- Create necessary directories
- Build Docker images
- Set up management scripts
- Configure the service

### Using Docker (Manual)

1. Clone the repository and navigate to the project directory
2. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
3. Start the server:
   ```bash
   docker-compose up -d
   ```

The server will be available at `http://localhost:8000`

### Manual Installation

1. Ensure you have Python 3.11+ installed
2. Install the package:
   ```bash
   pip install -e .
   ```
3. Run the server:
   ```bash
   python -m cross_tool_memory.main
   ```

## Management

After installation, use the provided management scripts:

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

Or use Make commands:
```bash
make deploy-prod    # Deploy production environment
make backup         # Create backup
make health-check   # Check server health
```

## Data Management

### Data Export/Import

Export and import your conversation data, projects, and preferences:

```bash
# Export all data to a compressed file
python scripts/data_management.py export --path my_backup.zip

# Export without compression
python scripts/data_management.py export --path my_backup.json --no-compress

# Import data from backup
python scripts/data_management.py import my_backup.zip

# Import with overwrite of existing data
python scripts/data_management.py import my_backup.zip --overwrite

# Selective import (only conversations)
python scripts/data_management.py import my_backup.zip --conversations-only
```

### Data Cleanup

Clean up old data to free up space:

```bash
# Clean up conversations older than 1 year (dry run)
python scripts/data_management.py cleanup --conversations --days 365 --dry-run

# Actually delete old conversations
python scripts/data_management.py cleanup --conversations --days 365

# Clean up orphaned data (broken references)
python scripts/data_management.py cleanup --orphaned

# Keep at least 100 conversations regardless of age
python scripts/data_management.py cleanup --conversations --days 365 --keep-minimum 100
```

### Data Statistics and Validation

Monitor your data health:

```bash
# Show comprehensive data statistics
python scripts/data_management.py stats

# Validate data integrity
python scripts/data_management.py validate

# Get raw JSON output for scripting
python scripts/data_management.py stats --json
```

### System Backup and Restore

For complete system backups including AI models and configuration:

```bash
# Quick backup (database and config only)
python scripts/backup_restore.py backup

# Full backup (includes AI models and logs)
python scripts/backup_restore.py backup --include-logs

# Custom backup name
python scripts/backup_restore.py backup --name my-backup

# List available backups
python scripts/backup_restore.py list

# Restore from backup
python scripts/backup_restore.py restore backup_name

# Restore specific components only
python scripts/backup_restore.py restore backup_name --no-models
```

### Automated Backups

Set up automated backups using cron:

```bash
# Daily data export at 2 AM
0 2 * * * python3 /path/to/scripts/data_management.py export

# Weekly full system backup on Sundays at 3 AM
0 3 * * 0 python3 /path/to/scripts/backup_restore.py backup

# Monthly cleanup of old conversations
0 4 1 * * python3 /path/to/scripts/data_management.py cleanup --conversations --days 365
```

## Configuration

The server can be configured through:
- Environment variables (see `.env.example`)
- YAML configuration file (`config.yml`)
- Command line arguments

Key configuration options:
- **Database Path**: Location of SQLite database
- **Models Path**: Directory for AI models
- **Server Host/Port**: Network binding configuration
- **Encryption**: Enable/disable data encryption
- **Logging**: Log levels and file locations

## Integration

### MCP Protocol (Recommended)

Add the server to your MCP client configuration:

```json
{
  "mcpServers": {
    "cross-tool-memory": {
      "command": "cross-tool-memory",
      "args": ["--mode", "mcp"]
    }
  }
}
```

### REST API

For tools that don't support MCP, use the REST API:

1. Start the server in REST mode:
   ```bash
   cross-tool-memory --mode rest --host 127.0.0.1 --port 8000
   ```

2. Or run both MCP and REST simultaneously:
   ```bash
   cross-tool-memory --mode both --port 8000
   ```

#### REST API Endpoints

**Core Memory Operations:**
- `POST /context` - Store conversation context
- `POST /context/search` - Search and retrieve relevant context
- `GET /projects/{project_id}/context` - Get project-specific context
- `POST /history` - Get conversation history for a tool

**CRUD Operations:**
- `GET|POST|PUT|DELETE /conversations` - Manage conversations
- `GET|POST|PUT|DELETE /projects` - Manage projects  
- `GET|POST|PUT|DELETE /preferences` - Manage user preferences

**System:**
- `GET /health` - Health check
- `GET /stats` - Database statistics
- `GET /docs` - Interactive API documentation (Swagger UI)

#### Authentication

Set an API key for secure access:

```bash
export API_KEY="your-secret-key"
cross-tool-memory --mode rest --api-key $API_KEY
```

Then include the key in requests:
```bash
curl -H "Authorization: Bearer your-secret-key" http://localhost:8000/health
```

#### Example Usage

```python
import httpx

# Store context
async with httpx.AsyncClient() as client:
    response = await client.post("http://localhost:8000/context", json={
        "content": "I'm implementing a new feature...",
        "tool_name": "cursor",
        "metadata": {"tags": ["feature", "implementation"]},
        "project_id": "my-project"
    })

# Search for relevant context
async with httpx.AsyncClient() as client:
    response = await client.post("http://localhost:8000/context/search", json={
        "query": "feature implementation",
        "project_id": "my-project",
        "limit": 10
    })
```

See `examples/rest_api_client.py` for a complete client implementation.

## Development

1. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```
2. Run tests:
   ```bash
   pytest
   ```
3. Format code:
   ```bash
   black src/ tests/
   isort src/ tests/
   ```

## License

MIT License - see LICENSE file for details.
## D
ocumentation

For detailed information, see:

- **[Installation Guide](INSTALL.md)** - Comprehensive installation instructions for all platforms
- **[Deployment Guide](DEPLOYMENT.md)** - Production deployment strategies and configurations
- **[API Documentation](docs/REST_API.md)** - Complete REST API reference
- **[Security Guide](docs/SECURITY.md)** - Security best practices and configuration

## Uninstallation

To completely remove the Cross-Tool Memory MCP Server:

```bash
# Using the uninstall script
./scripts/uninstall.sh

# Or manually with Make
make uninstall
```

This will remove:
- Docker containers and images
- Installation directory and all data
- Systemd service (if installed)
- System logs

**Warning**: This will permanently delete all stored conversations and data. Create a backup first if needed.

## Troubleshooting

### Common Issues

1. **Port already in use**: Change the port in `docker-compose.yml` or `.env`
2. **Permission denied**: Fix directory permissions with `chmod -R 755 ~/.cross-tool-memory`
3. **Database locked**: Stop services and remove lock files in the data directory
4. **Models not downloading**: Check internet connection and disk space

### Health Check

Check if the server is running:
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "database": "connected",
  "models": "loaded"
}
```

### Logs

View server logs:
```bash
# Docker logs
docker-compose logs -f cross-tool-memory

# Log files (if file logging enabled)
tail -f ~/.cross-tool-memory/logs/memory-server.log
```

For more troubleshooting information, see the [Installation Guide](INSTALL.md#troubleshooting).

## Support

- Check the [troubleshooting section](#troubleshooting)
- Review server logs for error messages
- Ensure you're using the latest version
- Check the project's issue tracker for known issues