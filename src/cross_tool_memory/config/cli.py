"""
Command-line interface for configuration and model management.

This module provides CLI commands for:
- Configuration validation and management
- Model downloads and updates
- System health checks
- Storage management
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import Optional, List

from .config_manager import ConfigManager, get_config_manager
from .model_manager import ModelManager, get_model_manager


def setup_logging(level: str = "INFO"):
    """Set up logging for CLI operations."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def cmd_config_validate(args):
    """Validate configuration file."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        print("✓ Configuration is valid")
        
        if args.verbose:
            print(f"Server: {config.server.host}:{config.server.port}")
            print(f"Database: {config.database.path}")
            print(f"Embedding model: {config.ai_models.embedding.model_name}")
            print(f"LLM enabled: {config.ai_models.llm.enabled}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Configuration validation failed: {e}")
        return 1


def cmd_config_create_example(args):
    """Create example configuration file."""
    try:
        config_manager = ConfigManager()
        config_manager.create_example_config(args.output_file)
        print(f"✓ Example configuration created: {args.output_file}")
        return 0
        
    except Exception as e:
        print(f"✗ Failed to create example configuration: {e}")
        return 1


def cmd_config_show(args):
    """Show current configuration."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        
        if args.format == "json":
            print(json.dumps(config.dict(), indent=2, default=str))
        else:
            # Pretty print configuration
            print("Current Configuration:")
            print("=" * 50)
            
            print(f"Server:")
            print(f"  Host: {config.server.host}")
            print(f"  Port: {config.server.port}")
            print(f"  Debug: {config.server.debug}")
            
            print(f"\nDatabase:")
            print(f"  Path: {config.database.path}")
            print(f"  Pool Size: {config.database.pool_size}")
            print(f"  Echo: {config.database.echo}")
            
            print(f"\nAI Models:")
            print(f"  Embedding Model: {config.ai_models.embedding.model_name}")
            print(f"  Embedding Device: {config.ai_models.embedding.device}")
            print(f"  Cache Directory: {config.ai_models.embedding.cache_dir}")
            print(f"  LLM Enabled: {config.ai_models.llm.enabled}")
            if config.ai_models.llm.enabled:
                print(f"  LLM Provider: {config.ai_models.llm.provider}")
                print(f"  LLM Model: {config.ai_models.llm.model}")
            
            print(f"\nSecurity:")
            print(f"  Encryption: {config.security.encryption.enabled}")
            print(f"  API Key Required: {config.security.api.require_key}")
            
            print(f"\nLogging:")
            print(f"  Level: {config.logging.level}")
            print(f"  File Logging: {config.logging.file.enabled}")
            if config.logging.file.enabled:
                print(f"  Log File: {config.logging.file.path}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Failed to show configuration: {e}")
        return 1


def cmd_model_list(args):
    """List available and downloaded models."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        model_manager = ModelManager(config.ai_models.embedding.cache_dir)
        
        if args.type:
            model_types = [args.type]
        else:
            model_types = ["embedding", "llm"]
        
        for model_type in model_types:
            print(f"\n{model_type.title()} Models:")
            print("=" * 30)
            
            # Show available models
            available = model_manager.get_available_models(model_type)
            downloaded = model_manager.list_models(model_type)
            downloaded_names = {m.name for m in downloaded}
            
            for model_name in available:
                status = "✓ Downloaded" if model_name in downloaded_names else "○ Available"
                print(f"  {status} {model_name}")
                
                # Show additional info for downloaded models
                if model_name in downloaded_names:
                    info = model_manager.get_model_info(model_name, model_type)
                    if info and args.verbose:
                        if info.size_bytes:
                            size_mb = info.size_bytes / (1024 * 1024)
                            print(f"    Size: {size_mb:.1f} MB")
                        if info.last_used:
                            print(f"    Last used: {info.last_used.strftime('%Y-%m-%d %H:%M')}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Failed to list models: {e}")
        return 1


def cmd_model_download(args):
    """Download a model."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        model_manager = ModelManager(config.ai_models.embedding.cache_dir)
        
        def progress_callback(message, progress):
            if progress is not None:
                print(f"\r{message} ({progress}%)", end="", flush=True)
            else:
                print(f"\r{message}", end="", flush=True)
        
        print(f"Downloading {args.model_type} model: {args.model_name}")
        
        success = model_manager.download_model(
            args.model_name,
            args.model_type,
            force=args.force,
            progress_callback=progress_callback if not args.quiet else None
        )
        
        print()  # New line after progress
        
        if success:
            print(f"✓ Successfully downloaded {args.model_name}")
            
            # Validate model
            if model_manager.validate_model(args.model_name, args.model_type):
                print("✓ Model validation passed")
            else:
                print("⚠ Model validation failed")
                return 1
        else:
            print(f"✗ Failed to download {args.model_name}")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"✗ Model download failed: {e}")
        return 1


