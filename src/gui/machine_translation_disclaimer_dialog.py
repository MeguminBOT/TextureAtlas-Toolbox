#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog warning users about machine-translated content quality."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QCheckBox,
)
from PySide6.QtCore import Qt, QSettings

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels


class MachineTranslationDisclaimerDialog(QDialog):
    """Modal dialog displaying a machine translation quality warning.

    Attributes:
        language_name: Display name of the translated language.
        disclaimer_title: Title text for the warning.
        disclaimer_message: Body text explaining translation limitations.
    """

    tr = translate

    def __init__(
        self, parent=None, language_name="", disclaimer_title="", disclaimer_message=""
    ):
        """Initialize the disclaimer dialog.

        Args:
            parent: Parent widget for the dialog.
            language_name: Display name of the language.
            disclaimer_title: Title for the disclaimer window.
            disclaimer_message: Warning message body text.
        """
        super().__init__(parent)
        self.language_name = language_name
        self.disclaimer_title = disclaimer_title
        self.disclaimer_message = disclaimer_message
        self.setup_ui()

    def setup_ui(self):
        """Build the header, message area, checkbox, and buttons."""

        self.setWindowTitle(self.disclaimer_title)
        self.setModal(True)
        self.resize(500, 300)

        layout = QVBoxLayout(self)

        header_layout = QHBoxLayout()

        icon_label = QLabel()
        icon_label.setText("🤖")
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(48, 48)
        header_layout.addWidget(icon_label)

        title_label = QLabel(f"{self.disclaimer_title}\n{self.language_name}")
        title_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-left: 10px;"
        )
        title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        header_layout.addWidget(title_label)

        header_layout.addStretch()
        layout.addLayout(header_layout)

        message_text = QTextEdit()
        message_text.setPlainText(self.disclaimer_message)
        message_text.setReadOnly(True)
        message_text.setMaximumHeight(120)
        message_text.setStyleSheet(
            """
            QTextEdit {
                border: 1px solid palette(mid);
                padding: 8px;
                background-color: palette(base);
                color: palette(text);
                border-radius: 4px;
            }
        """
        )
        layout.addWidget(message_text)

        self.dont_show_checkbox = QCheckBox(
            self.tr("Don't show this disclaimer again for this language")
        )
        layout.addWidget(self.dont_show_checkbox)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        github_button = QPushButton(self.tr("View on GitHub"))
        github_button.clicked.connect(self.open_github)
        button_layout.addWidget(github_button)

        ok_button = QPushButton(self.tr(ButtonLabels.OK))
        ok_button.setDefault(True)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

    def open_github(self):
        """Open the project repository in the default browser."""

        import webbrowser

        webbrowser.open("https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames")

    def should_save_preference(self):
        """Check whether the user opted to hide future disclaimers.

        Returns:
            True if the 'don't show again' checkbox is checked.
        """
        return self.dont_show_checkbox.isChecked()

    @staticmethod
    def should_show_disclaimer(language_code):
        """Determine if the disclaimer should appear for a language.

        Args:
            language_code: ISO language code to check.

        Returns:
            True if the disclaimer has not been dismissed for this language.
        """
        settings = QSettings()
        return not settings.value(
            f"translations/hide_disclaimer_{language_code}", False, type=bool
        )

    @staticmethod
    def set_disclaimer_preference(language_code, hide=True):
        """Persist the user's disclaimer visibility preference.

        Args:
            language_code: ISO language code to store the preference for.
            hide: If True, suppress future disclaimers for this language.
        """
        settings = QSettings()
        settings.setValue(f"translations/hide_disclaimer_{language_code}", hide)

    @staticmethod
    def show_machine_translation_disclaimer(
        parent, translation_manager, language_code, language_name
    ):
        """Display the disclaimer dialog if required for a machine-translated language.

        Args:
            parent: Parent widget for the dialog.
            translation_manager: Manager providing translation metadata.
            language_code: ISO code of the language being activated.
            language_name: Human-readable language name.

        Returns:
            True if the user accepted or no disclaimer was needed.
        """
        if not MachineTranslationDisclaimerDialog.should_show_disclaimer(language_code):
            return True

        if not translation_manager.is_machine_translated(language_code):
            return True

        title, message = translation_manager.get_machine_translation_disclaimer()

        dialog = MachineTranslationDisclaimerDialog(
            parent, language_name, title, message
        )
        result = dialog.exec()

        if dialog.should_save_preference():
            MachineTranslationDisclaimerDialog.set_disclaimer_preference(
                language_code, True
            )

        return result == QDialog.DialogCode.Accepted
