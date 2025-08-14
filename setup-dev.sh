#!/bin/bash
# Development setup script for Cortex MCP

set -e

echo "🚀 Setting up Cortex MCP development environment..."

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: Not in a virtual environment. Consider running:"
    echo "   python -m venv .venv"
    echo "   source .venv/bin/activate"
    echo ""
fi

# Install server in development mode
echo "📦 Installing Cortex MCP Server..."
cd cortex-mcp-server
pip install -e ".[dev]"
cd ..

# Install client in development mode
echo "📦 Installing Cortex MCP Client..."
cd cortex-mcp-client
pip install -e ".[dev]"
cd ..

echo "✅ Development setup complete!"
echo ""
echo "🔧 Available commands:"
echo "   # Start server"
echo "   cd cortex-mcp-server && python -m cortex_mcp.main"
echo ""
echo "   # Test client"
echo "   cortex-mcp-client --test"
echo ""
echo "   # Run tests"
echo "   cd cortex-mcp-server && pytest"