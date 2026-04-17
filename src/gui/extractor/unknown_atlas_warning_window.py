#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Warning dialog for unknown or unsupported texture atlas formats.

Displays detected unknown atlases with thumbnails and lets users choose
whether to proceed with limited extraction, skip unknown files, or cancel.
"""

import os
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QFrame,
    QGridLayout,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels, MenuActions, WindowTitles

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class UnknownAtlasWarningWindow(QDialog):
    """Modal dialog warning about unknown atlas formats.

    Shows a list of detected unknown atlases with thumbnails, explains their
    extraction limitations, and offers proceed/skip/cancel options.

    Attributes:
        unknown_atlases: List of filenames with unrecognized formats.
        input_directory: Path to the directory containing atlas files.
        result: User's choice: "proceed", "skip", or "cancel".
    """

    tr = translate

    def __init__(self, parent, unknown_atlases, input_directory=None):
        """Initialize the warning dialog.

        Args:
            parent: Parent widget for modal behavior.
            unknown_atlases: List of atlas filenames with unknown formats.
            input_directory: Directory path for loading thumbnails.
        """
        super().__init__(parent)
        self.unknown_atlases = unknown_atlases
        self.input_directory = input_directory
        self.result = "cancel"

        self.setWindowTitle(self.tr(WindowTitles.UNKNOWN_ATLAS_WARNING))
        self.setModal(True)
        self.resize(600, 650)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.setup_ui()

    def setup_ui(self):
        """Build and configure all UI components for the dialog."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_layout = QHBoxLayout()

        warning_label = QLabel("⚠️")
        warning_label.setFont(QFont("Arial", 24))
        title_layout.addWidget(warning_label)

        title_text = QLabel(self.tr(WindowTitles.UNKNOWN_ATLAS_WARNING))
        title_text.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_text)
        title_layout.addStretch()

        main_layout.addLayout(title_layout)

        message_text = self.tr(
            "Warning: {count} unknown atlas type(s) detected:\n\n"
            "This means either the metadata file is missing or is unsupported.\n\n"
            "The tool can attempt to extract the unknown atlas(es) but has these limitations:\n"
            "• Animation export is not supported\n"
            "• Cropping may be inconsistent\n"
            "• Sprite detection may miss or incorrectly identify sprites\n"
            "• Output may not be usable in rare cases\n\n"
            "What would you like to do?"
        ).format(count=len(self.unknown_atlases))

        message_label = QLabel(message_text)
        message_label.setWordWrap(True)
        message_label.setFont(QFont("Arial", 10))
        message_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        message_label.setStyleSheet("QLabel { margin-bottom: 15px; }")
        main_layout.addWidget(message_label)

        files_label = QLabel(self.tr("Affected files:"))
        files_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        main_layout.addWidget(files_label)

        self.create_thumbnail_section(main_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        proceed_btn = QPushButton(self.tr(MenuActions.PROCEED_ANYWAY))
        proceed_btn.clicked.connect(self.on_proceed)
        proceed_btn.setMinimumWidth(120)
        proceed_btn.setDefault(True)
        button_layout.addWidget(proceed_btn)

        skip_btn = QPushButton(self.tr(MenuActions.SKIP_UNKNOWN))
        skip_btn.clicked.connect(self.on_skip)
        skip_btn.setMinimumWidth(120)
        button_layout.addWidget(skip_btn)

        cancel_btn = QPushButton(self.tr(ButtonLabels.CANCEL))
        cancel_btn.clicked.connect(self.on_cancel)
        cancel_btn.setMinimumWidth(120)
        button_layout.addWidget(cancel_btn)

        main_layout.addLayout(button_layout)

        proceed_btn.setShortcut("Return")
        cancel_btn.setShortcut("Escape")

    def create_thumbnail_section(self, main_layout):
        """Build a scrollable grid of atlas thumbnails.

        Args:
            main_layout: Parent layout to add the thumbnail section to.
        """
        # Create scroll area for thumbnails
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(200)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        thumbnail_widget = QWidget()
        thumbnail_layout = QGridLayout(thumbnail_widget)
        thumbnail_layout.setSpacing(5)

        max_cols = 4
        row = 0
        col = 0

        for i, atlas_name in enumerate(self.unknown_atlases[:16]):
            thumb_frame = self.create_thumbnail_frame(atlas_name)
            thumbnail_layout.addWidget(thumb_frame, row, col)

            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        if len(self.unknown_atlases) > 16:
            more_label = QLabel(
                self.tr("... and {count} more").format(
                    count=len(self.unknown_atlases) - 16
                )
            )
            more_label.setFont(QFont("Arial", 9, QFont.Weight.ExtraLight))
            more_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            more_label.setStyleSheet(
                "QLabel { color: palette(placeholderText); padding: 15px; }"
            )
            thumbnail_layout.addWidget(more_label, row, col)

        for i in range(max_cols):
            thumbnail_layout.setColumnStretch(i, 1)

        scroll_area.setWidget(thumbnail_widget)
        main_layout.addWidget(scroll_area)

    def create_thumbnail_frame(self, atlas_name):
        """Create a framed widget containing a thumbnail and filename.

        Args:
            atlas_name: Filename of the atlas to display.

        Returns:
            QFrame containing the thumbnail image and label.
        """
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setLineWidth(1)
        frame.setStyleSheet(
            "QFrame { background-color: palette(alternateBase); border: 1px solid palette(mid); }"
        )
        frame.setFixedSize(120, 110)

        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)

        thumbnail_label = QLabel()
        thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumbnail_label.setFixedSize(80, 80)

        thumbnail_pixmap = self.create_thumbnail(atlas_name)
        if thumbnail_pixmap:
            thumbnail_label.setPixmap(thumbnail_pixmap)
        else:
            thumbnail_label.setText("📷")
            thumbnail_label.setFont(QFont("Arial", 16))
            thumbnail_label.setStyleSheet(
                "QLabel { border: 1px solid palette(mid); background-color: palette(base); color: palette(placeholderText); }"
            )

        layout.addWidget(thumbnail_label)

        name_label = QLabel(atlas_name)
        name_label.setFont(QFont("Arial", 7))
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(116)
        name_label.setStyleSheet(
            "QLabel { color: palette(text); background-color: palette(alternateBase); padding: 2px; border-radius: 2px; }"
        )
        layout.addWidget(name_label)

        return frame

    def create_thumbnail(self, filename):
        """Generate an 80x80 thumbnail pixmap for the given atlas file.

        Args:
            filename: Name of the image file within input_directory.

        Returns:
            QPixmap scaled to 80x80, or None if loading fails.
        """
        if not PIL_AVAILABLE or not self.input_directory:
            return None

        try:
            file_path = os.path.join(self.input_directory, filename)
            if not os.path.exists(file_path):
                return None

            with Image.open(file_path) as img:
                if img.mode in ("RGBA", "LA", "P"):
                    try:
                        from utils.transparency_utils import composite_with_checkerboard

                        if img.mode == "P":
                            img = img.convert("RGBA")
                        elif img.mode == "LA":
                            rgba_img = Image.new("RGBA", img.size)
                            rgba_img.paste(
                                img,
                                mask=img.split()[-1] if len(img.split()) > 1 else None,
                            )
                            img = rgba_img

                        img.thumbnail((80, 80), Image.Resampling.LANCZOS)
                        img = composite_with_checkerboard(img, square_size=4)

                    except ImportError:
                        background = Image.new("RGB", img.size, (255, 255, 255))
                        if img.mode == "P":
                            img = img.convert("RGBA")
                        background.paste(
                            img,
                            mask=(
                                img.split()[-1] if img.mode in ("RGBA", "LA") else None
                            ),
                        )
                        img = background
                elif img.mode != "RGB":
                    img = img.convert("RGB")

                if img.mode == "RGBA":
                    try:
                        from utils.transparency_utils import composite_with_checkerboard

                        img.thumbnail((80, 80), Image.Resampling.LANCZOS)
                        img = composite_with_checkerboard(img, square_size=4)
                    except ImportError:
                        img = img.convert("RGB")
                        img.thumbnail((80, 80), Image.Resampling.LANCZOS)
                else:
                    img.thumbnail((80, 80), Image.Resampling.LANCZOS)

                img_path = os.path.join(
                    os.environ.get("TEMP", "/tmp"), f"thumb_{filename}.png"
                )
                img.save(img_path)
                pixmap = QPixmap(img_path)

                try:
                    os.remove(img_path)
                except Exception:
                    pass

                return pixmap.scaled(
                    80,
                    80,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

        except Exception:
            return None

    def on_proceed(self):
        """Accept the dialog with 'proceed' result."""
        self.result = "proceed"
        self.accept()

    def on_skip(self):
        """Accept the dialog with 'skip' result."""
        self.result = "skip"
        self.accept()

    def on_cancel(self):
        """Reject the dialog with 'cancel' result."""
        self.result = "cancel"
        self.reject()

    def get_result(self):
        """Return the user's choice: 'proceed', 'skip', or 'cancel'."""
        return self.result

    @staticmethod
    def show_warning(parent_window, unknown_atlases, input_directory=None):
        """Display the warning dialog and return the user's choice.

        Args:
            parent_window: Parent Qt widget for modal behavior.
            unknown_atlases: List of unknown atlas filenames.
            input_directory: Directory containing atlas files for thumbnails.

        Returns:
            User's choice: 'proceed', 'skip', or 'cancel'.
        """
        dialog = UnknownAtlasWarningWindow(
            parent_window, unknown_atlases, input_directory
        )
        dialog.exec()
        return dialog.get_result()
