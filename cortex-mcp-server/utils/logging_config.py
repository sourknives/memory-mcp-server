"""
Comprehensive logging configuration for the cortex mcp system.

This module provides structured logging with different levels, formatters,
and handlers for various components of the system.
"""

import logging
import logging.handlers
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Union
import json


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add extra fields if present
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)
        
        return json.dumps(log_data, default=str)


class ColoredConsoleFormatter(logging.Formatter):
    """Console formatter with color coding for different log levels."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors for console output."""
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        
        # Format timestamp
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        # Format the message
        formatted_message = (
            f"{color}[{timestamp}] {record.levelname:8s}{reset} "
            f"{record.name:20s} | {record.getMessage()}"
        )
        
        # Add exception information if present
        if record.exc_info:
            formatted_message += f"\n{self.formatException(record.exc_info)}"
        
        return formatted_message


class LoggingConfig:
    """Configuration for logging system."""
    
    def __init__(
        self,
        log_level: str = "INFO",
        log_dir: Optional[str] = None,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        console_output: bool = True,
        file_output: bool = True,
        structured_logs: bool = False,
        component_levels: Optional[Dict[str, str]] = None
    ):
        """
        Initialize logging configuration.
        
        Args:
            log_level: Default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_dir: Directory for log files (defaults to ~/.cortex_mcp/logs)
            max_file_size: Maximum size of log files before rotation
            backup_count: Number of backup files to keep
            console_output: Whether to output logs to console
            file_output: Whether to output logs to files
            structured_logs: Whether to use structured JSON logging
            component_levels: Specific log levels for different components
        """
        self.log_level = log_level.upper()
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.console_output = console_output
        self.file_output = file_output
        self.structured_logs = structured_logs
        self.component_levels = component_levels or {}
        
        # Set up log directory
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path.home() / ".cortex_mcp" / "logs"
        
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def setup_logging(self) -> None:
        """Set up the logging system with configured handlers."""
        # Clear any existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        # Set root logger level
        root_logger.setLevel(getattr(logging, self.log_level))
        
        handlers = []
        
        # Console handler
        if self.console_output:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(getattr(logging, self.log_level))
            
            if self.structured_logs:
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(ColoredConsoleFormatter())
            
            handlers.append(console_handler)
        
        # File handlers
        if self.file_output:
            # Main application log
            app_log_file = self.log_dir / "cortex_mcp.log"
            app_handler = logging.handlers.RotatingFileHandler(
                app_log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count
            )
            app_handler.setLevel(getattr(logging, self.log_level))
            
            if self.structured_logs:
                app_handler.setFormatter(StructuredFormatter())
            else:
                app_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                ))
            
            handlers.append(app_handler)
            
            # Error log (ERROR and CRITICAL only)
            error_log_file = self.log_dir / "errors.log"
            error_handler = logging.handlers.RotatingFileHandler(
                error_log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count
            )
            error_handler.setLevel(logging.ERROR)
            
            if self.structured_logs:
                error_handler.setFormatter(StructuredFormatter())
            else:
                error_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
                ))
            
            handlers.append(error_handler)
            
            # Performance log for timing information
            perf_log_file = self.log_dir / "performance.log"
            perf_handler = logging.handlers.RotatingFileHandler(
                perf_log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count
            )
            perf_handler.setLevel(logging.INFO)
            perf_handler.addFilter(PerformanceLogFilter())
            
            if self.structured_logs:
                perf_handler.setFormatter(StructuredFormatter())
            else:
                perf_handler.setFormatter(logging.Formatter(
                    '%(asctime)s - %(message)s'
                ))
            
            handlers.append(perf_handler)
        
        # Add all handlers to root logger
        for handler in handlers:
            root_logger.addHandler(handler)
        
        # Set component-specific log levels
        for component, level in self.component_levels.items():
            component_logger = logging.getLogger(component)
            component_logger.setLevel(getattr(logging, level.upper()))
        
        # Log the configuration
        logger = logging.getLogger(__name__)
        logger.info(f"Logging configured - Level: {self.log_level}, Dir: {self.log_dir}")


class PerformanceLogFilter(logging.Filter):
    """Filter to only allow performance-related log messages."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter log records to only include performance messages."""
        return hasattr(record, 'performance') or 'performance' in record.getMessage().lower()


