#!/bin/bash

# TextureAtlas Toolbox - Portable Distribution Builder
# This script creates a portable distribution for macOS/Linux.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "============================================================"
echo " TextureAtlas Toolbox - Portable Distribution Builder"
echo "============================================================"
echo
echo " This script creates a portable distribution that includes:"
echo "   - Python virtual environment with all dependencies"
echo "   - Single-click launcher scripts"
echo "   - Setup script for first-time configuration"
echo
echo " The output will be placed in '_build-output/portable'"
echo "============================================================"
echo

# Check for Python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python 3.10 or later."
    exit 1
fi

# Show Python version
PY_VERSION=$($PYTHON_CMD --version)
echo "Using: $PY_VERSION"
echo

# Confirm
read -p "Do you wish to proceed with building the portable distribution? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo
echo "Starting build process..."
echo

# Run the Python build script
$PYTHON_CMD setup/build_portable.py

if [ $? -ne 0 ]; then
    echo
    echo "============================================================"
    echo " BUILD FAILED"
    echo "============================================================"
    exit 1
fi

echo
echo "============================================================"
echo " BUILD COMPLETE"
echo "============================================================"
echo
echo "The portable distribution has been created in:"
echo "  _build-output/portable/"
echo
echo "You can now distribute the tar.gz file to users."
echo
