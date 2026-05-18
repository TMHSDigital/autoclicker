@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "VENV=.venv"
set "PY=%VENV%\Scripts\python.exe"

if "%1"=="" goto usage
if /i "%1"=="install" goto install
if /i "%1"=="test" goto test
if /i "%1"=="coverage" goto coverage
if /i "%1"=="lint" goto lint
if /i "%1"=="format" goto format
if /i "%1"=="typecheck" goto typecheck
if /i "%1"=="check" goto check
if /i "%1"=="clean" goto clean
if /i "%1"=="lock" goto lock
if /i "%1"=="smoke" goto smoke
goto usage

:install
if not exist "%VENV%\Scripts\python.exe" python -m venv "%VENV%"
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -e ".[dev,build]"
exit /b %ERRORLEVEL%

:test
"%PY%" -m pytest
exit /b %ERRORLEVEL%

:coverage
"%PY%" -m pytest --cov=autoclicker --cov-report=term --cov-report=html --cov-report=xml
exit /b %ERRORLEVEL%

:lint
"%PY%" -m ruff check autoclicker autoclicker.py tests scripts
if errorlevel 1 exit /b 1
"%PY%" -m ruff format --check .
exit /b %ERRORLEVEL%

:format
"%PY%" -m ruff format .
exit /b %ERRORLEVEL%

:typecheck
"%PY%" -m mypy autoclicker
exit /b %ERRORLEVEL%

:check
call "%~f0" lint
if errorlevel 1 exit /b 1
call "%~f0" typecheck
if errorlevel 1 exit /b 1
call "%~f0" test
exit /b %ERRORLEVEL%

:clean
if exist "%VENV%" rmdir /s /q "%VENV%"
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist htmlcov rmdir /s /q htmlcov
for /d %%i in (*.egg-info) do if exist "%%i" rmdir /s /q "%%i"
for /d /r %%i in (__pycache__) do @if exist "%%i" rmdir /s /q "%%i"
exit /b 0

:lock
"%PY%" tools\refresh_lock.py
exit /b %ERRORLEVEL%

:smoke
"%PY%" scripts\smoke_check.py
exit /b %ERRORLEVEL%

:usage
echo Usage: tasks.bat ^<install^|test^|coverage^|lint^|format^|typecheck^|check^|clean^|lock^|smoke^>
exit /b 1