class PerformanceLogger:
    """Logger for performance metrics and timing information."""
    
    def __init__(self, logger_name: str = "performance"):
        self.logger = logging.getLogger(logger_name)
    
    def log_operation_time(
        self,
        operation: str,
        duration: float,
        metadata: Optional[Dict] = None
    ) -> None:
        """Log the duration of an operation."""
        extra_fields = {
            "performance": True,
            "operation": operation,
            "duration_ms": round(duration * 1000, 2),
            "duration_s": round(duration, 3)
        }
        
        if metadata:
            extra_fields.update(metadata)
        
        # Create a log record with extra fields
        record = logging.LogRecord(
            name=self.logger.name,
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg=f"Operation '{operation}' completed in {duration:.3f}s",
            args=(),
            exc_info=None
        )
        record.extra_fields = extra_fields
        
        self.logger.handle(record)
    
    def log_search_performance(
        self,
        query: str,
        result_count: int,
        duration: float,
        search_type: str = "hybrid"
    ) -> None:
        """Log search operation performance."""
        self.log_operation_time(
            operation="search",
            duration=duration,
            metadata={
                "query_length": len(query),
                "result_count": result_count,
                "search_type": search_type
            }
        )
    
    def log_database_performance(
        self,
        operation: str,
        table: str,
        duration: float,
        record_count: Optional[int] = None
    ) -> None:
        """Log database operation performance."""
        metadata = {
            "table": table,
            "db_operation": operation
        }
        
        if record_count is not None:
            metadata["record_count"] = record_count
        
        self.log_operation_time(
            operation=f"db_{operation}",
            duration=duration,
            metadata=metadata
        )


class ComponentLogger:
    """Logger wrapper for specific components with context."""
    
    def __init__(self, component_name: str):
        self.logger = logging.getLogger(f"cortex_mcp.{component_name}")
        self.component_name = component_name
    
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message with component context."""
        self._log(logging.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """Log info message with component context."""
        self._log(logging.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message with component context."""
        self._log(logging.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """Log error message with component context."""
        self._log(logging.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """Log critical message with component context."""
        self._log(logging.CRITICAL, message, **kwargs)
    
    def _log(self, level: int, message: str, **kwargs) -> None:
        """Internal method to log with extra context."""
        extra_fields = {
            "component": self.component_name,
            **kwargs
        }
        
        # Create a log record with extra fields
        record = logging.LogRecord(
            name=self.logger.name,
            level=level,
            pathname="",
            lineno=0,
            msg=message,
            args=(),
            exc_info=None
        )
        record.extra_fields = extra_fields
        
        self.logger.handle(record)


def setup_default_logging(
    log_level: str = "INFO",
    structured_logs: bool = False
) -> None:
    """Set up default logging configuration."""
    import os
    
    # Skip logging setup if running in MCP mode
    if os.environ.get('DISABLE_LOGGING'):
        return
    
    config = LoggingConfig(
        log_level=log_level,
        structured_logs=structured_logs,
        component_levels={
            "cortex_mcp.database": "INFO",
            "cortex_mcp.search": "INFO",
            "cortex_mcp.mcp": "INFO",
            "cortex_mcp.api": "INFO",
            "sqlalchemy.engine": "WARNING",  # Reduce SQLAlchemy noise
            "sentence_transformers": "WARNING",  # Reduce model loading noise
        }
    )
    config.setup_logging()


def get_component_logger(component_name: str) -> ComponentLogger:
    """Get a logger for a specific component."""
    return ComponentLogger(component_name)


def get_performance_logger() -> PerformanceLogger:
    """Get the performance logger."""
    return PerformanceLogger()


# Context manager for timing operations
class TimedOperation:
    """Context manager for timing operations and logging performance."""
    
    def __init__(
        self,
        operation_name: str,
        logger: Optional[Union[logging.Logger, ComponentLogger, PerformanceLogger]] = None,
        metadata: Optional[Dict] = None
    ):
        self.operation_name = operation_name
        self.logger = logger or get_performance_logger()
        self.metadata = metadata or {}
        self.start_time: Optional[float] = None
        self.duration: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            self.duration = time.time() - self.start_time
            
            if isinstance(self.logger, PerformanceLogger):
                self.logger.log_operation_time(
                    self.operation_name,
                    self.duration,
                    self.metadata
                )
            elif hasattr(self.logger, 'info'):
                self.logger.info(
                    f"Operation '{self.operation_name}' completed in {self.duration:.3f}s",
                    **self.metadata
                )


# Import time for TimedOperation
import time