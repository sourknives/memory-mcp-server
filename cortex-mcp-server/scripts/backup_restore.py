#!/usr/bin/env python3
"""
Cross-Tool Memory MCP Server Backup and Restore Utility

This script provides comprehensive backup and restore functionality for the
Cross-Tool Memory MCP Server, including database, models, configuration,
and logs.
"""

import argparse
import json
import logging
import os
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BackupRestoreManager:
    """Manages backup and restore operations for the memory server."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the backup/restore manager.
        
        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or self._find_config_file()
        self.config = self._load_config()
        self.backup_dir = Path.home() / ".cross-tool-memory" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def _find_config_file(self) -> str:
        """Find the configuration file."""
        possible_paths = [
            "config.yml",
            "config.yaml",
            Path.home() / ".cross-tool-memory" / "config.yml",
            "/app/config.yml"
        ]
        
        for path in possible_paths:
            if Path(path).exists():
                return str(path)
        
        raise FileNotFoundError("Configuration file not found")
    
    def _load_config(self) -> Dict:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.warning(f"Could not load config: {e}")
            return {}
    
    def _get_database_path(self) -> str:
        """Get the database path from config or environment."""
        # Try environment variable first
        db_path = os.getenv("DATABASE_PATH")
        if db_path and Path(db_path).exists():
            return db_path
        
        # Try config file
        if "database" in self.config:
            db_path = self.config["database"].get("path")
            if db_path and Path(db_path).exists():
                return db_path
        
        # Default paths
        default_paths = [
            "data/memory.db",
            Path.home() / ".cross-tool-memory" / "data" / "memory.db",
            "/app/data/memory.db"
        ]
        
        for path in default_paths:
            if Path(path).exists():
                return str(path)
        
        raise FileNotFoundError("Database file not found")
    
    def _get_models_path(self) -> str:
        """Get the models directory path."""
        # Try environment variable first
        models_path = os.getenv("MODELS_PATH")
        if models_path and Path(models_path).exists():
            return models_path
        
        # Try config file
        if "models" in self.config:
            models_path = self.config["models"].get("path")
            if models_path and Path(models_path).exists():
                return models_path
        
        # Default paths
        default_paths = [
            "models",
            Path.home() / ".cross-tool-memory" / "models",
            "/app/models"
        ]
        
        for path in default_paths:
            if Path(path).exists():
                return str(path)
        
        logger.warning("Models directory not found")
        return ""
    
    def _get_logs_path(self) -> str:
        """Get the logs directory path."""
        # Try environment variable first
        log_file = os.getenv("LOG_FILE")
        if log_file:
            return str(Path(log_file).parent)
        
        # Default paths
        default_paths = [
            "logs",
            Path.home() / ".cross-tool-memory" / "logs",
            "/app/logs"
        ]
        
        for path in default_paths:
            if Path(path).exists():
                return str(path)
        
        logger.warning("Logs directory not found")
        return ""
    
    def create_backup(self, backup_name: Optional[str] = None, 
                     include_models: bool = True, 
                     include_logs: bool = False) -> str:
        """Create a comprehensive backup.
        
        Args:
            backup_name: Custom backup name (auto-generated if None)
            include_models: Whether to include AI models in backup
            include_logs: Whether to include log files in backup
            
        Returns:
            str: Path to backup file
        """
        if backup_name is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"memory_backup_{timestamp}"
        
        backup_file = self.backup_dir / f"{backup_name}.tar.gz"
        
        logger.info(f"Creating backup: {backup_file}")
        
        with tempfile.TemporaryDirectory() as temp_dir:
            backup_root = Path(temp_dir) / backup_name
            backup_root.mkdir()
            
            # Create backup manifest
            manifest = {
                "backup_name": backup_name,
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
                "includes": {
                    "database": True,
                    "config": True,
                    "models": include_models,
                    "logs": include_logs
                }
            }
            
            # Backup database
            try:
                db_path = self._get_database_path()
                db_backup_path = backup_root / "database"
                db_backup_path.mkdir()
                
                # Use SQLite backup API for consistency
                source_conn = sqlite3.connect(db_path)
                backup_conn = sqlite3.connect(db_backup_path / "memory.db")
                source_conn.backup(backup_conn)
                source_conn.close()
                backup_conn.close()
                
                logger.info("Database backed up successfully")
                manifest["database_size"] = os.path.getsize(db_backup_path / "memory.db")
            except Exception as e:
                logger.error(f"Database backup failed: {e}")
                manifest["includes"]["database"] = False
            
            # Backup configuration
            try:
                config_backup_path = backup_root / "config"
                config_backup_path.mkdir()
                
                # Copy main config file
                if Path(self.config_path).exists():
                    shutil.copy2(self.config_path, config_backup_path / "config.yml")
                
                # Copy environment file if it exists
                env_paths = [
                    ".env",
                    Path.home() / ".cross-tool-memory" / ".env"
                ]
                for env_path in env_paths:
                    if Path(env_path).exists():
                        shutil.copy2(env_path, config_backup_path / ".env")
                        break
                
                logger.info("Configuration backed up successfully")
            except Exception as e:
                logger.error(f"Configuration backup failed: {e}")
                manifest["includes"]["config"] = False
            
            # Backup models (optional)
            if include_models:
                try:
                    models_path = self._get_models_path()
                    if models_path and Path(models_path).exists():
                        models_backup_path = backup_root / "models"
                        shutil.copytree(models_path, models_backup_path)
                        logger.info("Models backed up successfully")
                        
                        # Calculate total size
                        total_size = sum(
                            f.stat().st_size for f in Path(models_backup_path).rglob('*') if f.is_file()
                        )
                        manifest["models_size"] = total_size
                    else:
                        manifest["includes"]["models"] = False
                except Exception as e:
                    logger.error(f"Models backup failed: {e}")
                    manifest["includes"]["models"] = False
            
            # Backup logs (optional)
            if include_logs:
                try:
                    logs_path = self._get_logs_path()
                    if logs_path and Path(logs_path).exists():
                        logs_backup_path = backup_root / "logs"
                        shutil.copytree(logs_path, logs_backup_path)
                        logger.info("Logs backed up successfully")
                        
                        # Calculate total size
                        total_size = sum(
                            f.stat().st_size for f in Path(logs_backup_path).rglob('*') if f.is_file()
                        )
                        manifest["logs_size"] = total_size
                    else:
                        manifest["includes"]["logs"] = False
                except Exception as e:
                    logger.error(f"Logs backup failed: {e}")
                    manifest["includes"]["logs"] = False
            
            # Save manifest
            with open(backup_root / "manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create compressed archive
            with tarfile.open(backup_file, "w:gz") as tar:
                tar.add(backup_root, arcname=backup_name)
            
            logger.info(f"Backup created successfully: {backup_file}")
            return str(backup_file)
    
    def list_backups(self) -> List[Dict]:
        """List available backups.
        
        Returns:
            List of backup information dictionaries
        """
        backups = []
        
        for backup_file in self.backup_dir.glob("*.tar.gz"):
            try:
                with tarfile.open(backup_file, "r:gz") as tar:
                    # Try to extract manifest
                    manifest_members = [m for m in tar.getmembers() if m.name.endswith("manifest.json")]
                    if manifest_members:
                        manifest_file = tar.extractfile(manifest_members[0])
                        manifest = json.load(manifest_file)
                        
                        backup_info = {
                            "file": str(backup_file),
                            "name": backup_file.stem.replace(".tar", ""),
                            "size": backup_file.stat().st_size,
                            "created_at": manifest.get("created_at"),
                            "includes": manifest.get("includes", {}),
                            "database_size": manifest.get("database_size"),
                            "models_size": manifest.get("models_size"),
                            "logs_size": manifest.get("logs_size")
                        }
                    else:
                        # Fallback for backups without manifest
                        backup_info = {
                            "file": str(backup_file),
                            "name": backup_file.stem.replace(".tar", ""),
                            "size": backup_file.stat().st_size,
                            "created_at": datetime.fromtimestamp(backup_file.stat().st_mtime).isoformat(),
                            "includes": {"database": True, "config": True, "models": True, "logs": True}
                        }
                    
                    backups.append(backup_info)
            except Exception as e:
                logger.warning(f"Could not read backup {backup_file}: {e}")
        
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)
    
    def restore_backup(self, backup_path: str, 
                      restore_database: bool = True,
                      restore_config: bool = True,
                      restore_models: bool = True,
                      restore_logs: bool = False) -> bool:
        """Restore from backup.
        
        Args:
            backup_path: Path to backup file
            restore_database: Whether to restore database
            restore_config: Whether to restore configuration
            restore_models: Whether to restore models
            restore_logs: Whether to restore logs
            
        Returns:
            bool: True if restore successful
        """
        backup_file = Path(backup_path)
        if not backup_file.exists():
            logger.error(f"Backup file not found: {backup_path}")
            return False
        
        logger.info(f"Restoring from backup: {backup_file}")
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                # Extract backup
                with tarfile.open(backup_file, "r:gz") as tar:
                    tar.extractall(temp_dir)
                
                # Find backup root directory
                backup_root = None
                for item in Path(temp_dir).iterdir():
                    if item.is_dir():
                        backup_root = item
                        break
                
                if not backup_root:
                    logger.error("Invalid backup structure")
                    return False
                
                # Load manifest if available
                manifest_path = backup_root / "manifest.json"
                manifest = {}
                if manifest_path.exists():
                    with open(manifest_path) as f:
                        manifest = json.load(f)
                
                # Restore database
                if restore_database and (backup_root / "database").exists():
                    try:
                        db_path = self._get_database_path()
                        backup_db_path = backup_root / "database" / "memory.db"
                        
                        # Create backup of current database
                        if Path(db_path).exists():
                            current_backup = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                            shutil.copy2(db_path, current_backup)
                            logger.info(f"Current database backed up to: {current_backup}")
                        
                        # Restore database
                        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(backup_db_path, db_path)
                        logger.info("Database restored successfully")
                    except Exception as e:
                        logger.error(f"Database restore failed: {e}")
                        return False
                
                # Restore configuration
                if restore_config and (backup_root / "config").exists():
                    try:
                        config_backup_path = backup_root / "config"
                        
                        # Restore main config
                        if (config_backup_path / "config.yml").exists():
                            shutil.copy2(config_backup_path / "config.yml", self.config_path)
                        
                        # Restore environment file
                        if (config_backup_path / ".env").exists():
                            env_target = Path.home() / ".cross-tool-memory" / ".env"
                            env_target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(config_backup_path / ".env", env_target)
                        
                        logger.info("Configuration restored successfully")
                    except Exception as e:
                        logger.error(f"Configuration restore failed: {e}")
                
                # Restore models
                if restore_models and (backup_root / "models").exists():
                    try:
                        models_path = self._get_models_path()
                        if not models_path:
                            models_path = str(Path.home() / ".cross-tool-memory" / "models")
                        
                        models_backup_path = backup_root / "models"
                        
                        # Remove existing models directory
                        if Path(models_path).exists():
                            shutil.rmtree(models_path)
                        
                        # Restore models
                        shutil.copytree(models_backup_path, models_path)
                        logger.info("Models restored successfully")
                    except Exception as e:
                        logger.error(f"Models restore failed: {e}")
                
                # Restore logs
                if restore_logs and (backup_root / "logs").exists():
                    try:
                        logs_path = self._get_logs_path()
                        if not logs_path:
                            logs_path = str(Path.home() / ".cross-tool-memory" / "logs")
                        
                        logs_backup_path = backup_root / "logs"
                        
                        # Create logs directory if it doesn't exist
                        Path(logs_path).mkdir(parents=True, exist_ok=True)
                        
                        # Restore logs
                        for log_file in logs_backup_path.rglob("*"):
                            if log_file.is_file():
                                target_file = Path(logs_path) / log_file.relative_to(logs_backup_path)
                                target_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(log_file, target_file)
                        
                        logger.info("Logs restored successfully")
                    except Exception as e:
                        logger.error(f"Logs restore failed: {e}")
                
                logger.info("Restore completed successfully")
                return True
                
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """Clean up old backup files.
        
        Args:
            keep_count: Number of recent backups to keep
            
        Returns:
            int: Number of backups deleted
        """
        backups = self.list_backups()
        
        if len(backups) <= keep_count:
            logger.info(f"Only {len(backups)} backups found, no cleanup needed")
            return 0
        
        backups_to_delete = backups[keep_count:]
        deleted_count = 0
        
        for backup in backups_to_delete:
            try:
                Path(backup["file"]).unlink()
                logger.info(f"Deleted old backup: {backup['name']}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete backup {backup['name']}: {e}")
        
        logger.info(f"Cleaned up {deleted_count} old backups")
        return deleted_count


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


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Cross-Tool Memory MCP Server Backup and Restore Utility"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create a backup")
    backup_parser.add_argument("--name", help="Custom backup name")
    backup_parser.add_argument("--no-models", action="store_true", help="Exclude AI models from backup")
    backup_parser.add_argument("--include-logs", action="store_true", help="Include log files in backup")
    backup_parser.add_argument("--config", help="Path to configuration file")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List available backups")
    list_parser.add_argument("--config", help="Path to configuration file")
    
    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore from backup")
    restore_parser.add_argument("backup", help="Path to backup file or backup name")
    restore_parser.add_argument("--no-database", action="store_true", help="Skip database restore")
    restore_parser.add_argument("--no-config", action="store_true", help="Skip configuration restore")
    restore_parser.add_argument("--no-models", action="store_true", help="Skip models restore")
    restore_parser.add_argument("--include-logs", action="store_true", help="Include logs in restore")
    restore_parser.add_argument("--config", help="Path to configuration file")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old backups")
    cleanup_parser.add_argument("--keep", type=int, default=10, help="Number of backups to keep (default: 10)")
    cleanup_parser.add_argument("--config", help="Path to configuration file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        manager = BackupRestoreManager(args.config)
        
        if args.command == "backup":
            backup_path = manager.create_backup(
                backup_name=args.name,
                include_models=not args.no_models,
                include_logs=args.include_logs
            )
            print(f"Backup created: {backup_path}")
        
        elif args.command == "list":
            backups = manager.list_backups()
            if not backups:
                print("No backups found")
                return
            
            print(f"{'Name':<30} {'Created':<20} {'Size':<10} {'Includes'}")
            print("-" * 80)
            
            for backup in backups:
                includes = []
                if backup["includes"].get("database"):
                    includes.append("DB")
                if backup["includes"].get("config"):
                    includes.append("Config")
                if backup["includes"].get("models"):
                    includes.append("Models")
                if backup["includes"].get("logs"):
                    includes.append("Logs")
                
                created = backup["created_at"][:19] if backup["created_at"] else "Unknown"
                size = format_size(backup["size"])
                includes_str = ", ".join(includes)
                
                print(f"{backup['name']:<30} {created:<20} {size:<10} {includes_str}")
        
        elif args.command == "restore":
            # Check if backup argument is a file path or backup name
            backup_path = args.backup
            if not Path(backup_path).exists():
                # Try to find backup by name
                backups = manager.list_backups()
                matching_backups = [b for b in backups if b["name"] == args.backup]
                if matching_backups:
                    backup_path = matching_backups[0]["file"]
                else:
                    print(f"Backup not found: {args.backup}")
                    return
            
            success = manager.restore_backup(
                backup_path,
                restore_database=not args.no_database,
                restore_config=not args.no_config,
                restore_models=not args.no_models,
                restore_logs=args.include_logs
            )
            
            if success:
                print("Restore completed successfully")
            else:
                print("Restore failed")
                sys.exit(1)
        
        elif args.command == "cleanup":
            deleted_count = manager.cleanup_old_backups(args.keep)
            print(f"Cleaned up {deleted_count} old backups")
    
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()