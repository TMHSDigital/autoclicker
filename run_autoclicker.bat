@echo off
REM Windows Autoclicker Launcher
REM This batch file sets up the virtual environment and runs the autoclicker

echo Windows Autoclicker Launcher
echo ==============================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    echo.
    echo Press any key to open download page...
    pause >nul
    start https://python.org/downloads/
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>nul') do set PYTHON_VERSION=%%i
echo Found Python: %PYTHON_VERSION%

REM Create virtual environment if it doesn't exist
if not exist autoclicker_env (
    echo Creating virtual environment...
    python -m venv autoclicker_env
    if %errorlevel% neq 0 (
        echo ERROR: Failed to create virtual environment
        echo You may need to run as administrator
        pause
        exit /b 1
    )
    echo.
)

REM Activate virtual environment and install dependencies
echo Setting up virtual environment...
call autoclicker_env\Scripts\activate.bat

REM Upgrade pip first
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1

if exist requirements.txt (
    echo Installing/updating dependencies...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install dependencies
        echo You may need to run as administrator or check your internet connection
        pause
        exit /b 1
    )
    echo.
)

REM Create icon if it doesn't exist
if not exist autoclicker.ico (
    echo Creating application icon...
    python create_icon.py
    if %errorlevel% neq 0 (
        echo Warning: Could not create icon file
        echo Continuing anyway...
    )
    echo.
)

REM Check if main application exists
if not exist autoclicker.py (
    echo ERROR: autoclicker.py not found
    echo Please ensure all files are in the same directory
    pause
    exit /b 1
)

REM Run the autoclicker
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
