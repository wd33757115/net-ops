# Production: start full Docker Compose stack
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$UseSupervisorV1,
    [int]$WaitSeconds = 45
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NetOps Production - Start" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Set-Location $ProjectRoot
$composeFile = Join-Path $ProjectRoot "deployment\docker-compose.yml"

if ($UseSupervisorV1) {
    $env:USE_SUPERVISOR_V2 = "false"
} else {
    $env:USE_SUPERVISOR_V2 = "true"
}

Write-Step ("Docker compose up USE_SUPERVISOR_V2=" + $env:USE_SUPERVISOR_V2)
docker compose -f $composeFile up -d
Write-Ok "Containers started"

Write-Step ("Wait " + $WaitSeconds + " seconds")
Start-Sleep -Seconds $WaitSeconds

Write-Step "Django migrate"
docker compose -f $composeFile exec -T django python manage.py migrate --noinput 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [WARN] migrate may need retry when containers are ready" -ForegroundColor Yellow
} else {
    Write-Ok "migrate done"
}

Write-Step "Container status"
docker compose -f $composeFile ps

Write-Host ""
Write-Host "  React:    http://localhost:3000" -ForegroundColor Gray
Write-Host "  Django:   http://localhost:8001" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan
