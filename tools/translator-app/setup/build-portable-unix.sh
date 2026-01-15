#!/bin/bash

# Translation Editor - Embedded Python Distribution Builder
# This script builds a portable distribution with bundled Python.

echo "============================================================"
echo "  Translation Editor - Embedded Python Distribution Builder"
echo "============================================================"
echo ""

# Change to script directory
cd "$(dirname "$0")"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed!"
    echo "Please install Python 3.10 or later."
    exit 1
fi

# Run the build script
python3 build_portable.py "$@"

exit_code=$?

if [ $exit_code -ne 0 ]; then
    echo ""
    echo "Build failed!"
    exit $exit_code
fi

echo ""
echo "Build completed successfully!"
