# Production: stop Docker Compose stack
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$RemoveVolumes
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NetOps Production - Stop" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Set-Location $ProjectRoot
$composeFile = Join-Path $ProjectRoot "deployment\docker-compose.yml"

if ($RemoveVolumes) {
    docker compose -f $composeFile down -v
} else {
    docker compose -f $composeFile down
}

Write-Host "`n[Done] Production stopped" -ForegroundColor Green
