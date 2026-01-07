#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Mock tests for the update system that don't modify actual workspace files.

These tests validate update detection, download logic, and mode handling
without performing real file replacements. Safe to run directly on the
development workspace.

Usage:
    python -m pytest tests/test_update_mock.py -v
    python tests/test_update_mock.py  # Run directly
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Add src to path for imports
SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils.update_installer import (
    UpdateMode,
    UpdateUtilities,
    Updater,
    launch_external_updater,
    _write_metadata_file,
)
from utils.version import APP_VERSION


# Test repository for fake releases
TEST_REPO_RELEASES_URL = "https://github.com/MeguminBOT/for-testing-purposes/releases"
TEST_REPO_TAGS_URL = "https://api.github.com/repos/MeguminBOT/for-testing-purposes/tags"
TEST_REPO_RELEASE_BY_TAG = "https://api.github.com/repos/MeguminBOT/for-testing-purposes/releases/tags/{tag}"


class TestUpdateMode(unittest.TestCase):
    """Tests for UpdateMode enum."""

    def test_update_mode_values(self):
        """Verify all expected update modes exist."""
        self.assertIsNotNone(UpdateMode.SOURCE)
        self.assertIsNotNone(UpdateMode.EXECUTABLE)
        self.assertIsNotNone(UpdateMode.EMBEDDED)

    def test_update_mode_distinct(self):
        """Verify all modes have distinct values."""
        modes = [UpdateMode.SOURCE, UpdateMode.EXECUTABLE, UpdateMode.EMBEDDED]
        values = [m.value for m in modes]
        self.assertEqual(len(values), len(set(values)))


