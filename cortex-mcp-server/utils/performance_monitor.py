"""
Performance monitoring utilities for search operations and system components.

This module provides comprehensive performance monitoring, metrics collection,
and analysis capabilities for the cortex mcp system.
"""

import asyncio
import time
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import threading

from utils.logging_config import get_component_logger, PerformanceLogger, TimedOperation
from utils.error_handling import graceful_degradation

logger = get_component_logger("performance_monitor")
perf_logger = PerformanceLogger()


class MetricType(Enum):
    """Types of performance metrics."""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"
    SEARCH_ACCURACY = "search_accuracy"
    DATABASE_PERFORMANCE = "database_performance"


@dataclass
class PerformanceMetric:
    """Individual performance metric data point."""
    timestamp: datetime
    metric_type: MetricType
    operation: str
    value: float
    unit: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "metric_type": self.metric_type.value,
            "operation": self.operation,
            "value": self.value,
            "unit": self.unit,
            "metadata": self.metadata
        }


@dataclass
class PerformanceStats:
    """Statistical analysis of performance metrics."""
    operation: str
    metric_type: MetricType
    count: int
    min_value: float
    max_value: float
    mean_value: float
    median_value: float
    p95_value: float
    p99_value: float
    std_deviation: float
    unit: str
    time_range: Dict[str, datetime]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "operation": self.operation,
            "metric_type": self.metric_type.value,
            "count": self.count,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "median_value": self.median_value,
            "p95_value": self.p95_value,
            "p99_value": self.p99_value,
            "std_deviation": self.std_deviation,
            "unit": self.unit,
            "time_range": {
                "start": self.time_range["start"].isoformat(),
                "end": self.time_range["end"].isoformat()
            }
        }


@dataclass
class PerformanceAlert:
    """Performance alert for threshold violations."""
    timestamp: datetime
    severity: str  # "low", "medium", "high", "critical"
    operation: str
    metric_type: MetricType
    current_value: float
    threshold_value: float
    description: str
    suggested_action: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "operation": self.operation,
            "metric_type": self.metric_type.value,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "description": self.description,
            "suggested_action": self.suggested_action
        }


@dataclass
class PerformanceReport:
    """Comprehensive performance analysis report."""
    timestamp: datetime
    time_range: Dict[str, datetime]
    stats: List[PerformanceStats]
    alerts: List[PerformanceAlert]
    trends: Dict[str, Any]
    recommendations: List[str]
    system_health_score: float  # 0-100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "time_range": {
                "start": self.time_range["start"].isoformat(),
                "end": self.time_range["end"].isoformat()
            },
            "stats": [stat.to_dict() for stat in self.stats],
            "alerts": [alert.to_dict() for alert in self.alerts],
            "trends": self.trends,
            "recommendations": self.recommendations,
            "system_health_score": self.system_health_score
        }


class PerformanceThresholds:
    """Performance threshold configuration."""
    
    def __init__(self):
        self.thresholds = {
            # Search operation thresholds (milliseconds)
            "search_semantic": {"warning": 1000, "critical": 3000},
            "search_keyword": {"warning": 500, "critical": 1500},
            "search_hybrid": {"warning": 1500, "critical": 4000},
            
            # Database operation thresholds (milliseconds)
            "db_query": {"warning": 100, "critical": 500},
            "db_insert": {"warning": 50, "critical": 200},
            "db_update": {"warning": 75, "critical": 300},
            "db_delete": {"warning": 50, "critical": 200},
            
            # Embedding generation thresholds (milliseconds)
            "embedding_generation": {"warning": 500, "critical": 2000},
            
            # Memory usage thresholds (MB)
            "memory_usage": {"warning": 500, "critical": 1000},
            
            # Error rate thresholds (percentage)
            "error_rate": {"warning": 5.0, "critical": 10.0}
        }
    
    def get_threshold(self, operation: str, level: str) -> Optional[float]:
        """Get threshold value for operation and level."""
        return self.thresholds.get(operation, {}).get(level)
    
    def set_threshold(self, operation: str, level: str, value: float) -> None:
        """Set threshold value for operation and level."""
        if operation not in self.thresholds:
            self.thresholds[operation] = {}
        self.thresholds[operation][level] = value


