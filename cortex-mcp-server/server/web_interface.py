"""
Enhanced web interface for Cortex MCP Server.

This module provides a comprehensive, modern web UI that replaces the existing
non-functional interface with a clean, responsive single-page application.
"""

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional, Dict, Any
import json
import os
from pathlib import Path
from datetime import datetime

def create_web_interface_router(rest_api_server) -> APIRouter:
    """Create enhanced web interface router with access to the REST API server instance."""
    router = APIRouter(tags=["web-interface"])
    
    # Load asset manifest for production builds
    manifest = load_asset_manifest()
    
    @router.get("/", response_class=HTMLResponse)
    async def web_dashboard_root():
        """Main web dashboard at root URL."""
        return HTMLResponse(content=get_enhanced_dashboard_html(manifest))
    
    @router.get("/ui", response_class=HTMLResponse)
    async def web_dashboard():
        """Main web dashboard with enhanced functionality."""
        return HTMLResponse(content=get_enhanced_dashboard_html(manifest))
    
    @router.get("/ui/", response_class=HTMLResponse)
    async def web_dashboard_alt():
        """Alternative path for web dashboard."""
        return HTMLResponse(content=get_enhanced_dashboard_html(manifest))
    
    return router


def load_asset_manifest() -> Dict[str, str]:
    """Load asset manifest for production builds."""
    manifest_path = Path(__file__).parent.parent / "static" / "build" / "manifest.json"
    
    if manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load asset manifest: {e}")
    
    # Return default paths for development
    return {
        "styles.css": "css/styles.css",
        "utils.js": "js/utils.js",
        "api.js": "js/api.js",
        "ui.js": "js/ui.js",
        "app.js": "js/app.js"
    }


def get_enhanced_dashboard_html(manifest: Dict[str, str]) -> str:
    """Get the enhanced dashboard HTML with modern foundation and optimized assets."""
    
    # Determine if we're in production mode
    is_production = os.getenv("CORTEX_ENV", "development") == "production"
    static_prefix = "/static/build" if is_production else "/static"
    
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cortex MCP - Enhanced Web Interface</title>
    <link rel="stylesheet" href="{static_prefix}/{manifest['styles.css']}">
    <link rel="preload" href="{static_prefix}/js/simple-app.js" as="script">
