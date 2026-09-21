@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  where uv >nul 2>nul
  if errorlevel 1 (
    echo First launch requires uv. Install uv, then run this launcher again.
    pause
    exit /b 1
  )
  echo Preparing the local Python environment. Docker is not required.
  call uv sync --frozen
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
if not exist "frontend\dist\index.html" (
  echo Building the frontend. Node.js and pnpm are required for this step.
  call pnpm --dir frontend install --frozen-lockfile
  if errorlevel 1 exit /b 1
  call pnpm --dir frontend build
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -m chb.cli ui
if errorlevel 1 pause
endlocal