def cmd_model_validate(args):
    """Validate a downloaded model."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        model_manager = ModelManager(config.ai_models.embedding.cache_dir)
        
        print(f"Validating {args.model_type} model: {args.model_name}")
        
        if not model_manager.is_model_available(args.model_name, args.model_type):
            print(f"✗ Model {args.model_name} is not available")
            return 1
        
        if model_manager.validate_model(args.model_name, args.model_type):
            print(f"✓ Model {args.model_name} validation passed")
            return 0
        else:
            print(f"✗ Model {args.model_name} validation failed")
            return 1
        
    except Exception as e:
        print(f"✗ Model validation failed: {e}")
        return 1


def cmd_model_cleanup(args):
    """Clean up unused models."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        model_manager = ModelManager(config.ai_models.embedding.cache_dir)
        
        print(f"Cleaning up models unused for {args.days} days...")
        
        if not args.force:
            response = input("This will permanently delete unused models. Continue? (y/N): ")
            if response.lower() != 'y':
                print("Cleanup cancelled")
                return 0
        
        cleaned = model_manager.cleanup_unused_models(args.days)
        
        if cleaned:
            print(f"✓ Cleaned up {len(cleaned)} models:")
            for model_name in cleaned:
                print(f"  - {model_name}")
        else:
            print("✓ No models needed cleanup")
        
        return 0
        
    except Exception as e:
        print(f"✗ Model cleanup failed: {e}")
        return 1


