@echo off
setlocal
cd /d "%~dp0"
echo Starting static UI development only. Full app: ..\launch-ui.cmd
pnpm dev
if errorlevel 1 pause
endlocal
