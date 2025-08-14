# Cortex MCP Client

A lightweight MCP client for connecting AI development tools (Claude Desktop, Cursor, Kiro) to remote Cortex MCP servers.

## Installation

```bash
pip install cortex-mcp-client
```

## Quick Start

### 1. Configure Environment Variables

```bash
export CORTEX_MCP_SERVER_URL="https://your-cortex-server.com:8000"
export CORTEX_MCP_API_KEY="your-api-key-here"
```

### 2. Test Connection

```bash
cortex-mcp-client --test
```

### 3. Configure Your MCP Host

Add this configuration to your MCP host (Claude Desktop, Cursor, Kiro):

```json
{
  "mcpServers": {
    "cortex-mcp": {
      "command": "cortex-mcp-client",
      "args": [],
      "env": {
        "CORTEX_MCP_SERVER_URL": "https://your-cortex-server.com:8000",
        "CORTEX_MCP_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CORTEX_MCP_SERVER_URL` | Remote server URL | `http://localhost:8000` |
| `CORTEX_MCP_API_KEY` | API key for authentication | None |
| `CORTEX_MCP_TIMEOUT` | Request timeout in seconds | `30` |
| `CORTEX_MCP_USE_TLS` | Use TLS/HTTPS | `false` |
| `CORTEX_MCP_VERIFY_SSL` | Verify SSL certificates | `true` |

### MCP Host Configuration Files

#### Claude Desktop

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "cortex-mcp": {
      "command": "cortex-mcp-client",
      "args": [],
      "env": {
        "CORTEX_MCP_SERVER_URL": "https://your-server.com:8000",
        "CORTEX_MCP_API_KEY": "your-api-key"
      }
    }
  }
}
```

#### Kiro IDE

**Workspace:** `.kiro/settings/mcp.json`
**User:** `~/.kiro/settings/mcp.json`

```json
{
  "mcpServers": {
    "cortex-mcp": {
      "command": "cortex-mcp-client",
      "args": [],
      "env": {
        "CORTEX_MCP_SERVER_URL": "https://your-server.com:8000",
        "CORTEX_MCP_API_KEY": "your-api-key"
      },
      "autoApprove": [
        "store_memory",
        "retrieve_memories",
        "search_memories"
      ]
    }
  }
}
```

#### Cursor IDE

Configuration location varies by platform. Use the same JSON structure as Claude Desktop.

## Available Tools

Once connected, these MCP tools are available in your AI development environment:

- **`store_memory`** - Store information in persistent memory
- **`retrieve_memories`** - Retrieve stored memories by query
- **`search_memories`** - Semantic search across all memories
- **`list_memories`** - List recent or filtered memories
- **`delete_memory`** - Remove specific memories

## CLI Usage

```bash
# Test connection
cortex-mcp-client --test

# Show current configuration
cortex-mcp-client --config

# Show version
cortex-mcp-client --version

# Run as MCP server (normally called by MCP host)
cortex-mcp-client
```

## Troubleshooting

### Connection Issues

1. **Test connectivity:**
   ```bash
   cortex-mcp-client --test
   ```

2. **Check server status:**
   ```bash
   curl https://your-server.com:8000/health
   ```

3. **Verify configuration:**
   ```bash
   cortex-mcp-client --config
   ```

### Common Problems

**"Connection refused"**
- Server is not running or not accessible
- Check firewall settings
- Verify server URL and port

**"Authentication failed"**
- Check API key is correct
- Verify server has authentication enabled

**"SSL verification failed"**
- For development: set `CORTEX_MCP_VERIFY_SSL=false`
- For production: ensure valid SSL certificate

**"Timeout errors"**
- Increase timeout: `CORTEX_MCP_TIMEOUT=60`
- Check network connectivity

## Development

### Local Development

```bash
git clone <repository-url>
cd client-package
pip install -e .
```

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT License - see LICENSE file for details.

## Support

- GitHub Issues: https://github.com/example/cortex-mcp/issues
- Documentation: https://github.com/example/cortex-mcp