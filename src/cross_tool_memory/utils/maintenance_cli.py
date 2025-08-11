"""
Command-line interface for monitoring and maintenance tools.

This module provides a comprehensive CLI for database integrity checks,
storage monitoring, performance analysis, and log troubleshooting.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
import click

from ..config.database import DatabaseConfig, get_database_manager
from ..utils.database_integrity import run_integrity_check
from ..utils.storage_monitor import generate_storage_report, run_automated_cleanup
from ..utils.performance_monitor import generate_performance_report, get_performance_monitor
from ..utils.log_analyzer import analyze_logs, search_logs
from ..utils.logging_config import setup_default_logging, get_component_logger

logger = get_component_logger("maintenance_cli")


@click.group()
@click.option('--database-path', help='Path to SQLite database file')
@click.option('--data-dir', help='Data directory path')
@click.option('--log-dir', help='Log directory path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.pass_context
def cli(ctx, database_path, data_dir, log_dir, verbose):
    """Cross-Tool Memory Monitoring and Maintenance CLI."""
    # Setup logging
    log_level = "DEBUG" if verbose else "INFO"
    setup_default_logging(log_level=log_level)
    
    # Store configuration in context
    ctx.ensure_object(dict)
    ctx.obj['database_path'] = database_path
    ctx.obj['data_dir'] = Path(data_dir) if data_dir else None
    ctx.obj['log_dir'] = Path(log_dir) if log_dir else None
    ctx.obj['verbose'] = verbose


@cli.group()
def integrity():
    """Database integrity check commands."""
    pass


@integrity.command('check')
@click.option('--auto-fix', is_flag=True, help='Automatically fix issues that can be safely repaired')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
@click.pass_context
def integrity_check(ctx, auto_fix, output):
    """Run comprehensive database integrity check."""
    click.echo("Running database integrity check...")
    
    try:
        # Setup database manager
        db_config = DatabaseConfig(database_path=ctx.obj['database_path'])
        db_manager = get_database_manager(db_config)
        
        # Run integrity check
        result = asyncio.run(run_integrity_check(db_manager, auto_fix=auto_fix))
        
        if output == 'json':
            # Convert to JSON-serializable format
            json_result = {
                "timestamp": result.timestamp.isoformat(),
                "total_checks": result.total_checks,
                "issues_found": len(result.issues_found),
                "duration_seconds": result.duration_seconds,
                "is_healthy": result.is_healthy,
                "summary": result.summary,
                "issues": [
                    {
                        "type": issue.issue_type.value,
                        "table": issue.table_name,
                        "record_id": issue.record_id,
                        "description": issue.description,
                        "severity": issue.severity,
                        "auto_fixable": issue.auto_fixable,
                        "fix_suggestion": issue.fix_suggestion
                    }
                    for issue in result.issues_found
                ]
            }
            click.echo(json.dumps(json_result, indent=2))
        else:
            # Text output
            click.echo(f"\n{'='*60}")
            click.echo(f"DATABASE INTEGRITY CHECK REPORT")
            click.echo(f"{'='*60}")
            click.echo(f"Timestamp: {result.timestamp}")
            click.echo(f"Duration: {result.duration_seconds:.2f} seconds")
            click.echo(f"Total checks: {result.total_checks}")
            click.echo(f"Issues found: {len(result.issues_found)}")
            click.echo(f"Database health: {'HEALTHY' if result.is_healthy else 'ISSUES DETECTED'}")
            
            if result.summary:
                click.echo(f"\nSummary:")
                for key, value in result.summary.items():
                    click.echo(f"  {key}: {value}")
            
            if result.issues_found:
                click.echo(f"\nIssues detected:")
                for issue in result.issues_found:
                    severity_color = {
                        'critical': 'red',
                        'high': 'red',
                        'medium': 'yellow',
                        'low': 'blue'
                    }.get(issue.severity, 'white')
                    
                    click.echo(f"\n  {click.style(issue.severity.upper(), fg=severity_color)} - {issue.table_name}")
                    click.echo(f"    Record: {issue.record_id}")
                    click.echo(f"    Issue: {issue.description}")
                    if issue.fix_suggestion:
                        click.echo(f"    Fix: {issue.fix_suggestion}")
                    if issue.auto_fixable:
                        click.echo(f"    {click.style('Auto-fixable', fg='green')}")
            else:
                click.echo(f"\n{click.style('✓ No integrity issues found', fg='green')}")
        
    except Exception as e:
        click.echo(f"Error running integrity check: {e}", err=True)
        sys.exit(1)


@cli.group()
def storage():
    """Storage monitoring and cleanup commands."""
    pass


@storage.command('report')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
@click.pass_context
def storage_report(ctx, output):
    """Generate storage usage report."""
    click.echo("Generating storage usage report...")
    
    try:
        # Setup database manager
        db_config = DatabaseConfig(database_path=ctx.obj['database_path'])
        db_manager = get_database_manager(db_config)
        
        # Generate report
        report = asyncio.run(generate_storage_report(
            db_manager=db_manager,
            data_dir=ctx.obj['data_dir'],
            log_dir=ctx.obj['log_dir']
        ))
        
        if output == 'json':
            click.echo(json.dumps(report.to_dict(), indent=2))
        else:
            # Text output
            click.echo(f"\n{'='*60}")
            click.echo(f"STORAGE USAGE REPORT")
            click.echo(f"{'='*60}")
            click.echo(f"Timestamp: {report.timestamp}")
            
            # Usage information
            usage = report.usage
            click.echo(f"\nStorage Usage:")
            click.echo(f"  Database: {usage.database_size_mb:.1f} MB")
            click.echo(f"  Log files: {usage.log_files_size_mb:.1f} MB")
            click.echo(f"  Temp files: {usage.temp_files_size_mb:.1f} MB")
            click.echo(f"  Total used: {usage.total_size_mb:.1f} MB")
            click.echo(f"  Available: {usage.available_space_mb:.1f} MB")
            click.echo(f"  Usage: {usage.usage_percentage:.1f}%")
            
            # Warnings
            if report.warnings:
                click.echo(f"\nWarnings:")
                for warning in report.warnings:
                    click.echo(f"  {click.style('⚠', fg='yellow')} {warning}")
            
            # Conversation stats
            if 'error' not in report.conversation_stats:
                stats = report.conversation_stats
                click.echo(f"\nConversation Statistics:")
                click.echo(f"  Total conversations: {stats['total_conversations']}")
                click.echo(f"  Average content length: {stats['avg_content_length']:.0f} chars")
                
                if stats['by_tool']:
                    click.echo(f"  By tool:")
                    for tool, count in stats['by_tool'].items():
                        click.echo(f"    {tool}: {count}")
            
            # Cleanup recommendations
            if report.cleanup_recommendations:
                click.echo(f"\nCleanup Recommendations:")
                for rec in report.cleanup_recommendations:
                    priority_color = {
                        'high': 'red',
                        'medium': 'yellow',
                        'low': 'blue'
                    }.get(rec['priority'], 'white')
                    
                    click.echo(f"  {click.style(rec['priority'].upper(), fg=priority_color)}: {rec['description']}")
                    click.echo(f"    Estimated savings: {rec['estimated_savings_mb']:.1f} MB")
            else:
                click.echo(f"\n{click.style('✓ No cleanup recommendations', fg='green')}")
        
    except Exception as e:
        click.echo(f"Error generating storage report: {e}", err=True)
        sys.exit(1)


@storage.command('cleanup')
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned up without actually doing it')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
@click.pass_context
def storage_cleanup(ctx, dry_run, output):
    """Run automated storage cleanup."""
    action = "Simulating" if dry_run else "Running"
    click.echo(f"{action} automated storage cleanup...")
    
    try:
        # Setup database manager
        db_config = DatabaseConfig(database_path=ctx.obj['database_path'])
        db_manager = get_database_manager(db_config)
        
        # Run cleanup
        results = asyncio.run(run_automated_cleanup(
            db_manager=db_manager,
            data_dir=ctx.obj['data_dir'],
            log_dir=ctx.obj['log_dir'],
            dry_run=dry_run
        ))
        
        if output == 'json':
            json_results = [
                {
                    "action": result.action.value,
                    "success": result.success,
                    "items_processed": result.items_processed,
                    "mb_freed": result.mb_freed,
                    "duration_seconds": result.duration_seconds,
                    "error_message": result.error_message,
                    "details": result.details
                }
                for result in results
            ]
            click.echo(json.dumps(json_results, indent=2))
        else:
            # Text output
            click.echo(f"\n{'='*60}")
            click.echo(f"STORAGE CLEANUP RESULTS")
            click.echo(f"{'='*60}")
            
            total_mb_freed = sum(r.mb_freed for r in results if r.success)
            total_items = sum(r.items_processed for r in results if r.success)
            
            click.echo(f"Total items processed: {total_items}")
            click.echo(f"Total space {'would be ' if dry_run else ''}freed: {total_mb_freed:.1f} MB")
            
            for result in results:
                status_color = 'green' if result.success else 'red'
                status = '✓' if result.success else '✗'
                
                click.echo(f"\n{click.style(status, fg=status_color)} {result.action.value}")
                click.echo(f"  Items processed: {result.items_processed}")
                click.echo(f"  Space {'would be ' if dry_run else ''}freed: {result.mb_freed:.1f} MB")
                click.echo(f"  Duration: {result.duration_seconds:.2f}s")
                
                if result.error_message:
                    click.echo(f"  Error: {result.error_message}")
        
    except Exception as e:
        click.echo(f"Error running storage cleanup: {e}", err=True)
        sys.exit(1)


@cli.group()
def performance():
    """Performance monitoring commands."""
    pass


@performance.command('report')
@click.option('--hours', default=24, help='Number of hours to analyze (default: 24)')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
def performance_report(hours, output):
    """Generate performance analysis report."""
    click.echo(f"Generating performance report for last {hours} hours...")
    
    try:
        # Define time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        time_range = {"start": start_time, "end": end_time}
        
        # Generate report
        report = generate_performance_report(time_range)
        
        if output == 'json':
            click.echo(json.dumps(report.to_dict(), indent=2))
        else:
            # Text output
            click.echo(f"\n{'='*60}")
            click.echo(f"PERFORMANCE ANALYSIS REPORT")
            click.echo(f"{'='*60}")
            click.echo(f"Timestamp: {report.timestamp}")
            click.echo(f"Time range: {start_time} to {end_time}")
            click.echo(f"System health score: {report.system_health_score:.1f}/100")
            
            # Performance statistics
            if report.stats:
                click.echo(f"\nPerformance Statistics:")
                for stat in report.stats:
                    if stat.metric_type.value == "response_time":
                        click.echo(f"\n  {stat.operation}:")
                        click.echo(f"    Count: {stat.count}")
                        click.echo(f"    Average: {stat.mean_value:.1f}ms")
                        click.echo(f"    95th percentile: {stat.p95_value:.1f}ms")
                        click.echo(f"    Max: {stat.max_value:.1f}ms")
            
            # Alerts
            if report.alerts:
                click.echo(f"\nPerformance Alerts:")
                for alert in report.alerts:
                    severity_color = {
                        'critical': 'red',
                        'warning': 'yellow',
                        'low': 'blue'
                    }.get(alert.severity, 'white')
                    
                    click.echo(f"  {click.style(alert.severity.upper(), fg=severity_color)}: {alert.description}")
            
            # Recommendations
            if report.recommendations:
                click.echo(f"\nRecommendations:")
                for rec in report.recommendations:
                    click.echo(f"  • {rec}")
            else:
                click.echo(f"\n{click.style('✓ No performance issues detected', fg='green')}")
        
    except Exception as e:
        click.echo(f"Error generating performance report: {e}", err=True)
        sys.exit(1)


@cli.group()
def logs():
    """Log analysis and troubleshooting commands."""
    pass


@logs.command('analyze')
@click.option('--hours', default=24, help='Number of hours to analyze (default: 24)')
@click.option('--max-entries', default=10000, help='Maximum log entries to analyze')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
@click.pass_context
def logs_analyze(ctx, hours, max_entries, output):
    """Analyze logs for patterns and issues."""
    click.echo(f"Analyzing logs for last {hours} hours...")
    
    try:
        # Define time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        time_range = {"start": start_time, "end": end_time}
        
        # Analyze logs
        report = analyze_logs(
            log_dir=ctx.obj['log_dir'],
            time_range=time_range,
            max_entries=max_entries
        )
        
        if output == 'json':
            click.echo(json.dumps(report.to_dict(), indent=2))
        else:
            # Text output
            click.echo(f"\n{'='*60}")
            click.echo(f"LOG ANALYSIS REPORT")
            click.echo(f"{'='*60}")
            click.echo(f"Timestamp: {report.timestamp}")
            click.echo(f"Time range: {start_time} to {end_time}")
            
            # Statistics
            stats = report.statistics
            click.echo(f"\nLog Statistics:")
            click.echo(f"  Total entries: {stats.total_entries}")
            click.echo(f"  Error rate: {stats.error_rate:.1f}%")
            click.echo(f"  Warning rate: {stats.warning_rate:.1f}%")
            
            if stats.entries_by_level:
                click.echo(f"  By level:")
                for level, count in stats.entries_by_level.items():
                    click.echo(f"    {level}: {count}")
            
            # Patterns
            if report.patterns:
                click.echo(f"\nDetected Patterns:")
                for pattern in report.patterns:
                    severity_color = {
                        'critical': 'red',
                        'high': 'red',
                        'medium': 'yellow',
                        'low': 'blue'
                    }.get(pattern.severity, 'white')
                    
                    click.echo(f"  {click.style(pattern.severity.upper(), fg=severity_color)}: {pattern.description}")
                    click.echo(f"    Count: {pattern.count}")
                    click.echo(f"    First: {pattern.first_occurrence}")
                    click.echo(f"    Last: {pattern.last_occurrence}")
            
            # Anomalies
            if report.anomalies:
                click.echo(f"\nAnomalies:")
                for anomaly in report.anomalies:
                    click.echo(f"  • {anomaly['description']}")
            
            # Recommendations
            if report.recommendations:
                click.echo(f"\nRecommendations:")
                for rec in report.recommendations:
                    click.echo(f"  • {rec}")
            
            # Health indicators
            health = report.health_indicators
            overall_health = health.get('overall_health', 'unknown')
            health_color = {
                'good': 'green',
                'warning': 'yellow',
                'critical': 'red'
            }.get(overall_health, 'white')
            
            click.echo(f"\nOverall Health: {click.style(overall_health.upper(), fg=health_color)}")
        
    except Exception as e:
        click.echo(f"Error analyzing logs: {e}", err=True)
        sys.exit(1)


@logs.command('search')
@click.argument('query')
@click.option('--hours', default=24, help='Number of hours to search (default: 24)')
@click.option('--max-results', default=50, help='Maximum results to return')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
@click.pass_context
def logs_search(ctx, query, hours, max_results, output):
    """Search logs for specific patterns."""
    click.echo(f"Searching logs for: {query}")
    
    try:
        # Define time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        time_range = {"start": start_time, "end": end_time}
        
        # Search logs
        results = search_logs(
            query=query,
            log_dir=ctx.obj['log_dir'],
            time_range=time_range,
            max_results=max_results
        )
        
        if output == 'json':
            json_results = [entry.to_dict() for entry in results]
            click.echo(json.dumps(json_results, indent=2))
        else:
            # Text output
            click.echo(f"\nFound {len(results)} matching entries:")
            
            for entry in results:
                level_color = {
                    'DEBUG': 'blue',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'red'
                }.get(entry.level.value, 'white')
                
                click.echo(f"\n{entry.timestamp} {click.style(entry.level.value, fg=level_color)} {entry.logger_name}")
                click.echo(f"  {entry.message}")
        
    except Exception as e:
        click.echo(f"Error searching logs: {e}", err=True)
        sys.exit(1)


@cli.command('health')
@click.option('--output', '-o', type=click.Choice(['text', 'json']), default='text', help='Output format')
@click.pass_context
def health_check(ctx, output):
    """Run comprehensive system health check."""
    click.echo("Running comprehensive system health check...")
    
    try:
        # Setup database manager
        db_config = DatabaseConfig(database_path=ctx.obj['database_path'])
        db_manager = get_database_manager(db_config)
        
        # Run all health checks
        integrity_result = asyncio.run(run_integrity_check(db_manager))
        storage_report = asyncio.run(generate_storage_report(
            db_manager=db_manager,
            data_dir=ctx.obj['data_dir'],
            log_dir=ctx.obj['log_dir']
        ))
        performance_report = generate_performance_report()
        log_report = analyze_logs(log_dir=ctx.obj['log_dir'])
        
        if output == 'json':
            health_data = {
                "timestamp": datetime.now().isoformat(),
                "database_integrity": {
                    "healthy": integrity_result.is_healthy,
                    "issues_count": len(integrity_result.issues_found),
                    "critical_issues": len([i for i in integrity_result.issues_found if i.severity == "critical"])
                },
                "storage": {
                    "usage_percentage": storage_report.usage.usage_percentage,
                    "warnings_count": len(storage_report.warnings),
                    "cleanup_recommendations": len(storage_report.cleanup_recommendations)
                },
                "performance": {
                    "health_score": performance_report.system_health_score,
                    "alerts_count": len(performance_report.alerts),
                    "critical_alerts": len([a for a in performance_report.alerts if a.severity == "critical"])
                },
                "logs": {
                    "health": log_report.health_indicators.get("overall_health", "unknown"),
                    "error_rate": log_report.statistics.error_rate,
                    "patterns_count": len(log_report.patterns),
                    "anomalies_count": len(log_report.anomalies)
                }
            }
            click.echo(json.dumps(health_data, indent=2))
        else:
            # Text output
            click.echo(f"\n{'='*60}")
            click.echo(f"SYSTEM HEALTH CHECK")
            click.echo(f"{'='*60}")
            
            # Database integrity
            db_status = "HEALTHY" if integrity_result.is_healthy else "ISSUES"
            db_color = "green" if integrity_result.is_healthy else "red"
            click.echo(f"Database Integrity: {click.style(db_status, fg=db_color)}")
            if not integrity_result.is_healthy:
                click.echo(f"  Issues found: {len(integrity_result.issues_found)}")
            
            # Storage
            storage_color = "green" if storage_report.usage.usage_percentage < 80 else "yellow" if storage_report.usage.usage_percentage < 90 else "red"
            click.echo(f"Storage Usage: {click.style(f'{storage_report.usage.usage_percentage:.1f}%', fg=storage_color)}")
            if storage_report.warnings:
                click.echo(f"  Warnings: {len(storage_report.warnings)}")
            
            # Performance
            perf_score = performance_report.system_health_score
            perf_color = "green" if perf_score >= 80 else "yellow" if perf_score >= 60 else "red"
            click.echo(f"Performance Score: {click.style(f'{perf_score:.1f}/100', fg=perf_color)}")
            if performance_report.alerts:
                click.echo(f"  Alerts: {len(performance_report.alerts)}")
            
            # Logs
            log_health = log_report.health_indicators.get("overall_health", "unknown")
            log_color = {"good": "green", "warning": "yellow", "critical": "red"}.get(log_health, "white")
            click.echo(f"Log Health: {click.style(log_health.upper(), fg=log_color)}")
            click.echo(f"  Error rate: {log_report.statistics.error_rate:.1f}%")
            
            # Overall assessment
            issues = []
            if not integrity_result.is_healthy:
                issues.append("database integrity")
            if storage_report.usage.usage_percentage > 80:
                issues.append("storage usage")
            if performance_report.system_health_score < 70:
                issues.append("performance")
            if log_health != "good":
                issues.append("log analysis")
            
            if issues:
                click.echo(f"\n{click.style('⚠ Issues detected in:', fg='yellow')} {', '.join(issues)}")
                click.echo("Run specific commands for detailed analysis and recommendations.")
            else:
                click.echo(f"\n{click.style('✓ System health is good', fg='green')}")
        
    except Exception as e:
        click.echo(f"Error running health check: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    cli()