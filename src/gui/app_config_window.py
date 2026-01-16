#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Modal dialog for editing global application settings.

Provides tabbed access to system resource limits, extraction defaults,
image compression options, UI preferences, and update behavior.
"""

import platform
import multiprocessing
import subprocess
import psutil
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QWidget,
    QPushButton,
    QLineEdit,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QMessageBox,
    QTabWidget,
    QSpinBox,
    QDoubleSpinBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils.translation_manager import tr as translate
from utils.combo_options import (
    FRAME_SELECTION_OPTIONS,
    CROPPING_METHOD_OPTIONS,
    FILENAME_FORMAT_OPTIONS,
    populate_combobox,
)
from utils.duration_utils import (
    DURATION_NATIVE,
    duration_to_milliseconds,
    get_duration_display_meta,
    load_duration_display_value,
    resolve_native_duration_type,
)


class AppConfigWindow(QDialog):
    """Modal dialog for editing global application settings.

    Organizes settings into tabs for system resources, extraction defaults,
    compression options, UI preferences, and update behavior.

    Attributes:
        app_config: Persistent settings object exposing DEFAULTS and settings.
        max_cores: Number of physical CPU cores detected.
        max_threads: Number of logical CPU threads detected.
        max_memory_mb: Total system RAM in megabytes.
        cpu_model: Human-readable CPU model string.
        extraction_fields: Dict mapping setting keys to extraction controls.
        compression_fields: Dict mapping setting keys to compression controls.
    """

    tr = translate

    def __init__(self, parent, app_config):
        """Initialize the configuration dialog.

        Args:
            parent: Parent widget for modal behavior.
            app_config: Persistent settings object with DEFAULTS and settings.
        """
        super().__init__(parent)
        self.app_config = app_config
        self.setWindowTitle(self.tr("App Options"))
        self.setModal(True)
        self.resize(520, 750)

        self.get_system_info()

        self.init_variables()

        self.setup_ui()
        self.load_current_settings()

    def get_system_info(self):
        """Detect CPU model, thread count, and available RAM."""

        self.max_cores = multiprocessing.cpu_count()
        self.max_threads = None
        self.max_memory_mb = int(psutil.virtual_memory().total / (1024 * 1024))

        self.cpu_model = "Unknown CPU"
        try:
            if platform.system() == "Windows":
                self.cpu_model = (
                    subprocess.check_output("wmic cpu get Name", shell=True)
                    .decode(errors="ignore")
                    .split("\n")[1]
                    .strip()
                )
                self.max_threads = int(
                    subprocess.check_output(
                        "wmic cpu get NumberOfLogicalProcessors", shell=True
                    )
                    .decode(errors="ignore")
                    .split("\n")[1]
                    .strip()
                )
            elif platform.system() == "Linux":
                with open("/proc/cpuinfo") as f:
                    for line in f:
                        if "model name" in line:
                            self.cpu_model = line.split(":")[1].strip()
                            break
                self.max_threads = multiprocessing.cpu_count()
            elif platform.system() == "Darwin":
                self.cpu_model = (
                    subprocess.check_output(
                        ["sysctl", "-n", "machdep.cpu.brand_string"]
                    )
                    .decode(errors="ignore")
                    .strip()
                )
                self.max_threads = int(
                    subprocess.check_output(["sysctl", "-n", "hw.logicalcpu"])
                    .decode(errors="ignore")
                    .strip()
                )
        except Exception:
            pass

        if not self.max_threads:
            self.max_threads = self.max_cores

    def init_variables(self):
        """Initialize placeholder attributes for UI controls."""

        self.cpu_threads_edit = None
        self.memory_limit_edit = None
        self.check_updates_cb = None
        self.auto_update_cb = None
        self.remember_input_dir_cb = None
        self.remember_output_dir_cb = None
        self.filter_single_frame_spritemaps_cb = None
        self.use_native_file_dialog_cb = None
        self.merge_duplicates_cb = None
        self.duration_input_type_combo = None
        self.color_scheme_combo = None
        self.duration_label = None
        self.duration_spinbox = None
        self._duration_display_type = None
        self._duration_value_ms = 42
        self.extraction_fields = {}
        self.compression_fields = {}
        self.generator_fields = {}

    def setup_ui(self):
        """Build and configure all UI components for the dialog."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        tab_widget = QTabWidget()

        system_tab = self.create_system_tab()
        tab_widget.addTab(system_tab, "System Resources")

        interface_tab = self.create_interface_tab()
        tab_widget.addTab(interface_tab, "Interface")

        extraction_tab = self.create_extraction_tab()
        tab_widget.addTab(extraction_tab, "Extraction Defaults")

        generator_tab = self.create_generator_tab()
        tab_widget.addTab(generator_tab, "Generator Defaults")

        compression_tab = self.create_compression_tab()
        tab_widget.addTab(compression_tab, "Compression Defaults")

        update_tab = self.create_update_tab()
        tab_widget.addTab(update_tab, "Updates")

        main_layout.addWidget(tab_widget)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        reset_btn = QPushButton(self.tr("Reset to defaults"))
        reset_btn.clicked.connect(self.reset_to_defaults)
        reset_btn.setMinimumWidth(130)
        button_layout.addWidget(reset_btn)

        cancel_btn = QPushButton(self.tr("Cancel"))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumWidth(100)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton(self.tr("Save"))
        save_btn.clicked.connect(self.save_config)
        save_btn.setMinimumWidth(100)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        main_layout.addLayout(button_layout)

    def _wrap_in_scroll_area(self, content_widget: QWidget) -> QScrollArea:
        """Wrap a widget in a styled scroll area for consistent tab appearance.

        Args:
            content_widget: The widget containing the tab's content.

        Returns:
            QScrollArea with no frame and consistent styling.
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(content_widget)
        return scroll_area

    def _apply_color_scheme(self, scheme: str) -> None:
        """Apply the specified color scheme to the application immediately.

        Args:
            scheme: One of 'auto', 'light', or 'dark'.
        """
        app = QApplication.instance()
        if app is None:
            return
        style_hints = app.styleHints()
        if scheme == "light":
            style_hints.setColorScheme(Qt.ColorScheme.Light)
        elif scheme == "dark":
            style_hints.setColorScheme(Qt.ColorScheme.Dark)
        else:
            style_hints.setColorScheme(Qt.ColorScheme.Unknown)

    def create_system_tab(self):
        """Build the system resources tab with CPU and memory controls.

        Returns:
            QWidget containing resource limit widgets.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        sys_group = QGroupBox("Your Computer")
        sys_layout = QVBoxLayout(sys_group)

        cpu_label = QLabel(
            self.tr("CPU: {cpu} (Threads: {threads})").format(
                cpu=self.cpu_model, threads=self.max_threads
            )
        )
        cpu_label.setFont(QFont("Arial", 9))
        sys_layout.addWidget(cpu_label)

        ram_label = QLabel(
            self.tr("RAM: {memory:,} MB").format(memory=self.max_memory_mb)
        )
        ram_label.setFont(QFont("Arial", 9))
        sys_layout.addWidget(ram_label)

        layout.addWidget(sys_group)

        resource_group = QGroupBox("App Resource Limits")
        resource_layout = QGridLayout(resource_group)

        cpu_threads_tooltip = self.tr(
            "Number of worker threads for parallel processing.\n\n"
            "More threads is not always faster—each worker holds\n"
            "sprite data in memory, so you need adequate RAM.\n\n"
            "Rough estimates (actual usage varies by spritesheet sizes):\n"
            "•  4,096 MB RAM → up to 2 threads\n"
            "•  8,192 MB RAM → up to 4 threads\n"
            "• 16,384 MB RAM → up to 8 threads\n"
            "• 32,768 MB RAM → up to 16 threads\n\n"
            "Using more threads with insufficient memory (e.g. 16\n"
            "threads on 8,192 MB) will cause most threads to sit idle\n"
            "waiting for memory to free up."
        )

        cpu_label = QLabel(
            self.tr("CPU threads to use (max: {max_threads}):").format(
                max_threads=self.max_threads
            )
        )
        cpu_label.setToolTip(cpu_threads_tooltip)
        resource_layout.addWidget(cpu_label, 0, 0)

        self.cpu_threads_edit = QSpinBox()
        self.cpu_threads_edit.setRange(1, self.max_threads)
        self.cpu_threads_edit.setToolTip(cpu_threads_tooltip)
        resource_layout.addWidget(self.cpu_threads_edit, 0, 1)

        mem_label = QLabel(
            self.tr("Memory limit (MB, max: {max_memory}):").format(
                max_memory=self.max_memory_mb
            )
        )
        memory_limit_tooltip = self.tr(
            "Memory threshold for worker threads.\n\n"
            "When the app's memory usage exceeds this limit, new\n"
            "worker threads will wait before starting their next file.\n"
            "Existing work is not interrupted.\n\n"
            "Set to 0 to disable memory-based throttling (Not recommended, may make app unstable)."
        )

        mem_label.setToolTip(memory_limit_tooltip)
        resource_layout.addWidget(mem_label, 1, 0)

        self.memory_limit_edit = QSpinBox()
        self.memory_limit_edit.setRange(0, self.max_memory_mb)
        self.memory_limit_edit.setSuffix(" MB")
        self.memory_limit_edit.setToolTip(memory_limit_tooltip)
        resource_layout.addWidget(self.memory_limit_edit, 1, 1)

        layout.addWidget(resource_group)
        layout.addStretch()

        return self._wrap_in_scroll_area(widget)

    def create_extraction_tab(self):
        """Build the extraction defaults tab with format and scale controls.

        Returns:
            QWidget containing extraction setting widgets.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Animation export group
        anim_group = QGroupBox("Animation Export Defaults")
        anim_layout = QGridLayout(anim_group)

        row = 0
        anim_layout.addWidget(QLabel(self.tr("Enable animation export:")), row, 0)
        anim_export_cb = QCheckBox()
        anim_export_cb.setChecked(True)
        self.extraction_fields["animation_export"] = anim_export_cb
        anim_layout.addWidget(anim_export_cb, row, 1)
        row += 1

        anim_layout.addWidget(QLabel(self.tr("Animation format")), row, 0)
        anim_format_combo = QComboBox()
        anim_format_combo.addItems(["GIF", "WebP", "APNG"])
        anim_format_combo.setCurrentText("GIF")
        anim_format_combo.currentTextChanged.connect(self._on_animation_format_changed)
        self.extraction_fields["animation_format"] = anim_format_combo
        anim_layout.addWidget(anim_format_combo, row, 1)
        row += 1

        duration_label = QLabel(self.tr("Duration"))
        self.duration_label = duration_label
        anim_layout.addWidget(duration_label, row, 0)
        duration_spinbox = QSpinBox()
        duration_spinbox.setRange(1, 10000)
        duration_spinbox.setValue(42)
        self.duration_spinbox = duration_spinbox
        self.extraction_fields["duration"] = duration_spinbox
        anim_layout.addWidget(duration_spinbox, row, 1)
        self._update_duration_controls(duration_ms=42)
        duration_spinbox.valueChanged.connect(self._on_duration_spinbox_changed)
        row += 1

        anim_layout.addWidget(QLabel(self.tr("Loop delay")), row, 0)
        delay_spinbox = QSpinBox()
        delay_spinbox.setRange(0, 99999)
        delay_spinbox.setValue(250)
        self.extraction_fields["delay"] = delay_spinbox
        anim_layout.addWidget(delay_spinbox, row, 1)
        row += 1

        anim_layout.addWidget(QLabel(self.tr("Minimum period")), row, 0)
        period_spinbox = QSpinBox()
        period_spinbox.setRange(0, 99999)
        period_spinbox.setValue(0)
        self.extraction_fields["period"] = period_spinbox
        anim_layout.addWidget(period_spinbox, row, 1)
        row += 1

        anim_layout.addWidget(QLabel(self.tr("Scale")), row, 0)
        scale_spinbox = QDoubleSpinBox()
        scale_spinbox.setRange(0.01, 100.0)
        scale_spinbox.setDecimals(2)
        scale_spinbox.setSingleStep(0.01)
        scale_spinbox.setValue(1.0)
        scale_spinbox.setSuffix(" x")
        self.extraction_fields["scale"] = scale_spinbox
        anim_layout.addWidget(scale_spinbox, row, 1)
        row += 1

        anim_layout.addWidget(QLabel(self.tr("Alpha threshold")), row, 0)
        threshold_spinbox = QSpinBox()
        threshold_spinbox.setRange(0, 100)
        threshold_spinbox.setSingleStep(1)
        threshold_spinbox.setValue(50)
        threshold_spinbox.setSuffix(" %")
        threshold_spinbox.setToolTip(
            self.tr(
                "Alpha threshold for GIF transparency (0-100%):\n"
                "• 0%: All pixels visible\n"
                "• 50%: Default, balanced transparency\n"
                "• 100%: Only fully opaque pixels visible"
            )
        )
        self.extraction_fields["threshold"] = threshold_spinbox
        anim_layout.addWidget(threshold_spinbox, row, 1)
        row += 1

        anim_layout.addWidget(QLabel(self.tr("Variable delay:")), row, 0)
        variable_delay_cb = QCheckBox()
        variable_delay_cb.setChecked(False)
        self.extraction_fields["variable_delay"] = variable_delay_cb
        anim_layout.addWidget(variable_delay_cb, row, 1)
        row += 1

        layout.addWidget(anim_group)

        # Frame export group
        frame_group = QGroupBox("Frame Export Defaults")
        frame_layout = QGridLayout(frame_group)

        row = 0
        frame_layout.addWidget(QLabel(self.tr("Enable frame export:")), row, 0)
        frame_export_cb = QCheckBox()
        frame_export_cb.setChecked(True)
        self.extraction_fields["frame_export"] = frame_export_cb
        frame_layout.addWidget(frame_export_cb, row, 1)
        row += 1

        frame_layout.addWidget(QLabel(self.tr("Frame format")), row, 0)
        frame_format_combo = QComboBox()
        frame_format_combo.addItems(
            ["AVIF", "BMP", "DDS", "PNG", "TGA", "TIFF", "WebP"]
        )
        frame_format_combo.setCurrentText("PNG")
        self.extraction_fields["frame_format"] = frame_format_combo
        frame_layout.addWidget(frame_format_combo, row, 1)
        row += 1

        frame_layout.addWidget(QLabel(self.tr("Frame scale")), row, 0)
        frame_scale_spinbox = QDoubleSpinBox()
        frame_scale_spinbox.setRange(0.01, 100.0)
        frame_scale_spinbox.setDecimals(2)
        frame_scale_spinbox.setSingleStep(0.01)
        frame_scale_spinbox.setValue(1.0)
        frame_scale_spinbox.setSuffix(" x")
        self.extraction_fields["frame_scale"] = frame_scale_spinbox
        frame_layout.addWidget(frame_scale_spinbox, row, 1)
        row += 1

        frame_layout.addWidget(QLabel(self.tr("Frame selection")), row, 0)
        frame_selection_combo = QComboBox()
        options_without_custom = tuple(
            opt for opt in FRAME_SELECTION_OPTIONS if opt.internal != "custom"
        )
        populate_combobox(frame_selection_combo, options_without_custom, self.tr)
        frame_selection_combo.setCurrentIndex(0)
        frame_selection_combo.setToolTip(
            self.tr(
                "Which frames to export:\n"
                "• All: Export every frame\n"
                "• No duplicates: Export unique frames only (skip repeated frames)\n"
                "• First: Export only the first frame\n"
                "• Last: Export only the last frame\n"
                "• First, Last: Export first and last frames"
            )
        )
        self.extraction_fields["frame_selection"] = frame_selection_combo
        frame_layout.addWidget(frame_selection_combo, row, 1)

        layout.addWidget(frame_group)

        # General export settings group
        general_group = QGroupBox("General Export Settings")
        general_layout = QGridLayout(general_group)

        row = 0
        general_layout.addWidget(QLabel(self.tr("Cropping method")), row, 0)
        crop_combo = QComboBox()
        populate_combobox(crop_combo, CROPPING_METHOD_OPTIONS, self.tr)
        crop_combo.setCurrentIndex(1)  # Default to "Animation based"
        crop_combo.setToolTip(
            self.tr(
                "How cropping should be done:\n"
                "• None: No cropping, keep original sprite size\n"
                "• Animation based: Crop to fit all frames in an animation\n"
                "• Frame based: Crop each frame individually (frames only)"
            )
        )
        self.extraction_fields["crop_option"] = crop_combo
        general_layout.addWidget(crop_combo, row, 1)
        row += 1

        general_layout.addWidget(QLabel(self.tr("Resampling method")), row, 0)
        from utils.resampling import (
            RESAMPLING_DISPLAY_NAMES,
            get_resampling_tooltip,
        )

        resampling_combo = QComboBox()
        resampling_combo.addItems(RESAMPLING_DISPLAY_NAMES)
        resampling_combo.setCurrentText("Nearest")
        resampling_combo.setToolTip(
            "Resampling method for image scaling:\n\n"
            + "\n\n".join(
                f"• {name}: {get_resampling_tooltip(name).split(chr(10))[0]}"
                for name in RESAMPLING_DISPLAY_NAMES
            )
        )
        self.extraction_fields["resampling_method"] = resampling_combo
        general_layout.addWidget(resampling_combo, row, 1)
        row += 1

        general_layout.addWidget(QLabel(self.tr("Filename format")), row, 0)
        from utils.version import APP_NAME

        filename_format_combo = QComboBox()
        populate_combobox(filename_format_combo, FILENAME_FORMAT_OPTIONS, self.tr)
        filename_format_combo.setCurrentIndex(0)
        filename_format_combo.setToolTip(
            self.tr(
                "How output filenames are formatted:\n"
                "• Standardized: Uses {app_name} standardized naming\n"
                "• No spaces: Replace spaces with underscores\n"
                "• No special characters: Remove special chars"
            ).format(app_name=APP_NAME)
        )
        self.extraction_fields["filename_format"] = filename_format_combo
        general_layout.addWidget(filename_format_combo, row, 1)
        row += 1

        general_layout.addWidget(QLabel(self.tr("Filename prefix")), row, 0)
        prefix_entry = QLineEdit()
        prefix_entry.setPlaceholderText(self.tr("Optional prefix"))
        self.extraction_fields["filename_prefix"] = prefix_entry
        general_layout.addWidget(prefix_entry, row, 1)
        row += 1

        general_layout.addWidget(QLabel(self.tr("Filename suffix")), row, 0)
        suffix_entry = QLineEdit()
        suffix_entry.setPlaceholderText(self.tr("Optional suffix"))
        self.extraction_fields["filename_suffix"] = suffix_entry
        general_layout.addWidget(suffix_entry, row, 1)

        layout.addWidget(general_group)
        layout.addStretch()

        return self._wrap_in_scroll_area(widget)

    def _get_animation_format(self) -> str:
        """Return the currently selected animation format in uppercase.

        Falls back to the persisted default if no combobox selection exists.
        """
        control = self.extraction_fields.get("animation_format")
        if isinstance(control, QComboBox):
            current_text = control.currentText()
            if current_text:
                return current_text.upper()
        defaults = self.app_config.settings.get("extraction_defaults", {})
        return str(defaults.get("animation_format", "GIF")).upper()

    def _get_interface_duration_type(self) -> str:
        """Return the user's preferred duration input type.

        Reads from the combobox if available, otherwise falls back to
        persisted interface settings. Defaults to ``"fps"``.
        """
        if self.duration_input_type_combo:
            current_type = self.duration_input_type_combo.currentData()
            if current_type:
                return current_type
        interface_defaults = self.app_config.settings.get("interface", {})
        return interface_defaults.get("duration_input_type", "fps")

    def _resolve_duration_type(self, animation_format: str) -> str:
        """Resolve 'native' to the format-specific duration type.

        Args:
            animation_format: Current animation format (GIF, WebP, APNG).

        Returns:
            The resolved duration type (e.g., centiseconds for GIF).
        """
        duration_type = self._get_interface_duration_type()
        if duration_type == DURATION_NATIVE:
            return resolve_native_duration_type(animation_format)
        return duration_type

    def _get_duration_spinbox_value_ms(self) -> int:
        """Return the cached duration value in milliseconds."""

        return max(1, int(getattr(self, "_duration_value_ms", 42)))

    def _update_duration_controls(
        self,
        duration_ms: int | None = None,
        stored_display_value: int | None = None,
        stored_display_type: str | None = None,
    ) -> None:
        """Refresh the duration spinbox label, range, and value.

        Converts the canonical millisecond value to the current display
        unit and updates the spinbox without triggering change signals.
        When stored display values are provided and match the current
        display type, uses them directly to avoid FPS precision loss.

        Args:
            duration_ms: Authoritative duration in milliseconds. When
                ``None``, uses the cached ``_duration_value_ms``.
            stored_display_value: Previously stored display value for
                lossless FPS round-trips.
            stored_display_type: Type of the stored display value.
        """
        if not self.duration_spinbox or not self.duration_label:
            return

        anim_format = self._get_animation_format()
        duration_type = self._get_interface_duration_type()
        display_meta = get_duration_display_meta(duration_type, anim_format)

        if duration_ms is None:
            duration_ms = self._get_duration_spinbox_value_ms()
        duration_ms = max(1, int(duration_ms))
        self._duration_value_ms = duration_ms

        label_text = self.tr(display_meta.label)
        if not label_text.endswith(":"):
            label_text = f"{label_text}:"
        self.duration_label.setText(label_text)

        tooltip = self.tr(display_meta.tooltip)
        self.duration_label.setToolTip(tooltip)
        self.duration_spinbox.setToolTip(tooltip)

        self.duration_spinbox.blockSignals(True)
        self.duration_spinbox.setRange(display_meta.min_value, display_meta.max_value)
        self.duration_spinbox.setSuffix(self.tr(display_meta.suffix))

        display_value = load_duration_display_value(
            duration_ms,
            stored_display_value,
            stored_display_type,
            display_meta.resolved_type,
            anim_format,
        )
        clamped_value = max(
            display_meta.min_value,
            min(display_value, display_meta.max_value),
        )
        self.duration_spinbox.setValue(clamped_value)
        self.duration_spinbox.blockSignals(False)

        self._duration_display_type = display_meta.resolved_type

    def _on_duration_spinbox_changed(self, value: int) -> None:
        """Cache the spinbox value converted to milliseconds.

        Called when the user edits the duration spinbox so that the
        canonical millisecond value stays in sync with the display.
        """
        if not self.duration_spinbox or not self._duration_display_type:
            return

        anim_format = self._get_animation_format()
        self._duration_value_ms = duration_to_milliseconds(
            max(1, value), self._duration_display_type, anim_format
        )

    def _on_duration_input_type_changed(self, _index: int = 0) -> None:
        """Slot invoked when the duration input type combobox changes."""

        self._update_duration_controls()

    def _on_animation_format_changed(self, _format: str = "") -> None:
        """Slot invoked when the animation format combobox changes."""

        self._update_duration_controls()

    def create_generator_tab(self):
        """Build the generator defaults tab with atlas packing settings.

        Returns:
            QWidget containing generator setting widgets.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Atlas settings group (match main Generate tab wording)
        algo_group = QGroupBox(self.tr("Atlas Settings"))
        algo_layout = QGridLayout(algo_group)

        row = 0
        algo_layout.addWidget(QLabel(self.tr("Packer method")), row, 0)
        algorithm_combo = QComboBox()
        algorithm_combo.addItems(
            [
                "Automatic (Best Fit)",
                "MaxRects",
                "Guillotine",
                "Shelf",
                "Shelf FFDH",
                "Skyline",
                "Simple Row",
            ]
        )
        algorithm_combo.setCurrentText("Automatic (Best Fit)")
        algorithm_combo.setToolTip(
            self.tr(
                "Packing algorithm to use for arranging sprites.\n"
                "• Automatic: Tries multiple algorithms and picks the best result\n"
                "• MaxRects: Good general-purpose algorithm\n"
                "• Guillotine: Fast, good for similar-sized sprites\n"
                "• Shelf: Simple and fast, less optimal packing\n"
                "• Shelf FFDH: Shelf with First Fit Decreasing Height (sorts by height)\n"
                "• Skyline: Good for sprites with similar heights\n"
                "• Simple Row: Basic left-to-right, row-by-row placement"
            )
        )
        self.generator_fields["algorithm"] = algorithm_combo
        algo_layout.addWidget(algorithm_combo, row, 1)
        row += 1

        algo_layout.addWidget(QLabel(self.tr("Heuristic")), row, 0)
        heuristic_combo = QComboBox()
        heuristic_combo.addItem("Auto (Best Result)", "auto")
        heuristic_combo.setToolTip(
            self.tr(
                "Algorithm-specific heuristic for sprite placement.\n"
                "Auto will try multiple heuristics and pick the best result."
            )
        )
        self.generator_fields["heuristic"] = heuristic_combo
        algo_layout.addWidget(heuristic_combo, row, 1)

        algorithm_combo.currentTextChanged.connect(self._update_heuristic_options)
        self._update_heuristic_options(algorithm_combo.currentText())

        layout.addWidget(algo_group)

        # Atlas size group
        size_group = QGroupBox(self.tr("Atlas Settings"))
        size_layout = QGridLayout(size_group)

        row = 0
        size_layout.addWidget(QLabel(self.tr("Max atlas size")), row, 0)
        max_size_combo = QComboBox()
        max_size_combo.addItems(["512", "1024", "2048", "4096", "8192", "16384"])
        max_size_combo.setCurrentText("4096")
        max_size_combo.setToolTip(
            self.tr(
                "Maximum width and height of the generated atlas.\n"
                "Larger atlases can fit more sprites but may have\n"
                "compatibility issues with older hardware."
            )
        )
        self.generator_fields["max_size"] = max_size_combo
        size_layout.addWidget(max_size_combo, row, 1)
        row += 1

        size_layout.addWidget(QLabel(self.tr("Padding:")), row, 0)
        padding_spinbox = QSpinBox()
        padding_spinbox.setRange(0, 32)
        padding_spinbox.setValue(2)
        padding_spinbox.setToolTip(
            self.tr(
                "Pixels of padding between sprites.\n"
                "Helps prevent texture bleeding during rendering."
            )
        )
        self.generator_fields["padding"] = padding_spinbox
        size_layout.addWidget(padding_spinbox, row, 1)
        row += 1

        power_of_two_cb = QCheckBox(self.tr('Use "Power of 2" sizes'))
        power_of_two_cb.setChecked(False)
        power_of_two_cb.setToolTip(
            self.tr(
                "Force atlas dimensions to be powers of 2 (e.g., 512, 1024, 2048).\n"
                "Required by some older graphics hardware and game engines."
            )
        )
        self.generator_fields["power_of_two"] = power_of_two_cb
        size_layout.addWidget(power_of_two_cb, row, 0, 1, 2)

        layout.addWidget(size_group)

        # Sprite optimization group
        optim_group = QGroupBox("Sprite Optimization")
        optim_layout = QVBoxLayout(optim_group)

        allow_rotation_cb = QCheckBox(self.tr("Allow rotation (90°)"))
        allow_rotation_cb.setChecked(False)
        allow_rotation_cb.setToolTip(
            self.tr(
                "Allow sprites to be rotated 90° for tighter packing.\n"
                "Only supported by some atlas formats."
            )
        )
        self.generator_fields["allow_rotation"] = allow_rotation_cb
        optim_layout.addWidget(allow_rotation_cb)

        allow_flip_cb = QCheckBox(self.tr("Allow flip X/Y (non-standard)"))
        allow_flip_cb.setChecked(False)
        allow_flip_cb.setToolTip(
            self.tr(
                "Detect horizontally/vertically flipped sprite variants.\n"
                "Stores only the canonical version with flip metadata,\n"
                "reducing atlas size for mirrored sprites.\n"
                "Only supported by Starling-XML format."
            )
        )
        self.generator_fields["allow_flip"] = allow_flip_cb
        optim_layout.addWidget(allow_flip_cb)

        trim_sprites_cb = QCheckBox(self.tr("Trim transparent edges"))
        trim_sprites_cb.setChecked(False)
        trim_sprites_cb.setToolTip(
            self.tr(
                "Trim transparent pixels from sprite edges for tighter packing.\n"
                "Offset metadata is stored so sprites render correctly.\n"
                "Not all atlas formats support trim metadata."
            )
        )
        self.generator_fields["trim_sprites"] = trim_sprites_cb
        optim_layout.addWidget(trim_sprites_cb)

        layout.addWidget(optim_group)

        # Output format group
        output_group = QGroupBox("Output Format")
        output_layout = QGridLayout(output_group)

        row = 0
        output_layout.addWidget(QLabel(self.tr("Atlas type")), row, 0)
        export_format_combo = QComboBox()
        export_format_combo.addItems(
            [
                "Sparrow/Starling XML",
                "JSON Hash",
                "JSON Array",
                "Aseprite JSON",
                "TexturePacker XML",
                "Spine Atlas",
                "Phaser 3 JSON",
                "CSS Spritesheet",
                "Plain Text",
                "Plist (Cocos2d)",
                "UIKit Plist",
                "Godot Atlas",
                "Egret2D JSON",
                "Paper2D (Unreal)",
                "Unity TexturePacker",
            ]
        )
        export_format_combo.setCurrentText("Sparrow/Starling XML")
        export_format_combo.setToolTip(
            self.tr("Metadata format for the generated atlas.")
        )
        self.generator_fields["export_format"] = export_format_combo
        output_layout.addWidget(export_format_combo, row, 1)
        row += 1

        output_layout.addWidget(QLabel(self.tr("Image format")), row, 0)
        image_format_combo = QComboBox()
        image_format_combo.addItems(["PNG", "JPEG", "WebP", "BMP", "TGA", "TIFF"])
        image_format_combo.setCurrentText("PNG")
        image_format_combo.setToolTip(self.tr("Image format for the atlas texture."))
        self.generator_fields["image_format"] = image_format_combo
        output_layout.addWidget(image_format_combo, row, 1)

        layout.addWidget(output_group)
        layout.addStretch()

        return self._wrap_in_scroll_area(widget)

    def create_compression_tab(self):
        """Build the compression settings tab with per-format controls.

        Returns:
            QWidget containing PNG, WebP, AVIF, and TIFF widgets.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        png_group = QGroupBox(self.tr("PNG Settings"))
        png_layout = QGridLayout(png_group)

        row = 0
        png_layout.addWidget(QLabel(self.tr("Compress Level (0-9):")), row, 0)
        png_compress_spinbox = QSpinBox()
        png_compress_spinbox.setRange(0, 9)
        png_compress_spinbox.setValue(9)
        png_compress_spinbox.setToolTip(
            "PNG compression level (0-9):\n"
            "• 0: No compression (fastest, largest file)\n"
            "• 1-3: Low compression\n"
            "• 4-6: Medium compression\n"
            "• 7-9: High compression (slowest, smallest file)\n"
            "This doesn't affect the quality of the image, only the file size"
        )
        self.compression_fields["png_compress_level"] = png_compress_spinbox
        png_layout.addWidget(png_compress_spinbox, row, 1)
        row += 1

        png_optimize_checkbox = QCheckBox(self.tr("Optimize PNG"))
        png_optimize_checkbox.setChecked(True)
        png_optimize_checkbox.setToolTip(
            "PNG optimize:\n"
            "• Enabled: Uses additional compression techniques for smaller files\n"
            "When enabled, compression level is automatically set to 9\n"
            "Results in slower processing but better compression\n\n"
            "This doesn't affect the quality of the image, only the file size"
        )
        self.compression_fields["png_optimize"] = png_optimize_checkbox
        png_layout.addWidget(png_optimize_checkbox, row, 0, 1, 2)

        layout.addWidget(png_group)

        webp_group = QGroupBox(self.tr("WebP Settings"))
        webp_layout = QGridLayout(webp_group)

        row = 0
        webp_lossless_checkbox = QCheckBox(self.tr("Lossless WebP"))
        webp_lossless_checkbox.setChecked(True)
        webp_lossless_checkbox.setToolTip(
            "WebP lossless mode:\n"
            "• Enabled: Perfect quality preservation, larger file size\n"
            "• Disabled: Lossy compression with adjustable quality\n"
            "When enabled, quality sliders are disabled"
        )
        self.compression_fields["webp_lossless"] = webp_lossless_checkbox
        webp_layout.addWidget(webp_lossless_checkbox, row, 0, 1, 2)
        row += 1

        webp_layout.addWidget(QLabel(self.tr("Quality (0-100):")), row, 0)
        webp_quality_spinbox = QSpinBox()
        webp_quality_spinbox.setRange(0, 100)
        webp_quality_spinbox.setValue(90)
        webp_quality_spinbox.setToolTip(
            "WebP quality (0-100):\n"
            "• 0: Lowest quality, smallest file\n"
            "• 75: Balanced quality/size\n"
            "• 100: Highest quality, largest file\n"
            "Only used in lossy mode"
        )
        self.compression_fields["webp_quality"] = webp_quality_spinbox
        webp_layout.addWidget(webp_quality_spinbox, row, 1)
        row += 1

        webp_layout.addWidget(QLabel(self.tr("Method (0-6):")), row, 0)
        webp_method_spinbox = QSpinBox()
        webp_method_spinbox.setRange(0, 6)
        webp_method_spinbox.setValue(3)
        webp_method_spinbox.setToolTip(
            "WebP compression method (0-6):\n"
            "• 0: Fastest encoding, larger file\n"
            "• 3: Balanced speed/compression\n"
            "• 6: Slowest encoding, best compression\n"
            "Higher values take more time but produce smaller files"
        )
        self.compression_fields["webp_method"] = webp_method_spinbox
        webp_layout.addWidget(webp_method_spinbox, row, 1)
        row += 1

        webp_layout.addWidget(QLabel(self.tr("Alpha Quality (0-100):")), row, 0)
        webp_alpha_quality_spinbox = QSpinBox()
        webp_alpha_quality_spinbox.setRange(0, 100)
        webp_alpha_quality_spinbox.setValue(90)
        webp_alpha_quality_spinbox.setToolTip(
            "WebP alpha channel quality (0-100):\n"
            "Controls transparency compression quality\n"
            "• 0: Maximum alpha compression\n"
            "• 100: Best alpha quality\n"
            "Only used in lossy mode"
        )
        self.compression_fields["webp_alpha_quality"] = webp_alpha_quality_spinbox
        webp_layout.addWidget(webp_alpha_quality_spinbox, row, 1)
        row += 1

        webp_exact_checkbox = QCheckBox(self.tr("Exact WebP"))
        webp_exact_checkbox.setChecked(True)
        webp_exact_checkbox.setToolTip(
            "WebP exact mode:\n"
            "• Enabled: Preserves RGB values in transparent areas\n"
            "• Disabled: Allows optimization of transparent pixels\n"
            "Enable for better quality when transparency matters"
        )
        self.compression_fields["webp_exact"] = webp_exact_checkbox
        webp_layout.addWidget(webp_exact_checkbox, row, 0, 1, 2)

        layout.addWidget(webp_group)

        avif_group = QGroupBox(self.tr("AVIF Settings"))
        avif_layout = QGridLayout(avif_group)

        row = 0
        avif_lossless_checkbox = QCheckBox(self.tr("Lossless AVIF"))
        avif_lossless_checkbox.setChecked(True)
        self.compression_fields["avif_lossless"] = avif_lossless_checkbox
        avif_layout.addWidget(avif_lossless_checkbox, row, 0, 1, 2)
        row += 1

        avif_layout.addWidget(QLabel(self.tr("Quality (0-100):")), row, 0)
        avif_quality_spinbox = QSpinBox()
        avif_quality_spinbox.setRange(0, 100)
        avif_quality_spinbox.setValue(90)
        avif_quality_spinbox.setToolTip(
            "AVIF quality (0-100):\n"
            "• 0-30: Low quality, very small files\n"
            "• 60-80: Good quality for most images\n"
            "• 85-95: High quality (recommended)\n"
            "• 95-100: Excellent quality, larger files"
        )
        self.compression_fields["avif_quality"] = avif_quality_spinbox
        avif_layout.addWidget(avif_quality_spinbox, row, 1)
        row += 1

        avif_layout.addWidget(QLabel(self.tr("Speed (0-10):")), row, 0)
        avif_speed_spinbox = QSpinBox()
        avif_speed_spinbox.setRange(0, 10)
        avif_speed_spinbox.setValue(5)
        avif_speed_spinbox.setToolTip(
            "AVIF encoding speed (0-10):\n"
            "• 0: Slowest encoding, best compression\n"
            "• 5: Balanced speed/compression (default)\n"
            "• 10: Fastest encoding, larger files\n"
            "Higher values encode faster but produce larger files"
        )
        self.compression_fields["avif_speed"] = avif_speed_spinbox
        avif_layout.addWidget(avif_speed_spinbox, row, 1)

        layout.addWidget(avif_group)

        tiff_group = QGroupBox(self.tr("TIFF Settings"))
        tiff_layout = QGridLayout(tiff_group)

        row = 0
        tiff_layout.addWidget(QLabel(self.tr("Compression Type:")), row, 0)
        tiff_compression_combobox = QComboBox()
        tiff_compression_combobox.addItems(["none", "lzw", "zip", "jpeg"])
        tiff_compression_combobox.setCurrentText("lzw")
        tiff_compression_combobox.setToolTip(
            "TIFF compression algorithm:\n"
            "• none: No compression, largest files\n"
            "• lzw: Lossless, good compression (recommended)\n"
            "• zip: Lossless, better compression\n"
            "• jpeg: Lossy compression, smallest files"
        )
        self.compression_fields["tiff_compression_type"] = tiff_compression_combobox
        tiff_layout.addWidget(tiff_compression_combobox, row, 1)
        row += 1

        tiff_layout.addWidget(QLabel(self.tr("Quality (0-100):")), row, 0)
        tiff_quality_spinbox = QSpinBox()
        tiff_quality_spinbox.setRange(0, 100)
        tiff_quality_spinbox.setValue(90)
        tiff_quality_spinbox.setToolTip(
            "TIFF quality (0-100):\n"
            "Only used with JPEG compression\n"
            "• 0-50: Low quality, small files\n"
            "• 75-90: Good quality\n"
            "• 95-100: Excellent quality"
        )
        self.compression_fields["tiff_quality"] = tiff_quality_spinbox
        tiff_layout.addWidget(tiff_quality_spinbox, row, 1)
        row += 1

        tiff_optimize_checkbox = QCheckBox(self.tr("Optimize TIFF"))
        tiff_optimize_checkbox.setChecked(True)
        tiff_optimize_checkbox.setToolTip(
            "TIFF optimization:\n"
            "• Enabled: Optimize file structure for smaller size\n"
            "• Disabled: Standard TIFF format\n"
            "Recommended to keep enabled"
        )
        self.compression_fields["tiff_optimize"] = tiff_optimize_checkbox
        self.compression_fields["tiff_optimize"] = tiff_optimize_checkbox
        tiff_layout.addWidget(tiff_optimize_checkbox, row, 0, 1, 2)

        layout.addWidget(tiff_group)
        layout.addStretch()

        return self._wrap_in_scroll_area(widget)

    def create_update_tab(self):
        """Build the update preferences tab with auto-update toggles.

        Returns:
            QWidget containing update preference widgets.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        group = QGroupBox(self.tr("Update Preferences"))
        group_layout = QVBoxLayout(group)

        self.check_updates_cb = QCheckBox(self.tr("Check for updates on startup"))
        self.check_updates_cb.stateChanged.connect(self.on_check_updates_change)
        group_layout.addWidget(self.check_updates_cb)

        self.auto_update_cb = QCheckBox(self.tr("Auto-download and install updates"))
        group_layout.addWidget(self.auto_update_cb)

        note_label = QLabel(
            self.tr(
                "Note: Auto-update will download and install updates automatically when available."
            )
        )
        note_label.setFont(QFont("Arial", 8, QFont.Weight.ExtraLight))
        note_label.setStyleSheet("QLabel { color: #666; }")
        note_label.setWordWrap(True)
        group_layout.addWidget(note_label)

        layout.addWidget(group)
        layout.addStretch()

        return self._wrap_in_scroll_area(widget)

    def on_check_updates_change(self, state):
        """Toggle auto-update checkbox based on the check-updates setting.

        Args:
            state: Qt check state from the checkbox.
        """
        self.auto_update_cb.setEnabled(state == Qt.CheckState.Checked.value)
        if state != Qt.CheckState.Checked.value:
            self.auto_update_cb.setChecked(False)

    def load_current_settings(self):
        """Populate all controls from the persisted configuration."""

        resource_limits = self.app_config.get("resource_limits", {})
        default_threads = (self.max_threads + 1) // 4

        cpu_default = resource_limits.get("cpu_cores", "auto")
        if cpu_default is None or cpu_default == "auto":
            cpu_default = default_threads
        self.cpu_threads_edit.setValue(int(cpu_default))

        default_mem = ((self.max_memory_mb // 4 + 9) // 10) * 10
        mem_default = resource_limits.get("memory_limit_mb", 0)
        if mem_default is None or mem_default == 0:
            mem_default = default_mem
        self.memory_limit_edit.setValue(int(mem_default))

        extraction_defaults = self.app_config.get("extraction_defaults", {})
        # Keys that use internal values with data stored in item data
        combo_data_keys = {"frame_selection", "crop_option", "filename_format"}
        for key, control in self.extraction_fields.items():
            value = extraction_defaults.get(key)
            if value is not None:
                if isinstance(control, QComboBox):
                    if key in combo_data_keys:
                        # Find index by item data (internal value)
                        idx = control.findData(str(value))
                        if idx >= 0:
                            control.setCurrentIndex(idx)
                    else:
                        control.setCurrentText(str(value))
                elif isinstance(control, QSpinBox):
                    # Threshold is stored as 0.0-1.0 but displayed as 0-100%
                    if key == "threshold":
                        control.setValue(int(float(value) * 100))
                    elif key == "duration":
                        stored_display_value = extraction_defaults.get(
                            "duration_display_value"
                        )
                        stored_display_type = extraction_defaults.get(
                            "duration_display_type"
                        )
                        self._update_duration_controls(
                            int(value), stored_display_value, stored_display_type
                        )
                    else:
                        control.setValue(int(value))
                elif isinstance(control, QDoubleSpinBox):
                    control.setValue(float(value))
                elif isinstance(control, QLineEdit):
                    control.setText(str(value))
                elif isinstance(control, QCheckBox):
                    control.setChecked(bool(value))

        compression_defaults = self.app_config.get("compression_defaults", {})
        for key, control in self.compression_fields.items():
            if "_" in key:
                format_name = key.split("_", 1)[0]
                setting_name = "_".join(key.split("_")[1:])
                format_defaults = compression_defaults.get(format_name, {})
                value = format_defaults.get(setting_name)
            else:
                value = compression_defaults.get(key)

            if value is not None:
                if isinstance(control, QCheckBox):
                    control.setChecked(bool(value))
                elif isinstance(control, QSpinBox):
                    control.setValue(int(value))
                elif isinstance(control, QComboBox):
                    control.setCurrentText(str(value))

        update_settings = self.app_config.get("update_settings", {})
        self.check_updates_cb.setChecked(
            update_settings.get("check_updates_on_startup", True)
        )
        self.auto_update_cb.setChecked(
            update_settings.get("auto_download_updates", False)
        )

        interface = self.app_config.get("interface", {})
        if self.remember_input_dir_cb:
            self.remember_input_dir_cb.setChecked(
                interface.get("remember_input_directory", True)
            )
        if self.remember_output_dir_cb:
            self.remember_output_dir_cb.setChecked(
                interface.get("remember_output_directory", True)
            )
        if self.filter_single_frame_spritemaps_cb:
            self.filter_single_frame_spritemaps_cb.setChecked(
                interface.get("filter_single_frame_spritemaps", False)
            )
        if self.use_native_file_dialog_cb:
            self.use_native_file_dialog_cb.setChecked(
                interface.get("use_native_file_dialog", False)
            )
        if self.merge_duplicates_cb:
            self.merge_duplicates_cb.setChecked(
                interface.get("merge_duplicate_frames", True)
            )
        if self.duration_input_type_combo:
            duration_type = interface.get("duration_input_type", "fps")
            index = self.duration_input_type_combo.findData(duration_type)
            if index >= 0:
                self.duration_input_type_combo.setCurrentIndex(index)
        if self.color_scheme_combo:
            color_scheme = interface.get("color_scheme", "auto")
            index = self.color_scheme_combo.findData(color_scheme)
            if index >= 0:
                self.color_scheme_combo.setCurrentIndex(index)

        # Load generator defaults
        generator_defaults = self.app_config.get("generator_defaults", {})
        self._load_generator_settings(generator_defaults)

        self.on_check_updates_change(self.check_updates_cb.checkState())

    def reset_to_defaults(self):
        """Prompt for confirmation and restore all controls to defaults."""

        reply = QMessageBox.question(
            self,
            "Reset to Defaults",
            "Are you sure you want to reset all settings to their default values?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            default_threads = (self.max_threads + 1) // 4
            self.cpu_threads_edit.setValue(default_threads)

            default_mem = ((self.max_memory_mb // 4 + 9) // 10) * 10
            self.memory_limit_edit.setValue(default_mem)

            defaults = self.app_config.DEFAULTS["extraction_defaults"]

            for key, control in self.extraction_fields.items():
                if key in defaults:
                    default_value = defaults[key]
                    if isinstance(control, QComboBox):
                        control.setCurrentText(str(default_value))
                    elif isinstance(control, QSpinBox):
                        # Threshold is stored as 0.0-1.0 but displayed as 0-100%
                        if key == "threshold":
                            control.setValue(int(float(default_value) * 100))
                        elif key == "duration":
                            self._update_duration_controls(int(default_value))
                        else:
                            control.setValue(int(default_value))
                    elif isinstance(control, QDoubleSpinBox):
                        control.setValue(float(default_value))
                    elif isinstance(control, QCheckBox):
                        control.setChecked(bool(default_value))
                    elif isinstance(control, QLineEdit):
                        control.setText(str(default_value))

            comp_defaults = self.app_config.DEFAULTS["compression_defaults"]

            for key, control in self.compression_fields.items():
                if "_" in key:
                    format_name = key.split("_", 1)[0]
                    setting_name = "_".join(key.split("_")[1:])

                    if (
                        format_name in comp_defaults
                        and setting_name in comp_defaults[format_name]
                    ):
                        default_value = comp_defaults[format_name][setting_name]

                        if isinstance(control, QCheckBox):
                            control.setChecked(bool(default_value))
                        elif isinstance(control, QSpinBox):
                            control.setValue(int(default_value))
                        elif isinstance(control, QComboBox):
                            control.setCurrentText(str(default_value))

            update_defaults = self.app_config.DEFAULTS["update_settings"]
            self.check_updates_cb.setChecked(
                update_defaults.get("check_updates_on_startup", True)
            )
            self.auto_update_cb.setChecked(
                update_defaults.get("auto_download_updates", False)
            )

            if self.merge_duplicates_cb:
                self.merge_duplicates_cb.setChecked(True)
            if self.duration_input_type_combo:
                default_type = self.app_config.DEFAULTS.get("interface", {}).get(
                    "duration_input_type", "fps"
                )
                index = self.duration_input_type_combo.findData(default_type)
                if index >= 0:
                    self.duration_input_type_combo.setCurrentIndex(index)
            if self.color_scheme_combo:
                default_scheme = self.app_config.DEFAULTS.get("interface", {}).get(
                    "color_scheme", "auto"
                )
                index = self.color_scheme_combo.findData(default_scheme)
                if index >= 0:
                    self.color_scheme_combo.setCurrentIndex(index)

            gen_defaults = self.app_config.DEFAULTS["generator_defaults"]
            self._load_generator_settings(gen_defaults)

    def save_config(self):
        """Validate inputs, update the config object, and persist to disk."""

        try:
            resource_limits = {}

            cpu_threads = self.cpu_threads_edit.value()
            if cpu_threads > self.max_threads:
                raise ValueError(
                    self.tr("CPU threads cannot exceed {max_threads}").format(
                        max_threads=self.max_threads
                    )
                )
            resource_limits["cpu_cores"] = cpu_threads

            memory_limit = self.memory_limit_edit.value()
            if memory_limit > self.max_memory_mb:
                raise ValueError(
                    self.tr("Memory limit cannot exceed {max_memory} MB").format(
                        max_memory=self.max_memory_mb
                    )
                )
            resource_limits["memory_limit_mb"] = memory_limit

            extraction_defaults = {}
            # Keys that use internal values stored in item data
            combo_data_keys = {"frame_selection", "crop_option", "filename_format"}
            for key, control in self.extraction_fields.items():
                if isinstance(control, QComboBox):
                    if key in combo_data_keys:
                        # Use item data (internal value) instead of display text
                        extraction_defaults[key] = control.currentData()
                    else:
                        extraction_defaults[key] = control.currentText()
                elif isinstance(control, QSpinBox):
                    # Threshold is displayed as 0-100% but stored as 0.0-1.0
                    if key == "threshold":
                        extraction_defaults[key] = control.value() / 100.0
                    elif key == "duration":
                        extraction_defaults[key] = self._get_duration_spinbox_value_ms()
                        extraction_defaults["duration_display_value"] = control.value()
                        extraction_defaults["duration_display_type"] = getattr(
                            self, "_duration_display_type", "fps"
                        )
                    else:
                        extraction_defaults[key] = control.value()
                elif isinstance(control, QDoubleSpinBox):
                    extraction_defaults[key] = control.value()
                elif isinstance(control, QCheckBox):
                    extraction_defaults[key] = control.isChecked()
                elif isinstance(control, QLineEdit):
                    # String fields like filename_prefix, filename_suffix
                    extraction_defaults[key] = control.text()

            compression_defaults = {"png": {}, "webp": {}, "avif": {}, "tiff": {}}

            for key, control in self.compression_fields.items():
                if "_" in key:
                    format_name = key.split("_", 1)[0]
                    setting_name = "_".join(key.split("_")[1:])

                    if format_name in compression_defaults:
                        if isinstance(control, QCheckBox):
                            compression_defaults[format_name][
                                setting_name
                            ] = control.isChecked()
                        elif isinstance(control, QSpinBox):
                            compression_defaults[format_name][
                                setting_name
                            ] = control.value()
                        elif isinstance(control, QComboBox):
                            compression_defaults[format_name][
                                setting_name
                            ] = control.currentText()

            update_settings = {
                "check_updates_on_startup": self.check_updates_cb.isChecked(),
                "auto_download_updates": self.auto_update_cb.isChecked(),
            }

            interface = self.app_config.settings.setdefault("interface", {})
            if self.remember_input_dir_cb:
                interface["remember_input_directory"] = (
                    self.remember_input_dir_cb.isChecked()
                )
            if self.remember_output_dir_cb:
                interface["remember_output_directory"] = (
                    self.remember_output_dir_cb.isChecked()
                )
            if self.filter_single_frame_spritemaps_cb:
                interface["filter_single_frame_spritemaps"] = (
                    self.filter_single_frame_spritemaps_cb.isChecked()
                )
            if self.use_native_file_dialog_cb:
                interface["use_native_file_dialog"] = (
                    self.use_native_file_dialog_cb.isChecked()
                )
            if self.merge_duplicates_cb:
                interface["merge_duplicate_frames"] = (
                    self.merge_duplicates_cb.isChecked()
                )
            if self.duration_input_type_combo:
                interface["duration_input_type"] = (
                    self.duration_input_type_combo.currentData()
                )
            if self.color_scheme_combo:
                interface["color_scheme"] = self.color_scheme_combo.currentData()

            # Save generator defaults
            generator_defaults = self._collect_generator_settings()

            self.app_config.settings["resource_limits"] = resource_limits
            self.app_config.settings["extraction_defaults"] = extraction_defaults
            self.app_config.settings["compression_defaults"] = compression_defaults
            self.app_config.settings["update_settings"] = update_settings
            self.app_config.settings["generator_defaults"] = generator_defaults
            self.app_config.settings["interface"] = interface

            self.app_config.save()

            if self.color_scheme_combo:
                self._apply_color_scheme(interface.get("color_scheme", "auto"))

            QMessageBox.information(
                self,
                self.tr("Settings Saved"),
                self.tr("Configuration has been saved successfully."),
            )
            self.accept()

        except ValueError as e:
            QMessageBox.critical(
                self,
                self.tr("Invalid Input"),
                self.tr("Error: {error}").format(error=str(e)),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr("Error"),
                self.tr("Failed to save configuration: {error}").format(error=str(e)),
            )

    @staticmethod
    def parse_value(key, val, expected_type):
        """Convert a raw config value to the specified type.

        Args:
            key: Setting key for error context.
            val: Raw value to convert.
            expected_type: One of 'int', 'float', 'bool', or 'str'.

        Returns:
            Converted value matching expected_type.

        Raises:
            ValueError: If conversion fails.
        """
        if expected_type == "int":
            return int(val)
        elif expected_type == "float":
            return float(val)
        elif expected_type == "bool":
            if isinstance(val, bool):
                return val
            return str(val).lower() in ("true", "1", "yes", "on")
        else:
            return str(val)

    def create_interface_tab(self):
        """Build the interface preferences tab with UI behavior settings.

        Returns:
            QWidget containing interface preference controls.
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Appearance group
        appearance_group = QGroupBox(self.tr("Appearance"))
        appearance_layout = QHBoxLayout(appearance_group)

        color_scheme_label = QLabel(self.tr("Color scheme:"))
        color_scheme_tooltip = self.tr(
            "Override the operating system's dark/light mode:\n\n"
            "• Auto: Follow system theme\n"
            "• Light: Always use light theme\n"
            "• Dark: Always use dark theme"
        )
        color_scheme_label.setToolTip(color_scheme_tooltip)
        appearance_layout.addWidget(color_scheme_label)

        self.color_scheme_combo = QComboBox()
        self.color_scheme_combo.addItem(self.tr("Auto (System)"), "auto")
        self.color_scheme_combo.addItem(self.tr("Light"), "light")
        self.color_scheme_combo.addItem(self.tr("Dark"), "dark")
        self.color_scheme_combo.setToolTip(color_scheme_tooltip)
        appearance_layout.addWidget(self.color_scheme_combo)
        appearance_layout.addStretch()

        layout.addWidget(appearance_group)

        dir_group = QGroupBox(self.tr("Directory Memory"))
        dir_layout = QVBoxLayout(dir_group)

        self.remember_input_dir_cb = QCheckBox(
            self.tr("Remember last used input directory")
        )
        self.remember_input_dir_cb.setToolTip(
            self.tr(
                "When enabled, the app will remember and restore the last used input directory on startup"
            )
        )
        dir_layout.addWidget(self.remember_input_dir_cb)

        self.remember_output_dir_cb = QCheckBox(
            self.tr("Remember last used output directory")
        )
        self.remember_output_dir_cb.setToolTip(
            self.tr(
                "When enabled, the app will remember and restore the last used output directory on startup"
            )
        )
        dir_layout.addWidget(self.remember_output_dir_cb)

        layout.addWidget(dir_group)

        # Spritemap settings group
        spritemap_group = QGroupBox(self.tr("Spritemap Settings"))
        spritemap_layout = QVBoxLayout(spritemap_group)

        self.filter_single_frame_spritemaps_cb = QCheckBox(
            self.tr("Hide single-frame spritemap animations")
        )
        self.filter_single_frame_spritemaps_cb.setToolTip(
            self.tr(
                "When enabled, spritemap animations with only one frame will be hidden from the animation list.\n"
                "Adobe Animate spritemaps often contain single-frame symbols for cut-ins and poses.\n"
                "Should not affect animations that use these single frame symbols."
            )
        )
        spritemap_layout.addWidget(self.filter_single_frame_spritemaps_cb)

        layout.addWidget(spritemap_group)

        file_dialog_group = QGroupBox(self.tr("File Picker"))
        file_dialog_layout = QVBoxLayout(file_dialog_group)

        self.use_native_file_dialog_cb = QCheckBox(
            self.tr("Use native file picker when available")
        )
        self.use_native_file_dialog_cb.setToolTip(
            self.tr(
                "Uses the OS-native file dialog instead of the Qt-styled picker.\n"
                "This only affects the Extract tab's manual file selection."
            )
        )
        file_dialog_layout.addWidget(self.use_native_file_dialog_cb)

        layout.addWidget(file_dialog_group)

        # Animation behavior group
        anim_behavior_group = QGroupBox(self.tr("Animation Behavior"))
        anim_behavior_layout = QVBoxLayout(anim_behavior_group)

        self.merge_duplicates_cb = QCheckBox(self.tr("Merge duplicate frames"))
        self.merge_duplicates_cb.setChecked(True)
        self.merge_duplicates_cb.setToolTip(
            self.tr(
                "When enabled, consecutive duplicate frames are merged into a\n"
                "single frame with combined duration. Disable if you want to\n"
                "keep all frames individually for manual timing adjustments."
            )
        )
        anim_behavior_layout.addWidget(self.merge_duplicates_cb)

        duration_layout = QHBoxLayout()
        duration_label = QLabel(self.tr("Duration input type:"))
        duration_tooltip = self.tr(
            "Choose how frame timing is entered in the UI:\n\n"
            "• Format Native: Uses each format's native unit:\n"
            "    - GIF: Centiseconds (10ms increments)\n"
            "    - APNG/WebP: Milliseconds\n"
            "• FPS: Traditional frames-per-second (converted to delays)\n"
            "• Deciseconds: 1/10th of a second\n"
            "• Centiseconds: 1/100th of a second\n"
            "• Milliseconds: 1/1000th of a second"
        )
        duration_label.setToolTip(duration_tooltip)
        duration_layout.addWidget(duration_label)

        self.duration_input_type_combo = QComboBox()
        self.duration_input_type_combo.addItem(self.tr("Format Native"), "native")
        self.duration_input_type_combo.addItem(
            self.tr("FPS (frames per second)"), "fps"
        )
        self.duration_input_type_combo.addItem(self.tr("Deciseconds"), "deciseconds")
        self.duration_input_type_combo.addItem(self.tr("Centiseconds"), "centiseconds")
        self.duration_input_type_combo.addItem(self.tr("Milliseconds"), "milliseconds")
        self.duration_input_type_combo.setToolTip(duration_tooltip)
        self.duration_input_type_combo.currentIndexChanged.connect(
            self._on_duration_input_type_changed
        )
        duration_layout.addWidget(self.duration_input_type_combo)
        duration_layout.addStretch()
        anim_behavior_layout.addLayout(duration_layout)

        layout.addWidget(anim_behavior_group)
        layout.addStretch()

        return self._wrap_in_scroll_area(widget)

    # Mapping from display names to internal format keys
    _EXPORT_FORMAT_MAP = {
        "Sparrow/Starling XML": "starling-xml",
        "JSON Hash": "json-hash",
        "JSON Array": "json-array",
        "Aseprite JSON": "aseprite",
        "TexturePacker XML": "texture-packer-xml",
        "Spine Atlas": "spine",
        "Phaser 3 JSON": "phaser3",
        "CSS Spritesheet": "css",
        "Plain Text": "txt",
        "Plist (Cocos2d)": "plist",
        "UIKit Plist": "uikit-plist",
        "Godot Atlas": "godot",
        "Egret2D JSON": "egret2d",
        "Paper2D (Unreal)": "paper2d",
        "Unity TexturePacker": "unity",
    }

    _EXPORT_FORMAT_REVERSE = {v: k for k, v in _EXPORT_FORMAT_MAP.items()}

    _ALGORITHM_MAP = {
        "Automatic (Best Fit)": "auto",
        "MaxRects": "maxrects",
        "Guillotine": "guillotine",
        "Shelf": "shelf",
        "Shelf FFDH": "shelf-ffdh",
        "Skyline": "skyline",
        "Simple Row": "simple",
    }

    _ALGORITHM_REVERSE = {v: k for k, v in _ALGORITHM_MAP.items()}

    # Format: list of (key, display_name) tuples
    _ALGORITHM_HEURISTICS = {
        "auto": [],
        "maxrects": [
            ("bssf", "Best Short Side Fit (BSSF)"),
            ("blsf", "Best Long Side Fit (BLSF)"),
            ("baf", "Best Area Fit (BAF)"),
            ("bl", "Bottom-Left (BL)"),
            ("cp", "Contact Point (CP)"),
        ],
        "guillotine": [
            ("bssf", "Best Short Side Fit (BSSF)"),
            ("blsf", "Best Long Side Fit (BLSF)"),
            ("baf", "Best Area Fit (BAF)"),
            ("waf", "Worst Area Fit (WAF)"),
        ],
        "shelf": [
            ("next_fit", "Next Fit"),
            ("first_fit", "First Fit"),
            ("best_width", "Best Width Fit"),
            ("best_height", "Best Height Fit"),
            ("worst_width", "Worst Width Fit"),
        ],
        "shelf-ffdh": [
            ("next_fit", "Next Fit"),
            ("first_fit", "First Fit"),
            ("best_width", "Best Width Fit"),
            ("best_height", "Best Height Fit"),
            ("worst_width", "Worst Width Fit"),
        ],
        "skyline": [
            ("bottom_left", "Bottom-Left (BL)"),
            ("min_waste", "Minimum Waste"),
            ("best_fit", "Best Fit"),
        ],
        "simple": [],
    }

    def _update_heuristic_options(self, algorithm_display_name: str = None):
        """Update heuristic combobox options based on selected algorithm.

        Args:
            algorithm_display_name: Display name of the selected algorithm.
                If None, reads from the algorithm combobox.
        """
        heuristic_combo = self.generator_fields.get("heuristic")
        algorithm_combo = self.generator_fields.get("algorithm")
        if not heuristic_combo or not algorithm_combo:
            return

        if algorithm_display_name is None:
            algorithm_display_name = algorithm_combo.currentText()

        algorithm_key = self._ALGORITHM_MAP.get(
            algorithm_display_name, algorithm_display_name.lower()
        )

        heuristic_combo.blockSignals(True)
        heuristic_combo.clear()

        heuristic_combo.addItem("Auto (Best Result)", "auto")

        heuristics = self._ALGORITHM_HEURISTICS.get(algorithm_key, [])
        for key, display_name in heuristics:
            heuristic_combo.addItem(display_name, key)

        heuristic_combo.setCurrentIndex(0)
        heuristic_combo.blockSignals(False)

    def _load_generator_settings(self, generator_defaults: dict):
        """Populate generator controls from persisted configuration.

        Args:
            generator_defaults: Dictionary of generator settings.
        """
        algorithm_value = generator_defaults.get("algorithm")
        if algorithm_value:
            algorithm_combo = self.generator_fields.get("algorithm")
            if algorithm_combo:
                display_name = self._ALGORITHM_REVERSE.get(
                    algorithm_value, algorithm_value
                )
                algorithm_combo.setCurrentText(display_name)

        for key, control in self.generator_fields.items():
            if key == "algorithm":
                continue

            value = generator_defaults.get(key)
            if value is None:
                continue

            if isinstance(control, QComboBox):
                if key == "heuristic":
                    index = control.findData(value)
                    if index >= 0:
                        control.setCurrentIndex(index)
                    else:
                        control.setCurrentIndex(0)
                elif key == "export_format":
                    display_name = self._EXPORT_FORMAT_REVERSE.get(value, value)
                    control.setCurrentText(display_name)
                elif key == "max_size":
                    control.setCurrentText(str(value))
                else:
                    control.setCurrentText(str(value))
            elif isinstance(control, QSpinBox):
                control.setValue(int(value))
            elif isinstance(control, QCheckBox):
                control.setChecked(bool(value))

    def _collect_generator_settings(self) -> dict:
        """Collect generator settings from UI controls.

        Returns:
            Dictionary of generator settings for persistence.
        """
        generator_defaults = {}

        for key, control in self.generator_fields.items():
            if isinstance(control, QComboBox):
                if key == "algorithm":
                    display_text = control.currentText()
                    generator_defaults[key] = self._ALGORITHM_MAP.get(
                        display_text, display_text.lower()
                    )
                elif key == "heuristic":
                    generator_defaults[key] = control.currentData() or "auto"
                elif key == "export_format":
                    display_text = control.currentText()
                    generator_defaults[key] = self._EXPORT_FORMAT_MAP.get(
                        display_text, display_text
                    )
                elif key == "max_size":
                    generator_defaults[key] = int(control.currentText())
                else:
                    generator_defaults[key] = control.currentText()
            elif isinstance(control, QSpinBox):
                generator_defaults[key] = control.value()
            elif isinstance(control, QCheckBox):
                generator_defaults[key] = control.isChecked()

        return generator_defaults
