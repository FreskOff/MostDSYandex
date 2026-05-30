@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$n='presence.py'; Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'MostDSYandex.exe' -or ($_.CommandLine -and $_.CommandLine.Contains($n) -and ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe')) } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo MostDSYandex stopped.
pause
