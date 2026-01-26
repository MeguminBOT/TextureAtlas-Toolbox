#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for translation system consistency.

Verifies that all translation-related code uses the unified context
and doesn't contain legacy patterns that would cause translation lookups
to fail.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

# Project paths
SRC_DIR = Path(__file__).parent.parent / "src"
UNIFIED_CONTEXT = "TextureAtlasToolboxApp"

# Add src to path for imports
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Legacy contexts that should NOT appear (except in comments/strings explaining them)
LEGACY_CONTEXTS = {
    "TextureAtlasToolboxApp",
    "ExtractTabWidget",
}

# Legacy method names that should NOT exist
LEGACY_METHODS = {"trc", "trd"}

# Legacy class attributes that should NOT exist
LEGACY_ATTRIBUTES = {
    "UI_CONSTANTS_CONTEXT",
    "DURATION_UTILS_CONTEXT",
    "TRANSLATION_CONTEXT",
}


def get_python_files():
    """Yield all Python files in the src directory."""
    for path in SRC_DIR.rglob("*.py"):
        # Skip __pycache__ directories
        if "__pycache__" in str(path):
            continue
        yield path


class TestTranslationContextConsistency:
    """Tests that all QT_TRANSLATE_NOOP calls use the unified context."""

    def test_qt_translate_noop_uses_unified_context(self):
        """All QT_TRANSLATE_NOOP calls should use TextureAtlasToolboxApp context."""
        pattern = re.compile(r'QT_TRANSLATE_NOOP\s*\(\s*["\']([^"\']+)["\']')
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                context = match.group(1)
                if context != UNIFIED_CONTEXT:
                    line_num = content[: match.start()].count("\n") + 1
                    violations.append(
                        f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                        f"QT_TRANSLATE_NOOP uses '{context}' instead of '{UNIFIED_CONTEXT}'"
                    )

        assert not violations, "Found QT_TRANSLATE_NOOP with wrong context:\n" + "\n".join(
            violations
        )

    def test_qcoreapplication_translate_uses_unified_context(self):
        """Direct QCoreApplication.translate calls should use unified context."""
        # Match QCoreApplication.translate("SomeContext", ...)
        pattern = re.compile(
            r'QCoreApplication\.translate\s*\(\s*["\']([^"\']+)["\']'
        )
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                context = match.group(1)
                # Allow the unified context and APP_TRANSLATION_CONTEXT variable reference
                if context != UNIFIED_CONTEXT and context in LEGACY_CONTEXTS:
                    line_num = content[: match.start()].count("\n") + 1
                    violations.append(
                        f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                        f"QCoreApplication.translate uses legacy context '{context}'"
                    )

        assert not violations, "Found QCoreApplication.translate with legacy context:\n" + "\n".join(
            violations
        )


class TestNoLegacyMethods:
    """Tests that legacy translation methods don't exist."""

    def test_no_trc_method_definitions(self):
        """No class should define a trc() method."""
        pattern = re.compile(r"def trc\s*\(")
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                    f"Found legacy 'def trc()' method definition"
                )

        assert not violations, "Found legacy trc method definitions:\n" + "\n".join(
            violations
        )

    def test_no_trd_method_definitions(self):
        """No class should define a trd() method."""
        pattern = re.compile(r"def trd\s*\(")
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                    f"Found legacy 'def trd()' method definition"
                )

        assert not violations, "Found legacy trd method definitions:\n" + "\n".join(
            violations
        )

    def test_no_trc_method_calls(self):
        """No code should call self.trc() or obj.trc()."""
        pattern = re.compile(r"\.trc\s*\(")
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                    f"Found legacy '.trc()' method call"
                )

        assert not violations, "Found legacy trc method calls:\n" + "\n".join(
            violations
        )

    def test_no_trd_method_calls(self):
        """No code should call self.trd() or obj.trd()."""
        pattern = re.compile(r"\.trd\s*\(")
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                    f"Found legacy '.trd()' method call"
                )

        assert not violations, "Found legacy trd method calls:\n" + "\n".join(
            violations
        )


class TestNoLegacyAttributes:
    """Tests that legacy context-related class attributes don't exist."""

    def test_no_ui_constants_context_attribute(self):
        """No class should have UI_CONSTANTS_CONTEXT attribute."""
        pattern = re.compile(r"^\s*UI_CONSTANTS_CONTEXT\s*=", re.MULTILINE)
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                    f"Found legacy 'UI_CONSTANTS_CONTEXT' attribute"
                )

        assert not violations, "Found legacy UI_CONSTANTS_CONTEXT attributes:\n" + "\n".join(
            violations
        )

    def test_no_duration_utils_context_attribute(self):
        """No class should have DURATION_UTILS_CONTEXT attribute."""
        pattern = re.compile(r"^\s*DURATION_UTILS_CONTEXT\s*=", re.MULTILINE)
        violations = []

        for filepath in get_python_files():
            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                    f"Found legacy 'DURATION_UTILS_CONTEXT' attribute"
                )

        assert not violations, "Found legacy DURATION_UTILS_CONTEXT attributes:\n" + "\n".join(
            violations
        )

    def test_no_translation_context_attribute(self):
        """No class should have TRANSLATION_CONTEXT attribute (except translation_manager.py)."""
        pattern = re.compile(r"^\s*TRANSLATION_CONTEXT\s*=", re.MULTILINE)
        violations = []

        for filepath in get_python_files():
            # Skip translation_manager.py which legitimately defines the context
            if filepath.name == "translation_manager.py":
                continue

            content = filepath.read_text(encoding="utf-8")
            for match in pattern.finditer(content):
                line_num = content[: match.start()].count("\n") + 1
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)}:{line_num} - "
                    f"Found legacy 'TRANSLATION_CONTEXT' class attribute"
                )

        assert not violations, "Found legacy TRANSLATION_CONTEXT attributes:\n" + "\n".join(
            violations
        )


