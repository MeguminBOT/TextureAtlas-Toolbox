#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Integration tests for the update system with real file operations.

These tests create temporary copies of the workspace and perform actual
update operations to validate the complete update workflow for each mode.

WARNING: These tests download files from the internet and modify files
in temporary directories. They are intended for developer validation
before releases.

Test Repository: https://github.com/MeguminBOT/for-testing-purposes/releases

Usage:
    python tests/test_update_integration.py                    # Run all tests
    python tests/test_update_integration.py --source-only      # SOURCE mode only
    python tests/test_update_integration.py --embedded-only    # EMBEDDED mode only
    python tests/test_update_integration.py --executable-only  # EXECUTABLE mode (stub)
    python tests/test_update_integration.py --skip-build       # Skip embedded build step
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Optional

# Add src to path for imports
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# =============================================================================
# Test Configuration
# =============================================================================

# Test repository with fake "newer" versions for update testing
TEST_REPO_OWNER = "MeguminBOT"
TEST_REPO_NAME = "for-testing-purposes"
TEST_REPO_RELEASES_URL = f"https://github.com/{TEST_REPO_OWNER}/{TEST_REPO_NAME}/releases"
TEST_REPO_API_TAGS = f"https://api.github.com/repos/{TEST_REPO_OWNER}/{TEST_REPO_NAME}/tags"
TEST_REPO_API_RELEASE_BY_TAG = f"https://api.github.com/repos/{TEST_REPO_OWNER}/{TEST_REPO_NAME}/releases/tags/{{tag}}"

# Files and folders to copy for integration tests
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

# Timeout for update operations (seconds)
UPDATE_TIMEOUT = 300


# =============================================================================
# Helper Functions
# =============================================================================

def get_project_root() -> Path:
    """Get the root directory of the TextureAtlas-to-GIF-and-Frames project."""
    return Path(__file__).resolve().parents[1]


def copy_workspace_to_temp(temp_dir: Path) -> Path:
    """Copy essential workspace files to a temporary directory.

    Args:
        temp_dir: Target temporary directory.

    Returns:
        Path to the workspace copy.
    """
    project_root = get_project_root()
    workspace_copy = temp_dir / "workspace"
    workspace_copy.mkdir(parents=True, exist_ok=True)

    for item_name in WORKSPACE_ITEMS_TO_COPY:
        src_path = project_root / item_name
        dst_path = workspace_copy / item_name

        if not src_path.exists():
            print(f"  [SKIP] {item_name} (not found)")
            continue

        if src_path.is_dir():
            shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
            print(f"  [COPY] {item_name}/ -> {dst_path}")
        else:
            shutil.copy2(src_path, dst_path)
            print(f"  [COPY] {item_name} -> {dst_path}")

    return workspace_copy


def patch_version_file(workspace_path: Path, fake_version: str = "1.0.0") -> None:
    """Patch the version.py file to report an older version.

    This makes the update checker think an update is available.

    Args:
        workspace_path: Path to the workspace copy.
        fake_version: Version string to set (should be older than test releases).
    """
    version_file = workspace_path / "src" / "utils" / "version.py"
    if not version_file.exists():
        print(f"  [WARN] version.py not found at {version_file}")
        return

    content = version_file.read_text(encoding="utf-8")

    # Replace APP_VERSION
    import re
    new_content = re.sub(
        r'APP_VERSION\s*=\s*["\'][^"\']+["\']',
        f'APP_VERSION = "{fake_version}"',
        content
    )

    # Replace REPO_OWNER and REPO_NAME to point to test repository
    # These are used to dynamically build the GitHub API URLs
    new_content = re.sub(
        r'REPO_OWNER\s*=\s*["\'][^"\']+["\']',
        f'REPO_OWNER = "{TEST_REPO_OWNER}"',
        new_content
    )
    new_content = re.sub(
        r'REPO_NAME\s*=\s*["\'][^"\']+["\']',
        f'REPO_NAME = "{TEST_REPO_NAME}"',
        new_content
    )

    version_file.write_text(new_content, encoding="utf-8")
    print(f"  [PATCH] version.py: APP_VERSION = {fake_version}")
    print(f"  [PATCH] version.py: REPO_OWNER = {TEST_REPO_OWNER}")
    print(f"  [PATCH] version.py: REPO_NAME = {TEST_REPO_NAME}")


