@echo off
REM Installe les dependances FitMatch (Windows)
cd /d "%~dp0"
echo Installation des dependances...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
  echo Essai avec py...
  py -m pip install -r requirements.txt
)
echo Termine.
pause
