#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QApplication, QMainWindow, QFileDialog, QMessageBox
from PySide6.QtCore import QThread, Signal, QTimer, Qt, QCoreApplication, QSize
from PySide6.QtGui import QIcon, QAction

# Import our own modules
from utils.dependencies_checker import DependenciesChecker
from utils.version import APP_VERSION

DependenciesChecker.check_and_configure_imagemagick()  # This function must be called before any other operations that require ImageMagick (DO NOT MOVE THIS IMPORT LINE)
from utils.app_config import AppConfig  # noqa: E402
from utils.update_checker import UpdateChecker  # noqa: E402
from utils.settings_manager import SettingsManager  # noqa: E402
from utils.translation_manager import (  # noqa: E402
    get_translation_manager,
    tr as translate,
)
from utils.FNF.character_data import CharacterData  # noqa: E402
from core.extractor import Extractor  # noqa: E402
from gui.app_ui import Ui_TextureAtlasToolboxApp  # noqa: E402
from gui.app_config_window import AppConfigWindow  # noqa: E402
from gui.settings_window import SettingsWindow  # noqa: E402
from gui.extractor.find_replace_window import FindReplaceWindow  # noqa: E402
from gui.help_window import HelpWindow  # noqa: E402
from gui.contributors_window import ContributorsWindow  # noqa: E402
from gui.extractor.processing_window import ProcessingWindow  # noqa: E402
from gui.extractor.compression_settings_window import (  # noqa: E402
    CompressionSettingsWindow,
)
from gui.machine_translation_disclaimer_dialog import (  # noqa: E402
    MachineTranslationDisclaimerDialog,
)
from gui.first_start_dialog import show_first_start_dialog  # noqa: E402


class ExtractorWorker(QThread):
    """Worker thread for extraction process."""

    progress_updated = Signal(
        int, int, object
    )  # current, total, status (filename str or status dict)
    statistics_updated = Signal(
        int, int, int
    )  # frames_generated, animations_generated, sprites_failed
    debug_message = Signal(str)  # debug message for processing log
    extraction_completed = Signal(str)  # completion message
    extraction_failed = Signal(str)
    error_occurred = Signal(str, str)  # title, message
    question_needed = Signal(str, str)  # title, message

    def __init__(self, app_instance, spritesheet_list):
        super().__init__()
        self.app_instance = app_instance
        self.spritesheet_list = spritesheet_list
        self.continue_on_error = True

    def run(self):
        try:
            print(
                f"[ExtractorWorker] Starting extraction of {len(self.spritesheet_list)} files"
            )
            completion_message = self.app_instance.run_extractor_core(
                self.spritesheet_list, self.emit_progress
            )
            print(f"[ExtractorWorker] Extraction completed: {completion_message}")
            self.extraction_completed.emit(completion_message)
        except Exception as e:
            print(f"[ExtractorWorker] Extraction failed: {str(e)}")
            self.extraction_failed.emit(str(e))

    def emit_progress(self, current, total, status=""):
        """Thread-safe progress emission."""
        print(f"[ExtractorWorker] Progress: {current}/{total} - {status}")
        self.progress_updated.emit(current, total, status)

    def emit_statistics(self, frames_generated, animations_generated, sprites_failed):
        """Thread-safe statistics emission."""
        print(
            f"[ExtractorWorker] Stats: F:{frames_generated}, A:{animations_generated}, S:{sprites_failed}"
        )
        self.statistics_updated.emit(
            frames_generated, animations_generated, sprites_failed
        )


