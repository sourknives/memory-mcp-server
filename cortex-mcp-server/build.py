#!/usr/bin/env python3
"""
Production build script for Cortex MCP Server web interface.
Optimizes assets, minifies code, and prepares for deployment.
"""

import os
import sys
import json
import gzip
import shutil
import hashlib
import argparse
from pathlib import Path
from typing import Dict, List, Optional

try:
    import jsmin
    import cssmin
except ImportError:
    print("Warning: jsmin and cssmin not available. Install with: pip install jsmin cssmin")
    jsmin = None
    cssmin = None

class WebAssetBuilder:
    """Builds and optimizes web assets for production."""
    
    def __init__(self, source_dir: str, build_dir: str):
        self.source_dir = Path(source_dir)
        self.build_dir = Path(build_dir)
        self.manifest = {}
        
    def build(self, minify: bool = True, compress: bool = True) -> None:
        """Build optimized assets."""
        print("🚀 Starting production build...")
        
        # Create build directory
        self.build_dir.mkdir(parents=True, exist_ok=True)
        
        # Process CSS files
        self._process_css_files(minify, compress)
        
        # Process JavaScript files
        self._process_js_files(minify, compress)
        
        # Copy other static assets
        self._copy_static_assets()
        
        # Generate asset manifest
        self._generate_manifest()
        
        # Generate service worker with cache busting
        self._generate_service_worker()
        
        print("✅ Production build completed!")
        print(f"📁 Build output: {self.build_dir}")
        
    def _process_css_files(self, minify: bool, compress: bool) -> None:
        """Process and optimize CSS files."""
        print("📝 Processing CSS files...")
        
        css_dir = self.build_dir / "css"
        css_dir.mkdir(exist_ok=True)
        
        source_css = self.source_dir / "static" / "css" / "styles.css"
        if not source_css.exists():
            print(f"Warning: {source_css} not found")
            return
            
        with open(source_css, 'r', encoding='utf-8') as f:
            css_content = f.read()
        
        # Minify CSS if available
        if minify and cssmin:
            css_content = cssmin.cssmin(css_content)
            print("  ✨ CSS minified")
        
        # Generate hash for cache busting
        css_hash = hashlib.md5(css_content.encode()).hexdigest()[:8]
        css_filename = f"styles.{css_hash}.css"
        css_path = css_dir / css_filename
        
        # Write minified CSS
        with open(css_path, 'w', encoding='utf-8') as f:
            f.write(css_content)
        
        # Compress with gzip
        if compress:
            with open(css_path, 'rb') as f_in:
                with gzip.open(f"{css_path}.gz", 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print("  🗜️ CSS compressed with gzip")
        
        self.manifest['styles.css'] = f"css/{css_filename}"
        print(f"  📄 Generated: {css_filename}")
        
    def _process_js_files(self, minify: bool, compress: bool) -> None:
        """Process and optimize JavaScript files."""
        print("📝 Processing JavaScript files...")
        
        js_dir = self.build_dir / "js"
        js_dir.mkdir(exist_ok=True)
        
        js_files = [
            "utils.js",
            "api.js", 
            "ui.js",
            "app.js"
        ]
        
        for js_file in js_files:
            source_js = self.source_dir / "static" / "js" / js_file
            if not source_js.exists():
                print(f"Warning: {source_js} not found")
                continue
                
            with open(source_js, 'r', encoding='utf-8') as f:
                js_content = f.read()
            
            # Minify JavaScript if available
            if minify and jsmin:
                try:
                    js_content = jsmin.jsmin(js_content)
                    print(f"  ✨ {js_file} minified")
                except Exception as e:
                    print(f"  ⚠️ Failed to minify {js_file}: {e}")
            
            # Generate hash for cache busting
            js_hash = hashlib.md5(js_content.encode()).hexdigest()[:8]
            js_filename = f"{js_file.replace('.js', '')}.{js_hash}.js"
            js_path = js_dir / js_filename
            
            # Write processed JavaScript
            with open(js_path, 'w', encoding='utf-8') as f:
                f.write(js_content)
            
            # Compress with gzip
            if compress:
                with open(js_path, 'rb') as f_in:
                    with gzip.open(f"{js_path}.gz", 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                print(f"  🗜️ {js_file} compressed with gzip")
            
            self.manifest[js_file] = f"js/{js_filename}"
            print(f"  📄 Generated: {js_filename}")
    
    def _copy_static_assets(self) -> None:
        """Copy other static assets."""
        print("📁 Copying static assets...")
        
        # Copy service worker (will be processed separately)
        source_sw = self.source_dir / "static" / "sw.js"
        if source_sw.exists():
            shutil.copy2(source_sw, self.build_dir / "sw.js")
            print("  📄 Copied service worker")
    
    def _generate_manifest(self) -> None:
        """Generate asset manifest for cache busting."""
        manifest_path = self.build_dir / "manifest.json"
        
        with open(manifest_path, 'w') as f:
            json.dump(self.manifest, f, indent=2)
        
        print(f"  📋 Generated manifest: {len(self.manifest)} assets")
    
    def _generate_service_worker(self) -> None:
        """Generate service worker with updated asset paths."""
        print("🔧 Generating optimized service worker...")
        
        # Read original service worker
        source_sw = self.source_dir / "static" / "sw.js"
        if not source_sw.exists():
            print("Warning: Service worker not found")
            return
        
        with open(source_sw, 'r', encoding='utf-8') as f:
            sw_content = f.read()
        
        # Update cache name for new version
        import time
        cache_version = f"cortex-mcp-v{int(time.time())}"
        sw_content = sw_content.replace('cortex-mcp-v2', cache_version)
        
        # Update static assets list with hashed filenames
        static_assets = [
            '/ui',
            f"/static/{self.manifest.get('styles.css', 'css/styles.css')}",
            f"/static/{self.manifest.get('utils.js', 'js/utils.js')}",
            f"/static/{self.manifest.get('api.js', 'js/api.js')}",
            f"/static/{self.manifest.get('ui.js', 'js/ui.js')}",
            f"/static/{self.manifest.get('app.js', 'js/app.js')}"
        ]
        
        # Replace static assets array in service worker
        assets_str = json.dumps(static_assets, indent=4)
        sw_content = sw_content.replace(
            'const STATIC_ASSETS = [\n    \'/ui\',\n    \'/static/css/styles.css\',\n    \'/static/js/utils.js\',\n    \'/static/js/api.js\',\n    \'/static/js/ui.js\',\n    \'/static/js/app.js\'\n];',
            f'const STATIC_ASSETS = {assets_str};'
        )
        
        # Write optimized service worker
        sw_path = self.build_dir / "sw.js"
        with open(sw_path, 'w', encoding='utf-8') as f:
            f.write(sw_content)
        
        print("  🔧 Service worker updated with hashed assets")

def create_deployment_config() -> None:
    """Create deployment configuration files."""
    print("📋 Creating deployment configuration...")
    
    # Nginx configuration
    nginx_config = """
# Nginx configuration for Cortex MCP Server
server {
    listen 80;
    server_name localhost;
    
    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/javascript
        application/json
        application/xml+rss;
    
    # Static assets with long cache
    location /static/ {
        alias /app/static/build/;
        expires 1y;
        add_header Cache-Control "public, immutable";
        
        # Serve pre-compressed files
        location ~* \\.(?:css|js)$ {
            gzip_static on;
        }
    }
    
    # Service worker - no cache
    location /sw.js {
        alias /app/static/build/sw.js;
        expires -1;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
    }
    
    # API endpoints
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Main application
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""
    
    with open("nginx.prod.conf", 'w') as f:
        f.write(nginx_config)
    
    # Docker configuration for production
    dockerfile_prod = """
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    nginx \\
    supervisor \\
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Build optimized assets
RUN python build.py --minify --compress

# Copy nginx configuration
COPY nginx.prod.conf /etc/nginx/sites-available/default

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Expose port
EXPOSE 80

# Start supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
"""
    
    with open("Dockerfile.prod", 'w') as f:
        f.write(dockerfile_prod)
    
    # Supervisor configuration
    supervisor_config = """
[supervisord]
nodaemon=true
user=root

[program:nginx]
command=/usr/sbin/nginx -g "daemon off;"
autostart=true
autorestart=true
stderr_logfile=/var/log/nginx.err.log
stdout_logfile=/var/log/nginx.out.log

[program:cortex-mcp]
command=python -m uvicorn main:app --host 0.0.0.0 --port 8000
directory=/app
autostart=true
autorestart=true
stderr_logfile=/var/log/cortex-mcp.err.log
stdout_logfile=/var/log/cortex-mcp.out.log
"""
    
    with open("supervisord.conf", 'w') as f:
        f.write(supervisor_config)
    
    print("  📄 Created nginx.prod.conf")
    print("  📄 Created Dockerfile.prod")
    print("  📄 Created supervisord.conf")

def main():
    """Main build function."""
    parser = argparse.ArgumentParser(description="Build Cortex MCP web assets for production")
    parser.add_argument("--source", default=".", help="Source directory")
    parser.add_argument("--build", default="./static/build", help="Build output directory")
    parser.add_argument("--no-minify", action="store_true", help="Skip minification")
    parser.add_argument("--no-compress", action="store_true", help="Skip gzip compression")
    parser.add_argument("--deployment-config", action="store_true", help="Generate deployment configuration")
    
    args = parser.parse_args()
    
    # Create builder
    builder = WebAssetBuilder(args.source, args.build)
    
    # Build assets
    builder.build(
        minify=not args.no_minify,
        compress=not args.no_compress
    )
    
    # Generate deployment configuration if requested
    if args.deployment_config:
        create_deployment_config()
    
    print("\n🎉 Build completed successfully!")
    print("\nNext steps:")
    print("1. Update web_interface.py to use the manifest for asset paths")
    print("2. Configure your web server to serve static files from the build directory")
    print("3. Enable gzip compression for better performance")

if __name__ == "__main__":
    main()