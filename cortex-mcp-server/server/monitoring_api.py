"""
Monitoring API endpoints for the cortex mcp system.

This module adds monitoring and maintenance endpoints to the REST API,
providing web-based access to the monitoring tools.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from utils.database_integrity import run_integrity_check
from utils.storage_monitor import generate_storage_report, run_automated_cleanup
from utils.performance_monitor import generate_performance_report
from utils.log_analyzer import analyze_logs


class MonitoringResponse(BaseModel):
    """Base response model for monitoring endpoints."""
    timestamp: datetime
    status: str
    data: Dict[str, Any]


class HealthCheckResponse(BaseModel):
    """Health check response model."""
    timestamp: datetime
    database_integrity: Dict[str, Any]
    storage: Dict[str, Any]
    performance: Dict[str, Any]
    logs: Dict[str, Any]
    overall_status: str


def create_monitoring_router(rest_api_server) -> APIRouter:
    """Create monitoring API router with access to the REST API server instance."""
    router = APIRouter(prefix="/monitoring", tags=["monitoring"])
    
    @router.get("/", response_class=HTMLResponse)
    async def monitoring_dashboard():
        """Serve the monitoring dashboard HTML."""
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cortex MCP - Monitoring Dashboard</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f5f5f5;
                }
                .container {
                    max-width: 1200px;
                    margin: 0 auto;
                }
                .header {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 30px;
                    border-radius: 10px;
                    margin-bottom: 30px;
                    text-align: center;
                }
                .header h1 {
                    margin: 0;
                    font-size: 2.5em;
                }
                .header p {
                    margin: 10px 0 0 0;
                    opacity: 0.9;
                }
                .grid {
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .card {
                    background: white;
                    border-radius: 10px;
                    padding: 25px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    transition: transform 0.2s;
                }
                .card:hover {
                    transform: translateY(-2px);
                }
                .card h3 {
                    margin: 0 0 15px 0;
                    color: #333;
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .status-indicator {
                    width: 12px;
                    height: 12px;
                    border-radius: 50%;
                    display: inline-block;
                }
                .status-healthy { background-color: #4CAF50; }
                .status-warning { background-color: #FF9800; }
                .status-critical { background-color: #F44336; }
                .status-unknown { background-color: #9E9E9E; }
                .metric {
                    display: flex;
                    justify-content: space-between;
                    margin: 10px 0;
                    padding: 8px 0;
                    border-bottom: 1px solid #eee;
                }
                .metric:last-child {
                    border-bottom: none;
                }
                .metric-label {
                    color: #666;
                }
                .metric-value {
                    font-weight: bold;
                    color: #333;
                }
                .btn {
                    background: #667eea;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                    cursor: pointer;
                    margin: 5px;
                    transition: background 0.2s;
                }
                .btn:hover {
                    background: #5a6fd8;
                }
                .btn-danger {
                    background: #F44336;
                }
                .btn-danger:hover {
                    background: #d32f2f;
                }
                .loading {
                    text-align: center;
                    padding: 20px;
                    color: #666;
                }
                .error {
                    background: #ffebee;
                    color: #c62828;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 10px 0;
                }
                .success {
                    background: #e8f5e8;
                    color: #2e7d32;
                    padding: 15px;
                    border-radius: 5px;
                    margin: 10px 0;
                }
                .actions {
                    text-align: center;
                    margin: 30px 0;
                }
                .log-entry {
                    font-family: monospace;
                    font-size: 12px;
                    padding: 5px;
                    margin: 2px 0;
                    border-radius: 3px;
                }
                .log-error { background: #ffebee; }
                .log-warning { background: #fff3e0; }
                .log-info { background: #e3f2fd; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🧠 Cortex MCP</h1>
                    <p>Monitoring Dashboard</p>
                </div>
                
                <div class="actions">
                    <button class="btn" onclick="refreshAll()">🔄 Refresh All</button>
                    <button class="btn" onclick="runHealthCheck()">🏥 Health Check</button>
                    <button class="btn" onclick="runIntegrityCheck()">🔍 Integrity Check</button>
                    <button class="btn btn-danger" onclick="runCleanup()">🧹 Run Cleanup</button>
                </div>
                
                <div id="alerts"></div>
                
                <div class="grid">
                    <div class="card">
                        <h3>
                            <span class="status-indicator status-unknown" id="db-status"></span>
                            Database Health
                        </h3>
                        <div id="database-metrics">
                            <div class="loading">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h3>
                            <span class="status-indicator status-unknown" id="storage-status"></span>
                            Storage Usage
                        </h3>
                        <div id="storage-metrics">
                            <div class="loading">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h3>
                            <span class="status-indicator status-unknown" id="perf-status"></span>
                            Performance
                        </h3>
                        <div id="performance-metrics">
                            <div class="loading">Loading...</div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <h3>
                            <span class="status-indicator status-unknown" id="logs-status"></span>
                            Log Analysis
                        </h3>
                        <div id="logs-metrics">
                            <div class="loading">Loading...</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <h3>Recent Activity</h3>
                    <div id="recent-logs">
                        <div class="loading">Loading recent logs...</div>
                    </div>
                </div>
            </div>
            
            <script>
                let refreshInterval;
                
                async function fetchData(endpoint) {
                    try {
                        const response = await fetch(`/monitoring/${endpoint}`);
                        if (!response.ok) throw new Error(`HTTP ${response.status}`);
                        return await response.json();
                    } catch (error) {
                        console.error(`Error fetching ${endpoint}:`, error);
                        return { error: error.message };
                    }
                }
                
                function updateStatus(elementId, status) {
                    const element = document.getElementById(elementId);
                    element.className = `status-indicator status-${status}`;
                }
                
                function formatBytes(bytes) {
                    if (bytes === 0) return '0 B';
                    const k = 1024;
                    const sizes = ['B', 'KB', 'MB', 'GB'];
                    const i = Math.floor(Math.log(bytes) / Math.log(k));
                    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
                }
                
                function showAlert(message, type = 'info') {
                    const alertsDiv = document.getElementById('alerts');
                    const alertClass = type === 'error' ? 'error' : 'success';
                    alertsDiv.innerHTML = `<div class="${alertClass}">${message}</div>`;
                    setTimeout(() => alertsDiv.innerHTML = '', 5000);
                }
                
                async function updateDatabaseMetrics() {
                    const data = await fetchData('integrity');
                    const metricsDiv = document.getElementById('database-metrics');
                    
                    if (data.error) {
                        metricsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                        updateStatus('db-status', 'critical');
                        return;
                    }
                    
                    const isHealthy = data.data.is_healthy;
                    updateStatus('db-status', isHealthy ? 'healthy' : 'warning');
                    
                    metricsDiv.innerHTML = `
                        <div class="metric">
                            <span class="metric-label">Status</span>
                            <span class="metric-value">${isHealthy ? '✅ Healthy' : '⚠️ Issues Found'}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Checks</span>
                            <span class="metric-value">${data.data.total_checks}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Issues Found</span>
                            <span class="metric-value">${data.data.issues_found}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Duration</span>
                            <span class="metric-value">${data.data.duration_seconds.toFixed(2)}s</span>
                        </div>
                    `;
                }
                
                async function updateStorageMetrics() {
                    const data = await fetchData('storage');
                    const metricsDiv = document.getElementById('storage-metrics');
                    
                    if (data.error) {
                        metricsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                        updateStatus('storage-status', 'critical');
                        return;
                    }
                    
                    const usage = data.data.usage;
                    const status = usage.usage_percentage > 80 ? 'warning' : 'healthy';
                    updateStatus('storage-status', status);
                    
                    metricsDiv.innerHTML = `
                        <div class="metric">
                            <span class="metric-label">Database Size</span>
                            <span class="metric-value">${usage.database_size_mb.toFixed(1)} MB</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Log Files</span>
                            <span class="metric-value">${usage.log_files_size_mb.toFixed(1)} MB</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Used</span>
                            <span class="metric-value">${usage.total_size_mb.toFixed(1)} MB</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Usage</span>
                            <span class="metric-value">${usage.usage_percentage.toFixed(1)}%</span>
                        </div>
                    `;
                }
                
                async function updatePerformanceMetrics() {
                    const data = await fetchData('performance');
                    const metricsDiv = document.getElementById('performance-metrics');
                    
                    if (data.error) {
                        metricsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                        updateStatus('perf-status', 'critical');
                        return;
                    }
                    
                    const score = data.data.system_health_score;
                    const status = score >= 80 ? 'healthy' : score >= 60 ? 'warning' : 'critical';
                    updateStatus('perf-status', status);
                    
                    metricsDiv.innerHTML = `
                        <div class="metric">
                            <span class="metric-label">Health Score</span>
                            <span class="metric-value">${score.toFixed(1)}/100</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Alerts</span>
                            <span class="metric-value">${data.data.alerts.length}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Stats Available</span>
                            <span class="metric-value">${data.data.stats.length}</span>
                        </div>
                    `;
                }
                
                async function updateLogsMetrics() {
                    const data = await fetchData('logs');
                    const metricsDiv = document.getElementById('logs-metrics');
                    
                    if (data.error) {
                        metricsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                        updateStatus('logs-status', 'critical');
                        return;
                    }
                    
                    const health = data.data.health_indicators.overall_health;
                    const status = health === 'good' ? 'healthy' : health === 'warning' ? 'warning' : 'critical';
                    updateStatus('logs-status', status);
                    
                    metricsDiv.innerHTML = `
                        <div class="metric">
                            <span class="metric-label">Health</span>
                            <span class="metric-value">${health.toUpperCase()}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Total Entries</span>
                            <span class="metric-value">${data.data.statistics.total_entries}</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Error Rate</span>
                            <span class="metric-value">${data.data.statistics.error_rate.toFixed(1)}%</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Patterns</span>
                            <span class="metric-value">${data.data.patterns.length}</span>
                        </div>
                    `;
                }
                
                async function refreshAll() {
                    showAlert('Refreshing all metrics...', 'info');
                    await Promise.all([
                        updateDatabaseMetrics(),
                        updateStorageMetrics(),
                        updatePerformanceMetrics(),
                        updateLogsMetrics()
                    ]);
                    showAlert('All metrics updated successfully!', 'success');
                }
                
                async function runHealthCheck() {
                    showAlert('Running comprehensive health check...', 'info');
                    const data = await fetchData('health');
                    if (data.error) {
                        showAlert(`Health check failed: ${data.error}`, 'error');
                    } else {
                        showAlert(`Health check completed - Status: ${data.overall_status}`, 'success');
                        await refreshAll();
                    }
                }
                
                async function runIntegrityCheck() {
                    showAlert('Running database integrity check...', 'info');
                    const data = await fetchData('integrity/run');
                    if (data.error) {
                        showAlert(`Integrity check failed: ${data.error}`, 'error');
                    } else {
                        const issues = data.data.issues_found;
                        showAlert(`Integrity check completed - ${issues} issues found`, issues > 0 ? 'warning' : 'success');
                        await updateDatabaseMetrics();
                    }
                }
                
                async function runCleanup() {
                    if (!confirm('Are you sure you want to run automated cleanup? This will delete old data.')) {
                        return;
                    }
                    showAlert('Running automated cleanup...', 'info');
                    const data = await fetchData('storage/cleanup');
                    if (data.error) {
                        showAlert(`Cleanup failed: ${data.error}`, 'error');
                    } else {
                        const freed = data.data.total_mb_freed || 0;
                        showAlert(`Cleanup completed - ${freed.toFixed(1)} MB freed`, 'success');
                        await updateStorageMetrics();
                    }
                }
                
                // Initialize dashboard
                document.addEventListener('DOMContentLoaded', function() {
                    refreshAll();
                    // Auto-refresh every 30 seconds
                    refreshInterval = setInterval(refreshAll, 30000);
                });
                
                // Cleanup on page unload
                window.addEventListener('beforeunload', function() {
                    if (refreshInterval) {
                        clearInterval(refreshInterval);
                    }
                });
            </script>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    
    @router.get("/health", response_model=MonitoringResponse)
    async def comprehensive_health_check(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(rest_api_server.security)
    ):
        """Run comprehensive system health check."""
        try:
            # Run all health checks
            integrity_result = await run_integrity_check(rest_api_server.db_manager)
            storage_report = await generate_storage_report(rest_api_server.db_manager)
            performance_report = generate_performance_report()
            log_report = analyze_logs()
            
            # Determine overall status
            issues = []
            if not integrity_result.is_healthy:
                issues.append("database integrity")
            if storage_report.usage.usage_percentage > 80:
                issues.append("storage usage")
            if performance_report.system_health_score < 70:
                issues.append("performance")
            if log_report and log_report.health_indicators.get("overall_health") != "good":
                issues.append("log analysis")
            
            overall_status = "critical" if len(issues) > 2 else "warning" if issues else "healthy"
            
            return MonitoringResponse(
                timestamp=datetime.now(),
                status=overall_status,
                data={
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
                        "health": log_report.health_indicators.get("overall_health", "unknown") if log_report else "unknown",
                        "error_rate": log_report.statistics.error_rate if log_report else 0,
                        "patterns_count": len(log_report.patterns) if log_report else 0,
                        "anomalies_count": len(log_report.anomalies) if log_report else 0
                    },
                    "issues": issues,
                    "overall_status": overall_status
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")
    
    @router.get("/integrity", response_model=MonitoringResponse)
    async def get_integrity_status(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(rest_api_server.security)
    ):
        """Get current database integrity status."""
        try:
            result = await run_integrity_check(rest_api_server.db_manager)
            return MonitoringResponse(
                timestamp=datetime.now(),
                status="healthy" if result.is_healthy else "warning",
                data={
                    "is_healthy": result.is_healthy,
                    "total_checks": result.total_checks,
                    "issues_found": len(result.issues_found),
                    "duration_seconds": result.duration_seconds,
                    "summary": result.summary,
                    "issues": [
                        {
                            "type": issue.issue_type.value,
                            "table": issue.table_name,
                            "severity": issue.severity,
                            "description": issue.description,
                            "auto_fixable": issue.auto_fixable
                        }
                        for issue in result.issues_found
                    ]
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Integrity check failed: {str(e)}")
    
    @router.post("/integrity/run", response_model=MonitoringResponse)
    async def run_integrity_check_endpoint(
        auto_fix: bool = Query(False, description="Automatically fix issues that can be safely repaired"),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(rest_api_server.security)
    ):
        """Run database integrity check with optional auto-fix."""
        try:
            result = await run_integrity_check(rest_api_server.db_manager, auto_fix=auto_fix)
            return MonitoringResponse(
                timestamp=datetime.now(),
                status="healthy" if result.is_healthy else "warning",
                data={
                    "is_healthy": result.is_healthy,
                    "total_checks": result.total_checks,
                    "issues_found": len(result.issues_found),
                    "duration_seconds": result.duration_seconds,
                    "auto_fix_enabled": auto_fix,
                    "summary": result.summary
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Integrity check failed: {str(e)}")
    
    @router.get("/storage", response_model=MonitoringResponse)
    async def get_storage_status(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(rest_api_server.security)
    ):
        """Get current storage usage status."""
        try:
            report = await generate_storage_report(rest_api_server.db_manager)
            return MonitoringResponse(
                timestamp=datetime.now(),
                status="warning" if report.usage.usage_percentage > 80 else "healthy",
                data={
                    "usage": report.usage.to_dict(),
                    "conversation_stats": report.conversation_stats,
                    "project_stats": report.project_stats,
                    "cleanup_recommendations": report.cleanup_recommendations,
                    "warnings": report.warnings
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Storage check failed: {str(e)}")
    
    @router.post("/storage/cleanup", response_model=MonitoringResponse)
    async def run_storage_cleanup(
        dry_run: bool = Query(False, description="Simulate cleanup without actually deleting data"),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(rest_api_server.security)
    ):
        """Run automated storage cleanup."""
        try:
            results = await run_automated_cleanup(rest_api_server.db_manager, dry_run=dry_run)
            total_mb_freed = sum(r.mb_freed for r in results if r.success)
            total_items = sum(r.items_processed for r in results if r.success)
            
            return MonitoringResponse(
                timestamp=datetime.now(),
                status="success",
                data={
                    "total_mb_freed": total_mb_freed,
                    "total_items_processed": total_items,
                    "dry_run": dry_run,
                    "results": [
                        {
                            "action": result.action.value,
                            "success": result.success,
                            "items_processed": result.items_processed,
                            "mb_freed": result.mb_freed,
                            "duration_seconds": result.duration_seconds,
                            "error_message": result.error_message
                        }
                        for result in results
                    ]
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Storage cleanup failed: {str(e)}")
    
    @router.get("/performance", response_model=MonitoringResponse)
    async def get_performance_status(
        hours: int = Query(24, description="Number of hours to analyze"),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(rest_api_server.security)
    ):
        """Get current performance status."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            time_range = {"start": start_time, "end": end_time}
            
            report = generate_performance_report(time_range)
            
            return MonitoringResponse(
                timestamp=datetime.now(),
                status="healthy" if report.system_health_score >= 80 else "warning" if report.system_health_score >= 60 else "critical",
                data={
                    "system_health_score": report.system_health_score,
                    "time_range_hours": hours,
                    "stats": [
                        {
                            "operation": stat.operation,
                            "metric_type": stat.metric_type.value,
                            "count": stat.count,
                            "mean_value": stat.mean_value,
                            "p95_value": stat.p95_value,
                            "unit": stat.unit
                        }
                        for stat in report.stats
                    ],
                    "alerts": [
                        {
                            "severity": alert.severity,
                            "operation": alert.operation,
                            "description": alert.description,
                            "timestamp": alert.timestamp.isoformat()
                        }
                        for alert in report.alerts
                    ],
                    "recommendations": report.recommendations
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Performance check failed: {str(e)}")
    
    @router.get("/logs", response_model=MonitoringResponse)
    async def get_logs_status(
        hours: int = Query(24, description="Number of hours to analyze"),
        max_entries: int = Query(1000, description="Maximum log entries to analyze"),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(rest_api_server.security)
    ):
        """Get current log analysis status."""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            time_range = {"start": start_time, "end": end_time}
            
            report = analyze_logs(time_range=time_range, max_entries=max_entries)
            
            if not report:
                return MonitoringResponse(
                    timestamp=datetime.now(),
                    status="unknown",
                    data={"error": "No log data available"}
                )
            
            health = report.health_indicators.get("overall_health", "unknown")
            status = "healthy" if health == "good" else "warning" if health == "warning" else "critical"
            
            return MonitoringResponse(
                timestamp=datetime.now(),
                status=status,
                data={
                    "health_indicators": report.health_indicators,
                    "statistics": {
                        "total_entries": report.statistics.total_entries,
                        "error_rate": report.statistics.error_rate,
                        "warning_rate": report.statistics.warning_rate,
                        "entries_by_level": report.statistics.entries_by_level
                    },
                    "patterns": [
                        {
                            "type": pattern.pattern_type.value,
                            "count": pattern.count,
                            "severity": pattern.severity,
                            "description": pattern.description
                        }
                        for pattern in report.patterns
                    ],
                    "anomalies": report.anomalies,
                    "recommendations": report.recommendations,
                    "time_range_hours": hours
                }
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Log analysis failed: {str(e)}")
    
    return router