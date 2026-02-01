#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Embedded Python distribution builder for Translation Editor.

This script creates a self-contained distribution that includes:
- Embedded Python runtime (no system Python required)
- All required pip packages pre-installed
- Application source code and assets
- Single-click launcher scripts

Usage:
    python build_portable.py [--python-version 3.14.0] [--output-dir dist]

The resulting package can be distributed as an archive that users extract
and run via the included launcher script.

Asset naming pattern:
    <AppName>-<OS>-<Arch>-<PackageType>-<Version>.<ext>
    Examples:
        TranslationEditor-win-x64-embedded-python-v1.1.0.zip
        TranslationEditor-win-x64-embedded-python-v1.1.0.7z
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
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
INCLUDE_FOLDERS = ["src", "templates"]
INCLUDE_FILES = ["README.md"]

# Requirements for the Translation Editor (PySide6 + optional requests)
REQUIRED_PACKAGES = [
    "PySide6>=6.9.2",
    "requests>=2.32.3",  # Optional but useful for translation services
    "certifi>=2024.8.30",
    "charset-normalizer>=3.4.0",
    "idna>=3.10",
    "urllib3>=2.2.3",
]

# App info
APP_NAME = "TranslationEditor"
DISPLAY_NAME = "Translation Editor"


def get_app_version(project_root: Path) -> str:
    """Get the app version from src/Main.py."""
    main_file = project_root / "src" / "Main.py"
    if main_file.exists():
        content = main_file.read_text(encoding="utf-8")
        # Look for: app.setApplicationVersion("1.1.0")
        match = re.search(r'setApplicationVersion\(["\']([^"\']+)["\']\)', content)
        if match:
            return match.group(1)
    return "1.0.0"


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
    """Builds an embedded Python distribution of Translation Editor."""

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

        # Archive naming: TranslationEditor-win-x64-embedded-python-v1.1.0
        self.archive_name = f"{APP_NAME}-{self.os_id}-{self.arch_id}-embedded-python-v{self.app_version}"
        # Folder name inside archive: user-friendly name
        self.dist_name = DISPLAY_NAME

    def log(self, message: str) -> None:
        if self.verbose:
            print(f"[BUILD] {message}", flush=True)

    def log_step(self, step: int, total: int, message: str) -> None:
        if self.verbose:
            print(f"\n{'='*60}", flush=True)
            print(f"  Step {step}/{total}: {message}", flush=True)
            print(f"{'='*60}", flush=True)

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
            with zipfile.ZipFile(embed_zip, "r") as zf:
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
        # Find the ._pth file (e.g., python314._pth)
        pth_files = list(python_dir.glob("python*._pth"))
        if not pth_files:
            raise FileNotFoundError("Could not find Python ._pth file")

        pth_file = pth_files[0]
        self.log(f"Configuring: {pth_file.name}")

        # Extract python version from filename (e.g., python314._pth -> python314)
        pth_stem = pth_file.stem

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
        """Install required packages."""
        python_exe = python_dir / "python.exe"
        site_packages = python_dir / "Lib" / "site-packages"

        self.log("Installing packages...")
        self.log("Using binary-only packages (no source builds)...")

        # Environment to disable user site-packages
        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"
        env["PIP_NO_CACHE_DIR"] = "1"

        # Install packages
        result = subprocess.run(
            [
                str(python_exe),
                "-m",
                "pip",
                "install",
                *REQUIRED_PACKAGES,
                "--target",
                str(site_packages),
                "--only-binary",
                ":all:",
                "--no-warn-script-location",
                "--disable-pip-version-check",
            ],
            capture_output=True,
            text=True,
            cwd=python_dir,
            env=env,
        )

        if result.returncode != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            raise RuntimeError("Failed to install requirements")

        self.log("All packages installed successfully")

        # List installed packages for verification
        result = subprocess.run(
            [
                str(python_exe),
                "-m",
                "pip",
                "list",
                "--format=columns",
                "--path",
                str(site_packages),
            ],
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode == 0:
            self.log("Installed packages:")
            for line in result.stdout.strip().split("\n"):
                self.log(f"  {line}")

        # Strip unnecessary PySide6 components to reduce size
        self._strip_pyside6(site_packages)

        # Verify critical packages are importable
        self._verify_critical_packages(python_exe)

    def _strip_pyside6(self, site_packages: Path) -> None:
        """Remove unnecessary PySide6 components to reduce distribution size.

        Translation Editor only uses QtCore, QtGui, and QtWidgets.
        """
        pyside6_dir = site_packages / "PySide6"
        if not pyside6_dir.exists():
            return

        self.log("Stripping unnecessary PySide6 components...")

        # Get size before cleanup
        size_before = sum(
            f.stat().st_size for f in pyside6_dir.rglob("*") if f.is_file()
        )

        # Executables/tools to remove
        # Keep: lrelease.exe, lupdate.exe (needed for .ts/.qm translation workflow)
        remove_executables = [
            "assistant.exe",
            "designer.exe",
            "linguist.exe",
            "qmllint.exe",
            "qmlls.exe",
            "qmlformat.exe",
            "qmlcachegen.exe",
            "qmltyperegistrar.exe",
            "qmlimportscanner.exe",
            "balsam.exe",
            "balsamui.exe",
            "qsb.exe",
            "rcc.exe",
            "uic.exe",
            "svgtoqml.exe",
            "QtWebEngineProcess.exe",
        ]

        # DLLs to remove (Qt modules we don't use)
        # Keep: Qt6Core, Qt6Gui, Qt6Widgets and their dependencies
        # Keep: Qt6Network (internal dependency for QtWidgets/QtGui)
        # Keep: Qt6Svg (used for SVG icon rendering)
        # Keep: Qt6Xml (needed by lrelease/lupdate for parsing .ts XML files)
        # Keep: Qt6Qml, Qt6QmlCore, Qt6QmlMeta, Qt6QmlModels (required by lupdate.exe)
        remove_dll_patterns = [
            "Qt63D",
            "Qt6Bluetooth",
            "Qt6Charts",
            "Qt6DataVisualization",
            "Qt6Designer",
            "Qt6Graphs",
            "Qt6Help",
            "Qt6HttpServer",
            "Qt6Labs",
            "Qt6Location",
            "Qt6Multimedia",
            # Qt6Network - KEEP: Internal dependency for QtWidgets
            "Qt6Nfc",
            "Qt6OpenGL",
            "Qt6Pdf",
            "Qt6Positioning",
            # Qt6Qml - KEEP: Required by lupdate.exe
            "Qt6Quick",
            "Qt6RemoteObjects",
            "Qt6Scxml",
            "Qt6Sensors",
            "Qt6SerialBus",
            "Qt6SerialPort",
            "Qt6ShaderTools",
            "Qt6SpatialAudio",
            "Qt6Sql",
            "Qt6StateMachine",
            # Qt6Svg - KEEP: Used for SVG icon rendering
            "Qt6Test",
            "Qt6TextToSpeech",
            "Qt6VirtualKeyboard",
            "Qt6WebChannel",
            "Qt6WebEngine",
            "Qt6WebSockets",
            "Qt6WebView",
        ]

        # Python bindings to remove (.pyd and .pyi files)
        # Keep: QtCore, QtGui, QtWidgets (main app)
        # Keep: QtNetwork (internal dependency for QtWidgets)
        # Keep: QtSvg, QtSvgWidgets (SVG icon support)
        # Keep: QtPrintSupport (QtWidgets print dialog dependency)
        # Keep: QtXml (lrelease/lupdate dependency)
        remove_binding_patterns = [
            "Qt3D",
            "QtBluetooth",
            "QtCharts",
            "QtConcurrent",
            "QtDataVisualization",
            "QtDBus",
            "QtDesigner",
            "QtGraphs",
            "QtHelp",
            "QtHttpServer",
            "QtLocation",
            "QtMultimedia",
            # QtNetwork - KEEP: Internal dependency
            "QtNfc",
            "QtOpenGL",
            "QtPdf",
            "QtPositioning",
            # QtPrintSupport - KEEP: QtWidgets dependency
            "QtQml",
            "QtQuick",
            "QtRemoteObjects",
            "QtScxml",
            "QtSensors",
            "QtSerialBus",
            "QtSerialPort",
            "QtSpatialAudio",
            "QtSql",
            "QtStateMachine",
            # QtSvg - KEEP: SVG icon support
            # QtSvgWidgets - KEEP: SVG icon support
            "QtTest",
            "QtTextToSpeech",
            "QtUiTools",
            "QtWebChannel",
            "QtWebEngine",
            "QtWebSockets",
            "QtWebView",
            # QtXml - KEEP: lrelease/lupdate dependency
            "QtAxContainer",
        ]

        # Directories to remove entirely
        remove_dirs = [
            "qml",
            "translations",
            "resources",
            "typesystems",
            "glue",
            "include",
            "metatypes",
            "doc",
        ]

        removed_count = 0
        removed_size = 0

        # Remove executables
        for exe in remove_executables:
            exe_path = pyside6_dir / exe
            if exe_path.exists():
                removed_size += exe_path.stat().st_size
                exe_path.unlink()
                removed_count += 1

        # Remove DLLs by pattern
        for pattern in remove_dll_patterns:
            for dll in pyside6_dir.glob(f"{pattern}*.dll"):
                removed_size += dll.stat().st_size
                dll.unlink()
                removed_count += 1

        # Remove Python bindings (.pyd and .pyi files)
        for pattern in remove_binding_patterns:
            for ext in [".pyd", ".pyi"]:
                binding = pyside6_dir / f"{pattern}{ext}"
                if binding.exists():
                    removed_size += binding.stat().st_size
                    binding.unlink()
                    removed_count += 1

        # Remove directories
        for dirname in remove_dirs:
            dir_path = pyside6_dir / dirname
            if dir_path.exists() and dir_path.is_dir():
                dir_size = sum(
                    f.stat().st_size for f in dir_path.rglob("*") if f.is_file()
                )
                removed_size += dir_size
                for attempt in range(3):
                    try:
                        shutil.rmtree(dir_path)
                        break
                    except PermissionError:
                        if attempt < 2:
                            time.sleep(0.5)
                        else:
                            raise
                removed_count += 1

        # Remove ffmpeg/multimedia DLLs
        for dll in pyside6_dir.glob("av*.dll"):
            removed_size += dll.stat().st_size
            dll.unlink()
            removed_count += 1
        for dll in pyside6_dir.glob("sw*.dll"):
            removed_size += dll.stat().st_size
            dll.unlink()
            removed_count += 1

        # Get size after cleanup
        size_after = sum(
            f.stat().st_size for f in pyside6_dir.rglob("*") if f.is_file()
        )

        saved_mb = (size_before - size_after) / (1024 * 1024)
        self.log(f"  Removed {removed_count} items, saved {saved_mb:.1f} MB")
        self.log(
            f"  PySide6 size: {size_before / (1024*1024):.1f} MB -> "
            f"{size_after / (1024*1024):.1f} MB"
        )

    def _verify_critical_packages(self, python_exe: Path) -> None:
        """Verify that critical packages are importable."""
        critical_packages = [
            "PySide6.QtCore",
            "PySide6.QtGui",
            "PySide6.QtWidgets",
            "PySide6.QtNetwork",  # Internal dependency for QtWidgets
            "PySide6.QtSvg",  # SVG icon support
            "PySide6.QtXml",  # Required by lupdate/lrelease for .ts parsing
            "requests",
            "urllib3",
            "certifi",
        ]

        env = os.environ.copy()
        env["PYTHONNOUSERSITE"] = "1"

        self.log("Verifying critical packages are importable...")
        failed_packages = []

        for package in critical_packages:
            result = subprocess.run(
                [str(python_exe), "-c", f"import {package}; print('{package} OK')"],
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                failed_packages.append(package)
                self.log(f"  [FAIL] {package}: {result.stderr.strip()}")
            else:
                self.log(f"  [OK] {package}")

        if failed_packages:
            raise RuntimeError(
                f"Critical packages failed to import: {', '.join(failed_packages)}\n"
                "The portable build may be incomplete or corrupted."
            )

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
                        "*_crash.log",
                        "*_unused_strings.txt",
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
        bat_content = r"""@echo off
cd /d "%~dp0"

:: Translation Editor Launcher
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
"""
        bat_path = dist_path / "Translation Editor.bat"
        bat_path.write_text(bat_content, encoding="utf-8")
        self.log(f"Created: {bat_path.name}")

        # Debug launcher - uses python.exe with console for troubleshooting
        debug_bat_content = r"""@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: Translation Editor Debug Launcher
:: This launcher keeps the console window open to show any errors.
:: Use this for troubleshooting if the app doesn't start correctly.

title Translation Editor (Debug Mode)

echo ============================================================
echo  Translation Editor - Debug Mode
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
"""
        debug_bat_path = dist_path / "Translation Editor Debug.bat"
        debug_bat_path.write_text(debug_bat_content, encoding="utf-8")
        self.log(f"Created: {debug_bat_path.name}")

    def _create_archive(self, dist_path: Path) -> tuple[Path, Optional[Path]]:
        """Create ZIP and 7z archives of the distribution."""
        zip_path = self.output_dir / f"{self.archive_name}.zip"
        sevenz_path = self.output_dir / f"{self.archive_name}.7z"

        # Remove existing archives
        for path in (zip_path, sevenz_path):
            if path.exists():
                path.unlink()

        # Create ZIP archive
        self.log(f"Creating ZIP archive: {zip_path.name}")
        with zipfile.ZipFile(
            zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9
        ) as zf:
            for root, dirs, files in os.walk(dist_path):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                for file in files:
                    file_path = Path(root) / file
                    arc_name = file_path.relative_to(self.output_dir)
                    zf.write(file_path, arc_name)

        zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
        self.log(f"ZIP archive size: {zip_size_mb:.2f} MB")

        # Try to create 7z archive
        sevenz_created = self._create_7z_archive(dist_path, sevenz_path)

        return zip_path, sevenz_path if sevenz_created else None

    def _create_7z_archive(self, dist_path: Path, sevenz_path: Path) -> bool:
        """Create a 7z archive using the 7z command-line tool."""
        sevenz_cmd = None

        if platform.system() == "Windows":
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
            sevenz_cmd = shutil.which("7z") or shutil.which("7za")

        if not sevenz_cmd:
            self.log("7z not found - skipping 7z archive creation")
            self.log("Install 7-Zip to also generate .7z archives")
            return False

        self.log(f"Creating 7z archive: {sevenz_path.name}")

        try:
            result = subprocess.run(
                [
                    sevenz_cmd,
                    "a",
                    "-t7z",
                    "-m0=LZMA2",
                    "-mf=off",
                    "-mx=9",
                    "-mfb=273",
                    "-ms=on",
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
        total_steps = 5
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

        # Step 5: Create archives
        self.log_step(5, total_steps, "Creating distribution archives")
        zip_path, sevenz_path = self._create_archive(dist_path)
        tar_path = self._create_tar_archive(dist_path)

        self.log(f"\n{'='*60}")
        self.log("BUILD COMPLETE!")
        self.log(f"Distribution folder: {dist_path}")
        self.log(f"ZIP archive: {zip_path}")
        if sevenz_path:
            self.log(f"7z archive: {sevenz_path}")
        self.log(f"tar.gz archive: {tar_path}")
        self.log(f"{'='*60}\n")

        return zip_path

    def _create_venv(self, venv_path: Path) -> None:
        """Create a virtual environment."""
        import venv

        self.log(f"Creating venv at: {venv_path}")
        self.log("This may take a moment...")
        try:
            venv.create(venv_path, with_pip=True, clear=True)
            self.log("Virtual environment created successfully")
        except Exception as e:
            self.log(f"venv.create failed: {e}")
            raise

    def _install_requirements_unix(self, venv_path: Path) -> None:
        """Install requirements in Unix virtual environment."""
        if platform.system() == "Windows":
            pip_exe = venv_path / "Scripts" / "pip.exe"
            site_packages = venv_path / "Lib" / "site-packages"
        else:
            pip_exe = venv_path / "bin" / "pip"
            # Find site-packages in Unix venv (e.g., lib/python3.14/site-packages)
            lib_dir = venv_path / "lib"
            site_packages = None
            if lib_dir.exists():
                for py_dir in lib_dir.iterdir():
                    if py_dir.name.startswith("python"):
                        site_packages = py_dir / "site-packages"
                        break

        self.log("Installing packages...")

        result = subprocess.run(
            [str(pip_exe), "install", *REQUIRED_PACKAGES],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            print(f"STDERR: {result.stderr}", flush=True)
            raise RuntimeError("Failed to install requirements")

        self.log("All packages installed successfully")

        # Strip unnecessary PySide6 components to reduce size
        if site_packages and site_packages.exists():
            self._strip_pyside6(site_packages)

    def _create_unix_launcher_scripts(self, dist_path: Path) -> None:
        """Create Unix launcher scripts."""
        sh_content = """#!/bin/bash

# Translation Editor Launcher
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

export PYTHONPATH="$SCRIPT_DIR/src"

echo "Starting Translation Editor..."
exec "$PYTHON_EXE" "src/Main.py" "$@"
"""
        sh_path = dist_path / "Translation Editor.sh"
        sh_path.write_text(sh_content, encoding="utf-8")
        sh_path.chmod(0o755)
        self.log(f"Created: {sh_path.name}")

        # Debug launcher
        debug_sh_content = """#!/bin/bash

# Translation Editor Debug Launcher

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo " Translation Editor - Debug Mode"
echo "============================================================"
echo

if [ -f "python/bin/python" ]; then
    PYTHON_EXE="python/bin/python"
elif [ -f "python/bin/python3" ]; then
    PYTHON_EXE="python/bin/python3"
else
    echo "ERROR: Bundled Python not found!"
    exit 1
fi

echo "Python executable: $PYTHON_EXE"
"$PYTHON_EXE" --version
echo

export PYTHONPATH="$SCRIPT_DIR/src"

echo "Starting application..."
echo
"$PYTHON_EXE" "src/Main.py" "$@"
EXIT_CODE=$?

echo
echo "============================================================"
echo " Application has exited with code: $EXIT_CODE"
echo "============================================================"
read -p "Press Enter to close..."
"""
        debug_sh_path = dist_path / "Translation Editor Debug.sh"
        debug_sh_path.write_text(debug_sh_content, encoding="utf-8")
        debug_sh_path.chmod(0o755)
        self.log(f"Created: {debug_sh_path.name}")

    def _create_tar_archive(self, dist_path: Path) -> Path:
        """Create a tar.gz archive of the distribution."""
        import tarfile

        archive_filename = f"{self.archive_name}.tar.gz"
        archive_path = self.output_dir / archive_filename

        if archive_path.exists():
            archive_path.unlink()

        self.log(f"Creating archive: {archive_filename}")

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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a portable distribution of Translation Editor"
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
    # Main project root (TextureAtlas-to-GIF-and-Frames) is 3 levels up from setup/
    main_project_root = script_path.parent.parent.parent.parent

    # Default output directory - use main project's build output folder
    if args.output_dir is None:
        output_dir = main_project_root / "_build-output" / "portable"
    else:
        output_dir = args.output_dir.resolve()

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get app version for display
    app_version = get_app_version(project_root)

    print(f"\n{'='*60}", flush=True)
    print("  Translation Editor - Embedded Python Distribution Builder", flush=True)
    print(f"{'='*60}", flush=True)
    print(f"  Project root: {project_root}", flush=True)
    print(f"  Output directory: {output_dir}", flush=True)
    print(f"  App version: v{app_version}", flush=True)
    print(f"  Python version: {args.python_version}", flush=True)
    print(
        f"  Target platform: {platform.system()} "
        f"({get_os_identifier()}-{get_arch_identifier()})",
        flush=True,
    )
    print(f"{'='*60}\n", flush=True)

    builder = PortableBuilder(
        project_root=project_root,
        output_dir=output_dir,
        python_version=args.python_version,
        verbose=not args.quiet,
    )

    print(f"  Archive name: {builder.archive_name}", flush=True)
    print(f"  Folder name: {builder.dist_name}", flush=True)
    print(flush=True)

    try:
        archive_path = builder.build()
        print(f"\nSuccess! Distribution created at:\n  {archive_path}", flush=True)
        return 0
    except Exception as e:
        print(f"\nError: {e}", flush=True)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
