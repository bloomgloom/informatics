@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python 3.11 or newer is required.
    echo Download it from https://www.python.org/downloads/windows/
    pause
    exit /b 1
  )
  set "PYTHON_CMD=python"
)

%PYTHON_CMD% -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11 or newer is required.'"
if errorlevel 1 (
  pause
  exit /b 1
)

%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto :failed

if exist .venv\.setup-complete del .venv\.setup-complete
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto :failed

if not exist logs mkdir logs
if not exist local mkdir local
if not exist local\roster_names.txt copy config\roster_names.example.txt local\roster_names.txt >nul
if not exist local\seats.csv copy config\seats.example.csv local\seats.csv >nul
type nul > .venv\.setup-complete
echo.
echo Installation complete. Run start.bat to start the server.
pause
exit /b 0

:failed
echo.
echo Installation failed. Check the internet connection and try again.
pause
exit /b 1

