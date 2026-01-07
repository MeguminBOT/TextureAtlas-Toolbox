#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Interactive GUI tests for the update system requiring human verification.

These tests launch the actual application GUI and require manual interaction
to verify that update dialogs, progress bars, and workflows function correctly.

Usage:
    python tests/test_update_interactive.py                    # Full interactive test
    python tests/test_update_interactive.py --mode source      # Test SOURCE mode
    python tests/test_update_interactive.py --mode embedded    # Test EMBEDDED mode  
    python tests/test_update_interactive.py --skip-cleanup     # Keep temp files for inspection
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

# Add src to path for imports
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# =============================================================================
# Configuration
# =============================================================================

TEST_REPO_OWNER = "MeguminBOT"
TEST_REPO_NAME = "for-testing-purposes"

WORKSPACE_ITEMS_TO_COPY = [
    "src",
    "assets",
    "ImageMagick",
    "docs",
    "setup",
    "LICENSE",
    "README.md",
    "latestVersion.txt",
]


# =============================================================================
# Console Utilities
# =============================================================================

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'


def print_header(text: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{text:^60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.HEADER}{'='*60}{Colors.END}\n")


def print_step(step_num: int, text: str) -> None:
    """Print a numbered step."""
    print(f"{Colors.CYAN}[Step {step_num}]{Colors.END} {text}")


def print_success(text: str) -> None:
    """Print a success message."""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")


def print_warning(text: str) -> None:
    """Print a warning message."""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")


def print_error(text: str) -> None:
    """Print an error message."""
    print(f"{Colors.RED}✗ {text}{Colors.END}")


def print_info(text: str) -> None:
    """Print an info message."""
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")


def prompt_user(message: str, valid_responses: list[str] = None) -> str:
    """Prompt user for input and return response."""
    if valid_responses:
        options = "/".join(valid_responses)
        full_message = f"{Colors.YELLOW}{message} [{options}]: {Colors.END}"
    else:
        full_message = f"{Colors.YELLOW}{message}: {Colors.END}"
    
    while True:
        response = input(full_message).strip().lower()
        if valid_responses is None or response in [r.lower() for r in valid_responses]:
            return response
        print_error(f"Invalid response. Please enter one of: {', '.join(valid_responses)}")


def prompt_continue() -> bool:
    """Ask user to press Enter to continue or 'q' to quit."""
    response = input(f"{Colors.YELLOW}Press Enter to continue (or 'q' to quit): {Colors.END}").strip().lower()
    return response != 'q'


def prompt_pass_fail(test_name: str) -> bool:
    """Ask user if a test passed or failed."""
    print()
    response = prompt_user(f"Did '{test_name}' work correctly?", ["y", "n", "yes", "no"])
    return response in ["y", "yes"]


# =============================================================================
# Workspace Setup
# =============================================================================

def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).resolve().parents[1]


def copy_workspace(temp_dir: Path) -> Path:
    """Copy workspace files to temp directory."""
    project_root = get_project_root()
    workspace = temp_dir / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    
    for item_name in WORKSPACE_ITEMS_TO_COPY:
        src_path = project_root / item_name
        dst_path = workspace / item_name
        
        if not src_path.exists():
            print_warning(f"Skipping {item_name} (not found)")
            continue
        
        if src_path.is_dir():
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
        else:
            shutil.copy2(src_path, dst_path)
        print_info(f"Copied {item_name}")
    
    return workspace


