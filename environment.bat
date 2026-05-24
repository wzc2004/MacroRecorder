@chcp 65001 >nul
@echo off
setlocal enabledelayedexpansion
title MacroRecorder - Auto Environment Setup

cd /d "%~dp0"

echo ============================================
echo   MacroRecorder - Auto Setup
echo   Auto-detect and install missing environment
echo ============================================
echo.

:: ==================================================================
:: STEP 1: Check Python
:: ==================================================================
echo [1/3] Python...

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   Python not found. Attempting automatic install...

    winget --version >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Using winget to install Python...
        winget install Python.Python.3.11 --accept-package-agreements --accept-source-agreements 2>nul
        if %errorlevel% equ 0 (
            echo   Python installed via winget.
            echo   Please REOPEN this window and re-run this script.
            pause
            exit /b 0
        )
    )

    echo   Downloading Python installer...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile '%TEMP%\python-installer.exe'" 2>nul
    if exist "%TEMP%\python-installer.exe" (
        echo   Installing Python (silent)...
        "%TEMP%\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0
        del "%TEMP%\python-installer.exe" 2>nul
        echo   Done. Please REOPEN this window and re-run this script.
        pause
        exit /b 0
    )

    echo   Auto-install failed. Please install manually:
    echo     https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python %PYVER% OK.

:: ==================================================================
:: STEP 2: pip and pynput
:: ==================================================================
echo [2/3] pip and pynput...

pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   pip missing, repairing...
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
)
python -c "import pynput" 2>nul
if %errorlevel% neq 0 (
    echo   ERROR: Failed to install pynput.
    pause
    exit /b 1
)
echo   pip + pynput OK.

:: ==================================================================
:: STEP 3: tkinter
:: ==================================================================
echo [3/3] tkinter...

python -c "import tkinter" 2>nul
if %errorlevel% neq 0 (
    echo   tkinter not found.
    echo   Reinstall Python from https://www.python.org/downloads/
    echo   Make sure "tcl/tk and IDLE" is checked during install.
    pause
    exit /b 1
)
echo   tkinter OK.

:: ==================================================================
:: ALL OK
:: ==================================================================
echo.
echo ============================================
echo   All checks passed!
echo ============================================
echo.
echo   [1] Start MacroRecorder now
echo   [2] Exit
echo.
set /p CHOICE="Enter choice (1/2): "
if "%CHOICE%"=="1" (
    echo.
    echo Starting MacroRecorder...
    python "%~dp0main.py"
)
exit /b 0
