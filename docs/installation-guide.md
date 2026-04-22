# Installation Guide

This guide will walk you through installing and setting up TextureAtlas Toolbox on your system.
macOS and Linux users or developers can refer to the detailed manual installation sections.


<!-- TODO: Add screenshot of the main application window here -->
<!-- ![TextureAtlas Toolbox main window](images/main-window.png) -->

## Table of Contents

- [System Requirements](#system-requirements)
  - [Minimum Requirements](#minimum-requirements)
  - [Recommended Requirements](#recommended-requirements)
  - [Performance Notes](#performance-notes)
- [Normal Install (Windows only)](#normal-install-windows-only)
- [Manual Installation](#manual-installation)
  - [Python Installation](#python-installation)
    - [Windows](#windows)
    - [macOS](#macos)
    - [Linux (Ubuntu/Debian)](#linux-ubuntudebian)
  - [Installing Python Dependencies](#installing-python-dependencies)
    - [Using requirements.txt (Recommended)](#using-requirementstxt-recommended)
    - [Full manual Installation](#full-manual-installation)
    - [Package Details](#package-details)
  - [ImageMagick Setup](#imagemagick-setup)
    - [Windows (Manual)](#windows-manual)
    - [macOS (Manual)](#macos-manual)
    - [Linux (Manual)](#linux-manual)
  - [Clone Repository (For Developers)](#clone-repository-for-developers)
  - [Compiling from Source (Windows)](#compiling-from-source-windows)
- [Troubleshooting Installation & Common Errors](#troubleshooting-installation--common-errors)
  - [Python Not Recognized](#python-not-recognized)
  - [Missing Packages](#missing-packages)
  - [ImageMagick Errors](#imagemagick-errors)
  - ["No module named 'PIL'"](#no-module-named-pil)
- [Verifying Installation](#verifying-installation)
- [Updating the Application](#updating-the-application)

## System Requirements

### Minimum Requirements

- **Operating System**: Windows 10+, macOS 11+, or Linux (Ubuntu 20.04+/Debian 11+/Fedora 36+)
- **CPU**: At least 2 cores (dual-core or better required)
- **Python**: Version 3.14 or higher
- **RAM**: At least 8GB
- **Storage**: 1GB for application + output of single spritesheet processing (5GB+ recommended
  for batch processing)
- **Internet Access**: Required for downloading dependencies and updates

### Recommended Requirements

- **Operating System**: Windows 10/11 (64-bit), macOS 11+ (Big Sur or later), or recent Linux
  (Ubuntu 22.04+/Fedora 38+)
- **CPU**: Quad-core or better
- **Python**: Version 3.14 or higher (64-bit)
- **RAM**: 16GB or more (32GB+ recommended for batch processing large atlases or Adobe Animate
  spritemaps)
- **Storage**: SSD with 10GB+ free space for faster processing speeds (a regular hard drive
  will suffice for smaller workloads)
- **Internet Access**: Required for downloading dependencies and updates

> **Important Notices:**
> - 32-bit operating systems are **not officially supported** and will **not receive
>   troubleshooting help**.
> - Operating systems below macOS 11, Windows 10, and older Linux distributions are **not
>   officially supported** and will **not receive troubleshooting help**.
> - Python versions below 3.14 are **not officially supported** and will **not receive
>   troubleshooting help**.

### Performance Notes
> **Adobe Animate Spritemap Extraction**  
> Extracting Adobe Animate spritemaps (the `Animation.json` + `sheet.json` pairs) is
> significantly more memory-intensive than other formats. Each spritemap typically requires
> decompressing high-resolution frames and rebuilding matrix transformations. **Expect
> substantially higher RAM and CPU usage during these operations.**  
> - For large Adobe Animate atlases, close other memory-heavy applications before processing.
> - Consider reducing the number of worker threads if you encounter out-of-memory errors.
> - An SSD is strongly recommended for caching intermediate frames.

## Normal Install (Windows only)

> **Antivirus False Positives**  
> The Windows executable releases are **very likely to be flagged as malware** by antivirus
> software. This is a common false positive for Python applications compiled with tools like
> Nuitka or PyInstaller. The application is open-source and safe—you can verify the code
> yourself. If your antivirus blocks or quarantines the executable:
> - Add an exception for the `TextureAtlas Toolbox.exe` file or the installation folder.
> - Alternatively, use the [Manual Installation](#manual-installation) method to run from
>   source, which avoids this issue entirely.
> - You can also [compile the application yourself](#compiling-from-source-windows) using the
>   provided build script, but this requires doing the [Manual Installation](#manual-installation) anyways.

1. Go to the [GitHub Releases page](https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames/releases).
2. Download the latest release ZIP or 7z file.
3. Extract all files to a folder of your choice (e.g., `C:\TextureAtlasToolbox`).
4. Run `TextureAtlas Toolbox.exe`.

<!-- TODO: Add screenshot of the extracted folder contents here -->
<!-- ![Extracted folder contents](images/extracted-folder.png) -->

**That's it!** If you encounter any issues, check the [Troubleshooting section](#-troubleshooting-installation--common-errors) below.

---

## Manual Installation

**For the Advanced users, developers or Mac/Linux users**:

This will guide you through how to install Python and the required dependencies to run the app directly from the .py scripts.


### Python Installation

#### Windows

1. Download Python 3.14+ from [python.org](https://www.python.org/downloads/).
2. **Important**: During installation, check the box for **"Add Python to PATH"**.
3. Complete the installation.
4. Open Command Prompt and verify installation:
   ```cmd
   python --version
   ```
   If you see a version number (e.g., `Python 3.14.0`), Python is installed correctly.

#### macOS

1. **Recommended**: Install Homebrew if you haven't already:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
2. Install Python:
   ```bash
   brew install python
   ```
3. Verify installation:
   ```bash
   python3 --version
   ```

#### Linux (Ubuntu/Debian)

1. Update package lists:
   ```bash
   sudo apt update
   ```
2. Install Python and pip:
   ```bash
   sudo apt install python3 python3-pip
   ```

3. Verify installation:
   ```bash
   python3 --version
   ```

### Installing Python Dependencies

#### Using requirements.txt (Recommended Stable Build)

**Windows:**

The `setup/setup_windows.bat` script automates the entire setup process:

1. **Double-click** or run `setup/setup_windows.bat` from the project folder.
2. The script performs the following steps automatically:
   - **Detects Python**: Checks for `py`, `python`, or common installation paths.
   - **Validates version**: Ensures Python 3.14+ is available.
   - **Installs Python if missing**: Downloads and silently installs Python 3.14.x (64-bit) from
     python.org, adding it to your PATH. You may be prompted for administrator approval.
   - **Upgrades pip**: Updates pip to the latest version.
   - **Prompts for dependency install**: Asks whether to install dependencies.
   - **Lets you choose stable or experimental**: Select option 1 for `requirements.txt` (stable)
     or option 2 for `requirements-experimental.txt` (bleeding-edge).
   - **Installs dependencies**: Runs `pip install --upgrade --user` with your chosen file.
   - **Adds Scripts to PATH**: Automatically adds the Python Scripts directory to your user PATH
     so tools like `pip` work in new terminal sessions.

<!-- TODO: Add screenshot of the setup script prompts here -->
<!-- ![Windows setup script](images/setup-windows.png) -->

If you prefer manual steps, open a terminal or command prompt, navigate to the project root
directory, and run:
```powershell
pip install -r setup/requirements.txt
```
If you encounter permission errors, try:
```powershell
python -m pip install --user -r setup/requirements.txt
```
Need the bleeding-edge dependency set? Replace `requirements.txt` with
`requirements-experimental.txt` in the commands above.

**macOS:**

1. Open Terminal and run the setup script:
   ```bash
   bash setup/setup_macOSX.sh
   ```
   This will attempt to install all required dependencies automatically. Note that the `.sh`
   script for macOS is experimental and not extensively tested.
2. If you prefer manual steps, navigate to the project root directory and run:
   ```bash
   pip install -r setup/requirements.txt
   ```
   If you encounter permission errors, try:
   ```bash
   python3 -m pip install --user -r setup/requirements.txt
   ```
   For the experimental stack, swap in `setup/requirements-experimental.txt`.

**Linux:**

1. Open a terminal, navigate to the project root directory, and run:
   ```bash
   pip install -r setup/requirements.txt
   ```
   If you encounter permission errors, try:
   ```bash
   python3 -m pip install --user -r setup/requirements.txt
   ```
   Swap the filename with `setup/requirements-experimental.txt` if you prefer the less-tested
   dependency set.

##### Full manual Installation

If you prefer, you can install packages individually:
```bash
pip install certifi charset-normalizer colorama idna numpy pillow psutil requests tqdm urllib3 Wand pyside6 py7zr etcpak texture2ddecoder qt-material qtawesome
```

#### Package Details

| Package | Version | Purpose |
|---------|---------|---------|
| **certifi** | 2024.8.30 | Root certificates for SSL validation |
| **charset-normalizer** | 3.4.0 | Encoding detection for text files and web content |
| **colorama** | 0.4.6 | Cross-platform colored terminal text |
| **etcpak** | 0.9.11 | GPU texture compression (BC1/BC3/BC7, ETC1/ETC2) |
| **idna** | 3.10 | Internationalized Domain Names support |
| **texture2ddecoder** | 1.0.6 | Adobe Animate spritemap texture decoding |
| **numpy** | 2.2.0 | Numerical operations |
| **pillow** | 11.3.0 | Image processing and manipulation |
| **psutil** | 6.1.0 | System and process utilities (resource monitoring) |
| **py7zr** | 1.0.0 | 7-Zip archive support |
| **pyside6** | 6.9.2 | Qt 6 bindings for the GUI framework |
| **qt-material** | 2.14 | Material Design theme styles for the Qt UI |
| **qtawesome** | 1.4.0 | Icon font integration (Font Awesome / Material) for the UI |
| **requests** | 2.32.3 | HTTP library for update checking |
| **tqdm** | 4.67.1 | Progress bar for loops and CLI operations |
| **urllib3** | 2.2.3 | HTTP client (dependency of requests) |
| **Wand** | 0.6.13 | Python binding for ImageMagick |

### Optional GPU Texture Compression Tools

The `etcpak` Python package (included in requirements) provides BC1, BC3, BC7, ETC1, and ETC2
compression out of the box. For additional GPU compression formats, install the following
command-line tools:

| Tool              | Formats            | Download                                               |
| ----------------- | ------------------ | ------------------------------------------------------ |
| **astcenc**       | ASTC 4×4, 6×6, 8×8 | [arm.com](https://github.com/ARM-software/astc-encoder) |
| **PVRTexToolCLI** | PVRTC 4bpp, 2bpp   | [Imagination Technologies](https://developer.imaginationtech.com/pvrtextool/) |

These tools are optional — the application works without them, but ASTC and PVRTC formats
will be unavailable.

### ImageMagick Setup

ImageMagick is required for GIF processing and optimization.


#### Windows (Manual)

1. Download ImageMagick from [imagemagick.org](https://imagemagick.org/script/download.php#windows).
2. Choose the version matching your system (64-bit recommended).
3. Run the installer.
4. **Important**: During installation, check:
   - "Install development headers and libraries for C and C++"
   - "Add application directory to your system PATH"
5. After installation, open a new Command Prompt and verify:
   ```cmd
   magick --version
   ```
   If you see version info, ImageMagick is installed.

#### macOS (Manual)

1. Install via Homebrew:
   ```bash
   brew install imagemagick
   ```
2. Verify:
   ```bash
   magick --version
   ```

#### Linux (Manual)

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install imagemagick libmagickwand-dev
```
**Fedora:**
```bash
sudo dnf install ImageMagick ImageMagick-devel
```
**CentOS/RHEL:**
```bash
sudo yum install ImageMagick ImageMagick-devel
```
**Verify Installation:**
```bash
magick --version
```

### Clone Repository (For Developers)

1. Open a terminal or command prompt.
2. Run:
   ```bash
   git clone https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames.git
   cd TextureAtlas-to-GIF-and-Frames
   ```

### Compiling from Python to Source (Windows)

If you prefer to compile your own Windows executable,
use the provided Nuitka build script:

1. Ensure you have Python **3.14 or later** installed. The build script always installs/
   upgrades to the latest Nuitka, which compiles 3.14 cleanly. Python 3.13 requires
   Visual Studio (MSVC) — MinGW64 is not supported on 3.13.
2. *(Optional)* Install Visual Studio with the following components for MSVC builds:
   - Windows 10 SDK (10.0.19041.0 or later)
   - MSVC v143 – VS 2022 C++ x64/x86 build tools
   - C++/CLI support for v143 build tools
3. Run the build script:
   ```cmd
   setup\build-windows.bat
   ```
4. The script will:
   - Automatically install or upgrade Nuitka via pip.
   - Detect whether to use MSVC or MinGW64 (prompts you if both are available).
   - Ask for a version number to embed in the executable.
   - Compile the application to `_build-output\dist\` as `TextureAtlasToolbox.exe`.

> **Note:** This build script is provided as-is; the maintainer does not offer support for
> build-related issues.

---

## Troubleshooting Installation & Common Errors

If you run into installation or startup problems, use this section to diagnose and fix the most
common issues. These solutions apply to both source and (where relevant) .exe versions.

### Python Not Recognized

- **Windows**: Run `setup/setup_windows.bat` or reinstall Python and ensure "Add Python to PATH"
  is checked.
- **macOS**: Run `setup/setup_macOSX.sh` or install Python via Homebrew. (The setup script for
  macOS is experimental and not extensively tested.)
- **Linux**: Install Python using your package manager.

### Missing Packages

- Install all dependencies:
  ```bash
  pip install -r setup/requirements.txt
  ```

### ImageMagick Errors

- Ensure ImageMagick is installed and added to your PATH.
- On Windows, verify the `ImageMagick` folder exists or reinstall manually.

### "No module named 'PIL'"

- Install Pillow:
  ```bash
  pip install Pillow
  ```


## Verifying Installation

1. Start the application:
   ```bash
   cd src
   python Main.py
   ```
2. Ensure the GUI opens without errors.
3. Test loading a sample texture atlas and exporting a GIF.


## Updating the Application

- The app checks for updates on startup.
- If notified, download the latest release and replace your files.

---

*Last updated: April 22, 2026 — TextureAtlas Toolbox v3.0.0*
