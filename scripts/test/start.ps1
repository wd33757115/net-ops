# Test env: Docker middleware + local FastAPI / Django / React
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$FastAPIPort = 8000,
    [int]$DjangoPort = 8001,
    [int]$ReactPort = 3000,
    [switch]$SkipMiddleware,
    [switch]$UseSupervisorV1,
    [switch]$DevMode
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_port_utils.ps1")

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @{} }
    $vars = @{}
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#")) { return }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) { return }
        $vars[$line.Substring(0, $idx).Trim()] = $line.Substring($idx + 1).Trim()
    }
    return $vars
}

function Escape-SingleQuotedPath([string]$Path) {
    return $Path.Replace("'", "''")
}

function New-LauncherScript {
    param(
        [string]$Path,
        [string]$WorkingDirectory,
        [hashtable]$EnvVars,
        [string]$CommandLine,
        [string]$LogFile,
        [string[]]$PreCommands = @()
    )
    $lines = New-Object System.Collections.Generic.List[string]
    [void]$lines.Add('$ErrorActionPreference = "Continue"')
    [void]$lines.Add("Set-Location -LiteralPath '$(Escape-SingleQuotedPath $WorkingDirectory)'")
    foreach ($cmd in $PreCommands) {
        [void]$lines.Add($cmd)
    }
    foreach ($key in ($EnvVars.Keys | Sort-Object)) {
        $val = Escape-SingleQuotedPath ($EnvVars[$key].ToString())
        [void]$lines.Add("`$env:$key = '$val'")
    }
    [void]$lines.Add("$CommandLine *>> '$(Escape-SingleQuotedPath $LogFile)'")
    $lines | Set-Content -Path $Path -Encoding UTF8
}

function Start-LauncherProcess {
    param([string]$LauncherPath)
    return Start-Process -FilePath "powershell.exe" -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $LauncherPath
    ) -PassThru -WindowStyle Minimized
}

$AppPorts = @($FastAPIPort, $DjangoPort, $ReactPort, 3001, 3002)
$runtimeDir = Join-Path $ProjectRoot ".runtime\test"
$pidFile = Join-Path $runtimeDir "pids.json"
$logDir = Join-Path $ProjectRoot ".runtime\test\logs"
New-Item -ItemType Directory -Force -Path $runtimeDir, $logDir | Out-Null

Write-ColorOutput "============================================================" "Cyan"
Write-ColorOutput "  NetOps Test Environment - Start" "Cyan"
Write-ColorOutput "  (Middleware Docker + Local App Processes)" "Cyan"
Write-ColorOutput "============================================================" "Cyan"
Write-ColorOutput "  Project: $ProjectRoot" "Gray"
Write-ColorOutput "  FastAPI: $FastAPIPort | Django: $DjangoPort | React: $ReactPort" "Gray"
Write-ColorOutput "" "Cyan"

Set-Location $ProjectRoot

$venvPython = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-ColorOutput "  [ERROR] venv not found. Run scripts\test\install.ps1" "Red"
    exit 1
}