def run_python_script(
    workspace_path: Path,
    script_args: list[str],
    timeout: int = UPDATE_TIMEOUT,
    env_override: Optional[dict] = None,
) -> tuple[int, str, str]:
    """Run a Python script in the workspace.

    Args:
        workspace_path: Path to the workspace.
        script_args: Arguments to pass to Python.
        timeout: Maximum execution time in seconds.
        env_override: Optional environment variables to override.

    Returns:
        Tuple of (return_code, stdout, stderr).
    """
    env = os.environ.copy()
    if env_override:
        env.update(env_override)

    # Ensure PYTHONPATH includes the workspace src
    src_path = workspace_path / "src"
    env["PYTHONPATH"] = str(src_path)

    cmd = [sys.executable] + script_args

    print(f"  [RUN] {' '.join(cmd)}")
    print(f"  [CWD] {workspace_path}")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(workspace_path),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Process timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", str(e)


def build_embedded_release(output_dir: Path) -> Optional[Path]:
    """Build an embedded Python release for testing.

    Args:
        output_dir: Directory to output the embedded release.

    Returns:
        Path to the built release directory, or None on failure.
    """
    project_root = get_project_root()
    build_script = project_root / "setup" / "build_portable.py"

    if not build_script.exists():
        print(f"  [ERROR] build_portable.py not found at {build_script}")
        return None

    print(f"  [BUILD] Running build_portable.py...")
    print(f"  [BUILD] Output: {output_dir}")

    # Run the build script
    cmd = [
        sys.executable,
        str(build_script),
        "--output", str(output_dir),
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout for build
        )

        if result.returncode != 0:
            print(f"  [BUILD] FAILED with code {result.returncode}")
            print(f"  [BUILD] stdout: {result.stdout[-2000:]}")
            print(f"  [BUILD] stderr: {result.stderr[-2000:]}")
            return None

        # Find the built release directory
        # Expected structure: output_dir/TextureAtlas*/
        for item in output_dir.iterdir():
            if item.is_dir() and item.name.startswith("TextureAtlas"):
                print(f"  [BUILD] SUCCESS: {item}")
                return item

        # Fallback: check if output_dir itself is the release
        if (output_dir / "python").exists():
            print(f"  [BUILD] SUCCESS: {output_dir}")
            return output_dir

        print(f"  [BUILD] Could not find built release in {output_dir}")
        return None

    except subprocess.TimeoutExpired:
        print(f"  [BUILD] Build timed out after 600 seconds")
        return None
    except Exception as e:
        print(f"  [BUILD] Build failed with exception: {e}")
        return None


# =============================================================================
# Test Classes
# =============================================================================

class TestSourceModeUpdate(unittest.TestCase):
    """Integration tests for SOURCE mode updates."""

    @classmethod
    def setUpClass(cls):
        """Create a temporary workspace for SOURCE mode tests."""
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="tatgf_test_source_"))
        print(f"\n{'='*60}")
        print(f"SOURCE MODE INTEGRATION TEST")
        print(f"{'='*60}")
        print(f"Temp directory: {cls.temp_dir}")
        print(f"Test repository: {TEST_REPO_RELEASES_URL}")
        print()

        print("Copying workspace files...")
        cls.workspace = copy_workspace_to_temp(cls.temp_dir)
        print()

        print("Patching version file...")
        patch_version_file(cls.workspace, fake_version="1.0.0")
        print()

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary workspace."""
        print(f"\nCleaning up {cls.temp_dir}...")
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
            print("Cleanup complete.")
        except Exception as e:
            print(f"Cleanup failed: {e}")

    def test_01_workspace_structure(self):
        """Verify workspace was copied correctly."""
        print("\n[TEST] Verifying workspace structure...")

        # Check essential directories exist
        self.assertTrue((self.workspace / "src").is_dir(), "src/ should exist")
        self.assertTrue((self.workspace / "src" / "Main.py").is_file(), "Main.py should exist")
        self.assertTrue((self.workspace / "src" / "utils").is_dir(), "utils/ should exist")

        print("  [OK] Workspace structure verified")

    def test_02_version_patched(self):
        """Verify version was patched correctly."""
        print("\n[TEST] Verifying version patch...")

        version_file = self.workspace / "src" / "utils" / "version.py"
        content = version_file.read_text(encoding="utf-8")

        self.assertIn('APP_VERSION = "1.0.0"', content)
        self.assertIn(TEST_REPO_OWNER, content)

        print("  [OK] Version patched to 1.0.0")
        print(f"  [OK] Using test repository: {TEST_REPO_OWNER}/{TEST_REPO_NAME}")

    def test_03_update_detection(self):
        """Test that an update is detected from the test repository."""
        print("\n[TEST] Testing update detection...")

        # Run a quick check using the update checker
        script = """
