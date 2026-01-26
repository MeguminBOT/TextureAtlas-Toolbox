#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scrollable help dialogs for application documentation and FNF guidance."""

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit
from PySide6.QtGui import QFont

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels


class HelpWindow(QDialog):
    """Modal dialog displaying scrollable help text with monospace formatting."""

    tr = translate

    def __init__(self, parent=None, help_text="", title="Help"):
        """Initialize the help dialog with the given content.

        Args:
            parent: Parent widget for the dialog.
            help_text: Documentation text to display.
            title: Window title.
        """
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setGeometry(200, 200, 800, 600)
        self.help_text = help_text
        self.setup_ui()

    def setup_ui(self):
        """Build the text area and close button layout."""

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        text_edit = QTextEdit()
        text_edit.setPlainText(self.help_text)
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(text_edit)

        close_btn = QPushButton(self.tr(ButtonLabels.CLOSE))
        close_btn.clicked.connect(self.close)
        close_btn.setMaximumWidth(100)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    @staticmethod
    def create_main_help_window(parent=None):
        """Display the main help dialog with application instructions.

        Args:
            parent: Parent widget for the dialog.
        """
        help_text = (
            "_________________________________________ Main Window _________________________________________\n\n"
            "DRAG AND DROP\n"
            "You can drag and drop a folder containing PNG files and their data files into the window.\n"
            "This will automatically populate the PNG and animation lists.\n\n"
            "INPUT SELECTION\n"
            "• Select Directory: Choose a folder containing PNG files and their corresponding data files\n"
            "• Select Files: Manually choose specific PNG files to process\n\n"
            "OUTPUT SETTINGS\n"
            "• Select an output directory where exported animations and frames will be saved\n\n"
            "ANIMATION FORMATS\n"
            "• GIF: Traditional animated format, supports transparency threshold\n"
            "• WebP: Modern format with better compression and quality\n"
            "• APNG: Animated PNG with full alpha channel support\n\n"
            "FRAME FORMATS\n"
            "• PNG: Lossless with full transparency support\n"
            "• WebP: Modern format with excellent compression\n"
            "• AVIF: Next-generation format with superior compression\n"
            "• TGA, TIFF, BMP, DDS: Additional format options\n\n"
            "ANIMATION SETTINGS\n"
            "• Frame Rate: Playback speed in frames per second\n"
            "• Loop Delay: Pause before animation repeats (milliseconds)\n"
            "• Minimum Period: Minimum total animation duration\n"
            "• Scale: Resize factor for output animations\n"
            "• Alpha Threshold: Transparency cutoff for GIF format\n\n"
            "FRAME SETTINGS\n"
            "• Frame Selection: Choose which frames to export (All, No duplicates, First, Last, etc.)\n"
            "• Frame Scale: Resize factor for individual frames\n"
            "• Compression: Format-specific quality settings\n\n"
            "CROPPING OPTIONS\n"
            "• None: Keep original frame dimensions\n"
            "• Animation Based: Crop to the bounds of all frames in animation\n"
            "• Frame Based: Crop each frame individually\n\n"
            "FILENAME OPTIONS\n"
            "• Prefix/Suffix: Add text before or after filenames\n"
            "• Format: Choose naming convention (Standardized, No spaces, No special chars)\n"
            "• Advanced: Use find/replace rules for custom filename processing\n\n"
            "OVERRIDE SETTINGS\n"
            "• Override Spritesheet Settings: Custom settings for specific PNG files\n"
            "• Override Animation Settings: Custom settings for specific animations\n"
            "• Show Override Settings: View all current custom settings\n\n"
            "PROCESSING\n"
            "1. Select input directory or files\n"
            "2. Select output directory\n"
            "3. Configure animation and frame settings\n"
            "4. Click 'Start Process' to begin extraction\n\n"
            "LIST OPERATIONS\n"
            "• Single-click a PNG file to view its animations\n"
            "• Double-click an animation to preview it\n"
            "• Right-click a PNG file to delete it from the list\n\n"
            "KEYBOARD SHORTCUTS\n"
            "• Ctrl+O: Open directory\n"
            "• Ctrl+Shift+O: Open files\n"
            "• F1: Show this help\n"
            "• Escape: Cancel current operation\n\n"
        )

        window = HelpWindow(parent, help_text, "Main Help")
        window.exec()

    @staticmethod
    def create_fnf_help_window(parent=None):
        """Display the Friday Night Funkin' sprite handling guide.

        Args:
            parent: Parent widget for the dialog.
        """
        help_text = (
            "________________________________ Friday Night Funkin' Guide ________________________________\n\n"
            "SPECIAL FNF FEATURES\n"
            "This application includes special support for Friday Night Funkin' (FNF) character sprites.\n\n"
            "IMPORTING FNF CHARACTER DATA\n"
            "• Use 'Import → FNF: Import settings from character data file'\n"
            "• Select a character's JSON data file\n"
            "• Animation settings will be automatically configured\n\n"
            "FNF SPRITE STRUCTURE\n"
            "FNF characters typically include:\n"
            "• PNG spritesheet file (e.g., 'BOYFRIEND.png')\n"
            "• XML data file (e.g., 'BOYFRIEND.xml')\n"
            "• JSON character data (e.g., 'BOYFRIEND.json')\n\n"
            "RECOMMENDED SETTINGS FOR FNF\n"
            "Animation Format: WebP or APNG (better quality than GIF)\n"
            "Frame Rate: 24 FPS (standard for FNF)\n"
            "Loop Delay: 0 ms for idle animations, 250ms+ for others\n"
            "Scale: 1.0x (maintain original size)\n"
            "Cropping: Animation Based (removes empty space)\n\n"
            "FNF ANIMATION TYPES\n"
            "• Idle: Continuous looping character stance\n"
            "• Sing: Note-hitting animations (left, down, up, right)\n"
            "• Miss: Failed note animations\n"
            "• Hey: Special gesture animations\n\n"
            "BATCH PROCESSING FNF CHARACTERS\n"
            "1. Place all character folders in one directory\n"
            "2. Use 'Select Directory' to process multiple characters\n"
            "3. Set global animation settings\n"
            "4. Use override settings for character-specific adjustments\n\n"
            "FNF-SPECIFIC TIPS\n"
            "• Enable 'No duplicates' frame selection to reduce file sizes\n"
            "• Use variable delay for more natural animation timing\n"
            "• Consider APNG format for characters with complex transparency\n"
            "• Export both animations and individual frames for modding flexibility\n\n"
            "TROUBLESHOOTING FNF IMPORTS\n"
            "• Ensure XML and PNG files have matching names\n"
            "• Check that JSON character data is properly formatted\n"
            "• Verify animation names match between XML and JSON files\n"
            "• Use 'Show Override Settings' to review imported configurations\n\n"
            "MODDING COMPATIBILITY\n"
            "Exported animations work with:\n"
            "• Psych Engine\n"
            "• Kade Engine\n"
            "• Base FNF\n"
            "• Most FNF mods and engines\n\n"
        )

        window = HelpWindow(parent, help_text, "FNF Help")
        window.exec()

    @staticmethod
    def create_scrollable_help_window(help_text, title="Help", parent=None):
        """Display a custom help dialog with the given text.

        Args:
            help_text: Documentation text to display.
            title: Window title.
            parent: Parent widget for the dialog.
        """
        window = HelpWindow(parent, help_text, title)
        window.exec()
