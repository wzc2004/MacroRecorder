@echo off
setlocal enabledelayedexpansion
title MacroRecorder

cd /d "%~dp0"

echo ============================================
echo   MacroRecorder
echo ============================================
echo.

:: ==================================================================
:: Check Python
:: ==================================================================
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   Python NOT found.
    echo.
    echo   MacroRecorder requires Python 3.7+.
    echo.
    if exist "%~dp0environment.bat" (
        echo   Option 1: Run environment.bat (auto-install)
        echo   Option 2: Install manually from python.org
        echo.
        :askenv
        set /p DOENV="Run environment.bat now? [Y/n]: "
        if /i "!DOENV!"=="n" goto noenv
        if /i "!DOENV!"=="N" goto noenv
        if /i "!DOENV!"=="" goto runenv
        if /i "!DOENV!"=="y" goto runenv
        if /i "!DOENV!"=="Y" goto runenv
        echo Please answer Y or n.
        goto askenv
        :runenv
        call "%~dp0environment.bat"
        exit /b 0
        :noenv
    )
    echo   Download: https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python %PYVER% - OK

:: ==================================================================
:: Check pip
:: ==================================================================
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   pip missing, repairing...
    python -m ensurepip --upgrade >nul 2>&1
    pip --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo   Could not repair pip. Try running environment.bat
        pause
        exit /b 1
    )
)
echo   pip - OK

:: ==================================================================
:: Check pynput
:: ==================================================================
python -c "import pynput" 2>nul
if %errorlevel% neq 0 (
    echo   Installing pynput...
    pip install pynput 2>nul
    if %errorlevel% neq 0 (
        pip install pynput --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>nul
    )
    python -c "import pynput" 2>nul
    if %errorlevel% neq 0 (
        echo   Failed to install pynput. Try running environment.bat
        pause
        exit /b 1
    )
    echo   pynput installed.
) else (
    echo   pynput - OK
)

:: ==================================================================
:: Check tkinter
:: ==================================================================
python -c "import tkinter" 2>nul
if %errorlevel% neq 0 (
    echo   tkinter NOT found.
    echo   Reinstall Python from python.org with "tcl/tk" option.
    pause
    exit /b 1
)

:: ==================================================================
:: Launch
:: ==================================================================
echo.
echo   Starting MacroRecorder...
echo   (Switch to your target window within 5 seconds after recording)
echo.

python "%~dp0main.py"

if %errorlevel% neq 0 (
    echo.
    echo   MacroRecorder exited with an error (code: %errorlevel%).
    pause
)
