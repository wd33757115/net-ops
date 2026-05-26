# E2E smoke test via Django BFF
param(
    [string]$BffBaseUrl = "http://localhost:8001",
    [int]$TimeoutSec = 120
)

$ErrorActionPreference = "Continue"

function Write-Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

function Test-Health {
    try {
        $r = Invoke-RestMethod -Uri "$BffBaseUrl/api/health/" -TimeoutSec 10
        if ($r.success -eq $true) { return $true }
        if ($r.status -eq "healthy") { return $true }
        if ($r.data.status -eq "healthy") { return $true }
        return $false
    } catch {
        return $false
    }
}

function Invoke-Chat($query) {
    $body = @{ query = $query; source = "chat" } | ConvertTo-Json -Compress
    $headers = @{ "Content-Type" = "application/json" }
    return Invoke-RestMethod -Uri "$BffBaseUrl/api/chat/" -Method POST -Body $body -Headers $headers -TimeoutSec $TimeoutSec
}

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Supervisor v2 E2E" -ForegroundColor Cyan
Write-Host "  BFF: $BffBaseUrl" -ForegroundColor Gray
Write-Host "============================================================" -ForegroundColor Cyan

Write-Step "Health check"
if (-not (Test-Health)) {
    Write-Host "  [FAIL] BFF unreachable. Run scripts\test\start.ps1 first." -ForegroundColor Red
    exit 1
}
Write-Host "  [OK] BFF healthy" -ForegroundColor Green

$cases = @(
    @{ Name = "single-skill"; Query = "list all devices" },
    @{ Name = "parallel"; Query = "patrol devices and backup config at the same time" },
    @{ Name = "sequential"; Query = "patrol devices first then backup config based on results" }
)

$passed = 0
foreach ($case in $cases) {
    Write-Step ("[" + $case.Name + "] " + $case.Query)
    try {
        $resp = Invoke-Chat $case.Query
        $data = if ($resp.data) { $resp.data } else { $resp }
        $answer = $null
        if ($data.answer) { $answer = $data.answer }
        elseif ($data.response) { $answer = $data.response }
        elseif ($data.message) { $answer = $data.message }
        else { $answer = ($data | ConvertTo-Json -Depth 3) }
        if ($answer) {
            $preview = if ($answer.Length -gt 200) { $answer.Substring(0, 200) + "..." } else { $answer }
            Write-Host "  [OK] $preview" -ForegroundColor Green
            $passed++
        }
    } catch {
        Write-Host "  [FAIL] $($_.Exception.Message)" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "E2E: $passed / $($cases.Count) passed" -ForegroundColor $(if ($passed -eq $cases.Count) { "Green" } else { "Yellow" })
if ($passed -lt $cases.Count) { exit 1 }
