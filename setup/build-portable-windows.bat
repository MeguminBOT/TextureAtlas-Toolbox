@echo off
cd /d "%~dp0.."
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo  TextureAtlas Toolbox - Portable Distribution Builder
echo ============================================================
echo.
echo  This script creates a portable distribution that includes:
echo    - Embedded Python runtime (no installation required)
echo    - All required packages pre-installed
echo    - Single-click launcher scripts
echo.
echo  The output will be placed in '_build-output\portable'
echo ============================================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH.
    echo Please install Python 3.10 or later to build the distribution.
    pause
    exit /b 1
)

:: Show Python version
for /f "delims=" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo Using: %PYVER%
echo.

:: Optional: Allow specifying Python version
set "PY_VERSION=3.14.0"
if not "%~1"=="" set "PY_VERSION=%~1"

echo Target embedded Python version: %PY_VERSION%
echo.

choice /m "Do you wish to proceed with building the portable distribution?"
if errorlevel 2 (
    echo Cancelled.
    exit /b 0
)

echo.
echo Starting build process...
echo.

:: Run the Python build script
python setup\build_portable.py --python-version %PY_VERSION%

if errorlevel 1 (
    echo.
    echo ============================================================
    echo  BUILD FAILED
    echo ============================================================
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  BUILD COMPLETE
echo ============================================================
echo.
echo The portable distribution has been created in:
echo   _build-output\portable\
echo.
echo You can now distribute the ZIP file to users.
echo.
pause
