"""
Comprehensive web interface for Cross-Tool Memory Server.

This module provides a full-featured web UI that mirrors all API and CLI functionality.
"""

from fastapi import APIRouter, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional, Dict, Any
import json
from datetime import datetime

def create_web_interface_router(rest_api_server) -> APIRouter:
    """Create web interface router with access to the REST API server instance."""
    router = APIRouter(tags=["web-interface"])
    
    @router.get("/", response_class=HTMLResponse)
    async def web_dashboard():
        """Main web dashboard with all functionality."""
        return HTMLResponse(content=get_dashboard_html())
    
    @router.get("/ui", response_class=HTMLResponse)
    async def web_dashboard_alt():
        """Alternative path for web dashboard."""
        return HTMLResponse(content=get_dashboard_html())
    
    @router.get("/endpoints", response_class=HTMLResponse)
    async def api_endpoints():
        """Show all available API endpoints."""
        return HTMLResponse(content=get_endpoints_html(rest_api_server))
    
    @router.get("/api-test", response_class=HTMLResponse)
    async def api_test_page():
        """API testing interface."""
        return HTMLResponse(content=get_api_test_html())
    
    return router


def get_dashboard_html() -> str:
    """Get the main dashboard HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cross-Tool Memory - Web Interface</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: #f5f7fa; line-height: 1.6; 
        }
        .header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header p { opacity: 0.9; font-size: 1.1em; }
        .nav-tabs { 
            display: flex; background: white; border-radius: 10px; 
            margin: 20px 0; overflow: hidden; box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        .nav-tab { 
            flex: 1; padding: 15px 20px; background: white; border: none; 
            cursor: pointer; font-size: 16px; transition: all 0.3s; 
        }
        .nav-tab.active { background: #667eea; color: white; }
        .nav-tab:hover:not(.active) { background: #f8f9fa; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .card { 
            background: white; border-radius: 10px; padding: 25px; 
            margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        .form-group { margin-bottom: 20px; }
        .form-group label { 
            display: block; margin-bottom: 5px; font-weight: 600; color: #333; 
        }
        .form-control { 
            width: 100%; padding: 12px; border: 2px solid #e1e5e9; 
            border-radius: 6px; font-size: 14px; transition: border-color 0.3s; 
        }
        .form-control:focus { 
            outline: none; border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); 
        }
        .btn { 
            padding: 12px 24px; border: none; border-radius: 6px; 
            cursor: pointer; font-size: 14px; font-weight: 600; 
            transition: all 0.3s; text-decoration: none; display: inline-block; 
        }
        .btn-primary { background: #667eea; color: white; }
        .btn-primary:hover { background: #5a6fd8; transform: translateY(-1px); }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }
        .result-box { 
            background: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; 
            padding: 15px; margin-top: 15px; font-family: monospace; font-size: 13px; 
            max-height: 300px; overflow-y: auto; 
        }
        .success { background: #d4edda; border-color: #c3e6cb; color: #155724; }
        .error { background: #f8d7da; border-color: #f5c6cb; color: #721c24; }
        .memory-item { 
            border: 1px solid #e9ecef; border-radius: 6px; padding: 15px; 
            margin-bottom: 15px; background: white; 
        }
        .memory-meta { 
            font-size: 12px; color: #6c757d; margin-bottom: 10px; 
            display: flex; justify-content: space-between; 
        }
        .memory-content { margin-bottom: 10px; }
        .memory-actions { display: flex; gap: 10px; }
        .loading { text-align: center; padding: 40px; color: #6c757d; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat-card { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; padding: 20px; border-radius: 10px; text-align: center; 
        }
        .stat-number { font-size: 2em; font-weight: bold; margin-bottom: 5px; }
        .stat-label { opacity: 0.9; }
        textarea.form-control { min-height: 100px; resize: vertical; }
        .search-filters { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; margin-bottom: 20px; 
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="container">
            <h1>🧠 Cross-Tool Memory</h1>
            <p>Comprehensive Web Interface - Manage memories, projects, and system settings</p>
        </div>
    </div>
    
    <div class="container">
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="showTab('dashboard')">📊 Dashboard</button>
            <button class="nav-tab" onclick="showTab('memories')">🧠 Memories</button>
            <button class="nav-tab" onclick="showTab('projects')">📁 Projects</button>
            <button class="nav-tab" onclick="showTab('search')">🔍 Search</button>
            <button class="nav-tab" onclick="showTab('settings')">⚙️ Settings</button>
            <button class="nav-tab" onclick="showTab('monitoring')">📈 Monitoring</button>
            <button class="nav-tab" onclick="showTab('api')">🔧 API Test</button>
            <button class="nav-tab" onclick="showTab('endpoints')">🔗 All Endpoints</button>
        </div>
        
        <!-- Dashboard Tab -->
        <div id="dashboard" class="tab-content active">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-number" id="total-memories">-</div>
                    <div class="stat-label">Total Memories</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="total-projects">-</div>
                    <div class="stat-label">Projects</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="system-health">-</div>
                    <div class="stat-label">System Health</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="storage-usage">-</div>
                    <div class="stat-label">Storage Usage</div>
                </div>
            </div>
            
            <div class="grid">
                <div class="card">
                    <h3>Recent Memories</h3>
                    <div id="recent-memories" class="loading">Loading recent memories...</div>
                </div>
                <div class="card">
                    <h3>Quick Actions</h3>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <button class="btn btn-primary" onclick="showTab('memories')">Add New Memory</button>
                        <button class="btn btn-success" onclick="showTab('projects')">Create Project</button>
                        <button class="btn btn-secondary" onclick="runHealthCheck()">Run Health Check</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Memories Tab -->
        <div id="memories" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h3>Add New Memory</h3>
                    <form id="add-memory-form">
                        <div class="form-group">
                            <label>Tool Name</label>
                            <input type="text" class="form-control" id="memory-tool" placeholder="e.g., cursor, claude, kiro" required>
                        </div>
                        <div class="form-group">
                            <label>Project</label>
                            <select class="form-control" id="memory-project" required>
                                <option value="">Select a project...</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Content</label>
                            <textarea class="form-control" id="memory-content" placeholder="Enter the memory content..." required></textarea>
                        </div>
                        <div class="form-group">
                            <label>Tags (comma-separated)</label>
                            <input type="text" class="form-control" id="memory-tags" placeholder="e.g., important, bug-fix, feature">
                        </div>
                        <div class="form-group">
                            <label>Metadata (JSON)</label>
                            <textarea class="form-control" id="memory-metadata" placeholder='{"priority": "high", "type": "implementation"}'></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary">Store Memory</button>
                    </form>
                    <div id="add-memory-result" class="result-box" style="display: none;"></div>
                </div>
                
                <div class="card">
                    <h3>Memory Management</h3>
                    <div class="form-group">
                        <label>Filter by Tool</label>
                        <select class="form-control" id="filter-tool" onchange="loadMemories()">
                            <option value="">All Tools</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Filter by Project</label>
                        <select class="form-control" id="filter-project" onchange="loadMemories()">
                            <option value="">All Projects</option>
                        </select>
                    </div>
                    <button class="btn btn-secondary" onclick="loadMemories()">Refresh Memories</button>
                </div>
            </div>
            
            <div class="card">
                <h3>All Memories</h3>
                <div id="memories-list" class="loading">Loading memories...</div>
            </div>
        </div>
        
        <!-- Projects Tab -->
        <div id="projects" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h3>Create New Project</h3>
                    <form id="create-project-form">
                        <div class="form-group">
                            <label>Project Name</label>
                            <input type="text" class="form-control" id="project-name" placeholder="Enter project name" required>
                        </div>
                        <div class="form-group">
                            <label>Description</label>
                            <textarea class="form-control" id="project-description" placeholder="Project description (optional)"></textarea>
                        </div>
                        <div class="form-group">
                            <label>Path (optional)</label>
                            <input type="text" class="form-control" id="project-path" placeholder="/path/to/project">
                        </div>
                        <button type="submit" class="btn btn-primary">Create Project</button>
                    </form>
                    <div id="create-project-result" class="result-box" style="display: none;"></div>
                </div>
                
                <div class="card">
                    <h3>Project Statistics</h3>
                    <div id="project-stats" class="loading">Loading project statistics...</div>
                </div>
            </div>
            
            <div class="card">
                <h3>All Projects</h3>
                <div id="projects-list" class="loading">Loading projects...</div>
            </div>
        </div>
        
        <!-- Search Tab -->
        <div id="search" class="tab-content">
            <div class="card">
                <h3>Search Memories</h3>
                <form id="search-form">
                    <div class="search-filters">
                        <div class="form-group">
                            <label>Search Query</label>
                            <input type="text" class="form-control" id="search-query" placeholder="Enter search terms..." required>
                        </div>
                        <div class="form-group">
                            <label>Search Type</label>
                            <select class="form-control" id="search-type">
                                <option value="hybrid">Hybrid (Semantic + Keyword)</option>
                                <option value="semantic">Semantic Search</option>
                                <option value="keyword">Keyword Search</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Project Filter</label>
                            <select class="form-control" id="search-project">
                                <option value="">All Projects</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Tool Filter</label>
                            <select class="form-control" id="search-tool">
                                <option value="">All Tools</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Max Results</label>
                            <input type="number" class="form-control" id="search-limit" value="20" min="1" max="100">
                        </div>
                    </div>
                    <button type="submit" class="btn btn-primary">Search</button>
                </form>
                <div id="search-results" class="result-box" style="display: none;"></div>
            </div>
        </div>
        
        <!-- Settings Tab -->
        <div id="settings" class="tab-content">
            <div class="grid">
                <div class="card">
                    <h3>System Preferences</h3>
                    <div id="preferences-list" class="loading">Loading preferences...</div>
                    <hr style="margin: 20px 0;">
                    <h4>Add/Update Preference</h4>
                    <form id="preference-form">
                        <div class="form-group">
                            <label>Key</label>
                            <input type="text" class="form-control" id="pref-key" placeholder="preference.key" required>
                        </div>
                        <div class="form-group">
                            <label>Value</label>
                            <textarea class="form-control" id="pref-value" placeholder="Preference value" required></textarea>
                        </div>
                        <button type="submit" class="btn btn-primary">Save Preference</button>
                    </form>
                    <div id="preference-result" class="result-box" style="display: none;"></div>
                </div>
                
                <div class="card">
                    <h3>Database Management</h3>
                    <div style="display: flex; flex-direction: column; gap: 10px;">
                        <button class="btn btn-secondary" onclick="runIntegrityCheck()">Run Integrity Check</button>
                        <button class="btn btn-secondary" onclick="runStorageCleanup()">Run Storage Cleanup</button>
                        <button class="btn btn-danger" onclick="exportData()">Export All Data</button>
                    </div>
                    <div id="db-management-result" class="result-box" style="display: none;"></div>
                </div>
            </div>
        </div>
        
        <!-- Monitoring Tab -->
        <div id="monitoring" class="tab-content">
            <div class="card">
                <h3>System Monitoring</h3>
                <p>For detailed monitoring, visit the <a href="/monitoring/" target="_blank">dedicated monitoring dashboard</a>.</p>
                <div style="display: flex; gap: 10px; margin: 20px 0;">
                    <button class="btn btn-primary" onclick="loadMonitoringData()">Refresh Status</button>
                    <button class="btn btn-secondary" onclick="window.open('/monitoring/', '_blank')">Open Full Dashboard</button>
                </div>
                <div id="monitoring-summary" class="loading">Loading monitoring data...</div>
            </div>
        </div>
        
        <!-- API Test Tab -->
        <div id="api" class="tab-content">
            <div class="card">
                <h3>API Testing Interface</h3>
                <p>Test API endpoints directly from the web interface.</p>
                <div class="form-group">
                    <label>HTTP Method</label>
                    <select class="form-control" id="api-method">
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="DELETE">DELETE</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Endpoint</label>
                    <input type="text" class="form-control" id="api-endpoint" placeholder="/health" value="/health">
                </div>
                <div class="form-group">
                    <label>Request Body (JSON)</label>
                    <textarea class="form-control" id="api-body" placeholder='{"key": "value"}'></textarea>
                </div>
                <button class="btn btn-primary" onclick="testApiEndpoint()">Send Request</button>
                <div id="api-result" class="result-box" style="display: none;"></div>
            </div>
        </div>
        
        <!-- All Endpoints Tab -->
        <div id="endpoints" class="tab-content">
            <div class="card">
                <h3>All Available API Endpoints</h3>
                <p>Complete list of all REST API endpoints with descriptions and quick access links.</p>
                <div id="endpoints-list" class="loading">Loading endpoints...</div>
            </div>
        </div>
    </div>
    
    <script>
        // Global variables
        let projects = [];
        let memories = [];
        
        // Tab management
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.nav-tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');
            
            // Load tab-specific data
            switch(tabName) {
                case 'dashboard':
                    loadDashboard();
                    break;
                case 'memories':
                    loadMemories();
                    loadProjects();
                    break;
                case 'projects':
                    loadProjects();
                    break;
                case 'search':
                    loadProjects();
                    break;
                case 'settings':
                    loadPreferences();
                    break;
                case 'monitoring':
                    loadMonitoringData();
                    break;
                case 'endpoints':
                    loadEndpoints();
                    break;
            }
        }
        
        // API helper functions
        async function apiCall(method, endpoint, data = null) {
            const options = {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                }
            };
            
            if (data) {
                options.body = JSON.stringify(data);
            }
            
            try {
                const response = await fetch(endpoint, options);
                const result = await response.json();
                return { success: response.ok, data: result, status: response.status };
            } catch (error) {
                return { success: false, error: error.message };
            }
        }
        
        // Dashboard functions
        async function loadDashboard() {
            try {
                // Load basic stats
                const [healthResult, projectsResult] = await Promise.all([
                    apiCall('GET', '/health'),
                    apiCall('GET', '/projects')
                ]);
                
                if (healthResult.success) {
                    document.getElementById('system-health').textContent = 
                        healthResult.data.status === 'healthy' ? '✅' : '⚠️';
                }
                
                if (projectsResult.success) {
                    document.getElementById('total-projects').textContent = projectsResult.data.length || 0;
                }
                
                // Load monitoring data for storage
                const monitoringResult = await apiCall('GET', '/monitoring/storage');
                if (monitoringResult.success) {
                    const usage = monitoringResult.data.data.usage.usage_percentage;
                    document.getElementById('storage-usage').textContent = usage.toFixed(1) + '%';
                }
                
                loadRecentMemories();
            } catch (error) {
                console.error('Error loading dashboard:', error);
            }
        }
        
        async function loadRecentMemories() {
            const result = await apiCall('GET', '/conversations?limit=5');
            const container = document.getElementById('recent-memories');
            
            if (result.success && result.data.length > 0) {
                container.innerHTML = result.data.map(memory => `
                    <div class="memory-item">
                        <div class="memory-meta">
                            <span>${memory.tool_name}</span>
                            <span>${new Date(memory.timestamp).toLocaleDateString()}</span>
                        </div>
                        <div class="memory-content">${memory.content.substring(0, 100)}...</div>
                    </div>
                `).join('');
                
                document.getElementById('total-memories').textContent = result.data.length;
            } else {
                container.innerHTML = '<p>No recent memories found.</p>';
                document.getElementById('total-memories').textContent = '0';
            }
        }
        
        // Initialize the dashboard
        document.addEventListener('DOMContentLoaded', function() {
            loadDashboard();
        });
        
        // Form handlers will be added in the next part...
    </script>
</body>
</html>
"""


