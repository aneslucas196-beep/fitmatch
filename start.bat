@echo off
REM Lance FitMatch (web + rappels 24/7)
cd /d "%~dp0"
if "%PORT%"=="" set PORT=5000
python start_server.py
pause
