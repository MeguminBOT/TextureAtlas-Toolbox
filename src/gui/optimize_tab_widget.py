#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Optimize tab widget for batch PNG / image compression.

Provides a UI for selecting images, choosing compression / quantization
options via presets or custom settings, previewing before/after file
sizes, and running the optimizer in a background thread.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.optimizer import (
    COLOR_MODE_LABELS,
    ColorMode,
    DITHER_METHOD_LABELS,
    DitherMethod,
    ImageOptimizer,
    OptimizeOptions,
    OptimizePreset,
    OptimizeResult,
    PRESET_LABELS,
    PRESET_OPTIONS,
    QUANTIZE_METHOD_LABELS,
    QuantizeMethod,
    SUPPORTED_EXTENSIONS,
)
from gui.base_tab_widget import BaseTabWidget
from gui.job_progress_window import JobProgressWindow
from utils.translation_manager import tr as translate
from utils.ui_constants import CheckBoxLabels, GroupTitles, Labels, Tooltips


# ---------------------------------------------------------------
# Worker thread
# ---------------------------------------------------------------


class OptimizerWorker(QThread):
    """Background worker that runs the optimization batch."""

    progress_updated = Signal(int, int, str)  # current, total, filename
    log_message = Signal(str)  # single log line for the console
    optimize_completed = Signal(list)  # List[OptimizeResult]
    optimize_failed = Signal(str)

    def __init__(
        self,
        file_paths: List[str],
        options: OptimizeOptions,
    ):
        super().__init__()
        self.file_paths = file_paths
        self.options = options

    def run(self):
        """Execute the optimization batch in a background thread."""
        try:
            optimizer = ImageOptimizer(
                progress_callback=self._emit_progress,
                log_callback=self._emit_log,
            )
            results = optimizer.optimize_batch(self.file_paths, self.options)
            self.optimize_completed.emit(results)
        except Exception as exc:
            import traceback

            error_msg = str(exc) or repr(exc)
            tb_str = traceback.format_exc()
            print(f"[OptimizerWorker] FATAL: {error_msg}")
            print(f"[OptimizerWorker] Traceback:\n{tb_str}")
            self.optimize_failed.emit(f"{error_msg}\n\n{tb_str}")

    def _emit_progress(self, current: int, total: int, filename: str):
        self.progress_updated.emit(current, total, filename)

    def _emit_log(self, message: str):
        self.log_message.emit(message)


# ---------------------------------------------------------------
# Tab widget
# ---------------------------------------------------------------


