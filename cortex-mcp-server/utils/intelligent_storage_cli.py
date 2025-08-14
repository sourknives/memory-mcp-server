#!/usr/bin/env python3
"""
Command-line interface for managing intelligent storage settings.

This utility provides a convenient way to view, modify, and manage
intelligent storage configuration from the command line.
"""

import argparse
import json
import sys
from typing import Dict, Any, Optional
from pathlib import Path

from services.intelligent_storage_config import (
    IntelligentStorageConfig,
    StorageCategory,
    get_intelligent_storage_config
)
from config.database import get_database_manager


def print_config_table(config_info: Dict[str, Any]) -> None:
    """
    Print configuration in a formatted table.
    
    Args:
        config_info: Configuration information dictionary
    """
    print("\n" + "="*80)
    print("INTELLIGENT STORAGE CONFIGURATION")
    print("="*80)
    
    # Group by category
    categories = {}
    for key, info in config_info.items():
        category = key.split('.')[1] if '.' in key else 'general'
        if category not in categories:
            categories[category] = []
        categories[category].append((key, info))
    
    for category, items in categories.items():
        print(f"\n{category.upper().replace('_', ' ')} SETTINGS:")
        print("-" * 40)
        
        for key, info in items:
            setting_name = key.split('.')[-1].replace('_', ' ').title()
            current_value = info['current_value']
            default_value = info['default_value']
            description = info['description']
            
            # Format value display
            if isinstance(current_value, bool):
                value_display = "✓ Enabled" if current_value else "✗ Disabled"
            else:
                value_display = str(current_value)
            
            print(f"  {setting_name:30} {value_display:15}")
            if current_value != default_value:
                print(f"  {'':30} (default: {default_value})")
            print(f"  {'':30} {description}")
            print()


def print_category_settings(config_manager: IntelligentStorageConfig) -> None:
    """
    Print category-specific settings.
    
    Args:
        config_manager: Configuration manager instance
    """
    print("\n" + "="*80)
    print("CATEGORY-SPECIFIC SETTINGS")
    print("="*80)
    
    for category in StorageCategory:
        settings = config_manager.get_category_settings(category)
        category_name = category.value.replace('_', ' ').title()
        
        print(f"\n{category_name}:")
        print("-" * 30)
        print(f"  Enabled:              {'✓' if settings.get('enabled') else '✗'}")
        print(f"  Auto-store:           {'✓' if settings.get('auto_store_enabled') else '✗'}")
        print(f"  Confidence threshold: {settings.get('confidence_threshold', 'N/A')}")
        print(f"  Suggestion threshold: {settings.get('suggestion_threshold', 'N/A')}")


def show_config(config_manager: IntelligentStorageConfig, detailed: bool = False) -> None:
    """
    Show current configuration.
    
    Args:
        config_manager: Configuration manager instance
        detailed: Whether to show detailed information
    """
    if detailed:
        config_info = config_manager.get_config_info()
        print_config_table(config_info)
        print_category_settings(config_manager)
    else:
        config = config_manager.get_all_config()
        print("\nCurrent Intelligent Storage Configuration:")
        print("-" * 50)
        for key, value in config.items():
            setting_name = key.replace('intelligent_storage.', '').replace('_', ' ').title()
            if isinstance(value, bool):
                value_display = "✓ Enabled" if value else "✗ Disabled"
            else:
                value_display = str(value)
            print(f"  {setting_name:30} {value_display}")


def set_config_value(config_manager: IntelligentStorageConfig, key: str, value: str) -> bool:
    """
    Set a configuration value with type conversion.
    
    Args:
        config_manager: Configuration manager instance
        key: Configuration key
        value: Value to set (as string)
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Add prefix if not present
    if not key.startswith('intelligent_storage.'):
        key = f'intelligent_storage.{key}'
    
    # Convert string value to appropriate type
    converted_value = value
    if value.lower() in ('true', 'false'):
        converted_value = value.lower() == 'true'
    elif value.replace('.', '').replace('-', '').isdigit():
        if '.' in value:
            converted_value = float(value)
        else:
            converted_value = int(value)
    
    try:
        success = config_manager.set_config(key, converted_value)
        if success:
            print(f"✓ Successfully set {key} = {converted_value}")
            return True
        else:
            print(f"✗ Failed to set {key}")
            return False
    except Exception as e:
        print(f"✗ Error setting {key}: {e}")
        return False


def reset_config(config_manager: IntelligentStorageConfig, confirm: bool = False) -> bool:
    """
    Reset configuration to defaults.
    
    Args:
        config_manager: Configuration manager instance
        confirm: Whether user has confirmed the reset
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not confirm:
        response = input("Are you sure you want to reset all settings to defaults? (y/N): ")
        if response.lower() not in ('y', 'yes'):
            print("Reset cancelled.")
            return False
    
    try:
        success = config_manager.reset_to_defaults()
        if success:
            print("✓ Successfully reset all settings to defaults")
            return True
        else:
            print("✗ Failed to reset settings")
            return False
    except Exception as e:
        print(f"✗ Error resetting settings: {e}")
        return False


