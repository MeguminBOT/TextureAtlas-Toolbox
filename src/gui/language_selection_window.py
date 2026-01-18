#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog for selecting the application display language."""

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QMessageBox,
)
from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels

# Optional: compiled Qt resources for icons (generated via pyside6-rcc).
try:
    import resources.icons_rc  # type: ignore  # noqa: F401
except ImportError:
    pass


class LanguageSelectionWindow(QDialog):
    """Modal dialog for choosing the application language.

    Displays available languages with native names, English names, and
    quality indicators (Native, Reviewed, Unreviewed, Machine, Unknown).

    Attributes:
        parent_window: Reference to the parent widget.
        current_language: Language code currently active.
        new_language: Language code selected by the user.
    """

    tr = translate

    def __init__(self, parent=None, current_language="en_us"):
        """Initialize the language selection dialog.

        Args:
            parent: Parent widget for the dialog.
            current_language: Language code currently in use.
        """
        super().__init__(parent)
        self.parent_window = parent
        self.current_language = current_language
        self.new_language = current_language

        # Markers are text fallbacks (no emoji) in case icons fail to load.
        self.QUALITY_MARKERS = {
            "native": "[✔]",
            "reviewed": "[~]",
            "unreviewed": "[ ]",
            "machine": "[BOT]",
            "unknown": "[?]",
        }

        # Resource prefix is /icons/quality, files live under icons/material in the qrc.
        self.QUALITY_ICON_PATHS = {
            "native": ":/icons/quality/icons/material/quality_native.svg",
            "reviewed": ":/icons/quality/icons/material/quality_reviewed.svg",
            "unreviewed": ":/icons/quality/icons/material/quality_unreviewed.svg",
            "machine": ":/icons/quality/icons/material/quality_machine.svg",
            "unknown": ":/icons/quality/icons/material/quality_unknown.svg",
        }
        self.QUALITY_ICONS = {
            key: QIcon(path) for key, path in self.QUALITY_ICON_PATHS.items()
        }

        self.setup_ui()
        self.setup_connections()

        self.setWindowTitle(self.tr("Language Settings"))
        self.setModal(True)
        self.setFixedSize(500, 300)

        if parent:
            self.move(
                parent.x() + (parent.width() - self.width()) // 2,
                parent.y() + (parent.height() - self.height()) // 2,
            )

    def _format_language_display_name(self, native_name, english_name):
        """Format a language name for display in the combo box.

        Args:
            native_name: Language name in its native script.
            english_name: Language name in English.

        Returns:
            Combined display string using forward slash separator.
        """
        if not english_name or english_name == native_name:
            return native_name

        if english_name.lower() in native_name.lower():
            return native_name

        return f"{native_name} / {english_name}"

    def get_auto_detected_language(self):
        """Detect the preferred language from the system locale.

        Returns:
            Language code matching the system locale, or 'en' if unavailable.
        """
        translation_manager = None
        if self.parent_window and hasattr(self.parent_window, "translation_manager"):
            translation_manager = self.parent_window.translation_manager
        else:
            try:
                from utils.translation_manager import get_translation_manager

                translation_manager = get_translation_manager()
            except ImportError:
                return "en"

        if not translation_manager:
            return "en"

        system_locale = translation_manager.get_system_locale()

        available_languages = translation_manager.get_available_languages()

        if system_locale in available_languages:
            return system_locale

        return "en"

    def setup_ui(self):
        """Build the language combo box, info label, and button row."""

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(self.tr("Select Application Language"))
        title_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title_label)

        lang_layout = QHBoxLayout()

        self.language_label = QLabel(self.tr("Language:"))
        lang_layout.addWidget(self.language_label)

        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(280)
        lang_layout.addWidget(self.language_combo)

        lang_layout.addStretch()
        layout.addLayout(lang_layout)

        self.populate_languages()

        self.info_label = QLabel(
            self.tr(
                "Note: The application may need to be restarted to fully apply the language change.\n"
                "Auto detects your system language and falls back to English if unavailable.\n"
                "Quality indicators: {native} Native, {reviewed} Reviewed, {unreviewed} Unreviewed, {machine} Machine, {unknown} Unknown"
            ).format(
                native=self.QUALITY_MARKERS["native"],
                reviewed=self.QUALITY_MARKERS["reviewed"],
                unreviewed=self.QUALITY_MARKERS["unreviewed"],
                machine=self.QUALITY_MARKERS["machine"],
                unknown=self.QUALITY_MARKERS["unknown"],
            )
        )
        self.info_label.setStyleSheet("color: #666; font-size: 10px;")
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_button = QPushButton(self.tr(ButtonLabels.CANCEL))
        self.cancel_button.setMinimumWidth(80)
        button_layout.addWidget(self.cancel_button)

        self.apply_button = QPushButton(self.tr(ButtonLabels.APPLY))
        self.apply_button.setMinimumWidth(80)
        self.apply_button.setDefault(True)
        button_layout.addWidget(self.apply_button)

        layout.addLayout(button_layout)

    def setup_connections(self):
        """Connect widget signals to their handler slots."""

        self.language_combo.currentTextChanged.connect(self.on_language_changed)
        self.cancel_button.clicked.connect(self.reject)
        self.apply_button.clicked.connect(self.apply_language_change)

    def populate_languages(self):
        """Fill the combo box with available language options."""

        translation_manager = None
        if self.parent_window and hasattr(self.parent_window, "translation_manager"):
            translation_manager = self.parent_window.translation_manager
        else:
            try:
                from utils.translation_manager import get_translation_manager

                translation_manager = get_translation_manager()
            except ImportError:
                translation_manager = None

        if translation_manager:
            available_languages = translation_manager.get_available_languages()
        else:
            # Minimal fallback to avoid duplication when translation manager is unavailable.
            available_languages = {
                "en": {
                    "name": "English",
                    "english_name": "English",
                    "quality": "native",
                }
            }

        self.language_combo.clear()

        auto_detected_lang = self.get_auto_detected_language()
        auto_detected_display = "English"

        if translation_manager:
            auto_detected_display = translation_manager.get_display_name(
                auto_detected_lang
            )
        elif auto_detected_lang in available_languages:
            lang_info = available_languages[auto_detected_lang]
            if isinstance(lang_info, dict):
                auto_detected_display = lang_info.get("name", auto_detected_lang)

        auto_display_text = self.tr("Auto (System Default): {language}").format(
            language=auto_detected_display
        )
        self.language_combo.addItem(auto_display_text, "auto")

        self.language_combo.insertSeparator(1)

        for lang_code, lang_info in available_languages.items():
            if isinstance(lang_info, dict):
                if translation_manager:
                    display_name = translation_manager.get_display_name(
                        lang_code, show_english=True, show_completeness=True
                    )
                    quality = translation_manager.get_quality_level(lang_code)
                else:
                    native_name = lang_info.get("name", lang_code)
                    english_name = lang_info.get("english_name", "")
                    quality = lang_info.get("quality", "unknown")

                    if english_name and lang_code != "en":
                        display_name = self._format_language_display_name(
                            native_name, english_name
                        )
                    else:
                        display_name = native_name

                if quality == "native":
                    icon = self.QUALITY_ICONS.get("native")
                    marker = self.QUALITY_MARKERS["native"]
                elif quality == "reviewed":
                    icon = self.QUALITY_ICONS.get("reviewed")
                    marker = self.QUALITY_MARKERS["reviewed"]
                elif quality == "unreviewed":
                    icon = self.QUALITY_ICONS.get("unreviewed")
                    marker = self.QUALITY_MARKERS["unreviewed"]
                elif quality == "machine":
                    icon = self.QUALITY_ICONS.get("machine")
                    marker = self.QUALITY_MARKERS["machine"]
                else:
                    icon = self.QUALITY_ICONS.get("unknown")
                    marker = self.QUALITY_MARKERS["unknown"]

                if icon is None or icon.isNull():
                    # Fall back to text marker prefix if the resource icon is missing.
                    display_name = f"{marker} {display_name}"
                    self.language_combo.addItem(display_name, lang_code)
                else:
                    self.language_combo.addItem(icon, display_name, lang_code)
            else:
                display_name = lang_info
                self.language_combo.addItem(display_name, lang_code)

        selection_index = 0
        for i in range(self.language_combo.count()):
            item_data = self.language_combo.itemData(i)
            if item_data == self.current_language:
                selection_index = i
                break

        self.language_combo.setCurrentIndex(selection_index)

    def on_language_changed(self):
        """Store the newly selected language code."""

        self.new_language = self.language_combo.currentData()

    def apply_language_change(self):
        """Apply the selected language and close the dialog."""

        if self.new_language != self.current_language:
            try:
                if self.parent_window and hasattr(
                    self.parent_window, "change_language"
                ):
                    self.parent_window.change_language(self.new_language)
                    self.accept()
                else:
                    QMessageBox.warning(
                        self,
                        self.tr("Error"),
                        self.tr(
                            "Could not change language: Parent window not available"
                        ),
                    )
            except Exception as e:
                QMessageBox.warning(
                    self,
                    self.tr("Error"),
                    self.tr("Failed to change language: {}").format(str(e)),
                )
        else:
            self.accept()


def show_language_selection(parent=None):
    """Display the language selection dialog.

    Args:
        parent: Parent widget for the dialog.

    Returns:
        True if the user accepted a language change, False otherwise.
    """
    try:
        current_language = "en_us"
        if parent and hasattr(parent, "app_config"):
            current_language = parent.app_config.get_language()

        dialog = LanguageSelectionWindow(parent, current_language)
        result = dialog.exec()

        return result == QDialog.DialogCode.Accepted

    except Exception as e:
        if parent:
            from PySide6.QtCore import QCoreApplication

            error_msg = QCoreApplication.translate(
                "LanguageSelectionWindow", "Could not open language selection: {error}"
            ).format(error=str(e))
            QMessageBox.warning(
                parent,
                QCoreApplication.translate("LanguageSelectionWindow", "Error"),
                error_msg,
            )
        return False