def patch_version(workspace: Path, fake_version: str = "1.0.0") -> None:
    """Patch version.py to use test repository and older version.
    
    This rewrites the entire version.py file to ensure all URL constants
    use the test repository values (not just the REPO_OWNER/REPO_NAME vars).
    """
    version_file = workspace / "src" / "utils" / "version.py"
    
    # Rewrite the entire file with test values
    new_content = f'''"""Centralized application version constants and helpers.

Exports the current version string, GitHub API URLs, and a utility for
parsing semantic version tags into comparable tuples.
"""

from __future__ import annotations

import re

APP_NAME = "TextureAtlas Toolbox"
APP_VERSION = "{fake_version}"
REPO_OWNER = "{TEST_REPO_OWNER}"
REPO_NAME = "{TEST_REPO_NAME}"

_API_ROOT = f"https://api.github.com/repos/{{REPO_OWNER}}/{{REPO_NAME}}"
GITHUB_TAGS_URL = f"{{_API_ROOT}}/tags"
GITHUB_RELEASES_URL = f"{{_API_ROOT}}/releases"
GITHUB_RELEASE_BY_TAG_URL = f"{{GITHUB_RELEASES_URL}}/tags/{{{{tag}}}}"
GITHUB_LATEST_RELEASE_URL = f"{{GITHUB_RELEASES_URL}}/latest"

_SUFFIX_PRIORITY = {{"alpha": 0, "beta": 1, "": 2}}
_SUFFIX_PATTERN = re.compile(r"-(?P<label>[A-Za-z]+)$")
_SEMVER_PREFIX = re.compile(r"^\\s*[vV]?\\d")


def version_to_tuple(version: str) -> tuple[int, ...]:
    """Parse a semantic version string into a comparable tuple.

    Supports optional ``v``/``V`` prefix and ``-alpha``/``-beta`` suffixes.
    Non-semantic tags raise ``ValueError``.

    Args:
        version: Version string like ``v1.2.3`` or ``1.2.0-beta``.

    Returns:
        Tuple of version segments with a trailing suffix rank.

    Raises:
        ValueError: If ``version`` is not a valid semantic version.
    """

    if not _SEMVER_PREFIX.match(version or ""):
        raise ValueError("Version tag must begin with a semantic number")

    cleaned = version.strip().lstrip("vV")
    suffix_label = ""

    match = _SUFFIX_PATTERN.search(cleaned)
    if match:
        candidate = match.group("label").lower()
        if candidate in _SUFFIX_PRIORITY:
            suffix_label = candidate
        cleaned = cleaned[: match.start()]

    digit_chunks = re.findall(r"\\d+", cleaned)
    parts = tuple(int(chunk) for chunk in digit_chunks) or (0,)
    suffix_rank = _SUFFIX_PRIORITY[suffix_label]
    return parts + (suffix_rank,)


__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "REPO_OWNER",
    "REPO_NAME",
    "GITHUB_TAGS_URL",
    "GITHUB_RELEASES_URL",
    "GITHUB_RELEASE_BY_TAG_URL",
    "GITHUB_LATEST_RELEASE_URL",
    "version_to_tuple",
]
'''
    
    version_file.write_text(new_content, encoding="utf-8")
    print_success(f"Patched version to {fake_version}")
    print_success(f"Patched repo to {TEST_REPO_OWNER}/{TEST_REPO_NAME}")
    
    # Clear any __pycache__ to ensure fresh import
    for pycache in workspace.rglob("__pycache__"):
        if pycache.is_dir():
            shutil.rmtree(pycache, ignore_errors=True)
    print_info("Cleared __pycache__ directories")


# =============================================================================
# Interactive Tests
# =============================================================================