def export_config(config_manager: IntelligentStorageConfig, output_file: Optional[str] = None) -> bool:
    """
    Export configuration to file.
    
    Args:
        config_manager: Configuration manager instance
        output_file: Output file path (optional)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        export_data = config_manager.export_config()
        
        if output_file:
            output_path = Path(output_file)
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)
            print(f"✓ Configuration exported to {output_path}")
        else:
            print(json.dumps(export_data, indent=2, default=str))
        
        return True
    except Exception as e:
        print(f"✗ Error exporting configuration: {e}")
        return False


def import_config(config_manager: IntelligentStorageConfig, 
                 input_file: str, 
                 overwrite: bool = False) -> bool:
    """
    Import configuration from file.
    
    Args:
        config_manager: Configuration manager instance
        input_file: Input file path
        overwrite: Whether to overwrite existing settings
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        input_path = Path(input_file)
        if not input_path.exists():
            print(f"✗ Input file not found: {input_path}")
            return False
        
        with open(input_path, 'r') as f:
            import_data = json.load(f)
        
        success = config_manager.import_config(import_data, overwrite=overwrite)
        if success:
            print(f"✓ Configuration imported from {input_path}")
            return True
        else:
            print(f"✗ Failed to import configuration from {input_path}")
            return False
    except Exception as e:
        print(f"✗ Error importing configuration: {e}")
        return False


def initialize_defaults(config_manager: IntelligentStorageConfig) -> bool:
    """
    Initialize default preferences.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        success = config_manager.initialize_defaults()
        if success:
            print("✓ Successfully initialized default preferences")
            return True
        else:
            print("✗ Failed to initialize default preferences")
            return False
    except Exception as e:
        print(f"✗ Error initializing defaults: {e}")
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Manage intelligent storage configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s show                           # Show current configuration
  %(prog)s show --detailed                # Show detailed configuration
  %(prog)s set auto_store_threshold 0.9   # Set auto-store threshold
  %(prog)s set privacy_mode true          # Enable privacy mode
  %(prog)s reset                          # Reset to defaults
  %(prog)s export config.json             # Export to file
  %(prog)s import config.json --overwrite # Import from file
  %(prog)s init                           # Initialize defaults
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Show current configuration')
    show_parser.add_argument('--detailed', action='store_true', 
                           help='Show detailed configuration information')
    
    # Set command
    set_parser = subparsers.add_parser('set', help='Set configuration value')
    set_parser.add_argument('key', help='Configuration key (without intelligent_storage prefix)')
    set_parser.add_argument('value', help='Configuration value')
    
    # Reset command
    reset_parser = subparsers.add_parser('reset', help='Reset configuration to defaults')
    reset_parser.add_argument('--yes', action='store_true', 
                            help='Skip confirmation prompt')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export configuration')
    export_parser.add_argument('file', nargs='?', help='Output file (optional, prints to stdout if not provided)')
    
    # Import command
    import_parser = subparsers.add_parser('import', help='Import configuration')
    import_parser.add_argument('file', help='Input file')
    import_parser.add_argument('--overwrite', action='store_true',
                             help='Overwrite existing settings')
    
    # Initialize command
    init_parser = subparsers.add_parser('init', help='Initialize default preferences')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # Initialize configuration manager
        config_manager = get_intelligent_storage_config()
        
        # Execute command
        if args.command == 'show':
            show_config(config_manager, detailed=args.detailed)
        
        elif args.command == 'set':
            success = set_config_value(config_manager, args.key, args.value)
            return 0 if success else 1
        
        elif args.command == 'reset':
            success = reset_config(config_manager, confirm=args.yes)
            return 0 if success else 1
        
        elif args.command == 'export':
            success = export_config(config_manager, args.file)
            return 0 if success else 1
        
        elif args.command == 'import':
            success = import_config(config_manager, args.file, overwrite=args.overwrite)
            return 0 if success else 1
        
        elif args.command == 'init':
            success = initialize_defaults(config_manager)
            return 0 if success else 1
        
        return 0
        
    except KeyboardInterrupt:
        print("\n✗ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())