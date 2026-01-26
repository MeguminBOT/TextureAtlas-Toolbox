#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog displaying current animation and spritesheet override settings."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels


class SettingsWindow(QDialog):
    """Modal dialog listing user-defined animation and spritesheet overrides.

    Attributes:
        settings_manager: Manager holding the current override dictionaries.
        content_widget: Scrollable container for settings labels.
        content_layout: Vertical layout inside the content widget.
    """

    tr = translate

    def __init__(self, parent, settings_manager):
        """Initialize the settings overview dialog.

        Args:
            parent: Parent widget for the dialog.
            settings_manager: Manager containing override settings to display.
        """
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle(self.tr("Current Settings Overview"))
        self.setModal(True)
        self.resize(450, 350)

        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.update_settings()

        scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton(self.tr(ButtonLabels.CLOSE))
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        main_layout.addLayout(button_layout)

    def update_settings(self):
        """Refresh the displayed animation and spritesheet settings."""

        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        animation_label = QLabel(self.tr("Animation Settings"))
        animation_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        animation_label.setStyleSheet(
            "QLabel { color: #2E86AB; margin: 10px 0 5px 0; }"
        )
        self.content_layout.addWidget(animation_label)

        if self.settings_manager.animation_settings:
            for key, value in self.settings_manager.animation_settings.items():
                setting_label = QLabel(
                    self.tr("  {key}: {value}").format(key=key, value=value)
                )
                setting_label.setStyleSheet("QLabel { margin-left: 20px; }")
                self.content_layout.addWidget(setting_label)
        else:
            no_settings_label = QLabel(
                self.tr("  No animation-specific settings configured")
            )
            no_settings_label.setStyleSheet(
                "QLabel { margin-left: 20px; color: #777; font-style: italic; }"
            )
            self.content_layout.addWidget(no_settings_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { margin: 10px 0; }")
        self.content_layout.addWidget(separator)

        spritesheet_label = QLabel(self.tr("Spritesheet Settings"))
        spritesheet_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        spritesheet_label.setStyleSheet(
            "QLabel { color: #A23B72; margin: 10px 0 5px 0; }"
        )
        self.content_layout.addWidget(spritesheet_label)

        if self.settings_manager.spritesheet_settings:
            for key, value in self.settings_manager.spritesheet_settings.items():
                setting_label = QLabel(
                    self.tr("  {key}: {value}").format(key=key, value=value)
                )
                setting_label.setStyleSheet("QLabel { margin-left: 20px; }")
                self.content_layout.addWidget(setting_label)
        else:
            no_settings_label = QLabel(
                self.tr("  No spritesheet-specific settings configured")
            )
            no_settings_label.setStyleSheet(
                "QLabel { margin-left: 20px; color: #777; font-style: italic; }"
            )
            self.content_layout.addWidget(no_settings_label)

        self.content_layout.addStretch()