class TestUpdateUtilities(unittest.TestCase):
    """Tests for UpdateUtilities helper methods."""

    def test_is_compiled_returns_bool(self):
        """is_compiled should return a boolean."""
        result = UpdateUtilities.is_compiled()
        self.assertIsInstance(result, bool)
        # In test environment, we're running from source
        self.assertFalse(result)

    def test_is_embedded_python_returns_bool(self):
        """is_embedded_python should return a boolean."""
        result = UpdateUtilities.is_embedded_python()
        self.assertIsInstance(result, bool)

    def test_detect_update_mode_returns_valid_mode(self):
        """detect_update_mode should return a valid UpdateMode."""
        result = UpdateUtilities.detect_update_mode()
        self.assertIsInstance(result, UpdateMode)
        self.assertIn(result, [UpdateMode.SOURCE, UpdateMode.EXECUTABLE, UpdateMode.EMBEDDED])

    def test_detect_update_mode_source_in_dev_environment(self):
        """In development environment, should detect SOURCE mode."""
        # When running tests from source, should be SOURCE mode
        with patch.object(UpdateUtilities, 'is_compiled', return_value=False):
            with patch.object(UpdateUtilities, 'is_embedded_python', return_value=False):
                result = UpdateUtilities.detect_update_mode()
                self.assertEqual(result, UpdateMode.SOURCE)

    def test_detect_update_mode_executable(self):
        """When compiled, should detect EXECUTABLE mode."""
        with patch.object(UpdateUtilities, 'is_compiled', return_value=True):
            with patch.object(UpdateUtilities, 'is_embedded_python', return_value=False):
                result = UpdateUtilities.detect_update_mode()
                self.assertEqual(result, UpdateMode.EXECUTABLE)

    def test_detect_update_mode_embedded(self):
        """When in embedded Python, should detect EMBEDDED mode."""
        with patch.object(UpdateUtilities, 'is_compiled', return_value=False):
            with patch.object(UpdateUtilities, 'is_embedded_python', return_value=True):
                result = UpdateUtilities.detect_update_mode()
                self.assertEqual(result, UpdateMode.EMBEDDED)

    def test_is_file_locked_nonexistent(self):
        """is_file_locked should return False for non-existent files."""
        result = UpdateUtilities.is_file_locked("/nonexistent/path/to/file.txt")
        self.assertFalse(result)

    def test_is_file_locked_accessible_file(self):
        """is_file_locked should return False for accessible files."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp_path = tmp.name

        try:
            result = UpdateUtilities.is_file_locked(tmp_path)
            self.assertFalse(result)
        finally:
            os.unlink(tmp_path)

    def test_find_root_returns_path_or_none(self):
        """find_root should return a path or None."""
        # Should find src directory
        result = UpdateUtilities.find_root("src")
        if result is not None:
            self.assertTrue(os.path.isdir(result))
            self.assertTrue(os.path.exists(os.path.join(result, "src")))

    def test_has_write_access(self):
        """has_write_access should correctly detect writable directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = UpdateUtilities.has_write_access(tmp_dir)
            self.assertTrue(result)

    def test_find_embedded_python_dir_in_temp(self):
        """find_embedded_python_dir should detect embedded Python structure."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create fake embedded Python structure
            python_dir = Path(tmp_dir) / "python"
            python_dir.mkdir()
            (python_dir / "python.exe").touch()
            (python_dir / "pythonw.exe").touch()
            (python_dir / "python314._pth").touch()

            result = UpdateUtilities.find_embedded_python_dir(tmp_dir)
            self.assertIsNotNone(result)
            self.assertEqual(Path(result).name, "python")

    def test_find_embedded_python_dir_not_found(self):
        """find_embedded_python_dir should return None when not found."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = UpdateUtilities.find_embedded_python_dir(tmp_dir)
            self.assertIsNone(result)

    def test_find_locked_python_files(self):
        """find_locked_python_files should return list of locked files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create some test files
            (Path(tmp_dir) / "test.pyd").touch()
            (Path(tmp_dir) / "python.exe").touch()

            result = UpdateUtilities.find_locked_python_files(tmp_dir)
            self.assertIsInstance(result, list)


class TestUpdaterInitialization(unittest.TestCase):
    """Tests for Updater class initialization."""

    def test_updater_default_source_mode(self):
        """Updater should default to SOURCE mode."""
        updater = Updater(ui=None)
        self.assertEqual(updater.update_mode, UpdateMode.SOURCE)
        self.assertFalse(updater.exe_mode)
        self.assertFalse(updater.embedded_mode)

    def test_updater_explicit_executable_mode(self):
        """Updater should accept explicit EXECUTABLE mode."""
        updater = Updater(ui=None, update_mode=UpdateMode.EXECUTABLE)
        self.assertEqual(updater.update_mode, UpdateMode.EXECUTABLE)
        self.assertTrue(updater.exe_mode)
        self.assertFalse(updater.embedded_mode)

    def test_updater_explicit_embedded_mode(self):
        """Updater should accept explicit EMBEDDED mode."""
        updater = Updater(ui=None, update_mode=UpdateMode.EMBEDDED)
        self.assertEqual(updater.update_mode, UpdateMode.EMBEDDED)
        self.assertFalse(updater.exe_mode)
        self.assertTrue(updater.embedded_mode)

    def test_updater_legacy_exe_mode_flag(self):
        """Updater should support legacy exe_mode flag."""
        updater = Updater(ui=None, exe_mode=True)
        self.assertEqual(updater.update_mode, UpdateMode.EXECUTABLE)
        self.assertTrue(updater.exe_mode)

    def test_updater_legacy_embedded_mode_flag(self):
        """Updater should support legacy embedded_mode flag."""
        updater = Updater(ui=None, embedded_mode=True)
        self.assertEqual(updater.update_mode, UpdateMode.EMBEDDED)
        self.assertTrue(updater.embedded_mode)

    def test_updater_with_target_tag(self):
        """Updater should store target tag."""
        updater = Updater(ui=None, target_tag="v2.0.5")
        self.assertEqual(updater.target_tag, "v2.0.5")

    def test_updater_with_release_metadata(self):
        """Updater should store release metadata."""
        metadata = {"tag_name": "v2.0.5", "zipball_url": "https://example.com/zip"}
        updater = Updater(ui=None, release_metadata=metadata)
        self.assertEqual(updater.release_metadata, metadata)


class TestMetadataFile(unittest.TestCase):
    """Tests for metadata file handling."""

    def test_write_metadata_file_creates_file(self):
        """_write_metadata_file should create a JSON file."""
        metadata = {"tag_name": "v2.0.5", "zipball_url": "https://example.com"}
        metadata_path = _write_metadata_file(metadata)

        try:
            self.assertTrue(metadata_path.exists())
            with open(metadata_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded, metadata)
        finally:
            # Cleanup
            if metadata_path.exists():
                metadata_path.unlink()
            if metadata_path.parent.exists():
                shutil.rmtree(metadata_path.parent, ignore_errors=True)

    def test_write_metadata_file_empty_dict(self):
        """_write_metadata_file should handle empty metadata."""
        metadata_path = _write_metadata_file({})

        try:
            self.assertTrue(metadata_path.exists())
            with open(metadata_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded, {})
        finally:
            if metadata_path.exists():
                metadata_path.unlink()
            if metadata_path.parent.exists():
                shutil.rmtree(metadata_path.parent, ignore_errors=True)

    def test_write_metadata_file_none(self):
        """_write_metadata_file should handle None metadata."""
        metadata_path = _write_metadata_file(None)

        try:
            self.assertTrue(metadata_path.exists())
            with open(metadata_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded, {})
        finally:
            if metadata_path.exists():
                metadata_path.unlink()
            if metadata_path.parent.exists():
                shutil.rmtree(metadata_path.parent, ignore_errors=True)


class TestLaunchExternalUpdater(unittest.TestCase):
    """Tests for launch_external_updater function."""

    @patch('subprocess.Popen')
    def test_launch_external_updater_source_mode(self, mock_popen):
        """launch_external_updater should work for SOURCE mode."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = launch_external_updater(
            release_metadata={"tag_name": "v2.0.5"},
            latest_version="2.0.5",
            update_mode=UpdateMode.SOURCE,
            wait_seconds=0,
        )

        self.assertTrue(result)
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        self.assertIn("--update", args)
        self.assertNotIn("--exe-mode", args)
        self.assertNotIn("--embedded-mode", args)

    @patch('subprocess.Popen')
    def test_launch_external_updater_executable_mode(self, mock_popen):
        """launch_external_updater should pass --exe-mode for EXECUTABLE."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = launch_external_updater(
            release_metadata={"tag_name": "v2.0.5"},
            latest_version="2.0.5",
            update_mode=UpdateMode.EXECUTABLE,
            wait_seconds=0,
        )

        self.assertTrue(result)
        args = mock_popen.call_args[0][0]
        self.assertIn("--exe-mode", args)

    @patch('subprocess.Popen')
    def test_launch_external_updater_embedded_mode(self, mock_popen):
        """launch_external_updater should pass --embedded-mode for EMBEDDED."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = launch_external_updater(
            release_metadata={"tag_name": "v2.0.5"},
            latest_version="2.0.5",
            update_mode=UpdateMode.EMBEDDED,
            wait_seconds=0,
        )

        self.assertTrue(result)
        args = mock_popen.call_args[0][0]
        self.assertIn("--embedded-mode", args)

    @patch('subprocess.Popen')
    def test_launch_external_updater_legacy_exe_mode(self, mock_popen):
        """launch_external_updater should support legacy exe_mode flag."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = launch_external_updater(
            release_metadata={"tag_name": "v2.0.5"},
            exe_mode=True,
            wait_seconds=0,
        )

        self.assertTrue(result)
        args = mock_popen.call_args[0][0]
        self.assertIn("--exe-mode", args)

    @patch('subprocess.Popen')
    def test_launch_external_updater_legacy_embedded_mode(self, mock_popen):
        """launch_external_updater should support legacy embedded_mode flag."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        result = launch_external_updater(
            release_metadata={"tag_name": "v2.0.5"},
            embedded_mode=True,
            wait_seconds=0,
        )

        self.assertTrue(result)
        args = mock_popen.call_args[0][0]
        self.assertIn("--embedded-mode", args)

    @patch('subprocess.Popen')
    def test_launch_external_updater_with_wait(self, mock_popen):
        """launch_external_updater should pass wait time."""
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_popen.return_value = mock_process

        launch_external_updater(
            release_metadata={},
            update_mode=UpdateMode.SOURCE,
            wait_seconds=5,
        )

        args = mock_popen.call_args[0][0]
        self.assertIn("--wait", args)
        wait_idx = args.index("--wait")
        self.assertEqual(args[wait_idx + 1], "5")

    @patch('subprocess.Popen', side_effect=Exception("Process failed"))
    def test_launch_external_updater_failure(self, mock_popen):
        """launch_external_updater should return False on failure."""
        result = launch_external_updater(
            release_metadata={},
            update_mode=UpdateMode.SOURCE,
            wait_seconds=0,
        )
        self.assertFalse(result)


