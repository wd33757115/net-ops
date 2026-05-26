# Verify test environment health (API + frontend HTML)
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [int]$FastAPIPort = 8000,
    [int]$DjangoPort = 8001,
    [int]$ReactPort = 3000
)

$ErrorActionPreference = "Continue"
. (Join-Path $PSScriptRoot "_port_utils.ps1")

Write-ColorOutput "============================================================" "Cyan"
Write-ColorOutput "  NetOps Test Environment - Verify" "Cyan"
Write-ColorOutput "============================================================" "Cyan"

$failed = $false

function Assert-Ok($name, $cond, $detail = "") {
    if ($cond) {
        Write-ColorOutput "  [OK] $name" "Green"
    } else {
        Write-ColorOutput "  [FAIL] $name $detail" "Red"
        $script:failed = $true
    }
}

try {
    $api = Invoke-RestMethod "http://localhost:$FastAPIPort/health" -TimeoutSec 15
    Assert-Ok "FastAPI /health" ($api.status -eq "healthy" -or $api.status -eq "degraded")
} catch {
    Assert-Ok "FastAPI /health" $false $_.Exception.Message
}

try {
    $bff = Invoke-RestMethod "http://localhost:$DjangoPort/api/health/" -TimeoutSec 15
    Assert-Ok "Django BFF /api/health/" ($bff.success -eq $true)
} catch {
    Assert-Ok "Django BFF /api/health/" $false $_.Exception.Message
}

try {
    $convs = Invoke-RestMethod "http://localhost:$DjangoPort/api/conversations/" -TimeoutSec 15
    Assert-Ok "Django BFF /api/conversations/" ($convs.success -eq $true)
} catch {
    Assert-Ok "Django BFF /api/conversations/" $false $_.Exception.Message
}

try {
    $html = (Invoke-WebRequest "http://localhost:$ReactPort/chat" -UseBasicParsing -TimeoutSec 15).Content
    $hasBundle = $html -match '/assets/index-.*\.js'
    Assert-Ok "React HTML bundle" $hasBundle
} catch {
    Assert-Ok "React HTML bundle" $false $_.Exception.Message
}

try {
    $jsPath = (Invoke-WebRequest "http://localhost:$ReactPort/chat" -UseBasicParsing).Content |
        Select-String -Pattern '/assets/index-[^"]+\.js' |
        ForEach-Object { $_.Matches[0].Value }
    if ($jsPath) {
        $js = Invoke-WebRequest "http://localhost:$ReactPort$jsPath" -UseBasicParsing -TimeoutSec 30
        Assert-Ok "React JS bundle" ($js.StatusCode -eq 200 -and $js.Content -match 'getElementById\("root"\)')
    } else {
        Assert-Ok "React JS bundle" $false "path not found"
    }
} catch {
    Assert-Ok "React JS bundle" $false $_.Exception.Message
}

Write-ColorOutput "" "Cyan"
if ($failed) {
    Write-ColorOutput "Verification FAILED" "Red"
    exit 1
}
Write-ColorOutput "All checks passed. Open http://localhost:$ReactPort/chat in your browser." "Green"
