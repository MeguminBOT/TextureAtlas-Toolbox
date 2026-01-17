#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Animation preview dialog for viewing and adjusting extracted animations.

Provides a real-time preview of GIF, WebP, and APNG animations with playback
controls, frame selection, and export settings. Runs frame loading in a
background thread to maintain UI responsiveness.
"""

import os
from typing import List

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QGroupBox,
    QCheckBox,
    QColorDialog,
    QSplitter,
    QComboBox,
    QLineEdit,
    QWidget,
    QMessageBox,
    QScrollArea,
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor

try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from utils.duration_utils import (
    convert_duration,
    duration_to_milliseconds,
    get_duration_display_meta,
    load_duration_display_value,
    milliseconds_to_duration,
)
from utils.combo_options import (
    CROPPING_METHOD_OPTIONS,
    populate_combobox,
    get_index_by_internal,
)
from utils.ui_constants import (
    Labels,
    GroupTitles,
    Placeholders,
    SpinBoxConfig,
    Tooltips,
    ButtonLabels,
    DialogTitles,
)
from utils.resampling import (
    RESAMPLING_DISPLAY_NAMES,
    get_resampling_index,
    get_resampling_name,
    DEFAULT_RESAMPLING_METHOD,
)

MAX_FRAMES_IN_MEMORY = 100
FRAME_CACHE_SIZE = 20


class AnimationProcessor(QThread):
    """Background thread for loading animation frames with optimized memory.

    Reads animation files frame-by-frame and emits signals as each frame
    is converted to a QPixmap. Supports early termination via ``stop()``.

    Signals:
        frame_processed(int, QPixmap): Emitted when a frame is ready.
        processing_complete(): Emitted when all frames are loaded.
        error_occurred(str): Emitted with an error message on failure.
        progress_updated(int, int): Emitted with current and total frame count.

    Attributes:
        frames: List of loaded QPixmap frames.
        frame_durations: Per-frame display durations in milliseconds.
    """

    frame_processed = Signal(int, QPixmap)
    processing_complete = Signal()
    error_occurred = Signal(str)
    progress_updated = Signal(int, int)

    def __init__(self, animation_path: str, settings: dict):
        """Initialize the animation processor.

        Args:
            animation_path: Path to the animation file (GIF, WebP, or APNG).
            settings: Animation settings dictionary (currently unused).
        """
        super().__init__()
        self.animation_path = animation_path
        self.settings = settings
        self.frames: List[QPixmap] = []
        self.frame_durations: List[int] = []
        self._stop_requested = False

    def stop(self):
        """Request to stop processing."""
        self._stop_requested = True

    def run(self):
        """Process animation frames in background with optimizations."""
        try:
            if not PIL_AVAILABLE:
                self.error_occurred.emit("PIL/Pillow not available")
                return

            with Image.open(self.animation_path) as img:
                frame_count = getattr(img, "n_frames", 1)

                self.frames = [QPixmap()] * frame_count
                self.frame_durations = [100] * frame_count

                for frame_idx in range(frame_count):
                    if self._stop_requested:
                        return

                    img.seek(frame_idx)

                    duration = getattr(img, "info", {}).get("duration", 100)
                    self.frame_durations[frame_idx] = duration

                    frame_copy = img.copy()
                    if frame_copy.mode != "RGBA":
                        frame_copy = frame_copy.convert("RGBA")

                    w, h = frame_copy.size
                    bytes_data = frame_copy.tobytes("raw", "RGBA")
                    qimg = QImage(bytes_data, w, h, QImage.Format.Format_RGBA8888)
                    pixmap = QPixmap.fromImage(qimg)

                    if hasattr(pixmap, "toImage"):
                        device_pixmap = QPixmap(pixmap.size())
                        device_pixmap.fill(Qt.GlobalColor.transparent)
                        painter = QPainter(device_pixmap)
                        painter.setCompositionMode(
                            QPainter.CompositionMode.CompositionMode_SourceOver
                        )
                        painter.drawPixmap(0, 0, pixmap)
                        painter.end()
                        pixmap = device_pixmap

                    self.frames[frame_idx] = pixmap
                    self.frame_processed.emit(frame_idx, pixmap)
                    self.progress_updated.emit(frame_idx + 1, frame_count)
                    self.msleep(1)

            if not self._stop_requested:
                self.processing_complete.emit()

        except Exception as e:
            self.error_occurred.emit(f"Failed to load animation: {str(e)}")


class FrameListWidget(QListWidget):
    """List widget for frame navigation with checkbox selection.

    Displays all animation frames with optional delay labels and checkboxes
    for including or excluding frames from playback and export.

    Signals:
        frame_selected(int): Emitted when a frame is clicked.
        frame_checked(int, bool): Emitted when a checkbox is toggled.
    """

    frame_selected = Signal(int)
    frame_checked = Signal(int, bool)

    def __init__(self):
        super().__init__()
        self.setMaximumWidth(140)
        self.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.currentItemChanged.connect(self._on_selection_changed)
        self.itemChanged.connect(self._on_item_changed)

    def set_frame_count(self, count: int, frame_durations: List[int] = None):
        """Populate the list with frame entries.

        Args:
            count: Number of frames to display.
            frame_durations: Optional per-frame delays in milliseconds.
        """
        self.clear()
        for i in range(count):
            if frame_durations and i < len(frame_durations):
                delay_ms = frame_durations[i]
                frame_text = f"Frame {i + 1} ({delay_ms}ms)"
            else:
                frame_text = f"Frame {i + 1}"

            item = QListWidgetItem(frame_text)
            item.setData(Qt.ItemDataRole.UserRole, i)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            self.addItem(item)

    def update_frame_delays(self, frame_durations: List[int], show_delays: bool = True):
        """Refresh delay labels on existing frame entries.

        Args:
            frame_durations: Per-frame delays in milliseconds.
            show_delays: Whether to display delays in the label text.
        """
        for i in range(self.count()):
            item = self.item(i)
            if item:
                if frame_durations and i < len(frame_durations):
                    delay_ms = frame_durations[i]
                    frame_text = f"Frame {i + 1} ({delay_ms}ms)"
                else:
                    frame_text = f"Frame {i + 1}"
                item.setText(frame_text)

    def select_frame(self, frame_index: int):
        """Highlight a frame in the list.

        Args:
            frame_index: Zero-based index of the frame to select.
        """
        if 0 <= frame_index < self.count():
            self.setCurrentRow(frame_index)

    def get_checked_frames(self):
        """Return indices of all checked frames.

        Returns:
            List of zero-based indices for frames whose checkbox is checked.
        """
        checked_frames = []
        for i in range(self.count()):
            item = self.item(i)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked_frames.append(i)
        return checked_frames

    def set_checked_frames(self, frame_indices):
        """Check only the specified frames, unchecking all others.

        Args:
            frame_indices: Iterable of zero-based frame indices to check.
        """
        for i in range(self.count()):
            item = self.item(i)
            if item:
                item.setCheckState(Qt.CheckState.Unchecked)

        for frame_index in frame_indices:
            if 0 <= frame_index < self.count():
                item = self.item(frame_index)
                if item:
                    item.setCheckState(Qt.CheckState.Checked)

    def _on_selection_changed(self, current, previous):
        """Emit frame_selected when the list selection changes.

        Args:
            current: Newly selected QListWidgetItem.
            previous: Previously selected QListWidgetItem.
        """
        if current:
            frame_index = current.data(Qt.ItemDataRole.UserRole)
            if frame_index is not None:
                self.frame_selected.emit(frame_index)

    def _on_item_changed(self, item):
        """Emit frame_checked when a checkbox state changes.

        Args:
            item: The QListWidgetItem whose checkbox was toggled.
        """
        frame_index = item.data(Qt.ItemDataRole.UserRole)
        if frame_index is not None:
            is_checked = item.checkState() == Qt.CheckState.Checked
            self.frame_checked.emit(frame_index, is_checked)


class AnimationDisplay(QScrollArea):
    """Scrollable widget for displaying animation frames with zoom support.

    Supports solid-color and checkered transparency backgrounds as well as
    Ctrl+wheel zoom. Caches scaled pixmaps to minimize redraw cost.

    Signals:
        scale_changed(float): Emitted when the zoom level changes.
    """

    scale_changed = Signal(float)

    def __init__(self):
        super().__init__()

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: transparent;")
        self.image_label.setScaledContents(False)

        self.setWidget(self.image_label)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumSize(600, 500)
        self.setStyleSheet("border: 1px solid gray; background-color: transparent;")

        self._background_color = QColor(127, 127, 127, 255)
        self._background_mode = "None"
        self._checkered_pattern = None
        self._current_pixmap = None
        self._scale_factor = 1.0
        self._original_size = None

        self._cached_scaled_pixmap = None
        self._cached_scale = None

        self.image_label.installEventFilter(self)

    def eventFilter(self, source, event):
        """Forward wheel events from the image label to this widget.

        Args:
            source: The watched QObject.
            event: The incoming QEvent.

        Returns:
            True if the event was handled, False otherwise.
        """
        if source == self.image_label and event.type() == event.Type.Wheel:
            return self.wheelEvent(event)
        return super().eventFilter(source, event)

    def wheelEvent(self, event):
        """Zoom the frame on Ctrl+scroll, scroll otherwise.

        Args:
            event: QWheelEvent containing scroll delta and modifiers.

        Returns:
            True if zooming was applied, otherwise the parent result.
        """
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            angle_delta = event.angleDelta().y()
            zoom_factor = 1.1 if angle_delta > 0 else 1.0 / 1.1
            new_scale = self._scale_factor * zoom_factor
            new_scale = max(0.1, min(5.0, new_scale))
            old_scale = self._scale_factor
            self.set_scale_factor(new_scale)
            if abs(old_scale - new_scale) > 0.001:
                self.scale_changed.emit(new_scale)

            event.accept()
            return True
        else:
            return super().wheelEvent(event)

    def set_background_color(self, color: QColor):
        """Set a solid background color and switch to Solid Color mode.

        Args:
            color: QColor to fill behind the frame.
        """
        self._background_color = color
        self._background_mode = "Solid Color"
        self.setStyleSheet("border: 1px solid gray; background-color: transparent;")
        self.update_display()

    def set_background_mode(self, mode: str):
        """Switch the background rendering mode.

        Args:
            mode: One of 'None', 'Solid Color', or 'Transparency Pattern'.
        """
        self._background_mode = mode
        if mode == "Transparency Pattern":
            self._create_checkered_pattern()

        self.setStyleSheet("border: 1px solid gray; background-color: transparent;")
        self.update_display()

    def set_transparency_background(self, show_transparency: bool):
        """Toggle transparency pattern on or off.

        Deprecated: use ``set_background_mode()`` instead.

        Args:
            show_transparency: If True, enable the checkered pattern.
        """
        if show_transparency:
            self.set_background_mode("Transparency Pattern")
        else:
            self.set_background_mode("Solid Color")

    def _create_checkered_pattern(self):
        """Build a repeating checkered tile for transparency backgrounds."""
        checker_size = 16
        pattern_size = checker_size * 2

        self._checkered_pattern = QPixmap(pattern_size, pattern_size)
        painter = QPainter(self._checkered_pattern)

        light_gray = QColor(240, 240, 240)
        white = QColor(255, 255, 255)

        for x in range(0, pattern_size, checker_size):
            for y in range(0, pattern_size, checker_size):
                is_light = ((x // checker_size) + (y // checker_size)) % 2 == 0
                color = light_gray if is_light else white
                painter.fillRect(x, y, checker_size, checker_size, color)

        painter.end()

    def get_scale_factor(self):
        """Return the current zoom multiplier.

        Returns:
            Zoom factor where 1.0 is 100%.
        """
        return self._scale_factor

    def set_scale_factor(self, scale: float):
        """Apply a new zoom level and refresh the display.

        Args:
            scale: Zoom multiplier (1.0 = 100%).
        """
        if abs(self._scale_factor - scale) > 0.001:
            self._scale_factor = scale

            self._cached_scaled_pixmap = None
            self._cached_scale = None

            self.update_display()

    def set_frame(self, pixmap: QPixmap):
        """Display a new frame pixmap at the current zoom level.

        Args:
            pixmap: QPixmap to render in the scroll area.
        """
        self._current_pixmap = pixmap
        self._cached_scaled_pixmap = None
        self._cached_scale = None

        if pixmap and not pixmap.isNull():
            self._original_size = pixmap.size()

        self.update_display()

    def update_display(self):
        """Redraw the current frame with scaling and background applied."""
        if not self._current_pixmap or self._current_pixmap.isNull():
            self.image_label.clear()
            return

        pixmap_size = self._current_pixmap.size()
        scaled_width = int(pixmap_size.width() * self._scale_factor)
        scaled_height = int(pixmap_size.height() * self._scale_factor)
        scaled_size = QSize(scaled_width, scaled_height)

        if (
            self._cached_scaled_pixmap
            and self._cached_scale
            and abs(self._cached_scale - self._scale_factor) < 0.001
            and self._cached_scaled_pixmap.size() == scaled_size
        ):
            display_pixmap = self._cached_scaled_pixmap
        else:
            if self._scale_factor == 1.0:
                display_pixmap = self._current_pixmap
            else:
                display_pixmap = self._current_pixmap.scaled(
                    scaled_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )

                self._cached_scaled_pixmap = display_pixmap
                self._cached_scale = self._scale_factor

        if self._background_mode == "Transparency Pattern" and self._checkered_pattern:
            final_pixmap = QPixmap(display_pixmap.size())
            final_pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(final_pixmap)

            pattern_size = self._checkered_pattern.size()
            for x in range(0, final_pixmap.width(), pattern_size.width()):
                for y in range(0, final_pixmap.height(), pattern_size.height()):
                    painter.drawPixmap(x, y, self._checkered_pattern)

            painter.drawPixmap(0, 0, display_pixmap)
            painter.end()

            self.image_label.setPixmap(final_pixmap)
        elif self._background_mode == "Solid Color":
            final_pixmap = QPixmap(display_pixmap.size())
            final_pixmap.fill(self._background_color)

            painter = QPainter(final_pixmap)
            painter.drawPixmap(0, 0, display_pixmap)
            painter.end()

            self.image_label.setPixmap(final_pixmap)
        else:
            self.image_label.setPixmap(display_pixmap)

        self.image_label.resize(display_pixmap.size())

    def clear_cache(self):
        """Discard cached scaled pixmaps to free memory."""
        self._cached_scaled_pixmap = None
        self._cached_scale = None


class AnimationPreviewWindow(QDialog):
    """Dialog for previewing and configuring animation playback.

    Loads frames in a background thread and provides controls for FPS,
    scale, looping, frame selection, and background display. Emits
    ``settings_saved`` when the user closes and saves.

    Signals:
        settings_saved(dict): Emitted with the chosen export settings.

    Attributes:
        animation_path: Path to the animation file being previewed.
        settings: Dictionary of current animation settings.
        frames: List of loaded QPixmap frames.
        frame_durations: Per-frame display durations in milliseconds.
    """

    settings_saved = Signal(dict)

    def __init__(self, parent, animation_path: str, settings: dict):
        """Create the preview dialog and start loading frames.

        Args:
            parent: Parent widget (typically the main application window).
            animation_path: Path to the animation file to preview.
            settings: Initial animation settings dictionary.
        """
        super().__init__(parent)
        self.animation_path = animation_path
        self.settings = settings.copy() if settings else {}

        self.frames: List[QPixmap] = []
        self.frame_durations: List[int] = []
        self.custom_frame_durations: List[int] = []
        self.current_frame = 0
        self.is_playing = False
        self.is_loading = False
        self.processor = None
        self._loop_delay_applied = False

        self._last_update_time = 0
        self._update_throttle = 16

        self.display = None
        self.frame_list = None
        self.play_button = None
        self.position_slider = None
        self.timer = None
        self.progress_label = None

        self.fps_spinbox = None
        self.fps_label = None  # Label for FPS/delay switching
        self.scale_spinbox = None
        self.loop_checkbox = None
        self.per_frame_mode_checkbox = None

        self.init_ui()
        self.load_animation()

    def init_ui(self):
        """Build the dialog layout and connect signals."""
        self.setWindowTitle(self.tr("Animation Preview"))
        self.setMinimumSize(960, 480)
        self.resize(1366, 768)

        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        main_layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        left_panel = self.create_frame_panel()
        splitter.addWidget(left_panel)

        center_panel = self.create_display_panel()
        splitter.addWidget(center_panel)

        right_panel = self.create_settings_panel()
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        controls_layout = self.create_controls()
        main_layout.addLayout(controls_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton(self.tr(ButtonLabels.CLOSE))
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)

        close_save_button = QPushButton(self.tr(ButtonLabels.CLOSE_AND_SAVE))
        close_save_button.clicked.connect(self.close_and_save)
        button_layout.addWidget(close_save_button)

        main_layout.addLayout(button_layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.next_frame)

        self.update_format_settings()

    def close_and_save(self):
        """Emit settings_saved with current settings and close the dialog."""
        checked_frames = self.get_checked_frame_indices()

        duration_ms = self._get_spinbox_duration_ms()
        display_value = self.fps_spinbox.value()
        duration_type = self._get_current_duration_type()

        save_settings = {
            "duration": duration_ms,
            "duration_display_value": display_value,
            "duration_display_type": duration_type,
            "scale": self.anim_scale_spinbox.value(),
            "resampling_method": get_resampling_name(
                self.resampling_combo.currentIndex()
            ),
            "animation_format": self.format_combo.currentText(),
            "delay": self.delay_spinbox.value(),
            "period": self.period_spinbox.value(),
            "threshold": self.threshold_spinbox.value() / 100.0,
            "var_delay": self.var_delay_checkbox.isChecked(),
            "crop_option": self.crop_combo.currentData(),
        }

        if len(checked_frames) < len(self.frames) and checked_frames:
            save_settings["indices"] = checked_frames

        if (
            self.per_frame_mode_checkbox.isChecked()
            and self.custom_frame_durations
            and len(self.custom_frame_durations) == len(self.frames)
        ):
            save_settings["custom_frame_durations"] = self.custom_frame_durations.copy()

        self.settings_saved.emit(save_settings)

        self.accept()

    def create_frame_panel(self) -> QWidget:
        """Build the left panel containing the frame list.

        Returns:
            QWidget with the frame list layout.
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        layout.addWidget(QLabel(self.tr(Labels.FRAMES) + ":"))

        self.frame_list = FrameListWidget()
        self.frame_list.frame_selected.connect(self.goto_frame)
        self.frame_list.frame_checked.connect(self.on_frame_checked)
        layout.addWidget(self.frame_list)

        return panel

    def create_display_panel(self) -> QWidget:
        """Build the center panel containing the animation display.

        Returns:
            QWidget with the animation display and info labels.
        """
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.display = AnimationDisplay()

        self.display.setToolTip(self.tr(Tooltips.CTRL_ZOOM))

        self.display.scale_changed.connect(self.on_display_scale_changed)

        layout.addWidget(self.display)

        info_layout = QHBoxLayout()

        self.frame_info_label = QLabel(self.tr("Frame 1 / 1"))
        self.frame_info_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        info_layout.addWidget(self.frame_info_label)

        self.progress_label = QLabel("")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.progress_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.progress_label)

        layout.addLayout(info_layout)

        return panel

    def create_settings_panel(self) -> QWidget:
        """Build the right panel containing format and playback controls.

        Returns:
            QWidget with grouped settings controls.
        """
        panel = QWidget()
        panel.setMaximumWidth(300)
        layout = QVBoxLayout(panel)

        format_group = QGroupBox(self.tr(Labels.ANIMATION_FORMAT))
        format_layout = QGridLayout(format_group)

        format_layout.addWidget(QLabel(self.tr(Labels.ANIMATION_FORMAT)), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["GIF", "WebP"])  # APNG disabled due to preview bug
        self.format_combo.setCurrentText(self.settings.get("animation_format", "GIF"))
        self.format_combo.currentTextChanged.connect(self.on_format_changed)
        format_layout.addWidget(self.format_combo, 0, 1)

        layout.addWidget(format_group)

        playback_group = QGroupBox(self.tr(GroupTitles.ANIMATION_SETTINGS))
        playback_layout = QGridLayout(playback_group)

        self.fps_label = QLabel(self.tr(Labels.FRAME_RATE))
        playback_layout.addWidget(self.fps_label, 0, 0)
        self.fps_spinbox = QSpinBox()
        self.fps_spinbox.setRange(
            int(SpinBoxConfig.FRAME_RATE_EXTENDED.min_val),
            int(SpinBoxConfig.FRAME_RATE_EXTENDED.max_val),
        )
        self.fps_spinbox.valueChanged.connect(self.on_fps_changed)
        playback_layout.addWidget(self.fps_spinbox, 0, 1)

        self._set_duration_spinbox_from_ms(
            self.settings.get("duration", 42),
            self.settings.get("duration_display_value"),
            self.settings.get("duration_display_type"),
        )
        self.update_frame_rate_display()

        playback_layout.addWidget(QLabel(self.tr(Labels.LOOP_DELAY)), 1, 0)
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 5000)
        self.delay_spinbox.setValue(self.settings.get("delay", 250))
        self.delay_spinbox.valueChanged.connect(self.on_delay_changed)
        playback_layout.addWidget(self.delay_spinbox, 1, 1)

        playback_layout.addWidget(QLabel(self.tr(Labels.MINIMUM_PERIOD)), 2, 0)
        self.period_spinbox = QSpinBox()
        self.period_spinbox.setRange(0, 10000)
        self.period_spinbox.setValue(self.settings.get("period", 0))
        self.period_spinbox.valueChanged.connect(self.on_period_changed)
        playback_layout.addWidget(self.period_spinbox, 2, 1)

        self.var_delay_checkbox = QCheckBox(self.tr(Labels.VARIABLE_DELAY))
        self.var_delay_checkbox.setChecked(self.settings.get("var_delay", False))
        self.var_delay_checkbox.toggled.connect(self.on_var_delay_changed)
        playback_layout.addWidget(self.var_delay_checkbox, 3, 0, 1, 2)

        playback_layout.addWidget(QLabel(self.tr(Labels.SCALE)), 4, 0)
        self.anim_scale_spinbox = QDoubleSpinBox()
        self.anim_scale_spinbox.setRange(0.1, 10.0)
        self.anim_scale_spinbox.setSingleStep(0.1)
        self.anim_scale_spinbox.setValue(self.settings.get("scale", 1.0))
        self.anim_scale_spinbox.valueChanged.connect(self.on_anim_scale_changed)
        playback_layout.addWidget(self.anim_scale_spinbox, 4, 1)

        playback_layout.addWidget(QLabel(self.tr(Labels.RESAMPLING)), 5, 0)
        self.resampling_combo = QComboBox()
        self.resampling_combo.addItems(RESAMPLING_DISPLAY_NAMES)
        current_resampling = self.settings.get(
            "resampling_method", DEFAULT_RESAMPLING_METHOD
        )
        self.resampling_combo.setCurrentIndex(get_resampling_index(current_resampling))
        self.resampling_combo.setToolTip(self.tr(Tooltips.RESAMPLING_IMAGES))
        self.resampling_combo.currentIndexChanged.connect(self.on_resampling_changed)
        playback_layout.addWidget(self.resampling_combo, 5, 1)

        playback_layout.addWidget(QLabel(self.tr(Labels.INDICES) + ":"), 6, 0)
        self.indices_edit = QLineEdit()
        self.indices_edit.setPlaceholderText(self.tr(Placeholders.INDICES_HINT))
        self.indices_edit.textChanged.connect(self.on_indices_changed)
        playback_layout.addWidget(self.indices_edit, 6, 1)

        playback_layout.addWidget(QLabel(self.tr(Labels.CROPPING_METHOD)), 7, 0)
        self.crop_combo = QComboBox()
        populate_combobox(self.crop_combo, CROPPING_METHOD_OPTIONS, self.tr)
        current_crop = self.settings.get("crop_option", "none")
        current_index = get_index_by_internal(CROPPING_METHOD_OPTIONS, current_crop)
        self.crop_combo.setCurrentIndex(current_index)
        self.crop_combo.currentIndexChanged.connect(self.on_crop_changed)
        playback_layout.addWidget(self.crop_combo, 7, 1)

        playback_layout.addWidget(QLabel(self.tr(Labels.ALPHA_THRESHOLD)), 8, 0)
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(0, 100)
        self.threshold_spinbox.setSingleStep(1)
        self.threshold_spinbox.setSuffix(" %")
        self.threshold_spinbox.setValue(int(self.settings.get("threshold", 0.5) * 100))
        self.threshold_spinbox.valueChanged.connect(self.on_threshold_changed)
        playback_layout.addWidget(self.threshold_spinbox, 8, 1)

        self.per_frame_mode_checkbox = QCheckBox(
            self.tr(Labels.EDIT_SELECTED_FRAME_ONLY)
        )
        self.per_frame_mode_checkbox.setChecked(False)
        self.per_frame_mode_checkbox.setToolTip(
            self.tr(
                "When enabled, the 'Frame rate' control switches to show\n"
                "the delay (in ms) for the currently selected frame.\n"
                "Other settings still affect the entire animation."
            )
        )
        self.per_frame_mode_checkbox.toggled.connect(self.on_per_frame_mode_changed)
        playback_layout.addWidget(self.per_frame_mode_checkbox, 9, 0, 1, 2)

        self.apply_to_all_button = QPushButton(self.tr(ButtonLabels.APPLY_TO_ALL))
        self.apply_to_all_button.setVisible(False)
        self.apply_to_all_button.setToolTip(
            self.tr("Apply the current frame delay to all frames")
        )
        self.apply_to_all_button.clicked.connect(self.apply_delay_to_all_frames)
        playback_layout.addWidget(self.apply_to_all_button, 10, 0)

        self.reset_timing_button = QPushButton(self.tr(ButtonLabels.RESET_TIMING))
        self.reset_timing_button.setVisible(False)
        self.reset_timing_button.setToolTip(
            self.tr("Reset all frame delays back to original values")
        )
        self.reset_timing_button.clicked.connect(self.reset_frame_timing)
        playback_layout.addWidget(self.reset_timing_button, 10, 1)

        layout.addWidget(playback_group)

        display_group = QGroupBox(self.tr(GroupTitles.DISPLAY))
        display_layout = QGridLayout(display_group)

        self.loop_checkbox = QCheckBox(self.tr(Labels.LOOP_PREVIEW))
        self.loop_checkbox.setChecked(True)
        display_layout.addWidget(self.loop_checkbox, 0, 0, 1, 2)

        display_layout.addWidget(QLabel(self.tr(Labels.PREVIEW_ZOOM_COLON)), 1, 0)
        self.scale_spinbox = QSpinBox()
        self.scale_spinbox.setRange(10, 500)
        self.scale_spinbox.setSingleStep(10)
        self.scale_spinbox.setValue(100)
        self.scale_spinbox.setSuffix("%")
        self.scale_spinbox.setToolTip(
            "Preview zoom level (also controlled by Ctrl+Mouse Wheel)"
        )
        self.scale_spinbox.valueChanged.connect(self.on_scale_percentage_changed)
        display_layout.addWidget(self.scale_spinbox, 1, 1)

        display_layout.addWidget(QLabel(self.tr(Labels.BACKGROUND_COLON)), 2, 0)
        bg_layout = QVBoxLayout()

        self.bg_mode_combo = QComboBox()
        self.bg_mode_combo.addItem(self.tr("None"), "None")
        self.bg_mode_combo.addItem(self.tr("Solid Color"), "Solid Color")
        self.bg_mode_combo.addItem(
            self.tr("Transparency Pattern"), "Transparency Pattern"
        )
        self.bg_mode_combo.setCurrentIndex(self.bg_mode_combo.findData("None"))
        self.bg_mode_combo.currentIndexChanged.connect(self.on_background_mode_changed)
        bg_layout.addWidget(self.bg_mode_combo)

        self.bg_color_button = QPushButton()
        self.bg_color_button.setFixedSize(50, 30)
        self.bg_color_button.setStyleSheet(
            "background-color: rgb(127, 127, 127); border: 1px solid gray;"
        )
        self.bg_color_button.clicked.connect(self.choose_background_color)
        bg_layout.addWidget(self.bg_color_button)

        bg_widget = QWidget()
        bg_widget.setLayout(bg_layout)
        display_layout.addWidget(bg_widget, 2, 1)

        layout.addWidget(display_group)

        export_group = QGroupBox(self.tr(GroupTitles.EXPORT))
        export_layout = QVBoxLayout(export_group)

        self.regenerate_button = QPushButton(
            self.tr(ButtonLabels.FORCE_REGENERATE_ANIMATION)
        )
        self.regenerate_button.clicked.connect(self.regenerate_animation)
        export_layout.addWidget(self.regenerate_button)

        layout.addWidget(export_group)

        layout.addStretch()

        self.update_format_settings()

        return panel

    def create_controls(self) -> QVBoxLayout:
        """Build playback control buttons and position slider.

        Returns:
            QVBoxLayout containing the playback controls.
        """
        controls_layout = QVBoxLayout()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.play_button = QPushButton(self.tr(ButtonLabels.PLAY))
        self.play_button.clicked.connect(self.toggle_playback)
        button_layout.addWidget(self.play_button)

        prev_button = QPushButton(self.tr(ButtonLabels.PREVIOUS))
        prev_button.clicked.connect(self.previous_frame)
        button_layout.addWidget(prev_button)

        next_button = QPushButton(self.tr(ButtonLabels.NEXT))
        next_button.clicked.connect(self.next_frame)
        button_layout.addWidget(next_button)

        button_layout.addStretch()
        controls_layout.addLayout(button_layout)

        slider_layout = QHBoxLayout()
        slider_layout.addWidget(QLabel(self.tr(Labels.POSITION_COLON)))
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setMinimum(0)
        self.position_slider.valueChanged.connect(self.on_position_changed)
        slider_layout.addWidget(self.position_slider)
        controls_layout.addLayout(slider_layout)

        return controls_layout

    def load_animation(self):
        """Start loading animation frames in a background thread."""
        if not os.path.exists(self.animation_path):
            QMessageBox.warning(
                self,
                self.tr(DialogTitles.ERROR),
                self.tr("Animation file not found: {path}").format(
                    path=self.animation_path
                ),
            )
            return

        if self.processor and self.processor.isRunning():
            self.processor.stop()
            self.processor.wait(1000)

        self.frames.clear()
        self.frame_durations.clear()

        self.is_loading = True
        self.progress_label.setText(self.tr("Loading..."))

        if self.play_button:
            self.play_button.setEnabled(False)

        self.processor = AnimationProcessor(self.animation_path, self.settings)
        self.processor.frame_processed.connect(self.on_frame_processed)
        self.processor.processing_complete.connect(self.on_processing_complete)
        self.processor.error_occurred.connect(self.on_processing_error)
        self.processor.progress_updated.connect(self.on_progress_updated)
        self.processor.start()

    def on_progress_updated(self, current: int, total: int):
        """Update the progress label during frame loading.

        Args:
            current: Number of frames loaded so far.
            total: Total number of frames in the animation.
        """
        if self.progress_label:
            percentage = int((current / total) * 100) if total > 0 else 0
            self.progress_label.setText(
                self.tr("Loading... {percent}% ({current}/{total})").format(
                    percent=percentage, current=current, total=total
                )
            )

    def on_frame_processed(self, frame_index: int, pixmap: QPixmap):
        """Store a loaded frame and update the display if visible.

        Args:
            frame_index: Zero-based index of the processed frame.
            pixmap: The converted QPixmap for this frame.
        """
        import time

        current_time = time.time() * 1000

        while len(self.frames) <= frame_index:
            self.frames.append(QPixmap())

        self.frames[frame_index] = pixmap

        if (
            frame_index == 0
            or current_time - self._last_update_time > self._update_throttle
        ):
            if frame_index == self.current_frame or (
                frame_index == 0 and self.current_frame == 0
            ):
                self.display.set_frame(pixmap)
                self._last_update_time = current_time

    def on_processing_complete(self):
        """Finalize frame loading and enable playback controls."""
        frame_count = len(self.frames)

        self.is_loading = False
        self.progress_label.setText(
            self.tr("Loaded {count} frames").format(count=frame_count)
        )

        if self.play_button:
            self.play_button.setEnabled(True)

        if self.processor and hasattr(self.processor, "frame_durations"):
            self.frame_durations = self.processor.frame_durations.copy()

        if (
            self.custom_frame_durations
            and len(self.custom_frame_durations) == frame_count
        ):
            self.frame_list.set_frame_count(frame_count, self.custom_frame_durations)
        elif self.frame_durations:
            self.frame_list.set_frame_count(frame_count, self.frame_durations)
        else:
            self.frame_list.set_frame_count(frame_count)

        if "indices" in self.settings and self.settings["indices"]:
            self.frame_list.set_checked_frames(self.settings["indices"])

        self.position_slider.setMaximum(max(0, frame_count - 1))

        if self.frames:
            self.current_frame = 0
            self.update_display()
            self.frame_list.select_frame(0)

        print(f"Animation loaded efficiently: {frame_count} frames")

    def on_processing_error(self, error_message: str):
        """Display an error and re-enable controls on load failure.

        Args:
            error_message: Description of the error that occurred.
        """
        self.is_loading = False
        self.progress_label.setText(self.tr("Error loading animation"))

        if self.play_button:
            self.play_button.setEnabled(True)

        QMessageBox.warning(self, self.tr(DialogTitles.ERROR), error_message)

    def cleanup_resources(self):
        """Stop the processor thread, timer, and release frames."""
        if self.processor and self.processor.isRunning():
            self.processor.stop()
            self.processor.wait(1000)

        if self.timer and self.timer.isActive():
            self.timer.stop()

        if hasattr(self.display, "clear_cache"):
            self.display.clear_cache()

        self.frames.clear()
        self.frame_durations.clear()
        self.custom_frame_durations.clear()

        self.current_frame = 0
        self.is_playing = False
        self.is_loading = False

    def closeEvent(self, event):
        """Release resources before the dialog closes.

        Args:
            event: QCloseEvent for the dialog.
        """
        self.cleanup_resources()
        super().closeEvent(event)

    def update_display(self):
        """Show the current frame and update UI state."""

        if 0 <= self.current_frame < len(self.frames):
            pixmap = self.frames[self.current_frame]
            self.display.set_frame(pixmap)

            total_frames = len(self.frames)
            frame_info = self.tr("Frame {index} / {total}").format(
                index=self.current_frame + 1, total=total_frames
            )

            if self.custom_frame_durations and self.current_frame < len(
                self.custom_frame_durations
            ):
                delay_ms = self.custom_frame_durations[self.current_frame]
                frame_info += self.tr(" ({delay}ms)").format(delay=delay_ms)
            elif self.frame_durations and self.current_frame < len(
                self.frame_durations
            ):
                delay_ms = self.frame_durations[self.current_frame]
                frame_info += self.tr(" ({delay}ms)").format(delay=delay_ms)

            self.frame_info_label.setText(frame_info)

            self.position_slider.blockSignals(True)
            self.position_slider.setValue(self.current_frame)
            self.position_slider.blockSignals(False)

            self.frame_list.select_frame(self.current_frame)

            self._update_frame_delay_spinbox()

    def toggle_playback(self):
        """Start or pause animation playback."""
        if self.is_playing:
            self.pause()
        else:
            self.play()

    def play(self):
        """Begin frame-by-frame playback at the configured duration."""
        if not self.frames:
            return

        if not self.loop_checkbox.isChecked():
            checked_frames = self.get_checked_frame_indices()
            if checked_frames and self.current_frame == checked_frames[-1]:
                self.goto_frame(checked_frames[0])

        self.is_playing = True
        self.play_button.setText(self.tr(ButtonLabels.PAUSE))

        self._loop_delay_applied = False

        interval = self._get_frame_duration_ms(self.current_frame)

        min_period = self.settings.get("period", 0)
        if min_period > 0:
            interval = max(interval, min_period)

        self.timer.start(max(1, interval))

    def pause(self):
        """Stop playback and reset the button label."""
        self.is_playing = False
        self.play_button.setText(self.tr(ButtonLabels.PLAY))
        self.timer.stop()

        self._loop_delay_applied = False

    def _restart_timer_for_current_frame(self):
        """Restart the playback timer using the current frame's duration."""
        interval = self._get_frame_duration_ms(self.current_frame)
        min_period = self.settings.get("period", 0)
        if min_period > 0:
            interval = max(interval, min_period)
        self.timer.start(max(1, interval))

    def next_frame(self):
        """Advance to the next frame, skipping unchecked frames during playback."""
        if not self.frames:
            return

        if self.is_playing:
            self.goto_next_checked_frame()
        else:
            self.current_frame += 1

            if self.current_frame >= len(self.frames):
                if self.loop_checkbox.isChecked():
                    self.current_frame = 0
                    if self.is_playing:
                        loop_delay = self.settings.get("delay", 250)
                        if loop_delay > 0:
                            self.timer.stop()
                            self.timer.start(loop_delay)
                            self.update_display()
                            return
                else:
                    self.current_frame = len(self.frames) - 1
                    self.pause()

            self.update_display()

            if self.is_playing:
                interval = self._get_frame_duration_ms(self.current_frame)
                min_period = self.settings.get("period", 0)
                if min_period > 0:
                    interval = max(interval, min_period)
                self.timer.start(max(1, interval))

    def previous_frame(self):
        """Step back to the previous frame."""
        if not self.frames:
            return

        self.current_frame -= 1
        if self.current_frame < 0:
            self.current_frame = max(0, len(self.frames) - 1)

        self.update_display()

    def goto_frame(self, frame_index: int):
        """Display a specific frame.

        Args:
            frame_index: Zero-based index of the frame to show.
        """
        if 0 <= frame_index < len(self.frames):
            self.current_frame = frame_index
            self.update_display()

    def on_frame_checked(self, frame_index, checked):
        """Handle frame checkbox toggling.

        Args:
            frame_index: Zero-based index of the toggled frame.
            checked: True if the checkbox is now checked.
        """
        if not checked and self.current_frame == frame_index:
            self.goto_next_checked_frame()

        self.update_indices_text_from_checkboxes()

    def update_indices_text_from_checkboxes(self):
        """Synchronize the indices text field with checkbox states."""
        checked_frames = self.get_checked_frame_indices()
        total_frames = len(self.frames)

        if len(checked_frames) == total_frames:
            self.indices_edit.blockSignals(True)
            self.indices_edit.setText("")
            self.indices_edit.blockSignals(False)
            self.settings.pop("indices", None)
        else:
            indices_text = self.compress_indices_to_text(checked_frames)
            self.indices_edit.blockSignals(True)
            self.indices_edit.setText(indices_text)
            self.indices_edit.blockSignals(False)
            self.settings["indices"] = checked_frames

    def compress_indices_to_text(self, indices):
        """Convert a list of indices to a compact range string.

        Args:
            indices: Iterable of integer frame indices.

        Returns:
            String like '0,2-5,7' representing the indices.
        """
        if not indices:
            return ""

        indices = sorted(set(indices))
        result = []
        i = 0

        while i < len(indices):
            start = indices[i]
            end = start

            while i + 1 < len(indices) and indices[i + 1] == indices[i] + 1:
                i += 1
                end = indices[i]

            if start == end:
                result.append(str(start))
            else:
                result.append(f"{start}-{end}")

            i += 1

        return ",".join(result)

    def get_checked_frame_indices(self):
        """Return a list of checked frame indices from the frame list.

        Returns:
            List of zero-based indices for all checked frames.
        """
        return self.frame_list.get_checked_frames()

    def goto_next_checked_frame(self):
        """Advance to the next checked frame, looping if enabled."""
        checked_frames = self.get_checked_frame_indices()
        if not checked_frames:
            return

        next_frames = [f for f in checked_frames if f > self.current_frame]
        if next_frames:
            self.goto_frame(next_frames[0])
            self._loop_delay_applied = False
            if self.is_playing:
                self._restart_timer_for_current_frame()
        else:
            if not self.loop_checkbox.isChecked():
                self.pause()
                return

            if self.is_playing and not self._loop_delay_applied:
                loop_delay = self.settings.get("delay", 250)
                if loop_delay > 0:
                    self.timer.stop()
                    QTimer.singleShot(loop_delay, self._loop_to_first_frame)
                    self._loop_delay_applied = True
                    return

            self.goto_frame(checked_frames[0])
            if self.is_playing:
                self._restart_timer_for_current_frame()
                self._loop_delay_applied = True

    def goto_previous_checked_frame(self):
        """Return to the previous checked frame."""
        checked_frames = self.get_checked_frame_indices()
        if not checked_frames:
            return

        prev_frames = [f for f in checked_frames if f < self.current_frame]
        if prev_frames:
            self.goto_frame(prev_frames[-1])
        else:
            self.goto_frame(checked_frames[-1])

    def on_position_changed(self, position: int):
        """Jump to the frame indicated by the position slider.

        Args:
            position: Slider value representing the frame index.
        """
        self.goto_frame(position)

    def on_fps_changed(self, value: int):
        """Handle duration spinbox value changes.

        In normal mode, this updates the duration setting.
        In per-frame mode, this updates the delay for the current frame.

        The spinbox value is in the current display unit (fps, ms, cs, ds).
        Internally we convert to milliseconds for timer calculations.

        Args:
            value: New duration value in the current display unit.
        """
        if self.per_frame_mode_checkbox and self.per_frame_mode_checkbox.isChecked():
            self._on_frame_delay_changed(value)
            return

        duration_type = self._get_current_duration_type()
        anim_format = (
            self.format_combo.currentText().upper() if self.format_combo else "GIF"
        )

        delay_ms = duration_to_milliseconds(value, duration_type, anim_format)
        self.settings["duration"] = delay_ms

        if self.settings.get("var_delay", False) and self.frame_durations:
            fps = max(1, round(1000 / delay_ms)) if delay_ms > 0 else 24
            new_durations = []
            for index in range(len(self.frame_durations)):
                duration = round((index + 1) * 1000 / fps, -1) - round(
                    index * 1000 / fps, -1
                )
                new_durations.append(int(duration))

            loop_delay = self.settings.get("delay", 250)
            period = self.settings.get("period", 0)

            new_durations[-1] += loop_delay
            new_durations[-1] += max(round(period, -1) - sum(new_durations), 0)

            self.frame_durations = new_durations

            if hasattr(self.frame_list, "update_frame_delays"):
                self.frame_list.update_frame_delays(self.frame_durations, True)

            self.update_display()
        else:
            self._update_frame_delay_display()

        if self.is_playing:
            self._restart_timer_for_current_frame()

        self.regenerate_animation()

    def _get_current_duration_type(self) -> str:
        """Get the resolved duration type from app_config.

        Returns:
            The duration type string (fps, milliseconds, centiseconds, etc.)
        """
        duration_type = "fps"
        parent = self.parent()
        if parent and hasattr(parent, "app_config"):
            interface = parent.app_config.get("interface", {})
            duration_type = interface.get("duration_input_type", "fps")

        # Resolve 'native' to format-specific type
        if duration_type == "native":
            anim_format = self._get_animation_format()
            if anim_format == "GIF":
                duration_type = "centiseconds"
            else:
                duration_type = "milliseconds"

        return duration_type

    def _get_animation_format(self) -> str:
        return self.format_combo.currentText().upper() if self.format_combo else "GIF"

    def _set_duration_spinbox_from_ms(
        self,
        duration_ms: int,
        stored_display_value: int | None = None,
        stored_display_type: str | None = None,
    ) -> None:
        duration_type = self._get_current_duration_type()
        anim_format = self._get_animation_format()
        display_value = load_duration_display_value(
            max(1, duration_ms),
            stored_display_value,
            stored_display_type,
            duration_type,
            anim_format,
        )
        self._prev_duration_type = duration_type
        if self.fps_spinbox:
            self.fps_spinbox.blockSignals(True)
            self.fps_spinbox.setValue(display_value)
            self.fps_spinbox.blockSignals(False)

    def _get_spinbox_duration_ms(self) -> int:
        duration_type = self._get_current_duration_type()
        anim_format = self._get_animation_format()
        return duration_to_milliseconds(
            max(1, self.fps_spinbox.value()), duration_type, anim_format
        )

    def _get_duration_ms(self) -> int:
        duration = self.settings.get("duration")
        if duration is None:
            duration = getattr(self, "_stored_duration_ms", 42)
        return max(1, int(duration))

    def _get_frame_duration_ms(self, frame_index: int) -> int:
        """Return the duration in milliseconds for a specific frame.

        Checks custom_frame_durations first (user overrides), then
        frame_durations (read from the GIF file), and finally falls back
        to the global duration setting.

        Args:
            frame_index: Zero-based index of the frame.

        Returns:
            Duration in milliseconds for the requested frame.
        """
        if self.custom_frame_durations and 0 <= frame_index < len(
            self.custom_frame_durations
        ):
            return max(1, self.custom_frame_durations[frame_index])
        if self.frame_durations and 0 <= frame_index < len(self.frame_durations):
            return max(1, self.frame_durations[frame_index])
        return self._get_duration_ms()

    def on_display_scale_changed(self, scale: float):
        """Sync the zoom spinbox when the display is scrolled.

        Args:
            scale: New zoom factor from the display widget.
        """
        self.scale_spinbox.blockSignals(True)
        percentage = int(scale * 100)
        self.scale_spinbox.setValue(percentage)
        self.scale_spinbox.blockSignals(False)

    def on_scale_percentage_changed(self, percentage: int):
        """Apply a new preview zoom level from the spinbox.

        Args:
            percentage: Zoom percentage (100 = 100%).
        """
        scale = percentage / 100.0
        self.display.set_scale_factor(scale)

    def on_scale_changed(self, scale: float):
        """Apply a preview zoom level directly.

        Deprecated: use ``on_scale_percentage_changed()`` instead.

        Args:
            scale: Zoom factor (1.0 = 100%).
        """
        self.display.set_scale_factor(scale)

    def choose_background_color(self):
        """Open a color dialog and apply the chosen background."""
        color = QColorDialog.getColor(
            QColor(127, 127, 127), self, self.tr("Choose Background Color")
        )
        if color.isValid():
            self.display.set_background_color(color)
            self.bg_color_button.setStyleSheet(
                f"background-color: {color.name()}; border: 1px solid gray;"
            )
            solid_index = self.bg_mode_combo.findData("Solid Color")
            if solid_index != -1:
                self.bg_mode_combo.setCurrentIndex(solid_index)

    def on_background_mode_changed(self, _index: int):
        """Switch the display background and show/hide the color button.

        Args:
            mode: One of 'None', 'Solid Color', or 'Transparency Pattern'.
        """
        mode = self.bg_mode_combo.currentData()
        self.display.set_background_mode(mode)
        self.bg_color_button.setVisible(mode == "Solid Color")

    def on_transparency_changed(self, checked: bool):
        """Toggle transparency background display.

        Deprecated: use ``on_background_mode_changed()`` instead.

        Args:
            checked: True to show the transparency pattern.
        """
        self.display.set_transparency_background(checked)

    def regenerate_animation(self):
        """Re-export the animation with current settings and reload it."""
        if not self.play_button or not self.progress_label:
            return

        try:
            from core.extractor import Extractor

            current_spritesheet_item = (
                self.parent().extract_tab_widget.listbox_png.currentItem()
            )
            current_animation_item = (
                self.parent().extract_tab_widget.listbox_data.currentItem()
            )

            if not current_spritesheet_item or not current_animation_item:
                QMessageBox.warning(
                    self, "Error", "Please select a spritesheet and animation first."
                )
                return

            current_format = self.settings.get("animation_format", "GIF")
            self.progress_label.setText(f"Generating {current_format}...")
            self.play_button.setEnabled(False)

            spritesheet_path = current_spritesheet_item.data(Qt.ItemDataRole.UserRole)
            if not spritesheet_path:
                QMessageBox.warning(
                    self, "Error", "Could not find spritesheet file path."
                )
                return

            spritesheet_name = current_spritesheet_item.text()
            metadata_path = None
            spritemap_info = None
            if spritesheet_name in self.parent().data_dict:
                data_files = self.parent().data_dict[spritesheet_name]
                if isinstance(data_files, dict):
                    # Check for metadata files in priority order
                    metadata_keys = [
                        "xml",
                        "txt",
                        "json",
                        "plist",
                        "atlas",
                        "css",
                        "tpsheet",
                        "tpset",
                        "paper2dsprites",
                    ]
                    for key in metadata_keys:
                        if key in data_files:
                            metadata_path = data_files[key]
                            break
                    # Special handling for spritemap
                    if metadata_path is None and "spritemap" in data_files:
                        spritemap_info = data_files["spritemap"]

            extractor = Extractor(None, "2.0.0", self.parent().settings_manager)

            animation_name = current_animation_item.text()
            complete_settings = self.parent().get_complete_preview_settings(
                spritesheet_name, animation_name
            )

            complete_settings.update(
                {
                    "animation_format": self.settings.get("animation_format", "GIF"),
                    "duration": self._get_spinbox_duration_ms(),
                    "scale": self.anim_scale_spinbox.value(),
                    "resampling_method": self.settings.get(
                        "resampling_method", DEFAULT_RESAMPLING_METHOD
                    ),
                    "crop_option": self.settings.get("crop_option", "none"),
                    "delay": self.settings.get("delay", 250),
                    "period": self.settings.get("period", 0),
                    "var_delay": self.settings.get("var_delay", False),
                }
            )

            indices_text = self.indices_edit.text().strip()
            if indices_text:
                try:
                    indices = []
                    for part in indices_text.split(","):
                        part = part.strip()
                        if "-" in part:
                            start, end = map(int, part.split("-"))
                            indices.extend(range(start, end + 1))
                        else:
                            indices.append(int(part))
                    complete_settings["indices"] = indices
                    complete_settings["frame_selection"] = "Custom"
                except ValueError:
                    complete_settings["frame_selection"] = "All"
            else:
                complete_settings["frame_selection"] = "All"

            if self.settings.get("animation_format") == "GIF":
                complete_settings["threshold"] = self.settings.get("threshold", 0.5)

            temp_path = extractor.generate_temp_animation_for_preview(
                atlas_path=spritesheet_path,
                metadata_path=metadata_path,
                settings=complete_settings,
                animation_name=animation_name,
                spritemap_info=spritemap_info,
                spritesheet_label=spritesheet_name,
            )

            if temp_path and os.path.exists(temp_path):
                self.animation_path = temp_path
                self.settings = complete_settings
                self.frames.clear()
                self.frame_durations.clear()
                self.load_animation()
            else:
                QMessageBox.warning(
                    self,
                    self.tr(DialogTitles.ERROR),
                    self.tr("Failed to regenerate animation."),
                )

        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr(DialogTitles.ERROR),
                self.tr("Failed to regenerate animation: {error}").format(error=str(e)),
            )

    def update_format_settings(self):
        """Show or hide controls depending on the selected format."""
        pass

    def update_frame_rate_display(self):
        """Update frame rate label and spinbox based on duration input type setting.

        Reads the duration_input_type from app_config and configures the
        fps_label text, spinbox range, suffix, value, and tooltip accordingly.
        When the duration type changes, the current value is converted to
        the new unit.
        """
        if not self.fps_spinbox or not self.fps_label:
            return

        duration_type = "fps"
        parent = self.parent()
        if parent and hasattr(parent, "app_config"):
            interface = parent.app_config.get("interface", {})
            duration_type = interface.get("duration_input_type", "fps")

        anim_format = (
            self.format_combo.currentText().upper() if self.format_combo else "GIF"
        )
        display_meta = get_duration_display_meta(duration_type, anim_format)
        resolved_type = display_meta.resolved_type
        duration_tooltip = self.tr(display_meta.tooltip)

        prev_type = getattr(self, "_prev_duration_type", resolved_type)
        current_value = self.fps_spinbox.value()

        if prev_type != resolved_type:
            converted_value = convert_duration(
                current_value, prev_type, resolved_type, anim_format
            )
        else:
            converted_value = current_value

        self._prev_duration_type = resolved_type

        self.fps_label.setText(self.tr(display_meta.label))
        self.fps_spinbox.setRange(display_meta.min_value, display_meta.max_value)
        self.fps_spinbox.setSuffix(self.tr(display_meta.suffix))

        self.fps_spinbox.setValue(converted_value)
        self.fps_label.setToolTip(duration_tooltip)
        self.fps_spinbox.setToolTip(duration_tooltip)

    def on_format_changed(self, format_type):
        """Update the animation format and regenerate.

        Args:
            format_type: New format string ('GIF', 'WebP', or 'APNG').
        """
        self.settings["animation_format"] = format_type
        self.update_format_settings()
        self.update_frame_rate_display()
        self.regenerate_animation()

    def on_delay_changed(self, delay):
        """Update the loop delay and regenerate.

        Args:
            delay: Delay in milliseconds before looping.
        """
        self.settings["delay"] = delay

        self._update_frame_delay_display()

        self.regenerate_animation()

    def on_period_changed(self, period):
        """Update the minimum frame period.

        Args:
            period: Minimum duration in milliseconds per frame.
        """
        self.settings["period"] = period

        self._update_frame_delay_display()

        if self.is_playing:
            self._restart_timer_for_current_frame()

    def on_var_delay_changed(self, enabled):
        """Toggle variable per-frame delay and regenerate.

        Args:
            enabled: True to calculate unique delays per frame.
        """
        self.settings["var_delay"] = enabled

        if enabled and self.frame_durations:
            delay_ms = self._get_duration_ms()
            fps = max(1, round(1000 / delay_ms)) if delay_ms > 0 else 24

            new_durations = []
            for index in range(len(self.frame_durations)):
                duration = round((index + 1) * 1000 / fps, -1) - round(
                    index * 1000 / fps, -1
                )
                new_durations.append(int(duration))

            loop_delay = self.settings.get("delay", 250)
            period = self.settings.get("period", 0)

            new_durations[-1] += loop_delay
            new_durations[-1] += max(round(period, -1) - sum(new_durations), 0)

            self.frame_durations = new_durations

            if hasattr(self.frame_list, "update_frame_delays"):
                self.frame_list.update_frame_delays(self.frame_durations, True)

            self.update_display()
        else:
            self._update_frame_delay_display()

        self.regenerate_animation()

    def on_indices_changed(self, indices_text):
        """Parse the indices text and update frame selection.

        Args:
            indices_text: Comma/range notation like '0,2-5,7'.
        """
        self.settings["indices_text"] = indices_text
        try:
            if indices_text.strip():
                indices = []
                for part in indices_text.split(","):
                    part = part.strip()
                    if "-" in part:
                        start, end = map(int, part.split("-"))
                        indices.extend(range(start, end + 1))
                    else:
                        indices.append(int(part))

                indices = [i for i in indices if 0 <= i < len(self.frames)]
                self.settings["indices"] = indices

                if hasattr(self.frame_list, "set_checked_frames"):
                    self.frame_list.set_checked_frames(indices)
            else:
                self.settings.pop("indices", None)
                if hasattr(self.frame_list, "set_checked_frames") and self.frames:
                    all_indices = list(range(len(self.frames)))
                    self.frame_list.set_checked_frames(all_indices)
        except ValueError:
            pass

    def on_anim_scale_changed(self, scale):
        """Update the animation export scale and regenerate.

        Args:
            scale: Export scale factor.
        """
        self.settings["scale"] = scale
        self.regenerate_animation()

    def on_crop_changed(self, _index):
        """Update the crop option and regenerate.

        Args:
            crop_option: One of 'None', 'Animation based', or 'Frame based'.
        """
        self.settings["crop_option"] = self.crop_combo.currentData()
        self.regenerate_animation()

    def on_threshold_changed(self, threshold):
        """Update the GIF threshold and regenerate.

        Args:
            threshold: Quantization threshold percentage (0-100).
        """
        self.settings["threshold"] = threshold / 100.0
        self.regenerate_animation()

    def on_resampling_changed(self, index: int):
        """Update the resampling method and regenerate.

        Args:
            index: Index of the selected resampling method.
        """
        self.settings["resampling_method"] = get_resampling_name(index)
        self.regenerate_animation()

    def _restart_normal_timer(self):
        """Resume playback with the current frame's duration interval."""
        if self.is_playing:
            self._restart_timer_for_current_frame()

    def _loop_to_first_frame(self):
        """Jump to the first checked frame and resume playback."""
        if self.is_playing:
            checked_frames = self.get_checked_frame_indices()
            if checked_frames:
                self.goto_frame(checked_frames[0])
                self._restart_normal_timer()

    def _update_frame_delay_display(self):
        """Recalculate and refresh the frame delay labels."""
        if not self.frame_durations or not hasattr(self, "frame_list"):
            return

        delay_ms = self._get_duration_ms()

        loop_delay = self.settings.get("delay", 250)
        var_delay = self.settings.get("var_delay", False)
        period = self.settings.get("period", 0)

        display_delays = []

        if self.custom_frame_durations and len(self.custom_frame_durations) == len(
            self.frame_durations
        ):
            display_delays = self.custom_frame_durations.copy()
        elif var_delay:
            display_delays = self.frame_durations.copy()
        else:
            fixed_delay = round(delay_ms, -1)
            display_delays = [int(fixed_delay)] * len(self.frame_durations)

            display_delays[-1] += loop_delay
            display_delays[-1] += max(round(period, -1) - sum(display_delays), 0)

        if hasattr(self.frame_list, "update_frame_delays"):
            self.frame_list.update_frame_delays(display_delays, True)

        self.update_display()

    def on_per_frame_mode_changed(self, enabled: bool):
        """Toggle per-frame timing edit mode.

        When enabled, the FPS spinbox switches to show delay in the configured
        duration input type for the currently selected frame.

        Args:
            enabled: True to enable editing individual frame delays.
        """
        if enabled:
            self._stored_duration_ms = self._get_spinbox_duration_ms()

        self.apply_to_all_button.setVisible(enabled)
        self.reset_timing_button.setVisible(enabled)

        self.fps_spinbox.blockSignals(True)
        if enabled:
            duration_type = self.settings.get("duration_input_type", "fps")
            anim_format = (
                self.format_combo.currentText().upper() if self.format_combo else "GIF"
            )
            display_meta = get_duration_display_meta(duration_type, anim_format)
            resolved_type = display_meta.resolved_type

            if resolved_type == "fps":
                resolved_type = "milliseconds"
                display_meta = get_duration_display_meta(resolved_type, anim_format)

            min_value = display_meta.min_value
            max_value = display_meta.max_value
            single_step = 1
            if resolved_type == "milliseconds":
                min_value = max(10, min_value)
                max_value = min(10000, max_value)
                single_step = 10

            self.fps_label.setText(self.tr(display_meta.label))
            self.fps_spinbox.setRange(min_value, max_value)
            self.fps_spinbox.setSuffix(self.tr(display_meta.suffix))
            self.fps_spinbox.setToolTip(self.tr(display_meta.tooltip))
            self.fps_spinbox.setSingleStep(single_step)

            self._per_frame_duration_type = resolved_type

            if not self.custom_frame_durations or len(
                self.custom_frame_durations
            ) != len(self.frame_durations):
                self._initialize_custom_durations()

            if self.custom_frame_durations and 0 <= self.current_frame < len(
                self.custom_frame_durations
            ):
                delay_ms = self.custom_frame_durations[self.current_frame]
                display_value = self._ms_to_display_unit(delay_ms, duration_type)
                self.fps_spinbox.setValue(display_value)
            else:
                base_ms = self._get_duration_ms()
                fallback_value = self._ms_to_display_unit(base_ms, duration_type)
                self.fps_spinbox.setValue(fallback_value)
        else:
            self.update_frame_rate_display()
            duration_ms = getattr(
                self, "_stored_duration_ms", self.settings.get("duration", 42)
            )
            self._set_duration_spinbox_from_ms(duration_ms)
            self._per_frame_duration_type = None

        self.fps_spinbox.blockSignals(False)

    def _ms_to_display_unit(self, ms: int, duration_type: str) -> int:
        """Convert milliseconds to the specified display unit.

        Args:
            ms: Delay in milliseconds.
            duration_type: One of 'deciseconds', 'centiseconds', or 'milliseconds'.

        Returns:
            The delay value in the specified unit.
        """
        if duration_type == "deciseconds":
            return max(1, round(ms / 100))
        elif duration_type == "centiseconds":
            return max(1, round(ms / 10))
        else:
            return max(1, ms)

    def _display_unit_to_ms(self, value: int, duration_type: str) -> int:
        """Convert a display unit value to milliseconds.

        Args:
            value: The delay value in the display unit.
            duration_type: One of 'deciseconds', 'centiseconds', or 'milliseconds'.

        Returns:
            The delay in milliseconds.
        """
        if duration_type == "deciseconds":
            return value * 100
        elif duration_type == "centiseconds":
            return value * 10
        else:
            return value

    def _initialize_custom_durations(self):
        """Initialize custom frame durations from the animation's per-frame durations."""
        if not self.frame_durations:
            return

        self.custom_frame_durations = self.frame_durations.copy()

    def _update_frame_delay_spinbox(self):
        """Update the FPS spinbox to show the current frame's delay when in per-frame mode."""
        if (
            not self.per_frame_mode_checkbox
            or not self.per_frame_mode_checkbox.isChecked()
        ):
            return

        if self.custom_frame_durations and 0 <= self.current_frame < len(
            self.custom_frame_durations
        ):
            delay_ms = self.custom_frame_durations[self.current_frame]
            duration_type = getattr(self, "_per_frame_duration_type", "milliseconds")
            display_value = self._ms_to_display_unit(delay_ms, duration_type)
            self.fps_spinbox.blockSignals(True)
            self.fps_spinbox.setValue(display_value)
            self.fps_spinbox.blockSignals(False)

    def _on_frame_delay_changed(self, value: int):
        """Update the delay for the currently selected frame.

        Args:
            value: New delay in the current display unit for the current frame.
        """
        if not self.per_frame_mode_checkbox.isChecked():
            return

        if not self.custom_frame_durations:
            self._initialize_custom_durations()

        duration_type = getattr(self, "_per_frame_duration_type", "milliseconds")
        delay_ms = self._display_unit_to_ms(value, duration_type)

        if 0 <= self.current_frame < len(self.custom_frame_durations):
            self.custom_frame_durations[self.current_frame] = delay_ms

            if hasattr(self.frame_list, "update_frame_delays"):
                self.frame_list.update_frame_delays(self.custom_frame_durations, True)

            self.update_display()

    def apply_delay_to_all_frames(self):
        """Apply the current frame's delay to all frames."""
        if not self.custom_frame_durations:
            self._initialize_custom_durations()

        duration_type = getattr(self, "_per_frame_duration_type", "milliseconds")
        display_value = self.fps_spinbox.value()
        delay_ms = self._display_unit_to_ms(display_value, duration_type)

        self.custom_frame_durations = [delay_ms] * len(self.frame_durations)

        if hasattr(self.frame_list, "update_frame_delays"):
            self.frame_list.update_frame_delays(self.custom_frame_durations, True)

        self.update_display()

    def reset_frame_timing(self):
        """Reset all frame delays to FPS-based calculated values."""
        self.custom_frame_durations.clear()
        self._initialize_custom_durations()

        self._update_frame_delay_spinbox()
        self._update_frame_delay_display()