def get_api_test_html() -> str:
    """Get the API testing interface HTML."""
    return """
<!DOCTYPE html>
<html>
<head><title>API Test Interface</title></head>
<body><h1>API Test Interface</h1><p>Coming soon...</p></body>
</html>
        
        // Projects functions
        async function loadProjects() {
            const result = await apiCall('GET', '/projects');
            
            if (result.success) {
                projects = result.data;
                
                // Update project dropdowns
                const selects = ['memory-project', 'filter-project', 'search-project'];
                selects.forEach(selectId => {
                    const select = document.getElementById(selectId);
                    if (select) {
                        const currentValue = select.value;
                        select.innerHTML = '<option value="">Select a project...</option>';
                        projects.forEach(project => {
                            const option = document.createElement('option');
                            option.value = project.id;
                            option.textContent = project.name;
                            if (option.value === currentValue) option.selected = true;
                            select.appendChild(option);
                        });
                    }
                });
                
                // Update projects list
                const projectsList = document.getElementById('projects-list');
                if (projectsList) {
                    if (projects.length > 0) {
                        projectsList.innerHTML = projects.map(project => `
                            <div class="memory-item">
                                <div class="memory-meta">
                                    <span><strong>${project.name}</strong></span>
                                    <span>Created: ${new Date(project.created_at).toLocaleDateString()}</span>
                                </div>
                                <div class="memory-content">${project.description || 'No description'}</div>
                                <div class="memory-actions">
                                    <button class="btn btn-secondary" onclick="viewProject('${project.id}')">View</button>
                                    <button class="btn btn-danger" onclick="deleteProject('${project.id}')">Delete</button>
                                </div>
                            </div>
                        `).join('');
                    } else {
                        projectsList.innerHTML = '<p>No projects found. Create your first project!</p>';
                    }
                }
            }
        }
        
        // Memory functions
        async function loadMemories() {
            const toolFilter = document.getElementById('filter-tool')?.value || '';
            const projectFilter = document.getElementById('filter-project')?.value || '';
            
            let endpoint = '/conversations?limit=50';
            const params = new URLSearchParams();
            if (toolFilter) params.append('tool_name', toolFilter);
            if (projectFilter) params.append('project_id', projectFilter);
            
            if (params.toString()) {
                endpoint += '&' + params.toString();
            }
            
            const result = await apiCall('GET', endpoint);
            const container = document.getElementById('memories-list');
            
            if (result.success && result.data.length > 0) {
                memories = result.data;
                container.innerHTML = memories.map(memory => `
                    <div class="memory-item">
                        <div class="memory-meta">
                            <span><strong>${memory.tool_name}</strong> | Project: ${getProjectName(memory.project_id)}</span>
                            <span>${new Date(memory.timestamp).toLocaleString()}</span>
                        </div>
                        <div class="memory-content">${memory.content}</div>
                        <div class="memory-actions">
                            <button class="btn btn-secondary" onclick="editMemory('${memory.id}')">Edit</button>
                            <button class="btn btn-danger" onclick="deleteMemory('${memory.id}')">Delete</button>
                        </div>
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<p>No memories found.</p>';
            }
        }
        
        function getProjectName(projectId) {
            const project = projects.find(p => p.id === projectId);
            return project ? project.name : 'Unknown Project';
        }
        
        // Form handlers
        document.getElementById('add-memory-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                tool_name: document.getElementById('memory-tool').value,
                project_id: document.getElementById('memory-project').value,
                content: document.getElementById('memory-content').value,
                tags: document.getElementById('memory-tags').value.split(',').map(t => t.trim()).filter(t => t),
                metadata: {}
            };
            
            const metadataText = document.getElementById('memory-metadata').value.trim();
            if (metadataText) {
                try {
                    formData.metadata = JSON.parse(metadataText);
                } catch (error) {
                    showResult('add-memory-result', 'Invalid JSON in metadata field', 'error');
                    return;
                }
            }
            
            const result = await apiCall('POST', '/context', formData);
            
            if (result.success) {
                showResult('add-memory-result', 'Memory stored successfully!', 'success');
                document.getElementById('add-memory-form').reset();
                loadMemories();
                loadDashboard();
            } else {
                showResult('add-memory-result', `Error: ${result.data.error || result.error}`, 'error');
            }
        });
        
        document.getElementById('create-project-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                name: document.getElementById('project-name').value,
                description: document.getElementById('project-description').value,
                path: document.getElementById('project-path').value || null
            };
            
            const result = await apiCall('POST', '/projects', formData);
            
            if (result.success) {
                showResult('create-project-result', 'Project created successfully!', 'success');
                document.getElementById('create-project-form').reset();
                loadProjects();
                loadDashboard();
            } else {
                showResult('create-project-result', `Error: ${result.data.error || result.error}`, 'error');
            }
        });
        
        document.getElementById('search-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const formData = {
                query: document.getElementById('search-query').value,
                search_type: document.getElementById('search-type').value,
                project_id: document.getElementById('search-project').value || null,
                tool_name: document.getElementById('search-tool').value || null,
                limit: parseInt(document.getElementById('search-limit').value)
            };
            
            const result = await apiCall('POST', '/context/search', formData);
            
            if (result.success) {
                const results = result.data.results || [];
                const html = results.length > 0 ? 
                    results.map(item => `
                        <div class="memory-item">
                            <div class="memory-meta">
                                <span><strong>${item.tool_name}</strong> | Score: ${(item.relevance_score * 100).toFixed(1)}%</span>
                                <span>${new Date(item.timestamp).toLocaleString()}</span>
                            </div>
                            <div class="memory-content">${item.content}</div>
                        </div>
                    `).join('') : '<p>No results found.</p>';
                
                showResult('search-results', html, 'success');
            } else {
                showResult('search-results', `Error: ${result.data.error || result.error}`, 'error');
            }
        });
        
        // Utility functions
        function showResult(elementId, content, type = 'info') {
            const element = document.getElementById(elementId);
            element.innerHTML = content;
            element.className = `result-box ${type}`;
            element.style.display = 'block';
        }
        
        async function runHealthCheck() {
            const result = await apiCall('GET', '/monitoring/health');
            if (result.success) {
                alert(`System Health: ${result.data.data.overall_status}`);
                loadDashboard();
            } else {
                alert('Health check failed');
            }
        }
        
        async function runIntegrityCheck() {
            const result = await apiCall('POST', '/monitoring/integrity/run');
            if (result.success) {
                const issues = result.data.data.issues_found;
                showResult('db-management-result', 
                    `Integrity check completed. ${issues} issues found.`, 
                    issues > 0 ? 'warning' : 'success');
            } else {
                showResult('db-management-result', 'Integrity check failed', 'error');
            }
        }
        
        async function runStorageCleanup() {
            if (!confirm('Are you sure you want to run storage cleanup? This may delete old data.')) {
                return;
            }
            
            const result = await apiCall('POST', '/monitoring/storage/cleanup');
            if (result.success) {
                const freed = result.data.data.total_mb_freed || 0;
                showResult('db-management-result', 
                    `Cleanup completed. ${freed.toFixed(1)} MB freed.`, 'success');
            } else {
                showResult('db-management-result', 'Storage cleanup failed', 'error');
            }
        }
        
        async function loadPreferences() {
            const result = await apiCall('GET', '/preferences');
            const container = document.getElementById('preferences-list');
            
            if (result.success && result.data.length > 0) {
                container.innerHTML = result.data.map(pref => `
                    <div class="memory-item">
                        <div class="memory-meta">
                            <span><strong>${pref.key}</strong></span>
                            <button class="btn btn-danger" onclick="deletePref('${pref.key}')">Delete</button>
                        </div>
                        <div class="memory-content">${pref.value}</div>
                    </div>
                `).join('');
            } else {
                container.innerHTML = '<p>No preferences found.</p>';
            }
        }
        
        async function loadMonitoringData() {
            const result = await apiCall('GET', '/monitoring/health');
            const container = document.getElementById('monitoring-summary');
            
            if (result.success) {
                const data = result.data.data;
                container.innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-card">
                            <div class="stat-number">${data.database_integrity.healthy ? '✅' : '❌'}</div>
                            <div class="stat-label">Database Health</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.storage.usage_percentage.toFixed(1)}%</div>
                            <div class="stat-label">Storage Usage</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.performance.health_score}/100</div>
                            <div class="stat-label">Performance Score</div>
                        </div>
                        <div class="stat-card">
                            <div class="stat-number">${data.logs.health.toUpperCase()}</div>
                            <div class="stat-label">Log Health</div>
                        </div>
                    </div>
                `;
            } else {
                container.innerHTML = '<p>Failed to load monitoring data.</p>';
            }
        }
        
        async function testApiEndpoint() {
            const method = document.getElementById('api-method').value;
            const endpoint = document.getElementById('api-endpoint').value;
            const bodyText = document.getElementById('api-body').value.trim();
            
            let body = null;
            if (bodyText && (method === 'POST' || method === 'PUT')) {
                try {
                    body = JSON.parse(bodyText);
                } catch (error) {
                    showResult('api-result', 'Invalid JSON in request body', 'error');
                    return;
                }
            }
            
            const result = await apiCall(method, endpoint, body);
            
            const resultHtml = `
                <strong>Status:</strong> ${result.status || 'Unknown'}<br>
                <strong>Success:</strong> ${result.success}<br>
                <strong>Response:</strong><br>
                <pre>${JSON.stringify(result.data || result.error, null, 2)}</pre>
            `;
            
            showResult('api-result', resultHtml, result.success ? 'success' : 'error');
        }
        
        // Additional utility functions
        async function deleteMemory(id) {
            if (!confirm('Are you sure you want to delete this memory?')) return;
            
            const result = await apiCall('DELETE', `/conversations/${id}`);
            if (result.success) {
                loadMemories();
                loadDashboard();
            } else {
                alert('Failed to delete memory');
            }
        }
        
        async function deleteProject(id) {
            if (!confirm('Are you sure you want to delete this project? This will also delete all associated memories.')) return;
            
            const result = await apiCall('DELETE', `/projects/${id}`);
            if (result.success) {
                loadProjects();
                loadDashboard();
            } else {
                alert('Failed to delete project');
            }
        }
        
        async function deletePref(key) {
            if (!confirm(`Are you sure you want to delete preference "${key}"?`)) return;
            
            const result = await apiCall('DELETE', `/preferences/${key}`);
            if (result.success) {
                loadPreferences();
            } else {
                alert('Failed to delete preference');
            }
        }
        
        // Preference form handler
        document.getElementById('preference-form').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const key = document.getElementById('pref-key').value;
            const value = document.getElementById('pref-value').value;
            
            const result = await apiCall('POST', '/preferences', { key, value });
            
            if (result.success) {
                showResult('preference-result', 'Preference saved successfully!', 'success');
                document.getElementById('preference-form').reset();
                loadPreferences();
            } else {
                showResult('preference-result', `Error: ${result.data.error || result.error}`, 'error');
            }
        });
        
        // Load all endpoints
        async function loadEndpoints() {
            const result = await apiCall('GET', '/openapi.json');
            const container = document.getElementById('endpoints-list');
            
            if (result.success && result.data.paths) {
                const endpoints = Object.keys(result.data.paths).sort();
                const endpointsByCategory = {
                    'Core Memory': [],
                    'Projects': [],
                    'Conversations': [],
                    'Preferences': [],
                    'Monitoring': [],
                    'System': [],
                    'Other': []
                };
                
                endpoints.forEach(path => {
                    const methods = Object.keys(result.data.paths[path]);
                    const pathInfo = result.data.paths[path];
                    
                    let category = 'Other';
                    if (path.includes('/context')) category = 'Core Memory';
                    else if (path.includes('/project')) category = 'Projects';
                    else if (path.includes('/conversation')) category = 'Conversations';
                    else if (path.includes('/preference')) category = 'Preferences';
                    else if (path.includes('/monitoring')) category = 'Monitoring';
                    else if (path.includes('/health') || path.includes('/stats') || path.includes('/openapi')) category = 'System';
                    
                    methods.forEach(method => {
                        const methodInfo = pathInfo[method];
                        endpointsByCategory[category].push({
                            path: path,
                            method: method.toUpperCase(),
                            summary: methodInfo.summary || 'No description',
                            description: methodInfo.description || ''
                        });
                    });
                });
                
                let html = '';
                Object.keys(endpointsByCategory).forEach(category => {
                    if (endpointsByCategory[category].length > 0) {
                        html += `<h4 style="margin-top: 30px; color: #667eea;">${category}</h4>`;
                        endpointsByCategory[category].forEach(endpoint => {
                            const methodColor = {
                                'GET': '#28a745',
                                'POST': '#007bff', 
                                'PUT': '#ffc107',
                                'DELETE': '#dc3545'
                            }[endpoint.method] || '#6c757d';
                            
                            html += `
                                <div class="memory-item" style="margin-bottom: 15px;">
                                    <div class="memory-meta">
                                        <span style="background: ${methodColor}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold;">${endpoint.method}</span>
                                        <span style="font-family: monospace; font-weight: bold;">${endpoint.path}</span>
                                    </div>
                                    <div class="memory-content">${endpoint.summary}</div>
                                    <div class="memory-actions">
                                        <button class="btn btn-secondary" onclick="testEndpoint('${endpoint.method}', '${endpoint.path}')">Test</button>
                                        <button class="btn btn-primary" onclick="copyEndpoint('${endpoint.path}')">Copy URL</button>
                                    </div>
                                </div>
                            `;
                        });
                    }
                });
                
                container.innerHTML = html;
            } else {
                container.innerHTML = '<p>Failed to load endpoints.</p>';
            }
        }
        
        function testEndpoint(method, path) {
            showTab('api');
            document.getElementById('api-method').value = method;
            document.getElementById('api-endpoint').value = path;
        }
        
        function copyEndpoint(path) {
            const fullUrl = window.location.origin + path;
            navigator.clipboard.writeText(fullUrl).then(() => {
                alert('Endpoint URL copied to clipboard!');
            }).catch(() => {
                alert('Failed to copy URL');
            });
        }
    </script>
</body>
</html>
"""


