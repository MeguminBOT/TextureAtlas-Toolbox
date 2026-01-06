#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Embedded Python distribution builder for TextureAtlas Toolbox.

This script creates a self-contained distribution that includes:
- Embedded Python runtime (no system Python required)
- All required pip packages pre-installed
- Application source code and assets
- Single-click launcher scripts

Usage:
    python build_portable.py [--python-version 3.14.0] [--output-dir dist]

The resulting package can be distributed as an archive that users extract
and run via the included launcher script.

Asset naming pattern (v2.0.0+):
    <AppName>-<OS>-<Arch>-<PackageType>-<Version>.<ext>
    Examples:
        TextureAtlasToolbox-win-x64-embedded-python-v2.0.0.zip
        TextureAtlasToolbox-win-x64-embedded-python-v2.0.0.7z
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

# Configuration
DEFAULT_PYTHON_VERSION = "3.14.0"
PYTHON_EMBED_URL_TEMPLATE = (
    "https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"
)
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# Files and folders to include in the distribution
INCLUDE_FOLDERS = ["src", "assets", "docs", "ImageMagick"]
INCLUDE_FILES = ["LICENSE", "README.md", "latestVersion.txt"]
# Use portable requirements with relaxed version constraints for newer Python compatibility
REQUIREMENTS_FILE = "setup/requirements-portable.txt"
REQUIREMENTS_FILE_FALLBACK = "setup/requirements.txt"

# App info - imported dynamically to get version
APP_NAME = "TextureAtlasToolbox"


def get_app_version(project_root: Path) -> str:
    """Get the app version from src/utils/version.py."""
    version_file = project_root / "src" / "utils" / "version.py"
    if version_file.exists():
        content = version_file.read_text(encoding="utf-8")
        for line in content.split('\n'):
            if line.startswith("APP_VERSION"):
                # Extract version string: APP_VERSION = "2.0.0"
                version = line.split('=')[1].strip().strip('"').strip("'")
                return version
    return "0.0.0"


def get_os_identifier() -> str:
    """Get the OS identifier for the asset name."""
    system = platform.system().lower()
    if system == "windows":
        return "win"
    elif system == "darwin":
        return "mac"
    elif system == "linux":
        return "linux"
    return system


def get_arch_identifier() -> str:
    """Get the architecture identifier for the asset name."""
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        return "x64"
    elif machine in ("arm64", "aarch64"):
        return "arm64"
    elif machine in ("i386", "i686", "x86"):
        return "x86"
    return machine


