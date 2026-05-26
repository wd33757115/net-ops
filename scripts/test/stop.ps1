# Test env: stop local processes and Docker middleware
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$KeepMiddleware
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_port_utils.ps1")

Write-ColorOutput "============================================================" "Cyan"
Write-ColorOutput "  NetOps Test Environment - Stop" "Cyan"
Write-ColorOutput "============================================================" "Cyan"

$pidFile = Join-Path $ProjectRoot ".runtime\test\pids.json"

Write-ColorOutput "[Step 1/3] Stop processes from PID file..." "Yellow"
Stop-ProjectAppProcesses -ProjectRoot $ProjectRoot
Stop-DockerAppContainers
if (Test-Path $pidFile) {
    $pids = Get-Content $pidFile -Raw | ConvertFrom-Json
    foreach ($name in $pids.PSObject.Properties.Name) {
        Stop-Process -Id ([int]$pids.$name) -Force -ErrorAction SilentlyContinue
        Write-ColorOutput "  [OK] Stopped $name" "Green"
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

Write-ColorOutput "[Step 2/3] Free ports 8000 / 8001 / 3000..." "Yellow"
Stop-ProcessesOnPorts -Ports @(8000, 8001, 3000, 3001, 3002)

if (-not $KeepMiddleware) {
    Write-ColorOutput "[Step 3/3] Stop Docker middleware..." "Yellow"
    $composeFile = Join-Path $ProjectRoot "deployment\docker-compose.middleware.yml"
    if (Test-Path $composeFile) {
        docker compose -f $composeFile down 2>$null
        Write-ColorOutput "  [OK] Middleware stopped" "Green"
    }
}

Write-ColorOutput "" "Cyan"
Write-ColorOutput "[Done] Test environment stopped" "Green"