def run_interactive_source_test(skip_cleanup: bool = False) -> bool:
    """Run interactive SOURCE mode update test.
    
    Returns:
        True if user confirms test passed, False otherwise.
    """
    print_header("INTERACTIVE SOURCE MODE TEST")
    
    print_info(f"Test Repository: https://github.com/{TEST_REPO_OWNER}/{TEST_REPO_NAME}/releases")
    print_info("This test will:")
    print("  1. Copy workspace to a temporary directory")
    print("  2. Patch version to 1.0.0 (older than test releases)")
    print("  3. Launch the application GUI")
    print("  4. You will manually trigger 'Check for Updates'")
    print("  5. Verify the update dialog appears with correct info")
    print("  6. Optionally proceed with the update")
    print()
    
    if not prompt_continue():
        return False
    
    # Setup
    print_step(1, "Creating temporary workspace...")
    temp_dir = Path(tempfile.mkdtemp(prefix="tatgf_interactive_source_"))
    print_info(f"Temp directory: {temp_dir}")
    
    try:
        print_step(2, "Copying workspace files...")
        workspace = copy_workspace(temp_dir)
        
        print_step(3, "Patching version file...")
        patch_version(workspace, "1.0.0")
        
        print_step(4, "Launching application...")
        print()
        print(f"{Colors.BOLD}{'─'*60}{Colors.END}")
        print(f"{Colors.BOLD}MANUAL TEST INSTRUCTIONS:{Colors.END}")
        print(f"{'─'*60}")
        print("1. The application will launch in a new window")
        print("2. Update check happens AUTOMATICALLY on startup")
        print("3. Verify the update dialog shows:")
        print(f"   - Current version: 1.0.0")
        print(f"   - Available version: v2.0.2 (or newer from test repo)")
        print("4. You can click 'Update Now' to test the full update flow")
        print("   OR click 'Cancel' to just test detection")
        print("5. Close the application when done testing")
        print(f"{'─'*60}")
        print()
        
        if not prompt_continue():
            return False
        
        # Launch the app
        main_py = workspace / "src" / "Main.py"
        env = os.environ.copy()
        env["PYTHONPATH"] = str(workspace / "src")
        
        print_info("Starting application... (close it when done testing)")
        print()
        
        process = subprocess.Popen(
            [sys.executable, str(main_py)],
            cwd=str(workspace),
            env=env,
        )
        
        # Wait for user to close the app
        process.wait()
        
        print()
        print_step(5, "Application closed. Verifying results...")
        
        # Ask user for results
        results = {}
        
        print()
        print(f"{Colors.BOLD}Please answer the following:{Colors.END}")
        print()
        
        results["app_launched"] = prompt_pass_fail("Application launched successfully")
        results["update_menu"] = prompt_pass_fail("Found 'Check for Updates' menu option")
        results["update_detected"] = prompt_pass_fail("Update was detected (dialog appeared)")
        results["version_correct"] = prompt_pass_fail("Dialog showed correct versions (1.0.0 → 2.0.x)")
        
        did_update = prompt_user("Did you click 'Update Now'?", ["y", "n"]) in ["y", "yes"]
        if did_update:
            results["update_started"] = prompt_pass_fail("Update process started")
            results["update_completed"] = prompt_pass_fail("Update completed successfully")
        
        # Summary
        print()
        print_header("TEST RESULTS")
        
        all_passed = True
        for test_name, passed in results.items():
            if passed:
                print_success(f"{test_name}: PASSED")
            else:
                print_error(f"{test_name}: FAILED")
                all_passed = False
        
        return all_passed
        
    finally:
        if skip_cleanup:
            print()
            print_warning(f"Skipping cleanup. Temp files at: {temp_dir}")
        else:
            print()
            print_step(6, "Cleaning up temporary files...")
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                print_success("Cleanup complete")
            except Exception as e:
                print_warning(f"Cleanup failed: {e}")


