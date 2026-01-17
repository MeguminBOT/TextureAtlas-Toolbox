# -*- coding: utf-8 -*-
"""Dialog for configuring image format compression settings.

Provides format-specific controls for PNG, WebP, AVIF, and TIFF compression
options. Integrates with SettingsManager and AppConfig for persistence.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QPushButton,
    QGroupBox,
    QScrollArea,
    QWidget,
)
from PySide6.QtCore import Qt

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels, Labels, WindowTitles, CheckBoxLabels


class CompressionSettingsWindow(QDialog):
    """Dialog for configuring format-specific compression settings.

    Displays controls appropriate to the selected image format and
    persists changes through SettingsManager.

    Attributes:
        settings_manager: SettingsManager instance for saving preferences.
        app_config: AppConfig instance providing default values.
        current_format: Uppercase format string ('PNG', 'WEBP', etc.).
        original_values: Snapshot of values when the dialog opened.
        compression_widgets: Dictionary mapping format names to widget dicts.
    """

    tr = translate

    def __init__(
        self, parent=None, settings_manager=None, app_config=None, current_format="PNG"
    ):
        """Create the compression settings dialog.

        Args:
            parent: Parent widget for the dialog.
            settings_manager: SettingsManager for reading/writing preferences.
            app_config: AppConfig providing format compression defaults.
            current_format: Image format to configure (case-insensitive).
        """
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.app_config = app_config
        self.current_format = current_format.upper()

        self.original_values = {}
        self.compression_widgets = {}

        self.setWindowTitle(self.tr(WindowTitles.COMPRESSION_SETTINGS))
        self.setModal(True)
        self.resize(400, 500)

        self.setup_ui()
        self.load_current_values()

    def setup_ui(self):
        """Build the dialog layout with format-specific controls."""
        layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        format_label = QLabel(
            self.tr("Compression settings for {format}").format(
                format=self.current_format
            )
        )
        format_label.setStyleSheet(
            "font-weight: bold; font-size: 14px; margin-bottom: 10px;"
        )
        content_layout.addWidget(format_label)

        if self.current_format == "PNG":
            self.create_png_settings(content_layout)
        elif self.current_format == "WEBP":
            self.create_webp_settings(content_layout)
        elif self.current_format == "AVIF":
            self.create_avif_settings(content_layout)
        elif self.current_format == "TIFF":
            self.create_tiff_settings(content_layout)
        else:
            no_settings_label = QLabel(
                self.tr(
                    "No compression settings available for {format} format."
                ).format(format=self.current_format)
            )
            no_settings_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            content_layout.addWidget(no_settings_label)

        content_layout.addStretch()
        scroll_area.setWidget(content_widget)
        layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton(self.tr(ButtonLabels.CANCEL))
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        ok_button = QPushButton(self.tr(ButtonLabels.OK))
        ok_button.clicked.connect(self.accept_changes)
        ok_button.setDefault(True)
        button_layout.addWidget(ok_button)

        layout.addLayout(button_layout)

    def create_png_settings(self, layout):
        """Add PNG compression controls to the layout.

        Args:
            layout: Parent QVBoxLayout for the settings group.
        """
        group = QGroupBox(self.tr("PNG Compression Settings"))
        grid = QGridLayout(group)

        grid.addWidget(QLabel(self.tr(Labels.COMPRESS_LEVEL_0_9)), 0, 0)
        compress_level = QSpinBox()
        compress_level.setRange(0, 9)
        compress_level.setValue(9)
        compress_level.setToolTip(
            self.tr(
                "PNG compression level (0-9):\n"
                "• 0: No compression (fastest, largest file)\n"
                "• 1-3: Low compression\n"
                "• 4-6: Medium compression\n"
                "• 7-9: High compression (slowest, smallest file)\n"
                "This doesn't affect the quality of the image, only the file size"
            )
        )
        grid.addWidget(compress_level, 0, 1)

        optimize = QCheckBox(self.tr(CheckBoxLabels.OPTIMIZE_PNG))
        optimize.setToolTip(
            self.tr(
                "PNG optimize:\n"
                "• Enabled: Uses additional compression techniques for smaller files\n"
                "When enabled, compression level is automatically set to 9\n"
                "Results in slower processing but better compression\n\n"
                "This doesn't affect the quality of the image, only the file size"
            )
        )
        optimize.toggled.connect(
            lambda checked: self.on_png_optimize_changed(checked, compress_level)
        )
        grid.addWidget(optimize, 1, 0, 1, 2)

        self.compression_widgets["PNG"] = {
            "compress_level": compress_level,
            "optimize": optimize,
        }

        layout.addWidget(group)

    def create_webp_settings(self, layout):
        """Add WebP compression controls to the layout.

        Args:
            layout: Parent QVBoxLayout for the settings group.
        """
        group = QGroupBox(self.tr("WebP Compression Settings"))
        grid = QGridLayout(group)

        lossless = QCheckBox(self.tr(CheckBoxLabels.LOSSLESS_WEBP))
        lossless.setToolTip(
            self.tr(
                "WebP lossless mode:\n"
                "• Enabled: Perfect quality preservation, larger file size\n"
                "• Disabled: Lossy compression with adjustable quality\n"
                "When enabled, quality sliders are disabled"
            )
        )
        grid.addWidget(lossless, 0, 0, 1, 2)

        grid.addWidget(QLabel(self.tr(Labels.QUALITY_0_100)), 1, 0)
        quality = QSpinBox()
        quality.setRange(0, 100)
        quality.setValue(100)
        quality.setToolTip(
            self.tr(
                "WebP quality (0-100):\n"
                "• 0: Lowest quality, smallest file\n"
                "• 75: Balanced quality/size\n"
                "• 100: Highest quality, largest file\n"
                "Only used in lossy mode"
            )
        )
        grid.addWidget(quality, 1, 1)

        grid.addWidget(QLabel(self.tr(Labels.METHOD_0_6)), 2, 0)
        method = QSpinBox()
        method.setRange(0, 6)
        method.setValue(6)
        method.setToolTip(
            self.tr(
                "WebP compression method (0-6):\n"
                "• 0: Fastest encoding, larger file\n"
                "• 3: Balanced speed/compression\n"
                "• 6: Slowest encoding, best compression\n"
                "Higher values take more time but produce smaller files"
            )
        )
        grid.addWidget(method, 2, 1)

        grid.addWidget(QLabel(self.tr(Labels.ALPHA_QUALITY_0_100)), 3, 0)
        alpha_quality = QSpinBox()
        alpha_quality.setRange(0, 100)
        alpha_quality.setValue(100)
        alpha_quality.setToolTip(
            self.tr(
                "WebP alpha channel quality (0-100):\n"
                "Controls transparency compression quality\n"
                "• 0: Maximum alpha compression\n"
                "• 100: Best alpha quality\n"
                "Only used in lossy mode"
            )
        )
        grid.addWidget(alpha_quality, 3, 1)

        exact = QCheckBox(self.tr(CheckBoxLabels.EXACT_WEBP))
        exact.setToolTip(
            self.tr(
                "WebP exact mode:\n"
                "• Enabled: Preserves RGB values in transparent areas\n"
                "• Disabled: Allows optimization of transparent pixels\n"
                "Enable for better quality when transparency matters"
            )
        )
        grid.addWidget(exact, 4, 0, 1, 2)

        lossless.toggled.connect(
            lambda checked: self.on_webp_lossless_changed(
                checked, quality, alpha_quality
            )
        )

        self.compression_widgets["WEBP"] = {
            "lossless": lossless,
            "quality": quality,
            "method": method,
            "alpha_quality": alpha_quality,
            "exact": exact,
        }

        layout.addWidget(group)

    def create_avif_settings(self, layout):
        """Add AVIF compression controls to the layout.

        Args:
            layout: Parent QVBoxLayout for the settings group.
        """
        group = QGroupBox(self.tr("AVIF Compression Settings"))
        grid = QGridLayout(group)

        lossless = QCheckBox(self.tr(CheckBoxLabels.LOSSLESS_AVIF))
        lossless.setToolTip(
            self.tr(
                "AVIF lossless mode:\n"
                "• Enabled: Perfect quality preservation, larger file size\n"
                "• Disabled: Lossy compression with adjustable quality\n"
                "When enabled, quality slider is disabled"
            )
        )
        grid.addWidget(lossless, 0, 0, 1, 2)

        grid.addWidget(QLabel(self.tr(Labels.QUALITY_0_100)), 1, 0)
        quality = QSpinBox()
        quality.setRange(0, 100)
        quality.setValue(100)
        quality.setToolTip(
            self.tr(
                "AVIF quality (0-100):\n"
                "• 0: Lowest quality, smallest file\n"
                "• 100: Highest quality, largest file\n"
                "Only used in lossy mode"
            )
        )
        grid.addWidget(quality, 1, 1)

        grid.addWidget(QLabel(self.tr(Labels.SPEED_0_10)), 2, 0)
        speed = QSpinBox()
        speed.setRange(0, 10)
        speed.setValue(5)
        speed.setToolTip(
            self.tr(
                "AVIF encoding speed (0-10):\n"
                "• 0: Slowest encoding, best compression\n"
                "• 5: Balanced speed/compression\n"
                "• 10: Fastest encoding, larger file\n"
                "Higher values encode faster but produce larger files.\n"
                "AVIF may take much longer to encode than other formats."
            )
        )
        grid.addWidget(speed, 2, 1)

        lossless.toggled.connect(
            lambda checked: self.on_avif_lossless_changed(checked, quality)
        )

        self.compression_widgets["AVIF"] = {
            "lossless": lossless,
            "quality": quality,
            "speed": speed,
        }

        layout.addWidget(group)

    def create_tiff_settings(self, layout):
        """Add TIFF compression controls to the layout.

        Args:
            layout: Parent QVBoxLayout for the settings group.
        """
        group = QGroupBox(self.tr("TIFF Compression Settings"))
        grid = QGridLayout(group)

        grid.addWidget(QLabel(self.tr(Labels.COMPRESSION_TYPE)), 0, 0)
        compression_type = QComboBox()
        compression_type.addItems(["none", "lzw", "zip", "jpeg"])
        compression_type.setCurrentText("lzw")
        compression_type.setToolTip(
            self.tr(
                "TIFF compression type:\n"
                "• None: No compression (largest files, fastest)\n"
                "• LZW: Lossless compression (good for graphics)\n"
                "• ZIP: Lossless compression (good for photos)\n"
                "• JPEG: Lossy compression (smallest files, adjustable quality)"
            )
        )
        grid.addWidget(compression_type, 0, 1)

        grid.addWidget(QLabel(self.tr(Labels.QUALITY_0_100)), 1, 0)
        quality = QSpinBox()
        quality.setRange(0, 100)
        quality.setValue(100)
        quality.setToolTip(
            self.tr(
                "TIFF JPEG quality (0-100):\n"
                "Only used when compression type is JPEG\n"
                "• 100: Highest quality, largest file"
            )
        )
        grid.addWidget(quality, 1, 1)

        optimize = QCheckBox(self.tr(CheckBoxLabels.OPTIMIZE_TIFF))
        optimize.setToolTip(
            self.tr(
                "TIFF optimize:\n"
                "• Enabled: Use additional optimization techniques\n"
                "Results in better compression but slower processing\n"
                "Not available when compression type is 'None'"
            )
        )
        grid.addWidget(optimize, 2, 0, 1, 2)

        compression_type.currentTextChanged.connect(
            lambda text: self.on_tiff_compression_type_changed(text, quality, optimize)
        )

        self.compression_widgets["TIFF"] = {
            "compression_type": compression_type,
            "quality": quality,
            "optimize": optimize,
        }

        layout.addWidget(group)

    def on_png_optimize_changed(self, checked, compress_level_widget):
        """Toggle compression level based on optimize checkbox.

        Args:
            checked: True if optimize is enabled.
            compress_level_widget: QSpinBox for compression level.
        """
        if checked:
            compress_level_widget.setValue(9)
            compress_level_widget.setEnabled(False)
        else:
            compress_level_widget.setEnabled(True)

    def on_webp_lossless_changed(self, checked, quality_widget, alpha_quality_widget):
        """Enable or disable quality controls based on lossless mode.

        Args:
            checked: True if lossless mode is enabled.
            quality_widget: QSpinBox for image quality.
            alpha_quality_widget: QSpinBox for alpha channel quality.
        """
        quality_widget.setEnabled(not checked)
        alpha_quality_widget.setEnabled(not checked)

    def on_avif_lossless_changed(self, checked, quality_widget):
        """Enable or disable quality control based on lossless mode.

        Args:
            checked: True if lossless mode is enabled.
            quality_widget: QSpinBox for image quality.
        """
        quality_widget.setEnabled(not checked)

    def on_tiff_compression_type_changed(
        self, compression_type, quality_widget, optimize_widget
    ):
        """Enable or disable controls based on the selected compression type.

        Args:
            compression_type: Selected compression algorithm name.
            quality_widget: QSpinBox for JPEG quality.
            optimize_widget: QCheckBox for optimization toggle.
        """
        if compression_type == "none":
            quality_widget.setEnabled(False)
            optimize_widget.setEnabled(False)
        elif compression_type == "jpeg":
            quality_widget.setEnabled(True)
            optimize_widget.setEnabled(True)
        else:
            quality_widget.setEnabled(False)
            optimize_widget.setEnabled(True)

    def load_current_values(self):
        """Populate widgets from SettingsManager and AppConfig defaults."""
        if not self.settings_manager or not self.app_config:
            return

        global_settings = self.settings_manager.global_settings
        compression_defaults = self.app_config.get_format_compression_settings(
            self.current_format.lower()
        )

        if self.current_format == "PNG":
            self.load_png_values(global_settings, compression_defaults)
        elif self.current_format == "WEBP":
            self.load_webp_values(global_settings, compression_defaults)
        elif self.current_format == "AVIF":
            self.load_avif_values(global_settings, compression_defaults)
        elif self.current_format == "TIFF":
            self.load_tiff_values(global_settings, compression_defaults)

        self.store_original_values()

    def load_png_values(self, global_settings, defaults):
        """Apply PNG settings to the widgets.

        Args:
            global_settings: Dictionary of user-saved settings.
            defaults: Dictionary of AppConfig default values.
        """
        if "PNG" not in self.compression_widgets:
            return

        widgets = self.compression_widgets["PNG"]

        compress_level = global_settings.get(
            "png_compress_level", defaults.get("png_compress_level", 9)
        )
        optimize = global_settings.get(
            "png_optimize", defaults.get("png_optimize", True)
        )

        widgets["compress_level"].setValue(compress_level)
        widgets["optimize"].setChecked(optimize)

        self.on_png_optimize_changed(optimize, widgets["compress_level"])

    def load_webp_values(self, global_settings, defaults):
        """Apply WebP settings to the widgets.

        Args:
            global_settings: Dictionary of user-saved settings.
            defaults: Dictionary of AppConfig default values.
        """
        if "WEBP" not in self.compression_widgets:
            return

        widgets = self.compression_widgets["WEBP"]

        lossless = global_settings.get(
            "webp_lossless", defaults.get("webp_lossless", True)
        )
        quality = global_settings.get("webp_quality", defaults.get("webp_quality", 100))
        method = global_settings.get("webp_method", defaults.get("webp_method", 6))
        alpha_quality = global_settings.get(
            "webp_alpha_quality", defaults.get("webp_alpha_quality", 100)
        )
        exact = global_settings.get("webp_exact", defaults.get("webp_exact", True))

        widgets["lossless"].setChecked(lossless)
        widgets["quality"].setValue(quality)
        widgets["method"].setValue(method)
        widgets["alpha_quality"].setValue(alpha_quality)
        widgets["exact"].setChecked(exact)

        self.on_webp_lossless_changed(
            lossless, widgets["quality"], widgets["alpha_quality"]
        )

    def load_avif_values(self, global_settings, defaults):
        """Apply AVIF settings to the widgets.

        Args:
            global_settings: Dictionary of user-saved settings.
            defaults: Dictionary of AppConfig default values.
        """
        if "AVIF" not in self.compression_widgets:
            return

        widgets = self.compression_widgets["AVIF"]

        lossless = global_settings.get(
            "avif_lossless", defaults.get("avif_lossless", True)
        )
        quality = global_settings.get("avif_quality", defaults.get("avif_quality", 100))
        speed = global_settings.get("avif_speed", defaults.get("avif_speed", 5))

        widgets["lossless"].setChecked(lossless)
        widgets["quality"].setValue(quality)
        widgets["speed"].setValue(speed)

        self.on_avif_lossless_changed(lossless, widgets["quality"])

    def load_tiff_values(self, global_settings, defaults):
        """Apply TIFF settings to the widgets.

        Args:
            global_settings: Dictionary of user-saved settings.
            defaults: Dictionary of AppConfig default values.
        """
        if "TIFF" not in self.compression_widgets:
            return

        widgets = self.compression_widgets["TIFF"]

        compression_type = global_settings.get(
            "tiff_compression_type", defaults.get("tiff_compression_type", "lzw")
        )
        quality = global_settings.get("tiff_quality", defaults.get("tiff_quality", 100))
        optimize = global_settings.get(
            "tiff_optimize", defaults.get("tiff_optimize", True)
        )

        widgets["compression_type"].setCurrentText(compression_type)
        widgets["quality"].setValue(quality)
        widgets["optimize"].setChecked(optimize)

        self.on_tiff_compression_type_changed(
            compression_type, widgets["quality"], widgets["optimize"]
        )

    def store_original_values(self):
        """Snapshot current widget values into original_values for comparison."""
        self.original_values = {}

        if self.current_format == "PNG" and "PNG" in self.compression_widgets:
            widgets = self.compression_widgets["PNG"]
            self.original_values = {
                "png_compress_level": widgets["compress_level"].value(),
                "png_optimize": widgets["optimize"].isChecked(),
            }
        elif self.current_format == "WEBP" and "WEBP" in self.compression_widgets:
            widgets = self.compression_widgets["WEBP"]
            self.original_values = {
                "webp_lossless": widgets["lossless"].isChecked(),
                "webp_quality": widgets["quality"].value(),
                "webp_method": widgets["method"].value(),
                "webp_alpha_quality": widgets["alpha_quality"].value(),
                "webp_exact": widgets["exact"].isChecked(),
            }
        elif self.current_format == "AVIF" and "AVIF" in self.compression_widgets:
            widgets = self.compression_widgets["AVIF"]
            self.original_values = {
                "avif_lossless": widgets["lossless"].isChecked(),
                "avif_quality": widgets["quality"].value(),
                "avif_speed": widgets["speed"].value(),
            }
        elif self.current_format == "TIFF" and "TIFF" in self.compression_widgets:
            widgets = self.compression_widgets["TIFF"]
            self.original_values = {
                "tiff_compression_type": widgets["compression_type"].currentText(),
                "tiff_quality": widgets["quality"].value(),
                "tiff_optimize": widgets["optimize"].isChecked(),
            }

    def get_current_values(self):
        """Read current widget values for the active format.

        Returns:
            Dictionary of setting keys to their current values.
        """
        if self.current_format == "PNG" and "PNG" in self.compression_widgets:
            widgets = self.compression_widgets["PNG"]
            return {
                "png_compress_level": widgets["compress_level"].value(),
                "png_optimize": widgets["optimize"].isChecked(),
            }
        elif self.current_format == "WEBP" and "WEBP" in self.compression_widgets:
            widgets = self.compression_widgets["WEBP"]
            return {
                "webp_lossless": widgets["lossless"].isChecked(),
                "webp_quality": widgets["quality"].value(),
                "webp_method": widgets["method"].value(),
                "webp_alpha_quality": widgets["alpha_quality"].value(),
                "webp_exact": widgets["exact"].isChecked(),
            }
        elif self.current_format == "AVIF" and "AVIF" in self.compression_widgets:
            widgets = self.compression_widgets["AVIF"]
            return {
                "avif_lossless": widgets["lossless"].isChecked(),
                "avif_quality": widgets["quality"].value(),
                "avif_speed": widgets["speed"].value(),
            }
        elif self.current_format == "TIFF" and "TIFF" in self.compression_widgets:
            widgets = self.compression_widgets["TIFF"]
            return {
                "tiff_compression_type": widgets["compression_type"].currentText(),
                "tiff_quality": widgets["quality"].value(),
                "tiff_optimize": widgets["optimize"].isChecked(),
            }
        return {}

    def values_changed(self):
        """Check whether any setting differs from the original snapshot.

        Returns:
            True if any value has changed, False otherwise.
        """
        current_values = self.get_current_values()
        return current_values != self.original_values

    def accept_changes(self):
        """Save changed settings to SettingsManager and close the dialog."""
        if not self.settings_manager:
            self.accept()
            return

        if self.values_changed():
            current_values = self.get_current_values()
            self.settings_manager.set_global_settings(**current_values)

        self.accept()
