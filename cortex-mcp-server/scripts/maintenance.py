#!/usr/bin/env python3
"""
Cortex MCP Maintenance Script

This script provides easy access to monitoring and maintenance tools
for the cortex mcp system.
"""

import sys
import os
from pathlib import Path

# Add the parent directory to Python path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from utils.maintenance_cli import cli

if __name__ == '__main__':
    cli()