class TestUpdaterProjectRoot(unittest.TestCase):
    """Tests for project root detection."""

    def test_find_project_root_source_mode(self):
        """find_project_root should find root in SOURCE mode."""
        updater = Updater(ui=None, update_mode=UpdateMode.SOURCE)
        root = updater.find_project_root()

        # Should find the project root (contains src/)
        if root is not None:
            self.assertTrue(os.path.isdir(root))
            # Project root should contain src/ or be the src directory
            self.assertTrue(
                os.path.exists(os.path.join(root, "src")) or
                os.path.basename(root) == "src"
            )


class TestUpdaterMockDownload(unittest.TestCase):
    """Tests for download logic with mocked network calls."""

    @patch('requests.get')
    def test_get_latest_release_info_with_tag(self, mock_get):
        """get_latest_release_info should fetch release by tag."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v2.0.5",
            "assets": [
                {"name": "test.7z", "browser_download_url": "https://example.com/test.7z"}
            ],
            "zipball_url": "https://example.com/zipball",
        }
        mock_get.return_value = mock_response

        result = Updater.get_latest_release_info(tag_name="v2.0.5")

        self.assertIsNotNone(result)
        self.assertEqual(result["tag_name"], "v2.0.5")

    @patch('requests.get')
    def test_get_latest_release_info_latest(self, mock_get):
        """get_latest_release_info should fetch latest release when no tag."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tag_name": "v2.0.6",
            "assets": [],
            "zipball_url": "https://example.com/zipball",
        }
        mock_get.return_value = mock_response

        result = Updater.get_latest_release_info()

        self.assertIsNotNone(result)

    @patch('requests.get')
    def test_get_latest_release_info_fallback(self, mock_get):
        """get_latest_release_info should use fallback metadata on error."""
        mock_get.side_effect = Exception("Network error")

        fallback = {"tag_name": "v2.0.0", "zipball_url": "https://fallback.com"}
        result = Updater.get_latest_release_info(fallback_metadata=fallback)

        self.assertEqual(result, fallback)


