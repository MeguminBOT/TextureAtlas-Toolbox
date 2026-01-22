#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Widgets and helpers that power the Extract tab in the GUI."""

import json
import os
import tempfile
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QDoubleSpinBox,
    QLineEdit,
    QFrame,
    QFileDialog,
    QMenu,
    QMessageBox,
)
from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QAction

from gui.base_tab_widget import BaseTabWidget
from utils.translation_manager import tr as translate
from utils.combo_options import (
    ANIMATION_FORMAT_OPTIONS,
    CROPPING_METHOD_OPTIONS,
    FILENAME_FORMAT_OPTIONS,
    FRAME_FORMAT_OPTIONS,
    FRAME_SELECTION_OPTIONS,
    get_display_texts,
    get_index_by_display,
    get_internal_by_index,
    populate_combobox,
)
from utils.ui_constants import (
    Labels,
    GroupTitles,
    SpinBoxConfig,
    ButtonLabels,
    DialogTitles,
    FileDialogTitles,
    Placeholders,
    MenuActions,
    TabTitles,
    configure_spinbox,
)

from gui.extractor.enhanced_list_widget import EnhancedListWidget
from utils.utilities import Utilities
from utils.duration_utils import (
    convert_duration,
    duration_to_milliseconds,
    get_duration_display_meta,
    load_duration_display_value,
    milliseconds_to_duration,
    resolve_native_duration_type,
)
from core.extractor.spritemap.metadata import (
    compute_symbol_lengths,
    extract_label_ranges,
)
from core.extractor.spritemap.normalizer import normalize_animation_document


class SpritesheetFileDialog(QFileDialog):
    """Custom file dialog for selecting spritesheet and metadata files.

    Extends QFileDialog to provide a more user-friendly experience when
    selecting multiple spritesheet files. In non-native mode, the dialog
    hides verbose filter details and provides an editable address bar for
    direct path entry, mimicking native dialog behavior.

    When ``use_native_dialog`` is True, the OS-native file picker is used
    instead, which shows full filter details but provides familiar navigation.

    Attributes:
        _address_line: QLineEdit used for direct path entry in the address bar.
    """

    tr = translate

    def __init__(
        self,
        parent,
        title,
        start_directory,
        name_filters,
        use_native_dialog=False,
    ):
        """Initialize the spritesheet file dialog.

        Args:
            parent: Parent widget for the dialog.
            title: Window title displayed in the dialog.
            start_directory: Initial directory to display.
            name_filters: List of file filter strings for the dropdown.
            use_native_dialog: When True, uses the OS-native file picker.
                When False, uses Qt's styled dialog with hidden filter
                details and an editable address bar.
        """
        super().__init__(parent, title, start_directory)
        self.setFileMode(QFileDialog.FileMode.ExistingFiles)
        self.setNameFilters(name_filters)
        self.setViewMode(QFileDialog.ViewMode.Detail)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, not use_native_dialog)
        if not use_native_dialog:
            self.setOption(QFileDialog.Option.HideNameFilterDetails, True)
            self.setLabelText(
                QFileDialog.DialogLabel.FileName, self.tr("Path or filenames")
            )
            self._tune_filename_entry()
            self._ensure_address_bar()

    def choose_files(self):
        """Execute the dialog and return selected file paths.

        Returns:
            list[str]: Paths of selected files, or empty list if cancelled.
        """
        return self.selectedFiles() if self.exec() else []

    def _tune_filename_entry(self):
        """Configure the filename entry field with placeholder text.

        Locates Qt's built-in filename edit widget and adds a helpful
        placeholder indicating users can paste paths or filenames.
        """
        file_name_edit = self.findChild(QLineEdit, "fileNameEdit")
        if not file_name_edit:
            return
        file_name_edit.setPlaceholderText(
            self.tr("Paste a path or space-separated files")
        )
        file_name_edit.setClearButtonEnabled(True)

    def _ensure_address_bar(self):
        """Set up an editable address bar for direct path navigation.

        Attempts to reuse Qt's built-in "Look in" combo box by making it
        editable. If that widget isn't found, injects a standalone line
        edit at the top of the dialog. The address bar syncs with directory
        changes and navigates when the user presses Enter.
        """
        location_combo = self.findChild(QComboBox, "lookInCombo")
        address_line = None

        if location_combo:
            location_combo.setEditable(True)
            location_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            address_line = location_combo.lineEdit()
        else:
            # Fallback: inject our own address bar at the top of the dialog layout.
            address_line = QLineEdit(self)
            address_line.setClearButtonEnabled(True)
            address_line.setMinimumWidth(200)
            layout = self.layout()
            if layout:
                layout.insertWidget(0, address_line)

        if not address_line:
            return

        self._address_line = address_line
        self._address_line.setPlaceholderText(self.tr("Type a path and press Enter"))
        self._address_line.returnPressed.connect(self._handle_address_entered)
        self.directoryEntered.connect(self._sync_address_line)
        self.currentChanged.connect(self._sync_address_line)
        self._sync_address_line(self.directory().absolutePath())

    def _handle_address_entered(self):
        """Navigate to the path entered in the address bar.

        Called when the user presses Enter in the address bar. Expands
        user home directory shortcuts (``~``) and changes the dialog's
        current directory.
        """
        if not hasattr(self, "_address_line"):
            return
        text = self._address_line.text().strip()
        if not text:
            return
        self.setDirectory(str(Path(text).expanduser()))

    def _sync_address_line(self, path):
        """Update the address bar to reflect the current directory.

        Connected to ``directoryEntered`` and ``currentChanged`` signals
        to keep the address bar synchronized with navigation.

        Args:
            path: Current directory path (str or Path object).
        """
        if not hasattr(self, "_address_line") or not self._address_line:
            return
        if isinstance(path, Path):
            path = str(path)
        self._address_line.setText(str(path))


