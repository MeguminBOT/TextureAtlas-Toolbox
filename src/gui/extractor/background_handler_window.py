#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog for configuring background color removal on unknown spritesheets.

Provides a user interface for selecting which detected background colors
should be keyed out during extraction. Supports batch selection and
per-spritesheet control.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QFrame,
    QCheckBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPainter

from utils.translation_manager import tr as translate


class BackgroundHandlerWindow(QDialog):
    """Dialog for background color detection and removal options.

    Displays detected background colors for unknown spritesheets and
    provides checkboxes to control whether background removal should
    be applied to each spritesheet.

    Attributes:
        detection_results: Original list of detection result dictionaries.
        result: Dictionary mapping filenames to processing choices.
        checkbox_vars: Dictionary mapping filenames to their QCheckBox widgets.
        filtered_results: Detection results excluding images with transparency.
    """

    tr = translate

    def __init__(self, parent, detection_results):
        """Create the background handler dialog.

        Args:
            parent: Parent widget for the dialog.
            detection_results: List of dicts with 'filename', 'colors', and
                'has_transparency' keys from background detection.
        """
        super().__init__(parent)
        self.detection_results = detection_results
        self.result = {}
        self.checkbox_vars = {}

        self.setWindowTitle(self.tr("Background Color Options"))
        self.setModal(True)
        self.resize(750, 550)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.filtered_results = [
            result
            for result in detection_results
            if not result.get("has_transparency", False)
        ]

        for detection_result in detection_results:
            if detection_result.get("has_transparency", False):
                self.result[detection_result["filename"]] = "exclude_background"

        if not self.filtered_results:
            print("[BackgroundHandlerWindow] No images need background processing")
            self.accept()
            return

            print(
                f"[BackgroundHandlerWindow] Filtered to {len(self.filtered_results)} images needing background processing"
            )

        self.setup_ui()

    def setup_ui(self):
        """Build the dialog layout with spritesheet entries and controls."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        title_layout = QHBoxLayout()

        icon_label = QLabel("🎨")
        icon_label.setFont(QFont("Arial", 24))
        title_layout.addWidget(icon_label)

        title_text = QLabel(self.tr("Background Color Options"))
        title_text.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_layout.addWidget(title_text)
        title_layout.addStretch()

        main_layout.addLayout(title_layout)

        # Description
        description = self.tr(
            "Found {count} unknown spritesheet(s) with background colors.\n"
            "Check the box next to each file to remove its background color during processing:"
        ).format(count=len(self.filtered_results))

        desc_label = QLabel(description)
        desc_label.setFont(QFont("Arial", 10))
        desc_label.setWordWrap(True)
        main_layout.addWidget(desc_label)

        global_layout = QHBoxLayout()

        select_all_btn = QPushButton(self.tr("Select All"))
        select_all_btn.clicked.connect(self.select_all)
        select_all_btn.setMaximumWidth(100)
        global_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton(self.tr("Select None"))
        select_none_btn.clicked.connect(self.select_none)
        select_none_btn.setMaximumWidth(100)
        global_layout.addWidget(select_none_btn)

        global_layout.addStretch()
        main_layout.addLayout(global_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setSpacing(3)

        for i, result in enumerate(self.filtered_results):
            entry_widget = self.create_spritesheet_entry(result, i)
            content_layout.addWidget(entry_widget)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        options_frame = QFrame()
        options_layout = QVBoxLayout(options_frame)

        options_label = QLabel(self.tr("Processing Options:"))
        options_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        options_layout.addWidget(options_label)

        option_text = self.tr(
            "• Checked: Remove background colors (apply color keying)\n"
            "• Unchecked: Keep background colors but exclude them during sprite detection"
        )

        options_desc = QLabel(option_text)
        options_desc.setFont(QFont("Arial", 9))
        options_desc.setStyleSheet("QLabel { margin-left: 10px; }")
        options_layout.addWidget(options_desc)

        transparency_tip = QLabel(
            self.tr(
                "💡 Tip: Checked files will have transparent backgrounds in PNG, WebP, and APNG outputs"
            )
        )
        transparency_tip.setFont(QFont("Arial", 8))
        transparency_tip.setStyleSheet("QLabel { margin-left: 10px; color: #0066cc; }")
        options_layout.addWidget(transparency_tip)

        main_layout.addWidget(options_frame)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        apply_btn = QPushButton(self.tr("Apply Settings"))
        apply_btn.clicked.connect(self.on_apply)
        apply_btn.setMinimumWidth(120)
        apply_btn.setDefault(True)
        button_layout.addWidget(apply_btn)

        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.clicked.connect(self.on_cancel)
        cancel_btn.setMinimumWidth(120)
        button_layout.addWidget(cancel_btn)

        main_layout.addLayout(button_layout)

        apply_btn.setShortcut("Return")
        cancel_btn.setShortcut("Escape")

    def create_spritesheet_entry(self, result, index):
        """Build a widget displaying one spritesheet's detected colors.

        Args:
            result: Detection result dict with 'filename' and 'colors' keys.
            index: Zero-based index for alternating row colors.

        Returns:
            QFrame containing the checkbox, filename, and color samples.
        """
        bg_color = "#f0f0f0" if index % 2 == 0 else "#ffffff"

        entry_frame = QFrame()
        entry_frame.setFrameStyle(QFrame.Shape.Box)
        entry_frame.setLineWidth(1)
        entry_frame.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; border: 1px solid #ccc; }}"
        )

        layout = QVBoxLayout(entry_frame)
        layout.setSpacing(3)
        layout.setContentsMargins(8, 4, 8, 4)

        header_layout = QHBoxLayout()

        checkbox = QCheckBox()
        checkbox.setChecked(True)
        self.checkbox_vars[result["filename"]] = checkbox
        header_layout.addWidget(checkbox)

        filename_label = QLabel(
            self.tr("📄 {filename}").format(filename=result["filename"])
        )
        filename_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(filename_label)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        colors_label = QLabel(self.tr("Detected background colors:"))
        colors_label.setFont(QFont("Arial", 9))
        colors_label.setStyleSheet("QLabel { margin-left: 15px; }")
        layout.addWidget(colors_label)

        for color_index, color in enumerate(result["colors"][:3]):
            color_layout = self.create_color_sample(color, color_index)
            layout.addLayout(color_layout)

        if len(result["colors"]) > 3:
            more_label = QLabel(
                self.tr("... and {count} more colors").format(
                    count=len(result["colors"]) - 3
                )
            )
            more_label.setFont(QFont("Arial", 8))
            more_label.setStyleSheet("QLabel { margin-left: 25px; color: gray; }")
            layout.addWidget(more_label)

        return entry_frame

    def create_color_sample(self, color, color_index):
        """Build a row with a color swatch and RGB label.

        Args:
            color: RGB tuple (r, g, b) for the detected color.
            color_index: Position in the color list (0 = primary).

        Returns:
            QHBoxLayout containing the color sample and text label.
        """
        layout = QHBoxLayout()
        layout.setContentsMargins(25, 1, 0, 1)

        color_sample = ColorSampleWidget(color)
        color_sample.setFixedSize(16, 16)
        layout.addWidget(color_sample)

        rgb_text = self.tr("RGB({r}, {g}, {b})").format(
            r=color[0], g=color[1], b=color[2]
        )
        priority_text = (
            self.tr("Primary")
            if color_index == 0
            else self.tr("Secondary {index}").format(index=color_index)
        )

        color_info = QLabel(
            self.tr("{priority}: {rgb}").format(priority=priority_text, rgb=rgb_text)
        )
        color_info.setFont(QFont("Arial", 9))
        layout.addWidget(color_info)
        layout.addStretch()

        return layout

    def select_all(self):
        """Check all spritesheet checkboxes for background removal."""
        for checkbox in self.checkbox_vars.values():
            checkbox.setChecked(True)

    def select_none(self):
        """Uncheck all spritesheet checkboxes."""
        for checkbox in self.checkbox_vars.values():
            checkbox.setChecked(False)

    def on_apply(self):
        """Store checkbox states in result dict and close the dialog."""
        for filename, checkbox in self.checkbox_vars.items():
            if checkbox.isChecked():
                self.result[filename] = "key_background"
            else:
                self.result[filename] = "exclude_background"
        self.accept()

    def on_cancel(self):
        """Clear results, set cancelled flag, and close the dialog."""
        self.result.clear()
        self.result["_cancelled"] = True
        self.reject()

    def get_result(self):
        """Return the mapping of filenames to processing choices.

        Returns:
            Dictionary with filenames as keys and 'key_background',
            'exclude_background', or '_cancelled' as values.
        """
        return self.result

    @staticmethod
    def show_background_options(parent_window, detection_results):
        """Display the background options dialog and return user choices.

        Args:
            parent_window: Parent Qt widget for the modal dialog.
            detection_results: List of dicts containing:
                - 'filename': Spritesheet filename.
                - 'colors': List of (r, g, b) tuples.
                - 'has_transparency': True if image already has alpha.

        Returns:
            Dictionary mapping filenames to processing choices:
            'key_background', 'exclude_background', or '_cancelled'.
        """
        print(
            f"[BackgroundHandlerWindow] Called with {len(detection_results)} detection results"
        )

        dialog = BackgroundHandlerWindow(parent_window, detection_results)
        dialog.exec()
        return dialog.get_result()

    @staticmethod
    def reset_batch_state():
        """Reset batch processing state for a new extraction session."""
        print("[BackgroundHandlerWindow] Batch state reset for new processing")


class ColorSampleWidget(QWidget):
    """Widget displaying a small colored rectangle.

    Renders a bordered square filled with the specified RGB color.

    Attributes:
        color: QColor instance for the fill color.
    """

    tr = translate

    def __init__(self, rgb_color):
        """Create a color sample widget.

        Args:
            rgb_color: Tuple of (r, g, b) values in 0-255 range.
        """
        super().__init__()
        self.color = QColor(rgb_color[0], rgb_color[1], rgb_color[2])

    def paintEvent(self, event):
        """Draw the color swatch with a black border.

        Args:
            event: QPaintEvent triggering the repaint.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setPen(QColor(0, 0, 0))
        painter.setBrush(self.color)
        painter.drawRect(1, 1, self.width() - 2, self.height() - 2)