</head>
<body>
    <div id="app" class="app-layout">
        <aside class="sidebar">
            <div class="sidebar-header">
                <div class="logo-section">
                    <span class="logo-icon">🧠</span>
                    <div class="logo-text">Cortex MCP</div>
                </div>
            </div>
            <nav class="main-navigation" role="navigation" aria-label="Main navigation">
                <div class="nav-tabs" role="tablist">
                    <button class="nav-tab active" role="tab" aria-selected="true" aria-controls="dashboard-panel" data-tab="dashboard">
                        <span class="tab-icon">📊</span>
                        <span class="tab-label">Dashboard</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="memories-panel" data-tab="memories">
                        <span class="tab-icon">🧠</span>
                        <span class="tab-label">Memories</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="projects-panel" data-tab="projects">
                        <span class="tab-icon">📁</span>
                        <span class="tab-label">Projects</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="search-panel" data-tab="search">
                        <span class="tab-icon">🔍</span>
                        <span class="tab-label">Search</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="settings-panel" data-tab="settings">
                        <span class="tab-icon">⚙️</span>
                        <span class="tab-label">Settings</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="monitoring-panel" data-tab="monitoring">
                        <span class="tab-icon">📈</span>
                        <span class="tab-label">Monitoring</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="api-panel" data-tab="api">
                        <span class="tab-icon">🔧</span>
                        <span class="tab-label">API Test</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="api-keys-panel" data-tab="api-keys">
                        <span class="tab-icon">🔑</span>
                        <span class="tab-label">API Keys</span>
                    </button>
                    <button class="nav-tab" role="tab" aria-selected="false" aria-controls="database-panel" data-tab="database">
                        <span class="tab-icon">🗄️</span>
                        <span class="tab-label">Database</span>
                    </button>
                </div>
            </nav>
        </aside>

        <main class="main-content">
            <header class="content-header">
                <div class="header-info">
                    <button class="mobile-menu-toggle" onclick="CortexApp.toggleSidebar()">
                        ☰
                    </button>
                    <h1 id="page-title">Dashboard</h1>
                </div>
                <div class="header-controls">
                    <div class="connection-status" id="connection-status">
                        <span class="status-dot"></span>
                        <span class="status-text">Connected</span>
                    </div>
                    <button id="refresh-btn" class="btn btn-icon" title="Refresh Data">
                        <span class="btn-icon">🔄</span>
                    </button>
                </div>
            </header>

            <div class="content-body">
                <div class="tab-panels">
                    <!-- Dashboard Panel -->
                    <div id="dashboard-panel" class="tab-panel active" role="tabpanel" aria-labelledby="dashboard-tab">
                        <div class="metrics-grid">
                            <div class="metric-card" role="region" aria-label="Total memories">
                                <div class="metric-icon">🧠</div>
                                <div class="metric-content">
                                    <div class="metric-value" id="total-memories">-</div>
                                    <div class="metric-label">Total Memories</div>
                                </div>
                            </div>
                            <div class="metric-card" role="region" aria-label="Active projects">
                                <div class="metric-icon">📁</div>
                                <div class="metric-content">
                                    <div class="metric-value" id="total-projects">-</div>
                                    <div class="metric-label">Active Projects</div>
                                </div>
                            </div>
                            <div class="metric-card" role="region" aria-label="System health">
                                <div class="metric-icon">💚</div>
                                <div class="metric-content">
                                    <div class="metric-value" id="system-health">-</div>
                                    <div class="metric-label">System Health</div>
                                </div>
                            </div>
                            <div class="metric-card" role="region" aria-label="Storage usage">
                                <div class="metric-icon">💾</div>
                                <div class="metric-content">
                                    <div class="metric-value" id="storage-usage">-</div>
                                    <div class="metric-label">Storage Usage</div>
                                </div>
                            </div>
                        </div>

                        <div class="dashboard-grid">
                            <div class="card">
                                <div class="card-header">
                                    <h3>Recent Memories</h3>
                                    <button class="btn btn-text" onclick="CortexApp.showTab('memories')">View All</button>
                                </div>
                                <div class="card-content">
                                    <div id="recent-memories" class="loading-state">
                                        <div class="loading-spinner" aria-label="Loading recent memories"></div>
                                        <p>Loading recent memories...</p>
                                    </div>
                                    <div id="last-refresh-time" class="last-refresh"></div>
                                </div>
                            </div>

                            <div class="card">
                                <div class="card-header">
                                    <h3>Quick Actions</h3>
                                </div>
                                <div class="card-content">
                                    <div class="action-buttons">
                                        <button class="btn btn-primary" onclick="CortexApp.showTab('memories')">
                                            <span class="btn-icon">➕</span>
                                            Add Memory
                                        </button>
                                        <button class="btn btn-success" onclick="CortexApp.showTab('projects')">
                                            <span class="btn-icon">📁</span>
                                            Create Project
                                        </button>
                                        <button class="btn btn-secondary" onclick="CortexApp.refreshData()">
                                            <span class="btn-icon">🏥</span>
                                            Health Check
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                <!-- Other panels will be loaded dynamically -->
                <div id="memories-panel" class="tab-panel" role="tabpanel" aria-labelledby="memories-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading memories interface...</p>
                    </div>
                </div>

                <div id="projects-panel" class="tab-panel" role="tabpanel" aria-labelledby="projects-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading projects interface...</p>
                    </div>
                </div>

                <div id="search-panel" class="tab-panel" role="tabpanel" aria-labelledby="search-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading search interface...</p>
                    </div>
                </div>

                <div id="settings-panel" class="tab-panel" role="tabpanel" aria-labelledby="settings-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading settings interface...</p>
                    </div>
                </div>

                <div id="monitoring-panel" class="tab-panel" role="tabpanel" aria-labelledby="monitoring-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading monitoring interface...</p>
                    </div>
                </div>

                <div id="api-panel" class="tab-panel" role="tabpanel" aria-labelledby="api-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading API testing interface...</p>
                    </div>
                </div>

                <div id="api-keys-panel" class="tab-panel" role="tabpanel" aria-labelledby="api-keys-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading API key management interface...</p>
                    </div>
                </div>

                <div id="database-panel" class="tab-panel" role="tabpanel" aria-labelledby="database-tab">
                    <div class="loading-state">
                        <div class="loading-spinner"></div>
                        <p>Loading database maintenance interface...</p>
                    </div>
                </div>
            </div>
        </main>
    </div>

    <!-- Toast notifications container -->
    <div id="toast-container" class="toast-container" aria-live="polite" aria-atomic="true"></div>

    <!-- Loading overlay -->
    <div id="loading-overlay" class="loading-overlay" style="display: none;">
        <div class="loading-content">
            <div class="loading-spinner large"></div>
            <p>Processing...</p>
        </div>
    </div>

    <!-- Simple, working JavaScript -->
    <script src="{static_prefix}/js/simple-app.js" defer></script>
</body>
</html>
"""