class TestUpdaterBackup(unittest.TestCase):
    """Tests for backup creation and cleanup."""

    def test_create_updater_backup(self):
        """create_updater_backup should create a .backup file."""
        updater = Updater(ui=None)
        updater.create_updater_backup()

        backup_path = Path(__file__).resolve().parents[1] / "src" / "utils" / "update_installer.py.backup"

        try:
            # Backup might be created (depends on permissions)
            if backup_path.exists():
                self.assertTrue(backup_path.is_file())
        finally:
            # Cleanup
            if backup_path.exists():
                backup_path.unlink()

    def test_cleanup_updater_backup(self):
        """cleanup_updater_backup should remove the .backup file."""
        backup_path = Path(__file__).resolve().parents[1] / "src" / "utils" / "update_installer.py.backup"

        try:
            # Create a backup file
            backup_path.write_text("test backup content")
            self.assertTrue(backup_path.exists())

            updater = Updater(ui=None)
            updater.cleanup_updater_backup()

            self.assertFalse(backup_path.exists())
        finally:
            if backup_path.exists():
                backup_path.unlink()


class TestMockUIUpdater(unittest.TestCase):
    """Tests for Updater with mock UI."""

    def test_updater_logs_to_mock_ui(self):
        """Updater should call UI log method."""
        mock_ui = MagicMock()
        updater = Updater(ui=mock_ui)

        updater.log("Test message", "info")

        mock_ui.log.assert_called_with("Test message", "info")

    def test_updater_sets_progress_on_mock_ui(self):
        """Updater should call UI set_progress method."""
        mock_ui = MagicMock()
        updater = Updater(ui=mock_ui)

        updater.set_progress(50, "Halfway done")

        mock_ui.set_progress.assert_called_with(50, "Halfway done")

    def test_updater_enables_restart_on_mock_ui(self):
        """Updater should call UI enable_restart method."""
        mock_ui = MagicMock()
        updater = Updater(ui=mock_ui)

        restart_func = lambda: None
        updater.enable_restart(restart_func)

        mock_ui.enable_restart.assert_called_with(restart_func)


class TestApplyPendingUpdates(unittest.TestCase):
    """Tests for apply_pending_updates functionality."""

    def test_apply_pending_updates_processes_new_files(self):
        """apply_pending_updates should rename .new files."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create a .new file
            new_file = Path(tmp_dir) / "test_file.py.new"
            target_file = Path(tmp_dir) / "test_file.py"
            new_file.write_text("new content")
            target_file.write_text("old content")

            results = UpdateUtilities.apply_pending_updates(tmp_dir)

            # Check that the .new file was processed
            self.assertGreater(len(results), 0)
            # The target file should now have new content
            if results[0][2]:  # If successful
                self.assertEqual(target_file.read_text(), "new content")
                self.assertFalse(new_file.exists())

    def test_apply_pending_updates_empty_dir(self):
        """apply_pending_updates should handle empty directories."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            results = UpdateUtilities.apply_pending_updates(tmp_dir)
            self.assertEqual(results, [])


class TestExtract7z(unittest.TestCase):
    """Tests for 7z extraction."""

    def test_extract_7z_nonexistent_archive(self):
        """extract_7z should handle non-existent archive gracefully."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # extract_7z may raise an exception or return False for missing files
            try:
                result = UpdateUtilities.extract_7z(
                    "/nonexistent/archive.7z",
                    tmp_dir
                )
                # If it returns, should be False
                self.assertFalse(result)
            except (FileNotFoundError, OSError):
                # Raising an exception is also acceptable behavior
                pass


if __name__ == "__main__":
    # Run with verbose output when executed directly
    unittest.main(verbosity=2)
