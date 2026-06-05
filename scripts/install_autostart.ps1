$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$startup = [Environment]::GetFolderPath("Startup")
$shortcutPath = Join-Path $startup "MostDSYandex Presence.lnk"
$exePath = Join-Path $projectDir "dist\MostDSYandex.exe"
$target = $exePath
$arguments = ""

if (-not (Test-Path $exePath)) {
    $pythonw = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if (-not $pythonw) {
        $pythonw = Get-Command python.exe -ErrorAction Stop
    }
    $target = $pythonw.Source
    $script = Join-Path $projectDir "presence.py"
    $arguments = "`"$script`" --tray"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.Arguments = $arguments
$shortcut.WorkingDirectory = $projectDir
$shortcut.WindowStyle = 7
$shortcut.Description = "Start Yandex Music Discord Rich Presence bridge"
$shortcut.Save()

Write-Host "Installed autostart shortcut:"
Write-Host $shortcutPath
