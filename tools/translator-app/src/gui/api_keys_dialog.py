#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Dialog for configuring translation API keys.

Allows users to enter and save API keys for machine translation providers
(DeepL, Google Cloud, LibreTranslate) through the GUI instead of manually
setting environment variables.
"""

from __future__ import annotations

from typing import Dict, Optional

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _create_password_field_with_toggle(
    placeholder: str, initial_value: str = ""
) -> tuple[QWidget, QLineEdit]:
    """Create a password input field with a show/hide toggle button.

    Args:
        placeholder: Placeholder text for the input field.
        initial_value: Initial text value for the field.

    Returns:
        A tuple of (container widget, line edit) for use in form layouts.
    """
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)

    line_edit = QLineEdit()
    line_edit.setPlaceholderText(placeholder)
    line_edit.setEchoMode(QLineEdit.EchoMode.Password)
    line_edit.setText(initial_value)
    layout.addWidget(line_edit)

    toggle_btn = QPushButton("Show")
    toggle_btn.setFixedWidth(50)
    toggle_btn.setCheckable(True)

    def on_toggle(checked: bool) -> None:
        if checked:
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            toggle_btn.setText("Hide")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            toggle_btn.setText("Show")

    toggle_btn.toggled.connect(on_toggle)
    layout.addWidget(toggle_btn)

    return container, line_edit


class ApiKeysDialog(QDialog):
    """Dialog for entering and saving translation API keys.

    Provides input fields for each supported translation provider's API key
    and endpoint configuration. Values are stored in preferences and applied
    to environment variables for the current session only.

    Attributes:
        api_keys: Dictionary of current API key values.
        deepl_key_input: Input field for DeepL API key.
        deepl_endpoint_input: Input field for DeepL API endpoint (Pro).
        google_key_input: Input field for Google Cloud Translation API key.
        libre_endpoint_input: Input field for LibreTranslate endpoint URL.
        libre_key_input: Input field for LibreTranslate API key.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        api_keys: Optional[Dict[str, str]] = None,
    ) -> None:
        """Initialize the API keys configuration dialog.

        Args:
            parent: Parent widget for the dialog.
            api_keys: Current API key values to populate the fields.
        """
        super().__init__(parent)
        self.api_keys = api_keys or {}
        self.setWindowTitle("API Keys Configuration")
        self.setMinimumWidth(500)
        self._init_ui()

    def _init_ui(self) -> None:
        """Build the dialog layout with input fields for each provider."""
        layout = QVBoxLayout(self)

        # Info label
        info_label = QLabel(
            "Configure API keys for machine translation providers.\n"
            "Keys are stored locally and set as environment variables only "
            "while this application is running."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # DeepL group
        deepl_group = QGroupBox("DeepL (Free and Paid subscription)")
        deepl_layout = QFormLayout(deepl_group)

        deepl_key_container, self.deepl_key_input = _create_password_field_with_toggle(
            "Enter your DeepL API key",
            self.api_keys.get("deepl_api_key", ""),
        )
        deepl_layout.addRow("API Key:", deepl_key_container)

        self.deepl_endpoint_input = QLineEdit()
        self.deepl_endpoint_input.setPlaceholderText(
            "Leave empty for free API, set for Pro"
        )
        self.deepl_endpoint_input.setText(self.api_keys.get("deepl_api_endpoint", ""))
        deepl_layout.addRow("Endpoint (Pro):", self.deepl_endpoint_input)

        layout.addWidget(deepl_group)

        # Google Cloud group
        google_group = QGroupBox("Google Cloud Translation (Paid per usage)")
        google_layout = QFormLayout(google_group)

        google_key_container, self.google_key_input = (
            _create_password_field_with_toggle(
                "Enter your Google Cloud API key",
                self.api_keys.get("google_translate_api_key", ""),
            )
        )
        google_layout.addRow("API Key:", google_key_container)

        layout.addWidget(google_group)

        # LibreTranslate group
        libre_group = QGroupBox("LibreTranslate (Self-hosted / Free)")
        libre_layout = QFormLayout(libre_group)

        self.libre_endpoint_input = QLineEdit()
        self.libre_endpoint_input.setPlaceholderText(
            "Default: http://127.0.0.1:5000/translate"
        )
        self.libre_endpoint_input.setText(
            self.api_keys.get("libretranslate_endpoint", "")
        )
        libre_layout.addRow("Endpoint URL:", self.libre_endpoint_input)

        libre_key_container, self.libre_key_input = _create_password_field_with_toggle(
            "Only if your instance requires a key",
            self.api_keys.get("libretranslate_api_key", ""),
        )
        libre_layout.addRow("API Key:", libre_key_container)

        layout.addWidget(libre_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_api_keys(self) -> Dict[str, str]:
        """Return the API keys as entered in the dialog.

        Returns:
            Dictionary mapping API key names to their values.
        """
        return {
            "deepl_api_key": self.deepl_key_input.text().strip(),
            "deepl_api_endpoint": self.deepl_endpoint_input.text().strip(),
            "google_translate_api_key": self.google_key_input.text().strip(),
            "libretranslate_endpoint": self.libre_endpoint_input.text().strip(),
            "libretranslate_api_key": self.libre_key_input.text().strip(),
        }
