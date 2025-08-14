# Cortex MCP Client Deployment Guide

This guide covers how to build, test, and deploy the lightweight Cortex MCP client package.

## Development Setup

```bash
cd client-package
pip install -e ".[dev]"
```

## Building the Package

### Automated Build

```bash
./build.sh
```

### Manual Build

```bash
# Install build dependencies
pip install build twine

# Clean previous builds
rm -rf build/ dist/ src/cortex_mcp_client.egg-info/

# Build the package
python -m build

# Check the package
python -m twine check dist/*
```

## Testing

### Local Testing

```bash
# Install the built package locally
pip install dist/cortex_mcp_client-*.whl

# Test the CLI
cortex-mcp-client --version
cortex-mcp-client --config

# Test connection (requires running server)
export CORTEX_MCP_SERVER_URL="http://localhost:8000"
cortex-mcp-client --test
```

### Integration Testing

1. **Start a Cortex MCP server:**
   ```bash
   # In the main project directory
   python -m cortex_mcp.main --mode rest
   ```

2. **Test the client:**
   ```bash
   export CORTEX_MCP_SERVER_URL="http://localhost:8000"
   cortex-mcp-client --test
   ```

3. **Test with MCP host:**
   - Configure Claude Desktop/Kiro/Cursor with the client
   - Verify tools are available and functional

## Publishing

### To Test PyPI

```bash
python -m twine upload --repository testpypi dist/*
```

### To Production PyPI

```bash
python -m twine upload dist/*
```

## Version Management

Update version in:
- `pyproject.toml` - `version = "x.y.z"`
- `src/cortex_mcp_client/__init__.py` - `__version__ = "x.y.z"`

## Distribution Strategy

### PyPI Package (Recommended)

**Pros:**
- ✅ Easy installation: `pip install cortex-mcp-client`
- ✅ Automatic dependency management
- ✅ Version management
- ✅ Minimal client footprint

**Cons:**
- ❌ Requires PyPI publishing
- ❌ Additional package to maintain

### GitHub Releases

Alternative distribution via GitHub releases:

```bash
# Create release archive
tar -czf cortex-mcp-client-v0.1.0.tar.gz client-package/

# Users can install from GitHub
pip install https://github.com/user/repo/releases/download/v0.1.0/cortex-mcp-client-v0.1.0.tar.gz
```

### Single File Distribution

For maximum simplicity, create a standalone script:

```bash
# Combine all dependencies into a single file
python -m pip install pex
pex cortex-mcp-client -o cortex-mcp-client.pex

# Users can run directly
./cortex-mcp-client.pex --test
```

## Client Configuration Examples

### Environment Variables

```bash
export CORTEX_MCP_SERVER_URL="https://your-server.com:8000"
export CORTEX_MCP_API_KEY="your-api-key"
export CORTEX_MCP_TIMEOUT="30"
export CORTEX_MCP_USE_TLS="true"
export CORTEX_MCP_VERIFY_SSL="true"
```

### MCP Host Configurations

All configurations use the same format:

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

## Troubleshooting

### Build Issues

**"Module not found" errors:**
```bash
pip install build twine
```

**"Permission denied" on build.sh:**
```bash
chmod +x build.sh
```

### Runtime Issues

**"cortex-mcp-client command not found":**
```bash
# Reinstall the package
pip uninstall cortex-mcp-client
pip install cortex-mcp-client

# Or install from local build
pip install dist/cortex_mcp_client-*.whl
```

**Connection errors:**
```bash
# Test connectivity
curl https://your-server.com:8000/health

# Check configuration
cortex-mcp-client --config

# Test connection
cortex-mcp-client --test
```

## Maintenance

### Regular Updates

1. Update dependencies in `pyproject.toml`
2. Test with latest MCP specification
3. Verify compatibility with MCP hosts
4. Update documentation

### Security Considerations

- Keep `httpx` dependency updated
- Validate SSL certificates by default
- Sanitize error messages (don't leak sensitive info)
- Support secure credential storage

## Support

- Main project: https://github.com/example/cortex-mcp
- Client issues: Use main project issue tracker
- PyPI package: https://pypi.org/project/cortex-mcp-client/