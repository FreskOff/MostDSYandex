$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $projectDir "presence.py"
$exePath = Join-Path $projectDir "dist\MostDSYandex.exe"
$logPath = Join-Path $projectDir "presence.log"
$errPath = Join-Path $projectDir "presence.err.log"

$existing = Get-CimInstance Win32_Process |
    Where-Object {
        ($_.Name -eq "MostDSYandex.exe") -or
        (($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") -and $_.CommandLine -and $_.CommandLine.Contains("presence.py"))
    }

if ($existing) {
    exit 0
}

if (Test-Path $exePath) {
    Start-Process `
        -FilePath $exePath `
        -WorkingDirectory $projectDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $logPath `
        -RedirectStandardError $errPath
    exit 0
}

Start-Process `
    -FilePath (Get-Command python).Source `
    -ArgumentList "-u `"$scriptPath`"" `
    -WorkingDirectory $projectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError $errPath