class TextureAtlasExtractorApp(QMainWindow):
    """
    A Qt/PySide6 GUI application for extracting textures from a texture atlas and converting them to GIF, WebP, and APNG formats.
    """

    tr = translate
    TRANSLATION_CONTEXT = "TextureAtlasExtractorApp"

    # Signal emitted when animation preview settings are saved
    preview_settings_saved = Signal(str)  # animation_name

    def __init__(self):
        super().__init__()

        # Initialize core attributes
        self.current_version = APP_VERSION
        self.app_config = AppConfig()
        self.settings_manager = SettingsManager()
        self.temp_dir = tempfile.mkdtemp()
        self.manual_selection_temp_dir = (
            None  # For storing temp directory used in manual file selection
        )
        self.data_dict = {}

        # Initialize translation manager and load language
        self.translation_manager = get_translation_manager()
        effective_language = self.app_config.get_effective_language()
        self.translation_manager.load_translation(effective_language)

        self.fnf_character_data = CharacterData()
        self.fnf_char_json_directory = ""
        self.replace_rules = []
        self.linkSourceCode = (
            "https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames"
        )

        # Initialize UI
        self.ui = Ui_TextureAtlasToolboxApp()
        self.ui.setupUi(self)
        self._resize_tools_tab_to_window()
        self._default_minimum_size = QSize(900, 770)
        self._editor_minimum_size = QSize(1280, 850)
        self._pre_editor_size: Optional[QSize] = None
        self.setMinimumSize(self._default_minimum_size)

        # Initialize advanced menu variables
        defaults = (
            self.app_config.get_extraction_defaults()
            if hasattr(self.app_config, "get_extraction_defaults")
            else {}
        )
        self.variable_delay = defaults.get("variable_delay", False)
        self.fnf_idle_loop = defaults.get("fnf_idle_loop", False)

        self.setup_advanced_menu()
        self.setup_gui()
        self.setup_extract_tab()
        self.setup_generate_tab()
        self.setup_editor_tab()
        self.setup_connections()
        self.ui.retranslateUi(self)

        # Re-apply duration input type, retranslateUi resets some labels.
        if hasattr(self, "extract_tab_widget"):
            self.extract_tab_widget.update_frame_rate_display()

        self.update_dynamic_tab_labels()
        self.ui.tools_tab.currentChanged.connect(self._on_tools_tab_changed)
        self._on_tools_tab_changed(self.ui.tools_tab.currentIndex())

        # Show first-start dialog for new users
        show_first_start_dialog(self, self.translation_manager, self.app_config)

        QTimer.singleShot(250, self.check_version)

    def setup_advanced_menu(self):
        """Set up the advanced menu with variable delay and FNF options."""
        # Create variable delay action
        self.variable_delay_action = QAction(
            self.tr("Variable delay"), self, checkable=True
        )
        self.variable_delay_action.setChecked(self.variable_delay)
        self.variable_delay_action.setStatusTip(
            self.tr("Enable variable delay between frames for more accurate timing")
        )

        # Create FNF idle loop action
        self.fnf_idle_loop_action = QAction(
            self.tr("FNF: Set loop delay on idle animations to 0"), self, checkable=True
        )
        self.fnf_idle_loop_action.setChecked(self.fnf_idle_loop)
        self.fnf_idle_loop_action.setStatusTip(
            self.tr(
                "Automatically set loop delay to 0 for animations with 'idle' in their name"
            )
        )

        # Add actions to advanced menu
        self.ui.advanced_menu.addAction(self.variable_delay_action)
        self.ui.advanced_menu.addAction(self.fnf_idle_loop_action)

        # Add language selection to options menu
        self.language_action = QAction(self.tr("Language..."), self, checkable=False)
        self.language_action.setStatusTip(self.tr("Change application language"))
        self.language_action.triggered.connect(self.show_language_selection)
        self.ui.options_menu.addSeparator()
        self.ui.options_menu.addAction(self.language_action)

    def setup_generate_tab(self):
        """Set up the Generate tab with proper functionality."""
        from gui.generate_tab_widget import GenerateTabWidget

        # Remove old label if it exists
        if hasattr(self.ui, "label") and self.ui.label:
            self.ui.label.setParent(None)

        # Create the generate tab widget and pass the UI reference
        self.generate_tab_widget = GenerateTabWidget(self.ui, self)

        print("Generate tab setup completed successfully")

    def setup_editor_tab(self):
        """Add the editor tab for manual alignment workflows."""
        from gui.editor_tab_widget import EditorTabWidget

        use_existing_ui = (
            hasattr(self.ui, "tool_editor") and self.ui.tool_editor is not None
        )
        self.editor_tab_widget = EditorTabWidget(self, use_existing_ui=use_existing_ui)

        if use_existing_ui:
            existing_index = self.ui.tools_tab.indexOf(self.ui.tool_editor)
            if existing_index == -1:
                existing_index = self.ui.tools_tab.addTab(
                    self.ui.tool_editor, self.tr("Editor")
                )
            self._editor_tab_index = existing_index
            self.ui.tools_tab.setTabText(existing_index, self.tr("Editor"))
        else:
            self._editor_tab_index = self.ui.tools_tab.addTab(
                self.editor_tab_widget, self.tr("Editor")
            )

        print("Editor tab setup completed successfully")

    def update_dynamic_tab_labels(self):
        """Refresh translated titles for tabs that are added at runtime."""
        if hasattr(self, "_editor_tab_index") and self._editor_tab_index != -1:
            self.ui.tools_tab.setTabText(self._editor_tab_index, self.tr("Editor"))

    def setup_extract_tab(self):
        """Set up the Extract tab with proper functionality."""
        from gui.extract_tab_widget import ExtractTabWidget

        self.extract_tab_widget = ExtractTabWidget(self, use_existing_ui=True)

        print("Extract tab setup completed successfully")
        self.ui.frame_format_combobox = self.extract_tab_widget.frame_format_combobox
        self.ui.frame_rate_entry = self.extract_tab_widget.frame_rate_entry
        self.ui.loop_delay_entry = self.extract_tab_widget.loop_delay_entry
        self.ui.min_period_entry = self.extract_tab_widget.min_period_entry
        self.ui.scale_entry = self.extract_tab_widget.scale_entry
        self.ui.threshold_entry = self.extract_tab_widget.threshold_entry
        self.ui.frame_scale_entry = self.extract_tab_widget.frame_scale_entry
        self.ui.frame_selection_combobox = (
            self.extract_tab_widget.frame_selection_combobox
        )
        self.ui.cropping_method_combobox = (
            self.extract_tab_widget.cropping_method_combobox
        )
        self.ui.filename_format_combobox = (
            self.extract_tab_widget.filename_format_combobox
        )
        self.ui.filename_prefix_entry = self.extract_tab_widget.filename_prefix_entry
        self.ui.filename_suffix_entry = self.extract_tab_widget.filename_suffix_entry
        self.ui.input_button = self.extract_tab_widget.input_button
        self.ui.output_button = self.extract_tab_widget.output_button
        self.ui.start_process_button = self.extract_tab_widget.start_process_button
        self.ui.reset_button = self.extract_tab_widget.reset_button
        self.ui.advanced_filename_button = (
            self.extract_tab_widget.advanced_filename_button
        )
        self.ui.show_override_settings_button = (
            self.extract_tab_widget.show_override_settings_button
        )
        self.ui.override_spritesheet_settings_button = (
            self.extract_tab_widget.override_spritesheet_settings_button
        )
        self.ui.override_animation_settings_button = (
            self.extract_tab_widget.override_animation_settings_button
        )
        self.ui.compression_settings_button = (
            self.extract_tab_widget.compression_settings_button
        )

        print("Extract tab setup completed successfully")

    def setup_gui(self):
        """Sets up the GUI components of the application."""
        self.setWindowTitle(
            self.tr("TextureAtlas Toolbox v{version}").format(
                version=self.current_version
            )
        )
        self.resize(900, 770)

        # Set application icon if available
        icon_path = Path("assets/icon.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        # Initialize directory labels with translated text
        self.ui.input_dir_label.setText(self.tr("No input directory selected"))
        self.ui.output_dir_label.setText(self.tr("No output directory selected"))

        # Initialize default values from app config
        defaults = (
            self.app_config.get_extraction_defaults()
            if hasattr(self.app_config, "get_extraction_defaults")
            else {}
        )

        # Set default values for UI elements
        self.ui.frame_rate_entry.setValue(defaults.get("frame_rate", 24))
        self.ui.loop_delay_entry.setValue(defaults.get("loop_delay", 250))
        self.ui.min_period_entry.setValue(defaults.get("min_period", 0))
        self.ui.scale_entry.setValue(defaults.get("scale", 1.0))
        self.ui.threshold_entry.setValue(
            defaults.get("threshold", 0.5) * 100.0
        )  # Convert from 0-1 to 0-100 for UI
        self.ui.frame_scale_entry.setValue(defaults.get("frame_scale", 1.0))

        # Set default groupbox states
        self.ui.animation_export_group.setChecked(
            defaults.get("animation_export", True)
        )
        self.ui.frame_export_group.setChecked(defaults.get("frame_export", True))

        # Set default selections using index mapping to avoid translation issues
        if "animation_format" in defaults:
            animation_format_map = ["GIF", "WebP", "APNG"]
            try:
                format_index = animation_format_map.index(defaults["animation_format"])
            except ValueError:
                format_index = 0  # Default to GIF
            self.ui.animation_format_combobox.setCurrentIndex(format_index)

        if "frame_format" in defaults:
            frame_format_map = ["AVIF", "BMP", "DDS", "PNG", "TGA", "TIFF", "WebP"]
            try:
                format_index = frame_format_map.index(defaults["frame_format"])
            except ValueError:
                format_index = 3  # Default to PNG
            self.ui.frame_format_combobox.setCurrentIndex(format_index)

    def _on_tools_tab_changed(self, index: int):
        editor_active = hasattr(self, "_editor_tab_index") and index == getattr(
            self, "_editor_tab_index", -1
        )
        self._apply_editor_window_constraints(editor_active)

    def _apply_editor_window_constraints(self, editor_active: bool):
        if not hasattr(self, "_default_minimum_size"):
            return
        if editor_active:
            if self._pre_editor_size is None:
                self._pre_editor_size = self.size()
            self.setMinimumSize(self._editor_minimum_size)
            target_width = max(self.width(), self._editor_minimum_size.width())
            target_height = max(self.height(), self._editor_minimum_size.height())
            if target_width != self.width() or target_height != self.height():
                self.resize(target_width, target_height)
        else:
            self.setMinimumSize(self._default_minimum_size)
            if self._pre_editor_size is not None:
                target_width = max(
                    self._default_minimum_size.width(), self._pre_editor_size.width()
                )
                target_height = max(
                    self._default_minimum_size.height(), self._pre_editor_size.height()
                )
                self.resize(target_width, target_height)
                self._pre_editor_size = None
        self._resize_tools_tab_to_window()

    def resizeEvent(self, event):  # noqa: D401 - Qt API
        super().resizeEvent(event)
        self._resize_tools_tab_to_window()

    def _resize_tools_tab_to_window(self):
        central = self.centralWidget()
        if not central or not hasattr(self.ui, "tools_tab"):
            return
        self.ui.tools_tab.setGeometry(central.rect())

    def setup_connections(self):
        """Sets up signal-slot connections for UI elements."""
        # Menu actions - connect to extract tab widget methods
        self.ui.select_directory.triggered.connect(
            self.extract_tab_widget.select_directory
        )
        self.ui.select_files.triggered.connect(
            self.extract_tab_widget.select_files_manually
        )
        self.ui.clear_export_list.triggered.connect(
            self.extract_tab_widget.clear_filelist
        )
        self.ui.preferences.triggered.connect(self.create_app_config_window)
        self.ui.fnf_import_settings.triggered.connect(self.fnf_import_settings)
        self.ui.help_manual.triggered.connect(self.show_help_manual)
        self.ui.help_fnf.triggered.connect(self.show_help_fnf)
        self.ui.show_contributors.triggered.connect(self.show_contributors_window)

        # Advanced menu actions
        self.variable_delay_action.toggled.connect(self.on_variable_delay_toggled)
        self.fnf_idle_loop_action.toggled.connect(self.on_fnf_idle_loop_toggled)

        # Note: Most UI element connections are now handled within the extract_tab_widget
        # Initial UI state update
        if hasattr(self, "extract_tab_widget"):
            self.extract_tab_widget.update_ui_state()

    def show_language_selection(self):
        """Show the language selection window."""
        try:
            from gui.language_selection_window import show_language_selection

            show_language_selection(self)
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr("Could not open language selection: {error}").format(
                    error=str(e)
                ),
            )

    def create_app_config_window(self):
        """Creates the preferences/app config window."""
        try:
            dialog = AppConfigWindow(self, self.app_config)
            if dialog.exec():
                # Update extract tab's frame rate display after settings change
                if hasattr(self, "extract_tab_widget") and hasattr(
                    self.extract_tab_widget, "update_frame_rate_display"
                ):
                    self.extract_tab_widget.update_frame_rate_display()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Warning"),
                self.tr("Could not open preferences: {error}").format(error=str(e)),
            )

    def show_help_manual(self):
        """Shows the main help window with application manual."""
        try:
            HelpWindow.create_main_help_window(self)
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr("Could not open help window: {error}").format(error=str(e)),
            )

    def show_help_fnf(self):
        """Shows the FNF-specific help window."""
        try:
            HelpWindow.create_fnf_help_window(self)
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr("Could not open FNF help window: {error}").format(error=str(e)),
            )

    def show_contributors_window(self):
        """Shows the contributors window."""
        try:
            ContributorsWindow.show_contributors(self)
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr("Could not open contributors window: {error}").format(
                    error=str(e)
                ),
            )

    def show_compression_settings(self):
        """Shows the compression settings window for the current frame format."""
        try:
            current_format = self.ui.frame_format_combobox.currentText()
            dialog = CompressionSettingsWindow(
                parent=self,
                settings_manager=self.settings_manager,
                app_config=self.app_config,
                current_format=current_format,
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr("Could not open compression settings window: {error}").format(
                    error=str(e)
                ),
            )

    def create_find_and_replace_window(self):
        """Creates the Find and Replace window."""
        try:
            dialog = FindReplaceWindow(
                self.store_replace_rules, self.replace_rules, self
            )
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Warning"),
                self.tr("Could not open find/replace window: {error}").format(
                    error=str(e)
                ),
            )

    def create_settings_window(self):
        """Creates the settings overview window."""
        try:
            dialog = SettingsWindow(self, self.settings_manager)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Warning"),
                self.tr("Could not open settings window: {error}").format(error=str(e)),
            )

    def store_replace_rules(self, rules):
        """Stores the replace rules from the Find and Replace window."""
        self.replace_rules = rules

    def fnf_import_settings(self):
        """Imports settings from FNF character data file."""
        # Start from the last used input directory for FNF files
        start_directory = self.app_config.get_last_input_directory()

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Select FNF Character Data File"),
            start_directory,
            self.tr("JSON files (*.json);;All files (*.*)"),
        )

        if file_path:
            try:
                # Save the directory of the selected file for next time
                import os

                file_dir = os.path.dirname(file_path)
                self.app_config.set_last_input_directory(file_dir)

                # Use the shared FNF character data helper
                self.fnf_character_data.import_character_settings(
                    file_path, self.settings_manager
                )
                QMessageBox.information(
                    self,
                    self.tr("Success"),
                    self.tr("FNF settings imported successfully!"),
                )
                if (
                    hasattr(self, "editor_tab_widget")
                    and self.editor_tab_widget is not None
                ):
                    try:
                        self.editor_tab_widget.enable_flxsprite_origin_mode()
                    except AttributeError:
                        pass
            except Exception as e:
                QMessageBox.warning(
                    self,
                    self.tr("Error"),
                    self.tr("Failed to import FNF settings: {error}").format(
                        error=str(e)
                    ),
                )

    def check_version(self, force=False):
        """Checks for updates to the application.

        Uses asynchronous checking on startup to avoid blocking the UI.
        When force=True (user-initiated), uses synchronous check for immediate feedback.
        """
        try:
            update_checker = UpdateChecker(self.current_version)

            if force:
                # User-initiated check - use synchronous method for immediate feedback
                update_available, latest_version, update_payload = (
                    update_checker.check_for_updates(self)
                )

                if update_available:
                    launched = update_checker.download_and_install_update(
                        update_payload=update_payload,
                        latest_version=latest_version,
                        parent_window=self,
                    )
                    if launched:
                        self._prepare_for_update_shutdown(latest_version)
                elif latest_version:
                    QMessageBox.information(
                        self,
                        self.tr("Up to Date"),
                        self.tr(
                            "You are already running the latest version ({version})."
                        ).format(version=latest_version),
                    )
            else:
                # Startup check - use async to avoid blocking
                # Keep reference to update_checker to prevent garbage collection
                self._update_checker = update_checker

                def on_update_available(latest_version, metadata):
                    launched = update_checker.download_and_install_update(
                        update_payload=metadata,
                        latest_version=latest_version,
                        parent_window=self,
                    )
                    if launched:
                        self._prepare_for_update_shutdown(latest_version)

                def on_no_update():
                    print("No updates available.")

                def on_error(error_msg):
                    print(f"Update check failed: {error_msg}")

                update_checker.check_for_updates_async(
                    parent_window=self,
                    on_update_available=on_update_available,
                    on_no_update=on_no_update,
                    on_error=on_error,
                )

        except Exception as e:
            print(f"Update check exception: {e}")
            if force:
                QMessageBox.warning(
                    self,
                    self.tr("Update Check Failed"),
                    self.tr("Could not check for updates: {error}").format(
                        error=str(e)
                    ),
                )

    def _prepare_for_update_shutdown(self, target_version):
        """Notify the user and close the application so the external updater can run."""
        version_label = target_version or self.tr("latest")
        QMessageBox.information(
            self,
            self.tr("Launching Updater"),
            self.tr(
                "The updater for version {version} will launch in a new window. "
                "The application will now close."
            ).format(version=version_label),
        )

        QTimer.singleShot(0, self._shutdown_for_update)

    def _shutdown_for_update(self):
        """Forcefully close the application to allow the updater to run."""
        import time

        print("Shutting down for update...")

        # Give a brief moment for the message box to close
        time.sleep(0.5)

        app = QApplication.instance()
        if app:
            app.setQuitOnLastWindowClosed(True)

        # Close this window
        self.close()

        # Quit the application
        if app:
            app.quit()

        # Force exit after a brief delay
        time.sleep(0.5)
        print("Force exiting application...")
        os._exit(0)

    def update_ui_state(self, *args):
        """Updates the UI state based on current selections and settings."""
        both_export_unchecked = not (
            self.ui.animation_export_group.isChecked()
            or self.ui.frame_export_group.isChecked()
        )
        self.ui.start_process_button.setEnabled(not both_export_unchecked)

        has_spritesheet_selected = self.ui.listbox_png.currentItem() is not None
        self.ui.override_spritesheet_settings_button.setEnabled(
            has_spritesheet_selected
        )

        has_animation_selected = self.ui.listbox_data.currentItem() is not None
        self.ui.override_animation_settings_button.setEnabled(has_animation_selected)

    def on_animation_format_change(self):
        """Handles animation format selection changes."""
        format_index = self.ui.animation_format_combobox.currentIndex()

        # Update UI based on format capabilities (GIF is index 0)
        if format_index == 0:  # GIF
            self.ui.threshold_entry.setEnabled(True)
            self.ui.threshold_label.setEnabled(True)
        else:
            self.ui.threshold_entry.setEnabled(False)
            self.ui.threshold_label.setEnabled(False)

    def on_frame_format_change(self):
        """Handles frame format selection changes."""
        # Update compression options based on format
        # This will need to be implemented when compression widgets are added
        pass

    def on_variable_delay_toggled(self, checked):
        """Handle the variable delay menu toggle."""
        self.variable_delay = checked

    def on_fnf_idle_loop_toggled(self, checked):
        """Handle the FNF idle loop menu toggle."""
        self.fnf_idle_loop = checked
        # Update the app config if needed
        if hasattr(self.app_config, "settings"):
            self.app_config.settings["fnf_idle_loop"] = checked

    def start_process(self):
        """Prepares and starts the processing thread."""
        # Use the extract tab widget's preparation method
        is_ready, error_message, spritesheet_list = (
            self.extract_tab_widget.prepare_for_extraction()
        )

        if not is_ready:
            QMessageBox.warning(self, self.tr("Error"), error_message)
            return

        # Create a temporary extractor instance with required arguments
        temp_extractor = Extractor(
            progress_callback=None,
            current_version=self.current_version,
            settings_manager=self.settings_manager,
        )
        input_dir = self.extract_tab_widget.get_input_directory()
        if temp_extractor._handle_unknown_spritesheets_background_detection(
            input_dir, spritesheet_list, self
        ):
            # User cancelled background detection
            return

        # Create and show processing window
        self.processing_window = ProcessingWindow(self)
        self.processing_window.start_processing(len(spritesheet_list))
        self.processing_window.show()
        self.processing_window.raise_()  # Bring to front
        self.processing_window.activateWindow()  # Make it active

        # Set processing state
        self.extract_tab_widget.set_processing_state(True)

        # Start extraction in worker thread
        self.worker = ExtractorWorker(self, spritesheet_list)
        self.worker.extraction_completed.connect(self.on_extraction_completed)
        self.worker.extraction_failed.connect(self.on_extraction_failed)
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.statistics_updated.connect(self.on_statistics_updated)
        self.worker.debug_message.connect(self.on_debug_message)
        self.worker.error_occurred.connect(self.on_worker_error)
        self.worker.question_needed.connect(self.on_worker_question)
        self.worker.start()

    def run_extractor_core(self, spritesheet_list, progress_signal):
        """Core extraction logic (runs in worker thread)."""
        try:
            print(f"[run_extractor_core] Starting with {len(spritesheet_list)} files")

            # Create progress callback that emits signals to update UI
            def progress_callback(current, total, status=""):
                print(f"[progress_callback] {current}/{total} - {status}")
                progress_signal(current, total, status)

            # Create statistics callback to track generation statistics
            def statistics_callback(
                frames_generated, animations_generated, sprites_failed
            ):
                print(
                    f"[statistics_callback] F:{frames_generated}, A:{animations_generated}, S:{sprites_failed}"
                )
                if hasattr(self, "worker") and self.worker:
                    print(
                        f"[statistics_callback] Emitting to worker: F:{frames_generated}, A:{animations_generated}, S:{sprites_failed}"
                    )
                    self.worker.emit_statistics(
                        frames_generated, animations_generated, sprites_failed
                    )
                else:
                    print(
                        "[statistics_callback] No worker available to emit statistics"
                    )

            # Create debug callback to send processing log updates
            def debug_callback(message):
                print(f"[debug_callback] {message}")
                # Emit debug message through a new signal
                if hasattr(self.worker, "debug_message"):
                    self.worker.debug_message.emit(message)

            # Create extractor instance
            extractor = Extractor(
                progress_callback,
                self.current_version,
                self.settings_manager,
                app_config=self.app_config,
                statistics_callback=statistics_callback,
            )

            # Set additional callbacks
            extractor.debug_callback = debug_callback
            extractor.fnf_idle_loop = self.fnf_idle_loop

            # Run extraction
            input_dir = self.extract_tab_widget.get_input_directory()
            output_dir = self.ui.output_dir_label.text()

            print(f"[run_extractor_core] Input: {input_dir}, Output: {output_dir}")

            extractor.process_directory(
                input_dir,
                output_dir,
                parent_window=self,
                spritesheet_list=spritesheet_list,
            )

            return "Extraction completed successfully!"

        except Exception as e:
            print(f"[run_extractor_core] Error: {str(e)}")
            raise e

    def on_extraction_completed(self, completion_message):
        """Called when extraction completes successfully."""
        print(f"[on_extraction_completed] {completion_message}")
        self.extract_tab_widget.set_processing_state(False)

        if hasattr(self, "processing_window"):
            self.processing_window.processing_completed(True, completion_message)

    def on_extraction_failed(self, error_message):
        """Called when extraction fails."""
        print(f"[on_extraction_failed] {error_message}")
        self.extract_tab_widget.set_processing_state(False)
        if hasattr(self, "processing_window"):
            self.processing_window.processing_completed(False, error_message)

    def on_progress_updated(self, current, total, status):
        """Updates the processing window with progress information."""
        print(f"[on_progress_updated] {current}/{total} - {status}")
        if hasattr(self, "processing_window") and self.processing_window:
            self.processing_window.update_progress(current, total, status)
        else:
            print("[on_progress_updated] No processing window available")

    def on_statistics_updated(
        self, frames_generated, animations_generated, sprites_failed
    ):
        """Updates the processing window with statistics information."""
        print(
            f"[on_statistics_updated] F:{frames_generated}, A:{animations_generated}, S:{sprites_failed}"
        )
        if hasattr(self, "processing_window") and self.processing_window:
            self.processing_window.update_statistics(
                frames_generated, animations_generated, sprites_failed
            )
        else:
            print("[on_statistics_updated] No processing window available")

    def on_debug_message(self, message):
        """Handle debug messages from worker thread."""
        print(f"[on_debug_message] {message}")
        if hasattr(self, "processing_window") and self.processing_window:
            self.processing_window.add_debug_message(message)
        else:
            print("[on_debug_message] No processing window available")

    def on_worker_error(self, title, message):
        """Handle error messages from worker thread."""
        QMessageBox.critical(self, title, message)

    def on_worker_question(self, title, message):
        """Handle question dialogs from worker thread."""
        reply = QMessageBox.question(
            self,
            title,
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        # Send the response back to the worker
        if hasattr(self, "worker"):
            self.worker.continue_on_error = reply == QMessageBox.StandardButton.Yes

    def closeEvent(self, event):
        """Handles the window close event."""
        # Clean up temporary files
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
            # Clean up manual selection temp directory
            if self.manual_selection_temp_dir:
                shutil.rmtree(self.manual_selection_temp_dir, ignore_errors=True)
        except Exception:
            pass

        # Save settings if needed
        try:
            self.app_config.save_settings()
        except Exception:
            pass

        event.accept()

    def change_language(self, language_code):
        """Change the application language and refresh the UI."""
        try:
            # Check if machine translation disclaimer should be shown
            if hasattr(self, "translation_manager"):
                # Get language display name
                available_languages = self.translation_manager.get_available_languages()
                language_name = available_languages.get(language_code, {}).get(
                    "name", language_code
                )

                # Show machine translation disclaimer if needed
                if not MachineTranslationDisclaimerDialog.show_machine_translation_disclaimer(
                    self, self.translation_manager, language_code, language_name
                ):
                    # User cancelled the language change
                    return

            # Update the config
            self.app_config.set_language(language_code)

            # Load the new translation
            if hasattr(self, "translation_manager"):
                success = self.translation_manager.load_translation(language_code)
                if success:
                    # Refresh the UI with new translations
                    self.translation_manager.refresh_ui(self)

                    # Retranslate all UI elements and update runtime tab labels
                    self.ui.retranslateUi(self)
                    self.update_dynamic_tab_labels()

                    # Show success message (in the new language)
                    from PySide6.QtCore import QCoreApplication

                    success_msg = QCoreApplication.translate(
                        "TextureAtlasExtractorApp", "Language changed successfully!"
                    )
                    QMessageBox.information(self, self.tr("Success"), success_msg)
                else:
                    # Show error message
                    QMessageBox.warning(
                        self,
                        self.tr("Error"),
                        self.tr("Could not load language '{language}'").format(
                            language=language_code
                        ),
                    )

        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Error"),
                self.tr("Failed to change language: {error}").format(error=str(e)),
            )

    def get_available_languages(self):
        """Get list of available languages for the language selector."""
        if hasattr(self, "translation_manager"):
            return self.translation_manager.get_available_languages()
        return {"en": "English"}

    def get_complete_preview_settings(self, spritesheet_name, animation_name):
        """Get complete settings for preview, merging global, spritesheet, and animation overrides."""
        # Update global settings through the extract tab widget
        if hasattr(self, "extract_tab_widget") and self.extract_tab_widget:
            self.extract_tab_widget.update_global_settings()

        full_animation_name = f"{spritesheet_name}/{animation_name}"

        # Get merged settings using the settings manager
        complete_settings = self.settings_manager.get_settings(
            spritesheet_name, full_animation_name
        )

        # For preview, force certain settings to ensure good preview experience
        preview_overrides = {
            "frame_selection": "All",  # Always show all frames in preview
            "crop_option": "None",  # No cropping for preview to see full frames
            "animation_export": True,  # Always export animation for preview
        }

        complete_settings.update(preview_overrides)

        return complete_settings

    def show_animation_preview_window(self, animation_path, settings):
        """Shows the animation preview window for the given animation file."""
        # APNG preview is disabled due to a bug
        if settings.get("animation_format", "GIF").upper() == "APNG":
            QMessageBox.warning(
                self,
                "Preview Unavailable",
                "APNG preview is currently disabled due to a bug.\n\n"
                "Please use GIF or WebP format for preview.",
            )
            return

        try:
            from gui.extractor.animation_preview_window import (
                AnimationPreviewWindow,
            )

            # Create and show the preview window
            preview_window = AnimationPreviewWindow(self, animation_path, settings)

            # Connect signal to handle saved settings
            preview_window.settings_saved.connect(self.handle_preview_settings_saved)

            preview_window.exec()
        except Exception as e:
            QMessageBox.warning(
                self,
                self.tr("Preview Error"),
                self.tr("Could not open animation preview: {error}").format(
                    error=str(e)
                ),
            )

    def handle_preview_settings_saved(self, preview_settings):
        """Handle settings saved from animation preview window"""
        # Get current animation details from extract tab widget
        if not hasattr(self, "extract_tab_widget") or not self.extract_tab_widget:
            return

        # Get the selected spritesheet and animation using extract tab widget methods
        spritesheet_name = self.extract_tab_widget.get_selected_spritesheet()
        animation_name = self.extract_tab_widget.get_selected_animation()

        if not spritesheet_name or not animation_name:
            return

        full_anim_name = "{spritesheet}/{animation}".format(
            spritesheet=spritesheet_name, animation=animation_name
        )

        # Save the preview settings using the settings manager
        self.settings_manager.animation_settings[full_anim_name] = preview_settings

        # Emit signal so any listening dialogs (like override settings) can close
        self.preview_settings_saved.emit(full_anim_name)

        # Show confirmation message
        QMessageBox.information(
            self,
            self.tr("Settings Saved"),
            self.tr("Animation override settings have been saved for '{name}'.").format(
                name=full_anim_name
            ),
        )

    def preview_animation_with_paths(
        self,
        spritesheet_path,
        metadata_path,
        animation_name,
        spritemap_info=None,
        spritesheet_label=None,
    ):
        """Preview an animation given the paths and animation name. Used by ExtractTabWidget."""
        try:
            # Generate temp animation for preview
            from core.extractor import Extractor

            extractor = Extractor(None, self.current_version, self.settings_manager)

            # Get spritesheet name from path for settings lookup
            spritesheet_name = spritesheet_label or os.path.basename(spritesheet_path)

            # Get complete preview settings that include global, spritesheet, and animation overrides
            preview_settings = self.get_complete_preview_settings(
                spritesheet_name, animation_name
            )

            temp_path = extractor.generate_temp_animation_for_preview(
                atlas_path=spritesheet_path,
                metadata_path=metadata_path,
                settings=preview_settings,
                animation_name=animation_name,
                spritemap_info=spritemap_info,
                spritesheet_label=spritesheet_name,
            )

            if temp_path and os.path.exists(temp_path):
                # Show animation preview
                self.show_animation_preview_window(temp_path, preview_settings)
            else:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    self.tr("Preview Error"),
                    self.tr("Could not generate animation preview."),
                )

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.warning(
                self,
                self.tr("Preview Error"),
                self.tr("Failed to preview animation: {error}").format(error=str(e)),
            )

    def open_animation_in_editor(
        self,
        spritesheet_name: str,
        animation_name: str,
        spritesheet_path: str,
        metadata_path: Optional[str],
        spritemap_info: Optional[dict] = None,
        spritemap_target: Optional[dict] = None,
    ):
        """Send an animation to the editor tab for manual alignment."""
        if not hasattr(self, "editor_tab_widget") or not self.editor_tab_widget:
            QMessageBox.warning(
                self,
                self.tr("Editor"),
                self.tr("The editor tab is not available in this session."),
            )
            return

        self.editor_tab_widget.add_animation_from_extractor(
            spritesheet_name,
            animation_name,
            spritesheet_path,
            metadata_path,
            spritemap_info,
            spritemap_target,
        )
        self.ui.tools_tab.setCurrentWidget(self.editor_tab_widget)


