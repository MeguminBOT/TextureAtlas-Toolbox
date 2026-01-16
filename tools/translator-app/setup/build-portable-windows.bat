@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================================
echo  Translation Editor - Embedded Python Distribution Builder
echo ============================================================
echo.
echo  This script builds a portable distribution of Translation Editor
echo  with an embedded Python runtime.
echo.
echo  The output will be placed in: _build-output\portable
echo ============================================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo Please install Python 3.10 or later.
    pause
    exit /b 1
)

:: Run the build script
python build_portable.py %*

if errorlevel 1 (
    echo.
    echo Build failed!
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
pause
