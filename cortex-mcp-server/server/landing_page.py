"""
Landing page for the Cortex MCP Server.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse


def create_landing_router() -> APIRouter:
    """Create landing page router."""
    router = APIRouter()
    
    @router.get("/", response_class=HTMLResponse)
    async def landing_page():
        """Landing page with links to all UI resources."""
        return HTMLResponse(content="""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cortex MCP Server</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            margin: 0; padding: 0; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            min-height: 100vh; display: flex; align-items: center; justify-content: center; 
        }
        .container { 
            background: white; border-radius: 20px; padding: 40px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.1); text-align: center; 
            max-width: 600px; width: 90%; 
        }
        .logo { font-size: 4em; margin-bottom: 20px; }
        h1 { color: #333; margin: 0 0 10px 0; font-size: 2.5em; }
        .subtitle { color: #666; margin-bottom: 40px; font-size: 1.2em; }
        .status { 
            background: #e8f5e8; color: #2e7d32; padding: 15px; 
            border-radius: 10px; margin-bottom: 30px; font-weight: bold; 
        }
        .links { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; margin-top: 30px; 
        }
        .link-card { 
            background: #f8f9fa; border: 2px solid #e9ecef; border-radius: 15px; 
            padding: 25px; text-decoration: none; color: #333; 
            transition: all 0.3s ease; display: block; 
        }
        .link-card:hover { 
            transform: translateY(-5px); box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            border-color: #667eea; 
        }
        .link-icon { font-size: 2.5em; margin-bottom: 15px; display: block; }
        .link-title { font-size: 1.3em; font-weight: bold; margin-bottom: 8px; }
        .link-desc { color: #666; font-size: 0.9em; line-height: 1.4; }
        .footer { 
            margin-top: 40px; padding-top: 20px; border-top: 1px solid #eee; 
            color: #666; font-size: 0.9em; 
        }
        .server-info { 
            background: #f8f9fa; border-radius: 10px; padding: 20px; 
            margin: 20px 0; text-align: left; 
        }
        .server-info h3 { margin: 0 0 15px 0; color: #333; }
        .info-grid { 
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
            gap: 15px; 
        }
        .info-item { 
            display: flex; justify-content: space-between; padding: 8px 0; 
            border-bottom: 1px solid #eee; 
        }
        .info-label { color: #666; font-weight: 500; }
        .info-value { color: #333; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">🧠</div>
        <h1>Cortex MCP</h1>
        <p class="subtitle">Intelligent, persistent memory storage across AI development tools</p>
        
        <div class="status">✅ Server Running - Both MCP Protocol & REST API Active</div>
        
        <div class="server-info">
            <h3>Server Information</h3>
            <div class="info-grid">
                <div class="info-item">
                    <span class="info-label">Mode:</span>
                    <span class="info-value">MCP + REST API</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Port:</span>
                    <span class="info-value">8000</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Protocol:</span>
                    <span class="info-value">HTTP + MCP</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Status:</span>
                    <span class="info-value">🟢 Healthy</span>
                </div>
            </div>
        </div>
        
        <div class="links">
            <a href="/ui" class="link-card">
                <span class="link-icon">🧠</span>
                <div class="link-title">Enhanced Web Interface</div>
                <div class="link-desc">Modern, responsive web interface for managing memories and projects</div>
            </a>
            
            <a href="/monitoring/" class="link-card">
                <span class="link-icon">📊</span>
                <div class="link-title">Monitoring Dashboard</div>
                <div class="link-desc">Real-time system health, performance metrics, and maintenance tools</div>
            </a>
            
            <a href="/docs" class="link-card">
                <span class="link-icon">📚</span>
                <div class="link-title">API Documentation</div>
                <div class="link-desc">Interactive Swagger UI for REST API endpoints and testing</div>
            </a>
            
            <a href="/redoc" class="link-card">
                <span class="link-icon">📖</span>
                <div class="link-title">API Reference</div>
                <div class="link-desc">Detailed ReDoc documentation with examples and schemas</div>
            </a>
            
            <a href="/health" class="link-card">
                <span class="link-icon">🏥</span>
                <div class="link-title">Health Check</div>
                <div class="link-desc">Quick server health status and basic system information</div>
            </a>
            
            <a href="/stats" class="link-card">
                <span class="link-icon">📈</span>
                <div class="link-title">Database Stats</div>
                <div class="link-desc">Database statistics and usage information</div>
            </a>
            
            <a href="/openapi.json" class="link-card">
                <span class="link-icon">⚙️</span>
                <div class="link-title">OpenAPI Schema</div>
                <div class="link-desc">Raw OpenAPI 3.0 specification for API integration</div>
            </a>
        </div>
        
        <div class="footer">
            <p><strong>MCP Protocol:</strong> Connect your MCP client to this server process for memory operations</p>
            <p><strong>REST API:</strong> Use HTTP endpoints for direct integration with web applications</p>
            <p>Built with FastAPI, SQLite, and comprehensive monitoring tools</p>
        </div>
    </div>
</body>
</html>""")
    
    return router