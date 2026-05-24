<#
.SYNOPSIS
    NetOps Multi-Agent System Startup Script v3.0 - Docker Only
#>

param(
    [string]$ProjectDir = "C:\Users\wangd\PycharmProjects\PythonProject\netops-agent",
    [int]$FastAPIPort = 8000,
    [int]$DjangoPort = 8001,
    [int]$ReactPort = 3000
)

$ErrorActionPreference = "Continue"

function Write-ColorOutput($text, $color) {
    Write-Host $text -ForegroundColor $color
}

function Get-ProcessOnPort($port) {
    $result = netstat -ano | Select-String ":$port "
    if ($result) {
        return $result -split '\s+' | Where-Object { $_ -match '^\d+$' } | Select-Object -Last 1
    }
    return $null
}

function Kill-ProcessOnPort($port) {
    $portPid = Get-ProcessOnPort $port
    if (-not $portPid) {
        Write-ColorOutput "    Port $port is free" Green
        return $true
    }
    Write-ColorOutput "    Port $port is used by PID $portPid, killing..." Yellow
    Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
    $newPortPid = Get-ProcessOnPort $port
    if ($newPortPid) {
        Write-ColorOutput "    Warning: Could not kill PID $newPortPid on port $port" Red
        return $false
    }
    Write-ColorOutput "    Port $port is now free" Green
    return $true
}

Write-ColorOutput "============================================================" Cyan
Write-ColorOutput "  NetOps Multi-Agent System Startup Script v3.0" Cyan
Write-ColorOutput "  (Docker Only - All services in containers)" Cyan
Write-ColorOutput "============================================================" Cyan
Write-ColorOutput "" Cyan

Write-ColorOutput "  Configuration:" Cyan
Write-ColorOutput "    - Project Directory: $ProjectDir" Gray
Write-ColorOutput "    - FastAPI Port: $FastAPIPort" Gray
Write-ColorOutput "    - Django Port: $DjangoPort" Gray
Write-ColorOutput "    - React Port: $ReactPort" Gray
Write-ColorOutput "" Cyan

Write-ColorOutput "[Step 0/5] Checking/cleaning ports..." Yellow
$portClean = $true
$portClean = $portClean -and (Kill-ProcessOnPort $FastAPIPort)
$portClean = $portClean -and (Kill-ProcessOnPort $DjangoPort)
$portClean = $portClean -and (Kill-ProcessOnPort $ReactPort)

Write-ColorOutput "[Step 1/5] Checking Docker..." Yellow
$dockerAvailable = $true
try {
    docker --version | Out-Null
} catch {
    $dockerAvailable = $false
}
if ($dockerAvailable) {
    Write-ColorOutput "  [OK] Docker is available" Green
} else {
    Write-ColorOutput "  [ERROR] Docker is not available" Red
    exit 1
}

Write-ColorOutput "[Step 2/5] Starting all services with Docker Compose..." Yellow
Write-ColorOutput "  Starting PostgreSQL, Redis, RabbitMQ, MinIO, Qdrant..." Gray
Write-ColorOutput "  Starting FastAPI, Django, React..." Gray
docker-compose -f "$ProjectDir/deployment/docker-compose.yml" up -d
Write-ColorOutput "  [OK] All Docker services started" Green

Write-ColorOutput "[Step 3/5] Waiting for services to be ready (30 seconds)..." Yellow
Start-Sleep -Seconds 30
Write-ColorOutput "  [OK] Services should be ready" Green

Write-ColorOutput "[Step 4/5] Checking service health..." Yellow
$services = @("netops-postgres", "netops-redis", "netops-rabbitmq", "netops-minio", "netops-qdrant", "netops-fastapi", "netops-django", "netops-react")
foreach ($service in $services) {
    $status = docker ps --filter "name=$service" --filter "status=running" --format "{{.Names}}"
    if ($status -eq $service) {
        Write-ColorOutput "  [OK] $service is running" Green
    } else {
        Write-ColorOutput "  [WAIT] $service is starting..." Yellow
    }
}

Write-ColorOutput "[Step 5/5] Verifying FastAPI is accessible..." Yellow
Start-Sleep -Seconds 5
$fastapiRunning = docker ps --filter "name=netops-fastapi" --filter "status=running" --format "{{.Names}}"
if ($fastapiRunning -eq "netops-fastapi") {
    Write-ColorOutput "  [OK] FastAPI container is running" Green
} else {
    Write-ColorOutput "  [WARNING] FastAPI container may still be starting" Yellow
}

Write-ColorOutput "============================================================" Cyan
Write-ColorOutput "  All Services Started via Docker!" Cyan
Write-ColorOutput "============================================================" Cyan
Write-ColorOutput "" Cyan

Write-ColorOutput "  Service URLs:" Cyan
Write-ColorOutput "  - React Frontend: http://localhost:$ReactPort" Gray
Write-ColorOutput "  - Django Backend: http://localhost:$DjangoPort" Gray
Write-ColorOutput "  - FastAPI:        http://localhost:$FastAPIPort" Gray
Write-ColorOutput "  - API Docs:       http://localhost:$FastAPIPort/docs" Gray
Write-ColorOutput "  - RabbitMQ:       http://localhost:15672 (guest/guest)" Gray
Write-ColorOutput "  - MinIO:          http://localhost:9001 (minioadmin/minioadmin)" Gray
Write-ColorOutput "" Cyan
Write-ColorOutput "  Container Status:" Cyan
docker ps --filter "name=netops-" --format "  {{.Names}}: {{.Status}}"
Write-ColorOutput "" Cyan

Write-ColorOutput "Tip: Use .\stop_all.ps1 to stop all services" Yellow
Write-ColorOutput "Tip: Use docker logs -f <container-name> to view logs" Yellow
