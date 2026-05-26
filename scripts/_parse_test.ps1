param(

    [Parameter(Mandatory = $true)]

    [string[]]$Paths

)

$hasError = $false

foreach ($path in $Paths) {

    $tokens = $null

    $errors = $null

    [void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$tokens, [ref]$errors)

    if ($errors -and $errors.Count -gt 0) {

        $hasError = $true

        Write-Host "FAIL $path" -ForegroundColor Red

        foreach ($err in $errors) {

            Write-Host "  $($err.Message)" -ForegroundColor Red

        }

    } else {

        Write-Host "OK   $path" -ForegroundColor Green

    }

}

if ($hasError) { exit 1 }

