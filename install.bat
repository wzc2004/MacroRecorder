@chcp 65001 >nul
@echo off
setlocal enabledelayedexpansion

cd /d "%~dp0"
title MacroRecorder - Setup

echo ============================================
echo   MacroRecorder - Setup
echo ============================================
echo.

:: ------------------------------------------------------------------
:: Step 1: Check Python
:: ------------------------------------------------------------------
echo [1/3] Checking Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ============================================
    echo   Python NOT FOUND
    echo ============================================
    echo.
    echo   MacroRecorder requires Python 3.7 or newer.
    echo.
    echo   Option 1: Run environment.bat for auto-install
    echo            (recommended, installs everything automatically)
    echo.
    echo   Option 2: Install manually from python.org
    echo            CHECK "Add Python to PATH" during install
    echo.
    if exist "%~dp0environment.bat" (
        set /p DOENV="Run environment.bat now? (Y/n): "
        if /i "!DOENV!" neq "n" (
            call "%~dp0environment.bat"
            exit /b 0
        )
    )
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python %PYVER% found.

:: ------------------------------------------------------------------
:: Step 2: Check pip
:: ------------------------------------------------------------------
echo [2/3] Checking pip...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   pip missing, trying to repair...
    python -m ensurepip --upgrade >nul 2>&1
    pip --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo   pip could not be repaired.
        if exist "%~dp0environment.bat" (
            set /p DOENV="Run environment.bat now? (Y/n): "
            if /i "!DOENV!" neq "n" (
                call "%~dp0environment.bat"
                exit /b 0
            )
        )
        pause
        exit /b 1
    )
)
echo   pip OK.

:: ------------------------------------------------------------------
:: Step 3: pynput
:: ------------------------------------------------------------------
echo [3/3] Checking pynput...
python -c "import pynput" 2>nul
if %errorlevel% neq 0 (
    echo   Installing pynput...
    pip install pynput 2>nul
    if %errorlevel% neq 0 (
        pip install pynput --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>nul
    )
    python -c "import pynput" 2>nul
    if %errorlevel% neq 0 (
        echo.
        echo   Failed to install pynput.
        if exist "%~dp0environment.bat" (
            set /p DOENV="Run environment.bat for auto-setup? (Y/n): "
            if /i "!DOENV!" neq "n" (
                call "%~dp0environment.bat"
                exit /b 0
            )
        )
        pause
        exit /b 1
    )
    echo   pynput installed.
) else (
    echo   pynput already installed.
)

:: ------------------------------------------------------------------
:: Check tkinter
:: ------------------------------------------------------------------
python -c "import tkinter" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo   WARNING: tkinter NOT FOUND
    echo.
    echo   tkinter is required for the GUI.
    echo   Reinstall Python from python.org with "tcl/tk" checked.
    echo.
    pause
    exit /b 1
)

:: ------------------------------------------------------------------
:: Launch
:: ------------------------------------------------------------------
echo.
echo   All checks passed! Starting MacroRecorder...
echo.

python "%~dp0main.py"

if %errorlevel% neq 0 (
    echo.
    echo   MacroRecorder exited with an error.
    pause
)
