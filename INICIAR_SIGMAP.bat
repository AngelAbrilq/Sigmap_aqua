@echo off
title SIGMAP-AQUA servidor
cd /d "%~dp0"
call venv\Scripts\activate.bat
set PYTHONUNBUFFERED=1
ipconfig > logs\ipconfig.txt
python firmware\tools\preparar_sustentacion.py --intervalo 30 > logs\preparacion.txt 2>&1
type logs\preparacion.txt
start "SIGMAP monitor" /min python firmware\tools\monitor_lecturas.py
echo.
echo Servidor en http://0.0.0.0:8000  (Ctrl+C para detener)
powershell -NoProfile -ExecutionPolicy Bypass -Command "python manage.py runserver 0.0.0.0:8000 2>&1 | ForEach-Object { $_.ToString() } | Tee-Object -FilePath logs\server.log"
pause
