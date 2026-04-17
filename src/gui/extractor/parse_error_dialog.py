#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dialog for displaying parse errors and warnings before extraction.

Provides a confirmation dialog that shows users any parsing issues detected
in their spritesheet metadata files, with options to continue, skip files,
or cancel the operation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QCheckBox,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels, CheckBoxLabels, DialogTitles, MenuActions

from parsers.parser_types import ParseResult, ParserErrorCode


class ParseErrorDialog(QDialog):
    """Dialog showing parse errors/warnings with options to continue or skip files.

    Usage:
        results = {
            "sprite1.png": parse_result1,
            "sprite2.png": parse_result2,
        }
        dialog = ParseErrorDialog(parent, results)
        action, files_to_skip = dialog.exec_and_get_result()
        if action == "cancel":
            return
        elif action == "continue":
            # Process all files, including those with errors
            pass
        elif action == "skip":
            # files_to_skip contains list of files user chose to skip
            pass
    """

    # Icons for different severity levels (using unicode for portability)
    ICON_ERROR = "❌"
    ICON_WARNING = "⚠️"
    ICON_INFO = "ℹ️"

    tr = translate

    def __init__(
        self,
        parent,
        parse_results: Dict[str, ParseResult],
        show_warnings: bool = True,
    ):
        """Initialize the parse error dialog.

        Args:
            parent: Parent widget.
            parse_results: Dict mapping file names to their ParseResult objects.
            show_warnings: Whether to show warnings (or only errors).
        """
        super().__init__(parent)
        self.parse_results = parse_results
        self.show_warnings = show_warnings
        self.files_to_skip: List[str] = []
        self._result_action = "cancel"

        self.setWindowTitle(self.tr(DialogTitles.PARSE_ISSUES_DETECTED))
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        self.setup_ui()
        self.populate_tree()

    def setup_ui(self):
        """Set up the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header with summary
        self._create_header(layout)

        # Tree widget showing files and their issues
        self._create_tree_widget(layout)

        # Options section
        self._create_options_section(layout)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Buttons
        self._create_buttons(layout)

    def _create_header(self, layout: QVBoxLayout):
        """Create the header section with summary info."""
        header_layout = QVBoxLayout()

        # Count errors and warnings
        total_errors = sum(r.error_count for r in self.parse_results.values())
        total_warnings = sum(r.warning_count for r in self.parse_results.values())
        files_with_issues = sum(
            1
            for r in self.parse_results.values()
            if r.error_count > 0 or (self.show_warnings and r.warning_count > 0)
        )

        # Main message
        message = QLabel()
        message.setWordWrap(True)

        if total_errors > 0:
            text = self.tr(
                "Found {errors} error(s) and {warnings} warning(s) in {files} file(s).\n"
                "Some sprites may not extract correctly."
            ).format(
                errors=total_errors, warnings=total_warnings, files=files_with_issues
            )
            message.setStyleSheet("color: #ef5350; font-weight: bold;")
        elif total_warnings > 0:
            text = self.tr(
                "Found {warnings} warning(s) in {files} file(s).\n"
                "Extraction can proceed but results may be affected."
            ).format(warnings=total_warnings, files=files_with_issues)
            message.setStyleSheet("color: #ffa726; font-weight: bold;")
        else:
            text = self.tr("All files parsed successfully.")
            message.setStyleSheet("color: #66bb6a; font-weight: bold;")

        message.setText(text)
        header_layout.addWidget(message)

        layout.addLayout(header_layout)

    def _create_tree_widget(self, layout: QVBoxLayout):
        """Create the tree widget showing files and issues."""
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(
            [
                self.tr("File / Issue"),
                self.tr("Type"),
                self.tr("Skip"),
            ]
        )
        self.tree.setColumnWidth(0, 350)
        self.tree.setColumnWidth(1, 80)
        self.tree.setColumnWidth(2, 50)
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)

        layout.addWidget(self.tree)

    def _create_options_section(self, layout: QVBoxLayout):
        """Create options section for bulk actions."""
        options_layout = QHBoxLayout()

        self.skip_all_errors_checkbox = QCheckBox(
            self.tr(CheckBoxLabels.SKIP_ALL_ERRORS)
        )
        self.skip_all_errors_checkbox.stateChanged.connect(self._on_skip_all_changed)
        options_layout.addWidget(self.skip_all_errors_checkbox)

        options_layout.addStretch()

        layout.addLayout(options_layout)

    def _create_buttons(self, layout: QVBoxLayout):
        """Create the button row."""
        button_layout = QHBoxLayout()

        # Continue button - process all files including those with errors
        self.continue_btn = QPushButton(self.tr(MenuActions.CONTINUE_ANYWAY))
        self.continue_btn.setToolTip(
            self.tr("Process all files, including those with errors")
        )
        self.continue_btn.clicked.connect(self._on_continue)

        # Skip selected button - skip files marked with checkbox
        self.skip_btn = QPushButton(self.tr(MenuActions.SKIP_SELECTED))
        self.skip_btn.setToolTip(
            self.tr("Skip files that are checked in the Skip column")
        )
        self.skip_btn.clicked.connect(self._on_skip_selected)

        # Cancel button
        self.cancel_btn = QPushButton(self.tr(ButtonLabels.CANCEL))
        self.cancel_btn.clicked.connect(self._on_cancel)

        button_layout.addStretch()
        button_layout.addWidget(self.continue_btn)
        button_layout.addWidget(self.skip_btn)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def populate_tree(self):
        """Populate the tree with parse results."""
        self.tree.clear()
        self._file_checkboxes: Dict[str, QCheckBox] = {}

        for filename, result in self.parse_results.items():
            if result.error_count == 0 and (
                not self.show_warnings or result.warning_count == 0
            ):
                continue

            # Create file item
            file_item = QTreeWidgetItem([filename, "", ""])
            file_item.setData(0, Qt.ItemDataRole.UserRole, filename)

            # Set icon based on severity
            if result.error_count > 0:
                file_item.setText(0, f"{self.ICON_ERROR} {filename}")
                file_item.setForeground(0, Qt.GlobalColor.red)
            elif result.warning_count > 0:
                file_item.setText(0, f"{self.ICON_WARNING} {filename}")
                file_item.setForeground(0, Qt.GlobalColor.darkYellow)

            # Add skip checkbox for files with errors
            if result.error_count > 0:
                skip_checkbox = QCheckBox()
                skip_checkbox.setToolTip(self.tr("Skip this file during extraction"))
                skip_checkbox.stateChanged.connect(
                    lambda state, fn=filename: self._on_file_skip_changed(fn, state)
                )
                self._file_checkboxes[filename] = skip_checkbox

            self.tree.addTopLevelItem(file_item)

            # Add checkbox widget to tree
            if result.error_count > 0 and filename in self._file_checkboxes:
                self.tree.setItemWidget(file_item, 2, self._file_checkboxes[filename])

            # Add error items
            for error in result.errors:
                error_text = self._format_error_message(error)
                error_item = QTreeWidgetItem([error_text, self.tr("Error"), ""])
                error_item.setForeground(0, Qt.GlobalColor.red)
                error_item.setForeground(1, Qt.GlobalColor.red)
                file_item.addChild(error_item)

            # Add warning items
            if self.show_warnings:
                for warning in result.warnings:
                    warning_text = self._format_warning_message(warning)
                    warning_item = QTreeWidgetItem(
                        [warning_text, self.tr("Warning"), ""]
                    )
                    warning_item.setForeground(0, Qt.GlobalColor.darkYellow)
                    warning_item.setForeground(1, Qt.GlobalColor.darkYellow)
                    file_item.addChild(warning_item)

            # Expand file items with errors
            if result.error_count > 0:
                file_item.setExpanded(True)

    def _format_error_message(self, error) -> str:
        """Format an error for display.

        Args:
            error: SpriteError object.

        Returns:
            Formatted error message.
        """
        msg = error.message
        if error.sprite_name:
            msg = f"[{error.sprite_name}] {msg}"
        return msg

    def _format_warning_message(self, warning) -> str:
        """Format a warning for display.

        Args:
            warning: ParserWarning object.

        Returns:
            Formatted warning message.
        """
        msg = warning.message
        if warning.sprite_name:
            msg = f"[{warning.sprite_name}] {msg}"
        return msg

    def _on_skip_all_changed(self, state: int):
        """Handle 'skip all errors' checkbox change."""
        checked = state == Qt.CheckState.Checked.value
        for filename, checkbox in self._file_checkboxes.items():
            checkbox.setChecked(checked)

    def _on_file_skip_changed(self, filename: str, state: int):
        """Handle individual file skip checkbox change."""
        if state == Qt.CheckState.Checked.value:
            if filename not in self.files_to_skip:
                self.files_to_skip.append(filename)
        else:
            if filename in self.files_to_skip:
                self.files_to_skip.remove(filename)

    def _on_continue(self):
        """Handle continue button click."""
        self._result_action = "continue"
        self.files_to_skip = []
        self.accept()

    def _on_skip_selected(self):
        """Handle skip selected button click."""
        self._result_action = "skip"
        self.accept()

    def _on_cancel(self):
        """Handle cancel button click."""
        self._result_action = "cancel"
        self.reject()

    def exec_and_get_result(self) -> Tuple[str, List[str]]:
        """Execute the dialog and return the result.

        Returns:
            Tuple of (action, files_to_skip) where action is one of:
            - "continue": Process all files
            - "skip": Skip files in files_to_skip list
            - "cancel": User cancelled the operation
        """
        self.exec()
        return self._result_action, self.files_to_skip

    @classmethod
    def show_if_needed(
        cls,
        parent,
        parse_results: Dict[str, ParseResult],
        show_warnings: bool = True,
    ) -> Tuple[str, List[str]]:
        """Show the dialog only if there are errors or warnings.

        Convenience method that checks if a dialog is needed before showing.

        Args:
            parent: Parent widget.
            parse_results: Dict mapping file names to their ParseResult objects.
            show_warnings: Whether to show warnings.

        Returns:
            Tuple of (action, files_to_skip). If no issues found, returns
            ("continue", []).
        """
        # Check if there are any issues to show
        has_errors = any(r.error_count > 0 for r in parse_results.values())
        has_warnings = show_warnings and any(
            r.warning_count > 0 for r in parse_results.values()
        )

        if not has_errors and not has_warnings:
            return "continue", []

        dialog = cls(parent, parse_results, show_warnings)
        return dialog.exec_and_get_result()


__all__ = ["ParseErrorDialog"]
