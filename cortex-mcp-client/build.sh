#!/bin/bash
# Build script for cortex-mcp-client package

set -e

echo "🏗️  Building cortex-mcp-client package..."

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/ src/cortex_mcp_client.egg-info/

# Build the package
echo "📦 Building package..."
python -m build

# Check the package
echo "🔍 Checking package..."
python -m twine check dist/*

echo "✅ Build complete!"
echo "📁 Built packages:"
ls -la dist/

echo ""
echo "🚀 To install locally:"
echo "   pip install dist/cortex_mcp_client-*.whl"
echo ""
echo "📤 To publish to PyPI:"
echo "   python -m twine upload dist/*"