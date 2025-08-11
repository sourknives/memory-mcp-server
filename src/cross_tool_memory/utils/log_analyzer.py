"""
Logging analysis tools for troubleshooting and system monitoring.

This module provides comprehensive log analysis, pattern detection,
and troubleshooting utilities for the cross-tool memory system.
"""

import re
import json
import gzip
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Pattern
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, Counter
import statistics

from ..utils.logging_config import get_component_logger
from ..utils.error_handling import graceful_degradation

logger = get_component_logger("log_analyzer")


class LogLevel(Enum):
    """Log levels for analysis."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogPattern(Enum):
    """Common log patterns to detect."""
    ERROR_PATTERN = "error_pattern"
    PERFORMANCE_ISSUE = "performance_issue"
    DATABASE_ERROR = "database_error"
    SEARCH_ERROR = "search_error"
    MEMORY_ISSUE = "memory_issue"
    CONNECTION_ERROR = "connection_error"
    AUTHENTICATION_ERROR = "auth_error"
    TIMEOUT_ERROR = "timeout_error"


@dataclass
class LogEntry:
    """Parsed log entry."""
    timestamp: datetime
    level: LogLevel
    logger_name: str
    message: str
    module: Optional[str] = None
    function: Optional[str] = None
    line_number: Optional[int] = None
    exception_info: Optional[Dict[str, Any]] = None
    extra_fields: Dict[str, Any] = field(default_factory=dict)
    raw_line: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level.value,
            "logger_name": self.logger_name,
            "message": self.message,
            "module": self.module,
            "function": self.function,
            "line_number": self.line_number,
            "exception_info": self.exception_info,
            "extra_fields": self.extra_fields
        }


@dataclass
class LogPattern:
    """Detected log pattern."""
    pattern_type: LogPattern
    count: int
    first_occurrence: datetime
    last_occurrence: datetime
    sample_messages: List[str]
    severity: str  # "low", "medium", "high", "critical"
    description: str
    suggested_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "pattern_type": self.pattern_type.value,
            "count": self.count,
            "first_occurrence": self.first_occurrence.isoformat(),
            "last_occurrence": self.last_occurrence.isoformat(),
            "sample_messages": self.sample_messages,
            "severity": self.severity,
            "description": self.description,
            "suggested_action": self.suggested_action
        }


@dataclass
class LogStatistics:
    """Log analysis statistics."""
    total_entries: int
    entries_by_level: Dict[str, int]
    entries_by_logger: Dict[str, int]
    entries_by_hour: Dict[int, int]
    error_rate: float
    warning_rate: float
    top_errors: List[Dict[str, Any]]
    time_range: Dict[str, datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "total_entries": self.total_entries,
            "entries_by_level": self.entries_by_level,
            "entries_by_logger": self.entries_by_logger,
            "entries_by_hour": self.entries_by_hour,
            "error_rate": self.error_rate,
            "warning_rate": self.warning_rate,
            "top_errors": self.top_errors,
            "time_range": {
                "start": self.time_range["start"].isoformat(),
                "end": self.time_range["end"].isoformat()
            }
        }


@dataclass
class LogAnalysisReport:
    """Comprehensive log analysis report."""
    timestamp: datetime
    time_range: Dict[str, datetime]
    statistics: LogStatistics
    patterns: List[LogPattern]
    anomalies: List[Dict[str, Any]]
    recommendations: List[str]
    health_indicators: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "time_range": {
                "start": self.time_range["start"].isoformat(),
                "end": self.time_range["end"].isoformat()
            },
            "statistics": self.statistics.to_dict(),
            "patterns": [pattern.to_dict() for pattern in self.patterns],
            "anomalies": self.anomalies,
            "recommendations": self.recommendations,
            "health_indicators": self.health_indicators
        }


class LogParser:
    """Parser for different log formats."""
    
    def __init__(self):
        # Regex patterns for different log formats
        self.patterns = {
            # Standard format: 2024-01-01 12:00:00 - logger_name - LEVEL - message
            "standard": re.compile(
                r"(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?)\s*-\s*"
                r"(?P<logger>[\w\.]+)\s*-\s*(?P<level>\w+)\s*-\s*(?P<message>.*)"
            ),
            
            # JSON format
            "json": re.compile(r"^\s*\{.*\}\s*$"),
            
            # Colored console format (with ANSI codes)
            "colored": re.compile(
                r"\[(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*"
                r"(?:\x1b\[\d+m)?(?P<level>\w+)(?:\x1b\[0m)?\s+"
                r"(?P<logger>[\w\.]+)\s*\|\s*(?P<message>.*)"
            )
        }
    
    def parse_log_line(self, line: str) -> Optional[LogEntry]:
        """
        Parse a single log line into a LogEntry.
        
        Args:
            line: Raw log line
            
        Returns:
            LogEntry or None if parsing fails
        """
        line = line.strip()
        if not line:
            return None
        
        # Try JSON format first
        if self.patterns["json"].match(line):
            try:
                data = json.loads(line)
                return self._parse_json_entry(data, line)
            except json.JSONDecodeError:
                pass
        
        # Try standard format
        match = self.patterns["standard"].match(line)
        if match:
            return self._parse_standard_entry(match, line)
        
        # Try colored format
        match = self.patterns["colored"].match(line)
        if match:
            return self._parse_colored_entry(match, line)
        
        # If no pattern matches, create a basic entry
        return LogEntry(
            timestamp=datetime.now(),
            level=LogLevel.INFO,
            logger_name="unknown",
            message=line,
            raw_line=line
        )
    
    def _parse_json_entry(self, data: Dict[str, Any], raw_line: str) -> LogEntry:
        """Parse JSON log entry."""
        timestamp_str = data.get("timestamp", "")
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            timestamp = datetime.now()
        
        level_str = data.get("level", "INFO").upper()
        try:
            level = LogLevel(level_str)
        except ValueError:
            level = LogLevel.INFO
        
        exception_info = None
        if "exception" in data:
            exception_info = data["exception"]
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            logger_name=data.get("logger", "unknown"),
            message=data.get("message", ""),
            module=data.get("module"),
            function=data.get("function"),
            line_number=data.get("line"),
            exception_info=exception_info,
            extra_fields={k: v for k, v in data.items() 
                         if k not in ["timestamp", "level", "logger", "message", "module", "function", "line", "exception"]},
            raw_line=raw_line
        )
    
    def _parse_standard_entry(self, match: re.Match, raw_line: str) -> LogEntry:
        """Parse standard format log entry."""
        timestamp_str = match.group("timestamp")
        try:
            # Handle both with and without milliseconds
            if "," in timestamp_str:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            else:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            timestamp = datetime.now()
        
        level_str = match.group("level").upper()
        try:
            level = LogLevel(level_str)
        except ValueError:
            level = LogLevel.INFO
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            logger_name=match.group("logger"),
            message=match.group("message"),
            raw_line=raw_line
        )
    
    def _parse_colored_entry(self, match: re.Match, raw_line: str) -> LogEntry:
        """Parse colored console format log entry."""
        timestamp_str = match.group("timestamp")
        try:
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            timestamp = datetime.now()
        
        level_str = match.group("level").upper()
        try:
            level = LogLevel(level_str)
        except ValueError:
            level = LogLevel.INFO
        
        return LogEntry(
            timestamp=timestamp,
            level=level,
            logger_name=match.group("logger"),
            message=match.group("message"),
            raw_line=raw_line
        )


class LogAnalyzer:
    """Comprehensive log analysis system."""
    
    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize log analyzer.
        
        Args:
            log_dir: Directory containing log files
        """
        if log_dir is None:
            log_dir = Path.home() / ".cross_tool_memory" / "logs"
        
        self.log_dir = Path(log_dir)
        self.parser = LogParser()
        
        # Pattern detection rules
        self.pattern_rules = {
            LogPattern.ERROR_PATTERN: {
                "regex": re.compile(r"error|exception|failed|failure", re.IGNORECASE),
                "severity": "high",
                "description": "Error patterns detected in logs"
            },
            LogPattern.PERFORMANCE_ISSUE: {
                "regex": re.compile(r"slow|timeout|performance|took \d+\.\d+s|exceeded", re.IGNORECASE),
                "severity": "medium",
                "description": "Performance issues detected"
            },
            LogPattern.DATABASE_ERROR: {
                "regex": re.compile(r"database|sql|connection.*failed|deadlock", re.IGNORECASE),
                "severity": "high",
                "description": "Database-related errors detected"
            },
            LogPattern.SEARCH_ERROR: {
                "regex": re.compile(r"search.*failed|embedding.*error|vector.*error", re.IGNORECASE),
                "severity": "medium",
                "description": "Search engine errors detected"
            },
            LogPattern.MEMORY_ISSUE: {
                "regex": re.compile(r"memory|out of memory|oom|allocation failed", re.IGNORECASE),
                "severity": "critical",
                "description": "Memory-related issues detected"
            },
            LogPattern.CONNECTION_ERROR: {
                "regex": re.compile(r"connection.*refused|network.*error|unreachable", re.IGNORECASE),
                "severity": "high",
                "description": "Network/connection errors detected"
            }
        }
    
    def read_log_files(
        self,
        time_range: Optional[Dict[str, datetime]] = None,
        max_entries: int = 10000
    ) -> List[LogEntry]:
        """
        Read and parse log files within time range.
        
        Args:
            time_range: Time range to filter logs
            max_entries: Maximum number of entries to read
            
        Returns:
            List of parsed log entries
        """
        logger.info(f"Reading log files from {self.log_dir}")
        
        entries = []
        
        # Find all log files
        log_files = []
        for pattern in ["*.log", "*.log.*"]:
            log_files.extend(self.log_dir.glob(pattern))
        
        # Sort by modification time (newest first)
        log_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        
        for log_file in log_files:
            if len(entries) >= max_entries:
                break
            
            try:
                entries.extend(self._read_single_log_file(log_file, time_range, max_entries - len(entries)))
            except Exception as e:
                logger.warning(f"Failed to read log file {log_file}: {e}")
        
        # Sort entries by timestamp
        entries.sort(key=lambda e: e.timestamp)
        
        logger.info(f"Read {len(entries)} log entries from {len(log_files)} files")
        return entries
    
    def _read_single_log_file(
        self,
        log_file: Path,
        time_range: Optional[Dict[str, datetime]],
        max_entries: int
    ) -> List[LogEntry]:
        """Read and parse a single log file."""
        entries = []
        
        # Handle compressed files
        if log_file.suffix == ".gz":
            open_func = gzip.open
            mode = "rt"
        else:
            open_func = open
            mode = "r"
        
        try:
            with open_func(log_file, mode, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if len(entries) >= max_entries:
                        break
                    
                    entry = self.parser.parse_log_line(line)
                    if entry:
                        # Filter by time range if specified
                        if time_range:
                            start_time = time_range.get("start")
                            end_time = time_range.get("end")
                            
                            if start_time and entry.timestamp < start_time:
                                continue
                            if end_time and entry.timestamp > end_time:
                                continue
                        
                        entries.append(entry)
        
        except Exception as e:
            logger.warning(f"Error reading log file {log_file}: {e}")
        
        return entries
    
    def calculate_statistics(self, entries: List[LogEntry]) -> LogStatistics:
        """
        Calculate comprehensive log statistics.
        
        Args:
            entries: List of log entries
            
        Returns:
            Log statistics
        """
        if not entries:
            return LogStatistics(
                total_entries=0,
                entries_by_level={},
                entries_by_logger={},
                entries_by_hour={},
                error_rate=0.0,
                warning_rate=0.0,
                top_errors=[],
                time_range={"start": datetime.now(), "end": datetime.now()}
            )
        
        # Basic counts
        total_entries = len(entries)
        entries_by_level = Counter(entry.level.value for entry in entries)
        entries_by_logger = Counter(entry.logger_name for entry in entries)
        
        # Entries by hour of day
        entries_by_hour = Counter(entry.timestamp.hour for entry in entries)
        
        # Error and warning rates
        error_count = entries_by_level.get("ERROR", 0) + entries_by_level.get("CRITICAL", 0)
        warning_count = entries_by_level.get("WARNING", 0)
        error_rate = (error_count / total_entries * 100) if total_entries > 0 else 0
        warning_rate = (warning_count / total_entries * 100) if total_entries > 0 else 0
        
        # Top errors
        error_messages = [entry.message for entry in entries 
                         if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]]
        error_counter = Counter(error_messages)
        top_errors = [
            {"message": msg, "count": count}
            for msg, count in error_counter.most_common(10)
        ]
        
        # Time range
        timestamps = [entry.timestamp for entry in entries]
        time_range = {
            "start": min(timestamps),
            "end": max(timestamps)
        }
        
        return LogStatistics(
            total_entries=total_entries,
            entries_by_level=dict(entries_by_level),
            entries_by_logger=dict(entries_by_logger),
            entries_by_hour=dict(entries_by_hour),
            error_rate=error_rate,
            warning_rate=warning_rate,
            top_errors=top_errors,
            time_range=time_range
        )
    
    def detect_patterns(self, entries: List[LogEntry]) -> List[LogPattern]:
        """
        Detect common patterns in log entries.
        
        Args:
            entries: List of log entries
            
        Returns:
            List of detected patterns
        """
        patterns = []
        
        for pattern_type, rule in self.pattern_rules.items():
            matching_entries = []
            
            for entry in entries:
                if rule["regex"].search(entry.message):
                    matching_entries.append(entry)
            
            if matching_entries:
                # Get sample messages (up to 5)
                sample_messages = list(set(entry.message for entry in matching_entries[:5]))
                
                pattern = LogPattern(
                    pattern_type=pattern_type,
                    count=len(matching_entries),
                    first_occurrence=min(entry.timestamp for entry in matching_entries),
                    last_occurrence=max(entry.timestamp for entry in matching_entries),
                    sample_messages=sample_messages,
                    severity=rule["severity"],
                    description=rule["description"],
                    suggested_action=self._get_suggested_action(pattern_type)
                )
                patterns.append(pattern)
        
        return patterns
    
    def _get_suggested_action(self, pattern_type: LogPattern) -> str:
        """Get suggested action for a pattern type."""
        suggestions = {
            LogPattern.ERROR_PATTERN: "Review error details and fix underlying issues",
            LogPattern.PERFORMANCE_ISSUE: "Investigate performance bottlenecks and optimize",
            LogPattern.DATABASE_ERROR: "Check database connectivity and query performance",
            LogPattern.SEARCH_ERROR: "Verify search engine configuration and model availability",
            LogPattern.MEMORY_ISSUE: "Monitor memory usage and consider increasing limits",
            LogPattern.CONNECTION_ERROR: "Check network connectivity and service availability"
        }
        return suggestions.get(pattern_type, "Investigate and resolve the underlying issue")
    
    def detect_anomalies(self, entries: List[LogEntry]) -> List[Dict[str, Any]]:
        """
        Detect anomalies in log patterns.
        
        Args:
            entries: List of log entries
            
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        if not entries:
            return anomalies
        
        # Group entries by hour
        entries_by_hour = defaultdict(list)
        for entry in entries:
            hour_key = entry.timestamp.replace(minute=0, second=0, microsecond=0)
            entries_by_hour[hour_key].append(entry)
        
        # Calculate hourly error rates
        hourly_error_rates = {}
        for hour, hour_entries in entries_by_hour.items():
            error_count = sum(1 for entry in hour_entries 
                            if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL])
            error_rate = (error_count / len(hour_entries) * 100) if hour_entries else 0
            hourly_error_rates[hour] = error_rate
        
        # Detect error rate spikes
        if len(hourly_error_rates) > 2:
            error_rates = list(hourly_error_rates.values())
            mean_rate = statistics.mean(error_rates)
            std_dev = statistics.stdev(error_rates) if len(error_rates) > 1 else 0
            
            threshold = mean_rate + (2 * std_dev)  # 2 standard deviations
            
            for hour, rate in hourly_error_rates.items():
                if rate > threshold and rate > 10:  # At least 10% error rate
                    anomalies.append({
                        "type": "error_rate_spike",
                        "timestamp": hour.isoformat(),
                        "description": f"Error rate spike: {rate:.1f}% (normal: {mean_rate:.1f}%)",
                        "severity": "high" if rate > 50 else "medium",
                        "value": rate,
                        "threshold": threshold
                    })
        
        # Detect sudden silence (no logs for extended period)
        if len(entries) > 1:
            time_gaps = []
            sorted_entries = sorted(entries, key=lambda e: e.timestamp)
            
            for i in range(1, len(sorted_entries)):
                gap = sorted_entries[i].timestamp - sorted_entries[i-1].timestamp
                time_gaps.append(gap.total_seconds())
            
            if time_gaps:
                mean_gap = statistics.mean(time_gaps)
                max_gap = max(time_gaps)
                
                # If max gap is more than 10x the average and > 1 hour
                if max_gap > (mean_gap * 10) and max_gap > 3600:
                    anomalies.append({
                        "type": "logging_silence",
                        "description": f"Extended logging silence: {max_gap/3600:.1f} hours",
                        "severity": "medium",
                        "value": max_gap,
                        "threshold": mean_gap * 10
                    })
        
        return anomalies
    
    def generate_recommendations(
        self,
        statistics: LogStatistics,
        patterns: List[LogPattern],
        anomalies: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Generate recommendations based on log analysis.
        
        Args:
            statistics: Log statistics
            patterns: Detected patterns
            anomalies: Detected anomalies
            
        Returns:
            List of recommendations
        """
        recommendations = []
        
        # High error rate
        if statistics.error_rate > 10:
            recommendations.append(
                f"High error rate detected ({statistics.error_rate:.1f}%) - investigate and fix errors"
            )
        
        # High warning rate
        if statistics.warning_rate > 20:
            recommendations.append(
                f"High warning rate ({statistics.warning_rate:.1f}%) - review warnings for potential issues"
            )
        
        # Critical patterns
        critical_patterns = [p for p in patterns if p.severity == "critical"]
        if critical_patterns:
            recommendations.append(
                f"Critical issues detected: {', '.join(p.description for p in critical_patterns)}"
            )
        
        # High severity patterns
        high_patterns = [p for p in patterns if p.severity == "high"]
        if high_patterns:
            recommendations.append(
                f"High priority issues: {', '.join(p.description for p in high_patterns)}"
            )
        
        # Anomalies
        high_anomalies = [a for a in anomalies if a.get("severity") == "high"]
        if high_anomalies:
            recommendations.append(
                f"Anomalies detected: {', '.join(a['description'] for a in high_anomalies)}"
            )
        
        # Log volume recommendations
        if statistics.total_entries > 50000:
            recommendations.append(
                "High log volume detected - consider adjusting log levels or implementing log rotation"
            )
        
        # If no issues found
        if not recommendations:
            recommendations.append("Log analysis shows no significant issues")
        
        return recommendations
    
    def generate_analysis_report(
        self,
        time_range: Optional[Dict[str, datetime]] = None,
        max_entries: int = 10000
    ) -> LogAnalysisReport:
        """
        Generate comprehensive log analysis report.
        
        Args:
            time_range: Time range for analysis
            max_entries: Maximum entries to analyze
            
        Returns:
            Comprehensive log analysis report
        """
        logger.info("Generating log analysis report")
        
        # Default to last 24 hours if no time range specified
        if not time_range:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)
            time_range = {"start": start_time, "end": end_time}
        
        # Read log entries
        entries = self.read_log_files(time_range, max_entries)
        
        # Calculate statistics
        statistics = self.calculate_statistics(entries)
        
        # Detect patterns
        patterns = self.detect_patterns(entries)
        
        # Detect anomalies
        anomalies = self.detect_anomalies(entries)
        
        # Generate recommendations
        recommendations = self.generate_recommendations(statistics, patterns, anomalies)
        
        # Calculate health indicators
        health_indicators = {
            "error_rate_health": "good" if statistics.error_rate < 5 else "warning" if statistics.error_rate < 10 else "critical",
            "pattern_health": "good" if not [p for p in patterns if p.severity in ["critical", "high"]] else "warning",
            "anomaly_health": "good" if not [a for a in anomalies if a.get("severity") == "high"] else "warning",
            "overall_health": "good"  # Will be calculated based on other indicators
        }
        
        # Calculate overall health
        health_scores = [
            1 if health_indicators["error_rate_health"] == "good" else 0.5 if health_indicators["error_rate_health"] == "warning" else 0,
            1 if health_indicators["pattern_health"] == "good" else 0.5,
            1 if health_indicators["anomaly_health"] == "good" else 0.5
        ]
        overall_score = sum(health_scores) / len(health_scores)
        
        if overall_score >= 0.8:
            health_indicators["overall_health"] = "good"
        elif overall_score >= 0.5:
            health_indicators["overall_health"] = "warning"
        else:
            health_indicators["overall_health"] = "critical"
        
        return LogAnalysisReport(
            timestamp=datetime.now(),
            time_range=time_range,
            statistics=statistics,
            patterns=patterns,
            anomalies=anomalies,
            recommendations=recommendations,
            health_indicators=health_indicators
        )


