#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verification and configuration of required external tools like ImageMagick."""

import shutil
import os
import platform
from typing import List, Tuple

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels

from utils.utilities import Utilities


class ErrorDialogWithLinks(QDialog):
    """Dialog displaying an error message with clickable hyperlinks."""

    tr = translate

    def __init__(self, message: str, links: List[Tuple[str, str]], parent=None):
        """Initialize the error dialog.

        Args:
            message: Error text to display.
            links: List of (label, url) tuples rendered as hyperlinks.
            parent: Parent widget for the dialog.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Error"))
        self.setFixedSize(400, 300)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        if parent:
            self.move(parent.geometry().center() - self.rect().center())

        self.setup_ui(message, links)

    def setup_ui(self, message: str, links: List[Tuple[str, str]]):
        """Build the message label, link labels, and OK button.

        Args:
            message: Error text to display.
            links: List of (label, url) tuples rendered as hyperlinks.
        """
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(msg_label)

        for link_text, link_url in links:
            link_label = QLabel(f'<a href="{link_url}">{link_text}</a>')
            link_label.setOpenExternalLinks(True)
            link_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            layout.addWidget(link_label)

        layout.addStretch()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_button = QPushButton(self.tr(ButtonLabels.OK))
        ok_button.clicked.connect(self.accept)
        ok_button.setFixedWidth(80)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)


class DependenciesChecker:
    """Utility for verifying and configuring external dependencies."""

    @staticmethod
    def show_error_popup_with_links(
        message: str, links: List[Tuple[str, str]], parent=None
    ):
        """Display an error dialog with clickable hyperlinks.

        Args:
            message: Error text to display.
            links: List of (label, url) tuples rendered as hyperlinks.
            parent: Parent widget for the dialog.
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        dialog = ErrorDialogWithLinks(message, links, parent)
        dialog.exec()

    @staticmethod
    def show_error_popup(message: str, parent=None):
        """Display a simple error message box.

        Args:
            message: Error text to display.
            parent: Parent widget for the dialog.
        """
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

            QMessageBox.critical(
                parent, translate("DependenciesChecker", "Error"), message
            )

    @staticmethod
    def check_imagemagick():
        """Check whether ImageMagick is available on the system PATH.

        Returns:
            True if the 'magick' command is found.
        """
        return shutil.which("magick") is not None

    @staticmethod
    def configure_imagemagick():
        """Configure the bundled ImageMagick by setting environment variables.

        Raises:
            FileNotFoundError: If the bundled ImageMagick folder is missing.
        """
        imagemagick_path = Utilities.find_root("ImageMagick")
        if imagemagick_path is None:
            raise FileNotFoundError(
                "Could not find 'ImageMagick' folder in any parent directory."
            )

        dll_path = os.path.join(imagemagick_path, "ImageMagick")
        if not os.path.isdir(dll_path):
            raise FileNotFoundError(
                f"Expected ImageMagick folder but couldn't be found at: {dll_path}"
            )

        os.environ["PATH"] = dll_path + os.pathsep + os.environ.get("PATH", "")

        coders_path = os.path.join(dll_path, "modules", "coders")
        if os.path.isdir(coders_path):
            os.environ["MAGICK_CODER_MODULE_PATH"] = coders_path

        print(f"[ImageMagick] Using bundled installation from: {dll_path}")

    @staticmethod
    def configure_imagemagick_unix():
        """Configure ImageMagick on Unix systems by setting MAGICK_HOME.

        This helps the Wand library find ImageMagick installed via package managers.
        The environment variable must be set before importing wand.

        Returns:
            True if MAGICK_HOME was set, False otherwise.
        """
        if os.environ.get("MAGICK_HOME"):
            print(f"[ImageMagick] MAGICK_HOME already set: {os.environ['MAGICK_HOME']}")
            return True

        magick_home = None

        if platform.system() == "Darwin":  # macOS
            # Homebrew on Apple Silicon
            if os.path.isdir("/opt/homebrew"):
                magick_home = "/opt/homebrew"
            # Homebrew on Intel
            elif os.path.isdir("/usr/local/opt/imagemagick"):
                magick_home = "/usr/local/opt/imagemagick"
            # MacPorts
            elif os.path.isdir("/opt/local") and os.path.exists(
                "/opt/local/lib/libMagickWand-7.Q16HDRI.dylib"
            ):
                magick_home = "/opt/local"
        else:  # Linux
            lib_paths = [
                "/usr/lib/libMagickWand-7.Q16HDRI.so",
                "/usr/lib/x86_64-linux-gnu/libMagickWand-7.Q16HDRI.so",
                "/usr/lib/aarch64-linux-gnu/libMagickWand-7.Q16HDRI.so",
                "/usr/lib64/libMagickWand-7.Q16HDRI.so",
            ]
            for lib_path in lib_paths:
                if os.path.exists(lib_path):
                    magick_home = "/usr"
                    break

        if magick_home:
            os.environ["MAGICK_HOME"] = magick_home
            print(f"[ImageMagick] Set MAGICK_HOME to: {magick_home}")
            return True

        return False

    @staticmethod
    def check_and_configure_imagemagick():
        """Ensure ImageMagick is available, configuring bundled version if needed.

        Returns:
            True if ImageMagick is ready for use, False otherwise.
        """
        if DependenciesChecker.check_imagemagick():
            print("[ImageMagick] Using system ImageMagick.")
            # On Unix, also set MAGICK_HOME to help Wand find the libraries
            if platform.system() != "Windows":
                DependenciesChecker.configure_imagemagick_unix()
            return True

        if platform.system() == "Windows":
            print(
                "[ImageMagick] System ImageMagick not found. Attempting bundled version..."
            )
            try:
                DependenciesChecker.configure_imagemagick()
                print("[ImageMagick] Bundled ImageMagick configured successfully.")
                return True
            except Exception as e:
                print(f"[ImageMagick] Failed to configure bundled ImageMagick: {e}")
        else:
            # On Unix, try to set MAGICK_HOME even if magick command not found
            print(
                "[ImageMagick] Command not found. Attempting to configure MAGICK_HOME..."
            )
            if DependenciesChecker.configure_imagemagick_unix():
                print("[ImageMagick] MAGICK_HOME configured for Wand library.")

        msg = (
            "ImageMagick not found or failed to initialize.\n\n"
            "Make sure you followed install steps correctly.\n"
            "If the issue persists, install ImageMagick manually."
        )

        if platform.system() == "Windows":
            links = [
                (
                    "App Installation Steps",
                    "https://textureatlastoolbox.com/installation.html",
                ),
                (
                    "Download ImageMagick for Windows",
                    "https://imagemagick.org/script/download.php#windows",
                ),
                (
                    "ImageMagick Windows Binary",
                    "https://download.imagemagick.org/ImageMagick/download/binaries/",
                ),
            ]
        elif platform.system() == "Darwin":  # macOS
            links = [
                (
                    "App Installation Steps",
                    "https://textureatlastoolbox.com/installation.html",
                ),
                (
                    "Download ImageMagick for macOS",
                    "https://imagemagick.org/script/download.php#macosx",
                ),
                ("Install via Homebrew: brew install imagemagick", "https://brew.sh/"),
            ]
        else:  # Linux and others
            links = [
                (
                    "App Installation Steps",
                    "https://textureatlastoolbox.com/installation.html",
                ),
                (
                    "Download ImageMagick for Linux",
                    "https://imagemagick.org/script/download.php#unix",
                ),
                (
                    "Ubuntu/Debian command: sudo apt install imagemagick",
                    "https://packages.ubuntu.com/imagemagick",
                ),
            ]

        DependenciesChecker.show_error_popup_with_links(msg, links)
        return False
