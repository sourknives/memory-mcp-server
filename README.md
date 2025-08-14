# Cortex MCP

A Model Context Protocol (MCP) server providing intelligent, persistent memory storage across AI development tools.

## Overview

Cortex MCP enables AI tools like Claude Desktop, Cursor, and Kiro to share persistent memory and context across conversations and sessions.

**Key Features:**
- 🧠 **Persistent Memory** - Store and retrieve information across AI tool sessions
- 🔍 **Semantic Search** - Find relevant information using AI-powered similarity
- 🔒 **Local & Private** - Runs on your infrastructure with encrypted storage
- 🌐 **Multi-Tool Support** - Works with Claude Desktop, Cursor, Kiro, and other MCP-enabled tools
- 📊 **Intelligent Storage** - Automatically categorizes and stores valuable conversations

## Quick Start

### For Remote Server Usage (Recommended)

1. **Install the lightweight client:**
   ```bash
   pip install cortex-mcp-client
   ```

2. **Configure your AI tool** (Claude Desktop, Cursor, Kiro):
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

3. **Test the connection:**
   ```bash
   cortex-mcp-client --test
   ```

### For Local Development

1. **Set up the server:**
   ```bash
   cd cortex-mcp-server
   pip install -e .
   python -m cortex_mcp.main
   ```

2. **Configure your AI tool for local connection:**
   ```json
   {
     "mcpServers": {
       "cortex-mcp": {
         "command": "python",
         "args": ["-m", "cortex_mcp.main", "--mode", "mcp"],
         "cwd": "/path/to/cortex-mcp-server"
       }
     }
   }
   ```

## Repository Structure

```
cortex-mcp/
├── cortex-mcp-server/     # Full MCP server implementation
│   ├── src/               # Server source code
│   ├── docs/              # Server documentation
│   ├── scripts/           # Management scripts
│   └── tests/             # Server tests
├── cortex-mcp-client/     # Lightweight remote client
│   ├── client.py          # Core MCP-to-HTTP bridge
│   ├── main.py            # CLI interface
│   └── README.md          # Client documentation
└── README.md              # This file
```

## Available Tools

Once configured, these MCP tools are available in your AI development environment:

- **`store_memory`** - Store information in persistent memory
- **`retrieve_memories`** - Retrieve stored memories by query
- **`search_memories`** - Semantic search across all memories
- **`list_memories`** - List recent or filtered memories
- **`delete_memory`** - Remove specific memories
- **`analyze_conversation_for_storage`** - Analyze conversation value
- **`suggest_memory_storage`** - Get intelligent storage suggestions

## Configuration Locations

### Claude Desktop
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

### Kiro IDE
- **Workspace:** `.kiro/settings/mcp.json`
- **User:** `~/.kiro/settings/mcp.json`

### Cursor IDE
- Configuration location varies by platform

## Documentation

- **Server Setup:** See `cortex-mcp-server/README.md`
- **Client Usage:** See `cortex-mcp-client/README.md`
- **Deployment:** See `cortex-mcp-server/DEPLOYMENT.md`

## Support

- **Issues:** [GitHub Issues](https://github.com/example/cortex-mcp/issues)
- **Documentation:** [GitHub Repository](https://github.com/example/cortex-mcp)

## License

MIT License - see LICENSE file for details.