@graceful_degradation(service_name="log_analyzer")
def analyze_logs(
    log_dir: Optional[Path] = None,
    time_range: Optional[Dict[str, datetime]] = None,
    max_entries: int = 10000
) -> LogAnalysisReport:
    """
    Analyze logs and generate comprehensive report.
    
    Args:
        log_dir: Directory containing log files
        time_range: Time range for analysis
        max_entries: Maximum entries to analyze
        
    Returns:
        LogAnalysisReport: Comprehensive log analysis
    """
    analyzer = LogAnalyzer(log_dir)
    return analyzer.generate_analysis_report(time_range, max_entries)


@graceful_degradation(service_name="log_search")
def search_logs(
    query: str,
    log_dir: Optional[Path] = None,
    time_range: Optional[Dict[str, datetime]] = None,
    max_results: int = 100
) -> List[LogEntry]:
    """
    Search logs for specific patterns or messages.
    
    Args:
        query: Search query (regex supported)
        log_dir: Directory containing log files
        time_range: Time range for search
        max_results: Maximum results to return
        
    Returns:
        List of matching log entries
    """
    analyzer = LogAnalyzer(log_dir)
    entries = analyzer.read_log_files(time_range, max_results * 10)  # Read more to filter
    
    # Compile search pattern
    try:
        pattern = re.compile(query, re.IGNORECASE)
    except re.error:
        # If regex is invalid, use literal search
        pattern = re.compile(re.escape(query), re.IGNORECASE)
    
    # Filter matching entries
    matching_entries = []
    for entry in entries:
        if len(matching_entries) >= max_results:
            break
        
        if pattern.search(entry.message) or pattern.search(entry.logger_name):
            matching_entries.append(entry)
    
    return matching_entries