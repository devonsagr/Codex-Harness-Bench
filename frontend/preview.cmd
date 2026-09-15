@echo off
setlocal
cd /d "%~dp0"
echo Starting static preview only. Full app: ..\launch-ui.cmd
pnpm preview
if errorlevel 1 pause
endlocal
