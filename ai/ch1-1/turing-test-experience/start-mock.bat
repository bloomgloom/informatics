@echo off
setlocal
cd /d "%~dp0"

if not exist .venv\Scripts\python.exe goto :setup
if not exist .venv\.setup-complete goto :setup
if not exist local\seats.csv goto :setup
goto :start

:setup
call setup.bat
if errorlevel 1 exit /b 1

:start
.venv\Scripts\python.exe -m app.main --mock-llm --dev --port 9000 %*

