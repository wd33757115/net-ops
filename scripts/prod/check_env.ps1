# 生产环境变量预检：默认密钥 / 必填项
param(
    [string]$EnvFile = (Join-Path (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path ".env")
)

$ErrorActionPreference = "Continue"
$failed = $false
$warned = $false

function Fail($msg) {
    Write-Host "  [FAIL] $msg" -ForegroundColor Red
    $script:failed = $true
}

function Warn($msg) {
    Write-Host "  [WARN] $msg" -ForegroundColor Yellow
    $script:warned = $true
}

function Ok($msg) {
    Write-Host "  [OK]   $msg" -ForegroundColor Green
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  NetOps Production - Environment Preflight" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

if (-not (Test-Path $EnvFile)) {
    Fail ".env 不存在：$EnvFile （请 copy .env.example .env）"
    exit 1
}

$lines = Get-Content $EnvFile -ErrorAction SilentlyContinue
$envMap = @{}
foreach ($line in $lines) {
    if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
    $k, $v = $line -split '=', 2
    $envMap[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
}

$weakPatterns = @(
    'change-me', 'netops123456', 'minioadmin', 'django-insecure',
    'itsm-secret-2026', 'my-secret-key', 'guest', 'admin123'
)

function Test-Weak([string]$name, [string]$value) {
    if (-not $value) { return }
    foreach ($p in $weakPatterns) {
        if ($value -ieq $p -or $value -match [regex]::Escape($p)) {
            Warn "$name 仍含默认/弱口令片段"
            return
        }
    }
}

if (-not $envMap['DEEPSEEK_API_KEY']) {
    Fail "DEEPSEEK_API_KEY 未设置"
} else {
    Ok "DEEPSEEK_API_KEY 已设置"
}

foreach ($key in @('SECRET_KEY', 'JWT_SECRET_KEY', 'POSTGRES_PASSWORD', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY', 'ITSM_WEBHOOK_SECRET')) {
    if (-not $envMap[$key]) {
        Warn "$key 未设置"
    } else {
        Test-Weak $key $envMap[$key]
    }
}

if ($envMap['DJANGO_DEBUG'] -eq 'true' -or $envMap['DJANGO_DEBUG'] -eq 'True') {
    Warn "DJANGO_DEBUG=true（生产应为 false）"
} else {
    Ok "DJANGO_DEBUG 非 true"
}

if ($envMap['DEBUG'] -eq 'true' -or $envMap['DEBUG'] -eq 'True') {
    Warn "DEBUG=true（生产应为 false）"
}

if ($envMap['ENFORCE_BFF_ORIGIN'] -eq 'false') {
    Warn "ENFORCE_BFF_ORIGIN=false（生产建议 true）"
} else {
    Ok "ENFORCE_BFF_ORIGIN 已启用或未显式关闭"
}

if ($envMap['LOG_FORMAT'] -ne 'json') {
    Warn "LOG_FORMAT 非 json（生产建议 json 便于采集）"
} else {
    Ok "LOG_FORMAT=json"
}

if (-not $envMap['CELERY_BROKER_URL']) {
    Warn "CELERY_BROKER_URL 未设置"
}

Write-Host ""
if ($failed) {
    Write-Host "预检未通过，请修正 .env 后重试。" -ForegroundColor Red
    exit 1
}
if ($warned) {
    Write-Host "预检完成（有警告，上线前建议处理）。" -ForegroundColor Yellow
    exit 0
}
Write-Host "预检通过。" -ForegroundColor Green
exit 0
