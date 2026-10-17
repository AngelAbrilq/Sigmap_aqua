@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python firmware\tools\preparar_sustentacion.py --intervalo 30 > logs\preparacion.txt 2>&1
echo FIN >> logs\preparacion.txt
