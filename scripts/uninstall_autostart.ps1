$ErrorActionPreference = "Stop"

$shortcutPath = Join-Path ([Environment]::GetFolderPath("Startup")) "MostDSYandex Presence.lnk"

if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Host "Removed autostart shortcut:"
    Write-Host $shortcutPath
} else {
    Write-Host "Autostart shortcut is not installed."
}
