# PostgreSQL / MinIO / Django SQLite 备份
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$OutDir = "",
    [switch]$SkipMinio,
    [switch]$SkipSqlite
)

$ErrorActionPreference = "Stop"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg) { Write-Host "  [OK] $msg" -ForegroundColor Green }

$composeBase = Join-Path $ProjectRoot "deployment\docker-compose.yml"
$composeProd = Join-Path $ProjectRoot "deployment\docker-compose.prod.yml"
$composeArgs = @("-f", $composeBase)
if (Test-Path $composeProd) {
    $composeArgs += @("-f", $composeProd)
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
if (-not $OutDir) {
    $OutDir = Join-Path $ProjectRoot "backups\$ts"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NetOps Production - Backup" -ForegroundColor Cyan
Write-Host "  Output: $OutDir" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

# 读取 .env 中的 MinIO 凭据
$envFile = Join-Path $ProjectRoot ".env"
$minioUser = "minioadmin"
$minioPass = "minioadmin"
$minioBucket = "netops-files"
if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*MINIO_ACCESS_KEY\s*=\s*(.+)$') { $minioUser = $matches[1].Trim().Trim('"').Trim("'") }
        if ($_ -match '^\s*MINIO_SECRET_KEY\s*=\s*(.+)$') { $minioPass = $matches[1].Trim().Trim('"').Trim("'") }
        if ($_ -match '^\s*MINIO_BUCKET_NAME\s*=\s*(.+)$') { $minioBucket = $matches[1].Trim().Trim('"').Trim("'") }
    }
}

Write-Step "PostgreSQL dump"
$pgFile = Join-Path $OutDir "postgres-netops_agent.sql"
docker compose @composeArgs exec -T postgres pg_dump -U netops -d netops_agent | Set-Content -Path $pgFile -Encoding utf8
Write-Ok "postgres -> $pgFile"

if (-not $SkipMinio) {
    Write-Step "MinIO bucket mirror ($minioBucket)"
    $minioOut = Join-Path $OutDir "minio-$minioBucket"
    New-Item -ItemType Directory -Force -Path $minioOut | Out-Null

    $network = docker inspect netops-minio --format '{{range $k, $v := .NetworkSettings.Networks}}{{$k}}{{end}}' 2>$null
    if (-not $network) {
        Write-Host "  [WARN] netops-minio 未运行，跳过 MinIO 备份" -ForegroundColor Yellow
    } else {
        docker run --rm `
            --network $network `
            -v "${minioOut}:/backup" `
            minio/mc:latest `
            /bin/sh -c "mc alias set local http://minio:9000 '$minioUser' '$minioPass' && mc mirror --overwrite local/$minioBucket /backup/"
        Write-Ok "minio -> $minioOut"
    }
}

if (-not $SkipSqlite) {
    Write-Step "Django SQLite (auth users)"
    $sqliteSrc = Join-Path $ProjectRoot "web\django_backend\db.sqlite3"
    if (Test-Path $sqliteSrc) {
        Copy-Item $sqliteSrc (Join-Path $OutDir "django-db.sqlite3") -Force
        Write-Ok "sqlite copied"
    } else {
        Write-Host "  [WARN] db.sqlite3 不存在，跳过" -ForegroundColor Yellow
    }
}

$manifest = @{
    timestamp     = $ts
    postgres      = "postgres-netops_agent.sql"
    minio         = if (-not $SkipMinio) { "minio-$minioBucket" } else { $null }
    django_sqlite = if (-not $SkipSqlite) { "django-db.sqlite3" } else { $null }
} | ConvertTo-Json
$manifest | Set-Content (Join-Path $OutDir "manifest.json") -Encoding utf8

Write-Host ""
Write-Host "[完成] 备份目录: $OutDir" -ForegroundColor Green