class OptimizeTabWidget(BaseTabWidget):
    """Image optimization tool tab.

    Always operates in standalone mode (builds its own UI) since there
    is no pre-existing Qt Designer layout for this tab.
    """

    tr = translate

    def __init__(self, parent_app=None):
        super().__init__(parent_app, use_existing_ui=False)
        self._file_list: List[str] = []
        self._worker: Optional[OptimizerWorker] = None
        self._progress_window: Optional[JobProgressWindow] = None
        self._applying_preset: bool = False
        self._setup_ui()

    # ------------------------------------------------------------------
    # BaseTabWidget overrides
    # ------------------------------------------------------------------

    def _setup_with_existing_ui(self):
        """Not used - this tab always builds its own UI."""
        raise NotImplementedError

    def _build_ui(self):
        """Deferred to ``_setup_ui`` so we can call it after ``super().__init__``."""
        pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(8, 8, 8, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ---- Left: file list ----
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        file_buttons_layout = QHBoxLayout()
        self._add_files_btn = QPushButton(self.tr("Add Files"))
        self._add_folder_btn = QPushButton(self.tr("Add Folder"))
        self._clear_btn = QPushButton(self.tr("Clear"))
        file_buttons_layout.addWidget(self._add_files_btn)
        file_buttons_layout.addWidget(self._add_folder_btn)
        file_buttons_layout.addWidget(self._clear_btn)
        left_layout.addLayout(file_buttons_layout)

        self._file_tree = QTreeWidget()
        self._file_tree.setHeaderLabels(
            [self.tr("File"), self.tr("Size"), self.tr("Status")]
        )
        self._file_tree.setRootIsDecorated(False)
        self._file_tree.setAlternatingRowColors(True)
        header = self._file_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.resizeSection(1, 80)
        header.resizeSection(2, 80)
        left_layout.addWidget(self._file_tree)

        self._file_count_label = QLabel(self.tr("No files selected"))
        left_layout.addWidget(self._file_count_label)

        splitter.addWidget(left_widget)

        # ---- Right: preset + options ----
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # -- Preset selector --
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel(self.tr(Labels.OPTIMIZER_PRESET)))
        self._preset_combo = QComboBox()
        for label in PRESET_LABELS:
            self._preset_combo.addItem(self.tr(label))
        self._preset_combo.setToolTip(self.tr(Tooltips.OPTIMIZER_PRESET))
        preset_layout.addWidget(self._preset_combo, stretch=1)
        right_layout.addLayout(preset_layout)

        # -- Compression options group --
        compression_group = QGroupBox(self.tr(GroupTitles.COMPRESSION))
        compression_form = QFormLayout(compression_group)

        self._compress_level_spin = QSpinBox()
        self._compress_level_spin.setRange(0, 9)
        self._compress_level_spin.setValue(9)
        self._compress_level_spin.setToolTip(self.tr(Tooltips.OPTIMIZER_COMPRESS_LEVEL))
        compression_form.addRow(
            self.tr(Labels.OPTIMIZER_COMPRESS_LEVEL), self._compress_level_spin
        )

        self._optimize_check = QCheckBox(self.tr(CheckBoxLabels.OPTIMIZER_OPTIMIZE))
        self._optimize_check.setChecked(True)
        self._optimize_check.setToolTip(self.tr(Tooltips.OPTIMIZER_OPTIMIZE))
        compression_form.addRow(self._optimize_check)

        self._strip_meta_check = QCheckBox(self.tr(CheckBoxLabels.STRIP_METADATA))
        self._strip_meta_check.setChecked(True)
        self._strip_meta_check.setToolTip(self.tr(Tooltips.OPTIMIZER_STRIP_METADATA))
        compression_form.addRow(self._strip_meta_check)

        self._skip_if_larger_check = QCheckBox(self.tr(CheckBoxLabels.SKIP_IF_LARGER))
        self._skip_if_larger_check.setChecked(True)
        self._skip_if_larger_check.setToolTip(
            self.tr(Tooltips.OPTIMIZER_SKIP_IF_LARGER)
        )
        compression_form.addRow(self._skip_if_larger_check)

        self._color_mode_combo = QComboBox()
        for label in COLOR_MODE_LABELS:
            self._color_mode_combo.addItem(self.tr(label))
        self._color_mode_combo.setToolTip(self.tr(Tooltips.OPTIMIZER_COLOR_MODE))
        compression_form.addRow(
            self.tr(Labels.OPTIMIZER_COLOR_MODE), self._color_mode_combo
        )

        right_layout.addWidget(compression_group)

        # -- Quantization group --
        quantize_group = QGroupBox(self.tr(GroupTitles.QUANTIZATION_LOSSY))
        quantize_layout = QVBoxLayout(quantize_group)

        self._quantize_check = QCheckBox(
            self.tr(CheckBoxLabels.ENABLE_COLOR_QUANTIZATION)
        )
        self._quantize_check.setChecked(False)
        self._quantize_check.setToolTip(self.tr(Tooltips.OPTIMIZER_QUANTIZE))
        quantize_layout.addWidget(self._quantize_check)

        quantize_form = QFormLayout()
        quantize_form.setContentsMargins(16, 0, 0, 0)

        self._max_colors_spin = QSpinBox()
        self._max_colors_spin.setRange(2, 256)
        self._max_colors_spin.setValue(256)
        self._max_colors_spin.setToolTip(self.tr(Tooltips.OPTIMIZER_MAX_COLORS))
        self._max_colors_label = QLabel(self.tr(Labels.OPTIMIZER_MAX_COLORS))
        quantize_form.addRow(self._max_colors_label, self._max_colors_spin)

        self._quantize_method_combo = QComboBox()
        for label in QUANTIZE_METHOD_LABELS:
            self._quantize_method_combo.addItem(self.tr(label))
        self._quantize_method_combo.setToolTip(self.tr(Tooltips.OPTIMIZER_METHOD))
        self._quantize_method_label = QLabel(self.tr(Labels.OPTIMIZER_METHOD))
        quantize_form.addRow(self._quantize_method_label, self._quantize_method_combo)

        self._dither_combo = QComboBox()
        for label in DITHER_METHOD_LABELS:
            self._dither_combo.addItem(self.tr(label))
        self._dither_combo.setCurrentIndex(1)  # Floyd-Steinberg default
        self._dither_combo.setToolTip(self.tr(Tooltips.OPTIMIZER_DITHER))
        self._dither_label = QLabel(self.tr(Labels.OPTIMIZER_DITHER))
        quantize_form.addRow(self._dither_label, self._dither_combo)

        quantize_layout.addLayout(quantize_form)
        right_layout.addWidget(quantize_group)

        # -- Output group --
        output_group = QGroupBox(self.tr(GroupTitles.OUTPUT))
        output_layout = QVBoxLayout(output_group)

        self._overwrite_check = QCheckBox(self.tr(CheckBoxLabels.OVERWRITE_ORIGINALS))
        self._overwrite_check.setChecked(False)
        self._overwrite_check.setToolTip(self.tr(Tooltips.OPTIMIZER_OVERWRITE))
        output_layout.addWidget(self._overwrite_check)

        output_dir_row = QHBoxLayout()
        self._output_dir_label = QLabel(self.tr("No output folder selected"))
        self._output_dir_label.setWordWrap(True)
        self._select_output_btn = QPushButton(self.tr("Select Output Folder"))
        output_dir_row.addWidget(self._output_dir_label, stretch=1)
        output_dir_row.addWidget(self._select_output_btn)
        output_layout.addLayout(output_dir_row)

        right_layout.addWidget(output_group)

        # -- GPU Texture Compression group --
        gpu_group = QGroupBox(self.tr("GPU Texture Compression"))
        gpu_form = QFormLayout(gpu_group)

        self._gpu_format_combo = QComboBox()
        from utils.combo_options import (
            TEXTURE_COMPRESSION_OPTIONS,
            TEXTURE_CONTAINER_OPTIONS,
        )

        for opt in TEXTURE_COMPRESSION_OPTIONS:
            self._gpu_format_combo.addItem(self.tr(opt.display_key), opt.internal)
        self._gpu_format_combo.setCurrentIndex(0)  # "None"
        self._gpu_format_combo.setToolTip(
            self.tr(
                "Produce a GPU-compressed file alongside the optimized PNG.\n\n"
                "Requires etcpak (pip install etcpak) for BC/ETC formats,\n"
                "or external CLI tools for ASTC/PVRTC."
            )
        )
        gpu_form.addRow(self.tr("Format"), self._gpu_format_combo)

        self._gpu_container_combo = QComboBox()
        for opt in TEXTURE_CONTAINER_OPTIONS:
            self._gpu_container_combo.addItem(self.tr(opt.display_key), opt.internal)
        self._gpu_container_combo.setCurrentIndex(0)  # DDS
        self._gpu_container_combo.setToolTip(
            self.tr(
                "DDS — DirectDraw Surface (desktop/console).\n"
                "KTX2 — Khronos Texture 2 (cross-platform, all formats)."
            )
        )
        self._gpu_container_label = QLabel(self.tr("Container"))
        gpu_form.addRow(self._gpu_container_label, self._gpu_container_combo)

        self._gpu_mipmap_check = QCheckBox(self.tr("Generate Mipmaps"))
        self._gpu_mipmap_check.setChecked(False)
        self._gpu_mipmap_check.setToolTip(
            self.tr(
                "Generate a full mipmap chain for better rendering\n"
                "when the texture is displayed at reduced sizes."
            )
        )
        gpu_form.addRow(self._gpu_mipmap_check)

        right_layout.addWidget(gpu_group)
        self._gpu_group = gpu_group
        self._on_gpu_format_changed()

        right_layout.addStretch()

        # Wrap right panel in a scroll area so it doesn't clip at small sizes
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        right_scroll.setWidget(right_widget)

        splitter.addWidget(right_scroll)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root_layout.addWidget(splitter)

        # ---- Bottom: action button ----
        bottom_layout = QHBoxLayout()

        self._optimize_btn = QPushButton(self.tr("Optimize Images"))
        self._optimize_btn.setMinimumHeight(36)
        bottom_layout.addWidget(self._optimize_btn)

        root_layout.addLayout(bottom_layout)

        # ---- Signals & initial state ----
        self._connect_signals()
        self._update_quantize_visibility()
        self._apply_saved_defaults()

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self):
        # Preset
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)

        # Options that switch preset to Custom when changed manually
        self._compress_level_spin.valueChanged.connect(self._on_option_changed)
        self._optimize_check.toggled.connect(self._on_option_changed)
        self._strip_meta_check.toggled.connect(self._on_option_changed)
        self._skip_if_larger_check.toggled.connect(self._on_option_changed)
        self._color_mode_combo.currentIndexChanged.connect(self._on_option_changed)
        self._quantize_check.toggled.connect(self._on_quantize_toggled)
        self._max_colors_spin.valueChanged.connect(self._on_option_changed)
        self._quantize_method_combo.currentIndexChanged.connect(self._on_option_changed)
        self._dither_combo.currentIndexChanged.connect(self._on_option_changed)

        # File management
        self._add_files_btn.clicked.connect(self._on_add_files)
        self._add_folder_btn.clicked.connect(self._on_add_folder)
        self._clear_btn.clicked.connect(self._on_clear)
        self._select_output_btn.clicked.connect(self._on_select_output)
        self._optimize_btn.clicked.connect(self._on_optimize)
        self._overwrite_check.toggled.connect(self._on_overwrite_toggled)
        # GPU compression
        self._gpu_format_combo.currentIndexChanged.connect(self._on_gpu_format_changed)

    # ------------------------------------------------------------------
    # Saved defaults
    # ------------------------------------------------------------------

    def _apply_saved_defaults(self):
        """Load saved optimizer defaults from app_config and apply to controls."""
        if not self.parent_app or not hasattr(self.parent_app, "app_config"):
            return

        defaults = self.parent_app.app_config.get_optimizer_defaults()
        if not defaults:
            return

        self._applying_preset = True
        try:
            # Compression settings
            if "compress_level" in defaults:
                self._compress_level_spin.setValue(int(defaults["compress_level"]))
            if "optimize" in defaults:
                self._optimize_check.setChecked(bool(defaults["optimize"]))
            if "strip_metadata" in defaults:
                self._strip_meta_check.setChecked(bool(defaults["strip_metadata"]))
            if "skip_if_larger" in defaults:
                self._skip_if_larger_check.setChecked(bool(defaults["skip_if_larger"]))

            # Color mode — find by enum value
            if "color_mode" in defaults:
                color_labels = list(COLOR_MODE_LABELS.keys())
                for i, label in enumerate(color_labels):
                    if COLOR_MODE_LABELS[label].value == defaults["color_mode"]:
                        self._color_mode_combo.setCurrentIndex(i)
                        break

            # Quantization
            if "quantize" in defaults:
                self._quantize_check.setChecked(bool(defaults["quantize"]))
            if "max_colors" in defaults:
                self._max_colors_spin.setValue(int(defaults["max_colors"]))

            if "quantize_method" in defaults:
                method_labels = list(QUANTIZE_METHOD_LABELS.keys())
                for i, label in enumerate(method_labels):
                    if (
                        QUANTIZE_METHOD_LABELS[label].value
                        == defaults["quantize_method"]
                    ):
                        self._quantize_method_combo.setCurrentIndex(i)
                        break

            if "dither" in defaults:
                dither_labels = list(DITHER_METHOD_LABELS.keys())
                for i, label in enumerate(dither_labels):
                    if DITHER_METHOD_LABELS[label].value == defaults["dither"]:
                        self._dither_combo.setCurrentIndex(i)
                        break

            # Output
            if "overwrite" in defaults:
                self._overwrite_check.setChecked(bool(defaults["overwrite"]))

            # GPU texture compression defaults
            if "texture_format" in defaults:
                idx = self._gpu_format_combo.findData(defaults["texture_format"])
                if idx >= 0:
                    self._gpu_format_combo.setCurrentIndex(idx)

            if "texture_container" in defaults:
                idx = self._gpu_container_combo.findData(defaults["texture_container"])
                if idx >= 0:
                    self._gpu_container_combo.setCurrentIndex(idx)

            if "generate_mipmaps" in defaults:
                self._gpu_mipmap_check.setChecked(bool(defaults["generate_mipmaps"]))

            # Preset — apply last so individual settings don't get overridden
            if "preset" in defaults:
                preset_keys = list(PRESET_LABELS.values())
                for i, preset in enumerate(preset_keys):
                    if preset.value == defaults["preset"]:
                        self._preset_combo.setCurrentIndex(i)
                        break

            self._update_quantize_visibility()
        finally:
            self._applying_preset = False

    # ------------------------------------------------------------------
    # Preset logic
    # ------------------------------------------------------------------

    def _on_preset_changed(self, index: int):
        """Apply the selected preset to all option controls."""
        if self._applying_preset:
            return

        preset_keys = list(PRESET_LABELS.values())
        if 0 <= index < len(preset_keys):
            preset = preset_keys[index]
            if preset is not OptimizePreset.CUSTOM:
                self._apply_preset(preset)

    def _apply_preset(self, preset: OptimizePreset) -> None:
        """Programmatically set all controls to match a preset."""
        options = PRESET_OPTIONS.get(preset)
        if not options:
            return

        self._applying_preset = True
        try:
            self._compress_level_spin.setValue(options.compress_level)
            self._optimize_check.setChecked(options.optimize)
            self._strip_meta_check.setChecked(options.strip_metadata)
            self._skip_if_larger_check.setChecked(options.skip_if_larger)

            # Color mode
            color_labels = list(COLOR_MODE_LABELS.keys())
            for i, label in enumerate(color_labels):
                if COLOR_MODE_LABELS[label] is options.color_mode:
                    self._color_mode_combo.setCurrentIndex(i)
                    break

            # Quantization
            self._quantize_check.setChecked(options.quantize)
            self._max_colors_spin.setValue(options.max_colors)

            method_labels = list(QUANTIZE_METHOD_LABELS.keys())
            for i, label in enumerate(method_labels):
                if QUANTIZE_METHOD_LABELS[label] is options.quantize_method:
                    self._quantize_method_combo.setCurrentIndex(i)
                    break

            dither_labels = list(DITHER_METHOD_LABELS.keys())
            for i, label in enumerate(dither_labels):
                if DITHER_METHOD_LABELS[label] is options.dither:
                    self._dither_combo.setCurrentIndex(i)
                    break

            self._update_quantize_visibility()
        finally:
            self._applying_preset = False

    def _on_option_changed(self):
        """Any manual option change switches the preset combo to Custom."""
        if self._applying_preset:
            return
        custom_idx = len(PRESET_LABELS) - 1  # Custom is last
        if self._preset_combo.currentIndex() != custom_idx:
            self._applying_preset = True
            self._preset_combo.setCurrentIndex(custom_idx)
            self._applying_preset = False

    def _on_quantize_toggled(self, _checked: bool):
        """Toggle quantization sub-controls and switch preset to Custom."""
        self._update_quantize_visibility()
        self._on_option_changed()

    def _update_quantize_visibility(self):
        """Show/hide quantization sub-controls based on the checkbox."""
        enabled = self._quantize_check.isChecked()
        self._max_colors_spin.setVisible(enabled)
        self._max_colors_label.setVisible(enabled)
        self._quantize_method_combo.setVisible(enabled)
        self._quantize_method_label.setVisible(enabled)
        self._dither_combo.setVisible(enabled)
        self._dither_label.setVisible(enabled)

    # ------------------------------------------------------------------
    # File management slots
    # ------------------------------------------------------------------

    def _on_add_files(self):
        start_dir = ""
        if self.parent_app and hasattr(self.parent_app, "app_config"):
            start_dir = self.parent_app.app_config.get_last_input_directory()

        exts = " ".join(f"*{e}" for e in sorted(SUPPORTED_EXTENSIONS))
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr("Select images to optimize"),
            start_dir,
            f"{self.tr('Images')} ({exts});;{self.tr('All files')} (*.*)",
        )
        if files:
            self._add_paths(files)

    def _on_add_folder(self):
        start_dir = ""
        if self.parent_app and hasattr(self.parent_app, "app_config"):
            start_dir = self.parent_app.app_config.get_last_input_directory()

        folder = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select folder with images"),
            start_dir,
        )
        if folder:
            found = ImageOptimizer.collect_images(folder)
            if found:
                self._add_paths(found)
            else:
                QMessageBox.information(
                    self,
                    self.tr("No images found"),
                    self.tr("No supported image files found in the selected folder."),
                )

    def _on_clear(self):
        self._file_list.clear()
        self._file_tree.clear()
        self._update_file_count()

    def _on_select_output(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            self.tr("Select output folder"),
            (
                self._output_dir_label.text()
                if self._output_dir_label.text() != self.tr("No output folder selected")
                else ""
            ),
        )
        if folder:
            self._output_dir_label.setText(folder)

    def _on_overwrite_toggled(self, checked: bool):
        self._select_output_btn.setEnabled(not checked)
        self._output_dir_label.setEnabled(not checked)

    # ------------------------------------------------------------------
    # Optimize action
    # ------------------------------------------------------------------

    def _on_optimize(self):
        if not self._file_list:
            QMessageBox.warning(
                self,
                self.tr("No files"),
                self.tr("Please add image files before optimizing."),
            )
            return

        options = self._build_options()
        if options is None:
            return

        self._set_processing(True)

        # Open dedicated progress window
        self._progress_window = JobProgressWindow(
            self, title=self.tr("Optimizing Images")
        )
        self._progress_window.start(total_steps=len(self._file_list))
        self._progress_window.show()

        self._worker = OptimizerWorker(list(self._file_list), options)
        self._worker.progress_updated.connect(self._on_progress)
        self._worker.log_message.connect(self._on_log_message)
        self._worker.optimize_completed.connect(self._on_completed)
        self._worker.optimize_failed.connect(self._on_failed)
        self._worker.start()

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------

    def _on_progress(self, current: int, total: int, filename: str):
        if self._progress_window is not None:
            self._progress_window.update_progress(current, total, filename)

    def _on_log_message(self, message: str):
        """Append a log line from the optimizer worker to the console."""
        # Strip the [ImageOptimizer] prefix for cleaner UI display
        display = message
        if display.startswith("[ImageOptimizer]"):
            display = display[len("[ImageOptimizer]") :].lstrip()
        if self._progress_window is not None:
            self._progress_window.append_log(display)

    def _on_completed(self, results: list):
        self._set_processing(False)

        success_count = 0
        skipped_count = 0
        total_saved = 0
        total_original = 0
        error_details: List[str] = []

        for result in results:
            result: OptimizeResult
            item = self._find_tree_item(result.source_path)
            if item is None:
                continue

            if result.success:
                if result.skipped:
                    skipped_count += 1
                    item.setText(2, "\u2298 Skipped")
                    item.setToolTip(
                        2,
                        self.tr(
                            "Skipped: optimized file was not smaller than original"
                        ),
                    )
                else:
                    success_count += 1
                    total_saved += result.savings_bytes
                    total_original += result.original_size

                    new_size = ImageOptimizer.format_size(result.optimized_size)
                    if result.savings_percent >= 0:
                        change = f"-{result.savings_percent:.1f}%"
                        item.setText(2, f"\u2713 {change}")
                    else:
                        change = f"+{abs(result.savings_percent):.1f}%"
                        item.setText(2, f"\u26a0 {change}")
                    item.setText(1, new_size)
                    tooltip = self.tr("Optimized: {old} \u2192 {new}").format(
                        old=ImageOptimizer.format_size(result.original_size),
                        new=new_size,
                    )
                    if result.ssim >= 0:
                        tooltip += f"\nSSIM: {result.ssim:.4f}"
                    item.setToolTip(2, tooltip)
            else:
                error_msg = result.error or "Unknown error"
                short_error = error_msg.split("\n")[0][:60]
                item.setText(2, f"\u2717 {short_error}")
                item.setToolTip(2, error_msg)
                error_details.append(
                    f"{os.path.basename(result.source_path)}: {error_msg}"
                )

        # Summary
        failed = len(results) - success_count - skipped_count
        if total_original > 0:
            pct = (total_saved / total_original) * 100.0
            summary = self.tr(
                "Done! {optimized} optimized, {skipped} skipped, "
                "{failed} failed. "
                "Saved {saved} ({percent:.1f}% reduction)."
            ).format(
                optimized=success_count,
                skipped=skipped_count,
                failed=failed,
                saved=ImageOptimizer.format_size(total_saved),
                percent=pct,
            )
        else:
            summary = self.tr(
                "Done! {optimized} optimized, {skipped} skipped, " "{failed} failed."
            ).format(
                optimized=success_count,
                skipped=skipped_count,
                failed=failed,
            )

        # Show error dialog if any files failed
        if error_details:
            detail_text = "\n\n".join(error_details)
            error_box = QMessageBox(self)
            error_box.setIcon(QMessageBox.Icon.Warning)
            error_box.setWindowTitle(
                self.tr("{count} file(s) failed").format(count=len(error_details))
            )
            error_box.setText(
                self.tr(
                    "{count} file(s) could not be optimized. " "See details below."
                ).format(count=len(error_details))
            )
            error_box.setDetailedText(detail_text)
            error_box.exec()

        # Finalize progress window
        if self._progress_window is not None:
            self._progress_window.update_progress(len(results), len(results))
            self._progress_window.finish(success=not error_details, message=summary)

    def _on_failed(self, error: str):
        self._set_processing(False)

        # Finalize progress window
        if self._progress_window is not None:
            self._progress_window.finish(
                success=False, message=self.tr("Optimization Failed")
            )

        QMessageBox.critical(
            self,
            self.tr("Optimization Failed"),
            self.tr("An error occurred during optimization:\n{error}").format(
                error=error
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _add_paths(self, paths: List[str]):
        """Add file paths to the list, skipping duplicates."""
        existing = set(self._file_list)
        for p in paths:
            if p not in existing and Path(p).suffix.lower() in SUPPORTED_EXTENSIONS:
                self._file_list.append(p)
                existing.add(p)
                self._add_tree_item(p)
        self._update_file_count()

    def _add_tree_item(self, path: str):
        item = QTreeWidgetItem()
        item.setText(0, os.path.basename(path))
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        item.setText(1, ImageOptimizer.format_size(size))
        item.setText(2, "")
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        self._file_tree.addTopLevelItem(item)

    def _find_tree_item(self, path: str) -> Optional[QTreeWidgetItem]:
        for i in range(self._file_tree.topLevelItemCount()):
            item = self._file_tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == path:
                return item
        return None

    def _update_file_count(self):
        count = len(self._file_list)
        if count == 0:
            self._file_count_label.setText(self.tr("No files selected"))
        else:
            self._file_count_label.setText(
                self.tr("{count} file(s) selected").format(count=count)
            )

    def _build_options(self) -> Optional[OptimizeOptions]:
        """Construct ``OptimizeOptions`` from current UI state."""
        overwrite = self._overwrite_check.isChecked()
        output_dir = ""

        if not overwrite:
            label_text = self._output_dir_label.text()
            if label_text == self.tr("No output folder selected") or not label_text:
                QMessageBox.warning(
                    self,
                    self.tr("No output folder"),
                    self.tr(
                        "Please select an output folder, or enable "
                        "'Overwrite originals'."
                    ),
                )
                return None
            output_dir = label_text

        # Resolve color mode
        color_labels = list(COLOR_MODE_LABELS.keys())
        cidx = self._color_mode_combo.currentIndex()
        color_mode = (
            COLOR_MODE_LABELS[color_labels[cidx]]
            if 0 <= cidx < len(color_labels)
            else ColorMode.KEEP
        )

        # Resolve quantize method
        quantize = self._quantize_check.isChecked()
        method_labels = list(QUANTIZE_METHOD_LABELS.keys())
        midx = self._quantize_method_combo.currentIndex()
        quantize_method = (
            QUANTIZE_METHOD_LABELS[method_labels[midx]]
            if 0 <= midx < len(method_labels)
            else QuantizeMethod.MEDIANCUT
        )

        # Resolve dither
        dither_labels = list(DITHER_METHOD_LABELS.keys())
        didx = self._dither_combo.currentIndex()
        dither = (
            DITHER_METHOD_LABELS[dither_labels[didx]]
            if 0 <= didx < len(dither_labels)
            else DitherMethod.FLOYD_STEINBERG
        )

        # Resolve GPU compression
        gpu_fmt = self._gpu_format_combo.currentData()
        texture_format = gpu_fmt if gpu_fmt and gpu_fmt != "none" else None
        texture_container = self._gpu_container_combo.currentData() or "dds"
        generate_mipmaps = self._gpu_mipmap_check.isChecked()

        return OptimizeOptions(
            compress_level=self._compress_level_spin.value(),
            optimize=self._optimize_check.isChecked(),
            color_mode=color_mode,
            quantize=quantize,
            quantize_method=quantize_method,
            max_colors=self._max_colors_spin.value(),
            dither=dither,
            strip_metadata=self._strip_meta_check.isChecked(),
            skip_if_larger=self._skip_if_larger_check.isChecked(),
            overwrite=overwrite,
            output_dir=output_dir,
            texture_format=texture_format,
            texture_container=texture_container,
            generate_mipmaps=generate_mipmaps,
        )

    def _set_processing(self, active: bool):
        self._optimize_btn.setEnabled(not active)
        self._add_files_btn.setEnabled(not active)
        self._add_folder_btn.setEnabled(not active)
        self._clear_btn.setEnabled(not active)

    def _on_gpu_format_changed(self, _index=None):
        """Show/hide container and mipmap controls based on GPU format."""
        fmt = self._gpu_format_combo.currentData()
        has_format = fmt is not None and fmt != "none"
        self._gpu_container_combo.setVisible(has_format)
        self._gpu_container_label.setVisible(has_format)
        self._gpu_mipmap_check.setVisible(has_format)

        # Show a one-time disclaimer when a GPU format is first selected
        if has_format and not getattr(self, "_gpu_disclaimer_shown", False):
            self._gpu_disclaimer_shown = True
            QMessageBox.information(
                self,
                self.tr("GPU Texture Compression"),
                self.tr(
                    "GPU texture compression produces hardware-specific formats "
                    "(DDS / KTX2) that are <b>not</b> regular image files.\n\n"
                    "Only use this when you know your target engine or renderer "
                    "supports the chosen format. Incorrect settings can produce "
                    "files that appear corrupted or fail to load.\n\n"
                    "Key points:\n"
                    "• DDS containers only support BC (DXT) formats; mobile "
                    "formats (ETC, ASTC, PVRTC) require KTX2.\n"
                    "• ASTC and PVRTC need external CLI tools installed "
                    "separately (astcenc / PVRTexToolCLI)."
                ),
            )