Write-ColorOutput "[Step 0/7] Stop old processes and free ports..." "Yellow"
Stop-ProjectAppProcesses -ProjectRoot $ProjectRoot
Stop-DockerAppContainers
if (Test-Path $pidFile) {
    $old = Get-Content $pidFile -Raw | ConvertFrom-Json
    foreach ($name in $old.PSObject.Properties.Name) {
        Stop-Process -Id ([int]$old.$name) -Force -ErrorAction SilentlyContinue
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}
foreach ($round in 1..2) {
    foreach ($p in $AppPorts) { Kill-ProcessOnPort -Port $p | Out-Null }
    $busy = @()
    foreach ($port in @($FastAPIPort, $DjangoPort, $ReactPort)) {
        if (-not (Test-PortBindable -Port $port -PythonExe $venvPython)) { $busy += $port }
    }
    if ($busy.Count -eq 0) { break }
    if ($round -eq 2) {
        Write-ColorOutput ("  [ERROR] Ports not bindable: " + ($busy -join ", ")) "Red"
        Write-ColorOutput "  Hint: close old PowerShell launcher windows, run stop.ps1, or end python/node in Task Manager" "Yellow"
        exit 1
    }
    Start-Sleep -Seconds 2
}
Write-ColorOutput "  [OK] Ports cleared" "Green"

$dotEnv = Import-DotEnvFile -Path (Join-Path $ProjectRoot ".env")

Write-ColorOutput "[Step 1/7] Check Docker..." "Yellow"
$dockerOk = $false
if ($SkipMiddleware) {
    Write-ColorOutput "  [SKIP] SkipMiddleware enabled" "Gray"
} elseif (Test-DockerAvailable) {
    Write-ColorOutput "  [OK] Docker is available" "Green"
    $dockerOk = $true
} else {
    Write-ColorOutput "  [WARN] Docker not available - start Docker Desktop, middleware skipped" "Yellow"
}

Write-ColorOutput "[Step 2/7] Start Docker middleware..." "Yellow"
if ($dockerOk) {
    $composeFile = Join-Path $ProjectRoot "deployment\docker-compose.middleware.yml"
    if (-not (Ensure-DockerReady -ComposeFile $composeFile)) {
        Write-ColorOutput "  [ERROR] docker compose up failed" "Red"
        exit 1
    }
    Write-ColorOutput "  Waiting 20s for PostgreSQL / Redis..." "Gray"
    Start-Sleep -Seconds 20
    $middleware = @("netops-postgres", "netops-redis", "netops-rabbitmq", "netops-minio", "netops-qdrant")
    foreach ($svc in $middleware) {
        $running = Get-DockerContainersRunning -Names @($svc)
        if ($running -contains $svc) {
            Write-ColorOutput "  [OK] $svc is running" "Green"
        } else {
            Write-ColorOutput "  [WAIT] $svc is starting..." "Yellow"
        }
    }
} else {
    Write-ColorOutput "  [SKIP] No Docker middleware" "Gray"
}

Write-ColorOutput "[Step 3/7] Django migrate..." "Yellow"
Push-Location (Join-Path $ProjectRoot "web\django_backend")
$env:DJANGO_SETTINGS_MODULE = "django_backend.settings"
$migrateLog = Join-Path $logDir "django-migrate.log"
& $venvPython manage.py migrate --noinput *>&1 | Out-File $migrateLog -Encoding utf8
Pop-Location
Write-ColorOutput "  [OK] migrate done (log: django-migrate.log)" "Green"

$useV2 = if ($UseSupervisorV1) { "false" } else { "true" }
$pids = @{}
$py = Escape-SingleQuotedPath $venvPython

$fastapiEnv = @{
    DEBUG = "true"
    ENFORCE_BFF_ORIGIN = "false"
    USE_SUPERVISOR_V2 = $useV2
    POSTGRES_HOST = "localhost"
    REDIS_HOST = "localhost"
    QDRANT_HOST = "localhost"
    MINIO_ENDPOINT = "localhost:9000"
}
foreach ($k in @("DEEPSEEK_API_KEY", "POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB", "POSTGRES_PORT")) {
    if ($dotEnv.ContainsKey($k)) { $fastapiEnv[$k] = $dotEnv[$k] }
}

Write-ColorOutput "[Step 4/7] Start Celery Worker (solo, Windows) ..." "Yellow"
$celeryLog = Join-Path $logDir "celery.log"
$celeryLauncher = Join-Path $logDir "celery-launcher.ps1"
$celeryEnv = @{
    POSTGRES_HOST = "localhost"
    REDIS_HOST = "localhost"
}
foreach ($k in @("DEEPSEEK_API_KEY", "POSTGRES_PASSWORD", "POSTGRES_USER", "POSTGRES_DB", "POSTGRES_PORT", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND")) {
    if ($dotEnv.ContainsKey($k)) { $celeryEnv[$k] = $dotEnv[$k] }
}
$celeryCmd = '& ''' + $py + ''' -m celery -A src.core.celery_tasks.celery_app worker --loglevel=info -P solo'
New-LauncherScript -Path $celeryLauncher -WorkingDirectory $ProjectRoot -EnvVars $celeryEnv -CommandLine $celeryCmd -LogFile $celeryLog -PreCommands @(
    'Remove-Item Env:DJANGO_SETTINGS_MODULE -ErrorAction SilentlyContinue'
)
$pids["celery"] = (Start-LauncherProcess -LauncherPath $celeryLauncher).Id
Write-ColorOutput "  [OK] Celery PID=$($pids['celery']) (log: celery.log)" "Green"
Start-Sleep -Seconds 5

Write-ColorOutput "[Step 5/7] Start FastAPI :$FastAPIPort ..." "Yellow"
$fastapiLog = Join-Path $logDir "fastapi.log"
$fastapiLauncher = Join-Path $logDir "fastapi-launcher.ps1"
$fastapiCmd = '& ''' + $py + ''' -m uvicorn src.gateway.main:app --host 0.0.0.0 --port ' + $FastAPIPort + ' --reload'
New-LauncherScript -Path $fastapiLauncher -WorkingDirectory $ProjectRoot -EnvVars $fastapiEnv -CommandLine $fastapiCmd -LogFile $fastapiLog
$pids["fastapi"] = (Start-LauncherProcess -LauncherPath $fastapiLauncher).Id
Write-ColorOutput "  [OK] FastAPI PID=$($pids['fastapi']) USE_SUPERVISOR_V2=$useV2" "Green"

Write-ColorOutput "[Step 6/7] Start Django BFF :$DjangoPort ..." "Yellow"
$djangoLog = Join-Path $logDir "django.log"
$djangoDir = Join-Path $ProjectRoot "web\django_backend"
$djangoLauncher = Join-Path $logDir "django-launcher.ps1"
$djangoCmd = '& ''' + $py + ''' -m daphne -b 0.0.0.0 -p ' + $DjangoPort + ' django_backend.asgi:application'
New-LauncherScript -Path $djangoLauncher -WorkingDirectory $djangoDir -EnvVars @{
    DJANGO_DEBUG = "true"
    FASTAPI_BASE_URL = "http://localhost:$FastAPIPort"
} -CommandLine $djangoCmd -LogFile $djangoLog
$pids["django"] = (Start-LauncherProcess -LauncherPath $djangoLauncher).Id
Write-ColorOutput "  [OK] Django PID=$($pids['django'])" "Green"

Write-ColorOutput "[Step 7/7] Start React :$ReactPort ..." "Yellow"
Kill-ProcessOnPort -Port $ReactPort | Out-Null
Kill-ProcessOnPort -Port 3001 | Out-Null
Kill-ProcessOnPort -Port 3002 | Out-Null
$reactLog = Join-Path $logDir "react.log"
$reactDir = Join-Path $ProjectRoot "web\react_frontend"
$reactLauncher = Join-Path $logDir "react-launcher.ps1"
if ($DevMode) {
    $viteCache = Join-Path $reactDir "node_modules\.vite"
    if (Test-Path $viteCache) {
        Remove-Item $viteCache -Recurse -Force -ErrorAction SilentlyContinue
        Write-ColorOutput "  Cleared Vite dep cache (dev mode)" "Gray"
    }
    $reactCmd = "npm run dev -- --host 0.0.0.0 --port $ReactPort --strictPort"
    Write-ColorOutput "  Mode: Vite dev (pass -DevMode explicitly)" "Gray"
} else {
    $reactCmd = "npm run build; if (`$LASTEXITCODE -ne 0) { exit `$LASTEXITCODE }; npm run preview -- --host 0.0.0.0 --port $ReactPort --strictPort"
    Write-ColorOutput "  Mode: Vite preview (production build, stable UI)" "Gray"
}
New-LauncherScript -Path $reactLauncher -WorkingDirectory $reactDir -EnvVars @{
    VITE_DJANGO_BACKEND_URL = "http://localhost:$DjangoPort"
} -CommandLine $reactCmd -LogFile $reactLog
$pids["react"] = (Start-LauncherProcess -LauncherPath $reactLauncher).Id
Write-ColorOutput "  [OK] React PID=$($pids['react'])" "Green"

$pids | ConvertTo-Json | Set-Content -Path $pidFile -Encoding UTF8

Write-ColorOutput "Waiting for services (up to 120s)..." "Yellow"
$reactOk = Wait-ReactReady -Port $ReactPort -TimeoutSec 120
$bffOk = Wait-HttpOk -Url "http://localhost:$DjangoPort/api/health/" -TimeoutSec 120
$apiOk = Wait-HttpOk -Url "http://localhost:$FastAPIPort/health" -TimeoutSec 120

if (-not $reactOk) {
    Write-ColorOutput "  [ERROR] React dev server not ready or wrong mode. Check $reactLog" "Red"
    Write-ColorOutput "  Hint: ensure Docker netops-react is stopped" "Yellow"
    exit 1
}

Write-ColorOutput "" "Cyan"
Write-ColorOutput "============================================================" "Cyan"
Write-ColorOutput "  Test Environment Ready" "Green"
Write-ColorOutput "============================================================" "Cyan"
Write-ColorOutput "  React:   http://localhost:$ReactPort/chat  $(if ($reactOk) {'[OK]'} else {'[WAIT]'})" "Gray"
Write-ColorOutput "  Django:  http://localhost:$DjangoPort/api/health/  $(if ($bffOk) {'[OK]'} else {'[WAIT]'})" "Gray"
Write-ColorOutput "  FastAPI: http://localhost:$FastAPIPort/health  $(if ($apiOk) {'[OK]'} else {'[WAIT]'})" "Gray"
Write-ColorOutput "  Celery:  see $logDir\celery.log (required for firewall/backup/patrol Skills)" "Gray"
Write-ColorOutput "  Logs:    $logDir" "Gray"
Write-ColorOutput "" "Cyan"
Write-ColorOutput "Tip: scripts\test\stop.ps1 to stop" "Yellow"
Start-Process "http://localhost:$ReactPort/chat"

if (-not $bffOk -or -not $apiOk) {
    Write-ColorOutput "  [WARN] Some backend health checks pending; see logs" "Yellow"
}

Write-ColorOutput "Running verify.ps1..." "Yellow"
& (Join-Path $PSScriptRoot "verify.ps1") -ProjectRoot $ProjectRoot -FastAPIPort $FastAPIPort -DjangoPort $DjangoPort -ReactPort $ReactPort
if ($LASTEXITCODE -ne 0) { exit 1 }
