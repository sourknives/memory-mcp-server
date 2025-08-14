# Intelligent Storage Configuration

This document describes the configuration options available for the intelligent storage system in the Cross-Tool Memory MCP service.

## Overview

The intelligent storage system automatically analyzes conversations to identify valuable content and either auto-stores it or suggests storage to users. The system can be configured through various preferences to match your workflow needs.

## Configuration Categories

### Global Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `enabled` | `true` | Enable/disable the entire intelligent storage system |
| `privacy_mode` | `false` | Disable all auto-storage when enabled (suggestions only) |
| `auto_store_threshold` | `0.85` | Confidence threshold for automatic storage (0.0-1.0) |
| `suggestion_threshold` | `0.60` | Confidence threshold for storage suggestions (0.0-1.0) |

### Content Category Settings

Control auto-storage for specific types of content:

| Category | Setting | Default | Description |
|----------|---------|---------|-------------|
| Preferences | `auto_store_preferences` | `true` | Auto-store user preferences and coding styles |
| Solutions | `auto_store_solutions` | `true` | Auto-store problem-solution pairs |
| Project Context | `auto_store_project_context` | `true` | Auto-store project-specific information |
| Decisions | `auto_store_decisions` | `true` | Auto-store technical decisions |
| Patterns | `auto_store_patterns` | `true` | Auto-store conversation patterns |

### Notification Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `notify_auto_store` | `true` | Show notifications when content is auto-stored |
| `notify_suggestions` | `true` | Show storage suggestions to user |

### Learning and Feedback

| Setting | Default | Description |
|---------|---------|-------------|
| `learn_from_feedback` | `true` | Learn from user approval/rejection of suggestions |
| `feedback_weight` | `0.1` | Weight for user feedback in learning (0.0-1.0) |

### Content Filtering

| Setting | Default | Description |
|---------|---------|-------------|
| `min_content_length` | `50` | Minimum content length for storage consideration |
| `max_suggestions_per_session` | `5` | Maximum storage suggestions per conversation session |

### Duplicate Detection

| Setting | Default | Description |
|---------|---------|-------------|
| `duplicate_detection` | `true` | Enable duplicate content detection |
| `similarity_threshold` | `0.8` | Similarity threshold for duplicate detection (0.0-1.0) |

## Managing Configuration

### Using the CLI Tool

The system includes a command-line tool for managing configuration:

```bash
# Show current configuration
python -m src.cortex_mcp.utils.intelligent_storage_cli show

# Show detailed configuration with descriptions
python -m src.cortex_mcp.utils.intelligent_storage_cli show --detailed

# Set a configuration value
python -m src.cortex_mcp.utils.intelligent_storage_cli set auto_store_threshold 0.9
python -m src.cortex_mcp.utils.intelligent_storage_cli set privacy_mode true

# Reset all settings to defaults
python -m src.cortex_mcp.utils.intelligent_storage_cli reset

# Export configuration to file
python -m src.cortex_mcp.utils.intelligent_storage_cli export my_config.json

# Import configuration from file
python -m src.cortex_mcp.utils.intelligent_storage_cli import my_config.json --overwrite

# Initialize default preferences (run once after installation)
python -m src.cortex_mcp.utils.intelligent_storage_cli init
```

### Programmatic Access

You can also manage configuration programmatically:

```python
from src.cortex_mcp.services.intelligent_storage_config import get_intelligent_storage_config

# Get configuration manager
config = get_intelligent_storage_config()

# Initialize defaults (run once)
config.initialize_defaults()

# Get a configuration value
threshold = config.get_config("intelligent_storage.auto_store_threshold", 0.85)

# Set a configuration value
config.set_config("intelligent_storage.privacy_mode", True)

# Check if auto-storage is enabled for a category
from src.cortex_mcp.services.intelligent_storage_config import StorageCategory
enabled = config.is_auto_storage_enabled(StorageCategory.PREFERENCES)

# Get category-specific settings
settings = config.get_category_settings(StorageCategory.SOLUTIONS)

# Get all configuration
all_config = config.get_all_config()

# Reset to defaults
config.reset_to_defaults()
```

## Configuration Validation

The system validates all configuration values:

- **Thresholds**: Must be between 0.0 and 1.0
- **Boolean values**: Accepts `true`/`false`, `1`/`0`, `yes`/`no`, `on`/`off`
- **Integer values**: Must be within specified ranges
- **Type conversion**: Automatically converts string values to appropriate types

## Privacy and Security

### Privacy Mode

When `privacy_mode` is enabled:
- No content is automatically stored
- Only storage suggestions are shown to the user
- User must explicitly approve all storage operations
- Provides maximum control over what gets stored

### Data Storage

All configuration is stored locally in your database:
- No configuration data is sent to external services
- Settings are encrypted if database encryption is enabled
- Configuration can be backed up and restored with the database

## Common Configuration Scenarios

### Conservative Storage (High Precision)
```bash
# Only store very high-confidence content
python -m src.cortex_mcp.utils.intelligent_storage_cli set auto_store_threshold 0.95
python -m src.cortex_mcp.utils.intelligent_storage_cli set suggestion_threshold 0.80
```

### Aggressive Storage (High Recall)
```bash
# Store more content with lower confidence
python -m src.cortex_mcp.utils.intelligent_storage_cli set auto_store_threshold 0.70
python -m src.cortex_mcp.utils.intelligent_storage_cli set suggestion_threshold 0.50
```

### Privacy-Focused
```bash
# Enable privacy mode and disable notifications
python -m src.cortex_mcp.utils.intelligent_storage_cli set privacy_mode true
python -m src.cortex_mcp.utils.intelligent_storage_cli set notify_auto_store false
```

### Category-Specific Control
```bash
# Only auto-store solutions and decisions
python -m src.cortex_mcp.utils.intelligent_storage_cli set auto_store_preferences false
python -m src.cortex_mcp.utils.intelligent_storage_cli set auto_store_project_context false
python -m src.cortex_mcp.utils.intelligent_storage_cli set auto_store_patterns false
```

## Troubleshooting

### Configuration Not Taking Effect
1. Verify the setting was saved: `show` command
2. Check for validation errors in logs
3. Restart any connected AI tools
4. Verify database connectivity

### Reset Configuration
If configuration becomes corrupted:
```bash
python -m src.cortex_mcp.utils.intelligent_storage_cli reset --yes
python -m src.cortex_mcp.utils.intelligent_storage_cli init
```

### Backup Configuration
Before making major changes:
```bash
python -m src.cortex_mcp.utils.intelligent_storage_cli export backup_config.json
```

## Integration with Existing System

The intelligent storage configuration system:
- Extends the existing preferences system
- Uses the same database tables and infrastructure
- Is backward compatible with existing installations
- Follows the same security and privacy principles

All settings are stored in the `preferences` table with the `learning` category and keys prefixed with `intelligent_storage.`.