def cmd_model_recommend(args):
    """Get model recommendations."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        model_manager = ModelManager(config.ai_models.embedding.cache_dir)
        
        recommendations = model_manager.get_model_recommendations(args.use_case)
        
        print(f"Model Recommendations for '{args.use_case}' use case:")
        print("=" * 50)
        
        for model_type, models in recommendations.items():
            if models:
                print(f"\n{model_type.title()} Models:")
                for model in models:
                    status = "✓" if model_manager.is_model_available(model, model_type) else "○"
                    print(f"  {status} {model}")
                    
                    # Show model info
                    if model_type == "embedding" and model in model_manager.EMBEDDING_MODELS:
                        info = model_manager.EMBEDDING_MODELS[model]
                        print(f"    Size: ~{info['size_mb']} MB, {info['description']}")
                    elif model_type == "llm" and model in model_manager.LLM_MODELS:
                        info = model_manager.LLM_MODELS[model]
                        print(f"    Size: ~{info['size_mb']} MB, {info['description']}")
        
        return 0
        
    except Exception as e:
        print(f"✗ Failed to get recommendations: {e}")
        return 1


def cmd_system_health(args):
    """Check system health."""
    try:
        config_manager = ConfigManager(args.config_file)
        config = config_manager.get_config()
        model_manager = ModelManager(config.ai_models.embedding.cache_dir)
        
        print("System Health Check:")
        print("=" * 30)
        
        # Configuration health
        try:
            config_manager.get_config()
            print("✓ Configuration: Valid")
        except Exception as e:
            print(f"✗ Configuration: {e}")
        
        # Model manager health
        health = model_manager.health_check()
        status_icon = "✓" if health["status"] == "healthy" else "⚠" if health["status"] == "degraded" else "✗"
        print(f"{status_icon} Model Manager: {health['status'].title()}")
        
        if args.verbose:
            print(f"  Models: {health['model_count']}")
            print(f"  Cache Directory: {'✓' if health['cache_dir_exists'] else '✗'}")
            print(f"  Ollama Available: {'✓' if health['ollama_available'] else '✗'}")
            
            if health["issues"]:
                print("  Issues:")
                for issue in health["issues"]:
                    print(f"    - {issue}")
        
        # Storage stats
        stats = model_manager.get_storage_stats()
        print(f"\nStorage Usage:")
        print(f"  Total Models: {stats['total_models']}")
        print(f"  Storage Used: {stats['total_size_mb']:.1f} MB")
        print(f"  Cache Directory: {stats['cache_dir']}")
        
        return 0 if health["status"] != "unhealthy" else 1
        
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cross-Tool Memory Configuration and Model Management CLI"
    )
    
    parser.add_argument(
        "--config-file",
        default="config.yml",
        help="Configuration file path (default: config.yml)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Set logging level"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Configuration commands
    config_parser = subparsers.add_parser("config", help="Configuration management")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    
    # config validate
    validate_parser = config_subparsers.add_parser("validate", help="Validate configuration")
    validate_parser.set_defaults(func=cmd_config_validate)
    
    # config create-example
    example_parser = config_subparsers.add_parser("create-example", help="Create example configuration")
    example_parser.add_argument("output_file", help="Output file path")
    example_parser.set_defaults(func=cmd_config_create_example)
    
    # config show
    show_parser = config_subparsers.add_parser("show", help="Show current configuration")
    show_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    show_parser.set_defaults(func=cmd_config_show)
    
    # Model commands
    model_parser = subparsers.add_parser("model", help="Model management")
    model_subparsers = model_parser.add_subparsers(dest="model_command")
    
    # model list
    list_parser = model_subparsers.add_parser("list", help="List models")
    list_parser.add_argument("--type", choices=["embedding", "llm"], help="Filter by model type")
    list_parser.set_defaults(func=cmd_model_list)
    
    # model download
    download_parser = model_subparsers.add_parser("download", help="Download model")
    download_parser.add_argument("model_type", choices=["embedding", "llm"], help="Model type")
    download_parser.add_argument("model_name", help="Model name")
    download_parser.add_argument("--force", action="store_true", help="Force download even if exists")
    download_parser.add_argument("--quiet", action="store_true", help="Suppress progress output")
    download_parser.set_defaults(func=cmd_model_download)
    
    # model validate
    validate_model_parser = model_subparsers.add_parser("validate", help="Validate model")
    validate_model_parser.add_argument("model_type", choices=["embedding", "llm"], help="Model type")
    validate_model_parser.add_argument("model_name", help="Model name")
    validate_model_parser.set_defaults(func=cmd_model_validate)
    
    # model cleanup
    cleanup_parser = model_subparsers.add_parser("cleanup", help="Clean up unused models")
    cleanup_parser.add_argument("--days", type=int, default=30, help="Days unused threshold")
    cleanup_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    cleanup_parser.set_defaults(func=cmd_model_cleanup)
    
    # model recommend
    recommend_parser = model_subparsers.add_parser("recommend", help="Get model recommendations")
    recommend_parser.add_argument(
        "use_case",
        choices=["general", "fast", "quality", "minimal"],
        default="general",
        nargs="?",
        help="Use case for recommendations"
    )
    recommend_parser.set_defaults(func=cmd_model_recommend)
    
    # System commands
    health_parser = subparsers.add_parser("health", help="Check system health")
    health_parser.set_defaults(func=cmd_system_health)
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set up logging
    setup_logging(args.log_level)
    
    # Handle no command
    if not args.command:
        parser.print_help()
        return 1
    
    # Handle subcommands without sub-subcommands
    if args.command in ["config", "model"] and not hasattr(args, "func"):
        if args.command == "config":
            config_parser.print_help()
        else:
            model_parser.print_help()
        return 1
    
    # Execute command
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())