#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modal dialog acknowledging project contributors with links to their profiles."""

import webbrowser
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
from utils.ui_constants import ButtonLabels, WindowTitles


class ContributorsWindow(QDialog):
    """Modal dialog displaying project contributors with clickable profile links."""

    tr = translate

    def __init__(self, parent=None):
        """Initialize the dialog and build the contributor list UI.

        Args:
            parent: Parent widget for the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr(WindowTitles.CONTRIBUTORS))
        self.setMinimumSize(360, 300)
        self.resize(550, 480)
        self.setup_ui()

    def setup_ui(self):
        """Build the scrollable contributor list with title and close button."""

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        title_label = QLabel(self.tr("TextureAtlas Toolbox\nContributors"))
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)

        self.add_contributors(content_layout)

        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        close_btn = QPushButton(self.tr(ButtonLabels.CLOSE))
        close_btn.clicked.connect(self.close)
        close_btn.setMaximumWidth(100)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def add_contributors(self, layout):
        """Add contributor cards to the layout.

        Args:
            layout: Parent layout receiving each contributor card.
        """
        contributors_data = [
            {
                "name": "AutisticLulu",
                "role": "Project starter",
                "links": [
                    ("GitHub", "https://github.com/MeguminBOT"),
                    (
                        "Project Repository",
                        "https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames",
                    ),
                ],
            },
            {
                "name": "Jsfasdf250",
                "role": "Major contributor",
                "links": [
                    ("GitHub", "https://github.com/Jsfasdf250"),
                ],
            },
            {
                "name": "Julnz",
                "role": "App icon",
                "links": [
                    ("Website", "https://julnz.com"),
                ],
            },
        ]

        for contributor in contributors_data:
            self.add_contributor_card(layout, contributor)

    def add_contributor_card(self, layout, contributor_data):
        """Create and add a styled contributor card to the layout.

        Args:
            layout: Parent layout receiving the card widget.
            contributor_data: Dictionary with 'name', optional 'role',
                optional 'description', and optional 'links' list of
                (label, url) tuples.
        """
        card_frame = QFrame()
        card_frame.setFrameStyle(QFrame.Shape.Box)
        card_frame.setLineWidth(1)
        card_layout = QVBoxLayout(card_frame)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(15, 15, 15, 15)

        name_label = QLabel(contributor_data["name"])
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        name_label.setFont(name_font)
        card_layout.addWidget(name_label)

        if "role" in contributor_data:
            role_label = QLabel(contributor_data["role"])
            role_label.setStyleSheet("color: palette(placeholderText);")
            card_layout.addWidget(role_label)

        if "description" in contributor_data:
            desc_label = QLabel(contributor_data["description"])
            desc_label.setWordWrap(True)
            card_layout.addWidget(desc_label)

        if "links" in contributor_data:
            links_layout = QHBoxLayout()
            for link_text, link_url in contributor_data["links"]:
                link_btn = QPushButton(link_text)
                link_btn.clicked.connect(
                    lambda checked, url=link_url: self.open_link(url)
                )
                link_btn.setMaximumWidth(150)
                links_layout.addWidget(link_btn)
            links_layout.addStretch()
            card_layout.addLayout(links_layout)

        layout.addWidget(card_frame)

    def open_link(self, url):
        """Open a URL in the user's default web browser.

        Args:
            url: Web address to open.
        """
        webbrowser.open(url)

    @staticmethod
    def show_contributors(parent=None):
        """Display the contributors dialog modally.

        Args:
            parent: Parent widget for the dialog.
        """
        window = ContributorsWindow(parent)
        window.exec()