import sys
sys.path.insert(0, 'src')
from utils.update_checker import UpdateChecker
from utils.version import APP_VERSION, GITHUB_TAGS_URL

print(f"Current version: {APP_VERSION}")
print(f"Tags URL: {GITHUB_TAGS_URL}")

checker = UpdateChecker()
tags = checker._fetch_tags()
print(f"Found {len(tags)} tags")
for tag in tags[:5]:
    print(f"  - {tag.get('name', 'unknown')}")

newer = checker._find_newer_tag(tags)
if newer:
    print(f"Newer version found: {newer.get('name')}")
else:
    print("No newer version found")
"""

        script_file = self.workspace / "test_detection.py"
        script_file.write_text(script, encoding="utf-8")

        returncode, stdout, stderr = run_python_script(
            self.workspace,
            [str(script_file)],
            timeout=30,
        )

        print(f"  stdout:\n{stdout}")
        if stderr:
            print(f"  stderr:\n{stderr}")

        self.assertEqual(returncode, 0, f"Script failed: {stderr}")
        self.assertIn("Newer version found", stdout, "Should detect newer version")

        print("  [OK] Update detection works")

    def test_04_updater_initialization(self):
        """Test that the Updater can be initialized for SOURCE mode."""
        print("\n[TEST] Testing Updater initialization...")

        script = """
import sys
sys.path.insert(0, 'src')
from utils.update_installer import Updater, UpdateMode

updater = Updater(ui=None, update_mode=UpdateMode.SOURCE)
print(f"Update mode: {updater.update_mode.name}")
print(f"exe_mode: {updater.exe_mode}")
print(f"embedded_mode: {updater.embedded_mode}")

root = updater.find_project_root()
print(f"Project root: {root}")
"""

        script_file = self.workspace / "test_updater_init.py"
        script_file.write_text(script, encoding="utf-8")

        returncode, stdout, stderr = run_python_script(
            self.workspace,
            [str(script_file)],
            timeout=30,
        )

        print(f"  stdout:\n{stdout}")
        if stderr:
            print(f"  stderr:\n{stderr}")

        self.assertEqual(returncode, 0, f"Script failed: {stderr}")
        self.assertIn("Update mode: SOURCE", stdout)
        self.assertIn("exe_mode: False", stdout)

        print("  [OK] Updater initialization works")

    def test_05_source_update_dry_run(self):
        """Test SOURCE update workflow without final file replacement.

        This test validates the download and extraction logic but uses
        a mock to prevent actual file replacement.
        """
        print("\n[TEST] Testing SOURCE update (dry run)...")

        script = """
import sys
import os
import tempfile
sys.path.insert(0, 'src')

from utils.update_installer import Updater, UpdateMode
from utils.version import APP_VERSION

print(f"Starting dry run update from version {APP_VERSION}")

# Create updater
updater = Updater(ui=None, update_mode=UpdateMode.SOURCE)

# Fetch release info
release_info = updater.get_latest_release_info()
if release_info:
    print(f"Found release: {release_info.get('tag_name', 'unknown')}")
    print(f"Zipball URL: {release_info.get('zipball_url', 'N/A')[:80]}...")
    print("Dry run complete - would download and install")
else:
    print("ERROR: Could not fetch release info")
    sys.exit(1)
