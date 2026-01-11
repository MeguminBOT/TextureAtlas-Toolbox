# -*- coding: utf-8 -*-
################################################################################
## WE WILL NO LONGER RELY ON USING QT DESIGNER, SO EDIT THIS FILE HOWEVER YOU WANT OR MOVE PARTS OF THE CODE INTO NEW FILES AS NEEDED.
################################################################################

################################################################################
## Form generated from reading UI file 'app.ui'
## Created by: Qt User Interface Compiler version 6.10.1
## WARNING! All changes made in this file will be lost when recompiling UI file!
##
################################################################################

from PySide6.QtCore import (
    QCoreApplication,
    QMetaObject,
    QRect,
    QSize,
    Qt,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QListView,
    QMenu,
    QMenuBar,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from utils.combo_options import (
    FRAME_SELECTION_OPTIONS,
    CROPPING_METHOD_OPTIONS,
    FILENAME_FORMAT_OPTIONS,
    update_combobox_texts,
)


def _tr(source: str) -> str:
    """Translate a string using the TextureAtlasToolboxApp context."""
    return QCoreApplication.translate("TextureAtlasToolboxApp", source, None)


class Ui_TextureAtlasToolboxApp(object):
    def setupUi(self, TextureAtlasToolboxApp):
        if not TextureAtlasToolboxApp.objectName():
            TextureAtlasToolboxApp.setObjectName("TextureAtlasToolboxApp")
        TextureAtlasToolboxApp.resize(926, 778)
        TextureAtlasToolboxApp.setUnifiedTitleAndToolBarOnMac(True)
        self.select_directory = QAction(TextureAtlasToolboxApp)
        self.select_directory.setObjectName("select_directory")
        self.select_files = QAction(TextureAtlasToolboxApp)
        self.select_files.setObjectName("select_files")
        self.clear_export_list = QAction(TextureAtlasToolboxApp)
        self.clear_export_list.setObjectName("clear_export_list")
        self.fnf_import_settings = QAction(TextureAtlasToolboxApp)
        self.fnf_import_settings.setObjectName("fnf_import_settings")
        self.preferences = QAction(TextureAtlasToolboxApp)
        self.preferences.setObjectName("preferences")
        self.help_manual = QAction(TextureAtlasToolboxApp)
        self.help_manual.setObjectName("help_manual")
        self.help_fnf = QAction(TextureAtlasToolboxApp)
        self.help_fnf.setObjectName("help_fnf")
        self.show_contributors = QAction(TextureAtlasToolboxApp)
        self.show_contributors.setObjectName("show_contributors")
        self.centralwidget = QWidget(TextureAtlasToolboxApp)
        self.centralwidget.setObjectName("centralwidget")
        self.tools_tab = QTabWidget(self.centralwidget)
        self.tools_tab.setObjectName("tools_tab")
        self.tools_tab.setGeometry(QRect(0, 10, 921, 701))
        self.tools_tab.setStyleSheet("")
        self.tools_tab.setTabPosition(QTabWidget.TabPosition.North)
        self.tools_tab.setElideMode(Qt.TextElideMode.ElideLeft)
        self.tools_tab.setDocumentMode(False)
        self.tool_extract = QWidget()
        self.tool_extract.setObjectName("tool_extract")
        self.listbox_png = QListView(self.tool_extract)
        self.listbox_png.setObjectName("listbox_png")
        self.listbox_png.setGeometry(QRect(5, 10, 200, 621))
        self.listbox_png.setAlternatingRowColors(False)
        self.listbox_png.setProperty("isWrapping", False)
        self.listbox_data = QListView(self.tool_extract)
        self.listbox_data.setObjectName("listbox_data")
        self.listbox_data.setGeometry(QRect(210, 10, 200, 621))
        self.input_button = QPushButton(self.tool_extract)
        self.input_button.setObjectName("input_button")
        self.input_button.setGeometry(QRect(570, 10, 171, 24))
        self.output_button = QPushButton(self.tool_extract)
        self.output_button.setObjectName("output_button")
        self.output_button.setGeometry(QRect(570, 60, 171, 24))
        self.input_dir_label = QLabel(self.tool_extract)
        self.input_dir_label.setObjectName("input_dir_label")
        self.input_dir_label.setGeometry(QRect(430, 30, 451, 21))
        self.input_dir_label.setFrameShape(QFrame.Shape.NoFrame)
        self.input_dir_label.setFrameShadow(QFrame.Shadow.Plain)
        self.input_dir_label.setTextFormat(Qt.TextFormat.PlainText)
        self.input_dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.output_dir_label = QLabel(self.tool_extract)
        self.output_dir_label.setObjectName("output_dir_label")
        self.output_dir_label.setGeometry(QRect(430, 80, 451, 21))
        self.output_dir_label.setFrameShape(QFrame.Shape.NoFrame)
        self.output_dir_label.setFrameShadow(QFrame.Shadow.Plain)
        self.output_dir_label.setTextFormat(Qt.TextFormat.PlainText)
        self.output_dir_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation_export_group = QGroupBox(self.tool_extract)
        self.animation_export_group.setObjectName("animation_export_group")
        self.animation_export_group.setGeometry(QRect(458, 110, 191, 331))
        self.animation_export_group.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.animation_export_group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation_export_group.setFlat(False)
        self.animation_export_group.setCheckable(True)
        self.animation_export_group.setChecked(False)
        self.animation_format_combobox = QComboBox(self.animation_export_group)
        self.animation_format_combobox.addItem("")
        self.animation_format_combobox.addItem("")
        self.animation_format_combobox.addItem("")
        self.animation_format_combobox.setObjectName("animation_format_combobox")
        self.animation_format_combobox.setGeometry(QRect(10, 50, 171, 24))
        self.animation_format_combobox.setEditable(False)
        self.animation_format_combobox.setMaxVisibleItems(5)
        self.animation_format_combobox.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.animation_format_combobox.setFrame(True)
        self.animation_format_combobox.setModelColumn(0)
        self.animation_format_label = QLabel(self.animation_export_group)
        self.animation_format_label.setObjectName("animation_format_label")
        self.animation_format_label.setGeometry(QRect(40, 30, 111, 16))
        self.animation_format_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.animation_format_label.setIndent(0)
        self.frame_rate_entry = QSpinBox(self.animation_export_group)
        self.frame_rate_entry.setObjectName("frame_rate_entry")
        self.frame_rate_entry.setGeometry(QRect(10, 100, 171, 24))
        self.frame_rate_entry.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToNearestValue
        )
        self.frame_rate_entry.setProperty("showGroupSeparator", False)
        self.frame_rate_entry.setMinimum(1)
        self.frame_rate_entry.setMaximum(1000)
        self.frame_rate_entry.setValue(24)
        self.loop_delay_entry = QSpinBox(self.animation_export_group)
        self.loop_delay_entry.setObjectName("loop_delay_entry")
        self.loop_delay_entry.setGeometry(QRect(10, 150, 171, 24))
        self.loop_delay_entry.setAccelerated(True)
        self.loop_delay_entry.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToNearestValue
        )
        self.loop_delay_entry.setMaximum(10000)
        self.loop_delay_entry.setValue(250)
        self.loop_delay_entry.setDisplayIntegerBase(10)
        self.min_period_entry = QSpinBox(self.animation_export_group)
        self.min_period_entry.setObjectName("min_period_entry")
        self.min_period_entry.setGeometry(QRect(10, 200, 171, 24))
        self.min_period_entry.setAccelerated(True)
        self.min_period_entry.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToNearestValue
        )
        self.min_period_entry.setMaximum(10000)
        self.frame_rate_label = QLabel(self.animation_export_group)
        self.frame_rate_label.setObjectName("frame_rate_label")
        self.frame_rate_label.setGeometry(QRect(40, 80, 111, 16))
        self.frame_rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loop_delay_label = QLabel(self.animation_export_group)
        self.loop_delay_label.setObjectName("loop_delay_label")
        self.loop_delay_label.setGeometry(QRect(40, 130, 111, 16))
        self.loop_delay_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.min_period_label = QLabel(self.animation_export_group)
        self.min_period_label.setObjectName("min_period_label")
        self.min_period_label.setGeometry(QRect(40, 180, 111, 16))
        self.min_period_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scale_label = QLabel(self.animation_export_group)
        self.scale_label.setObjectName("scale_label")
        self.scale_label.setGeometry(QRect(40, 230, 111, 16))
        self.scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threshold_label = QLabel(self.animation_export_group)
        self.threshold_label.setObjectName("threshold_label")
        self.threshold_label.setGeometry(QRect(40, 280, 111, 16))
        self.threshold_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.threshold_entry = QSpinBox(self.animation_export_group)
        self.threshold_entry.setObjectName("threshold_entry")
        self.threshold_entry.setGeometry(QRect(10, 300, 171, 24))
        self.threshold_entry.setAccelerated(True)
        self.threshold_entry.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToNearestValue
        )
        self.threshold_entry.setMinimum(0)
        self.threshold_entry.setMaximum(100)
        self.threshold_entry.setValue(50)
        self.scale_entry = QDoubleSpinBox(self.animation_export_group)
        self.scale_entry.setObjectName("scale_entry")
        self.scale_entry.setGeometry(QRect(10, 250, 171, 24))
        self.scale_entry.setAccelerated(True)
        self.scale_entry.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToNearestValue
        )
        self.scale_entry.setDecimals(2)
        self.scale_entry.setMinimum(0.010000000000000)
        self.scale_entry.setMaximum(100.000000000000000)
        self.scale_entry.setSingleStep(0.010000000000000)
        self.scale_entry.setValue(1.000000000000000)
        self.frame_export_group = QGroupBox(self.tool_extract)
        self.frame_export_group.setObjectName("frame_export_group")
        self.frame_export_group.setGeometry(QRect(658, 110, 191, 331))
        self.frame_export_group.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.frame_export_group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_export_group.setFlat(False)
        self.frame_export_group.setCheckable(True)
        self.frame_export_group.setChecked(False)
        self.frame_format_combobox = QComboBox(self.frame_export_group)
        self.frame_format_combobox.addItem("")
        self.frame_format_combobox.addItem("")
        self.frame_format_combobox.addItem("")
        self.frame_format_combobox.addItem("")
        self.frame_format_combobox.addItem("")
        self.frame_format_combobox.addItem("")
        self.frame_format_combobox.addItem("")
        self.frame_format_combobox.setObjectName("frame_format_combobox")
        self.frame_format_combobox.setGeometry(QRect(10, 50, 171, 24))
        self.frame_format_combobox.setEditable(False)
        self.frame_format_combobox.setMaxVisibleItems(10)
        self.frame_format_combobox.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow
        )
        self.frame_format_combobox.setFrame(True)
        self.frame_format_combobox.setModelColumn(0)
        self.frame_format_label = QLabel(self.frame_export_group)
        self.frame_format_label.setObjectName("frame_format_label")
        self.frame_format_label.setGeometry(QRect(40, 30, 111, 16))
        self.frame_format_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_format_label.setIndent(0)
        self.frame_scale_label = QLabel(self.frame_export_group)
        self.frame_scale_label.setObjectName("frame_scale_label")
        self.frame_scale_label.setGeometry(QRect(40, 130, 111, 16))
        self.frame_scale_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_scale_entry = QDoubleSpinBox(self.frame_export_group)
        self.frame_scale_entry.setObjectName("frame_scale_entry")
        self.frame_scale_entry.setGeometry(QRect(10, 150, 171, 24))
        self.frame_scale_entry.setAccelerated(True)
        self.frame_scale_entry.setCorrectionMode(
            QAbstractSpinBox.CorrectionMode.CorrectToNearestValue
        )
        self.frame_scale_entry.setDecimals(2)
        self.frame_scale_entry.setMinimum(0.010000000000000)
        self.frame_scale_entry.setMaximum(100.000000000000000)
        self.frame_scale_entry.setSingleStep(0.010000000000000)
        self.frame_scale_entry.setValue(1.000000000000000)
        self.frame_selection_combobox = QComboBox(self.frame_export_group)
        self.frame_selection_combobox.addItem("")
        self.frame_selection_combobox.addItem("")
        self.frame_selection_combobox.addItem("")
        self.frame_selection_combobox.addItem("")
        self.frame_selection_combobox.addItem("")
        self.frame_selection_combobox.addItem("")
        self.frame_selection_combobox.setObjectName("frame_selection_combobox")
        self.frame_selection_combobox.setGeometry(QRect(10, 100, 171, 24))
        self.frame_selection_label = QLabel(self.frame_export_group)
        self.frame_selection_label.setObjectName("frame_selection_label")
        self.frame_selection_label.setGeometry(QRect(40, 80, 111, 16))
        self.frame_selection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.compression_settings_button = QPushButton(self.frame_export_group)
        self.compression_settings_button.setObjectName("compression_settings_button")
        self.compression_settings_button.setGeometry(QRect(10, 200, 171, 24))
        self.resampling_method_label = QLabel(self.tool_extract)
        self.resampling_method_label.setObjectName("resampling_method_label")
        self.resampling_method_label.setGeometry(QRect(458, 450, 131, 16))
        self.resampling_method_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.resampling_method_label.setIndent(0)
        self.resampling_method_combobox = QComboBox(self.tool_extract)
        self.resampling_method_combobox.addItem("")
        self.resampling_method_combobox.addItem("")
        self.resampling_method_combobox.addItem("")
        self.resampling_method_combobox.addItem("")
        self.resampling_method_combobox.addItem("")
        self.resampling_method_combobox.addItem("")
        self.resampling_method_combobox.setObjectName("resampling_method_combobox")
        self.resampling_method_combobox.setGeometry(QRect(458, 470, 131, 24))
        self.cropping_method_label = QLabel(self.tool_extract)
        self.cropping_method_label.setObjectName("cropping_method_label")
        self.cropping_method_label.setGeometry(QRect(600, 450, 111, 16))
        self.cropping_method_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cropping_method_label.setIndent(0)
        self.cropping_method_combobox = QComboBox(self.tool_extract)
        self.cropping_method_combobox.addItem("")
        self.cropping_method_combobox.addItem("")
        self.cropping_method_combobox.addItem("")
        self.cropping_method_combobox.setObjectName("cropping_method_combobox")
        self.cropping_method_combobox.setGeometry(QRect(593, 470, 131, 24))
        self.filename_prefix_label = QLabel(self.tool_extract)
        self.filename_prefix_label.setObjectName("filename_prefix_label")
        self.filename_prefix_label.setGeometry(QRect(458, 510, 131, 16))
        self.filename_prefix_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_prefix_label.setIndent(0)
        self.filename_prefix_entry = QLineEdit(self.tool_extract)
        self.filename_prefix_entry.setObjectName("filename_prefix_entry")
        self.filename_prefix_entry.setGeometry(QRect(458, 530, 131, 24))
        self.filename_suffix_label = QLabel(self.tool_extract)
        self.filename_suffix_label.setObjectName("filename_suffix_label")
        self.filename_suffix_label.setGeometry(QRect(593, 510, 131, 16))
        self.filename_suffix_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_suffix_label.setIndent(0)
        self.filename_suffix_entry = QLineEdit(self.tool_extract)
        self.filename_suffix_entry.setObjectName("filename_suffix_entry")
        self.filename_suffix_entry.setGeometry(QRect(593, 530, 131, 24))
        self.filename_format_combobox = QComboBox(self.tool_extract)
        self.filename_format_combobox.addItem("")
        self.filename_format_combobox.addItem("")
        self.filename_format_combobox.addItem("")
        self.filename_format_combobox.setObjectName("filename_format_combobox")
        self.filename_format_combobox.setGeometry(QRect(728, 470, 131, 24))
        self.filename_format_label = QLabel(self.tool_extract)
        self.filename_format_label.setObjectName("filename_format_label")
        self.filename_format_label.setGeometry(QRect(738, 450, 111, 16))
        self.filename_format_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_format_label.setIndent(0)
        self.advanced_filename_button = QPushButton(self.tool_extract)
        self.advanced_filename_button.setObjectName("advanced_filename_button")
        self.advanced_filename_button.setGeometry(QRect(560, 560, 191, 24))
        self.start_process_button = QPushButton(self.tool_extract)
        self.start_process_button.setObjectName("start_process_button")
        self.start_process_button.setGeometry(QRect(740, 635, 141, 32))
        self.start_process_button.setChecked(False)
        self.show_override_settings_button = QPushButton(self.tool_extract)
        self.show_override_settings_button.setObjectName(
            "show_override_settings_button"
        )
        self.show_override_settings_button.setGeometry(QRect(440, 635, 141, 32))
        self.override_spritesheet_settings_button = QPushButton(self.tool_extract)
        self.override_spritesheet_settings_button.setObjectName(
            "override_spritesheet_settings_button"
        )
        self.override_spritesheet_settings_button.setGeometry(QRect(5, 635, 200, 32))
        self.reset_button = QPushButton(self.tool_extract)
        self.reset_button.setObjectName("reset_button")
        self.reset_button.setGeometry(QRect(590, 635, 141, 32))
        self.override_animation_settings_button = QPushButton(self.tool_extract)
        self.override_animation_settings_button.setObjectName(
            "override_animation_settings_button"
        )
        self.override_animation_settings_button.setGeometry(QRect(210, 635, 200, 32))
        self.tools_tab.addTab(self.tool_extract, "")
        self.tool_generate = QWidget()
        self.tool_generate.setObjectName("tool_generate")
        self.main_layout = QVBoxLayout(self.tool_generate)
        self.main_layout.setSpacing(10)
        self.main_layout.setObjectName("main_layout")
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_splitter = QSplitter(self.tool_generate)
        self.main_splitter.setObjectName("main_splitter")
        self.main_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.file_panel = QFrame(self.main_splitter)
        self.file_panel.setObjectName("file_panel")
        self.file_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.file_panel.setFrameShadow(QFrame.Shadow.Raised)
        self.file_panel_layout = QVBoxLayout(self.file_panel)
        self.file_panel_layout.setSpacing(12)
        self.file_panel_layout.setObjectName("file_panel_layout")
        self.file_panel_layout.setContentsMargins(12, 12, 12, 12)
        self.input_group = QGroupBox(self.file_panel)
        self.input_group.setObjectName("input_group")
        self.input_group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.input_group.setFlat(True)
        self.input_layout = QVBoxLayout(self.input_group)
        self.input_layout.setSpacing(8)
        self.input_layout.setObjectName("input_layout")
        self.input_layout.setContentsMargins(10, 15, 10, 10)
        self.input_buttons_layout = QHBoxLayout()
        self.input_buttons_layout.setSpacing(2)
        self.input_buttons_layout.setObjectName("input_buttons_layout")
        self.add_directory_button = QPushButton(self.input_group)
        self.add_directory_button.setObjectName("add_directory_button")
        self.add_directory_button.setMinimumSize(QSize(0, 16))

        self.input_buttons_layout.addWidget(self.add_directory_button)

        self.add_files_button = QPushButton(self.input_group)
        self.add_files_button.setObjectName("add_files_button")
        self.add_files_button.setMinimumSize(QSize(0, 16))
        self.add_files_button.setFlat(False)

        self.input_buttons_layout.addWidget(self.add_files_button)

        self.add_existing_atlas_button = QPushButton(self.input_group)
        self.add_existing_atlas_button.setObjectName("add_existing_atlas_button")
        self.add_existing_atlas_button.setMinimumSize(QSize(0, 16))
        self.add_existing_atlas_button.setFlat(False)

        self.input_buttons_layout.addWidget(self.add_existing_atlas_button)

        self.clear_frames_button = QPushButton(self.input_group)
        self.clear_frames_button.setObjectName("clear_frames_button")
        self.clear_frames_button.setMinimumSize(QSize(0, 16))

        self.input_buttons_layout.addWidget(self.clear_frames_button)

        self.add_animation_button = QPushButton(self.input_group)
        self.add_animation_button.setObjectName("add_animation_button")
        self.add_animation_button.setMinimumSize(QSize(0, 16))

        self.input_buttons_layout.addWidget(self.add_animation_button)

        self.input_layout.addLayout(self.input_buttons_layout)

        self.animation_tree_placeholder = QWidget(self.input_group)
        self.animation_tree_placeholder.setObjectName("animation_tree_placeholder")
        self.animation_tree_placeholder.setMinimumSize(QSize(0, 200))

        self.input_layout.addWidget(self.animation_tree_placeholder)

        self.frame_info_label = QLabel(self.input_group)
        self.frame_info_label.setObjectName("frame_info_label")

        self.input_layout.addWidget(self.frame_info_label)

        self.file_panel_layout.addWidget(self.input_group)

        self.main_splitter.addWidget(self.file_panel)
        self.settings_panel = QFrame(self.main_splitter)
        self.settings_panel.setObjectName("settings_panel")
        self.settings_panel.setToolTipDuration(1)
        self.settings_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.settings_panel.setFrameShadow(QFrame.Shadow.Raised)
        self.settings_panel_layout = QVBoxLayout(self.settings_panel)
        self.settings_panel_layout.setSpacing(16)
        self.settings_panel_layout.setObjectName("settings_panel_layout")
        self.settings_panel_layout.setContentsMargins(16, 16, 16, 16)
        self.atlas_group = QGroupBox(self.settings_panel)
        self.atlas_group.setObjectName("atlas_group")
        self.atlas_group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.atlas_group.setFlat(True)
        self.atlas_layout = QGridLayout(self.atlas_group)
        self.atlas_layout.setSpacing(0)
        self.atlas_layout.setObjectName("atlas_layout")
        self.atlas_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.atlas_layout.setContentsMargins(2, 2, 2, 2)
        self.atlas_size_method_combobox = QComboBox(self.atlas_group)
        self.atlas_size_method_combobox.addItem("")
        self.atlas_size_method_combobox.addItem("")
        self.atlas_size_method_combobox.addItem("")
        self.atlas_size_method_combobox.setObjectName("atlas_size_method_combobox")
        self.atlas_size_method_combobox.setEditable(True)

        self.atlas_layout.addWidget(self.atlas_size_method_combobox, 21, 2, 1, 1)

        self.packer_method_combobox = QComboBox(self.atlas_group)
        self.packer_method_combobox.setObjectName("packer_method_combobox")

        self.atlas_layout.addWidget(self.packer_method_combobox, 5, 2, 1, 1)

        self.atlas_type_label = QLabel(self.atlas_group)
        self.atlas_type_label.setObjectName("atlas_type_label")

        self.atlas_layout.addWidget(self.atlas_type_label, 3, 0, 1, 1)

        self.image_format_combo = QComboBox(self.atlas_group)
        self.image_format_combo.addItem("")
        self.image_format_combo.addItem("")
        self.image_format_combo.addItem("")
        self.image_format_combo.addItem("")
        self.image_format_combo.addItem("")
        self.image_format_combo.addItem("")
        self.image_format_combo.addItem("")
        self.image_format_combo.addItem("")
        self.image_format_combo.setObjectName("image_format_combo")

        self.atlas_layout.addWidget(self.image_format_combo, 6, 2, 1, 1)

        self.atlas_size_spinbox_1 = QSpinBox(self.atlas_group)
        self.atlas_size_spinbox_1.setObjectName("atlas_size_spinbox_1")
        self.atlas_size_spinbox_1.setMinimum(32)
        self.atlas_size_spinbox_1.setMaximum(65536)
        self.atlas_size_spinbox_1.setValue(512)

        self.atlas_layout.addWidget(self.atlas_size_spinbox_1, 23, 2, 1, 1)

        self.atlas_size_method_label = QLabel(self.atlas_group)
        self.atlas_size_method_label.setObjectName("atlas_size_method_label")

        self.atlas_layout.addWidget(self.atlas_size_method_label, 21, 0, 1, 1)

        self.power_of_2_check = QCheckBox(self.atlas_group)
        self.power_of_2_check.setObjectName("power_of_2_check")
        self.power_of_2_check.setToolTipDuration(1)
        self.power_of_2_check.setChecked(False)

        self.atlas_layout.addWidget(self.power_of_2_check, 26, 0, 1, 1)

        self.atlas_size_label_1 = QLabel(self.atlas_group)
        self.atlas_size_label_1.setObjectName("atlas_size_label_1")

        self.atlas_layout.addWidget(self.atlas_size_label_1, 23, 0, 1, 1)

        self.atlas_type_combo = QComboBox(self.atlas_group)
        self.atlas_type_combo.addItem("")
        self.atlas_type_combo.setObjectName("atlas_type_combo")

        self.atlas_layout.addWidget(self.atlas_type_combo, 3, 2, 1, 1)

        self.allow_rotation_check = QCheckBox(self.atlas_group)
        self.allow_rotation_check.setObjectName("allow_rotation_check")
        self.allow_rotation_check.setChecked(True)

        self.atlas_layout.addWidget(self.allow_rotation_check, 12, 0, 1, 1)

        self.allow_flip_check = QCheckBox(self.atlas_group)
        self.allow_flip_check.setObjectName("allow_flip_check")
        self.allow_flip_check.setChecked(False)

        self.atlas_layout.addWidget(self.allow_flip_check, 13, 0, 1, 1)

        self.atlas_size_spinbox_2 = QSpinBox(self.atlas_group)
        self.atlas_size_spinbox_2.setObjectName("atlas_size_spinbox_2")
        self.atlas_size_spinbox_2.setMinimum(128)
        self.atlas_size_spinbox_2.setMaximum(65536)
        self.atlas_size_spinbox_2.setValue(8192)

        self.atlas_layout.addWidget(self.atlas_size_spinbox_2, 24, 2, 1, 1)

        self.packer_method_label = QLabel(self.atlas_group)
        self.packer_method_label.setObjectName("packer_method_label")

        self.atlas_layout.addWidget(self.packer_method_label, 5, 0, 1, 1)

        self.image_format_label = QLabel(self.atlas_group)
        self.image_format_label.setObjectName("image_format_label")

        self.atlas_layout.addWidget(self.image_format_label, 6, 0, 1, 1)

        self.atlas_size_label_2 = QLabel(self.atlas_group)
        self.atlas_size_label_2.setObjectName("atlas_size_label_2")

        self.atlas_layout.addWidget(self.atlas_size_label_2, 24, 0, 1, 1)

        self.padding_label = QLabel(self.atlas_group)
        self.padding_label.setObjectName("padding_label")

        self.atlas_layout.addWidget(self.padding_label, 25, 0, 1, 1)

        self.padding_spin = QSpinBox(self.atlas_group)
        self.padding_spin.setObjectName("padding_spin")
        # if QT_CONFIG(statustip)
        self.padding_spin.setStatusTip(
            "Adds some extra whitespace between textures or sprites to ensure they won't overlap"
        )
        # endif // QT_CONFIG(statustip)
        self.padding_spin.setFrame(True)
        self.padding_spin.setAlignment(
            Qt.AlignmentFlag.AlignLeading
            | Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )
        self.padding_spin.setMaximum(64)
        self.padding_spin.setValue(2)

        self.atlas_layout.addWidget(self.padding_spin, 25, 2, 1, 1)

        self.settings_panel_layout.addWidget(self.atlas_group)

        self.main_splitter.addWidget(self.settings_panel)

        self.main_layout.addWidget(self.main_splitter)

        self.generate_button = QPushButton(self.tool_generate)
        self.generate_button.setObjectName("generate_button")
        self.generate_button.setEnabled(False)
        self.generate_button.setMinimumSize(QSize(0, 45))

        self.main_layout.addWidget(self.generate_button)

        self.progress_panel = QFrame(self.tool_generate)
        self.progress_panel.setObjectName("progress_panel")
        self.progress_panel.setMaximumSize(QSize(16777215, 150))
        self.progress_panel.setFrameShape(QFrame.Shape.StyledPanel)
        self.progress_panel.setFrameShadow(QFrame.Shadow.Raised)
        self.progress_layout = QVBoxLayout(self.progress_panel)
        self.progress_layout.setSpacing(6)
        self.progress_layout.setObjectName("progress_layout")
        self.progress_layout.setContentsMargins(10, 10, 10, 10)
        self.progress_bar = QProgressBar(self.progress_panel)
        self.progress_bar.setObjectName("progress_bar")
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(24)

        self.progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel(self.progress_panel)
        self.status_label.setObjectName("status_label")

        self.progress_layout.addWidget(self.status_label)

        self.log_text = QTextEdit(self.progress_panel)
        self.log_text.setObjectName("log_text")
        self.log_text.setMaximumSize(QSize(16777215, 80))

        self.progress_layout.addWidget(self.log_text)

        self.main_layout.addWidget(self.progress_panel)

        self.tools_tab.addTab(self.tool_generate, "")
        self.tool_editor = QWidget()
        self.tool_editor.setObjectName("tool_editor")
        sizePolicy = QSizePolicy(
            QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding
        )
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.tool_editor.sizePolicy().hasHeightForWidth())
        self.tool_editor.setSizePolicy(sizePolicy)
        self.editor_tab_layout = QVBoxLayout(self.tool_editor)
        self.editor_tab_layout.setSpacing(8)
        self.editor_tab_layout.setObjectName("editor_tab_layout")
        self.editor_tab_layout.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)
        self.editor_tab_layout.setContentsMargins(8, 8, 8, 8)
        self.editor_outer_splitter = QSplitter(self.tool_editor)
        self.editor_outer_splitter.setObjectName("editor_outer_splitter")
        self.editor_outer_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.editor_outer_splitter.setChildrenCollapsible(False)
        self.editor_lists_widget = QWidget(self.editor_outer_splitter)
        self.editor_lists_widget.setObjectName("editor_lists_widget")
        self.editor_lists_widget.setMinimumSize(QSize(280, 0))
        self.editor_lists_widget.setMaximumSize(QSize(420, 16777215))
        self.editor_lists_layout = QVBoxLayout(self.editor_lists_widget)
        self.editor_lists_layout.setSpacing(8)
        self.editor_lists_layout.setObjectName("editor_lists_layout")
        self.editor_lists_layout.setContentsMargins(8, 8, 8, 8)
        self.editor_anim_label = QLabel(self.editor_lists_widget)
        self.editor_anim_label.setObjectName("editor_anim_label")

        self.editor_lists_layout.addWidget(self.editor_anim_label)

        self.animation_tree = QTreeWidget(self.editor_lists_widget)
        __qtreewidgetitem = QTreeWidgetItem()
        __qtreewidgetitem.setText(0, "1")
        self.animation_tree.setHeaderItem(__qtreewidgetitem)
        self.animation_tree.setObjectName("animation_tree")
        self.animation_tree.setHeaderHidden(True)

        self.editor_lists_layout.addWidget(self.animation_tree)

        self.editor_button_row = QHBoxLayout()
        self.editor_button_row.setSpacing(4)
        self.editor_button_row.setObjectName("editor_button_row")
        self.editor_button_row.setContentsMargins(4, 4, 4, 4)
        self.load_files_button = QPushButton(self.editor_lists_widget)
        self.load_files_button.setObjectName("load_files_button")

        self.editor_button_row.addWidget(self.load_files_button)

        self.remove_animation_button = QPushButton(self.editor_lists_widget)
        self.remove_animation_button.setObjectName("remove_animation_button")

        self.editor_button_row.addWidget(self.remove_animation_button)

        self.combine_button = QPushButton(self.editor_lists_widget)
        self.combine_button.setObjectName("combine_button")
        self.combine_button.setEnabled(False)

        self.editor_button_row.addWidget(self.combine_button)

        self.editor_lists_layout.addLayout(self.editor_button_row)

        self.editor_outer_splitter.addWidget(self.editor_lists_widget)
        self.editor_inner_splitter = QSplitter(self.editor_outer_splitter)
        self.editor_inner_splitter.setObjectName("editor_inner_splitter")
        self.editor_inner_splitter.setFrameShape(QFrame.Shape.NoFrame)
        self.editor_inner_splitter.setFrameShadow(QFrame.Shadow.Plain)
        self.editor_inner_splitter.setOrientation(Qt.Orientation.Horizontal)
        self.editor_inner_splitter.setChildrenCollapsible(False)
        self.canvas_panel = QWidget(self.editor_inner_splitter)
        self.canvas_panel.setObjectName("canvas_panel")
        self.canvas_column = QVBoxLayout(self.canvas_panel)
        self.canvas_column.setSpacing(4)
        self.canvas_column.setObjectName("canvas_column")
        self.canvas_column.setContentsMargins(0, 0, 0, 0)
        self.canvas_holder = QWidget(self.canvas_panel)
        self.canvas_holder.setObjectName("canvas_holder")
        self.canvas_holder_layout = QVBoxLayout(self.canvas_holder)
        self.canvas_holder_layout.setSpacing(0)
        self.canvas_holder_layout.setObjectName("canvas_holder_layout")
        self.canvas_holder_layout.setContentsMargins(0, 0, 0, 0)
        self.canvas_scroll = QScrollArea(self.canvas_holder)
        self.canvas_scroll.setObjectName("canvas_scroll")
        self.canvas_scroll.setWidgetResizable(True)
        self.canvas_scroll_placeholder = QWidget()
        self.canvas_scroll_placeholder.setObjectName("canvas_scroll_placeholder")
        self.canvas_scroll_placeholder.setGeometry(QRect(0, 0, 325, 596))
        self.canvas_scroll.setWidget(self.canvas_scroll_placeholder)

        self.canvas_holder_layout.addWidget(self.canvas_scroll)

        self.canvas_column.addWidget(self.canvas_holder)

        self.canvas_toolbar = QHBoxLayout()
        self.canvas_toolbar.setSpacing(4)
        self.canvas_toolbar.setObjectName("canvas_toolbar")
        self.canvas_toolbar.setContentsMargins(4, 4, 4, 4)
        self.zoom_out_button = QPushButton(self.canvas_panel)
        self.zoom_out_button.setObjectName("zoom_out_button")

        self.canvas_toolbar.addWidget(self.zoom_out_button)

        self.zoom_in_button = QPushButton(self.canvas_panel)
        self.zoom_in_button.setObjectName("zoom_in_button")

        self.canvas_toolbar.addWidget(self.zoom_in_button)

        self.zoom_100_button = QPushButton(self.canvas_panel)
        self.zoom_100_button.setObjectName("zoom_100_button")

        self.canvas_toolbar.addWidget(self.zoom_100_button)

        self.zoom_50_button = QPushButton(self.canvas_panel)
        self.zoom_50_button.setObjectName("zoom_50_button")

        self.canvas_toolbar.addWidget(self.zoom_50_button)

        self.center_view_button = QPushButton(self.canvas_panel)
        self.center_view_button.setObjectName("center_view_button")

        self.canvas_toolbar.addWidget(self.center_view_button)

        self.fit_canvas_button = QPushButton(self.canvas_panel)
        self.fit_canvas_button.setObjectName("fit_canvas_button")

        self.canvas_toolbar.addWidget(self.fit_canvas_button)

        self.reset_zoom_button = QPushButton(self.canvas_panel)
        self.reset_zoom_button.setObjectName("reset_zoom_button")

        self.canvas_toolbar.addWidget(self.reset_zoom_button)

        self.zoom_label = QLabel(self.canvas_panel)
        self.zoom_label.setObjectName("zoom_label")

        self.canvas_toolbar.addWidget(self.zoom_label)

        self.canvas_toolbar_spacer = QSpacerItem(
            40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )

        self.canvas_toolbar.addItem(self.canvas_toolbar_spacer)

        self.canvas_column.addLayout(self.canvas_toolbar)

        self.editor_status_label = QLabel(self.canvas_panel)
        self.editor_status_label.setObjectName("editor_status_label")

        self.canvas_column.addWidget(self.editor_status_label)

        self.editor_inner_splitter.addWidget(self.canvas_panel)
        self.controls_panel = QWidget(self.editor_inner_splitter)
        self.controls_panel.setObjectName("controls_panel")
        self.controls_panel.setMinimumSize(QSize(280, 0))
        self.controls_panel.setMaximumSize(QSize(320, 16777215))
        self.controls_panel_layout = QVBoxLayout(self.controls_panel)
        self.controls_panel_layout.setSpacing(8)
        self.controls_panel_layout.setObjectName("controls_panel_layout")
        self.controls_panel_layout.setContentsMargins(8, 8, 8, 8)
        self.controls_group = QGroupBox(self.controls_panel)
        self.controls_group.setObjectName("controls_group")
        self.controls_group.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        self.controls_group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.controls_group.setFlat(True)
        self.controls_layout = QFormLayout(self.controls_group)
        self.controls_layout.setObjectName("controls_layout")
        self.controls_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        self.controls_layout.setHorizontalSpacing(8)
        self.controls_layout.setVerticalSpacing(8)
        self.controls_layout.setContentsMargins(8, 8, 8, 8)
        self.label_offset_x = QLabel(self.controls_group)
        self.label_offset_x.setObjectName("label_offset_x")

        self.controls_layout.setWidget(
            0, QFormLayout.ItemRole.LabelRole, self.label_offset_x
        )

        self.label_offset_y = QLabel(self.controls_group)
        self.label_offset_y.setObjectName("label_offset_y")

        self.controls_layout.setWidget(
            1, QFormLayout.ItemRole.LabelRole, self.label_offset_y
        )

        self.offset_x_spin = QSpinBox(self.controls_group)
        self.offset_x_spin.setObjectName("offset_x_spin")
        self.offset_x_spin.setMinimum(-4096)
        self.offset_x_spin.setMaximum(4096)

        self.controls_layout.setWidget(
            0, QFormLayout.ItemRole.FieldRole, self.offset_x_spin
        )

        self.offset_y_spin = QSpinBox(self.controls_group)
        self.offset_y_spin.setObjectName("offset_y_spin")
        self.offset_y_spin.setMinimum(-4096)
        self.offset_y_spin.setMaximum(4096)
        self.offset_y_spin.setStepType(QAbstractSpinBox.StepType.DefaultStepType)

        self.controls_layout.setWidget(
            1, QFormLayout.ItemRole.FieldRole, self.offset_y_spin
        )

        self.control_buttons = QHBoxLayout()
        self.control_buttons.setObjectName("control_buttons")
        self.reset_offset_button = QPushButton(self.controls_group)
        self.reset_offset_button.setObjectName("reset_offset_button")

        self.control_buttons.addWidget(self.reset_offset_button)

        self.apply_all_button = QPushButton(self.controls_group)
        self.apply_all_button.setObjectName("apply_all_button")

        self.control_buttons.addWidget(self.apply_all_button)

        self.controls_layout.setLayout(
            2, QFormLayout.ItemRole.SpanningRole, self.control_buttons
        )

        self.save_overrides_button = QPushButton(self.controls_group)
        self.save_overrides_button.setObjectName("save_overrides_button")
        self.save_overrides_button.setEnabled(False)

        self.controls_layout.setWidget(
            3, QFormLayout.ItemRole.SpanningRole, self.save_overrides_button
        )

        self.controls_panel_layout.addWidget(self.controls_group)

        self.display_group = QGroupBox(self.controls_panel)
        self.display_group.setObjectName("display_group")
        self.display_group.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.display_group.setFlat(True)
        self.display_group.setCheckable(False)
        self.display_layout = QFormLayout(self.display_group)
        self.display_layout.setObjectName("display_layout")
        self.display_layout.setHorizontalSpacing(8)
        self.display_layout.setVerticalSpacing(8)
        self.display_layout.setContentsMargins(8, 8, 8, 8)
        self.label_canvas_width = QLabel(self.display_group)
        self.label_canvas_width.setObjectName("label_canvas_width")

        self.display_layout.setWidget(
            0, QFormLayout.ItemRole.LabelRole, self.label_canvas_width
        )

        self.canvas_width_spin = QSpinBox(self.display_group)
        self.canvas_width_spin.setObjectName("canvas_width_spin")
        self.canvas_width_spin.setMinimum(8)
        self.canvas_width_spin.setMaximum(4096)

        self.display_layout.setWidget(
            0, QFormLayout.ItemRole.FieldRole, self.canvas_width_spin
        )

        self.label_canvas_height = QLabel(self.display_group)
        self.label_canvas_height.setObjectName("label_canvas_height")

        self.display_layout.setWidget(
            1, QFormLayout.ItemRole.LabelRole, self.label_canvas_height
        )

        self.canvas_height_spin = QSpinBox(self.display_group)
        self.canvas_height_spin.setObjectName("canvas_height_spin")
        self.canvas_height_spin.setMinimum(8)
        self.canvas_height_spin.setMaximum(4096)

        self.display_layout.setWidget(
            1, QFormLayout.ItemRole.FieldRole, self.canvas_height_spin
        )

        self.label_canvas_origin = QLabel(self.display_group)
        self.label_canvas_origin.setObjectName("label_canvas_origin")

        self.display_layout.setWidget(
            2, QFormLayout.ItemRole.LabelRole, self.label_canvas_origin
        )

        self.origin_mode_combo = QComboBox(self.display_group)
        self.origin_mode_combo.setObjectName("origin_mode_combo")

        self.display_layout.setWidget(
            2, QFormLayout.ItemRole.FieldRole, self.origin_mode_combo
        )

        self.ghost_widget = QWidget(self.display_group)
        self.ghost_widget.setObjectName("ghost_widget")
        self.ghost_layout = QHBoxLayout(self.ghost_widget)
        self.ghost_layout.setSpacing(6)
        self.ghost_layout.setObjectName("ghost_layout")
        self.ghost_layout.setContentsMargins(0, 0, 0, 0)
        self.ghost_checkbox = QCheckBox(self.ghost_widget)
        self.ghost_checkbox.setObjectName("ghost_checkbox")

        self.ghost_layout.addWidget(self.ghost_checkbox)

        self.ghost_frame_combo = QComboBox(self.ghost_widget)
        self.ghost_frame_combo.setObjectName("ghost_frame_combo")
        self.ghost_frame_combo.setEnabled(False)

        self.ghost_layout.addWidget(self.ghost_frame_combo)

        self.display_layout.setWidget(
            3, QFormLayout.ItemRole.FieldRole, self.ghost_widget
        )

        self.label_snapping = QLabel(self.display_group)
        self.label_snapping.setObjectName("label_snapping")

        self.display_layout.setWidget(
            4, QFormLayout.ItemRole.LabelRole, self.label_snapping
        )

        self.snap_widget = QWidget(self.display_group)
        self.snap_widget.setObjectName("snap_widget")
        self.snap_layout = QHBoxLayout(self.snap_widget)
        self.snap_layout.setSpacing(6)
        self.snap_layout.setObjectName("snap_layout")
        self.snap_layout.setContentsMargins(0, 0, 0, 0)
        self.snap_checkbox = QCheckBox(self.snap_widget)
        self.snap_checkbox.setObjectName("snap_checkbox")

        self.snap_layout.addWidget(self.snap_checkbox)

        self.snap_step_spin = QSpinBox(self.snap_widget)
        self.snap_step_spin.setObjectName("snap_step_spin")
        self.snap_step_spin.setEnabled(False)
        self.snap_step_spin.setMinimum(1)
        self.snap_step_spin.setMaximum(256)
        self.snap_step_spin.setValue(1)

        self.snap_layout.addWidget(self.snap_step_spin)

        self.display_layout.setWidget(
            4, QFormLayout.ItemRole.FieldRole, self.snap_widget
        )

        self.label_ghost_frame = QLabel(self.display_group)
        self.label_ghost_frame.setObjectName("label_ghost_frame")

        self.display_layout.setWidget(
            3, QFormLayout.ItemRole.LabelRole, self.label_ghost_frame
        )

        self.detach_canvas_button = QPushButton(self.display_group)
        self.detach_canvas_button.setObjectName("detach_canvas_button")

        self.display_layout.setWidget(
            5, QFormLayout.ItemRole.SpanningRole, self.detach_canvas_button
        )

        self.controls_panel_layout.addWidget(self.display_group)

        self.export_composite_button = QPushButton(self.controls_panel)
        self.export_composite_button.setObjectName("export_composite_button")
        self.export_composite_button.setEnabled(False)

        self.controls_panel_layout.addWidget(self.export_composite_button)

        self.controls_panel_spacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

        self.controls_panel_layout.addItem(self.controls_panel_spacer)

        self.editor_inner_splitter.addWidget(self.controls_panel)
        self.editor_outer_splitter.addWidget(self.editor_inner_splitter)

        self.editor_tab_layout.addWidget(self.editor_outer_splitter)

        self.tools_tab.addTab(self.tool_editor, "")
        TextureAtlasToolboxApp.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(TextureAtlasToolboxApp)
        self.menubar.setObjectName("menubar")
        self.menubar.setGeometry(QRect(0, 0, 926, 33))
        self.file_menu = QMenu(self.menubar)
        self.file_menu.setObjectName("file_menu")
        self.import_menu = QMenu(self.menubar)
        self.import_menu.setObjectName("import_menu")
        self.help_menu = QMenu(self.menubar)
        self.help_menu.setObjectName("help_menu")
        self.contributors_menu = QMenu(self.menubar)
        self.contributors_menu.setObjectName("contributors_menu")
        self.advanced_menu = QMenu(self.menubar)
        self.advanced_menu.setObjectName("advanced_menu")
        self.options_menu = QMenu(self.menubar)
        self.options_menu.setObjectName("options_menu")
        TextureAtlasToolboxApp.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(TextureAtlasToolboxApp)
        self.statusbar.setObjectName("statusbar")
        TextureAtlasToolboxApp.setStatusBar(self.statusbar)

        self.menubar.addAction(self.file_menu.menuAction())
        self.menubar.addAction(self.import_menu.menuAction())
        self.menubar.addAction(self.help_menu.menuAction())
        self.menubar.addAction(self.contributors_menu.menuAction())
        self.menubar.addAction(self.advanced_menu.menuAction())
        self.menubar.addAction(self.options_menu.menuAction())
        self.file_menu.addAction(self.select_directory)
        self.file_menu.addAction(self.select_files)
        self.file_menu.addAction(self.clear_export_list)
        self.import_menu.addAction(self.fnf_import_settings)
        self.help_menu.addAction(self.help_manual)
        self.help_menu.addAction(self.help_fnf)
        self.contributors_menu.addAction(self.show_contributors)
        self.options_menu.addAction(self.preferences)

        self.retranslateUi(TextureAtlasToolboxApp)

        self.tools_tab.setCurrentIndex(0)
        self.animation_format_combobox.setCurrentIndex(0)
        self.frame_format_combobox.setCurrentIndex(3)
        self.cropping_method_combobox.setCurrentIndex(1)

        QMetaObject.connectSlotsByName(TextureAtlasToolboxApp)

    # setupUi

    def retranslateUi(self, TextureAtlasToolboxApp):
        self.select_directory.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Select directory", None
            )
        )
        self.select_files.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Select files", None)
        )
        self.clear_export_list.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Clear export list", None
            )
        )
        self.fnf_import_settings.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "FNF: Import settings from character data file",
                None,
            )
        )
        self.preferences.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Preferences", None)
        )
        self.help_manual.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "User Manual", None)
        )
        self.help_fnf.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "FNF Guide", None)
        )
        self.show_contributors.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Show Contributors", None
            )
        )
        # if QT_CONFIG(statustip)
        self.tools_tab.setStatusTip("")
        # endif // QT_CONFIG(statustip)
        # if QT_CONFIG(statustip)
        self.tool_extract.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Extract frames from TextureAtlases. Extraction supports exporting as frames or animations.",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        # if QT_CONFIG(statustip)
        self.listbox_png.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "List of all spritesheets to extract", None
            )
        )
        # endif // QT_CONFIG(statustip)
        # if QT_CONFIG(statustip)
        self.listbox_data.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "List of all the animations of the currently selected spritesheet",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.input_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Select input directory", None
            )
        )
        self.output_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Select output directory", None
            )
        )
        self.input_dir_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "No input directory selected", None
            )
        )
        self.output_dir_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "No output directory selected", None
            )
        )
        # if QT_CONFIG(statustip)
        self.animation_export_group.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Animation export settings", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.animation_export_group.setTitle(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Export as animations", None
            )
        )
        self.animation_format_combobox.setItemText(0, "GIF")
        self.animation_format_combobox.setItemText(1, "WebP")
        self.animation_format_combobox.setItemText(2, "APNG")

        # if QT_CONFIG(statustip)
        self.animation_format_combobox.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Sets the format of animated images", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.animation_format_combobox.setPlaceholderText("")
        self.animation_format_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Animation format", None
            )
        )
        # if QT_CONFIG(statustip)
        self.frame_rate_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Sets the playback rate of animated images",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.frame_rate_entry.setSuffix(" fps")
        self.frame_rate_entry.setPrefix("")
        # if QT_CONFIG(statustip)
        self.loop_delay_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Time to wait before looping the animation",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.loop_delay_entry.setSuffix(" ms")
        # if QT_CONFIG(statustip)
        self.min_period_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Forces animated images to be played for at least the set amount of time.",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.min_period_entry.setSuffix(" ms")
        self.frame_rate_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Frame rate", None)
        )
        self.loop_delay_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Loop delay", None)
        )
        self.min_period_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Minimum period", None)
        )
        self.scale_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Scale", None)
        )
        self.threshold_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Alpha threshold", None
            )
        )
        # if QT_CONFIG(statustip)
        self.threshold_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "[GIFs only!] Sets the alpha threshold of GIFs",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.threshold_entry.setSuffix(" %")
        # if QT_CONFIG(statustip)
        self.scale_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Sets the scale of animated images", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.scale_entry.setSuffix(" \u00d7")
        # if QT_CONFIG(statustip)
        self.frame_export_group.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Frame export settings", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.frame_export_group.setTitle(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Export as frames", None
            )
        )
        self.frame_format_combobox.setItemText(0, "AVIF")
        self.frame_format_combobox.setItemText(1, "BMP")
        self.frame_format_combobox.setItemText(2, "DDS")
        self.frame_format_combobox.setItemText(3, "PNG")
        self.frame_format_combobox.setItemText(4, "TGA")
        self.frame_format_combobox.setItemText(5, "TIFF")
        self.frame_format_combobox.setItemText(6, "WebP")

        # if QT_CONFIG(statustip)
        self.frame_format_combobox.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Sets the format of frame images", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.frame_format_combobox.setPlaceholderText("")
        self.frame_format_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Frame format", None)
        )
        self.frame_scale_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Scale", None)
        )
        # if QT_CONFIG(statustip)
        self.frame_scale_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Sets the scale of frames images", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.frame_scale_entry.setSuffix(" \u00d7")
        update_combobox_texts(
            self.frame_selection_combobox, FRAME_SELECTION_OPTIONS, _tr
        )

        # if QT_CONFIG(statustip)
        self.frame_selection_combobox.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                'Which frames to export. "All" exports all frames, "No duplicates" only exports unique frames, "First, Last" exports the first and last frame of the animation.',
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.frame_selection_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Frame selection", None
            )
        )
        # if QT_CONFIG(statustip)
        self.compression_settings_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Controls compression settings for frame images",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.compression_settings_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Compression settings", None
            )
        )
        self.cropping_method_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Cropping method", None
            )
        )
        update_combobox_texts(
            self.cropping_method_combobox, CROPPING_METHOD_OPTIONS, _tr
        )

        # if QT_CONFIG(statustip)
        self.cropping_method_combobox.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                'How cropping should be done. Note: "Frame based" only works on frames, animations will automatically use "Animation based" if "Frame based" was chosen.',
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.resampling_method_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Resampling method", None
            )
        )
        # Resampling method names are technical terms - not translated
        self.resampling_method_combobox.setItemText(0, "Nearest")
        self.resampling_method_combobox.setItemText(1, "Bilinear")
        self.resampling_method_combobox.setItemText(2, "Bicubic")
        self.resampling_method_combobox.setItemText(3, "Lanczos")
        self.resampling_method_combobox.setItemText(4, "Box")
        self.resampling_method_combobox.setItemText(5, "Hamming")
        # if QT_CONFIG(statustip)
        self.resampling_method_combobox.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Resampling algorithm for scaling images.",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.filename_prefix_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Filename prefix", None
            )
        )
        # if QT_CONFIG(statustip)
        self.filename_prefix_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Adds a prefix to the filename", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.filename_prefix_entry.setText("")
        self.filename_suffix_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Filename suffix", None
            )
        )
        # if QT_CONFIG(statustip)
        self.filename_suffix_entry.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Adds a suffix to the filename", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.filename_suffix_entry.setText("")
        self.filename_suffix_entry.setPlaceholderText("")
        update_combobox_texts(
            self.filename_format_combobox, FILENAME_FORMAT_OPTIONS, _tr
        )

        # if QT_CONFIG(statustip)
        self.filename_format_combobox.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                'How filenames should be formatted. Standardized exports names as "Spritesheet name - animation name".',
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.filename_format_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Filename format", None
            )
        )
        # if QT_CONFIG(statustip)
        self.advanced_filename_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                'Advanced filename options allows using pattern matching to remove certain words or phrases from filenames. Supports "Regular Expression".',
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.advanced_filename_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Advanced filename options", None
            )
        )
        # if QT_CONFIG(statustip)
        self.start_process_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Starts extraction process", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.start_process_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Start process", None)
        )
        # if QT_CONFIG(statustip)
        self.show_override_settings_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Opens a window showing all the current override settings.",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.show_override_settings_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Show override settings", None
            )
        )
        # if QT_CONFIG(statustip)
        self.override_spritesheet_settings_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Overrides the global settings for the selected spritesheet",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.override_spritesheet_settings_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Override spritesheet settings", None
            )
        )
        # if QT_CONFIG(statustip)
        self.reset_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Resets the filelist and override settings",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.reset_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Reset", None)
        )
        # if QT_CONFIG(statustip)
        self.override_animation_settings_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Overrides the global settings for the selected animation",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.override_animation_settings_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Override animation settings", None
            )
        )
        self.tools_tab.setTabText(
            self.tools_tab.indexOf(self.tool_extract),
            QCoreApplication.translate("TextureAtlasToolboxApp", "Extract", None),
        )
        self.input_group.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Input", None)
        )
        # if QT_CONFIG(tooltip)
        self.add_directory_button.setToolTip("")
        # endif // QT_CONFIG(tooltip)
        # if QT_CONFIG(statustip)
        self.add_directory_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Adds all images from the selected directory to the atlas generator",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.add_directory_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Directory", None)
        )
        # if QT_CONFIG(statustip)
        self.add_files_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Adds selected files to the atlas generator",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.add_files_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Files", None)
        )
        # if QT_CONFIG(statustip)
        self.add_existing_atlas_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Adds an existing atlas to be regenerated by the generator",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.add_existing_atlas_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Atlas", None)
        )
        # if QT_CONFIG(statustip)
        self.clear_frames_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Clears all input files", None
            )
        )
        # endif // QT_CONFIG(statustip)
        self.clear_frames_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Clear All", None)
        )
        # if QT_CONFIG(statustip)
        self.add_animation_button.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Manually adds a new animation entry for the atlas",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.add_animation_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "New Animation", None)
        )
        self.frame_info_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "No frames loaded", None
            )
        )
        self.atlas_group.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Atlas Settings", None)
        )
        self.atlas_size_method_combobox.setItemText(0, "Automatic")
        self.atlas_size_method_combobox.setItemText(1, "MinMax")
        self.atlas_size_method_combobox.setItemText(2, "Manual")

        # if QT_CONFIG(statustip)
        self.atlas_size_method_combobox.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Choose how the atlas size is determined",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.atlas_type_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Atlas type", None)
        )
        self.image_format_combo.setItemText(0, "PNG")
        self.image_format_combo.setItemText(1, "AVIF")
        self.image_format_combo.setItemText(2, "BMP")
        self.image_format_combo.setItemText(3, "DDS")
        self.image_format_combo.setItemText(4, "JPEG")
        self.image_format_combo.setItemText(5, "TGA")
        self.image_format_combo.setItemText(6, "TIFF")
        self.image_format_combo.setItemText(7, "WebP")

        # if QT_CONFIG(statustip)
        self.atlas_size_spinbox_1.setStatusTip("")
        # endif // QT_CONFIG(statustip)
        self.atlas_size_spinbox_1.setSuffix(" px")
        # if QT_CONFIG(statustip)
        self.atlas_size_method_label.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Choose how the atlas size is determined",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.atlas_size_method_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Atlas size method", None
            )
        )
        # if QT_CONFIG(statustip)
        self.power_of_2_check.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Pads the atlas to the nearest power-of-two size (e.g., 512, 1024, 4096). Improves compatibility with older hardware.",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.power_of_2_check.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", 'Use "Power of 2" sizes', None
            )
        )
        # if QT_CONFIG(statustip)
        self.atlas_size_label_1.setStatusTip("")
        # endif // QT_CONFIG(statustip)
        self.atlas_size_label_1.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Min atlas size", None)
        )

        self.allow_rotation_check.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Allow rotation (90\u00b0)", None
            )
        )
        self.allow_flip_check.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Allow flip X/Y (non-standard)", None
            )
        )
        # if QT_CONFIG(statustip)
        self.atlas_size_spinbox_2.setStatusTip("")
        # endif // QT_CONFIG(statustip)
        self.atlas_size_spinbox_2.setSuffix(" px")
        self.packer_method_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Packer method", None)
        )
        self.image_format_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Image format", None)
        )
        # if QT_CONFIG(statustip)
        self.atlas_size_label_2.setStatusTip("")
        # endif // QT_CONFIG(statustip)
        self.atlas_size_label_2.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Max atlas size", None)
        )
        # if QT_CONFIG(statustip)
        self.padding_label.setStatusTip(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Adds some extra whitespace between textures or sprites to ensure they won't overlap",
                None,
            )
        )
        # endif // QT_CONFIG(statustip)
        self.padding_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Padding:", None)
        )
        self.padding_spin.setSuffix(" px")
        self.generate_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Generate Atlas", None)
        )
        self.status_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Ready", None)
        )
        placeholder_text = QCoreApplication.translate(
            "TextureAtlasToolboxApp",
            "Atlas generation log will appear here...",
            None,
        )

        self.log_text.setHtml(
            '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">\n'
            '<html><head><meta name="qrichtext" content="1" /><meta charset="utf-8" /><style type="text/css">\n'
            "p, li { white-space: pre-wrap; }\n"
            "hr { height: 1px; border-width: 0; }\n"
            'li.unchecked::marker { content: "\\2610"; }\n'
            'li.checked::marker { content: "\\2612"; }\n'
            "</style></head><body style=\" font-family:'Segoe UI'; font-size:9pt; font-weight:400; font-style:normal;\">\n"
            f'<p style=" margin-top:0px; margin-bottom:0px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;">{placeholder_text}</p></body></html>'
        )
        self.tools_tab.setTabText(
            self.tools_tab.indexOf(self.tool_generate),
            QCoreApplication.translate("TextureAtlasToolboxApp", "Generate", None),
        )
        self.editor_anim_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Animations & Frames", None
            )
        )
        self.load_files_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Load", None)
        )
        self.remove_animation_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Remove", None)
        )
        self.combine_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Combine", None)
        )
        self.zoom_out_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "-", None)
        )
        self.zoom_in_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "+", None)
        )
        self.zoom_100_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "100%", None)
        )
        self.zoom_50_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "50%", None)
        )
        self.center_view_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Center View", None)
        )
        self.fit_canvas_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Fit Canvas", None)
        )
        self.reset_zoom_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Reset Zoom", None)
        )
        self.zoom_label.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Zoom: 100%", None)
        )
        self.editor_status_label.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp",
                "Drag the frame, use arrow keys for fine adjustments, or type offsets manually.",
                None,
            )
        )
        self.controls_group.setTitle(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Alignment controls", None
            )
        )
        self.label_offset_x.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Frame offset X", None)
        )
        self.label_offset_y.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Frame offset Y", None)
        )
        self.offset_x_spin.setSuffix(" px")
        self.offset_y_spin.setSuffix(" px")
        self.reset_offset_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Reset to default", None
            )
        )
        self.apply_all_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Apply to all frames", None
            )
        )
        self.save_overrides_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Save Alignment to Extract Tab", None
            )
        )
        self.display_group.setTitle(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Canvas controls", None
            )
        )
        self.label_canvas_width.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Canvas width", None)
        )
        self.canvas_width_spin.setSuffix(" px")
        self.label_canvas_height.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Canvas height", None)
        )
        self.canvas_height_spin.setSuffix(" px")
        self.label_canvas_origin.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Canvas origin", None)
        )
        self.ghost_checkbox.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Enable", None)
        )
        self.label_snapping.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Snapping", None)
        )
        self.snap_checkbox.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Enable", None)
        )
        self.snap_step_spin.setSuffix(" px")
        self.label_ghost_frame.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Ghost frame", None)
        )
        self.detach_canvas_button.setText(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Detach canvas", None)
        )
        self.export_composite_button.setText(
            QCoreApplication.translate(
                "TextureAtlasToolboxApp", "Export Composite to Sprites", None
            )
        )
        self.tools_tab.setTabText(
            self.tools_tab.indexOf(self.tool_editor),
            QCoreApplication.translate("TextureAtlasToolboxApp", "Editor", None),
        )
        self.file_menu.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "File", None)
        )
        self.import_menu.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Import", None)
        )
        self.help_menu.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Help", None)
        )
        self.contributors_menu.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Contributors", None)
        )
        self.advanced_menu.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Advanced", None)
        )
        self.options_menu.setTitle(
            QCoreApplication.translate("TextureAtlasToolboxApp", "Options", None)
        )
        pass

    # retranslateUi
