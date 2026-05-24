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
if errorlevel 1 goto nopython

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   Python %PYVER% - OK

:: ==================================================================
:: Check pip
:: ==================================================================
pip --version >nul 2>&1
if errorlevel 1 (
    echo   pip missing, repairing...
    python -m ensurepip --upgrade >nul 2>&1
    pip --version >nul 2>&1
    if errorlevel 1 goto piperr
)
echo   pip - OK

:: ==================================================================
:: Check pynput
:: ==================================================================
python -c "import pynput" 2>nul
if errorlevel 1 (
    echo   Installing pynput...
    pip install pynput 2>nul
    if errorlevel 1 pip install pynput --trusted-host pypi.org --trusted-host files.pythonhosted.org 2>nul
    python -c "import pynput" 2>nul
    if errorlevel 1 goto pynputerr
    echo   pynput installed.
) else (
    echo   pynput - OK
)

:: ==================================================================
:: Check tkinter
:: ==================================================================
python -c "import tkinter" 2>nul
if errorlevel 1 goto notk

:: ==================================================================
:: Launch
:: ==================================================================
echo.
echo   Starting MacroRecorder...
echo.
python "%~dp0main.py"
if errorlevel 1 (
    echo.
    echo   MacroRecorder exited with an error.
    pause
)
exit /b 0

:: ==================================================================
:: Error handlers (labels must be at top level, not inside blocks)
:: ==================================================================
:nopython
echo   Python NOT found.
echo.
echo   MacroRecorder requires Python 3.7+.
echo.
if exist "%~dp0environment.bat" (
    set /p DOENV="Run environment.bat for auto-install? [Y/n]: "
    if /i "!DOENV!"=="n" goto nopython_manual
    if /i "!DOENV!"=="N" goto nopython_manual
    call "%~dp0environment.bat"
    exit /b 0
)
:nopython_manual
echo   Download: https://www.python.org/downloads/
echo   IMPORTANT: Check "Add Python to PATH" during install.
pause
exit /b 1

:piperr
echo   Could not repair pip. Try running environment.bat
pause
exit /b 1

:pynputerr
echo   Failed to install pynput. Try running environment.bat
pause
exit /b 1

:notk
echo   tkinter NOT found.
echo   Reinstall Python from python.org with "tcl/tk" option.
pause
exit /b 1
