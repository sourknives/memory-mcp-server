#!/usr/bin/env python3
"""
Cross-Tool Memory Maintenance Script

This script provides easy access to monitoring and maintenance tools
for the cross-tool memory system.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))

from cross_tool_memory.utils.maintenance_cli import cli

if __name__ == '__main__':
    cli()