class TestTranslationImports:
    """Tests that translation imports are correct."""

    def test_tr_imported_from_translation_manager(self):
        """Files using tr should import from utils.translation_manager."""
        # This is a soft check - we look for files that use self.tr but don't
        # have tr = translate pattern
        violations = []

        # Files to skip:
        # - ui_constants.py: Contains docstring examples, not actual code
        # - update_installer.py: Uses Qt's native QDialog.tr() method
        skip_files = {"ui_constants.py", "update_installer.py"}

        for filepath in get_python_files():
            if filepath.name in skip_files:
                continue

            content = filepath.read_text(encoding="utf-8")

            # Check if file uses self.tr(
            if "self.tr(" not in content:
                continue

            # Check if it has the tr = translate assignment (class attribute)
            # or imports tr directly
            has_tr_assignment = bool(
                re.search(r"^\s*tr\s*=\s*translate\s*$", content, re.MULTILINE)
            )
            has_tr_import = "from utils.translation_manager import" in content and "tr" in content

            if not (has_tr_assignment or has_tr_import):
                violations.append(
                    f"{filepath.relative_to(SRC_DIR)} - "
                    f"Uses self.tr() but doesn't have 'tr = translate' or proper import"
                )

        assert not violations, "Found files with missing tr setup:\n" + "\n".join(
            violations
        )


class TestUnifiedTranslatorWorks:
    """Tests that the unified translator functions correctly."""

    def test_tr_callable_directly(self):
        """tr() should work as a direct function call."""
        from utils.translation_manager import tr

        result = tr("Test string")
        assert isinstance(result, str)
        # Without translations loaded, should return the original
        assert result == "Test string"

    def test_tr_as_class_attribute(self):
        """tr should work when assigned as a class attribute."""
        from utils.translation_manager import translate

        class TestWidget:
            tr = translate

            def get_text(self):
                return self.tr("Hello world")

        widget = TestWidget()
        result = widget.get_text()
        assert isinstance(result, str)
        assert result == "Hello world"

    def test_unified_context_constant_exists(self):
        """APP_TRANSLATION_CONTEXT should be defined and correct."""
        from utils.translation_manager import APP_TRANSLATION_CONTEXT

        assert APP_TRANSLATION_CONTEXT == UNIFIED_CONTEXT

    def test_default_context_alias_exists(self):
        """DEFAULT_TRANSLATION_CONTEXT should alias APP_TRANSLATION_CONTEXT."""
        from utils.translation_manager import (
            APP_TRANSLATION_CONTEXT,
            DEFAULT_TRANSLATION_CONTEXT,
        )

        assert DEFAULT_TRANSLATION_CONTEXT == APP_TRANSLATION_CONTEXT


class TestUIConstantsContext:
    """Tests that ui_constants.py uses the correct context."""

    def test_all_ui_constants_use_unified_context(self):
        """All strings in ui_constants.py should use TextureAtlasToolboxApp context."""
        ui_constants_path = SRC_DIR / "utils" / "ui_constants.py"
        if not ui_constants_path.exists():
            pytest.skip("ui_constants.py not found")

        content = ui_constants_path.read_text(encoding="utf-8")
        pattern = re.compile(r'QT_TRANSLATE_NOOP\s*\(\s*["\']([^"\']+)["\']')

        contexts_found = set()
        for match in pattern.finditer(content):
            contexts_found.add(match.group(1))

        # All contexts should be the unified one
        assert contexts_found == {UNIFIED_CONTEXT}, (
            f"ui_constants.py should only use '{UNIFIED_CONTEXT}' context, "
            f"but found: {contexts_found}"
        )


class TestDurationUtilsContext:
    """Tests that duration_utils.py uses the correct context."""

    def test_all_duration_utils_use_unified_context(self):
        """All strings in duration_utils.py should use TextureAtlasToolboxApp context."""
        duration_utils_path = SRC_DIR / "utils" / "duration_utils.py"
        if not duration_utils_path.exists():
            pytest.skip("duration_utils.py not found")

        content = duration_utils_path.read_text(encoding="utf-8")
        pattern = re.compile(r'QT_TRANSLATE_NOOP\s*\(\s*["\']([^"\']+)["\']')

        violations = []
        for match in pattern.finditer(content):
            context = match.group(1)
            if context != UNIFIED_CONTEXT:
                line_num = content[: match.start()].count("\n") + 1
                violations.append(f"Line {line_num}: uses '{context}'")

        assert not violations, (
            f"duration_utils.py should only use '{UNIFIED_CONTEXT}' context:\n"
            + "\n".join(violations)
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
