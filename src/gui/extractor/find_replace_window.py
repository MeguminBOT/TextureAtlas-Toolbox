#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog for creating find-and-replace rules applied to exported filenames.

Supports plain text and regular expression patterns for flexible renaming.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QScrollArea,
    QWidget,
    QGroupBox,
    QMenu,
)
from PySide6.QtCore import QCoreApplication, Qt

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels


class FindReplaceWindow(QDialog):
    """Dialog for managing filename find-and-replace rules.

    Allows adding, editing, and deleting replacement rules with optional
    regex support. Invokes a callback with the collected rules on accept.

    Attributes:
        on_store_callback: Function called with the list of rules on OK.
        replace_rules: List of rule dictionaries.
        rule_widgets: List of QGroupBox widgets representing each rule.
    """

    tr = translate

    UI_CONSTANTS_CONTEXT = "TextureAtlasToolboxApp"

    def trc(self, text: str) -> str:
        """Translate a string from ui_constants using its proper context."""
        return QCoreApplication.translate(self.UI_CONSTANTS_CONTEXT, text)

    def __init__(self, on_store_callback, replace_rules=None, parent=None):
        """Create the find-and-replace dialog.

        Args:
            on_store_callback: Function receiving the rules list on accept.
            replace_rules: Initial list of rule dictionaries.
            parent: Parent widget for the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Find and Replace"))
        self.setGeometry(200, 200, 500, 400)
        self.on_store_callback = on_store_callback
        self.replace_rules = replace_rules or []
        self.rule_widgets = []
        self.setup_ui()
        self.load_existing_rules()

    def setup_ui(self):
        """Build the dialog layout with rules list and controls."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(self.tr("Find and Replace Rules"))
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)

        instructions = QLabel(
            self.tr(
                "Create rules to find and replace text in exported filenames.\n"
                "Use $sprite or $anim placeholders to match actual names.\n"
                "Example: Find '$sprite' → Replace '' removes the sprite name from filename."
            )
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666666; margin-bottom: 10px;")
        layout.addWidget(instructions)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.rules_container = QWidget()
        self.rules_layout = QVBoxLayout(self.rules_container)
        self.rules_layout.setSpacing(5)
        self.rules_layout.addStretch()

        scroll_area.setWidget(self.rules_container)
        layout.addWidget(scroll_area)

        buttons_row = QHBoxLayout()

        add_btn = QPushButton(self.tr("Add Rule"))
        add_btn.clicked.connect(self.add_rule)
        buttons_row.addWidget(add_btn)

        preset_btn = QPushButton(self.tr("Add Preset Rule"))
        preset_menu = QMenu(self)
        preset_menu.addAction(
            self.tr("Remove sprite name"), self._add_preset_remove_sprite
        )
        preset_menu.addAction(
            self.tr("Shorten frame numbers"), self._add_preset_shorten_digits
        )
        preset_btn.setMenu(preset_menu)
        buttons_row.addWidget(preset_btn)

        buttons_row.addStretch()
        layout.addLayout(buttons_row)

        button_layout = QHBoxLayout()

        ok_btn = QPushButton(self.trc(ButtonLabels.OK))
        ok_btn.clicked.connect(self.accept_changes)
        ok_btn.setDefault(True)

        cancel_btn = QPushButton(self.trc(ButtonLabels.CANCEL))
        cancel_btn.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(ok_btn)
        button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)

    def load_existing_rules(self):
        """Populate the UI with pre-existing rules."""
        for rule in self.replace_rules:
            self.add_rule(rule)

    def add_rule(self, rule_data=None):
        """Create a new rule entry widget.

        Args:
            rule_data: Optional dict with 'find', 'replace', and 'regex' keys.
        """
        if rule_data is None:
            rule_data = {"find": "", "replace": "", "regex": False}
        elif not isinstance(rule_data, dict):
            rule_data = {"find": "", "replace": "", "regex": False}

        rule_frame = QGroupBox()
        rule_frame.setStyleSheet(
            """
            QGroupBox {
                border: 1px solid #cccccc;
                border-radius: 5px;
                margin-top: 5px;
                padding-top: 10px;
            }
        """
        )

        rule_layout = QVBoxLayout(rule_frame)
        rule_layout.setSpacing(8)

        find_layout = QHBoxLayout()
        find_label = QLabel(self.tr("Find:"))
        find_label.setMinimumWidth(60)
        find_entry = QLineEdit()
        find_entry.setText(rule_data.get("find", ""))
        find_entry.setPlaceholderText(self.tr("Text to find..."))
        find_layout.addWidget(find_label)
        find_layout.addWidget(find_entry)
        rule_layout.addLayout(find_layout)

        replace_layout = QHBoxLayout()
        replace_label = QLabel(self.tr("Replace:"))
        replace_label.setMinimumWidth(60)
        replace_entry = QLineEdit()
        replace_entry.setText(rule_data.get("replace", ""))
        replace_entry.setPlaceholderText(self.tr("Replacement text..."))
        replace_layout.addWidget(replace_label)
        replace_layout.addWidget(replace_entry)
        rule_layout.addLayout(replace_layout)

        options_layout = QHBoxLayout()
        regex_checkbox = QCheckBox(self.tr("Regular Expression"))
        regex_checkbox.setChecked(rule_data.get("regex", False))

        delete_btn = QPushButton(self.trc(ButtonLabels.DELETE))
        delete_btn.clicked.connect(lambda: self.delete_rule(rule_frame))
        delete_btn.setMaximumWidth(80)
        delete_btn.setStyleSheet("QPushButton { color: #cc0000; }")

        options_layout.addWidget(regex_checkbox)
        options_layout.addStretch()
        options_layout.addWidget(delete_btn)
        rule_layout.addLayout(options_layout)

        rule_frame.find_entry = find_entry
        rule_frame.replace_entry = replace_entry
        rule_frame.regex_checkbox = regex_checkbox

        self.rules_layout.insertWidget(self.rules_layout.count() - 1, rule_frame)
        self.rule_widgets.append(rule_frame)

    def delete_rule(self, rule_frame):
        """Remove a rule widget from the dialog.

        Args:
            rule_frame: QGroupBox widget representing the rule to delete.
        """
        if rule_frame in self.rule_widgets:
            self.rule_widgets.remove(rule_frame)
        self.rules_layout.removeWidget(rule_frame)
        rule_frame.deleteLater()

    def accept_changes(self):
        """Gather all rules and invoke the callback before closing."""
        rules = []
        for rule_frame in self.rule_widgets:
            rule = {
                "find": rule_frame.find_entry.text(),
                "replace": rule_frame.replace_entry.text(),
                "regex": rule_frame.regex_checkbox.isChecked(),
            }
            rules.append(rule)

        self.on_store_callback(rules)
        self.accept()

    @staticmethod
    def show_find_replace_window(on_store_callback, replace_rules=None, parent=None):
        """Display the find-and-replace dialog modally.

        Args:
            on_store_callback: Function receiving the rules list on accept.
            replace_rules: Initial list of rule dictionaries.
            parent: Parent widget for the dialog.
        """
        window = FindReplaceWindow(on_store_callback, replace_rules, parent)
        window.exec()

    def _add_preset_remove_sprite(self):
        """Add a preset rule to exclude the sprite name from filenames."""
        self.add_rule({"find": "$sprite", "replace": "", "regex": False})

    def _add_preset_shorten_digits(self):
        """Add a preset rule to shorten long frame numbers.

        Converts padded numbers like 0001, 10001 to minimal digits (1, 1).
        Uses regex to strip leading zeros from digit sequences.
        """
        self.add_rule({"find": r"(?<!\d)0+(\d+)", "replace": r"\1", "regex": True})
