# Cross-Tool Memory MCP Server Installation Script for Windows
# This script sets up the Cross-Tool Memory MCP Server for local deployment on Windows

param(
    [string]$InstallDir = "$env:USERPROFILE\.cross-tool-memory",
    [int]$Port = 8000,
    [string]$Host = "127.0.0.1"
)

# Colors for output
$Red = "Red"
$Green = "Green"
$Yellow = "Yellow"
$Blue = "Blue"

function Write-Header {
    Write-Host "================================" -ForegroundColor $Blue
    Write-Host "Cross-Tool Memory MCP Server" -ForegroundColor $Blue
    Write-Host "Windows Installation Script" -ForegroundColor $Blue
    Write-Host "================================" -ForegroundColor $Blue
    Write-Host ""
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor $Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor $Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor $Red
}

function Write-Info {
    param([string]$Message)
    Write-Host "ℹ $Message" -ForegroundColor $Blue
}

function Test-Requirements {
    Write-Info "Checking system requirements..."
    
    # Check Docker
    try {
        $dockerVersion = docker --version 2>$null
        if ($dockerVersion) {
            Write-Success "Docker found: $dockerVersion"
        } else {
            throw "Docker not found"
        }
    } catch {
        Write-Error "Docker is not installed. Please install Docker Desktop first."
        Write-Host "Visit: https://docs.docker.com/desktop/windows/"
        exit 1
    }
    
    # Check Docker Compose
    try {
        $composeVersion = docker-compose --version 2>$null
        if (-not $composeVersion) {
            $composeVersion = docker compose version 2>$null
        }
        if ($composeVersion) {
            Write-Success "Docker Compose found"
        } else {
            throw "Docker Compose not found"
        }
    } catch {
        Write-Error "Docker Compose is not installed."
        Write-Host "Visit: https://docs.docker.com/compose/install/"
        exit 1
    }
    
    # Check if port is available
    $portInUse = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($portInUse) {
        Write-Warning "Port $Port is already in use. You may need to change the port in docker-compose.yml"
    } else {
        Write-Success "Port $Port is available"
    }
}

function New-Directories {
    Write-Info "Creating installation directories..."
    
    $directories = @("data", "models", "logs", "backups", "ssl")
    foreach ($dir in $directories) {
        $fullPath = Join-Path $InstallDir $dir
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
    Write-Success "Created directory structure at $InstallDir"
}

function Copy-Files {
    Write-Info "Copying configuration files..."
    
    # Copy docker-compose.yml
    if (Test-Path "docker-compose.yml") {
        Copy-Item "docker-compose.yml" $InstallDir
        Write-Success "Copied docker-compose.yml"
    }
    
    # Copy and customize config.yml
    if (Test-Path "config.yml") {
        Copy-Item "config.yml" $InstallDir
        Write-Success "Copied config.yml"
    } else {
        Write-Warning "config.yml not found, you'll need to create one"
    }
    
    # Copy nginx config if it exists
    if (Test-Path "nginx.conf") {
        Copy-Item "nginx.conf" $InstallDir
        Write-Success "Copied nginx.conf"
    }
    
    # Copy environment example
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" (Join-Path $InstallDir ".env")
        Write-Success "Copied .env.example as .env"
    }
}

function Set-Environment {
    Write-Info "Setting up environment configuration..."
    
    $envFile = Join-Path $InstallDir ".env"
    if (Test-Path $envFile) {
        $content = Get-Content $envFile
        $content = $content -replace "DATABASE_PATH=.*", "DATABASE_PATH=$InstallDir\data\memory.db"
        $content = $content -replace "MODELS_PATH=.*", "MODELS_PATH=$InstallDir\models"
        $content = $content -replace "LOG_FILE=.*", "LOG_FILE=$InstallDir\logs\memory-server.log"
        $content | Set-Content $envFile
        Write-Success "Updated environment configuration"
    }
}

function Build-Image {
    Write-Info "Building Docker image..."
    
    Push-Location $InstallDir
    try {
        docker build -t cross-tool-memory-mcp .
        Write-Success "Docker image built successfully"
    } finally {
        Pop-Location
    }
}

function New-ManagementScripts {
    Write-Info "Creating management scripts..."
    
    # Start script
    $startScript = @"
@echo off
cd /d "%~dp0"
echo Starting Cross-Tool Memory MCP Server...
docker-compose up -d
echo Server started. Check status with: docker-compose ps
echo View logs with: docker-compose logs -f
pause
"@
    $startScript | Out-File -FilePath (Join-Path $InstallDir "start.bat") -Encoding ASCII
    
    # Stop script
    $stopScript = @"
@echo off
cd /d "%~dp0"
echo Stopping Cross-Tool Memory MCP Server...
docker-compose down
echo Server stopped.
pause
"@
    $stopScript | Out-File -FilePath (Join-Path $InstallDir "stop.bat") -Encoding ASCII
    
    # Status script
    $statusScript = @"
@echo off
cd /d "%~dp0"
echo Cross-Tool Memory MCP Server Status:
docker-compose ps
echo.
echo Recent logs:
docker-compose logs --tail=20
pause
"@
    $statusScript | Out-File -FilePath (Join-Path $InstallDir "status.bat") -Encoding ASCII
    
    # Update script
    $updateScript = @"
@echo off
cd /d "%~dp0"
echo Updating Cross-Tool Memory MCP Server...
docker-compose pull
docker-compose up -d
echo Update complete.
pause
"@
    $updateScript | Out-File -FilePath (Join-Path $InstallDir "update.bat") -Encoding ASCII
    
    Write-Success "Created management scripts"
}

function Write-Completion {
    Write-Host ""
    Write-Success "Installation completed successfully!"
    Write-Host ""
    Write-Info "Installation directory: $InstallDir"
    Write-Info "To start the server:"
    Write-Host "  Double-click $InstallDir\start.bat"
    Write-Host ""
    Write-Info "To stop the server:"
    Write-Host "  Double-click $InstallDir\stop.bat"
    Write-Host ""
    Write-Info "To check status:"
    Write-Host "  Double-click $InstallDir\status.bat"
    Write-Host ""
    Write-Info "Server will be available at: http://$Host`:$Port"
    Write-Info "Health check: http://$Host`:$Port/health"
    Write-Host ""
    Write-Warning "Don't forget to:"
    Write-Host "  1. Review and customize $InstallDir\config.yml"
    Write-Host "  2. Set up your MCP client configuration"
    Write-Host "  3. Configure SSL certificates if using HTTPS"
}

# Main installation flow
function Main {
    Write-Header
    
    # Check if running as administrator
    $currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    if ($currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Warning "Running as Administrator. Consider running as a regular user."
    }
    
    Test-Requirements
    New-Directories
    Copy-Files
    Set-Environment
    Build-Image
    New-ManagementScripts
    Write-Completion
}

# Run main function
Main