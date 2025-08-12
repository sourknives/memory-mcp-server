#!/bin/bash

# Cross-Tool Memory MCP Server - Production Startup Script

set -e

echo "🚀 Starting Cross-Tool Memory MCP Server in Production Mode"
echo "============================================================"

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: No virtual environment detected"
    echo "   Consider activating your virtual environment first"
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p data models logs ssl

# Set environment variables
export MEMORY_SERVER_HOST=0.0.0.0
export MEMORY_SERVER_PORT=8001
export DATABASE_PATH=./data/memory.db
export LOG_LEVEL=INFO
export ENVIRONMENT=production

# Check if port is available
if lsof -i :8001 >/dev/null 2>&1; then
    echo "❌ Port 8001 is already in use"
    echo "   Please stop the existing service or choose a different port"
    exit 1
fi

echo "🔧 Configuration:"
echo "   Host: $MEMORY_SERVER_HOST"
echo "   Port: $MEMORY_SERVER_PORT"
echo "   Database: $DATABASE_PATH"
echo "   Log Level: $LOG_LEVEL"
echo ""

echo "🌐 Starting server..."
echo "   Web UI: http://localhost:8001/ui"
echo "   API Docs: http://localhost:8001/docs"
echo "   Health Check: http://localhost:8001/health"
echo ""

# Start the server
python -m cross_tool_memory.main \
    --mode rest \
    --host $MEMORY_SERVER_HOST \
    --port $MEMORY_SERVER_PORT \
    --db-path $DATABASE_PATH

echo "🛑 Server stopped"