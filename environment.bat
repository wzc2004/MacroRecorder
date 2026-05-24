@echo off
setlocal enabledelayedexpansion
title MacroRecorder - Auto Environment Setup

cd /d "%~dp0"

echo ============================================
echo   MacroRecorder - Auto Environment Setup
echo ============================================
echo.
echo This script will check and install:
echo   - Python 3.11
echo   - pip
echo   - pynput
echo   - tkinter
echo.

:: ==================================================================
:: Check Python
:: ==================================================================
echo [1/3] Checking Python...

python --version >nul 2>&1
if not errorlevel 1 goto python_ok

echo   Python NOT found. Trying auto-install...

:: Method A: winget
winget --version >nul 2>&1
if errorlevel 1 goto method_b
echo   Using winget to install Python 3.11...
winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements 2>nul
if not errorlevel 1 goto python_winget_ok

:: Method B: download installer
:method_b
echo   Downloading Python installer...
powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python-installer.exe'" 2>nul
if not exist "%TEMP%\python-installer.exe" goto python_fail
echo   Installing (silent mode)...
"%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
del "%TEMP%\python-installer.exe" 2>nul
echo   Done. Please REOPEN this window and re-run.
pause
exit /b 0

:python_winget_ok
echo   Done. Please REOPEN this window and re-run.
pause
exit /b 0

:python_fail
echo.
echo   Auto-install failed.
echo   Please install manually: https://www.python.org/downloads/
echo   IMPORTANT: Check "Add Python to PATH" during install.
pause
exit /b 1

:python_ok
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python %PYVER% - OK

:: ==================================================================
:: pip and pynput
:: ==================================================================
echo [2/3] Checking pip and pynput...

pip --version >nul 2>&1
if not errorlevel 1 goto pip_ok
echo   Repairing pip...
python -m ensurepip --upgrade >nul 2>&1
python -m pip install --upgrade pip >nul 2>&1
:pip_ok

python -c "import pynput" 2>nul
if not errorlevel 1 goto pynput_ok
echo   Installing pynput...
pip install pynput 2>nul
if errorlevel 1 pip install pynput --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>nul
python -c "import pynput" 2>nul
if errorlevel 1 goto pynput_fail
echo   pynput installed.
goto pynput_done
:pynput_ok
echo   pynput already installed.
:pynput_done
echo   pip + pynput - OK

:: ==================================================================
:: tkinter
:: ==================================================================
echo [3/3] Checking tkinter...

python -c "import tkinter" 2>nul
if not errorlevel 1 goto tk_ok
echo   tkinter NOT found.
echo   Please reinstall Python from python.org
echo   Make sure "tcl/tk and IDLE" is checked during install.
pause
exit /b 1
:tk_ok
echo   tkinter - OK

:: ==================================================================
:: All OK - menu
:: ==================================================================
:menu
echo.
echo ============================================
echo   All checks passed! Environment is ready.
echo ============================================
echo.
echo   [1] Start MacroRecorder now
echo   [2] Exit
echo.
set "CHOICE="
set /p CHOICE="Enter choice (1 or 2): "
if "%CHOICE%"=="1" goto launch
if "%CHOICE%"=="2" goto done
echo Invalid choice. Please enter 1 or 2.
goto menu

:launch
echo.
echo Starting MacroRecorder...
python "%~dp0main.py"
pause
exit /b 0

:done
echo.
echo Setup complete. You can run install.bat to start later.
pause
exit /b 0

:pynput_fail
echo   ERROR: Could not install pynput.
pause
exit /b 1
