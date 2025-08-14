# Cortex MCP Server

The full MCP server implementation providing intelligent, persistent memory storage.

## Installation

### Docker (Recommended)

```bash
docker-compose up -d
```

### Manual Installation

```bash
pip install -e .
python -m cortex_mcp.main
```

## Configuration

Configure via environment variables or `config.yml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000
  
database:
  path: "memory.db"
  
security:
  api_keys:
    - "your-api-key-here"
  enable_encryption: true
```

## Available Modes

- **MCP Mode:** `python -m cortex_mcp.main --mode mcp`
- **REST API:** `python -m cortex_mcp.main --mode rest`
- **Web Interface:** `python -m cortex_mcp.main --mode web`

## API Endpoints

- `GET /health` - Health check
- `POST /api/v1/tools/{tool_name}` - Execute MCP tools
- `GET /api/v1/memories` - List memories
- `POST /api/v1/memories` - Store memory
- `GET /ui` - Web interface

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/
isort src/
```

## Deployment

See `DEPLOYMENT.md` for production deployment guides including:
- Docker deployment
- Kubernetes deployment
- Security configuration
- SSL/TLS setup

## API Key Management

Generate and manage API keys for secure access:

```bash
# Generate a new API key
python scripts/manage_api_keys.py generate --name "production-client"

# List all keys
python scripts/manage_api_keys.py list

# Rotate a key
python scripts/manage_api_keys.py rotate abc12345

# Deactivate a key
python scripts/manage_api_keys.py deactivate abc12345
```

## Scripts

- `scripts/manage_api_keys.py` - API key management
- `scripts/setup_mcp_host.py` - Configure MCP hosts
- `scripts/validate_mcp_config.py` - Validate configurations
- `scripts/data_management.py` - Data export/import
- `scripts/maintenance.py` - System maintenance