def apply_color_scheme(app: QApplication, scheme: str) -> None:
    """Apply the specified color scheme to the application.

    Args:
        app: The QApplication instance.
        scheme: One of 'auto', 'light', or 'dark'.
    """
    style_hints = app.styleHints()
    if scheme == "light":
        style_hints.setColorScheme(Qt.ColorScheme.Light)
    elif scheme == "dark":
        style_hints.setColorScheme(Qt.ColorScheme.Dark)
    else:
        style_hints.setColorScheme(Qt.ColorScheme.Unknown)


def main():
    """Main entry point for the application."""
    # Enable high DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)

    # Set application properties
    app.setApplicationName("TextureAtlas Toolbox")
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("AutisticLulu")

    # Apply color scheme from config before creating the main window
    config = AppConfig()
    color_scheme = config.get_color_scheme()
    apply_color_scheme(app, color_scheme)

    # Create and show the main window
    window = TextureAtlasExtractorApp()
    window.show()

    # Start the event loop
    sys.exit(app.exec())


def run_updater(
    exe_mode: bool = False,
    embedded_mode: bool = False,
    wait_seconds: int = 3,
    target_tag: str = None,
    app_root: str = None,
):
    """Run the updater in a separate process context with Qt GUI."""
    import time
    import json
    import threading
    from utils.update_installer import Updater, UpdateMode, UpdateUtilities

    # Import QtUpdateDialog - it's available since Qt is required for Main.py
    try:
        from utils.update_installer import QtUpdateDialog
    except ImportError:
        print("Error: Qt components not available for updater dialog")
        return

    print("Starting update process...")
    if wait_seconds > 0:
        print(f"Waiting {wait_seconds} seconds for main app to close...")
        time.sleep(wait_seconds)

    # Resolve update mode
    if exe_mode:
        update_mode = UpdateMode.EXECUTABLE
    elif embedded_mode:
        update_mode = UpdateMode.EMBEDDED
    else:
        # Auto-detect based on environment
        update_mode = UpdateUtilities.detect_update_mode()

    mode_labels = {
        UpdateMode.SOURCE: "source",
        UpdateMode.EXECUTABLE: "executable",
        UpdateMode.EMBEDDED: "embedded Python",
    }
    mode_label = mode_labels.get(update_mode, "unknown")
    print(f"Update mode: {mode_label}")

    # Check for metadata file passed via environment
    release_metadata = {}
    metadata_path = os.environ.get("UPDATER_METADATA_FILE")
    if metadata_path and os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                release_metadata = json.load(f)
            print(f"Loaded release metadata from {metadata_path}")
            # Clean up after reading
            os.remove(metadata_path)
        except Exception as e:
            print(f"Warning: Could not load metadata file: {e}")

    # Create Qt application for the updater dialog
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("TextureAtlas Toolbox Updater")
    app.setApplicationVersion(APP_VERSION)

    # Create and show the update dialog
    dialog = QtUpdateDialog(None)

    # Create updater with the dialog as UI
    updater = Updater(
        ui=dialog,
        update_mode=update_mode,
        target_tag=target_tag or release_metadata.get("tag_name"),
        release_metadata=release_metadata,
        app_root=app_root,
    )

    dialog.log(f"Starting {mode_label} update...", "info")
    dialog.log(f"Currently running version {APP_VERSION}", "info")
    if target_tag:
        dialog.log(f"Target version: {target_tag}", "info")

    def _run_update():
        try:
            print(f"[Worker Thread] Starting {mode_label} update...")
            if update_mode == UpdateMode.EXECUTABLE:
                updater.update_exe()
            elif update_mode == UpdateMode.EMBEDDED:
                updater.update_embedded()
            else:
                updater.update_source()
            print("[Worker Thread] Update completed successfully")
        except Exception as err:
            print(f"[Worker Thread] Error: {err}")
            import traceback

            traceback.print_exc()
            dialog.log(f"Update process encountered an error: {err}", "error")
            dialog.allow_close()
        else:
            dialog.allow_close()

    # Run update in a separate thread so dialog stays responsive
    worker = threading.Thread(target=_run_update, daemon=True)
    worker.start()

    # Show dialog and block until closed
    dialog.exec()
    print("[Main Thread] Updater dialog closed")


if __name__ == "__main__":
    import argparse

    try:
        parser = argparse.ArgumentParser(description="TextureAtlas Toolbox")
        parser.add_argument("--update", action="store_true", help="Run in update mode")
        parser.add_argument(
            "--exe-mode", action="store_true", help="Force executable update mode"
        )
        parser.add_argument(
            "--embedded-mode",
            action="store_true",
            help="Force embedded Python update mode",
        )
        parser.add_argument(
            "--target-tag",
            type=str,
            default=None,
            help="Target version tag to update to",
        )
        parser.add_argument(
            "--wait", type=int, default=3, help="Seconds to wait before starting update"
        )
        parser.add_argument(
            "--app-root",
            type=str,
            default=None,
            help="Override app root directory (used when running from temp Python)",
        )
        args = parser.parse_args()

        if args.update:
            # Update mode: run the updater instead of the main app
            # Priority: explicit flags > auto-detection
            run_updater(
                exe_mode=args.exe_mode,
                embedded_mode=args.embedded_mode,
                wait_seconds=args.wait,
                target_tag=args.target_tag,
                app_root=args.app_root,
            )
        else:
            # Normal mode: run the main application
            print("Starting main application...")
            main()

    except Exception as e:
        print(f"Fatal error during startup: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