def run_interactive_embedded_test(skip_cleanup: bool = False) -> bool:
    """Run interactive EMBEDDED mode update test.
    
    Returns:
        True if user confirms test passed, False otherwise.
    """
    print_header("INTERACTIVE EMBEDDED MODE TEST")
    
    print_info(f"Test Repository: https://github.com/{TEST_REPO_OWNER}/{TEST_REPO_NAME}/releases")
    print_info("This test will:")
    print("  1. Build an embedded Python release to a temp directory")
    print("  2. Patch the version to 1.0.0")
    print("  3. Launch the embedded release")
    print("  4. You will manually trigger 'Check for Updates'")
    print("  5. Verify embedded mode update workflow")
    print()
    print_warning("Note: Building embedded release takes several minutes")
    print()
    
    if not prompt_continue():
        return False
    
    # Setup
    print_step(1, "Creating temporary directory...")
    temp_dir = Path(tempfile.mkdtemp(prefix="tatgf_interactive_embedded_"))
    print_info(f"Temp directory: {temp_dir}")
    
    try:
        print_step(2, "Building embedded Python release...")
        print_info("This may take a few minutes...")
        
        project_root = get_project_root()
        build_script = project_root / "setup" / "build_portable.py"
        
        if not build_script.exists():
            print_error(f"build_portable.py not found at {build_script}")
            return False
        
        build_output = temp_dir / "build"
        build_output.mkdir(parents=True, exist_ok=True)
        
        result = subprocess.run(
            [sys.executable, str(build_script), "--output", str(build_output)],
            cwd=str(project_root),
            capture_output=True,
            text=True,
        )
        
        if result.returncode != 0:
            print_error("Build failed!")
            print(result.stderr[-2000:] if result.stderr else "No error output")
            return False
        
        # Find the built release
        embedded_release = None
        for item in build_output.iterdir():
            if item.is_dir() and item.name.startswith("TextureAtlas"):
                embedded_release = item
                break
        
        if not embedded_release:
            if (build_output / "python").exists():
                embedded_release = build_output
            else:
                print_error("Could not find built release")
                return False
        
        print_success(f"Build complete: {embedded_release}")
        
        print_step(3, "Patching version file...")
        patch_version(embedded_release, "1.0.0")
        
        print_step(4, "Launching embedded release...")
        print()
        print(f"{Colors.BOLD}{'─'*60}{Colors.END}")
        print(f"{Colors.BOLD}MANUAL TEST INSTRUCTIONS:{Colors.END}")
        print(f"{'─'*60}")
        print("1. The embedded application will launch")
        print("2. Update check happens AUTOMATICALLY on startup")
        print("3. An update dialog should appear (v1.0.0 → v2.0.2)")
        print("4. Test the update flow (it should detect EMBEDDED mode)")
        print("5. Close the application when done")
        print(f"{'─'*60}")
        print()
        
        if not prompt_continue():
            return False
        
        # Find launcher
        launcher = None
        for name in ["Launch.bat", "run.bat", "TextureAtlas Toolbox.bat"]:
            candidate = embedded_release / name
            if candidate.exists():
                launcher = candidate
                break
        
        if launcher:
            print_info(f"Using launcher: {launcher.name}")
            process = subprocess.Popen(
                ["cmd", "/c", str(launcher)],
                cwd=str(embedded_release),
            )
        else:
            # Direct Python launch
            python_exe = embedded_release / "python" / "python.exe"
            main_py = embedded_release / "src" / "Main.py"
            
            if not python_exe.exists():
                print_error(f"Python not found at {python_exe}")
                return False
            
            print_info("Launching via embedded Python...")
            process = subprocess.Popen(
                [str(python_exe), str(main_py)],
                cwd=str(embedded_release),
            )
        
        process.wait()
        
        print()
        print_step(5, "Application closed. Verifying results...")
        
        # Ask user for results
        results = {}
        
        print()
        print(f"{Colors.BOLD}Please answer the following:{Colors.END}")
        print()
        
        results["app_launched"] = prompt_pass_fail("Embedded app launched successfully")
        results["update_detected"] = prompt_pass_fail("Update was detected")
        results["embedded_mode"] = prompt_pass_fail("Update used EMBEDDED mode (check logs if unsure)")
        
        did_update = prompt_user("Did you proceed with the update?", ["y", "n"]) in ["y", "yes"]
        if did_update:
            results["update_completed"] = prompt_pass_fail("Embedded update completed")
        
        # Summary
        print()
        print_header("TEST RESULTS")
        
        all_passed = True
        for test_name, passed in results.items():
            if passed:
                print_success(f"{test_name}: PASSED")
            else:
                print_error(f"{test_name}: FAILED")
                all_passed = False
        
        return all_passed
        
    finally:
        if skip_cleanup:
            print()
            print_warning(f"Skipping cleanup. Temp files at: {temp_dir}")
        else:
            print()
            print_step(6, "Cleaning up temporary files...")
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                print_success("Cleanup complete")
            except Exception as e:
                print_warning(f"Cleanup failed: {e}")


