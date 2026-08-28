@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo Windows Autoclicker Launcher
echo ==============================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    echo.
    echo Press any key to open download page...
    pause >nul
    start https://python.org/downloads/
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>nul') do set PYTHON_VERSION=%%i
echo Found Python: %PYTHON_VERSION%

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

if not exist "%PY%" (
    echo Creating virtual environment...
    python -m venv "%VENV%"
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo.
)

echo Setting up virtual environment...
call "%VENV%\Scripts\activate.bat"

echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

if exist requirements-lock.txt (
    echo Installing/updating dependencies from requirements-lock.txt...
    python -m pip install -r requirements-lock.txt
) else if exist requirements.txt (
    echo Installing/updating dependencies from requirements.txt...
    python -m pip install -r requirements.txt
)
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)
echo.

if not exist autoclicker.ico (
    echo Creating application icon...
    python create_icon.py
    echo.
)

if not exist autoclicker.py (
    echo ERROR: autoclicker.py not found
    echo Please ensure all files are in the same directory
    pause
    exit /b 1
)

echo Starting Windows Autoclicker...
echo.
echo Controls:
echo   F6  - Start clicking
echo   F7  - Stop clicking
echo   ESC - Emergency stop
echo.
echo Press Ctrl+C in this window to exit
echo.

python autoclicker.py

echo.
echo Autoclicker closed.
pause
