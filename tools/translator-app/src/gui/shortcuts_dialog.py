"""Dialog for customizing keyboard shortcuts.

Allows users to configure keyboard shortcuts for editor actions such as
Copy Source, Auto-Translate, Search, and list navigation.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# Default keyboard shortcuts
DEFAULT_SHORTCUTS: Dict[str, str] = {
    "copy_source": "Ctrl+Shift+C",
    "auto_translate": "Ctrl+T",
    "search": "Ctrl+F",
    "next_item": "Ctrl+Down",
    "prev_item": "Ctrl+Up",
}

# Human-readable labels for each shortcut
SHORTCUT_LABELS: Dict[str, str] = {
    "copy_source": "Copy Source to Translation",
    "auto_translate": "Auto-Translate Current",
    "search": "Search Translations",
    "next_item": "Next Translation",
    "prev_item": "Previous Translation",
}


class ShortcutsDialog(QDialog):
    """Dialog for viewing and editing keyboard shortcuts.

    Provides a form with editable key sequence fields for each configurable
    action. Changes are returned via get_shortcuts() after acceptance.

    Attributes:
        shortcut_edits: Mapping of shortcut keys to their QKeySequenceEdit widgets.
        current_shortcuts: The shortcuts currently configured.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        current_shortcuts: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize the shortcuts dialog.

        Args:
            parent: Parent widget for the dialog.
            current_shortcuts: Currently configured shortcuts, or None for defaults.
        """
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.setMinimumWidth(400)

        self.current_shortcuts = current_shortcuts or DEFAULT_SHORTCUTS.copy()
        self.shortcut_edits: Dict[str, QKeySequenceEdit] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog layout with shortcut editors."""
        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Click a field and press a key combination to set the shortcut.\n"
            "Leave empty to disable the shortcut."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666666; margin-bottom: 10px;")
        layout.addWidget(info_label)

        editor_group = QGroupBox("Editor Shortcuts")
        form_layout = QFormLayout(editor_group)

        for key in DEFAULT_SHORTCUTS:
            label = SHORTCUT_LABELS.get(key, key)
            edit = QKeySequenceEdit()
            current_value = self.current_shortcuts.get(
                key, DEFAULT_SHORTCUTS.get(key, "")
            )
            if current_value:
                edit.setKeySequence(QKeySequence(current_value))
            self.shortcut_edits[key] = edit
            form_layout.addRow(f"{label}:", edit)

        layout.addWidget(editor_group)

        # Reset to defaults button
        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_to_defaults)
        layout.addWidget(reset_btn)

        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._validate_and_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _reset_to_defaults(self) -> None:
        """Reset all shortcut fields to their default key sequences.

        Iterates through every shortcut editor and restores the value from
        DEFAULT_SHORTCUTS, discarding any user customizations.
        """
        for key, edit in self.shortcut_edits.items():
            default_value = DEFAULT_SHORTCUTS.get(key, "")
            edit.setKeySequence(QKeySequence(default_value))

    def _validate_and_accept(self) -> None:
        """Validate shortcuts for conflicts, then accept if valid.

        Checks that no two actions share the same key sequence. If a conflict
        is detected, displays a warning and keeps the dialog open.
        """
        shortcuts = self.get_shortcuts()
        used_sequences: Dict[str, str] = {}

        for key, sequence in shortcuts.items():
            if not sequence:
                continue
            if sequence in used_sequences:
                conflict_label = SHORTCUT_LABELS.get(
                    used_sequences[sequence], used_sequences[sequence]
                )
                current_label = SHORTCUT_LABELS.get(key, key)
                QMessageBox.warning(
                    self,
                    "Shortcut Conflict",
                    f"The shortcut '{sequence}' is used by both:\n"
                    f"• {conflict_label}\n"
                    f"• {current_label}\n\n"
                    "Please use unique shortcuts for each action.",
                )
                return
            used_sequences[sequence] = key

        self.accept()

    def get_shortcuts(self) -> Dict[str, str]:
        """Return the configured shortcuts as a dictionary.

        Returns:
            A dictionary mapping shortcut keys to their key sequence strings.
        """
        result: Dict[str, str] = {}
        for key, edit in self.shortcut_edits.items():
            sequence = edit.keySequence()
            result[key] = sequence.toString() if not sequence.isEmpty() else ""
        return result


__all__ = ["ShortcutsDialog", "DEFAULT_SHORTCUTS", "SHORTCUT_LABELS"]