def run_update_dialog_only_test() -> bool:
    """Quick test that just shows the update dialog without full app.
    
    Returns:
        True if user confirms test passed.
    """
    print_header("UPDATE DIALOG PREVIEW TEST")
    
    print_info("This test launches just the update dialog for quick verification")
    print_info("No workspace copy needed - uses current source directly")
    print()
    
    if not prompt_continue():
        return False
    
    # Create a simple script to show the dialog
    script = '''
import sys
sys.path.insert(0, "src")

from PySide6.QtWidgets import QApplication
from utils.update_checker import UpdateDialog

app = QApplication(sys.argv)

# Create dialog with test data
dialog = UpdateDialog(
    parent=None,
    current_version="1.0.0",
    latest_version="2.0.2",
    changelog="""## What's New in v2.0.2

### Features
- Added embedded Python update support
- Improved update detection for all modes
- Better error handling during updates

### Bug Fixes
- Fixed file locking issues on Windows
- Resolved progress bar display glitches

### Notes
This is a TEST release from the test repository.
""",
    update_type="major",
)

print("Showing update dialog...")
print("Click 'Update Now' or 'Cancel' to close")

result = dialog.show_dialog()
print(f"User chose: {'Update' if result else 'Cancel'}")
'''
    
    print_step(1, "Launching update dialog preview...")
    print()
    
    project_root = get_project_root()
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=str(project_root),
        capture_output=False,
    )
    
    print()
    results = {}
    results["dialog_shown"] = prompt_pass_fail("Update dialog appeared")
    results["layout_correct"] = prompt_pass_fail("Dialog layout looked correct")
    results["buttons_worked"] = prompt_pass_fail("Buttons were clickable")
    
    print()
    print_header("TEST RESULTS")
    
    all_passed = True
    for test_name, passed in results.items():
        if passed:
            print_success(f"{test_name}: PASSED")
        else:
            print_error(f"{test_name}: FAILED")
            all_passed = False
    
    return all_passed


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Interactive GUI tests for the update system"
    )
    parser.add_argument(
        "--mode",
        choices=["source", "embedded", "dialog", "all"],
        default="all",
        help="Which test mode to run",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Keep temporary files after test for inspection",
    )
    
    args = parser.parse_args()
    
    print_header("INTERACTIVE UPDATE SYSTEM TESTS")
    print_info(f"Test Repository: https://github.com/{TEST_REPO_OWNER}/{TEST_REPO_NAME}")
    print_info("These tests require manual interaction to verify GUI behavior")
    print()
    
    results = {}
    
    if args.mode in ["dialog", "all"]:
        print()
        if prompt_user("Run Update Dialog preview test?", ["y", "n"]) in ["y", "yes"]:
            results["dialog"] = run_update_dialog_only_test()
    
    if args.mode in ["source", "all"]:
        print()
        if prompt_user("Run SOURCE mode test?", ["y", "n"]) in ["y", "yes"]:
            results["source"] = run_interactive_source_test(args.skip_cleanup)
    
    if args.mode in ["embedded", "all"]:
        print()
        if prompt_user("Run EMBEDDED mode test? (requires build)", ["y", "n"]) in ["y", "yes"]:
            results["embedded"] = run_interactive_embedded_test(args.skip_cleanup)
    
    # Final summary
    print()
    print_header("FINAL SUMMARY")
    
    if not results:
        print_warning("No tests were run")
        return
    
    all_passed = True
    for mode, passed in results.items():
        if passed:
            print_success(f"{mode.upper()} mode: ALL TESTS PASSED")
        else:
            print_error(f"{mode.upper()} mode: SOME TESTS FAILED")
            all_passed = False
    
    print()
    if all_passed:
        print_success("All interactive tests passed! 🎉")
    else:
        print_error("Some tests failed. Please review the results above.")
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
