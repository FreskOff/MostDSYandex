$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$entry = Join-Path $projectDir "presence.py"
$dist = Join-Path $projectDir "dist"
$build = Join-Path $projectDir "build"

python -m PyInstaller `
    --onefile `
    --clean `
    --windowed `
    --name MostDSYandex `
    --icon (Join-Path $projectDir "assets\app-icon.ico") `
    --add-data "$projectDir\assets;assets" `
    --distpath $dist `
    --workpath $build `
    --collect-submodules winsdk `
    --collect-submodules yandex_music `
    --collect-submodules pystray `
    $entry

Write-Host "Built:"
Write-Host (Join-Path $dist "MostDSYandex.exe")