def get_endpoints_html(rest_api_server) -> str:
    """Get the endpoints listing HTML."""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Endpoints - Cross-Tool Memory</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f7fa; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
        .endpoint-group { background: white; border-radius: 10px; padding: 25px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .endpoint-item { border: 1px solid #e9ecef; border-radius: 6px; padding: 15px; margin-bottom: 15px; }
        .method-badge { padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; color: white; }
        .method-get { background: #28a745; }
        .method-post { background: #007bff; }
        .method-put { background: #ffc107; color: #212529; }
        .method-delete { background: #dc3545; }
        .endpoint-path { font-family: monospace; font-weight: bold; margin: 0 10px; }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; margin: 2px; }
        .btn-primary { background: #667eea; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔗 API Endpoints</h1>
            <p>Complete reference of all available REST API endpoints</p>
            <a href="/" class="btn btn-secondary">← Back to Web Interface</a>
        </div>
        
        <div id="endpoints-container">
            <div class="endpoint-group">
                <h3>Loading endpoints...</h3>
            </div>
        </div>
    </div>
    
    <script>
        async function loadEndpoints() {
            try {
                const response = await fetch('/openapi.json');
                const openapi = await response.json();
                
                const endpointsByCategory = {
                    'Core Memory Operations': [],
                    'Project Management': [],
                    'Conversation Management': [],
                    'Preferences': [],
                    'Monitoring & Health': [],
                    'System Information': [],
                    'Web Interface': [],
                    'Other': []
                };
                
                Object.keys(openapi.paths).forEach(path => {
                    const methods = Object.keys(openapi.paths[path]);
                    
                    methods.forEach(method => {
                        const endpoint = openapi.paths[path][method];
                        let category = 'Other';
                        
                        if (path.includes('/context')) category = 'Core Memory Operations';
                        else if (path.includes('/project')) category = 'Project Management';
                        else if (path.includes('/conversation')) category = 'Conversation Management';
                        else if (path.includes('/preference')) category = 'Preferences';
                        else if (path.includes('/monitoring') || path.includes('/health') || path.includes('/stats')) category = 'Monitoring & Health';
                        else if (path.includes('/openapi') || path.includes('/docs') || path.includes('/redoc')) category = 'System Information';
                        else if (path.includes('/ui')) category = 'Web Interface';
                        
                        endpointsByCategory[category].push({
                            path: path,
                            method: method.toUpperCase(),
                            summary: endpoint.summary || 'No description available',
                            description: endpoint.description || '',
                            tags: endpoint.tags || []
                        });
                    });
                });
                
                let html = '';
                Object.keys(endpointsByCategory).forEach(category => {
                    if (endpointsByCategory[category].length > 0) {
                        html += `
                            <div class="endpoint-group">
                                <h3>${category}</h3>
                        `;
                        
                        endpointsByCategory[category].forEach(endpoint => {
                            html += `
                                <div class="endpoint-item">
                                    <div style="display: flex; align-items: center; margin-bottom: 10px;">
                                        <span class="method-badge method-${endpoint.method.toLowerCase()}">${endpoint.method}</span>
                                        <span class="endpoint-path">${endpoint.path}</span>
                                        <div style="margin-left: auto;">
                                            <button class="btn btn-primary" onclick="testEndpoint('${endpoint.method}', '${endpoint.path}')">Test</button>
                                            <button class="btn btn-secondary" onclick="copyUrl('${endpoint.path}')">Copy URL</button>
                                        </div>
                                    </div>
                                    <div style="color: #666; margin-bottom: 5px;">${endpoint.summary}</div>
                                    ${endpoint.description ? `<div style="color: #888; font-size: 14px;">${endpoint.description}</div>` : ''}
                                </div>
                            `;
                        });
                        
                        html += '</div>';
                    }
                });
                
                document.getElementById('endpoints-container').innerHTML = html;
            } catch (error) {
                document.getElementById('endpoints-container').innerHTML = `
                    <div class="endpoint-group">
                        <h3>Error loading endpoints</h3>
                        <p>Failed to load API endpoints: ${error.message}</p>
                    </div>
                `;
            }
        }
        
        function testEndpoint(method, path) {
            window.open(`/?tab=api&method=${method}&path=${encodeURIComponent(path)}`, '_blank');
        }
        
        function copyUrl(path) {
            const fullUrl = window.location.origin + path;
            navigator.clipboard.writeText(fullUrl).then(() => {
                alert('URL copied to clipboard!');
            }).catch(() => {
                alert('Failed to copy URL');
            });
        }
        
        // Load endpoints on page load
        document.addEventListener('DOMContentLoaded', loadEndpoints);
    </script>
</body>
</html>
"""