class PortableBuilder:
    """Builds an embedded Python distribution of TextureAtlas Toolbox."""

    def __init__(
        self,
        project_root: Path,
        output_dir: Path,
        python_version: str = DEFAULT_PYTHON_VERSION,
        verbose: bool = True,
    ):
        self.project_root = project_root
        self.output_dir = output_dir
        self.python_version = python_version
        self.verbose = verbose
        
        # Get app version and build asset name
        self.app_version = get_app_version(project_root)
        self.os_id = get_os_identifier()
        self.arch_id = get_arch_identifier()
        
        # Asset naming: TextureAtlasToolbox-win-x64-embedded-python-v2.0.0
        self.dist_name = f"{APP_NAME}-{self.os_id}-{self.arch_id}-embedded-python-v{self.app_version}"

    def log(self, message: str) -> None:
        if self.verbose:
            print(f"[BUILD] {message}")

    def log_step(self, step: int, total: int, message: str) -> None:
        if self.verbose:
            print(f"\n{'='*60}")
            print(f"  Step {step}/{total}: {message}")
            print(f"{'='*60}")

    def download_file(self, url: str, dest: Path) -> None:
        self.log(f"Downloading: {url}")
        urllib.request.urlretrieve(url, dest)
        self.log(f"Downloaded to: {dest}")

    def build_windows(self) -> Path:
        """Build portable distribution for Windows."""
        total_steps = 7
        dist_path = self.output_dir / self.dist_name
        python_dir = dist_path / "python"
        
        # Clean previous build
        if dist_path.exists():
            self.log(f"Removing previous build: {dist_path}")
            shutil.rmtree(dist_path)
        
        dist_path.mkdir(parents=True, exist_ok=True)

        # Step 1: Download embedded Python
        self.log_step(1, total_steps, "Downloading Embedded Python")
        embed_url = PYTHON_EMBED_URL_TEMPLATE.format(version=self.python_version)
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            embed_zip = tmp_path / "python-embed.zip"
            
            self.download_file(embed_url, embed_zip)
            
            # Extract embedded Python
            self.log("Extracting embedded Python...")
            python_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(embed_zip, 'r') as zf:
                zf.extractall(python_dir)

        # Step 2: Configure embedded Python for pip
        self.log_step(2, total_steps, "Configuring Python for pip support")
        self._configure_embedded_python(python_dir)

        # Step 3: Install pip
        self.log_step(3, total_steps, "Installing pip")
        self._install_pip(python_dir)

        # Step 4: Install requirements
        self.log_step(4, total_steps, "Installing required packages")
        self._install_requirements(python_dir)

        # Step 5: Copy application files
        self.log_step(5, total_steps, "Copying application files")
        self._copy_application_files(dist_path)

        # Step 6: Create launcher scripts
        self.log_step(6, total_steps, "Creating launcher scripts")
        self._create_launcher_scripts(dist_path)

        # Step 7: Create archives (ZIP and 7z)
        self.log_step(7, total_steps, "Creating distribution archives")
        zip_path, sevenz_path = self._create_archive(dist_path)

        self.log(f"\n{'='*60}")
        self.log("BUILD COMPLETE!")
        self.log(f"Distribution folder: {dist_path}")
        self.log(f"ZIP archive: {zip_path}")
        if sevenz_path:
            self.log(f"7z archive: {sevenz_path}")
        self.log(f"{'='*60}\n")

        return zip_path

    def _configure_embedded_python(self, python_dir: Path) -> None:
        """Configure embedded Python to support pip and site-packages."""
        # Find the ._pth file (e.g., python312._pth)
        pth_files = list(python_dir.glob("python*._pth"))
        if not pth_files:
            raise FileNotFoundError("Could not find Python ._pth file")
        
        pth_file = pth_files[0]
        self.log(f"Configuring: {pth_file.name}")

        # Rewrite the ._pth file with our required configuration
        # The ._pth file controls Python's sys.path in embedded mode
        # We need:
        # 1. The standard pythonXXX.zip for stdlib
        # 2. Lib/site-packages for pip packages
        # 3. . for current directory
        # 4. ../src so app modules are importable from python/ dir
        # 5. import site to enable site-packages mechanism
        
        # Extract python version from filename (e.g., python314._pth -> 314)
        pth_stem = pth_file.stem  # e.g., "python314"
        version_suffix = pth_stem.replace("python", "")  # e.g., "314"
        
        pth_content = f"""{pth_stem}.zip
Lib/site-packages
.
../src
import site
"""
        pth_file.write_text(pth_content, encoding="utf-8")
        self.log("Configured Python path:")
        self.log(f"  - {pth_stem}.zip (standard library)")
        self.log("  - Lib/site-packages (pip packages)")
        self.log("  - . (current directory)")
        self.log("  - ../src (application modules)")
        self.log("  - import site (enable site mechanism)")
        
        # Create the Lib/site-packages directory
        site_packages = python_dir / "Lib" / "site-packages"
        site_packages.mkdir(parents=True, exist_ok=True)
        self.log(f"Created: {site_packages}")

    def _install_pip(self, python_dir: Path) -> None:
        """Install pip into the embedded Python."""
        python_exe = python_dir / "python.exe"
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            get_pip_path = Path(tmp_dir) / "get-pip.py"
            self.download_file(GET_PIP_URL, get_pip_path)
            
            self.log("Running get-pip.py...")
            result = subprocess.run(
                [str(python_exe), str(get_pip_path), "--no-warn-script-location"],
                capture_output=True,
                text=True,
                cwd=python_dir,
            )
            
            if result.returncode != 0:
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                raise RuntimeError("Failed to install pip")
            
            self.log("pip installed successfully")

    def _install_requirements(self, python_dir: Path) -> None:
        """Install required packages from requirements.txt."""
        python_exe = python_dir / "python.exe"
        
        # Try portable requirements first, then fall back to standard
        requirements_path = self.project_root / REQUIREMENTS_FILE
        if not requirements_path.exists():
            requirements_path = self.project_root / REQUIREMENTS_FILE_FALLBACK
        
        if not requirements_path.exists():
            raise FileNotFoundError(f"Requirements file not found: {requirements_path}")
        
        self.log(f"Installing packages from: {requirements_path}")
        self.log("Using binary-only packages (no source builds)...")
        
        # Use pip to install requirements with binary-only preference
        # This avoids needing compilers for source builds
        result = subprocess.run(
            [
                str(python_exe),
                "-m", "pip",
                "install",
                "-r", str(requirements_path),
                "--only-binary", ":all:",
                "--no-warn-script-location",
                "--disable-pip-version-check",
            ],
            capture_output=True,
            text=True,
            cwd=python_dir,
        )
        
        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            raise RuntimeError("Failed to install requirements")
        
        self.log("All packages installed successfully")
        
        # List installed packages for verification
        result = subprocess.run(
            [str(python_exe), "-m", "pip", "list", "--format=columns"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            self.log("Installed packages:")
            for line in result.stdout.strip().split('\n'):
                self.log(f"  {line}")

    def _copy_application_files(self, dist_path: Path) -> None:
        """Copy application source code and assets to distribution."""
        # Copy folders
        for folder_name in INCLUDE_FOLDERS:
            src_folder = self.project_root / folder_name
            if src_folder.exists():
                dst_folder = dist_path / folder_name
                self.log(f"Copying folder: {folder_name}/")
                shutil.copytree(
                    src_folder,
                    dst_folder,
                    ignore=shutil.ignore_patterns(
                        "__pycache__",
                        "*.pyc",
                        "*.pyo",
                        ".git",
                        ".pytest_cache",
                        ".ruff_cache",
                        "app_config.cfg",  # Exclude user config file
                    ),
                )
            else:
                self.log(f"Warning: Folder not found, skipping: {folder_name}/")
        
        # Copy individual files
        for file_name in INCLUDE_FILES:
            src_file = self.project_root / file_name
            if src_file.exists():
                dst_file = dist_path / file_name
                self.log(f"Copying file: {file_name}")
                shutil.copy2(src_file, dst_file)
            else:
                self.log(f"Warning: File not found, skipping: {file_name}")

    def _create_launcher_scripts(self, dist_path: Path) -> None:
        """Create launcher scripts for the application."""
        # Main launcher - uses pythonw.exe for no console window
        bat_content = r'''@echo off
cd /d "%~dp0"

:: TextureAtlas Toolbox Launcher
:: This script launches the application using the bundled Python runtime.
:: Uses pythonw.exe for a clean launch without console window.

:: Check if bundled Python exists
if not exist "python\pythonw.exe" (
    echo ERROR: Bundled Python not found!
    echo Please make sure you extracted all files correctly.
    pause
    exit /b 1
)

:: Launch the application silently (no console)
start "" "python\pythonw.exe" "src\Main.py" %*
'''
        bat_path = dist_path / "TextureAtlas Toolbox.bat"
        bat_path.write_text(bat_content, encoding="utf-8")
        self.log(f"Created: {bat_path.name}")

        # Debug launcher - uses python.exe with console for troubleshooting
        debug_bat_content = r'''@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: TextureAtlas Toolbox Debug Launcher
:: This launcher keeps the console window open to show any errors.
:: Use this for troubleshooting if the app doesn't start correctly.

title TextureAtlas Toolbox (Debug Mode)

echo ============================================================
echo  TextureAtlas Toolbox - Debug Mode
echo ============================================================
echo.
echo Python executable: python\python.exe
echo.

"python\python.exe" --version
echo.

echo Starting application...
echo.

"python\python.exe" "src\Main.py" %*

echo.
echo ============================================================
echo  Application has exited.
echo ============================================================
pause
'''
        debug_bat_path = dist_path / "TextureAtlas Toolbox Debug.bat"
        debug_bat_path.write_text(debug_bat_content, encoding="utf-8")
        self.log(f"Created: {debug_bat_path.name}")

    def _create_archive(self, dist_path: Path) -> tuple[Path, Path | None]:
        """Create ZIP and 7z archives of the distribution.
        
        Returns:
            Tuple of (zip_path, sevenz_path). sevenz_path is None if 7z is not available.
        """
        zip_path = self.output_dir / f"{self.dist_name}.zip"
        sevenz_path = self.output_dir / f"{self.dist_name}.7z"
        
        # Remove existing archives
        for path in (zip_path, sevenz_path):
            if path.exists():
                path.unlink()
        
        # Create ZIP archive
        self.log(f"Creating ZIP archive: {zip_path.name}")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
            for root, dirs, files in os.walk(dist_path):
                # Skip __pycache__ directories
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(self.output_dir)
                    zf.write(file_path, arc_name)
        
        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        self.log(f"ZIP archive size: {zip_size_mb:.2f} MB")
        
        # Try to create 7z archive (requires 7z to be installed)
        sevenz_created = self._create_7z_archive(dist_path, sevenz_path)
        
        return zip_path, sevenz_path if sevenz_created else None

    def _create_7z_archive(self, dist_path: Path, sevenz_path: Path) -> bool:
        """Create a 7z archive using the 7z command-line tool.
        
        Returns:
            True if successful, False if 7z is not available.
        """
        # Try to find 7z executable
        sevenz_cmd = None
        
        if platform.system() == "Windows":
            # Common 7z locations on Windows
            possible_paths = [
                r"C:\Program Files\7-Zip\7z.exe",
                r"C:\Program Files (x86)\7-Zip\7z.exe",
                shutil.which("7z"),
                shutil.which("7za"),
            ]
            for path in possible_paths:
                if path and Path(path).exists():
                    sevenz_cmd = path
                    break
        else:
            # On Unix, try 7z or 7za
            sevenz_cmd = shutil.which("7z") or shutil.which("7za")
        
        if not sevenz_cmd:
            self.log("7z not found - skipping 7z archive creation")
            self.log("Install 7-Zip to also generate .7z archives")
            return False
        
        self.log(f"Creating 7z archive: {sevenz_path.name}")
        
        try:
            # Use 7z to create archive with maximum compression
            # -t7z: 7z archive type
            # -mx=9: maximum compression
            # -mfb=273: maximum fast bytes for LZMA2
            # -ms=on: solid archive
            result = subprocess.run(
                [
                    sevenz_cmd,
                    "a",           # add to archive
                    "-t7z",        # 7z format
                    "-mx=9",       # maximum compression
                    "-mfb=273",    # fast bytes
                    "-ms=on",      # solid archive
                    str(sevenz_path),
                    str(dist_path),
                ],
                capture_output=True,
                text=True,
                cwd=self.output_dir,
            )
            
            if result.returncode != 0:
                self.log(f"7z creation failed: {result.stderr}")
                return False
            
            sevenz_size_mb = sevenz_path.stat().st_size / (1024 * 1024)
            self.log(f"7z archive size: {sevenz_size_mb:.2f} MB")
            return True
            
        except Exception as e:
            self.log(f"7z creation failed: {e}")
            return False

    def build_unix(self) -> Path:
        """Build portable distribution for macOS/Linux."""
        total_steps = 6
        dist_path = self.output_dir / self.dist_name
        
        # Clean previous build
        if dist_path.exists():
            self.log(f"Removing previous build: {dist_path}")
            shutil.rmtree(dist_path)
        
        dist_path.mkdir(parents=True, exist_ok=True)

        # Step 1: Create virtual environment with system Python
        self.log_step(1, total_steps, "Creating Python virtual environment")
        venv_path = dist_path / "python"
        self._create_venv(venv_path)

        # Step 2: Install requirements
        self.log_step(2, total_steps, "Installing required packages")
        self._install_requirements_unix(venv_path)

        # Step 3: Copy application files
        self.log_step(3, total_steps, "Copying application files")
        self._copy_application_files(dist_path)

        # Step 4: Create launcher scripts
        self.log_step(4, total_steps, "Creating launcher scripts")
        self._create_unix_launcher_scripts(dist_path)

        # Step 5: Create portable Python download script
        self.log_step(5, total_steps, "Creating Python setup script")
        self._create_unix_setup_script(dist_path)

        # Step 6: Create archive
        self.log_step(6, total_steps, "Creating distribution archive")
        archive_path = self._create_tar_archive(dist_path)

        self.log(f"\n{'='*60}")
        self.log("BUILD COMPLETE!")
        self.log(f"Distribution folder: {dist_path}")
        self.log(f"Distribution archive: {archive_path}")
        self.log(f"{'='*60}\n")

        return archive_path

    def _create_venv(self, venv_path: Path) -> None:
        """Create a virtual environment."""
        import venv
        self.log(f"Creating venv at: {venv_path}")
        venv.create(venv_path, with_pip=True, clear=True)

    def _install_requirements_unix(self, venv_path: Path) -> None:
        """Install requirements in Unix virtual environment."""
        if platform.system() == "Windows":
            pip_exe = venv_path / "Scripts" / "pip.exe"
        else:
            pip_exe = venv_path / "bin" / "pip"
        
        requirements_path = self.project_root / REQUIREMENTS_FILE
        
        self.log(f"Installing packages from: {requirements_path}")
        
        result = subprocess.run(
            [str(pip_exe), "install", "-r", str(requirements_path)],
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print(f"STDERR: {result.stderr}")
            raise RuntimeError("Failed to install requirements")
        
        self.log("All packages installed successfully")

    def _create_unix_launcher_scripts(self, dist_path: Path) -> None:
        """Create Unix launcher scripts."""
        # Main launcher script
        sh_content = '''#!/bin/bash

# TextureAtlas Toolbox Launcher
# This script launches the application using the bundled Python environment.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check for bundled Python venv
if [ -f "python/bin/python" ]; then
    PYTHON_EXE="python/bin/python"
elif [ -f "python/bin/python3" ]; then
    PYTHON_EXE="python/bin/python3"
else
    echo "ERROR: Bundled Python not found!"
    echo "Please run setup.sh first to configure Python."
    exit 1
fi

# Set PYTHONPATH so Python can find modules in src/
export PYTHONPATH="$SCRIPT_DIR/src"

echo "Starting TextureAtlas Toolbox..."
exec "$PYTHON_EXE" "src/Main.py" "$@"
'''
        sh_path = dist_path / "TextureAtlas Toolbox.sh"
        sh_path.write_text(sh_content, encoding="utf-8")
        sh_path.chmod(0o755)
        self.log(f"Created: {sh_path.name}")

        # Simple start script
        start_sh_content = '''#!/bin/bash
# Simple launcher - redirects to main launcher
exec "$(dirname "$0")/TextureAtlas Toolbox.sh" "$@"
'''
        start_sh_path = dist_path / "start.sh"
        start_sh_path.write_text(start_sh_content, encoding="utf-8")
        start_sh_path.chmod(0o755)
        self.log(f"Created: {start_sh_path.name}")

    def _create_unix_setup_script(self, dist_path: Path) -> None:
        """Create a setup script for Unix that ensures Python dependencies."""
        setup_content = '''#!/bin/bash

# TextureAtlas Toolbox - First-time Setup
# Run this script once after extracting if the launcher doesn't work.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " TextureAtlas Toolbox - Setup"
echo "============================================================"
echo

# Check for Python 3
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Python 3 is not installed."
    echo "Please install Python 3.10 or later from your package manager:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora: sudo dnf install python3"
    echo "  macOS: brew install python3"
    exit 1
fi

# Check Python version
PY_VERSION=$($PYTHON_CMD -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Found Python $PY_VERSION"

# Create virtual environment if it doesn't exist
if [ ! -d "python" ]; then
    echo "Creating Python virtual environment..."
    $PYTHON_CMD -m venv python
fi

# Activate and install requirements
echo "Installing required packages..."
source python/bin/activate
pip install --upgrade pip
pip install -r setup/requirements.txt

echo
echo "============================================================"
echo " Setup complete! You can now run: ./TextureAtlas Toolbox.sh"
echo "============================================================"
'''
        setup_path = dist_path / "setup.sh"
        setup_path.write_text(setup_content, encoding="utf-8")
        setup_path.chmod(0o755)
        self.log(f"Created: {setup_path.name}")

        # Also copy requirements.txt to the dist
        requirements_src = self.project_root / REQUIREMENTS_FILE
        requirements_dst = dist_path / "setup" / "requirements.txt"
        requirements_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(requirements_src, requirements_dst)

    def _create_tar_archive(self, dist_path: Path) -> Path:
        """Create a tar.gz archive of the distribution."""
        import tarfile
        
        archive_name = f"{self.dist_name}.tar.gz"
        archive_path = self.output_dir / archive_name
        
        if archive_path.exists():
            archive_path.unlink()
        
        self.log(f"Creating archive: {archive_name}")
        
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(dist_path, arcname=dist_path.name)
        
        size_mb = archive_path.stat().st_size / (1024 * 1024)
        self.log(f"Archive size: {size_mb:.2f} MB")
        
        return archive_path

    def build(self) -> Path:
        """Build for the current platform."""
        if platform.system() == "Windows":
            return self.build_windows()
        else:
            return self.build_unix()


def main():
    parser = argparse.ArgumentParser(
        description="Build a portable distribution of TextureAtlas Toolbox"
    )
    parser.add_argument(
        "--python-version",
        default=DEFAULT_PYTHON_VERSION,
        help=f"Python version for embedded runtime (default: {DEFAULT_PYTHON_VERSION})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for the distribution (default: _build-output/portable)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )
    
    args = parser.parse_args()
    
    # Determine project root (parent of setup/)
    script_path = Path(__file__).resolve()
    project_root = script_path.parent.parent
    
    # Default output directory
    if args.output_dir is None:
        output_dir = project_root / "_build-output" / "portable"
    else:
        output_dir = args.output_dir.resolve()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Get app version for display
    app_version = get_app_version(project_root)
    
    print(f"\n{'='*60}")
    print("  TextureAtlas Toolbox - Embedded Python Distribution Builder")
    print(f"{'='*60}")
    print(f"  Project root: {project_root}")
    print(f"  Output directory: {output_dir}")
    print(f"  App version: v{app_version}")
    print(f"  Python version: {args.python_version}")
    print(f"  Target platform: {platform.system()} ({get_os_identifier()}-{get_arch_identifier()})")
    print(f"{'='*60}\n")
    
    builder = PortableBuilder(
        project_root=project_root,
        output_dir=output_dir,
        python_version=args.python_version,
        verbose=not args.quiet,
    )
    
    print(f"  Output name: {builder.dist_name}")
    print()
    
    try:
        archive_path = builder.build()
        print(f"\nSuccess! Distribution created at:\n  {archive_path}")
        return 0
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
