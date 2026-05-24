
&lt;#
.SYNOPSIS
    NetOps Multi-Agent System Shutdown Script v3.0 - Django + React 版本
#&gt;

param(
    [string]$ProjectDir = "C:\Users\wangd\PycharmProjects\PythonProject\netops-agent"
)

$ErrorActionPreference = "SilentlyContinue"

function Write-ColorOutput($text, $color) {
    Write-Host $text -ForegroundColor $color
}

Write-ColorOutput "============================================================" Cyan
Write-ColorOutput "  NetOps Multi-Agent System Shutdown Script v3.0" Cyan
Write-ColorOutput "  (Django + React + FastAPI)" Cyan
Write-ColorOutput "============================================================" Cyan
Write-Host ""

# 1. Stop application processes
Write-ColorOutput "[Step 1/4] Stopping frontend processes..." Green

# Stop Node.js (React)
$nodeProcesses = Get-Process node -ErrorAction SilentlyContinue
if ($nodeProcesses) {
    $count = $nodeProcesses.Count
    $nodeProcesses | Stop-Process -Force
    Start-Sleep -Seconds 1
    Write-ColorOutput "  [OK] Node.js (React) stopped ($count processes)" Green
} else {
    Write-ColorOutput "  [INFO] No Node.js processes found" Gray
}

# Stop Python processes
Write-ColorOutput "[Step 2/4] Stopping backend processes..." Green
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    $count = $pythonProcesses.Count
    $pythonProcesses | Stop-Process -Force
    Start-Sleep -Seconds 2
    Write-ColorOutput "  [OK] Python processes stopped ($count processes)" Green
} else {
    Write-ColorOutput "  [INFO] No Python processes found" Gray
}

# Stop Docker middleware
Write-ColorOutput "[Step 3/4] Stopping Docker middleware..." Green

$deploymentDir = Join-Path $ProjectDir "deployment"
$composeFile = Join-Path $deploymentDir "docker-compose.yml"

if (Test-Path $composeFile) {
    try {
        Set-Location $deploymentDir
        docker-compose -f $composeFile down
        Set-Location $ProjectDir
        Write-ColorOutput "  [OK] Docker containers stopped" Green
    } catch {
        Write-ColorOutput "  [ERROR] Failed to stop Docker containers" Red
    }
} else {
    Write-ColorOutput "  [INFO] Docker Compose file not found" Gray
}

# Verify ports
Write-ColorOutput "[Step 4/4] Verifying port release..." Green

$ports = @(3000, 8000, 8001, 5672, 6379, 15672, 5432, 9000, 9001, 6333)
$allReleased = $true

foreach ($port in $ports) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        Write-ColorOutput "  [WARNING] Port $port still in use" Red
        $allReleased = $false
    } else {
        Write-ColorOutput "  [OK] Port $port released" Green
    }
}

Write-Host ""
Write-ColorOutput "============================================================" Cyan
if ($allReleased) {
    Write-ColorOutput "  All Services Stopped Successfully!" Green
} else {
    Write-ColorOutput "  Services Stopped with Warnings" Yellow
}
Write-ColorOutput "============================================================" Cyan
Write-Host ""
Write-ColorOutput "Tip: Use .\start_all.ps1 to restart all services" Magenta
Write-Host ""
