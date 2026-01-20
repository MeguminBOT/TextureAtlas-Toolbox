#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""First-start dialog for new users.

Displays on first application launch to welcome users, inform them about
detected language settings, and configure initial preferences.
"""

import os
import subprocess
import sys

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QCheckBox,
    QGroupBox,
    QFrame,
    QComboBox,
    QLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from utils.translation_manager import get_translation_manager, tr as translate
from utils.version import APP_NAME, APP_VERSION

# Import Qt resources to make icons available
import resources.icons_rc  # type: ignore  # noqa: F401


class FirstStartDialog(QDialog):
    """Dialog shown on first application launch.

    Welcomes the user, displays detected language information with quality
    warnings if applicable, and allows configuration of update preferences.

    Attributes:
        translation_manager: TranslationManager instance for language operations.
        initial_language: The language code initially detected/selected.
        selected_language: Currently selected language code.
        language_changed: Whether the user changed the language from initial.
    """

    tr = translate
    REPO_ISSUES_URL = (
        "https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames/issues"
    )
    TRANSLATION_GUIDE_URL = "https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames/blob/main/docs/translation-guide.md"

    def _github_issues_link(self) -> str:
        """Return a localized clickable link to the GitHub issues page."""
        link_text = self.tr("GitHub issues page")
        return f'<a href="{self.REPO_ISSUES_URL}">{link_text}</a>'

    def _translation_guide_link(self) -> str:
        """Return a localized clickable link to the translation guide."""
        link_text = self.tr("translation guide")
        return f'<a href="{self.TRANSLATION_GUIDE_URL}">{link_text}</a>'

    def __init__(
        self,
        parent=None,
        translation_manager=None,
        detected_language: str = "en_us",
    ):
        """Initialize the first-start dialog.

        Args:
            parent: Parent widget for the dialog.
            translation_manager: TranslationManager instance.
            detected_language: Language code detected from system locale.
        """
        super().__init__(parent)
        self.translation_manager = translation_manager or get_translation_manager()
        self.initial_language = detected_language
        self.selected_language = detected_language
        self.language_changed = False

        # Store checkbox states to preserve across retranslation
        self._check_updates_state = True
        self._auto_download_state = False

        self.setup_ui()

    def setup_ui(self):
        """Build the dialog layout with welcome message, warnings, and options."""
        self.setWindowTitle(self.tr("Welcome to TextureAtlas Toolbox"))
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        # Fix the dialog to its size hint to avoid geometry negotiation warnings on Windows.
        layout.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        # Welcome header
        self.welcome_label = QLabel(
            self.tr("Welcome to {app_name} {app_version}").format(
                app_name=APP_NAME, app_version=APP_VERSION
            )
        )
        welcome_font = QFont()
        welcome_font.setPointSize(18)
        welcome_font.setBold(True)
        self.welcome_label.setFont(welcome_font)
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.welcome_label)

        # Language selection section
        self.lang_group = QGroupBox(self.tr("Language"))
        lang_layout = QVBoxLayout(self.lang_group)

        # Language selector row
        lang_select_row = QHBoxLayout()
        lang_select_row.setSpacing(8)

        self.lang_label = QLabel(self.tr("Select language:"))
        lang_select_row.addWidget(self.lang_label)

        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(200)
        self._populate_language_combo()
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        lang_select_row.addWidget(self.language_combo)
        lang_select_row.addStretch()

        lang_layout.addLayout(lang_select_row)

        # Quality indicator legend
        self.quality_legend = QLabel()
        self.quality_legend.setStyleSheet("color: #888; font-size: 10px;")
        self._update_quality_legend()
        lang_layout.addWidget(self.quality_legend)

        # Warning frame container (for machine translation warning)
        self.warning_container = QVBoxLayout()
        lang_layout.addLayout(self.warning_container)
        self._update_quality_warning()

        # Restart notice (hidden by default)
        self.restart_notice = QLabel(
            self.tr(
                "Note: Some text may not update until the application is restarted."
            )
        )
        self.restart_notice.setWordWrap(True)
        self.restart_notice.setStyleSheet("color: #ff9800; font-style: italic;")
        self.restart_notice.setVisible(False)
        lang_layout.addWidget(self.restart_notice)

        layout.addWidget(self.lang_group)

        # New feature notice
        self.notice_group = QGroupBox(self.tr("New Feature Notice"))
        notice_layout = QVBoxLayout(self.notice_group)
        self.notice_label = QLabel(
            self.tr(
                "Language selection is a new feature. You may encounter UI issues "
                "such as text not fitting properly in some areas. "
                "These will be improved over time."
                "\n"
            )
        )
        self.notice_label.setWordWrap(True)
        notice_layout.addWidget(self.notice_label)
        self.v2_notice_label = QLabel(
            self.tr(
                "Version 2 introduces many new features and changes from version 1.\n"
                "There may be unfound bugs. Please report issues on the {issues_link}."
            ).format(issues_link=self._github_issues_link())
        )
        self.v2_notice_label.setTextFormat(Qt.TextFormat.RichText)
        self.v2_notice_label.setOpenExternalLinks(True)
        self.v2_notice_label.setWordWrap(True)
        notice_layout.addWidget(self.v2_notice_label)
        layout.addWidget(self.notice_group)

        # Update preferences section
        self.update_group = QGroupBox(self.tr("Update Preferences"))
        update_layout = QVBoxLayout(self.update_group)

        self.update_info = QLabel(
            self.tr(
                "Would you like the application to check for updates automatically "
                "when it starts?"
            )
        )
        self.update_info.setWordWrap(True)
        update_layout.addWidget(self.update_info)

        self.check_updates_checkbox = QCheckBox(
            self.tr("Check for updates on startup (recommended)")
        )
        self.check_updates_checkbox.setChecked(self._check_updates_state)
        update_layout.addWidget(self.check_updates_checkbox)

        self.auto_download_checkbox = QCheckBox(
            self.tr("Automatically download updates when available")
        )
        self.auto_download_checkbox.setChecked(self._auto_download_state)
        update_layout.addWidget(self.auto_download_checkbox)

        layout.addWidget(self.update_group)

        # Spacer
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.continue_button = QPushButton(self.tr("Continue"))
        self.continue_button.setMinimumWidth(120)
        self.continue_button.setDefault(True)
        self.continue_button.clicked.connect(self.accept)
        button_layout.addWidget(self.continue_button)

        layout.addLayout(button_layout)

        # Let the layout constraint define the final fixed size.
        self.adjustSize()

    def _populate_language_combo(self):
        """Populate the language combo box with available languages."""
        self.language_combo.blockSignals(True)
        self.language_combo.clear()

        available = self.translation_manager.get_available_languages()

        for lang_code in sorted(available):
            display_name = self.translation_manager.get_display_name(
                lang_code, show_english=True, show_completeness=True
            )
            quality = self.translation_manager.get_quality_level(lang_code)
            icon = self._get_quality_icon(quality)

            if icon:
                self.language_combo.addItem(icon, display_name, lang_code)
            else:
                self.language_combo.addItem(display_name, lang_code)

        # Sort by display name
        self.language_combo.model().sort(0)

        # Find and set the current language after sorting
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == self.selected_language:
                self.language_combo.setCurrentIndex(i)
                break

        self.language_combo.blockSignals(False)

    def _on_language_changed(self, index: int):
        """Handle language selection change."""
        if index < 0:
            return

        new_lang = self.language_combo.itemData(index)
        if new_lang == self.selected_language:
            return

        # Save checkbox states before rebuild
        self._check_updates_state = self.check_updates_checkbox.isChecked()
        self._auto_download_state = self.auto_download_checkbox.isChecked()

        self.selected_language = new_lang
        self.language_changed = new_lang != self.initial_language

        # Load the new translation
        self.translation_manager.load_translation(new_lang)

        # Retranslate the dialog
        self._retranslate_ui()

        # Update quality legend and warning for new language
        self._update_quality_legend()
        self._update_quality_warning()

        # Show restart notice if language changed
        self.restart_notice.setVisible(self.language_changed)

    def _retranslate_ui(self):
        """Update all translatable text in the dialog."""
        self.setWindowTitle(self.tr("Welcome to TextureAtlas Toolbox"))
        self.welcome_label.setText(
            self.tr("Welcome to {app_name} {app_version}").format(
                app_name=APP_NAME, app_version=APP_VERSION
            )
        )
        self.lang_group.setTitle(self.tr("Language"))
        self.lang_label.setText(self.tr("Select language:"))
        self.restart_notice.setText(
            self.tr(
                "Note: Some text may not update until the application is restarted."
            )
        )
        self.notice_group.setTitle(self.tr("New Feature Notice"))
        self.notice_label.setText(
            self.tr(
                "Language selection is a new feature. You may encounter UI issues "
                "such as text not fitting properly in some areas. "
                "These will be improved over time."
                "\n"
            )
        )
        self.v2_notice_label.setText(
            self.tr(
                "Version 2 introduces many new features and changes from version 1.\n"
                "There may be unfound bugs. Please report issues on the {issues_link}."
            ).format(issues_link=self._github_issues_link())
        )
        self.update_group.setTitle(self.tr("Update Preferences"))
        self.update_info.setText(
            self.tr(
                "Would you like the application to check for updates automatically "
                "when it starts?"
            )
        )
        self.check_updates_checkbox.setText(
            self.tr("Check for updates on startup (recommended)")
        )
        self.auto_download_checkbox.setText(
            self.tr("Automatically download updates when available")
        )
        self.continue_button.setText(self.tr("Continue"))
        self._update_quality_legend()

    def _update_quality_legend(self):
        """Update the quality legend text showing current language quality."""
        quality = self.translation_manager.get_quality_level(self.selected_language)
        quality_names = {
            "native": self.tr("Native"),
            "reviewed": self.tr("Reviewed"),
            "unreviewed": self.tr("Unreviewed"),
            "machine": self.tr("Machine Translated"),
            "unknown": self.tr("Unknown"),
        }
        quality_display = quality_names.get(quality, quality)
        self.quality_legend.setText(
            self.tr("Translation quality: {quality}").format(quality=quality_display)
        )

    def _update_quality_warning(self):
        """Update the quality warning frame based on current language."""
        # Clear existing warning
        while self.warning_container.count():
            item = self.warning_container.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Check if we need a machine translation warning
        quality = self.translation_manager.get_quality_level(self.selected_language)
        if quality == "machine":
            warning_frame = self._create_warning_frame(
                self.tr("Machine Translation Warning"),
                self.tr(
                    "This language was machine translated (automated). "
                    "Some text may be inaccurate or awkward. "
                    "You can help improve it by contributing translations. "
                    "See the {guide_link} for how to contribute."
                ).format(guide_link=self._translation_guide_link()),
            )
            self.warning_container.addWidget(warning_frame)

    def _get_quality_icon(self, quality: str) -> QIcon | None:
        """Get the appropriate quality icon for the given quality level.

        Args:
            quality: Translation quality level.

        Returns:
            QIcon for the quality level, or None if not available.
        """
        icon_map = {
            "native": ":/icons/quality/icons/material/quality_native.svg",
            "reviewed": ":/icons/quality/icons/material/quality_reviewed.svg",
            "unreviewed": ":/icons/quality/icons/material/quality_unreviewed.svg",
            "machine": ":/icons/quality/icons/material/quality_machine.svg",
            "unknown": ":/icons/quality/icons/material/quality_unknown.svg",
        }
        icon_path = icon_map.get(quality)
        if icon_path:
            return QIcon(icon_path)
        return None

    def _create_warning_frame(self, title: str, message: str) -> QFrame:
        """Create a styled frame for warnings.

        Args:
            title: Title text for the warning.
            message: Body text explaining the warning.

        Returns:
            Configured QFrame widget.
        """
        frame = QFrame()
        frame.setStyleSheet(
            """
            QFrame {
                background-color: rgba(244, 67, 54, 0.15);
                border: 1px solid rgba(244, 67, 54, 0.5);
                border-radius: 6px;
                padding: 8px;
            }
            """
        )

        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(12, 8, 12, 8)

        # Use the machine translation icon
        icon_label = QLabel()
        icon = QIcon(":/icons/quality/icons/material/quality_machine.svg")
        icon_label.setPixmap(icon.pixmap(24, 24))
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        frame_layout.addWidget(icon_label)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_label = QLabel(f"<b>{title}</b>")
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setStyleSheet("background: transparent; border: none;")
        text_layout.addWidget(title_label)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setTextFormat(Qt.TextFormat.RichText)
        message_label.setOpenExternalLinks(True)
        message_label.setStyleSheet("background: transparent; border: none;")
        text_layout.addWidget(message_label)

        frame_layout.addLayout(text_layout, 1)

        return frame

    def get_update_preferences(self) -> dict:
        """Return the user's selected update preferences.

        Returns:
            Dictionary with 'check_updates_on_startup' and
            'auto_download_updates' boolean keys.
        """
        return {
            "check_updates_on_startup": self.check_updates_checkbox.isChecked(),
            "auto_download_updates": self.auto_download_checkbox.isChecked(),
        }

    def get_selected_language(self) -> str:
        """Return the user's selected language code."""
        return self.selected_language

    def was_language_changed(self) -> bool:
        """Return whether the user changed the language from initial detection."""
        return self.language_changed


