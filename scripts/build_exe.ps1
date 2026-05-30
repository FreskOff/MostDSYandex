$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$entry = Join-Path $projectDir "presence.py"
$dist = Join-Path $projectDir "dist"
$build = Join-Path $projectDir "build"

python -m PyInstaller `
    --onefile `
    --clean `
    --console `
    --name MostDSYandex `
    --distpath $dist `
    --workpath $build `
    --collect-submodules winsdk `
    --collect-submodules yandex_music `
    $entry

Write-Host "Built:"
Write-Host (Join-Path $dist "MostDSYandex.exe")