class ExtractTabWidget(BaseTabWidget):
    """Widget for the Extract tab functionality."""

    tr = translate

    # Context for translating strings from ui_constants module
    UI_CONSTANTS_CONTEXT = "TextureAtlasToolboxApp"

    # Context for translating strings from duration_utils module
    DURATION_UTILS_CONTEXT = "ExtractTabWidget"

    def trc(self, text: str) -> str:
        """Translate a string from ui_constants using its proper context.

        Use this method for strings defined in ui_constants.py (Labels,
        GroupTitles, CheckBoxLabels, etc.) to ensure they are looked up
        in the correct translation context.

        Args:
            text: The string constant from ui_constants to translate.

        Returns:
            The translated string.
        """
        return QCoreApplication.translate(self.UI_CONSTANTS_CONTEXT, text)

    def trd(self, text: str) -> str:
        """Translate a string from duration_utils using its proper context.

        Use this method for strings defined in duration_utils.py
        (display_meta.label, display_meta.tooltip, display_meta.suffix)
        to ensure they are looked up in the correct translation context.

        Args:
            text: The string from duration_utils to translate.

        Returns:
            The translated string.
        """
        return QCoreApplication.translate(self.DURATION_UTILS_CONTEXT, text)

    def __init__(self, parent=None, use_existing_ui=False):
        """Initialize the Extract tab UI and hook into parent callbacks.

        Args:
            parent (QWidget | None): Main window containing shared state such as
                ``app_config`` and ``settings_manager``.
            use_existing_ui (bool): When ``True`` attaches to designer-built
                widgets that already exist on ``parent`` instead of building the
                layout programmatically.
        """
        super().__init__(parent, use_existing_ui)
        self._init_state()
        self._setup_ui()
        self.setup_connections()
        self.setup_default_values()

    def _init_state(self):
        """Initialize instance state before UI setup."""
        self.filter_single_frame_spritemaps = True
        self.use_native_file_dialog = False
        if self.parent_app and hasattr(self.parent_app, "app_config"):
            interface = self.parent_app.app_config.get("interface", {})
            self.filter_single_frame_spritemaps = interface.get(
                "filter_single_frame_spritemaps", True
            )
            self.use_native_file_dialog = interface.get("use_native_file_dialog", False)
        self.editor_composites = defaultdict(dict)

    def _setup_with_existing_ui(self):
        """Set up the widget using existing UI elements from the parent."""
        if not self.parent_app or not hasattr(self.parent_app, "ui"):
            return

        self.listbox_png = self.parent_app.ui.listbox_png
        self.listbox_data = self.parent_app.ui.listbox_data
        self.input_button = self.parent_app.ui.input_button
        self.output_button = self.parent_app.ui.output_button
        self.input_dir_label = self.parent_app.ui.input_dir_label
        self.output_dir_label = self.parent_app.ui.output_dir_label
        self.animation_export_group = self.parent_app.ui.animation_export_group
        self.frame_export_group = self.parent_app.ui.frame_export_group
        self.animation_format_combobox = self.parent_app.ui.animation_format_combobox
        self.frame_format_combobox = self.parent_app.ui.frame_format_combobox
        self.frame_rate_label = self.parent_app.ui.frame_rate_label
        self.frame_rate_entry = self.parent_app.ui.frame_rate_entry
        self.loop_delay_entry = self.parent_app.ui.loop_delay_entry
        self.min_period_entry = self.parent_app.ui.min_period_entry
        self.scale_entry = self.parent_app.ui.scale_entry
        self.threshold_entry = self.parent_app.ui.threshold_entry
        self.frame_scale_entry = self.parent_app.ui.frame_scale_entry
        self.frame_selection_combobox = self.parent_app.ui.frame_selection_combobox
        self.cropping_method_combobox = self.parent_app.ui.cropping_method_combobox
        self.resampling_method_combobox = self.parent_app.ui.resampling_method_combobox
        self.filename_format_combobox = self.parent_app.ui.filename_format_combobox
        self.filename_prefix_entry = self.parent_app.ui.filename_prefix_entry
        self.filename_suffix_entry = self.parent_app.ui.filename_suffix_entry
        self.advanced_filename_button = self.parent_app.ui.advanced_filename_button
        self.show_override_settings_button = (
            self.parent_app.ui.show_override_settings_button
        )
        self.override_spritesheet_settings_button = (
            self.parent_app.ui.override_spritesheet_settings_button
        )
        self.override_animation_settings_button = (
            self.parent_app.ui.override_animation_settings_button
        )
        self.start_process_button = self.parent_app.ui.start_process_button
        self.reset_button = self.parent_app.ui.reset_button

        if not hasattr(self.parent_app.ui, "compression_settings_button"):
            self.compression_settings_button = QPushButton(
                self.tr("Compression Settings")
            )
        else:
            self.compression_settings_button = (
                self.parent_app.ui.compression_settings_button
            )

        # Convert QListView to EnhancedListWidget if needed
        if hasattr(self.listbox_png, "add_item"):
            pass
        else:
            from gui.extractor.enhanced_list_widget import EnhancedListWidget

            parent_widget = self.listbox_png.parent()
            geometry = self.listbox_png.geometry()
            self.listbox_png.setParent(None)

            self.listbox_png = EnhancedListWidget(parent_widget)
            self.listbox_png.setGeometry(geometry)
            self.listbox_png.setObjectName("listbox_png")
            self.listbox_png.setAlternatingRowColors(False)
            self.listbox_png.setContextMenuPolicy(
                Qt.ContextMenuPolicy.CustomContextMenu
            )

            parent_widget = self.listbox_data.parent()
            geometry = self.listbox_data.geometry()
            self.listbox_data.setParent(None)

            self.listbox_data = EnhancedListWidget(parent_widget)
            self.listbox_data.setGeometry(geometry)
            self.listbox_data.setObjectName("listbox_data")
            self.listbox_data.setContextMenuPolicy(
                Qt.ContextMenuPolicy.CustomContextMenu
            )

    def _build_ui(self):
        """Set up the UI components for the extract tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        top_section = self.create_top_section()
        main_layout.addWidget(top_section)

        export_section = self.create_export_section()
        main_layout.addWidget(export_section)

        bottom_section = self.create_bottom_section()
        main_layout.addWidget(bottom_section)

    def create_top_section(self):
        """Create the top section with file lists and directory buttons."""
        top_widget = QWidget()
        layout = QHBoxLayout(top_widget)

        lists_widget = QWidget()
        lists_layout = QHBoxLayout(lists_widget)

        self.listbox_png = EnhancedListWidget()
        self.listbox_png.setObjectName("listbox_png")
        self.listbox_png.setFixedSize(200, 621)
        self.listbox_png.setAlternatingRowColors(False)
        self.listbox_png.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lists_layout.addWidget(self.listbox_png)

        self.listbox_data = EnhancedListWidget()
        self.listbox_data.setObjectName("listbox_data")
        self.listbox_data.setFixedSize(200, 621)
        self.listbox_data.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lists_layout.addWidget(self.listbox_data)

        layout.addWidget(lists_widget)

        dir_widget = QWidget()
        dir_layout = QVBoxLayout(dir_widget)

        self.input_button = QPushButton(self.tr("Select input directory"))
        self.input_button.setFixedSize(171, 24)
        dir_layout.addWidget(self.input_button)

        self.input_dir_label = QLabel(self.tr("No input directory selected"))
        self.input_dir_label.setFixedSize(451, 21)
        self.input_dir_label.setFrameShape(QFrame.Shape.NoFrame)
        self.input_dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dir_layout.addWidget(self.input_dir_label)

        self.output_button = QPushButton(self.tr("Select output directory"))
        self.output_button.setFixedSize(171, 24)
        dir_layout.addWidget(self.output_button)

        self.output_dir_label = QLabel(self.tr("No output directory selected"))
        self.output_dir_label.setFixedSize(451, 21)
        self.output_dir_label.setFrameShape(QFrame.Shape.NoFrame)
        self.output_dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dir_layout.addWidget(self.output_dir_label)

        dir_layout.addStretch()
        layout.addWidget(dir_widget)

        return top_widget

    def create_export_section(self):
        """Create the export settings section."""
        export_widget = QWidget()
        layout = QHBoxLayout(export_widget)

        self.animation_export_group = self.create_animation_export_group()
        layout.addWidget(self.animation_export_group)

        self.frame_export_group = self.create_frame_export_group()
        layout.addWidget(self.frame_export_group)

        return export_widget

    def create_animation_export_group(self):
        """Create the animation export group box."""
        group = QGroupBox(self.trc(GroupTitles.ANIMATION_EXPORT))
        group.setFixedSize(191, 331)
        group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group.setCheckable(True)
        group.setChecked(True)

        format_label = QLabel(self.trc(Labels.FORMAT))
        format_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        format_label.setGeometry(40, 30, 111, 16)
        format_label.setParent(group)

        self.animation_format_combobox = QComboBox(group)
        self.animation_format_combobox.setGeometry(10, 50, 171, 24)
        self.animation_format_combobox.addItems(
            get_display_texts(ANIMATION_FORMAT_OPTIONS)
        )

        self.frame_rate_label = QLabel(self.trc(Labels.FRAME_RATE))
        self.frame_rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_rate_label.setGeometry(40, 80, 111, 16)
        self.frame_rate_label.setParent(group)

        self.frame_rate_entry = QSpinBox(group)
        self.frame_rate_entry.setGeometry(10, 100, 171, 24)
        configure_spinbox(self.frame_rate_entry, SpinBoxConfig.FRAME_RATE)

        loop_delay_label = QLabel(self.trc(Labels.LOOP_DELAY))
        loop_delay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loop_delay_label.setGeometry(40, 130, 111, 16)
        loop_delay_label.setParent(group)

        self.loop_delay_entry = QSpinBox(group)
        self.loop_delay_entry.setGeometry(10, 150, 171, 24)
        self.loop_delay_entry.setRange(0, 10000)
        self.loop_delay_entry.setValue(250)

        min_period_label = QLabel(self.trc(Labels.MIN_PERIOD))
        min_period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        min_period_label.setGeometry(40, 180, 111, 16)
        min_period_label.setParent(group)

        self.min_period_entry = QSpinBox(group)
        self.min_period_entry.setGeometry(10, 200, 171, 24)
        self.min_period_entry.setRange(0, 10000)
        self.min_period_entry.setValue(0)

        scale_label = QLabel(self.trc(Labels.SCALE))
        scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scale_label.setGeometry(40, 230, 111, 16)
        scale_label.setParent(group)

        self.scale_entry = QDoubleSpinBox(group)
        self.scale_entry.setGeometry(10, 250, 171, 24)
        configure_spinbox(self.scale_entry, SpinBoxConfig.SCALE)

        threshold_label = QLabel(self.trc(Labels.ALPHA_THRESHOLD))
        threshold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        threshold_label.setGeometry(40, 280, 111, 16)
        threshold_label.setParent(group)

        self.threshold_entry = QSpinBox(group)
        self.threshold_entry.setGeometry(10, 300, 171, 24)
        self.threshold_entry.setRange(0, 100)
        self.threshold_entry.setValue(50)

        return group

    def create_frame_export_group(self):
        """Create the frame export group box."""
        group = QGroupBox(self.trc(GroupTitles.FRAME_EXPORT))
        group.setFixedSize(191, 331)
        group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group.setCheckable(True)
        group.setChecked(True)

        format_label = QLabel(self.trc(Labels.FORMAT))
        format_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        format_label.setGeometry(40, 30, 111, 16)
        format_label.setParent(group)

        self.frame_format_combobox = QComboBox(group)
        self.frame_format_combobox.setGeometry(10, 50, 171, 24)
        self.frame_format_combobox.addItems(get_display_texts(FRAME_FORMAT_OPTIONS))

        selection_label = QLabel(self.trc(Labels.FRAME_SELECTION_TITLE))
        selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        selection_label.setGeometry(40, 80, 111, 16)
        selection_label.setParent(group)

        self.frame_selection_combobox = QComboBox(group)
        self.frame_selection_combobox.setGeometry(10, 100, 171, 24)
        populate_combobox(
            self.frame_selection_combobox, FRAME_SELECTION_OPTIONS, self.tr
        )

        scale_label = QLabel(self.trc(Labels.FRAME_SCALE))
        scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scale_label.setGeometry(40, 130, 111, 16)
        scale_label.setParent(group)

        self.frame_scale_entry = QDoubleSpinBox(group)
        self.frame_scale_entry.setGeometry(10, 150, 171, 24)
        configure_spinbox(self.frame_scale_entry, SpinBoxConfig.FRAME_SCALE)

        resampling_label = QLabel(self.trc(Labels.RESAMPLING))
        resampling_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        resampling_label.setGeometry(40, 180, 111, 16)
        resampling_label.setParent(group)

        self.resampling_method_combobox = QComboBox(group)
        self.resampling_method_combobox.setGeometry(10, 200, 171, 24)
        self.resampling_method_combobox.addItems(
            ["Nearest", "Bilinear", "Bicubic", "Lanczos", "Box", "Hamming"]
        )

        self.compression_settings_button = QPushButton(
            self.trc(ButtonLabels.COMPRESSION_SETTINGS)
        )
        self.compression_settings_button.setGeometry(10, 240, 171, 24)
        self.compression_settings_button.setParent(group)

        return group

    def create_bottom_section(self):
        """Create the bottom section with filename settings and buttons."""
        bottom_widget = QWidget()
        layout = QVBoxLayout(bottom_widget)

        filename_section = self.create_filename_section()
        layout.addWidget(filename_section)

        buttons_section = self.create_buttons_section()
        layout.addWidget(buttons_section)

        return bottom_widget

    def create_filename_section(self):
        """Create the filename settings section."""
        filename_widget = QWidget()
        layout = QHBoxLayout(filename_widget)

        cropping_label = QLabel(self.trc(Labels.CROPPING_METHOD))
        cropping_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(cropping_label)

        self.cropping_method_combobox = QComboBox()
        populate_combobox(
            self.cropping_method_combobox, CROPPING_METHOD_OPTIONS, self.tr
        )
        layout.addWidget(self.cropping_method_combobox)

        format_label = QLabel(self.trc(Labels.FILENAME_FORMAT))
        layout.addWidget(format_label)

        self.filename_format_combobox = QComboBox()
        populate_combobox(
            self.filename_format_combobox, FILENAME_FORMAT_OPTIONS, self.tr
        )
        layout.addWidget(self.filename_format_combobox)

        prefix_label = QLabel(self.trc(Labels.PREFIX))
        layout.addWidget(prefix_label)

        self.filename_prefix_entry = QLineEdit()
        layout.addWidget(self.filename_prefix_entry)

        suffix_label = QLabel(self.trc(Labels.SUFFIX))
        layout.addWidget(suffix_label)

        self.filename_suffix_entry = QLineEdit()
        layout.addWidget(self.filename_suffix_entry)

        return filename_widget

    def create_buttons_section(self):
        """Create the control buttons section."""
        buttons_widget = QWidget()
        layout = QHBoxLayout(buttons_widget)

        self.advanced_filename_button = QPushButton(
            self.tr("Advanced filename options")
        )
        layout.addWidget(self.advanced_filename_button)

        self.show_override_settings_button = QPushButton(
            self.tr("Show override settings")
        )
        layout.addWidget(self.show_override_settings_button)

        self.override_spritesheet_settings_button = QPushButton(
            self.tr("Override spritesheet settings")
        )
        layout.addWidget(self.override_spritesheet_settings_button)

        self.override_animation_settings_button = QPushButton(
            self.tr("Override animation settings")
        )
        layout.addWidget(self.override_animation_settings_button)

        self.reset_button = QPushButton(self.trc(ButtonLabels.RESET))
        layout.addWidget(self.reset_button)

        self.start_process_button = QPushButton(self.tr("Start process"))
        layout.addWidget(self.start_process_button)

        return buttons_widget

    def setup_connections(self):
        """Set up signal-slot connections."""
        if not self.parent_app:
            return

        if hasattr(self, "input_button"):
            self.input_button.clicked.connect(self.select_directory)
        if hasattr(self, "output_button"):
            self.output_button.clicked.connect(self.select_output_directory)

        if hasattr(self, "start_process_button"):
            self.start_process_button.clicked.connect(self.parent_app.start_process)
        if hasattr(self, "reset_button"):
            self.reset_button.clicked.connect(self.clear_filelist)
        if hasattr(self, "advanced_filename_button"):
            self.advanced_filename_button.clicked.connect(
                self.parent_app.create_find_and_replace_window
            )
        if hasattr(self, "show_override_settings_button"):
            self.show_override_settings_button.clicked.connect(
                self.parent_app.create_settings_window
            )
        if hasattr(self, "override_spritesheet_settings_button"):
            self.override_spritesheet_settings_button.clicked.connect(
                self.override_spritesheet_settings
            )
        if hasattr(self, "override_animation_settings_button"):
            self.override_animation_settings_button.clicked.connect(
                self.override_animation_settings
            )
        if hasattr(self, "compression_settings_button"):
            self.compression_settings_button.clicked.connect(
                self.parent_app.show_compression_settings
            )

        if hasattr(self, "listbox_png"):
            self.listbox_png.currentItemChanged.connect(self.on_select_spritesheet)
            self.listbox_png.currentItemChanged.connect(self.update_ui_state)
            self.listbox_png.itemDoubleClicked.connect(self.on_double_click_spritesheet)
            self.listbox_png.customContextMenuRequested.connect(
                self.show_listbox_png_menu
            )

        if hasattr(self, "listbox_data"):
            self.listbox_data.itemDoubleClicked.connect(self.on_double_click_animation)
            self.listbox_data.currentItemChanged.connect(self.update_ui_state)
            self.listbox_data.customContextMenuRequested.connect(
                self.show_listbox_data_menu
            )

        if hasattr(self, "animation_format_combobox"):
            self.animation_format_combobox.currentTextChanged.connect(
                self.on_animation_format_change
            )
        if hasattr(self, "frame_format_combobox"):
            self.frame_format_combobox.currentTextChanged.connect(
                self.on_frame_format_change
            )

        if hasattr(self, "animation_export_group"):
            self.animation_export_group.toggled.connect(self.update_ui_state)
        if hasattr(self, "frame_export_group"):
            self.frame_export_group.toggled.connect(self.update_ui_state)

    def setup_default_values(self):
        """Set up default values from app config."""
        if self.parent_app and hasattr(self.parent_app, "app_config"):
            defaults = (
                self.parent_app.app_config.get_extraction_defaults()
                if hasattr(self.parent_app.app_config, "get_extraction_defaults")
                else {}
            )

            duration_ms = defaults.get("duration", 42)
            stored_display_value = defaults.get("duration_display_value")
            stored_display_type = defaults.get("duration_display_type")

            self.loop_delay_entry.setValue(defaults.get("delay", 250))
            self.min_period_entry.setValue(defaults.get("period", 0))
            self.scale_entry.setValue(defaults.get("scale", 1.0))
            self.threshold_entry.setValue(defaults.get("threshold", 0.5) * 100.0)
            self.frame_scale_entry.setValue(defaults.get("frame_scale", 1.0))

            self.animation_export_group.setChecked(
                defaults.get("animation_export", True)
            )
            self.frame_export_group.setChecked(defaults.get("frame_export", True))

            if "animation_format" in defaults:
                format_index = self.get_animation_format_index(
                    defaults["animation_format"]
                )
                self.animation_format_combobox.setCurrentIndex(format_index)

            if "frame_format" in defaults:
                format_index = self.get_frame_format_index(defaults["frame_format"])
                self.frame_format_combobox.setCurrentIndex(format_index)

            # Set default resampling method (Nearest = index 0)
            resampling_index = self.get_resampling_method_index(
                defaults.get("resampling_method", "Nearest")
            )
            self.resampling_method_combobox.setCurrentIndex(resampling_index)

            if "frame_selection" in defaults:
                idx = self.frame_selection_combobox.findData(
                    defaults["frame_selection"]
                )
                if idx >= 0:
                    self.frame_selection_combobox.setCurrentIndex(idx)

            if "crop_option" in defaults:
                idx = self.cropping_method_combobox.findData(defaults["crop_option"])
                if idx >= 0:
                    self.cropping_method_combobox.setCurrentIndex(idx)

            if "filename_format" in defaults:
                idx = self.filename_format_combobox.findData(
                    defaults["filename_format"]
                )
                if idx >= 0:
                    self.filename_format_combobox.setCurrentIndex(idx)

            if "filename_prefix" in defaults:
                self.filename_prefix_entry.setText(defaults["filename_prefix"])
            if "filename_suffix" in defaults:
                self.filename_suffix_entry.setText(defaults["filename_suffix"])

            self._set_duration_spinbox_from_stored(
                duration_ms, stored_display_value, stored_display_type
            )

        self.update_frame_rate_display()

    def update_frame_rate_display(self):
        """Update frame rate label and spinbox based on duration input type setting.

        Configures the spinbox label, range, value, and tooltip according to the
        selected duration input type (fps, native, deciseconds, centiseconds,
        or milliseconds). When the duration type changes, the current value is
        converted to the new unit.
        """
        duration_type = self._get_duration_input_type()
        anim_format = self._get_animation_format()
        display_meta = get_duration_display_meta(duration_type, anim_format)
        resolved_type = display_meta.resolved_type
        duration_tooltip = self.trd(display_meta.tooltip)

        prev_type = getattr(self, "_prev_duration_type", resolved_type)
        current_value = self.frame_rate_entry.value()

        # Convert current value to new duration type
        if prev_type != resolved_type:
            converted_value = convert_duration(
                current_value, prev_type, resolved_type, anim_format
            )
        else:
            converted_value = current_value

        # Store the current resolved type for next conversion
        self._prev_duration_type = resolved_type

        self.frame_rate_label.setText(self.trd(display_meta.label))
        self.frame_rate_entry.setRange(display_meta.min_value, display_meta.max_value)
        self.frame_rate_entry.setSuffix(self.trd(display_meta.suffix))

        self.frame_rate_entry.setValue(converted_value)
        self.frame_rate_label.setToolTip(duration_tooltip)
        self.frame_rate_entry.setToolTip(duration_tooltip)

    def get_resampling_method_index(self, method_name):
        """Map a resampling method name to its combobox index.

        Args:
            method_name: One of ``"Nearest"``, ``"Bilinear"``, ``"Bicubic"``,
                ``"Lanczos"``, ``"Box"``, or ``"Hamming"``.

        Returns:
            The zero-based index, or ``0`` (Nearest) if the name is unrecognized.
        """
        method_map = {
            "Nearest": 0,
            "Bilinear": 1,
            "Bicubic": 2,
            "Lanczos": 3,
            "Box": 4,
            "Hamming": 5,
        }
        return method_map.get(method_name, 0)  # Default to Nearest

    def get_animation_format_index(self, format_name: str) -> int:
        """Map an animation format name to its combobox index.

        Args:
            format_name: One of ``"GIF"``, ``"WebP"``, or ``"APNG"``.

        Returns:
            The zero-based index, or ``0`` if the name is unrecognized.
        """
        return get_index_by_display(ANIMATION_FORMAT_OPTIONS, format_name)

    def get_frame_format_index(self, format_name: str) -> int:
        """Map a frame format name to its combobox index.

        Args:
            format_name: One of ``"AVIF"``, ``"BMP"``, ``"DDS"``, ``"PNG"``,
                ``"TGA"``, ``"TIFF"``, or ``"WebP"``.

        Returns:
            The zero-based index, or ``0`` if the name is unrecognized.
        """
        return get_index_by_display(FRAME_FORMAT_OPTIONS, format_name)

    def select_directory(self):
        """Opens a directory selection dialog and populates the spritesheet list."""
        if not self.parent_app:
            return

        start_directory = self.parent_app.app_config.get_last_input_directory()

        directory = QFileDialog.getExistingDirectory(
            self,
            self.trc(FileDialogTitles.SELECT_INPUT_DIR),
            start_directory,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )

        if directory:
            self.parent_app.app_config.set_last_input_directory(directory)
            self.input_dir_label.setText(directory)
            self.populate_spritesheet_list(directory)

            self.parent_app.settings_manager.animation_settings.clear()
            self.parent_app.settings_manager.spritesheet_settings.clear()

    def select_output_directory(self):
        """Opens a directory selection dialog for output directory."""
        if not self.parent_app:
            return

        start_directory = self.parent_app.app_config.get_last_output_directory()

        directory = QFileDialog.getExistingDirectory(
            self,
            self.trc(FileDialogTitles.SELECT_OUTPUT_DIR),
            start_directory,
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks,
        )

        if directory:
            self.parent_app.app_config.set_last_output_directory(directory)
            self.output_dir_label.setText(directory)

    def select_files_manually(self):
        """Opens a file selection dialog for manual file selection."""
        if not self.parent_app:
            return

        start_directory = self.parent_app.app_config.get_last_input_directory()
        interface = self.parent_app.app_config.get("interface", {})
        use_native_dialog = interface.get("use_native_file_dialog", False)

        dialog = SpritesheetFileDialog(
            self,
            self.trc(FileDialogTitles.SELECT_FILES),
            start_directory,
            self.SPRITESHEET_METADATA_FILTERS,
            use_native_dialog,
        )

        files = dialog.choose_files()

        if files:
            if files:
                first_file_dir = os.path.dirname(files[0])
                self.parent_app.app_config.set_last_input_directory(first_file_dir)

            if (
                hasattr(self.parent_app, "manual_selection_temp_dir")
                and self.parent_app.manual_selection_temp_dir
            ):
                try:
                    shutil.rmtree(
                        self.parent_app.manual_selection_temp_dir, ignore_errors=True
                    )
                except Exception:
                    pass

            self.parent_app.manual_selection_temp_dir = tempfile.mkdtemp(
                prefix="texture_atlas_manual_"
            )
            copied_files = self._copy_files_to_temp(
                files, Path(self.parent_app.manual_selection_temp_dir)
            )
            self.input_dir_label.setText(
                self.tr("Manual selection ({count} files)").format(
                    count=len(copied_files)
                )
            )
            self.populate_spritesheet_list_from_files(
                copied_files, self.parent_app.manual_selection_temp_dir
            )

    def populate_spritesheet_list(self, directory):
        """Populate the spritesheet listbox from a directory.

        Clears existing entries, scans for spritesheet image files, and
        registers any accompanying metadata files.

        Args:
            directory: Folder path to scan for spritesheets.
        """

        if not self.parent_app:
            return

        self.listbox_png.clear()
        self.listbox_data.clear()
        self.parent_app.data_dict.clear()

        directory_path = Path(directory)
        if not directory_path.exists():
            return

        image_files = []
        for ext in self.SUPPORTED_IMAGE_EXTENSIONS:
            image_files.extend(sorted(directory_path.glob(f"*{ext}")))

        for image_file in sorted(image_files):
            display_name = self._format_display_name(directory_path, image_file)
            self.listbox_png.add_item(display_name, str(image_file))
            self.find_data_files_for_spritesheet(
                image_file,
                search_directory=image_file.parent,
                display_name=display_name,
            )

        # Nested spritemap folders (Animation.json + matching spritemap json)
        nested_image_files = []
        for ext in self.SUPPORTED_IMAGE_EXTENSIONS:
            nested_image_files.extend(sorted(directory_path.rglob(f"*{ext}")))

        for image_file in sorted(nested_image_files):
            if image_file.parent == directory_path:
                continue
            animation_json = image_file.parent / "Animation.json"
            spritemap_json = image_file.parent / f"{image_file.stem}.json"
            if not (animation_json.exists() and spritemap_json.exists()):
                continue
            display_name = self._format_display_name(directory_path, image_file)
            if self.listbox_png.find_item_by_text(display_name):
                continue
            self.listbox_png.add_item(display_name, str(image_file))
            self.find_data_files_for_spritesheet(
                image_file,
                search_directory=image_file.parent,
                display_name=display_name,
            )

    def populate_spritesheet_list_from_files(self, files, temp_folder=None):
        """Populate the spritesheet listbox from manually selected files.

        Args:
            files: List of file paths selected by the user.
            temp_folder: Optional temporary folder used for manual selections.
        """

        if not self.parent_app:
            return

        self.listbox_png.clear()
        self.listbox_data.clear()
        self.parent_app.data_dict.clear()

        image_exts = {ext.lower() for ext in self.SUPPORTED_IMAGE_EXTENSIONS}

        for file_path in files:
            path = Path(file_path)
            if path.suffix.lower() in image_exts:
                display_name = self._format_display_name(
                    Path(temp_folder) if temp_folder else None, path
                )
                self.listbox_png.add_item(display_name, str(path))
                search_directory = Path(temp_folder) if temp_folder else path.parent
                self.find_data_files_for_spritesheet(
                    path,
                    search_directory=search_directory,
                    display_name=display_name,
                )

    def _format_display_name(
        self, base_directory: Optional[Path], spritesheet_path: Path
    ) -> str:
        """Format a spritesheet path as a user-friendly display label.

        When a base directory is provided, the path is shown relative to it
        using POSIX separators for consistency. Falls back to the filename
        alone if the spritesheet lies outside the base directory or no base
        is given.

        Args:
            base_directory: Root folder to compute relative paths from, or
                ``None`` to always use the filename.
            spritesheet_path: Absolute path to the spritesheet image.

        Returns:
            str: A forward-slash-separated relative path, or the bare filename.
        """

        if base_directory:
            try:
                relative = spritesheet_path.relative_to(base_directory)
                return relative.as_posix()
            except ValueError:
                pass
        return spritesheet_path.name

    def _copy_files_to_temp(self, files, temp_dir: Path):
        """Copy selected files into a staging directory, avoiding name collisions."""
        copied = []
        for file_path in files:
            src = Path(file_path)
            if not src.exists():
                continue
            dest = temp_dir / src.name
            counter = 1
            while dest.exists():
                dest = temp_dir / f"{src.stem}_{counter}{src.suffix}"
                counter += 1
            try:
                shutil.copy2(src, dest)
                copied.append(dest)
            except Exception:
                continue
        return copied

    SUPPORTED_IMAGE_EXTENSIONS = (
        ".png",
        ".jpg",
        ".jpeg",
        ".avif",
        ".bmp",
        ".tga",
        ".tiff",
        ".webp",
    )

    SUPPORTED_METADATA_EXTENSIONS = (
        ".json",
        ".xml",
        ".txt",
        ".plist",
        ".atlas",
        ".css",
        ".tpsheet",
        ".tpset",
        ".paper2dsprites",
    )

    SPRITESHEET_METADATA_FILTERS = [
        "All Spritesheet Files (*.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp *.xml *.txt *.json *.plist *.atlas *.css *.tpsheet *.tpset *.paper2dsprites)",
        "Spritesheets Images (*.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets XML (*.xml *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets JSON (*.json *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets TXT (*.txt *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets PLIST (*.plist *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets Atlas (*.atlas *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets CSS (*.css *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets TPSHEET (*.tpsheet *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets TPSET (*.tpset *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "Spritesheets PAPER2D (*.paper2dsprites *.png *.jpg *.jpeg *.avif *.bmp *.tga *.tiff *.webp)",
        "All files (*.*)",
    ]

    def find_data_files_for_spritesheet(
        self, spritesheet_path, search_directory=None, display_name=None
    ):
        """Locate and register metadata files accompanying a spritesheet.

        Scans the search directory for files matching the spritesheet's base
        name with supported extensions (.xml, .txt, .json, .plist, .atlas,
        .css, .tpsheet, .tpset, .paper2dsprites). Found files are stored in
        ``parent_app.data_dict`` keyed by the display name.

        Adobe Animate spritemaps receive special handling: when both
        ``Animation.json`` and a matching JSON file exist, symbol metadata
        is parsed and stored under the ``"spritemap"`` key.

        Args:
            spritesheet_path: Path to the spritesheet image (used to derive
                the base filename).
            search_directory: Folder to scan for metadata. Defaults to the
                spritesheet's parent directory.
            display_name: Key used in ``data_dict``. Defaults to the
                spritesheet filename if not provided.
        """

        if not self.parent_app:
            return

        spritesheet_path = Path(spritesheet_path)
        base_name = spritesheet_path.stem
        directory = (
            Path(search_directory) if search_directory else spritesheet_path.parent
        )

        record_key = display_name or spritesheet_path.name
        if record_key not in self.parent_app.data_dict:
            self.parent_app.data_dict[record_key] = {}

        xml_file = directory / f"{base_name}.xml"
        if xml_file.exists():
            self.parent_app.data_dict[record_key]["xml"] = str(xml_file)

        txt_file = directory / f"{base_name}.txt"
        if txt_file.exists():
            self.parent_app.data_dict[record_key]["txt"] = str(txt_file)

        plist_file = directory / f"{base_name}.plist"
        if plist_file.exists():
            self.parent_app.data_dict[record_key]["plist"] = str(plist_file)

        atlas_file = directory / f"{base_name}.atlas"
        if atlas_file.exists():
            self.parent_app.data_dict[record_key]["atlas"] = str(atlas_file)

        css_file = directory / f"{base_name}.css"
        if css_file.exists():
            self.parent_app.data_dict[record_key]["css"] = str(css_file)

        tpsheet_file = directory / f"{base_name}.tpsheet"
        if tpsheet_file.exists():
            self.parent_app.data_dict[record_key]["tpsheet"] = str(tpsheet_file)

        tpset_file = directory / f"{base_name}.tpset"
        if tpset_file.exists():
            self.parent_app.data_dict[record_key]["tpset"] = str(tpset_file)

        paper2d_file = directory / f"{base_name}.paper2dsprites"
        if paper2d_file.exists():
            self.parent_app.data_dict[record_key]["paper2dsprites"] = str(paper2d_file)

        # Check for spritemap with Animation.json (Adobe Animate)
        animation_json = directory / "Animation.json"
        spritemap_json = directory / f"{base_name}.json"
        if animation_json.exists() and spritemap_json.exists():
            symbol_map = self._build_spritemap_symbol_map(animation_json)
            self.parent_app.data_dict[record_key]["spritemap"] = {
                "type": "spritemap",
                "animation_json": str(animation_json),
                "spritemap_json": str(spritemap_json),
                "symbol_map": symbol_map,
            }
        elif spritemap_json.exists():
            # Look for standalone JSON files (Aseprite, TexturePacker JSON, etc.)
            # Only use if not already handled as spritemap above
            self.parent_app.data_dict[record_key]["json"] = str(spritemap_json)

    def _build_spritemap_symbol_map(self, animation_json_path):
        """Return a mapping of display labels to spritemap metadata entries.

        Args:
            animation_json_path: Path to ``Animation.json`` describing the Adobe
                Animate timeline.

        Returns:
            dict: Keys are human-friendly labels, values describe the original
                symbol, label, and estimated frame count.
        """
        symbol_map = {}

        def register_entry(display_name, entry_type, entry_value, frame_count):
            """Store entries with unique labels so symbols and labels never collide."""
            suffix = " (Timeline)" if entry_type == "timeline_label" else " (Symbol)"
            candidate = display_name
            if candidate in symbol_map:
                candidate = f"{display_name}{suffix}"
                counter = 2
                while candidate in symbol_map:
                    candidate = f"{display_name}{suffix} #{counter}"
                    counter += 1
            symbol_map[candidate] = {
                "type": entry_type,
                "value": entry_value,
                "frame_count": frame_count,
            }

        try:
            with open(animation_json_path, "r", encoding="utf-8") as animation_file:
                animation_json = normalize_animation_document(json.load(animation_file))

            symbol_lengths = compute_symbol_lengths(animation_json)

            for symbol in animation_json.get("SD", {}).get("S", []):
                raw_name = symbol.get("SN")
                if not raw_name:
                    continue
                frame_count = symbol_lengths.get(raw_name, 0)
                if self.filter_single_frame_spritemaps and frame_count <= 1:
                    continue
                display_name = Utilities.strip_trailing_digits(raw_name) or raw_name
                register_entry(display_name, "symbol", raw_name, frame_count)

            for label in extract_label_ranges(animation_json, None):
                label_name = label["name"]
                frame_count = label["end"] - label["start"]
                if self.filter_single_frame_spritemaps and frame_count <= 1:
                    continue
                register_entry(label_name, "timeline_label", label_name, frame_count)
        except Exception as exc:
            print(
                f"Error parsing spritemap animation metadata {animation_json_path}: {exc}"
            )
        return symbol_map

    def register_editor_composite(
        self,
        spritesheet_name: str,
        animation_name: str,
        editor_animation_id: str,
        definition: Optional[dict] = None,
    ):
        """Register an editor-created composite so it appears in the animation list.

        Stores the composite in ``editor_composites`` and persists alignment
        overrides to the settings manager when a definition is provided.
        Refreshes the animation list if the spritesheet is currently selected.

        Args:
            spritesheet_name: Display name of the parent spritesheet.
            animation_name: Label for the composite animation.
            editor_animation_id: Unique identifier assigned by the editor.
            definition: Optional dict containing frame layout and alignment
                data for the composite.
        """

        if not spritesheet_name or not animation_name or not editor_animation_id:
            return
        entries = self.editor_composites[spritesheet_name]
        entries[animation_name] = {
            "editor_id": editor_animation_id,
            "definition": definition,
        }
        if definition and hasattr(self.parent_app, "settings_manager"):
            sheet_settings = (
                self.parent_app.settings_manager.spritesheet_settings.setdefault(
                    spritesheet_name, {}
                )
            )
            composites = sheet_settings.setdefault("editor_composites", {})
            composites[animation_name] = definition

            alignment_overrides = definition.get("alignment")
            if alignment_overrides:
                full_name = f"{spritesheet_name}/{animation_name}"
                animation_settings = (
                    self.parent_app.settings_manager.animation_settings.setdefault(
                        full_name, {}
                    )
                )
                animation_settings["alignment_overrides"] = alignment_overrides
        current_item = self.listbox_png.currentItem()
        if current_item and current_item.text() == spritesheet_name:
            self.populate_animation_list(spritesheet_name)

    def _append_editor_composites_to_list(self, spritesheet_name: str):
        """Append editor-created composites to the animation listbox.

        Iterates over composites registered for the given spritesheet and adds
        any that are not already present in ``listbox_data``.

        Args:
            spritesheet_name: Display name of the spritesheet whose composites
                should be appended.
        """

        composites = self.editor_composites.get(spritesheet_name, {})
        for animation_name, entry in sorted(composites.items()):
            editor_id = entry.get("editor_id") if isinstance(entry, dict) else entry
            if self.listbox_data.find_item_by_text(animation_name):
                continue
            item = self.listbox_data.add_item(
                animation_name,
                {
                    "type": "editor_composite",
                    "editor_id": editor_id,
                    "name": animation_name,
                },
            )
            item.setToolTip(self.tr("Composite created in the Editor tab"))

    def on_select_spritesheet(self, current, previous):
        """Handle selection change in the spritesheet listbox.

        Triggers repopulation of the animation list for the newly selected
        spritesheet.

        Args:
            current: The newly selected QListWidgetItem, or ``None``.
            previous: The previously selected QListWidgetItem, or ``None``.
        """

        if not current or not self.parent_app:
            return

        spritesheet_name = current.text()
        self.populate_animation_list(spritesheet_name)

    def populate_animation_list(self, spritesheet_name):
        """Populate the animation listbox for a spritesheet.

        Clears the current list, parses associated metadata files using the
        appropriate parser, and appends any editor-created composites.

        Args:
            spritesheet_name: Display name (key in ``data_dict``) of the
                spritesheet to load animations for.
        """

        if not self.parent_app:
            return

        self.listbox_data.clear()

        if spritesheet_name not in self.parent_app.data_dict:
            # If no data files found, try to use the unknown parser
            self._populate_using_unknown_parser()
            self._append_editor_composites_to_list(spritesheet_name)
            return

        data_files = self.parent_app.data_dict[spritesheet_name]

        if isinstance(data_files, dict):
            if "xml" in data_files:
                try:
                    from parsers.xml_parser import XmlParser

                    xml_parser = XmlParser(
                        directory=str(Path(data_files["xml"]).parent),
                        xml_filename=Path(data_files["xml"]).name,
                    )
                    self._populate_animation_names(xml_parser.get_data())
                except Exception as e:
                    print(f"Error parsing XML: {e}")

            elif "txt" in data_files:
                try:
                    from parsers.txt_parser import TxtParser

                    txt_parser = TxtParser(
                        directory=str(Path(data_files["txt"]).parent),
                        txt_filename=Path(data_files["txt"]).name,
                    )
                    self._populate_animation_names(txt_parser.get_data())
                except Exception as e:
                    print(f"Error parsing TXT: {e}")

            elif "spritemap" in data_files:
                spritemap_info = data_files.get("spritemap", {})
                symbol_map = spritemap_info.get("symbol_map", {})
                if symbol_map:
                    for display_name in sorted(symbol_map.keys()):
                        target_data = symbol_map.get(display_name)
                        self.listbox_data.add_item(display_name, target_data)
                else:
                    try:
                        from parsers.spritemap_parser import SpritemapParser

                        animation_path = spritemap_info.get("animation_json")
                        if animation_path:
                            parser = SpritemapParser(
                                directory=str(Path(animation_path).parent),
                                animation_filename=Path(animation_path).name,
                                filter_single_frame=self.filter_single_frame_spritemaps,
                            )
                            self._populate_animation_names(parser.get_data())
                    except Exception as e:
                        print(f"Error parsing spritemap animations: {e}")

            elif "json" in data_files:
                self._parse_with_registry(data_files["json"])

            elif "plist" in data_files:
                self._parse_with_registry(data_files["plist"])

            elif "atlas" in data_files:
                self._parse_with_registry(data_files["atlas"])

            elif "css" in data_files:
                self._parse_with_registry(data_files["css"])

            elif "tpsheet" in data_files:
                self._parse_with_registry(data_files["tpsheet"])

            elif "tpset" in data_files:
                self._parse_with_registry(data_files["tpset"])

            elif "paper2dsprites" in data_files:
                self._parse_with_registry(data_files["paper2dsprites"])

            else:
                self._populate_unknown_parser_fallback()
        else:
            self._populate_unknown_parser_fallback()

        self._append_editor_composites_to_list(spritesheet_name)

    def _parse_with_registry(self, metadata_path: str):
        """Parse a metadata file using the ParserRegistry.

        Uses automatic format detection to find the appropriate parser
        and populate the animation list.

        Args:
            metadata_path: Path to the metadata file.
        """
        try:
            from parsers.parser_registry import ParserRegistry
            import inspect

            if not ParserRegistry._all_parsers:
                ParserRegistry.initialize()

            parser_cls = ParserRegistry.detect_parser(metadata_path)
            if parser_cls:
                filename = Path(metadata_path).name
                directory = str(Path(metadata_path).parent)

                sig = inspect.signature(parser_cls.__init__)
                params = list(sig.parameters.keys())

                filename_param = None
                for param in params:
                    if param.endswith("_filename") or param == "filename":
                        filename_param = param
                        break

                if filename_param:
                    parser = parser_cls(
                        directory=directory, **{filename_param: filename}
                    )
                else:
                    parser = parser_cls(directory=directory, filename=filename)

                self._populate_animation_names(parser.get_data())
            else:
                print(f"No parser found for: {metadata_path}")
                self._populate_unknown_parser_fallback()
        except Exception as e:
            print(f"Error parsing {metadata_path}: {e}")
            self._populate_unknown_parser_fallback()

    def _populate_unknown_parser_fallback(self):
        """Use the generic parser when nothing else recognized the source."""
        self._populate_using_unknown_parser()

    def _populate_using_unknown_parser(self):
        """Load animation names via the generic unknown-format parser."""

        try:
            from parsers.unknown_parser import UnknownParser

            current_item = self.listbox_png.currentItem()
            if not current_item:
                return

            spritesheet_path = current_item.data(Qt.ItemDataRole.UserRole)
            if not spritesheet_path:
                return

            unknown_parser = UnknownParser(
                directory=str(Path(spritesheet_path).parent),
                image_filename=Path(spritesheet_path).name,
            )
            self._populate_animation_names(unknown_parser.get_data())
        except Exception as exc:
            print(f"Error using unknown parser: {exc}")

    def _populate_animation_names(self, names):
        """Add animation names to the animation listbox.

        Args:
            names: Iterable of animation name strings to display.
        """

        if not self.listbox_data or not names:
            return

        add_item = getattr(self.listbox_data, "add_item", None)
        if callable(add_item):
            for name in sorted(names):
                add_item(name)
            return

        if hasattr(self.listbox_data, "addItem"):
            for name in sorted(names):
                self.listbox_data.addItem(name)

    def clear_filelist(self):
        """Clears the file list and resets settings."""
        if not self.parent_app:
            return

        if (
            hasattr(self.parent_app, "manual_selection_temp_dir")
            and self.parent_app.manual_selection_temp_dir
        ):
            try:
                import shutil

                shutil.rmtree(
                    self.parent_app.manual_selection_temp_dir, ignore_errors=True
                )
                self.parent_app.manual_selection_temp_dir = None
            except Exception:
                pass

        self.listbox_png.clear()
        self.listbox_data.clear()

        self.input_dir_label.setText(self.tr("No input directory selected"))
        self.output_dir_label.setText(self.tr("No output directory selected"))

        self.parent_app.settings_manager.animation_settings.clear()
        self.parent_app.settings_manager.spritesheet_settings.clear()
        self.parent_app.data_dict.clear()

        self.parent_app.settings_manager.animation_settings.clear()
        self.parent_app.settings_manager.spritesheet_settings.clear()
        self.parent_app.data_dict.clear()

    def delete_selected_spritesheet(self):
        """Delete one or more selected spritesheets and their settings."""
        if not self.parent_app:
            return

        selected_items = self.listbox_png.selectedItems()
        if not selected_items:
            current_item = self.listbox_png.currentItem()
            selected_items = [current_item] if current_item else []
        if not selected_items:
            return

        for item in selected_items:
            if item is None:
                continue
            spritesheet_name = item.text()
            if spritesheet_name in self.parent_app.data_dict:
                del self.parent_app.data_dict[spritesheet_name]

            row = self.listbox_png.row(item)
            if row >= 0:
                self.listbox_png.takeItem(row)

            self.parent_app.settings_manager.spritesheet_settings.pop(
                spritesheet_name, None
            )

        self.listbox_data.clear()

    def show_listbox_png_menu(self, position):
        """Display a context menu for the spritesheet listbox.

        Offers actions to open the spritesheet in the editor, override its
        settings, or remove it from the list.

        Args:
            position: Local coordinates where the user right-clicked.
        """

        if not self.parent_app:
            return

        item = self.listbox_png.itemAt(position)
        if item is None:
            return

        self.listbox_png.setCurrentItem(item)

        selected_items = self.listbox_png.selectedItems()
        if not selected_items or item not in selected_items:
            selected_items = [item]

        menu = QMenu(self)

        # Use UI context for MenuActions/ButtonLabels constants
        _trc = lambda text: QCoreApplication.translate("TextureAtlasToolboxApp", text)

        editor_action = QAction(_trc(MenuActions.ADD_TO_EDITOR), self)
        editor_action.triggered.connect(
            lambda checked=False, entries=selected_items: self.open_spritesheets_in_editor(
                entries
            )
        )
        menu.addAction(editor_action)
        menu.addSeparator()

        settings_action = QAction(_trc(MenuActions.OVERRIDE_SETTINGS), self)
        settings_action.triggered.connect(self.override_spritesheet_settings)
        menu.addAction(settings_action)

        menu.addSeparator()

        delete_action = QAction(_trc(ButtonLabels.DELETE), self)
        delete_action.triggered.connect(self.delete_selected_spritesheet)
        menu.addAction(delete_action)

        menu.exec(self.listbox_png.mapToGlobal(position))

    def show_listbox_data_menu(self, position):
        """Display a context menu for the animation listbox.

        Shows different options depending on whether the item is an
        editor-created composite or a parsed animation.

        Args:
            position: Local coordinates where the user right-clicked.
        """

        if not self.parent_app:
            return

        item = self.listbox_data.itemAt(position)
        if item is None:
            return

        self.listbox_data.setCurrentItem(item)

        selected_items = self.listbox_data.selectedItems()
        if not selected_items or item not in selected_items:
            selected_items = [item]

        menu = QMenu(self)
        any_composite = any(
            isinstance(sel.data(Qt.ItemDataRole.UserRole), dict)
            and sel.data(Qt.ItemDataRole.UserRole).get("type") == "editor_composite"
            for sel in selected_items
        )

        # Use UI context for MenuActions/ButtonLabels constants
        _trc = lambda text: QCoreApplication.translate("TextureAtlasToolboxApp", text)

        editor_action = QAction(
            (
                _trc(MenuActions.FOCUS_IN_EDITOR)
                if any_composite
                else _trc(MenuActions.ADD_TO_EDITOR)
            ),
            self,
        )
        editor_action.triggered.connect(
            lambda checked=False, entries=selected_items: self.open_selected_animations_in_editor(
                entries
            )
        )
        menu.addAction(editor_action)

        # Preview/settings make sense only for single non-composite selections
        if len(selected_items) == 1:
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if not (
                isinstance(item_data, dict)
                and item_data.get("type") == "editor_composite"
            ):
                menu.addSeparator()

                preview_action = QAction(_trc(MenuActions.PREVIEW_ANIMATION), self)
                preview_action.triggered.connect(self.preview_selected_animation)
                menu.addAction(preview_action)

                menu.addSeparator()

                settings_action = QAction(_trc(MenuActions.OVERRIDE_SETTINGS), self)
                settings_action.triggered.connect(self.override_animation_settings)
                menu.addAction(settings_action)

        menu.addSeparator()

        delete_action = QAction(_trc(MenuActions.REMOVE_FROM_LIST), self)
        delete_action.triggered.connect(self.delete_selected_animations)
        menu.addAction(delete_action)

        menu.exec(self.listbox_data.mapToGlobal(position))

    def on_double_click_animation(self, item):
        """Open the override settings dialog for a double-clicked animation.

        Args:
            item: The QListWidgetItem that was double-clicked.
        """

        if not item or not self.parent_app:
            return

        current_spritesheet_item = self.listbox_png.currentItem()
        if not current_spritesheet_item:
            QMessageBox.information(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Please select a spritesheet first."),
            )
            return

        spritesheet_name = current_spritesheet_item.text()
        animation_name = item.text()
        full_anim_name = "{spritesheet}/{animation}".format(
            spritesheet=spritesheet_name, animation=animation_name
        )

        def store_settings(settings):
            """Callback to store animation settings."""
            self.parent_app.settings_manager.animation_settings[full_anim_name] = (
                settings
            )

        self.update_global_settings()

        try:
            from gui.extractor.override_settings_window import (
                OverrideSettingsWindow,
            )

            dialog = OverrideSettingsWindow(
                self.parent_app,
                full_anim_name,
                "animation",
                self.parent_app.settings_manager,
                store_settings,
                self.parent_app,
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Could not open animation settings: {error}").format(
                    error=str(e)
                ),
            )

    def on_double_click_spritesheet(self, item):
        """Open the override settings dialog for a double-clicked spritesheet.

        Args:
            item: The QListWidgetItem that was double-clicked.
        """

        if not item or not self.parent_app:
            return

        spritesheet_name = item.text()

        def store_settings(settings):
            """Callback to store spritesheet settings."""
            self.parent_app.settings_manager.spritesheet_settings[spritesheet_name] = (
                settings
            )

        self.update_global_settings()

        try:
            from gui.extractor.override_settings_window import (
                OverrideSettingsWindow,
            )

            dialog = OverrideSettingsWindow(
                self.parent_app,
                spritesheet_name,
                "spritesheet",
                self.parent_app.settings_manager,
                store_settings,
                self.parent_app,
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Could not open spritesheet settings: {error}").format(
                    error=str(e)
                ),
            )

    def override_spritesheet_settings(self):
        """Opens window to override settings for selected spritesheet."""
        if not self.parent_app:
            return

        current_item = self.listbox_png.currentItem()
        if not current_item:
            QMessageBox.information(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Please select a spritesheet first."),
            )
            return

        spritesheet_name = current_item.text()

        def store_settings(settings):
            """Callback to store spritesheet settings."""
            self.parent_app.settings_manager.spritesheet_settings[spritesheet_name] = (
                settings
            )

        self.update_global_settings()

        try:
            from gui.extractor.override_settings_window import (
                OverrideSettingsWindow,
            )

            dialog = OverrideSettingsWindow(
                self.parent_app,
                spritesheet_name,
                "spritesheet",
                self.parent_app.settings_manager,
                store_settings,
                self.parent_app,
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Could not open spritesheet settings: {error}").format(
                    error=str(e)
                ),
            )

    def open_spritesheet_in_editor(self, spritesheet_item):
        """Send all animations of a spritesheet to the editor tab.

        Iterates over eligible (non-composite) animations and opens each one
        in the editor. Editor-created composites are skipped.

        Args:
            spritesheet_item: QListWidgetItem representing the spritesheet row.
        """

        if not self.parent_app or not spritesheet_item:
            return

        self.listbox_png.setCurrentItem(spritesheet_item)
        if self.listbox_data.count() == 0:
            QMessageBox.information(
                self,
                self.tr(TabTitles.EDITOR),
                self.tr(
                    "Load animations for this spritesheet before sending it to the editor."
                ),
            )
            return

        eligible_items = []
        for index in range(self.listbox_data.count()):
            item = self.listbox_data.item(index)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if (
                isinstance(item_data, dict)
                and item_data.get("type") == "editor_composite"
            ):
                continue
            eligible_items.append(item)

        if not eligible_items:
            QMessageBox.information(
                self,
                self.tr(TabTitles.EDITOR),
                self.tr("No animations were found for this spritesheet."),
            )
            return

        self.listbox_data.setCurrentItem(eligible_items[0])
        for item in eligible_items:
            self._open_animation_in_editor(spritesheet_item, item)

    def open_spritesheets_in_editor(self, spritesheet_items):
        """Batch-send multiple spritesheets to the editor tab."""
        if not self.parent_app:
            return
        for sheet_item in spritesheet_items or []:
            self.open_spritesheet_in_editor(sheet_item)

    def open_animation_item_in_editor(self, animation_item):
        """Send a single animation to the editor tab.

        If the item is an editor composite, focuses it in the editor instead
        of re-importing.

        Args:
            animation_item: QListWidgetItem representing the animation row.
        """

        if not self.parent_app or not animation_item:
            return

        spritesheet_item = self.listbox_png.currentItem()
        if not spritesheet_item:
            QMessageBox.information(
                self,
                self.tr(TabTitles.EDITOR),
                self.tr("Select a spritesheet first."),
            )
            return

        item_data = animation_item.data(Qt.ItemDataRole.UserRole)
        if isinstance(item_data, dict) and item_data.get("type") == "editor_composite":
            editor_id = item_data.get("editor_id")
            if editor_id and hasattr(self.parent_app, "editor_tab_widget"):
                focused = self.parent_app.editor_tab_widget.focus_animation_by_id(
                    editor_id
                )
                if (
                    focused
                    and hasattr(self.parent_app, "ui")
                    and hasattr(self.parent_app.ui, "tools_tab")
                ):
                    self.parent_app.ui.tools_tab.setCurrentWidget(
                        self.parent_app.editor_tab_widget
                    )
                else:
                    QMessageBox.information(
                        self,
                        self.tr(TabTitles.EDITOR),
                        self.tr(
                            "Unable to locate the exported composite in the editor."
                        ),
                    )
            return

        self._open_animation_in_editor(spritesheet_item, animation_item)

    def open_selected_animations_in_editor(self, animation_items):
        """Send one or more animations to the editor tab."""
        if not self.parent_app:
            return
        spritesheet_item = self.listbox_png.currentItem()
        if not spritesheet_item:
            QMessageBox.information(
                self,
                self.tr(TabTitles.EDITOR),
                self.tr("Select a spritesheet first."),
            )
            return

        for item in animation_items or []:
            self.open_animation_item_in_editor(item)

    def _open_animation_in_editor(self, spritesheet_item, animation_item):
        """Send the selected spritesheet + animation metadata to the editor tab.

        Args:
            spritesheet_item: QListWidgetItem describing the spritesheet row.
            animation_item: QListWidgetItem describing the animation row.
        """
        if not self.parent_app or not hasattr(
            self.parent_app, "open_animation_in_editor"
        ):
            return

        spritesheet_name = spritesheet_item.text()
        animation_name = animation_item.text()
        spritesheet_path = spritesheet_item.data(Qt.ItemDataRole.UserRole)
        if not spritesheet_path:
            QMessageBox.warning(
                self,
                self.tr(TabTitles.EDITOR),
                self.tr("The spritesheet path could not be determined."),
            )
            return

        data_entry = self.parent_app.data_dict.get(spritesheet_name, {})
        metadata_path = None
        if isinstance(data_entry, dict):
            metadata_path = data_entry.get("xml") or data_entry.get("txt")
        spritemap_info = (
            data_entry.get("spritemap") if isinstance(data_entry, dict) else None
        )
        spritemap_target = (
            animation_item.data(Qt.ItemDataRole.UserRole) if spritemap_info else None
        )

        if not metadata_path and not spritemap_info:
            QMessageBox.information(
                self,
                self.tr(TabTitles.EDITOR),
                self.tr("No metadata was located for this spritesheet."),
            )
            return

        self.parent_app.open_animation_in_editor(
            spritesheet_name,
            animation_name,
            spritesheet_path,
            metadata_path,
            spritemap_info,
            spritemap_target,
        )

    def delete_selected_animations(self):
        """Remove selected animations from the list (non-destructive)."""
        selected_items = self.listbox_data.selectedItems()
        if not selected_items:
            current_item = self.listbox_data.currentItem()
            selected_items = [current_item] if current_item else []
        if not selected_items:
            return

        spritesheet_item = self.listbox_png.currentItem()
        spritesheet_name = spritesheet_item.text() if spritesheet_item else None

        for item in selected_items:
            if item is None:
                continue
            item_data = item.data(Qt.ItemDataRole.UserRole)
            row = self.listbox_data.row(item)
            if row >= 0:
                self.listbox_data.takeItem(row)

            # Remove persisted editor composite definitions when deleting them from the list
            if (
                isinstance(item_data, dict)
                and item_data.get("type") == "editor_composite"
                and spritesheet_name
            ):
                composites = self.editor_composites.get(spritesheet_name, {})
                composites.pop(item.text(), None)
                if hasattr(self.parent_app, "settings_manager"):
                    sheet_settings = (
                        self.parent_app.settings_manager.spritesheet_settings.get(
                            spritesheet_name, {}
                        )
                    )
                    editor_defs = sheet_settings.get("editor_composites")
                    if isinstance(editor_defs, dict):
                        editor_defs.pop(item.text(), None)

    def override_animation_settings(self):
        """Opens window to override settings for selected animation."""
        if not self.parent_app:
            return

        current_item = self.listbox_data.currentItem()
        if not current_item:
            QMessageBox.information(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Please select an animation first."),
            )
            return

        current_spritesheet_item = self.listbox_png.currentItem()
        if not current_spritesheet_item:
            QMessageBox.information(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Please select a spritesheet first."),
            )
            return

        spritesheet_name = current_spritesheet_item.text()
        animation_name = current_item.text()
        full_anim_name = "{spritesheet}/{animation}".format(
            spritesheet=spritesheet_name, animation=animation_name
        )

        def store_settings(settings):
            """Callback to store animation settings."""
            self.parent_app.settings_manager.animation_settings[full_anim_name] = (
                settings
            )

        self.update_global_settings()

        try:
            from gui.extractor.override_settings_window import (
                OverrideSettingsWindow,
            )

            dialog = OverrideSettingsWindow(
                self.parent_app,
                full_anim_name,
                "animation",
                self.parent_app.settings_manager,
                store_settings,
                self.parent_app,
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Could not open animation settings: {error}").format(
                    error=str(e)
                ),
            )

    def preview_selected_animation(self):
        """Open a preview window for the currently selected animation.

        Locates metadata for the selected spritesheet and delegates to the
        parent application's preview functionality.
        """

        if not self.parent_app:
            return

        current_item = self.listbox_data.currentItem()
        if not current_item:
            QMessageBox.information(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Please select an animation first."),
            )
            return

        current_spritesheet_item = self.listbox_png.currentItem()
        if not current_spritesheet_item:
            QMessageBox.information(
                self,
                self.trc(DialogTitles.ERROR),
                self.tr("Please select a spritesheet first."),
            )
            return

        spritesheet_name = current_spritesheet_item.text()
        animation_name = current_item.text()

        try:
            spritesheet_path = current_spritesheet_item.data(Qt.ItemDataRole.UserRole)
            if not spritesheet_path:
                QMessageBox.warning(
                    self,
                    self.trc(DialogTitles.PREVIEW_ERROR),
                    self.tr("Could not find spritesheet file path."),
                )
                return

            metadata_path = None
            spritemap_info = None
            if spritesheet_name in self.parent_app.data_dict:
                data_files = self.parent_app.data_dict[spritesheet_name]
                if isinstance(data_files, dict):
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

            self.parent_app.preview_animation_with_paths(
                spritesheet_path,
                metadata_path,
                animation_name,
                spritemap_info,
                spritesheet_label=spritesheet_name,
            )

        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Preview error"),
                self.tr("Could not preview animation: {error}").format(error=str(e)),
            )

    def update_ui_state(self, *args):
        """Updates the UI state based on current selections and settings."""
        if not self.parent_app:
            return

        both_export_unchecked = not (
            self.animation_export_group.isChecked()
            or self.frame_export_group.isChecked()
        )
        self.start_process_button.setEnabled(not both_export_unchecked)

        has_spritesheet_selected = self.listbox_png.currentItem() is not None
        self.override_spritesheet_settings_button.setEnabled(has_spritesheet_selected)

        has_animation_selected = self.listbox_data.currentItem() is not None
        self.override_animation_settings_button.setEnabled(has_animation_selected)

    def on_animation_format_change(self):
        """Handles animation format selection changes."""
        if not self.parent_app:
            return

        format_index = self.animation_format_combobox.currentIndex()

        if format_index == 0:  # GIF
            self.threshold_entry.setEnabled(True)
            for child in self.animation_export_group.children():
                if (
                    isinstance(child, QLabel)
                    and "threshold" in child.objectName().lower()
                ):
                    child.setEnabled(True)
        else:
            self.threshold_entry.setEnabled(False)
            for child in self.animation_export_group.children():
                if (
                    isinstance(child, QLabel)
                    and "threshold" in child.objectName().lower()
                ):
                    child.setEnabled(False)

        self.update_frame_rate_display()

    def on_frame_format_change(self):
        """Handles frame format selection changes."""
        if not self.parent_app:
            return

        # Update compression options based on format
        # This will need to be implemented when compression widgets are added
        pass

    def get_extraction_settings(self):
        """Collect current extraction settings from the UI.

        Returns:
            A dict of all user-configured extraction parameters including
            formats, scales, frame selection, and filename options.
        """

        if not self.parent_app:
            return {}

        resampling_method_map = [
            "Nearest",
            "Bilinear",
            "Bicubic",
            "Lanczos",
            "Box",
            "Hamming",
        ]

        animation_format = get_internal_by_index(
            ANIMATION_FORMAT_OPTIONS, self.animation_format_combobox.currentIndex()
        ).upper()
        frame_format = get_internal_by_index(
            FRAME_FORMAT_OPTIONS, self.frame_format_combobox.currentIndex()
        ).upper()
        frame_selection = get_internal_by_index(
            FRAME_SELECTION_OPTIONS, self.frame_selection_combobox.currentIndex()
        )
        crop_option = get_internal_by_index(
            CROPPING_METHOD_OPTIONS, self.cropping_method_combobox.currentIndex()
        )
        filename_format = get_internal_by_index(
            FILENAME_FORMAT_OPTIONS, self.filename_format_combobox.currentIndex()
        )
        resampling_method = resampling_method_map[
            self.resampling_method_combobox.currentIndex()
        ]

        animation_export = self.animation_export_group.isChecked()
        frame_export = self.frame_export_group.isChecked()

        duration_type = self._get_duration_input_type()
        anim_format = self._get_animation_format()
        resolved_type = self._resolve_duration_type(duration_type, anim_format)

        display_value = self.frame_rate_entry.value()
        duration_ms = duration_to_milliseconds(
            display_value, resolved_type, anim_format
        )

        settings = {
            "animation_format": animation_format,
            "frame_format": frame_format,
            "animation_export": animation_export,
            "frame_export": frame_export,
            "duration": duration_ms,
            "duration_display_value": display_value,
            "duration_display_type": resolved_type,
            "delay": self.loop_delay_entry.value(),
            "period": self.min_period_entry.value(),
            "scale": self.scale_entry.value(),
            "threshold": self.threshold_entry.value() / 100.0,  # Convert % to 0-1 range
            "frame_scale": self.frame_scale_entry.value(),
            "frame_selection": frame_selection,
            "crop_option": crop_option,
            "resampling_method": resampling_method,
            "prefix": self.filename_prefix_entry.text(),
            "suffix": self.filename_suffix_entry.text(),
            "filename_format": filename_format,
            "replace_rules": getattr(self.parent_app, "replace_rules", []),
            "var_delay": getattr(self.parent_app, "variable_delay", False),
            "fnf_idle_loop": getattr(self.parent_app, "fnf_idle_loop", False),
            "filter_single_frame_spritemaps": self.filter_single_frame_spritemaps,
        }

        if hasattr(self.parent_app, "app_config"):
            interface = self.parent_app.app_config.get("interface", {})
            settings["merge_duplicate_frames"] = interface.get(
                "merge_duplicate_frames", True
            )
            settings["duration_input_type"] = interface.get(
                "duration_input_type", "fps"
            )
        else:
            settings["merge_duplicate_frames"] = True
            settings["duration_input_type"] = "fps"

        return settings

    def _get_duration_input_type(self) -> str:
        """Return the user's preferred duration input type from config."""

        if self.parent_app and hasattr(self.parent_app, "app_config"):
            interface = self.parent_app.app_config.get("interface", {})
            return interface.get("duration_input_type", "fps")
        return "fps"

    def _get_animation_format(self) -> str:
        """Return the currently selected animation format in uppercase."""

        if (
            hasattr(self, "animation_format_combobox")
            and self.animation_format_combobox
        ):
            return self.animation_format_combobox.currentText().upper()
        return "GIF"

    def _resolve_duration_type(self, duration_type: str, anim_format: str) -> str:
        """Resolve 'native' to the format-specific duration type.

        Args:
            duration_type: Configured duration input type.
            anim_format: Current animation format (GIF, WebP, APNG).

        Returns:
            The resolved duration type (e.g., centiseconds for GIF).
        """
        if duration_type == "native":
            return resolve_native_duration_type(anim_format)
        return duration_type

    def _set_duration_spinbox_from_ms(self, duration_ms: int) -> None:
        """Set the frame rate spinbox from a canonical millisecond value.

        Converts the duration to the current display unit and updates the
        spinbox accordingly, also caching the resolved type for later
        conversions.

        Args:
            duration_ms: Frame duration in milliseconds.
        """
        self._set_duration_spinbox_from_stored(duration_ms, None, None)

    def _set_duration_spinbox_from_stored(
        self,
        duration_ms: int,
        stored_display_value: int | None,
        stored_display_type: str | None,
    ) -> None:
        """Set the frame rate spinbox, using stored display value when possible.

        This method enables lossless FPS round-trips by using the stored
        display value directly when the stored type matches the current
        display type. This avoids precision loss from ms -> fps conversion
        (e.g., 60 FPS -> 17ms -> 59 FPS).

        Args:
            duration_ms: Frame duration in milliseconds (fallback).
            stored_display_value: The originally stored display value.
            stored_display_type: The type of the stored display value.
        """
        duration_type = self._get_duration_input_type()
        anim_format = self._get_animation_format()
        resolved_type = self._resolve_duration_type(duration_type, anim_format)
        display_value = load_duration_display_value(
            duration_ms,
            stored_display_value,
            stored_display_type,
            resolved_type,
            anim_format,
        )
        self._prev_duration_type = resolved_type
        self.frame_rate_entry.setValue(display_value)

    def update_global_settings(self):
        """Updates the global settings from the GUI."""
        if not self.parent_app:
            return

        settings = self.get_extraction_settings()

        for key, value in settings.items():
            self.parent_app.settings_manager.global_settings[key] = value

    def validate_extraction_inputs(self):
        """Check that required inputs are present before extraction.

        Returns:
            A tuple ``(is_valid, error_message)`` where ``is_valid`` is
            ``True`` when extraction can proceed and ``error_message``
            describes any issue found.
        """

        if not self.parent_app:
            return False, "No parent application"

        if self.input_dir_label.text() == self.tr("No input directory selected"):
            return False, self.tr("Please select an input directory first.")

        if self.output_dir_label.text() == self.tr("No output directory selected"):
            return False, self.tr("Please select an output directory first.")

        if not (
            self.animation_export_group.isChecked()
            or self.frame_export_group.isChecked()
        ):
            return False, self.tr(
                "Please enable at least one export option (Animation or Frame)."
            )

        if self.listbox_png.count() == 0:
            return False, self.tr(
                "No spritesheets found. Please select a directory with images."
            )

        return True, ""

    def get_spritesheet_list(self):
        """Retrieve the display names of all loaded spritesheets.

        Returns:
            A list of spritesheet name strings currently in the listbox.
        """

        spritesheet_list = []
        for i in range(self.listbox_png.count()):
            item = self.listbox_png.item(i)
            if item:
                spritesheet_list.append(item.text())
        return spritesheet_list

    def check_for_unknown_atlases(self, spritesheet_list):
        """Identify spritesheets lacking any recognized metadata file.

        Args:
            spritesheet_list: Display names of spritesheets to check.

        Returns:
            A tuple ``(has_unknown, unknown_atlases)`` where ``has_unknown``
            is ``True`` if any atlases lack metadata and ``unknown_atlases``
            lists their display names.
        """

        if not self.parent_app:
            return False, []

        unknown_atlases = []
        input_directory = self.get_input_directory()
        base_directory = Path(input_directory)

        for filename in spritesheet_list:
            relative_path = Path(filename)
            atlas_path = base_directory / relative_path
            atlas_dir = atlas_path.parent
            base_filename = relative_path.stem

            has_metadata = False
            for ext in self.SUPPORTED_METADATA_EXTENSIONS:
                metadata_path = atlas_dir / f"{base_filename}{ext}"
                if metadata_path.is_file():
                    has_metadata = True
                    break

            # Also check for Adobe Animate spritemap (Animation.json + matching json)
            if not has_metadata:
                animation_json_path = atlas_dir / "Animation.json"
                spritemap_json_path = atlas_dir / f"{base_filename}.json"
                if animation_json_path.is_file() and spritemap_json_path.is_file():
                    has_metadata = True

            # Check data_dict for spritemap metadata
            if (
                not has_metadata
                and self.parent_app
                and filename in self.parent_app.data_dict
            ):
                data_entry = self.parent_app.data_dict.get(filename, {})
                has_metadata = (
                    isinstance(data_entry, dict) and "spritemap" in data_entry
                )

            if (
                not has_metadata
                and atlas_path.is_file()
                and atlas_path.suffix.lower()
                in [".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"]
            ):
                unknown_atlases.append(filename)

        return len(unknown_atlases) > 0, unknown_atlases

    def filter_unknown_atlases(self, unknown_atlases):
        """Remove spritesheets without metadata from the listbox.

        Args:
            unknown_atlases: Display names of atlases to remove.
        """

        if not self.parent_app:
            return

        for unknown_atlas in unknown_atlases:
            for i in range(self.listbox_png.count()):
                item = self.listbox_png.item(i)
                if item and item.text() == unknown_atlas:
                    self.listbox_png.takeItem(i)
                    break

        self.listbox_data.clear()

    def prepare_for_extraction(self):
        """Validate inputs and prepare the extraction workflow.

        Returns:
            A tuple ``(success, message, spritesheet_list)`` where ``success``
            indicates readiness, ``message`` describes any error, and
            ``spritesheet_list`` contains names of sheets to process.
        """

        if not self.parent_app:
            return False, "No parent application", []

        is_valid, error_message = self.validate_extraction_inputs()
        if not is_valid:
            return False, error_message, []

        self.update_global_settings()

        spritesheet_list = self.get_spritesheet_list()

        has_unknown, unknown_atlases = self.check_for_unknown_atlases(spritesheet_list)
        if has_unknown:
            from gui.extractor.unknown_atlas_warning_window import (
                UnknownAtlasWarningWindow,
            )

            input_directory = self.input_dir_label.text()
            action = UnknownAtlasWarningWindow.show_warning(
                self.parent_app, unknown_atlases, input_directory
            )
            if action == "cancel":
                return False, "User cancelled due to unknown atlases", []
            elif action == "skip":
                self.filter_unknown_atlases(unknown_atlases)
                spritesheet_list = self.get_spritesheet_list()

        return True, "", spritesheet_list

    def get_input_directory(self):
        """Return the currently selected input directory path."""
        if (
            hasattr(self.parent_app, "manual_selection_temp_dir")
            and self.parent_app.manual_selection_temp_dir
        ):
            temp_dir = Path(self.parent_app.manual_selection_temp_dir)
            if temp_dir.exists():
                return str(temp_dir)
        return self.input_dir_label.text()

    def get_output_directory(self):
        """Return the currently selected output directory path."""

        return self.output_dir_label.text()

    def set_processing_state(self, is_processing):
        """Toggle UI elements between idle and processing states.

        Args:
            is_processing: ``True`` to disable controls during extraction,
                ``False`` to re-enable them.
        """

        self.start_process_button.setEnabled(not is_processing)
        self.start_process_button.setText(
            self.tr("Processing...") if is_processing else self.tr("Start Process")
        )

        self.input_button.setEnabled(not is_processing)
        self.output_button.setEnabled(not is_processing)
        self.reset_button.setEnabled(not is_processing)
        self.animation_export_group.setEnabled(not is_processing)
        self.frame_export_group.setEnabled(not is_processing)
        self.cropping_method_combobox.setEnabled(not is_processing)
        self.filename_format_combobox.setEnabled(not is_processing)
        self.filename_prefix_entry.setEnabled(not is_processing)
        self.filename_suffix_entry.setEnabled(not is_processing)

    def get_selected_spritesheet(self):
        """Return the display name of the currently selected spritesheet."""

        current_item = self.listbox_png.currentItem()
        return current_item.text() if current_item else None

    def get_selected_animation(self):
        """Return the display name of the currently selected animation."""

        current_item = self.listbox_data.currentItem()
        return current_item.text() if current_item else None