def show_first_start_dialog(
    parent, translation_manager, app_config
) -> tuple[bool, bool]:
    """Show the first-start dialog if this is the first launch.

    Args:
        parent: Parent widget for the dialog.
        translation_manager: TranslationManager instance for language info.
        app_config: AppConfig instance to check/set first_run flag.

    Returns:
        A tuple of (dialog_shown, restart_needed). dialog_shown is True if the
        dialog was shown and accepted. restart_needed is True if the user
        changed the language and the app should restart.
    """
    # Check if first run
    if app_config.get("first_run_completed", False):
        return False, False

    # Get detected language info
    system_locale = translation_manager.get_system_locale()
    available = translation_manager.get_available_languages()

    if system_locale in available:
        detected_lang = system_locale
    else:
        detected_lang = "en"

    dialog = FirstStartDialog(
        parent=parent,
        translation_manager=translation_manager,
        detected_language=detected_lang,
    )

    result = dialog.exec()

    if result == QDialog.DialogCode.Accepted:
        # Save language preference
        selected_language = dialog.get_selected_language()
        app_config.settings["language"] = selected_language

        # Save update preferences
        update_prefs = dialog.get_update_preferences()
        app_config.settings.setdefault("update_settings", {})
        app_config.settings["update_settings"]["check_updates_on_startup"] = (
            update_prefs["check_updates_on_startup"]
        )
        app_config.settings["update_settings"]["auto_download_updates"] = update_prefs[
            "auto_download_updates"
        ]

        # Mark first run as completed
        app_config.settings["first_run_completed"] = True
        app_config.save()

        # Check if language was changed and restart is needed
        restart_needed = dialog.was_language_changed()
        return True, restart_needed

    return False, False


def restart_application():
    """Restart the application by launching a new process and exiting."""
    # Find Main.py relative to this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    src_dir = os.path.dirname(current_dir)
    main_py = os.path.join(src_dir, "Main.py")

    if os.path.exists(main_py):
        try:
            subprocess.Popen(
                [sys.executable, main_py],
                cwd=src_dir,
            )
        except Exception:
            pass
    sys.exit(0)
