$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $projectDir "presence.py"
$logPath = Join-Path $projectDir "presence.log"
$errPath = Join-Path $projectDir "presence.err.log"

$existing = Get-CimInstance Win32_Process -Filter "name = 'python.exe' or name = 'pythonw.exe'" |
    Where-Object { $_.CommandLine -and $_.CommandLine.Contains("presence.py") }

if ($existing) {
    exit 0
}

$python = (Get-Command python).Source

Start-Process `
    -FilePath $python `
    -ArgumentList "-u `"$scriptPath`"" `
    -WorkingDirectory $projectDir `
    -WindowStyle Hidden `
    -RedirectStandardOutput $logPath `
    -RedirectStandardError $errPath
