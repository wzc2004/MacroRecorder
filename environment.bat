@echo off
setlocal enabledelayedexpansion
title MacroRecorder - Auto Environment Setup

cd /d "%~dp0"

echo ============================================
echo   MacroRecorder - Auto Environment Setup
echo ============================================
echo.
echo This script will check and install:
echo   - Python 3.11 (winget or direct download)
echo   - pip
echo   - pynput
echo   - tkinter
echo.

:: ==================================================================
:: STEP 1: Check Python
:: ==================================================================
echo [1/3] Checking Python...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   Python NOT found. Trying auto-install...

    :: Method A: winget
    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Using winget to install Python 3.11...
        winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements 2>nul
        if %errorlevel% equ 0 (
            echo   Done. Please REOPEN this window and re-run.
            pause
            exit /b 0
        )
    )

    :: Method B: download installer
    echo   Downloading Python installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python-installer.exe'" 2>nul
    if exist "%TEMP%\python-installer.exe" (
        echo   Installing (silent mode)...
        "%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
        del "%TEMP%\python-installer.exe" 2>nul
        echo   Done. Please REOPEN this window and re-run.
        pause
        exit /b 0
    )

    echo.
    echo   Auto-install failed.
    echo   Please install manually: https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python %PYVER% - OK

:: ==================================================================
:: STEP 2: pip and pynput
:: ==================================================================
echo [2/3] Checking pip and pynput...

pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   Repairing pip...
    python -m ensurepip --upgrade >nul 2>&1
    python -m pip install --upgrade pip >nul 2>&1
)

python -c "import pynput" 2>nul
if %errorlevel% neq 0 (
    echo   Installing pynput...
    pip install pynput 2>nul
    if %errorlevel% neq 0 (
        pip install pynput --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>nul
    )
    python -c "import pynput" 2>nul
    if %errorlevel% neq 0 (
        echo   ERROR: Could not install pynput.
        pause
        exit /b 1
    )
    echo   pynput installed.
) else (
    echo   pynput already installed.
)
echo   pip + pynput - OK

:: ==================================================================
:: STEP 3: tkinter
:: ==================================================================
echo [3/3] Checking tkinter...

python -c "import tkinter" 2>nul
if %errorlevel% neq 0 (
    echo   tkinter NOT found.
    echo   Please reinstall Python from python.org
    echo   Make sure "tcl/tk and IDLE" is checked during install.
    pause
    exit /b 1
)
echo   tkinter - OK

:: ==================================================================
:: ALL OK - menu loop
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
if "%CHOICE%"=="1" (
    echo.
    echo Starting MacroRecorder...
    python "%~dp0main.py"
    pause
    exit /b 0
)
if "%CHOICE%"=="2" (
    echo.
    echo Setup complete. You can run install.bat to start later.
    pause
    exit /b 0
)
echo Invalid choice. Please enter 1 or 2.
goto menu
