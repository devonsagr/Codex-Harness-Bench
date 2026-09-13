@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please install the project environment first. See README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -m chb.cli ui
if errorlevel 1 pause
endlocal
