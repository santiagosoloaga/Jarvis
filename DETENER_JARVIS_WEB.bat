@echo off
rem Apaga JARVIS web (el que corre en segundo plano).
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and $_.CommandLine -like '*web_jarvis.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
echo JARVIS web apagado.
pause
