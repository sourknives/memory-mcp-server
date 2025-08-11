#!/usr/bin/env python3
"""
Cross-Tool Memory MCP Server Data Management Utility

This script provides command-line access to data export/import functionality
including backup, restore, migration, and cleanup operations.
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cross_tool_memory.config.database import DatabaseManager, DatabaseConfig
from cross_tool_memory.services.data_export_import import DataExportImportService
from cross_tool_memory.utils.logging_config import setup_default_logging

# Setup logging
setup_default_logging()
logger = logging.getLogger(__name__)


def get_service() -> DataExportImportService:
    """Get initialized data export/import service."""
    config = DatabaseConfig()
    db_manager = DatabaseManager(config)
    db_manager.initialize_database()
    return DataExportImportService(db_manager)


def format_size(size_bytes: int) -> str:
    """Format file size in human readable format."""
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f} {size_names[i]}"


def print_json_pretty(data: Dict[str, Any]) -> None:
    """Print JSON data in a pretty format."""
    print(json.dumps(data, indent=2, default=str))


def export_data(args) -> None:
    """Handle data export command."""
    try:
        service = get_service()
        
        print(f"Starting data export...")
        if args.path:
            print(f"Export path: {args.path}")
        
        export_path = service.export_all_data(
            export_path=args.path,
            include_embeddings=args.include_embeddings,
            compress=not args.no_compress
        )
        
        # Get file size
        file_size = Path(export_path).stat().st_size
        
        print(f"✅ Export completed successfully!")
        print(f"📁 File: {export_path}")
        print(f"📊 Size: {format_size(file_size)}")
        
        if args.stats:
            print("\n📈 Export Statistics:")
            # Load the export file to show stats
            if export_path.endswith('.zip'):
                import zipfile
                with zipfile.ZipFile(export_path, 'r') as zipf:
                    with zipf.open("export_data.json") as f:
                        export_data = json.load(f)
            else:
                with open(export_path, 'r') as f:
                    export_data = json.load(f)
            
            stats = export_data.get("statistics", {})
            print(f"  Conversations: {stats.get('total_conversations', 0)}")
            print(f"  Projects: {stats.get('total_projects', 0)}")
            print(f"  Preferences: {stats.get('total_preferences', 0)}")
            print(f"  Context Links: {stats.get('total_context_links', 0)}")
            
            if stats.get('conversations_by_tool'):
                print("  By Tool:")
                for tool, count in stats['conversations_by_tool'].items():
                    print(f"    {tool}: {count}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        sys.exit(1)


def import_data(args) -> None:
    """Handle data import command."""
    try:
        if not Path(args.file).exists():
            print(f"❌ Import file not found: {args.file}")
            sys.exit(1)
        
        service = get_service()
        
        print(f"Starting data import from: {args.file}")
        
        # Prepare selective import options
        selective_import = None
        if any([args.conversations_only, args.projects_only, args.preferences_only]):
            selective_import = {
                "conversations": args.conversations_only or not any([args.projects_only, args.preferences_only]),
                "projects": args.projects_only or not any([args.conversations_only, args.preferences_only]),
                "preferences": args.preferences_only or not any([args.conversations_only, args.projects_only]),
                "context_links": args.conversations_only or not any([args.projects_only, args.preferences_only])
            }
        
        if args.overwrite:
            print("⚠️  Overwrite mode enabled - existing data will be replaced")
        
        results = service.import_data(
            import_path=args.file,
            overwrite_existing=args.overwrite,
            selective_import=selective_import
        )
        
        print(f"✅ Import completed successfully!")
        print(f"📊 Import Results:")
        
        for data_type, result in results["results"].items():
            print(f"  {data_type.title()}:")
            print(f"    Imported: {result['imported']}")
            print(f"    Skipped: {result['skipped']}")
            if result['errors'] > 0:
                print(f"    Errors: {result['errors']}")
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        sys.exit(1)


def migrate_schema(args) -> None:
    """Handle schema migration command."""
    try:
        service = get_service()
        
        print(f"Starting schema migration from {args.from_version} to {args.to_version}")
        
        if not args.no_backup:
            print("📦 Creating backup before migration...")
        
        results = service.migrate_data_schema(
            from_version=args.from_version,
            to_version=args.to_version,
            backup_before_migration=not args.no_backup
        )
        
        print(f"✅ Migration completed successfully!")
        
        if results.get("backup_created"):
            print(f"📦 Backup created: {results['backup_created']}")
        
        print(f"🔧 Migration Operations:")
        for operation in results["migration_results"]["operations"]:
            print(f"  ✓ {operation}")
        
        if results["migration_results"]["errors"]:
            print(f"⚠️  Errors encountered:")
            for error in results["migration_results"]["errors"]:
                print(f"  ❌ {error}")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


def cleanup_data(args) -> None:
    """Handle data cleanup command."""
    try:
        service = get_service()
        
        if args.conversations:
            print(f"🧹 Cleaning up conversations older than {args.days} days")
            if args.dry_run:
                print("🔍 DRY RUN - No data will be deleted")
            
            results = service.cleanup_old_conversations(
                older_than_days=args.days,
                keep_minimum=args.keep_minimum,
                dry_run=args.dry_run
            )
            
            print(f"📊 Cleanup Results:")
            print(f"  Total conversations: {results['total_conversations']}")
            print(f"  Old conversations found: {results['old_conversations_found']}")
            print(f"  Conversations to delete: {results['conversations_to_delete']}")
            print(f"  Conversations to keep: {results['conversations_to_keep']}")
            
            if args.dry_run:
                print(f"  Would delete: {len(results['deleted_conversation_ids'])} conversations")
            else:
                print(f"  Deleted: {len(results['deleted_conversation_ids'])} conversations")
        
        if args.orphaned:
            print(f"🧹 Cleaning up orphaned data")
            if args.dry_run:
                print("🔍 DRY RUN - No data will be deleted")
            
            results = service.cleanup_orphaned_data(dry_run=args.dry_run)
            
            print(f"📊 Orphaned Data Cleanup Results:")
            print(f"  Orphaned context links: {results['orphaned_context_links']}")
            print(f"  Orphaned project references: {results['orphaned_project_references']}")
        
        if not args.conversations and not args.orphaned:
            print("❌ Please specify --conversations or --orphaned")
            sys.exit(1)
        
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")
        sys.exit(1)


def show_statistics(args) -> None:
    """Handle statistics display command."""
    try:
        service = get_service()
        
        print("📊 Data Statistics")
        print("=" * 50)
        
        stats = service.get_data_statistics()
        
        # Conversations
        print(f"\n💬 Conversations:")
        print(f"  Total: {stats['conversations']['total']}")
        print(f"  Last week: {stats['conversations']['last_week']}")
        print(f"  Last month: {stats['conversations']['last_month']}")
        print(f"  Last year: {stats['conversations']['last_year']}")
        
        if stats['conversations']['by_tool']:
            print(f"  By tool:")
            for tool, count in stats['conversations']['by_tool'].items():
                print(f"    {tool}: {count}")
        
        # Projects
        print(f"\n📁 Projects:")
        print(f"  Total: {stats['projects']['total']}")
        print(f"  With conversations: {stats['projects']['with_conversations']}")
        
        if stats['projects']['most_active']:
            print(f"  Most active:")
            for project in stats['projects']['most_active']:
                print(f"    {project['name']}: {project['conversation_count']} conversations")
        
        # Preferences
        print(f"\n⚙️  Preferences:")
        print(f"  Total: {stats['preferences']['total']}")
        
        if stats['preferences']['by_category']:
            print(f"  By category:")
            for category, count in stats['preferences']['by_category'].items():
                print(f"    {category}: {count}")
        
        # Context Links
        print(f"\n🔗 Context Links:")
        print(f"  Total: {stats['context_links']['total']}")
        
        if stats['context_links']['by_type']:
            print(f"  By type:")
            for link_type, count in stats['context_links']['by_type'].items():
                print(f"    {link_type}: {count}")
        
        # Storage
        print(f"\n💾 Storage (estimated):")
        print(f"  Conversations: {stats['storage']['estimated_conversations_mb']:.1f} MB")
        print(f"  Preferences: {stats['storage']['estimated_preferences_mb']:.1f} MB")
        
        if args.json:
            print(f"\n📄 Raw JSON Data:")
            print_json_pretty(stats)
        
    except Exception as e:
        print(f"❌ Failed to get statistics: {e}")
        sys.exit(1)


def validate_integrity(args) -> None:
    """Handle data integrity validation command."""
    try:
        service = get_service()
        
        print("🔍 Validating data integrity...")
        
        results = service.validate_data_integrity()
        
        print(f"📊 Validation Results:")
        print(f"  Integrity Score: {results['summary']['data_integrity_score']:.1f}%")
        print(f"  Issues: {results['summary']['total_issues']}")
        print(f"  Warnings: {results['summary']['total_warnings']}")
        
        if results['issues']:
            print(f"\n❌ Issues Found:")
            for issue in results['issues']:
                print(f"  {issue['type']}: {issue['description']}")
        
        if results['warnings']:
            print(f"\n⚠️  Warnings:")
            for warning in results['warnings']:
                print(f"  {warning['type']}: {warning['description']}")
        
        if not results['issues'] and not results['warnings']:
            print(f"\n✅ No issues found - data integrity is good!")
        
        if args.json:
            print(f"\n📄 Raw JSON Data:")
            print_json_pretty(results)
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        sys.exit(1)


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Cross-Tool Memory MCP Server Data Management Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all data
  python data_management.py export --path my_backup.zip
  
  # Import data with overwrite
  python data_management.py import backup.zip --overwrite
  
  # Clean up old conversations (dry run)
  python data_management.py cleanup --conversations --days 365 --dry-run
  
  # Show statistics
  python data_management.py stats
  
  # Validate data integrity
  python data_management.py validate
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export data to file")
    export_parser.add_argument("--path", help="Export file path (auto-generated if not specified)")
    export_parser.add_argument("--include-embeddings", action="store_true", help="Include vector embeddings")
    export_parser.add_argument("--no-compress", action="store_true", help="Don't compress the export file")
    export_parser.add_argument("--stats", action="store_true", help="Show export statistics")
    export_parser.set_defaults(func=export_data)
    
    # Import command
    import_parser = subparsers.add_parser("import", help="Import data from file")
    import_parser.add_argument("file", help="Import file path")
    import_parser.add_argument("--overwrite", action="store_true", help="Overwrite existing data")
    import_parser.add_argument("--conversations-only", action="store_true", help="Import only conversations")
    import_parser.add_argument("--projects-only", action="store_true", help="Import only projects")
    import_parser.add_argument("--preferences-only", action="store_true", help="Import only preferences")
    import_parser.set_defaults(func=import_data)
    
    # Migration command
    migrate_parser = subparsers.add_parser("migrate", help="Migrate data schema")
    migrate_parser.add_argument("from_version", help="Source schema version")
    migrate_parser.add_argument("to_version", help="Target schema version")
    migrate_parser.add_argument("--no-backup", action="store_true", help="Skip backup before migration")
    migrate_parser.set_defaults(func=migrate_schema)
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old or orphaned data")
    cleanup_parser.add_argument("--conversations", action="store_true", help="Clean up old conversations")
    cleanup_parser.add_argument("--orphaned", action="store_true", help="Clean up orphaned data")
    cleanup_parser.add_argument("--days", type=int, default=365, help="Delete conversations older than N days")
    cleanup_parser.add_argument("--keep-minimum", type=int, default=100, help="Always keep at least N conversations")
    cleanup_parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without deleting")
    cleanup_parser.set_defaults(func=cleanup_data)
    
    # Statistics command
    stats_parser = subparsers.add_parser("stats", help="Show data statistics")
    stats_parser.add_argument("--json", action="store_true", help="Output raw JSON data")
    stats_parser.set_defaults(func=show_statistics)
    
    # Validation command
    validate_parser = subparsers.add_parser("validate", help="Validate data integrity")
    validate_parser.add_argument("--json", action="store_true", help="Output raw JSON data")
    validate_parser.set_defaults(func=validate_integrity)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Call the appropriate function
    args.func(args)


if __name__ == "__main__":
    main()