class PerformanceMonitor:
    """Comprehensive performance monitoring system."""
    
    def __init__(self, max_metrics: int = 10000):
        """
        Initialize performance monitor.
        
        Args:
            max_metrics: Maximum number of metrics to keep in memory
        """
        self.max_metrics = max_metrics
        self.metrics: deque = deque(maxlen=max_metrics)
        self.thresholds = PerformanceThresholds()
        self.alerts: List[PerformanceAlert] = []
        self.operation_counters = defaultdict(int)
        self.error_counters = defaultdict(int)
        self._lock = threading.Lock()
        
        logger.info("Performance monitor initialized")
    
    def record_metric(
        self,
        metric_type: MetricType,
        operation: str,
        value: float,
        unit: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Record a performance metric.
        
        Args:
            metric_type: Type of metric
            operation: Operation name
            value: Metric value
            unit: Unit of measurement
            metadata: Additional metadata
        """
        with self._lock:
            metric = PerformanceMetric(
                timestamp=datetime.now(),
                metric_type=metric_type,
                operation=operation,
                value=value,
                unit=unit,
                metadata=metadata or {}
            )
            
            self.metrics.append(metric)
            self.operation_counters[operation] += 1
            
            # Check for threshold violations
            self._check_thresholds(metric)
            
            # Log performance metric
            perf_logger.log_operation_time(operation, value / 1000, metadata)
    
    def record_search_performance(
        self,
        search_type: str,
        query: str,
        result_count: int,
        duration_ms: float,
        accuracy_score: Optional[float] = None
    ) -> None:
        """
        Record search operation performance.
        
        Args:
            search_type: Type of search (semantic, keyword, hybrid)
            query: Search query
            result_count: Number of results returned
            duration_ms: Duration in milliseconds
            accuracy_score: Optional accuracy score (0-1)
        """
        operation = f"search_{search_type}"
        
        # Record response time
        self.record_metric(
            MetricType.RESPONSE_TIME,
            operation,
            duration_ms,
            "ms",
            {
                "query_length": len(query),
                "result_count": result_count,
                "search_type": search_type
            }
        )
        
        # Record accuracy if provided
        if accuracy_score is not None:
            self.record_metric(
                MetricType.SEARCH_ACCURACY,
                operation,
                accuracy_score * 100,
                "percentage",
                {"query_length": len(query), "result_count": result_count}
            )
        
        # Log to performance logger
        perf_logger.log_search_performance(query, result_count, duration_ms / 1000, search_type)
    
    def record_database_performance(
        self,
        operation: str,
        table: str,
        duration_ms: float,
        record_count: Optional[int] = None,
        error: Optional[Exception] = None
    ) -> None:
        """
        Record database operation performance.
        
        Args:
            operation: Database operation (query, insert, update, delete)
            table: Table name
            duration_ms: Duration in milliseconds
            record_count: Number of records affected
            error: Exception if operation failed
        """
        db_operation = f"db_{operation}"
        
        if error:
            self.record_error(db_operation, error)
        else:
            self.record_metric(
                MetricType.DATABASE_PERFORMANCE,
                db_operation,
                duration_ms,
                "ms",
                {
                    "table": table,
                    "record_count": record_count,
                    "operation": operation
                }
            )
        
        # Log to performance logger
        perf_logger.log_database_performance(operation, table, duration_ms / 1000, record_count)
    
    def record_error(self, operation: str, error: Exception) -> None:
        """
        Record an error for an operation.
        
        Args:
            operation: Operation name
            error: Exception that occurred
        """
        with self._lock:
            self.error_counters[operation] += 1
            
            # Calculate error rate
            total_operations = self.operation_counters[operation]
            error_rate = (self.error_counters[operation] / total_operations * 100) if total_operations > 0 else 0
            
            self.record_metric(
                MetricType.ERROR_RATE,
                operation,
                error_rate,
                "percentage",
                {"error_type": type(error).__name__, "error_message": str(error)}
            )
    
    def _check_thresholds(self, metric: PerformanceMetric) -> None:
        """Check if metric violates any thresholds and create alerts."""
        if metric.metric_type != MetricType.RESPONSE_TIME:
            return
        
        warning_threshold = self.thresholds.get_threshold(metric.operation, "warning")
        critical_threshold = self.thresholds.get_threshold(metric.operation, "critical")
        
        if critical_threshold and metric.value > critical_threshold:
            alert = PerformanceAlert(
                timestamp=metric.timestamp,
                severity="critical",
                operation=metric.operation,
                metric_type=metric.metric_type,
                current_value=metric.value,
                threshold_value=critical_threshold,
                description=f"{metric.operation} response time ({metric.value:.1f}ms) exceeds critical threshold ({critical_threshold}ms)",
                suggested_action="Investigate performance bottlenecks and optimize operation"
            )
            self.alerts.append(alert)
            logger.error(f"Critical performance alert: {alert.description}")
            
        elif warning_threshold and metric.value > warning_threshold:
            alert = PerformanceAlert(
                timestamp=metric.timestamp,
                severity="warning",
                operation=metric.operation,
                metric_type=metric.metric_type,
                current_value=metric.value,
                threshold_value=warning_threshold,
                description=f"{metric.operation} response time ({metric.value:.1f}ms) exceeds warning threshold ({warning_threshold}ms)",
                suggested_action="Monitor operation performance and consider optimization"
            )
            self.alerts.append(alert)
            logger.warning(f"Performance warning: {alert.description}")
    
    def get_metrics(
        self,
        operation: Optional[str] = None,
        metric_type: Optional[MetricType] = None,
        time_range: Optional[Dict[str, datetime]] = None
    ) -> List[PerformanceMetric]:
        """
        Get metrics filtered by criteria.
        
        Args:
            operation: Filter by operation name
            metric_type: Filter by metric type
            time_range: Filter by time range (start, end)
            
        Returns:
            List of matching metrics
        """
        with self._lock:
            filtered_metrics = list(self.metrics)
        
        if operation:
            filtered_metrics = [m for m in filtered_metrics if m.operation == operation]
        
        if metric_type:
            filtered_metrics = [m for m in filtered_metrics if m.metric_type == metric_type]
        
        if time_range:
            start_time = time_range.get("start")
            end_time = time_range.get("end")
            
            if start_time:
                filtered_metrics = [m for m in filtered_metrics if m.timestamp >= start_time]
            if end_time:
                filtered_metrics = [m for m in filtered_metrics if m.timestamp <= end_time]
        
        return filtered_metrics
    
    def calculate_stats(
        self,
        operation: str,
        metric_type: MetricType,
        time_range: Optional[Dict[str, datetime]] = None
    ) -> Optional[PerformanceStats]:
        """
        Calculate statistical analysis for metrics.
        
        Args:
            operation: Operation name
            metric_type: Metric type
            time_range: Time range for analysis
            
        Returns:
            Performance statistics or None if no data
        """
        metrics = self.get_metrics(operation, metric_type, time_range)
        
        if not metrics:
            return None
        
        values = [m.value for m in metrics]
        
        if not values:
            return None
        
        # Calculate percentiles
        sorted_values = sorted(values)
        p95_index = int(0.95 * len(sorted_values))
        p99_index = int(0.99 * len(sorted_values))
        
        # Determine time range
        timestamps = [m.timestamp for m in metrics]
        actual_time_range = {
            "start": min(timestamps),
            "end": max(timestamps)
        }
        
        return PerformanceStats(
            operation=operation,
            metric_type=metric_type,
            count=len(values),
            min_value=min(values),
            max_value=max(values),
            mean_value=statistics.mean(values),
            median_value=statistics.median(values),
            p95_value=sorted_values[p95_index] if p95_index < len(sorted_values) else sorted_values[-1],
            p99_value=sorted_values[p99_index] if p99_index < len(sorted_values) else sorted_values[-1],
            std_deviation=statistics.stdev(values) if len(values) > 1 else 0,
            unit=metrics[0].unit,
            time_range=actual_time_range
        )
    
    def generate_performance_report(
        self,
        time_range: Optional[Dict[str, datetime]] = None
    ) -> PerformanceReport:
        """
        Generate comprehensive performance report.
        
        Args:
            time_range: Time range for analysis
            
        Returns:
            Comprehensive performance report
        """
        logger.info("Generating performance report")
        
        # Default to last 24 hours if no time range specified
        if not time_range:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)
            time_range = {"start": start_time, "end": end_time}
        
        # Get all unique operations and metric types
        metrics = self.get_metrics(time_range=time_range)
        operations = set(m.operation for m in metrics)
        metric_types = set(m.metric_type for m in metrics)
        
        # Calculate stats for each operation/metric type combination
        stats = []
        for operation in operations:
            for metric_type in metric_types:
                stat = self.calculate_stats(operation, metric_type, time_range)
                if stat:
                    stats.append(stat)
        
        # Get recent alerts
        recent_alerts = [
            alert for alert in self.alerts
            if time_range["start"] <= alert.timestamp <= time_range["end"]
        ]
        
        # Calculate trends
        trends = self._calculate_trends(time_range)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(stats, recent_alerts)
        
        # Calculate system health score
        health_score = self._calculate_health_score(stats, recent_alerts)
        
        return PerformanceReport(
            timestamp=datetime.now(),
            time_range=time_range,
            stats=stats,
            alerts=recent_alerts,
            trends=trends,
            recommendations=recommendations,
            system_health_score=health_score
        )
    
    def _calculate_trends(self, time_range: Dict[str, datetime]) -> Dict[str, Any]:
        """Calculate performance trends over time."""
        trends = {}
        
        # Split time range into buckets for trend analysis
        start_time = time_range["start"]
        end_time = time_range["end"]
        duration = end_time - start_time
        bucket_size = duration / 10  # 10 buckets
        
        # Analyze response time trends for key operations
        key_operations = ["search_semantic", "search_keyword", "search_hybrid", "db_query"]
        
        for operation in key_operations:
            metrics = self.get_metrics(operation, MetricType.RESPONSE_TIME, time_range)
            if not metrics:
                continue
            
            # Group metrics into time buckets
            buckets = defaultdict(list)
            for metric in metrics:
                bucket_index = int((metric.timestamp - start_time) / bucket_size)
                buckets[bucket_index].append(metric.value)
            
            # Calculate average for each bucket
            bucket_averages = []
            for i in range(10):
                if i in buckets:
                    bucket_averages.append(statistics.mean(buckets[i]))
                else:
                    bucket_averages.append(None)
            
            # Calculate trend (simple linear regression slope)
            valid_points = [(i, avg) for i, avg in enumerate(bucket_averages) if avg is not None]
            if len(valid_points) >= 2:
                x_values = [p[0] for p in valid_points]
                y_values = [p[1] for p in valid_points]
                
                # Simple slope calculation
                n = len(valid_points)
                slope = (n * sum(x * y for x, y in valid_points) - sum(x_values) * sum(y_values)) / \
                       (n * sum(x * x for x in x_values) - sum(x_values) ** 2)
                
                trends[operation] = {
                    "slope": slope,
                    "direction": "improving" if slope < 0 else "degrading" if slope > 0 else "stable",
                    "bucket_averages": bucket_averages
                }
        
        return trends
    
    def _generate_recommendations(
        self,
        stats: List[PerformanceStats],
        alerts: List[PerformanceAlert]
    ) -> List[str]:
        """Generate performance recommendations based on analysis."""
        recommendations = []
        
        # Check for slow operations
        for stat in stats:
            if stat.metric_type == MetricType.RESPONSE_TIME:
                if stat.mean_value > 1000:  # > 1 second
                    recommendations.append(
                        f"Optimize {stat.operation} - average response time is {stat.mean_value:.1f}ms"
                    )
                
                if stat.p95_value > 2000:  # > 2 seconds for 95th percentile
                    recommendations.append(
                        f"Investigate {stat.operation} performance spikes - 95th percentile is {stat.p95_value:.1f}ms"
                    )
        
        # Check for high error rates
        for stat in stats:
            if stat.metric_type == MetricType.ERROR_RATE and stat.mean_value > 5:
                recommendations.append(
                    f"Address errors in {stat.operation} - error rate is {stat.mean_value:.1f}%"
                )
        
        # Check for critical alerts
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        if critical_alerts:
            recommendations.append(
                f"Immediate attention required - {len(critical_alerts)} critical performance issues detected"
            )
        
        # General recommendations
        if not recommendations:
            recommendations.append("System performance is within acceptable ranges")
        
        return recommendations
    
    def _calculate_health_score(
        self,
        stats: List[PerformanceStats],
        alerts: List[PerformanceAlert]
    ) -> float:
        """Calculate overall system health score (0-100)."""
        score = 100.0
        
        # Deduct points for slow operations
        for stat in stats:
            if stat.metric_type == MetricType.RESPONSE_TIME:
                if stat.mean_value > 2000:  # > 2 seconds
                    score -= 20
                elif stat.mean_value > 1000:  # > 1 second
                    score -= 10
                elif stat.mean_value > 500:  # > 0.5 seconds
                    score -= 5
        
        # Deduct points for high error rates
        for stat in stats:
            if stat.metric_type == MetricType.ERROR_RATE:
                if stat.mean_value > 10:  # > 10%
                    score -= 30
                elif stat.mean_value > 5:  # > 5%
                    score -= 15
                elif stat.mean_value > 1:  # > 1%
                    score -= 5
        
        # Deduct points for alerts
        for alert in alerts:
            if alert.severity == "critical":
                score -= 15
            elif alert.severity == "warning":
                score -= 5
        
        return max(0, min(100, score))
    
    def clear_old_metrics(self, days_old: int = 7) -> int:
        """
        Clear metrics older than specified days.
        
        Args:
            days_old: Remove metrics older than this many days
            
        Returns:
            Number of metrics removed
        """
        cutoff_time = datetime.now() - timedelta(days=days_old)
        
        with self._lock:
            original_count = len(self.metrics)
            self.metrics = deque(
                (m for m in self.metrics if m.timestamp >= cutoff_time),
                maxlen=self.max_metrics
            )
            removed_count = original_count - len(self.metrics)
        
        logger.info(f"Cleared {removed_count} old performance metrics")
        return removed_count
    
    def clear_old_alerts(self, days_old: int = 30) -> int:
        """
        Clear alerts older than specified days.
        
        Args:
            days_old: Remove alerts older than this many days
            
        Returns:
            Number of alerts removed
        """
        cutoff_time = datetime.now() - timedelta(days=days_old)
        
        original_count = len(self.alerts)
        self.alerts = [alert for alert in self.alerts if alert.timestamp >= cutoff_time]
        removed_count = original_count - len(self.alerts)
        
        logger.info(f"Cleared {removed_count} old performance alerts")
        return removed_count


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor instance."""
    global _performance_monitor
    
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    
    return _performance_monitor


def reset_performance_monitor() -> None:
    """Reset the global performance monitor (mainly for testing)."""
    global _performance_monitor
    _performance_monitor = None


# Context manager for automatic performance monitoring
class MonitoredOperation:
    """Context manager for monitoring operation performance."""
    
    def __init__(
        self,
        operation: str,
        monitor: Optional[PerformanceMonitor] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        self.monitor = monitor or get_performance_monitor()
        self.metadata = metadata or {}
        self.start_time: Optional[float] = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration_ms = (time.time() - self.start_time) * 1000
            
            if exc_type:
                # Record error
                self.monitor.record_error(self.operation, exc_val)
            else:
                # Record successful operation
                self.monitor.record_metric(
                    MetricType.RESPONSE_TIME,
                    self.operation,
                    duration_ms,
                    "ms",
                    self.metadata
                )


@graceful_degradation(service_name="performance_monitor")
def generate_performance_report(
    time_range: Optional[Dict[str, datetime]] = None
) -> PerformanceReport:
    """
    Generate a comprehensive performance report.
    
    Args:
        time_range: Time range for analysis
        
    Returns:
        PerformanceReport: Comprehensive performance analysis
    """
    monitor = get_performance_monitor()
    return monitor.generate_performance_report(time_range)