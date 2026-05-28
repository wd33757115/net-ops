# Shared helpers for test start/stop scripts (netstat port kill + HTTP wait)

function Write-ColorOutput {
    param([string]$Text, [string]$Color = "White")
    Write-Host $Text -ForegroundColor $Color
}

function Get-ListeningPidsOnPort {
    param([int]$Port)
    $pids = New-Object System.Collections.Generic.HashSet[int]
    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            $procId = $_.OwningProcess
            if ($procId -and (Get-Process -Id $procId -ErrorAction SilentlyContinue)) {
                [void]$pids.Add([int]$procId)
            }
        }
    return @($pids)
}

function Stop-ProjectAppProcesses {
    param([string]$ProjectRoot)
    $pattern = [regex]::Escape($ProjectRoot)
    Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='node.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -match $pattern) } |
        ForEach-Object {
            Write-ColorOutput "    Stop project process PID $($_.ProcessId)" "Gray"
            cmd /c "taskkill /F /T /PID $($_.ProcessId)" 2>$null | Out-Null
        }
}

function Kill-ProcessOnPort {
    param([int]$Port)
    $pids = Get-ListeningPidsOnPort -Port $Port
    if ($pids.Count -eq 0) {
        Write-ColorOutput "    Port $Port is free" "Green"
        return $true
    }
    foreach ($portPid in $pids) {
        Write-ColorOutput "    Port $Port used by PID $portPid, killing..." "Yellow"
        cmd /c "taskkill /F /T /PID $portPid" 2>$null | Out-Null
        Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
    $still = Get-ListeningPidsOnPort -Port $Port
    if ($still.Count -gt 0) {
        Write-ColorOutput ("    Warning: port $Port still used by PIDs " + ($still -join ", ")) "Red"
        return $false
    }
    Write-ColorOutput "    Port $Port is now free" "Green"
    return $true
}

function Stop-ProcessesOnPorts {
    param([int[]]$Ports)
    foreach ($port in $Ports) {
        Kill-ProcessOnPort -Port $port | Out-Null
    }
}

function Test-PortsFree {
    param([int[]]$Ports)
    $busy = @()
    foreach ($port in $Ports) {
        if ((Get-ListeningPidsOnPort -Port $port).Count -gt 0) { $busy += $port }
    }
    return $busy
}

function Test-PortBindable {
    param(
        [int]$Port,
        [string]$PythonExe = "python"
    )
    # Port already in use by a live listener — not bindable for a new process
    if ((Get-ListeningPidsOnPort -Port $Port).Count -gt 0) {
        return $false
    }
    $script = @"
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    s.bind(('0.0.0.0', $Port))
    print('ok')
finally:
    s.close()
"@
    $tmp = [System.IO.Path]::GetTempFileName() + ".py"
    Set-Content -Path $tmp -Value $script -Encoding UTF8
    $out = & $PythonExe $tmp 2>&1
    Remove-Item $tmp -Force -ErrorAction SilentlyContinue
    return ($out -match 'ok')
}

function Test-ProjectServiceHealthy {
    param(
        [int]$Port,
        [string]$HealthUrl
    )
    if ((Get-ListeningPidsOnPort -Port $Port).Count -eq 0) { return $false }
    try {
        $r = Invoke-WebRequest -Uri $HealthUrl -UseBasicParsing -TimeoutSec 5
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Wait-ReactReady {
    param(
        [int]$Port = 3000,
        [int]$TimeoutSec = 90
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $html = (Invoke-WebRequest -Uri "http://localhost:$Port/" -UseBasicParsing -TimeoutSec 8).Content
            $isDev = ($html -match '@vite/client') -and ($html -match '/src/main\.tsx' -or $html -match 'html-proxy')
            $isPreview = ($html -match '/assets/index-.*\.js')
            if ($isDev -or $isPreview) { return $true }
        } catch {
            # retry
        }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Stop-DockerAppContainers {
    $appContainers = @("netops-react", "netops-django", "netops-fastapi")
    foreach ($name in $appContainers) {
        docker stop $name 2>$null | Out-Null
        docker rm $name 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "    Removed Docker app container: $name" "Gray"
        }
    }
    $fullCompose = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) "deployment\docker-compose.yml"
    if (Test-Path $fullCompose) {
        docker compose -f $fullCompose stop react django fastapi 2>$null | Out-Null
    }
}

function Ensure-DockerReady {
    param([string]$ComposeFile)
    $contexts = @("desktop-linux", "default")
    foreach ($ctx in $contexts) {
        docker context use $ctx 2>$null | Out-Null
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "  [OK] Docker context: $ctx" "Green"
            Stop-DockerAppContainers
            docker compose -f $ComposeFile up -d --remove-orphans 2>&1 | ForEach-Object { Write-Host "  $_" }
            return ($LASTEXITCODE -eq 0)
        }
    }
    return $false
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSec = 60,
        [int]$IntervalSec = 3
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) { return $true }
        } catch {
            # retry
        }
        Start-Sleep -Seconds $IntervalSec
    }
    return $false
}

function Test-DockerAvailable {
    foreach ($ctx in @("desktop-linux", "default")) {
        docker context use $ctx 2>$null | Out-Null
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return $true }
    }
    return $false
}

function Invoke-DockerComposeUp {
    param(
        [string]$ComposeFile,
        [string]$Label = "compose"
    )
    if (-not (Test-Path $ComposeFile)) {
        Write-ColorOutput "  [SKIP] $Label compose not found: $ComposeFile" "Gray"
        return $false
    }
    Write-ColorOutput "  Starting $Label..." "Gray"
    docker compose -f $ComposeFile up -d --remove-orphans 2>&1 | ForEach-Object { Write-Host "    $_" }
    if ($LASTEXITCODE -ne 0) {
        Write-ColorOutput "  [ERROR] $Label docker compose up failed" "Red"
        return $false
    }
    return $true
}

function Invoke-DockerComposeDown {
    param(
        [string]$ComposeFile,
        [string]$Label = "compose"
    )
    if (-not (Test-Path $ComposeFile)) {
        return $true
    }
    docker compose -f $ComposeFile down 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-ColorOutput "  [OK] $Label stopped" "Green"
        return $true
    }
    Write-ColorOutput "  [WARN] $Label docker compose down failed" "Yellow"
    return $false
}

function Wait-TcpPortReady {
    param(
        [int]$Port,
        [string]$Label,
        [int]$TimeoutSec = 90,
        [int]$IntervalSec = 2
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ((Get-ListeningPidsOnPort -Port $Port).Count -gt 0) {
            Write-ColorOutput "  [OK] $Label port $Port is listening" "Green"
            return $true
        }
        Start-Sleep -Seconds $IntervalSec
    }
    Write-ColorOutput "  [ERROR] $Label port $Port not ready after ${TimeoutSec}s" "Red"
    return $false
}

function Get-DockerContainersRunning {
    param([string[]]$Names)
    $running = @()
    foreach ($name in $Names) {
        $status = docker ps --filter "name=$name" --filter "status=running" --format "{{.Names}}" 2>$null
        if ($status -eq $name) { $running += $name }
    }
    return $running
}