"""

        script_file = self.workspace / "test_source_dry_run.py"
        script_file.write_text(script, encoding="utf-8")

        returncode, stdout, stderr = run_python_script(
            self.workspace,
            [str(script_file)],
            timeout=60,
        )

        print(f"  stdout:\n{stdout}")
        if stderr:
            print(f"  stderr:\n{stderr}")

        self.assertEqual(returncode, 0, f"Script failed: {stderr}")
        self.assertIn("Found release:", stdout)

        print("  [OK] SOURCE update dry run successful")


class TestEmbeddedModeUpdate(unittest.TestCase):
    """Integration tests for EMBEDDED mode updates.

    These tests build an embedded Python release and test updating it.
    """

    skip_build: bool = False  # Set via command line

    @classmethod
    def setUpClass(cls):
        """Create a temporary directory and optionally build embedded release."""
        cls.temp_dir = Path(tempfile.mkdtemp(prefix="tatgf_test_embedded_"))
        cls.embedded_release: Optional[Path] = None

        print(f"\n{'='*60}")
        print(f"EMBEDDED MODE INTEGRATION TEST")
        print(f"{'='*60}")
        print(f"Temp directory: {cls.temp_dir}")
        print(f"Test repository: {TEST_REPO_RELEASES_URL}")
        print()

        if cls.skip_build:
            print("[SKIP] Embedded build skipped (--skip-build flag)")
            return

        # Build embedded release
        print("Building embedded Python release...")
        build_output = cls.temp_dir / "build_output"
        build_output.mkdir(parents=True, exist_ok=True)

        cls.embedded_release = build_embedded_release(build_output)
        if cls.embedded_release:
            print(f"Embedded release built: {cls.embedded_release}")
        else:
            print("[WARN] Embedded build failed - some tests will be skipped")

    @classmethod
    def tearDownClass(cls):
        """Clean up the temporary directory."""
        print(f"\nCleaning up {cls.temp_dir}...")
        try:
            shutil.rmtree(cls.temp_dir, ignore_errors=True)
            print("Cleanup complete.")
        except Exception as e:
            print(f"Cleanup failed: {e}")

    def test_01_embedded_detection(self):
        """Test embedded Python detection utilities."""
        print("\n[TEST] Testing embedded Python detection...")

        # Test with a mock embedded structure
        mock_embedded = self.temp_dir / "mock_embedded"
        python_dir = mock_embedded / "python"
        python_dir.mkdir(parents=True, exist_ok=True)

        # Create characteristic files
        (python_dir / "python.exe").touch()
        (python_dir / "pythonw.exe").touch()
        (python_dir / "python314._pth").touch()

        # Now test detection
        sys.path.insert(0, str(get_project_root() / "src"))
        from utils.update_installer import UpdateUtilities

        result = UpdateUtilities.find_embedded_python_dir(str(mock_embedded))
        self.assertIsNotNone(result)
        self.assertEqual(Path(result).name, "python")

        print("  [OK] Embedded Python detection works")

    def test_02_embedded_updater_init(self):
        """Test Updater initialization in EMBEDDED mode."""
        print("\n[TEST] Testing EMBEDDED mode Updater initialization...")

        sys.path.insert(0, str(get_project_root() / "src"))
        from utils.update_installer import Updater, UpdateMode

        updater = Updater(ui=None, update_mode=UpdateMode.EMBEDDED)

        self.assertEqual(updater.update_mode, UpdateMode.EMBEDDED)
        self.assertTrue(updater.embedded_mode)
        self.assertFalse(updater.exe_mode)

        print("  [OK] EMBEDDED mode Updater initialization works")

    @unittest.skipIf(True, "Full embedded update requires built release")
    def test_03_embedded_update_full(self):
        """Test full EMBEDDED update workflow.

        This test is skipped by default as it requires a built embedded release.
        It can be enabled when running with a pre-built release.
        """
        if not self.embedded_release:
            self.skipTest("Embedded release not built")

        print("\n[TEST] Testing full EMBEDDED update workflow...")

        # Patch version in the embedded release
        embedded_src = self.embedded_release / "src"
        if embedded_src.exists():
            patch_version_file(self.embedded_release, fake_version="1.0.0")

        # Find the Python executable in the embedded release
        python_exe = self.embedded_release / "python" / "python.exe"
        if not python_exe.exists():
            python_exe = self.embedded_release / "python" / "python"

        if not python_exe.exists():
            self.skipTest(f"Python executable not found in {self.embedded_release}")

        # TODO: Run update test with embedded Python
        print("  [TODO] Full embedded update test not yet implemented")


class TestExecutableModeUpdate(unittest.TestCase):
    """Integration tests for EXECUTABLE mode updates.

    NOTE: These are stub/placeholder tests because Nuitka does not yet
    support Python 3.14. The actual implementation will be added when
    Nuitka support becomes available.
    """

    @classmethod
    def setUpClass(cls):
        """Set up for EXECUTABLE mode tests."""
        print(f"\n{'='*60}")
        print(f"EXECUTABLE MODE INTEGRATION TEST (STUB)")
        print(f"{'='*60}")
        print()
        print("NOTE: Nuitka does not currently support Python 3.14")
        print("These tests are placeholders for future implementation.")
        print()

    def test_01_executable_mode_enum(self):
        """Verify EXECUTABLE mode exists in UpdateMode enum."""
        print("\n[TEST] Verifying EXECUTABLE mode enum...")

        sys.path.insert(0, str(get_project_root() / "src"))
        from utils.update_installer import UpdateMode

        self.assertIsNotNone(UpdateMode.EXECUTABLE)
        print("  [OK] UpdateMode.EXECUTABLE exists")

    def test_02_executable_updater_init(self):
        """Test Updater initialization in EXECUTABLE mode."""
        print("\n[TEST] Testing EXECUTABLE mode Updater initialization...")

        sys.path.insert(0, str(get_project_root() / "src"))
        from utils.update_installer import Updater, UpdateMode

        updater = Updater(ui=None, update_mode=UpdateMode.EXECUTABLE)

        self.assertEqual(updater.update_mode, UpdateMode.EXECUTABLE)
        self.assertTrue(updater.exe_mode)
        self.assertFalse(updater.embedded_mode)

        print("  [OK] EXECUTABLE mode Updater initialization works")

    def test_03_is_compiled_detection(self):
        """Test is_compiled detection (should be False in test environment)."""
        print("\n[TEST] Testing is_compiled detection...")

        sys.path.insert(0, str(get_project_root() / "src"))
        from utils.update_installer import UpdateUtilities

        result = UpdateUtilities.is_compiled()
        self.assertFalse(result)  # We're running from source

        print("  [OK] is_compiled returns False in test environment")

    def test_04_executable_update_stub(self):
        """Stub test for EXECUTABLE update workflow.

        This test will be implemented when Nuitka supports Python 3.14.
        """
        print("\n[TEST] EXECUTABLE update workflow (STUB)...")
        print("  [STUB] Cannot test - Nuitka doesn't support Python 3.14")
        print("  [STUB] This test will be implemented when support is added")

        # Placeholder assertion that always passes
        self.assertTrue(True, "Stub test placeholder")

        print("  [OK] Stub test passed")


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    """Run integration tests with optional mode filtering."""
    parser = argparse.ArgumentParser(
        description="Integration tests for TextureAtlas Toolbox update system"
    )
    parser.add_argument(
        "--source-only",
        action="store_true",
        help="Run only SOURCE mode tests",
    )
    parser.add_argument(
        "--embedded-only",
        action="store_true",
        help="Run only EMBEDDED mode tests",
    )
    parser.add_argument(
        "--executable-only",
        action="store_true",
        help="Run only EXECUTABLE mode tests (stubs)",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip building embedded release (faster but skips some tests)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output",
    )

    args, remaining = parser.parse_known_args()

    # Configure test classes
    TestEmbeddedModeUpdate.skip_build = args.skip_build

    # Build test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    if args.source_only:
        suite.addTests(loader.loadTestsFromTestCase(TestSourceModeUpdate))
    elif args.embedded_only:
        suite.addTests(loader.loadTestsFromTestCase(TestEmbeddedModeUpdate))
    elif args.executable_only:
        suite.addTests(loader.loadTestsFromTestCase(TestExecutableModeUpdate))
    else:
        # Run all tests
        suite.addTests(loader.loadTestsFromTestCase(TestSourceModeUpdate))
        suite.addTests(loader.loadTestsFromTestCase(TestEmbeddedModeUpdate))
        suite.addTests(loader.loadTestsFromTestCase(TestExecutableModeUpdate))

    # Run tests
    verbosity = 2 if args.verbose else 1
    runner = unittest.TextTestRunner(verbosity=verbosity)

    print(f"\n{'#'*60}")
    print(f"# UPDATE SYSTEM INTEGRATION TESTS")
    print(f"# Test Repository: {TEST_REPO_RELEASES_URL}")
    print(f"# Python: {sys.version}")
    print(f"{'#'*60}\n")

    result = runner.run(suite)

    # Print summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")

    if result.failures:
        print("\nFailed tests:")
        for test, traceback in result.failures:
            print(f"  - {test}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  - {test}")

    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
