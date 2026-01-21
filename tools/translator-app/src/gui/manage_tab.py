"""Manage tab widget for translation file and language operations.

Provides a UI for running Qt localization commands (lupdate, lrelease),
managing the language registry, tracking translation progress across files,
and batch operations like removing vanished strings or MT disclaimers.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt, QThreadPool, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QVBoxLayout,
    QWidget,
)

from .add_language_dialog import AddLanguageDialog
from .batch_unused_dialog import BatchUnusedStringsDialog
from .icon_provider import IconProvider, IconStyle, IconType
from .string_matching_dialog import (
    StringMatchingDialog,
    apply_matches_to_file,
    extract_new_unfinished_strings,
    find_potential_matches,
    recover_duplicate_translations,
)
from localization import (
    LANGUAGE_REGISTRY,
    LocalizationOperations,
    OperationResult,
    save_language_registry,
)
from utils import BackgroundTaskWorker


class ManageTab(QWidget):
    """Widget tab for managing translation files and running localization tasks.

    Provides controls to select languages, run lupdate/lrelease, regenerate
    resource files, and view translation progress in a status table.

    Attributes:
        localization_ops: Backend helper for running translation commands.
        thread_pool: Qt thread pool for background task execution.
        language_list_widget: List widget displaying registered languages.
        manage_table: Table showing translation progress per language.
        manage_log_view: Text area displaying command output.
    """

    def __init__(
        self,
        *,
        parent: QWidget,
        localization_ops: LocalizationOperations,
        thread_pool: QThreadPool,
        status_bar: Optional[QStatusBar] = None,
        on_translations_dir_changed: Optional[Callable[[Path], None]] = None,
        open_ts_callback: Optional[Callable[[Path], None]] = None,
    ) -> None:
        """Initialize the manage tab.

        Args:
            parent: Parent widget.
            localization_ops: Backend for running translation commands.
            thread_pool: Pool for background task execution.
            status_bar: Optional status bar for messages.
            on_translations_dir_changed: Callback when translations folder changes.
            open_ts_callback: Callback to open a .ts file in the editor tab.
        """
        super().__init__(parent)
        self.localization_ops = localization_ops
        self.thread_pool = thread_pool
        self.status_bar = status_bar
        self._translations_dir_changed = on_translations_dir_changed
        self._open_ts_callback = open_ts_callback

        self.language_list_widget: Optional[QListWidget] = None
        self.manage_status_label: Optional[QLabel] = None
        self.manage_log_view: Optional[QPlainTextEdit] = None
        self.manage_table: Optional[QTableWidget] = None
        self.manage_action_buttons: List[QPushButton] = []
        self.manage_task_running = False
        self.translations_path_label: Optional[QLabel] = None
        self.src_path_label: Optional[QLabel] = None
        self.src_warning_label: Optional[QLabel] = None
        self._pending_extract_languages: List[str] = []
        self._current_worker: Optional[BackgroundTaskWorker] = None

        self._build_ui()
        self.populate_language_list(preserve_selection=False)
        self._refresh_status_table()

    def _build_ui(self) -> None:
        """Construct the tab layout with language list, action buttons, and status.

        Creates path selectors for source and translations folders, a language
        list with selection controls, action buttons for lupdate/lrelease/etc.,
        a status table, and a log viewer.
        """
        layout = QVBoxLayout(self)

        # Source directory row (TextureAtlas Toolbox src folder)
        src_row = QHBoxLayout()
        src_caption = QLabel("Source Directory:")
        src_caption.setMinimumWidth(140)
        src_row.addWidget(src_caption)
        self.src_path_label = QLabel()
        self.src_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        src_row.addWidget(self.src_path_label, 1)
        self.src_warning_label = QLabel()
        src_row.addWidget(self.src_warning_label)
        src_change_btn = QPushButton("Browse...")
        src_change_btn.setToolTip(
            "Select the TextureAtlas Toolbox 'src' folder if auto-detection failed."
        )
        src_change_btn.clicked.connect(self.prompt_src_folder)
        src_row.addWidget(src_change_btn)
        layout.addLayout(src_row)
        self._update_src_path_label()

        path_row = QHBoxLayout()
        path_caption = QLabel("Translations Folder:")
        path_caption.setMinimumWidth(140)
        path_row.addWidget(path_caption)
        self.translations_path_label = QLabel()
        self.translations_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_row.addWidget(self.translations_path_label, 1)
        change_btn = QPushButton("Change Folder...")
        change_btn.clicked.connect(self.prompt_translations_folder)
        path_row.addWidget(change_btn)
        layout.addLayout(path_row)
        self._update_translations_path_label()

        top_layout = QHBoxLayout()

        language_group = QGroupBox("Languages")
        language_layout = QVBoxLayout(language_group)
        self.language_list_widget = QListWidget()
        self.language_list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        self.language_list_widget.setToolTip(
            "Click to select one language. Hold Shift for ranges or Ctrl for individual toggles."
        )
        self.language_list_widget.itemDoubleClicked.connect(
            self._handle_language_double_click
        )
        self.language_list_widget.itemSelectionChanged.connect(
            self._update_disclaimer_button_text
        )
        language_layout.addWidget(self.language_list_widget)

        selector_row = QHBoxLayout()
        select_all_btn = QPushButton("Select All")
        select_all_btn.setToolTip("Highlight every language in the list.")
        select_all_btn.clicked.connect(self.select_all_languages)
        selector_row.addWidget(select_all_btn)
        clear_btn = QPushButton("Clear Selection")
        clear_btn.setToolTip("Remove the current selection.")
        clear_btn.clicked.connect(self.clear_language_selection)
        selector_row.addWidget(clear_btn)
        edit_btn = QPushButton("Edit Details...")
        edit_btn.setToolTip(
            "Update the display names or quality flag for the selected language."
        )
        edit_btn.clicked.connect(self.prompt_edit_language)
        selector_row.addWidget(edit_btn)
        add_btn = QPushButton("Add Language...")
        add_btn.setToolTip("Register a brand new language entry.")
        add_btn.clicked.connect(self.prompt_add_language)
        selector_row.addWidget(add_btn)
        delete_btn = QPushButton("Remove Selected...")
        delete_btn.setToolTip(
            "Delete the highlighted languages from the registry (optionally removing files)."
        )
        delete_btn.clicked.connect(self.prompt_delete_languages)
        selector_row.addWidget(delete_btn)
        selector_row.addStretch(1)
        language_layout.addLayout(selector_row)
        top_layout.addWidget(language_group, 2)

        actions_group = QGroupBox("Actions")
        actions_layout = QGridLayout(actions_group)
        buttons = [
            (
                "Update selected files",
                "extract",
                "Runs `lupdate` to get the latest translateable strings for the selected .ts file.\n\nRequires This directly detects new and obsolete strings from the source code files.",
            ),
            (
                "Build selected files",
                "compile",
                "Runs `lrelease` to build .qm files for the selected .ts files.",
            ),
            (
                "Regenerate resource file",
                "resource",
                "Writes the translations.qrc referencing the current compiled files.",
            ),
            (
                "Toggle MT Disclaimers",
                "disclaimer",
                "Add or remove the machine translation notice for selected languages.",
            ),
        ]
        self.manage_action_buttons = []
        self.disclaimer_button: Optional[QPushButton] = None
        for index, (label, action, tooltip) in enumerate(buttons):
            button = QPushButton(label)
            button.setToolTip(tooltip)
            button.clicked.connect(
                lambda _=False, op=action: self.run_manage_operation(op)
            )
            row = index // 2
            col = index % 2
            actions_layout.addWidget(button, row, col)
            self.manage_action_buttons.append(button)
            if action == "disclaimer":
                self.disclaimer_button = button
        top_layout.addWidget(actions_group, 3)

        layout.addLayout(top_layout)

        self.manage_status_label = QLabel("Idle")
        layout.addWidget(self.manage_status_label)

        self.manage_table = QTableWidget(0, 7)
        self.manage_table.setHorizontalHeaderLabels(
            ["Locale", ".ts", ".qm", "Progress", "Machine", "Needs Update", "Quality"]
        )
        self.manage_table.verticalHeader().setVisible(False)
        self.manage_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.manage_table.setSelectionMode(QTableWidget.NoSelection)
        header = self.manage_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.manage_table)

        self.manage_log_view = QPlainTextEdit()
        self.manage_log_view.setReadOnly(True)
        self.manage_log_view.setPlaceholderText("Run an action to see logs here...")
        layout.addWidget(self.manage_log_view)

    def populate_language_list(
        self,
        *,
        preserve_selection: bool = True,
        ensure_selected: Optional[Sequence[str]] = None,
    ) -> None:
        """Refresh the language list widget from the registry.

        Args:
            preserve_selection: Keep previously selected items selected.
            ensure_selected: If provided, select these language codes.
        """
        if not self.language_list_widget:
            return
        if preserve_selection and ensure_selected is None:
            selected_codes = set(self.get_selected_languages())
        else:
            selected_codes = {code.lower() for code in ensure_selected or []}
        self.language_list_widget.clear()
        icon_provider = IconProvider.instance()
        for code in sorted(LANGUAGE_REGISTRY.keys()):
            # Skip English - it's the source language, not a translation target
            if code.lower() == "en":
                continue
            meta = LANGUAGE_REGISTRY[code]
            display_name = meta.get("name", code)
            english = meta.get("english_name")
            if english and english != display_name:
                display_name = f"{display_name} ({english})"

            quality = meta.get("quality", "")
            indicator_text, indicator_icon = icon_provider.get_quality_indicator(
                quality
            )
            locale_label = self._format_locale_label(code)
            item = QListWidgetItem(f"{display_name} ({locale_label}){indicator_text}")
            if indicator_icon:
                item.setIcon(indicator_icon)
            item.setData(Qt.UserRole, code)
            self.language_list_widget.addItem(item)
            if code in selected_codes:
                item.setSelected(True)
        # Force immediate UI update
        self.language_list_widget.update()
        self.language_list_widget.repaint()
        QApplication.processEvents()

    def check_incomplete_locale_codes(self) -> None:
        """Check for incomplete locale codes and prompt user to fix them.

        Call this after the main window is shown to avoid blocking startup.
        """
        QTimer.singleShot(100, self._prompt_fix_incomplete_locales)

    def _prompt_fix_incomplete_locales(self) -> None:
        """Show warning for incomplete locales and offer to fix them.

        Scans the registry for base-only codes (e.g., 'fr' instead of 'fr_FR')
        and prompts the user to migrate each to a full locale code.
        """
        if not hasattr(self, "_locale_warning_shown"):
            self._locale_warning_shown: set[str] = set()

        base_codes = [
            code
            for code in LANGUAGE_REGISTRY.keys()
            if "_" not in code
            and code.lower() != "en"  # Skip English - it's the source language
            and code not in self._locale_warning_shown
        ]

        if not base_codes:
            return

        self._locale_warning_shown.update(base_codes)
        codes_list = ", ".join(f'"{c}"' for c in sorted(base_codes))

        reply = QMessageBox.question(
            self,
            "Incomplete Locale Codes Detected",
            f"The following languages use base codes without a locale:\n\n"
            f"{codes_list}\n\n"
            f"Full locale codes (e.g., 'fr_FR' instead of 'fr') are recommended "
            f"for proper language identification.\n\n"
            f"Would you like to fix them now?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply != QMessageBox.Yes:
            return

        for code in sorted(base_codes):
            self._fix_single_locale_code(code)

    def _fix_single_locale_code(self, old_code: str) -> None:
        """Open edit dialog to fix a single incomplete locale code.

        Args:
            old_code: The language code to fix (e.g., 'fr').
        """
        meta = LANGUAGE_REGISTRY.get(old_code)
        if not meta:
            return

        dialog = AddLanguageDialog(
            self,
            initial_data={
                "code": old_code,
                "native_name": meta.get("name", old_code),
                "english_name": meta.get("english_name", meta.get("name", old_code)),
                "quality": meta.get("quality", "unknown"),
            },
            code_editable=True,  # Allow changing the code
        )
        dialog.setWindowTitle(f"Fix Locale Code: {old_code.upper()}")

        if dialog.exec() != QDialog.Accepted:
            return

        data = dialog.get_data()
        if not data:
            return

        new_code = data["code"].lower()

        # If code unchanged, just update metadata
        if new_code == old_code:
            LANGUAGE_REGISTRY[old_code] = {
                "name": data["native_name"],
                "english_name": data["english_name"],
                "quality": data["quality"],
            }
            save_language_registry(LANGUAGE_REGISTRY)
            self.populate_language_list(preserve_selection=False)
            self._refresh_status_table()
            self._update_disclaimer_button_text()
            return

        # Code changed - need to rename files and update registry
        self._migrate_language_code(old_code, new_code, data)

    def _migrate_language_code(
        self, old_code: str, new_code: str, data: Dict[str, str]
    ) -> None:
        """Migrate a language from old code to new code.

        Renames files and updates the registry.

        Args:
            old_code: Original language code.
            new_code: New language code.
            data: New metadata from the dialog.
        """
        translations_dir = self.localization_ops.paths.translations_dir
        renamed_files: list[str] = []
        failed_renames: list[str] = []

        # Update language attribute inside .ts file before renaming
        old_ts_path = translations_dir / f"app_{old_code}.ts"
        if old_ts_path.exists():
            try:
                content = old_ts_path.read_text(encoding="utf-8")
                # Update the language attribute in the TS root element
                # Format: <TS version="2.1" language="xx"> or <TS language="xx" version="2.1">
                # Match language="old_code" (case-insensitive for the code)
                pattern = r'(<TS[^>]*\slanguage=")' + re.escape(old_code) + r'(")'
                replacement = r"\g<1>" + new_code + r"\g<2>"
                updated_content, count = re.subn(
                    pattern, replacement, content, flags=re.IGNORECASE
                )
                if count > 0:
                    old_ts_path.write_text(updated_content, encoding="utf-8")
                    if self.manage_log_view:
                        self.manage_log_view.appendPlainText(
                            f"    Updated language attribute in {old_ts_path.name}\n"
                        )
            except Exception as exc:
                if self.manage_log_view:
                    self.manage_log_view.appendPlainText(
                        f"    Warning: Could not update language attribute: {exc}\n"
                    )

        # Rename .ts and .qm files
        for suffix in (".ts", ".qm"):
            old_path = translations_dir / f"app_{old_code}{suffix}"
            new_path = translations_dir / f"app_{new_code}{suffix}"

            if not old_path.exists():
                continue

            if new_path.exists():
                failed_renames.append(
                    f"{old_path.name} -> {new_path.name}: Target already exists"
                )
                continue

            try:
                old_path.rename(new_path)
                renamed_files.append(f"{old_path.name} -> {new_path.name}")
            except OSError as exc:
                failed_renames.append(f"{old_path.name}: {exc}")

        if failed_renames:
            QMessageBox.warning(
                self,
                "File Rename Issues",
                "Some files could not be renamed:\n" + "\n".join(failed_renames),
            )

        # Add new registry entry
        LANGUAGE_REGISTRY[new_code] = {
            "name": data["native_name"],
            "english_name": data["english_name"],
            "quality": data["quality"],
        }
        save_language_registry(LANGUAGE_REGISTRY)

        # Log the migration
        if self.manage_log_view:
            self.manage_log_view.appendPlainText(
                f"[MIGRATE] {old_code.upper()} -> {new_code.upper()}\n"
            )
            if renamed_files:
                self.manage_log_view.appendPlainText(
                    "    Renamed: " + ", ".join(renamed_files) + "\n"
                )

        # Ask to remove old entry
        reply = QMessageBox.question(
            self,
            "Remove Old Language Entry",
            f"Language files have been renamed to use '{new_code.upper()}'.\n\n"
            f"Do you want to remove the old '{old_code.upper()}' entry from the registry?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )

        if reply == QMessageBox.Yes and old_code in LANGUAGE_REGISTRY:
            LANGUAGE_REGISTRY.pop(old_code, None)
            save_language_registry(LANGUAGE_REGISTRY)
            if self.manage_log_view:
                self.manage_log_view.appendPlainText(
                    f"    Removed old entry: {old_code.upper()}\n"
                )

        self.populate_language_list(
            preserve_selection=False, ensure_selected=[new_code]
        )
        self._refresh_status_table()
        self._update_disclaimer_button_text()

        if self.status_bar:
            self.status_bar.showMessage(
                f"Migrated {old_code.upper()} to {new_code.upper()}."
            )

    def select_all_languages(self) -> None:
        """Select all languages in the list widget.

        Uses Qt's selectAll() to highlight every item in the language list.
        """
        if self.language_list_widget:
            self.language_list_widget.selectAll()

    def clear_language_selection(self) -> None:
        """Clear the current language selection.

        Deselects all items in the language list widget.
        """
        if self.language_list_widget:
            self.language_list_widget.clearSelection()

    def _update_disclaimer_button_text(self) -> None:
        """Update disclaimer button text based on selection's disclaimer state.

        Sets the button label to 'Add', 'Remove', or 'Toggle' depending on
        whether selected languages have disclaimers present.
        """
        if not self.disclaimer_button or not self.language_list_widget:
            return

        selected_items = self.language_list_widget.selectedItems()
        if not selected_items:
            self.disclaimer_button.setText("Toggle MT Disclaimers")
            self.disclaimer_button.update()
            self.disclaimer_button.repaint()
            return

        languages = [
            item.data(Qt.UserRole) for item in selected_items if item.data(Qt.UserRole)
        ]
        if not languages:
            self.disclaimer_button.setText("Toggle MT Disclaimers")
            self.disclaimer_button.update()
            self.disclaimer_button.repaint()
            return

        has_disclaimer_count = sum(
            1 for lang in languages if self.localization_ops.has_disclaimer(lang)
        )

        if has_disclaimer_count == len(languages):
            self.disclaimer_button.setText("Remove MT Disclaimers")
        elif has_disclaimer_count == 0:
            self.disclaimer_button.setText("Add MT Disclaimers")
        else:
            self.disclaimer_button.setText("Toggle MT Disclaimers")

        # Force UI update
        self.disclaimer_button.update()
        self.disclaimer_button.repaint()
        QApplication.processEvents()

    def _handle_language_double_click(self, item: QListWidgetItem) -> None:
        """Open the corresponding .ts file when a language is double-clicked.

        Args:
            item: The list widget item that was double-clicked.
        """
        if not item:
            return
        code = item.data(Qt.UserRole)
        if not code:
            return
        ts_path = self.localization_ops.paths.translations_dir / f"app_{code}.ts"
        if not ts_path.exists():
            QMessageBox.information(
                self,
                "File Not Found",
                f"No translation file found for {code.upper()} in {self.localization_ops.paths.translations_dir}.",
            )
            return
        if self._open_ts_callback:
            self._open_ts_callback(ts_path)
        elif hasattr(self.parent(), "load_ts_file"):
            try:
                self.parent().load_ts_file(str(ts_path))  # type: ignore[attr-defined]
            except Exception:
                pass

    def prompt_add_language(self) -> None:
        """Show dialog to register a new language in the registry.

        Opens AddLanguageDialog, saves the new entry to the registry, and
        optionally runs lupdate to create the initial .ts file.
        """
        dialog = AddLanguageDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data:
            return
        code = data["code"].lower()
        native_name = data["native_name"]
        english_name = data["english_name"]
        quality = data["quality"]
        if code in LANGUAGE_REGISTRY:
            overwrite = QMessageBox.question(
                self,
                "Language Exists",
                f"{code.upper()} already exists. Update its metadata?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if overwrite != QMessageBox.Yes:
                return
        LANGUAGE_REGISTRY[code] = {
            "name": native_name,
            "english_name": english_name,
            "quality": quality,
        }
        save_language_registry(LANGUAGE_REGISTRY)
        self.populate_language_list(preserve_selection=False, ensure_selected=[code])
        self._refresh_status_table()
        if self.status_bar:
            self.status_bar.showMessage(f"Added {code.upper()} to the language list.")
        if self.manage_task_running:
            QMessageBox.information(
                self,
                "Language Added",
                "Language added. Wait for the current task to finish before creating files.",
            )
            return
        should_create = QMessageBox.question(
            self,
            "Create Translation File",
            f"Do you want to run Extract now to generate app_{code}.ts?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if should_create == QMessageBox.Yes:
            self._enqueue_operation(self.localization_ops.extract, [code])

    def prompt_delete_languages(self) -> None:
        """Prompt to delete selected languages from the registry.

        Presents a confirmation dialog with options to also remove the
        corresponding .ts/.qm files from disk.
        """
        if self.manage_task_running:
            QMessageBox.information(
                self,
                "Task Running",
                "Please wait for the current operation to finish before deleting languages.",
            )
            return
        languages = self.get_selected_languages()
        if not languages:
            QMessageBox.information(
                self,
                "Delete Languages",
                "Select at least one language to delete.",
            )
            return
        codes_preview = ", ".join(code.upper() for code in languages)
        prompt = QMessageBox(self)
        prompt.setIcon(QMessageBox.Warning)
        prompt.setWindowTitle("Delete Languages")
        prompt.setText(
            f"Remove the selected languages from the registry?\n\nLanguages: {codes_preview}"
        )
        prompt.setInformativeText(
            "Deleting also removes metadata. Choose whether to delete the corresponding"
            " .ts/.qm files."
        )
        delete_files_btn = prompt.addButton(
            "Delete and Remove Files", QMessageBox.DestructiveRole
        )
        prompt.addButton("Delete (Keep Files)", QMessageBox.ActionRole)
        cancel_btn = prompt.addButton(QMessageBox.Cancel)
        prompt.setDefaultButton(cancel_btn)
        prompt.exec()
        clicked = prompt.clickedButton()
        if clicked == cancel_btn:
            return
        delete_files = clicked == delete_files_btn
        self._delete_languages(languages, delete_files)

    def prompt_translations_folder(self) -> None:
        """Prompt user to select a different translations directory.

        Opens a folder picker, validates the selection, and refreshes the
        language list and status table to reflect the new location.
        """
        if self.manage_task_running:
            QMessageBox.information(
                self,
                "Task Running",
                "Please wait for the current operation to finish before changing folders.",
            )
            return
        current_dir = str(self.localization_ops.paths.translations_dir)
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Translations Folder",
            current_dir,
        )
        if not new_dir:
            return
        try:
            self.localization_ops.set_translations_dir(Path(new_dir))
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Folder", str(exc))
            return
        self._update_translations_path_label()
        if self._translations_dir_changed:
            self._translations_dir_changed(self.localization_ops.paths.translations_dir)
        if self.status_bar:
            self.status_bar.showMessage(f"Translations folder set to {new_dir}")
        self.refresh_language_list()
        self._refresh_status_table()

    def prompt_edit_language(self) -> None:
        """Show dialog to edit metadata for the selected language.

        Opens AddLanguageDialog in edit mode. If the locale code changes,
        triggers a file migration to rename .ts/.qm files.
        """
        languages = self.get_selected_languages()
        if len(languages) != 1:
            QMessageBox.information(
                self,
                "Edit Metadata",
                "Select exactly one language to edit.",
            )
            return
        code = languages[0]
        meta = LANGUAGE_REGISTRY.get(code)
        if not meta:
            QMessageBox.warning(
                self,
                "Missing Metadata",
                f"No metadata found for {code.upper()}.",
            )
            return
        dialog = AddLanguageDialog(
            self,
            initial_data={
                "code": code,
                "native_name": meta.get("name", code),
                "english_name": meta.get("english_name", meta.get("name", code)),
                "quality": meta.get("quality", "unknown"),
            },
            code_editable=True,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data:
            return

        new_code = data["code"].lower().strip()

        # Check if locale code changed - need to migrate
        if new_code != code:
            self._migrate_language_code(code, new_code, data)
        else:
            # Just update metadata, no migration needed
            LANGUAGE_REGISTRY[code] = {
                "name": data["native_name"],
                "english_name": data["english_name"],
                "quality": data["quality"],
            }
            save_language_registry(LANGUAGE_REGISTRY)
            self.populate_language_list(
                preserve_selection=False, ensure_selected=[code]
            )
            self._refresh_status_table()
            self._update_disclaimer_button_text()
            if self.status_bar:
                self.status_bar.showMessage(f"Updated metadata for {code.upper()}.")

    def get_selected_languages(self) -> List[str]:
        """Retrieve language codes for the currently selected list items.

        Returns:
            A list of lowercase language codes for each selected item.
        """
        if not self.language_list_widget:
            return []
        return [
            item.data(Qt.UserRole)
            for item in self.language_list_widget.selectedItems()
            if item.data(Qt.UserRole)
        ]

    def run_manage_operation(self, op_name: str) -> None:
        """Dispatch a localization operation by name (extract, compile, etc.).

        Args:
            op_name: Operation key such as 'extract', 'compile', 'resource', 'all'.
        """
        if self.manage_task_running:
            QMessageBox.information(
                self, "Task Running", "Please wait for the current operation to finish."
            )
            return
        languages = self.get_selected_languages()
        language_required_ops = {"extract", "compile", "status", "disclaimer"}
        needs_languages = op_name in language_required_ops
        if needs_languages and not languages:
            QMessageBox.information(
                self,
                "Select Languages",
                "Select at least one language before running this action.",
            )
            return
        if self.status_bar:
            if needs_languages:
                self.status_bar.showMessage(
                    f"Running {op_name} task for {len(languages)} language(s)..."
                )
            else:
                self.status_bar.showMessage(f"Running {op_name} task...")
        if op_name == "extract":
            self._pending_extract_languages = languages.copy()
            self._enqueue_operation(self.localization_ops.extract, languages)
        elif op_name == "compile":
            self._enqueue_operation(self.localization_ops.compile, languages)
        elif op_name == "resource":
            self._enqueue_operation(self.localization_ops.create_resource_file)
        elif op_name == "status":
            self._enqueue_operation(self.localization_ops.status_report, languages)
        elif op_name == "disclaimer":
            self._handle_disclaimer_operation(languages)
        else:
            QMessageBox.warning(
                self, "Unknown Operation", f"Unsupported action: {op_name}"
            )

    def _enqueue_operation(self, fn: Callable[..., Any], *args: object) -> None:
        """Start a background task for the given callable.

        Args:
            fn: The function to run in the thread pool.
            *args: Arguments to pass to fn.
        """
        self.manage_task_running = True
        self.set_manage_buttons_enabled(False)
        if self.manage_status_label:
            self.manage_status_label.setText("Running...")
        worker = BackgroundTaskWorker(fn, *args)
        worker.signals.completed.connect(self._handle_operation_completed)
        worker.signals.failed.connect(self._handle_operation_failed)
        self._current_worker = worker  # Keep reference to prevent premature GC
        self.thread_pool.start(worker)

    def _handle_disclaimer_operation(self, languages: List[str]) -> None:
        """Handle disclaimer add/remove operations for selected languages.

        Args:
            languages: List of language codes to process.
        """
        if not languages:
            return

        has_disclaimer_count = sum(
            1 for lang in languages if self.localization_ops.has_disclaimer(lang)
        )

        is_removal = has_disclaimer_count == len(languages)

        if is_removal:
            lang_list = ", ".join(lang.upper() for lang in languages)
            reply = QMessageBox.question(
                self,
                "Remove MT Disclaimers",
                f"Remove machine translation disclaimers from {len(languages)} file(s)?\n\n"
                f"Languages: {lang_list}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )

            if reply == QMessageBox.Yes:
                if self.status_bar:
                    self.status_bar.showMessage(
                        f"Removing machine translation disclaimers from {len(languages)} file(s)..."
                    )

                if self.manage_log_view:
                    self.manage_log_view.appendPlainText(
                        f"Removing machine translation disclaimers from {len(languages)} file(s): {lang_list}"
                    )

                result = self.localization_ops.remove_disclaimers(languages)
                self.append_manage_log(result)

                removed_count = sum(
                    1 for log in result.logs if "Removed disclaimer" in log
                )
                skipped_count = sum(
                    1 for log in result.logs if "No disclaimer found" in log
                )

                if self.manage_log_view:
                    summary = f"Summary: {removed_count} removed"
                    if skipped_count > 0:
                        summary += f", {skipped_count} already clean"
                    if result.errors:
                        summary += f", {len(result.errors)} failed"
                    self.manage_log_view.appendPlainText(summary + "\n")

                if result.success:
                    status_msg = f"Removed machine translation disclaimers from {removed_count} file(s)"
                    if skipped_count > 0:
                        status_msg += f" ({skipped_count} already clean)"
                    if self.status_bar:
                        self.status_bar.showMessage(status_msg)
                else:
                    error_count = len(result.errors)
                    if self.status_bar:
                        self.status_bar.showMessage(
                            f"Machine translation disclaimer removal: {removed_count} OK, {error_count} failed"
                        )

                self._refresh_status_table()
                self._update_disclaimer_button_text()
        else:
            self._enqueue_operation(self.localization_ops.toggle_disclaimers, languages)

    def _handle_operation_completed(self, payload: object) -> None:
        """Process results when a background operation finishes successfully.

        Args:
            payload: The OperationResult or list of results from the worker.
        """
        self._current_worker = None
        results: List[OperationResult]
        if isinstance(payload, list):
            results = payload
        else:
            results = [payload]
        overall_success = True
        has_extract = False
        for result in results:
            if not isinstance(result, OperationResult):
                continue
            self.append_manage_log(result)
            if result.name == "status":
                entries = result.details.get("entries", []) if result.details else []
                if isinstance(entries, list):
                    self._update_status_table(entries)
            if result.name == "extract" and result.success:
                has_extract = True
            if not result.success:
                overall_success = False

        # Check for unused strings after successful extract
        if has_extract and self._pending_extract_languages:
            self._check_for_unused_strings(self._pending_extract_languages)
            self._pending_extract_languages = []

        # Refresh the status table after any operation completes
        # (unless status was already run as part of the operation)
        has_status = any(
            isinstance(r, OperationResult) and r.name == "status" for r in results
        )
        if not has_status:
            self._refresh_status_table()

        status_text = "Completed" if overall_success else "Completed with issues"
        if self.manage_status_label:
            self.manage_status_label.setText(status_text)
        if self.status_bar:
            self.status_bar.showMessage(f"Localization task {status_text.lower()}.")
        self.set_manage_buttons_enabled(True)
        self.manage_task_running = False
        # Update button text immediately and schedule a delayed update as backup
        QApplication.processEvents()
        self._update_disclaimer_button_text()
        QTimer.singleShot(200, self._update_disclaimer_button_text)

    def _handle_operation_failed(self, message: str) -> None:
        """Handle a background operation failure.

        Args:
            message: The error message from the worker.
        """
        self._current_worker = None
        if self.manage_log_view:
            self.manage_log_view.appendPlainText(f"[ERROR] {message}\n")
        if self.status_bar:
            self.status_bar.showMessage(f"Localization task failed: {message}")
        if self.manage_status_label:
            self.manage_status_label.setText("Failed")
        self.set_manage_buttons_enabled(True)
        self.manage_task_running = False

    def set_manage_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable the action buttons.

        Args:
            enabled: True to enable buttons, False to disable.
        """
        for button in self.manage_action_buttons:
            button.setEnabled(enabled)

    def _update_translations_path_label(self) -> None:
        """Refresh the translations folder label with the current path."""
        if not self.translations_path_label:
            return
        current_path = self.localization_ops.paths.translations_dir
        display = self._format_path(current_path)
        self.translations_path_label.setText(display)
        self.translations_path_label.setToolTip(str(current_path))

    def _update_src_path_label(self) -> None:
        """Update the source directory label and warning indicator.

        Shows a warning icon if the TextureAtlas Toolbox project could not
        be auto-detected.
        """
        if not self.src_path_label:
            return
        current_path = self.localization_ops.paths.src_dir
        display = self._format_path(current_path)
        self.src_path_label.setText(display)
        self.src_path_label.setToolTip(str(current_path))

        # Show warning if project not properly detected
        if self.src_warning_label:
            if self.localization_ops.is_project_detected():
                self.src_warning_label.setText("")
                self.src_warning_label.setToolTip("")
                self.src_warning_label.setStyleSheet("")
            else:
                self.src_warning_label.setText("[!] Not detected")
                self.src_warning_label.setToolTip(
                    "TextureAtlas Toolbox source directory not found. "
                    "Click 'Browse...' to select it manually."
                )
                self.src_warning_label.setStyleSheet(
                    "color: orange; font-weight: bold;"
                )

    def prompt_src_folder(self) -> None:
        """Prompt user to select the TextureAtlas Toolbox src directory.

        Opens a folder picker and validates that the selection is a valid
        source folder before updating paths.
        """
        if self.manage_task_running:
            QMessageBox.information(
                self,
                "Task Running",
                "Please wait for the current operation to finish before changing folders.",
            )
            return

        current_dir = str(self.localization_ops.paths.src_dir)
        new_dir = QFileDialog.getExistingDirectory(
            self,
            "Select TextureAtlas Toolbox 'src' Folder",
            current_dir,
        )
        if not new_dir:
            return

        try:
            self.localization_ops.set_src_dir(Path(new_dir))
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Folder", str(exc))
            return

        self._update_src_path_label()
        self._update_translations_path_label()
        if self._translations_dir_changed:
            self._translations_dir_changed(self.localization_ops.paths.translations_dir)
        self.populate_language_list(preserve_selection=False)
        self._refresh_status_table()
        if self.status_bar:
            self.status_bar.showMessage(
                f"Source directory set to {self.localization_ops.paths.src_dir}"
            )

    @staticmethod
    def _format_locale_label(code: str) -> str:
        """Format a language code as a locale label.

        Args:
            code: A language code like "en" or "pt-BR".

        Returns:
            The lowercased, underscore-separated locale string (e.g., "pt_br").
        """
        return code.lower().replace("-", "_") if code else ""

    @staticmethod
    def _format_path(path: Path) -> str:
        """Truncate a path for display if too long.

        Args:
            path: The filesystem path to format.

        Returns:
            A string representation of the path, truncated with "..." if needed.
        """
        text = str(path)
        if len(text) <= 60:
            return text
        return "..." + text[-57:]

    def _delete_languages(self, languages: List[str], delete_files: bool) -> None:
        """Remove languages from the registry and optionally delete files.

        Args:
            languages: List of language codes to remove.
            delete_files: If True, also delete .ts and .qm files.
        """
        removed: List[str] = []
        for code in languages:
            if code in LANGUAGE_REGISTRY:
                removed.append(code)
                LANGUAGE_REGISTRY.pop(code, None)
        if not removed:
            QMessageBox.information(
                self,
                "Delete Languages",
                "Selected languages were not found in the registry.",
            )
            return

        save_language_registry(LANGUAGE_REGISTRY)

        deleted_files: List[str] = []
        failed_files: List[str] = []
        translations_dir: Path = self.localization_ops.paths.translations_dir
        if delete_files:
            translations_dir.mkdir(parents=True, exist_ok=True)
            for code in removed:
                for suffix in (".ts", ".qm"):
                    candidate = translations_dir / f"app_{code}{suffix}"
                    if not candidate.exists():
                        continue
                    try:
                        candidate.unlink()
                        deleted_files.append(candidate.name)
                    except OSError as exc:
                        failed_files.append(f"{candidate.name}: {exc}")

        self.populate_language_list(preserve_selection=False)
        if self.status_bar:
            self.status_bar.showMessage(
                f"Deleted {len(removed)} language(s){' and files' if delete_files else ''}."
            )

        if self.manage_log_view:
            header = "[DELETE] Removed languages: " + ", ".join(
                code.upper() for code in removed
            )
            self.manage_log_view.appendPlainText(header + "\n")
            if deleted_files:
                self.manage_log_view.appendPlainText(
                    "    Deleted files: " + ", ".join(deleted_files) + "\n"
                )
        if failed_files:
            QMessageBox.warning(
                self,
                "File Removal Issues",
                "Some translation files could not be removed:\n"
                + "\n".join(failed_files),
            )

    def append_manage_log(self, result: OperationResult) -> None:
        """Append an operation result to the log view.

        Args:
            result: The OperationResult to display in the log.
        """
        if not self.manage_log_view:
            return
        header = f"[{result.name.upper()}] {'OK' if result.success else 'FAILED'}"
        lines = [header]
        lines.extend(result.logs)
        if result.errors:
            lines.append("Errors:")
            lines.extend(f"  - {msg}" for msg in result.errors)
        self.manage_log_view.appendPlainText("\n".join(lines) + "\n")

    def _update_status_table(self, entries: List[Dict[str, Any]]) -> None:
        """Populate the status table with translation progress entries.

        Args:
            entries: List of dictionaries containing language status details.
        """
        if not self.manage_table:
            return
        self.manage_table.setRowCount(len(entries))
        icon_provider = IconProvider.instance()
        for row, entry in enumerate(entries):
            lang_item = QTableWidgetItem(
                self._format_locale_label(entry.get("language", ""))
            )
            # Create status items with icons or text based on provider style
            ts_exists = entry.get("ts_exists", False)
            qm_exists = entry.get("qm_exists", False)

            if icon_provider.style == IconStyle.EMOJI:
                ts_text = icon_provider.get_text(
                    IconType.SUCCESS if ts_exists else IconType.ERROR
                )
                qm_text = icon_provider.get_text(
                    IconType.SUCCESS if qm_exists else IconType.ERROR
                )
                ts_item = QTableWidgetItem(ts_text)
                qm_item = QTableWidgetItem(qm_text)
            else:
                ts_item = QTableWidgetItem()
                ts_item.setIcon(
                    icon_provider.get_icon(
                        IconType.SUCCESS if ts_exists else IconType.ERROR
                    )
                )
                qm_item = QTableWidgetItem()
                qm_item.setIcon(
                    icon_provider.get_icon(
                        IconType.SUCCESS if qm_exists else IconType.ERROR
                    )
                )
            total = entry.get("total_messages", 0)
            finished = entry.get("finished_messages", 0)
            progress = f"{finished}/{total}" if total else "0/0"
            if total:
                progress += f" ({finished / total * 100:.0f}%)"
            progress_item = QTableWidgetItem(progress)
            machine_count = entry.get("machine_translated", 0)
            if machine_count and total:
                machine_pct = machine_count / total * 100
                machine_text = f"{machine_count} ({machine_pct:.0f}%)"
            elif machine_count:
                machine_text = str(machine_count)
            else:
                machine_text = "-"
            machine_item = QTableWidgetItem(machine_text)
            if machine_count:
                machine_item.setToolTip(
                    f"{machine_count} string(s) translated by machine and not yet reviewed"
                )
            needs_update = entry.get("needs_update", False)
            needs_item = QTableWidgetItem("Yes" if needs_update else "No")
            unfinished = entry.get("unfinished_messages")
            if unfinished is not None:
                needs_item.setToolTip(f"Unfinished strings: {unfinished}")
            quality_item = QTableWidgetItem(entry.get("quality", ""))
            for item in (
                lang_item,
                ts_item,
                qm_item,
                progress_item,
                machine_item,
                needs_item,
                quality_item,
            ):
                item.setTextAlignment(Qt.AlignCenter)
            self.manage_table.setItem(row, 0, lang_item)
            self.manage_table.setItem(row, 1, ts_item)
            self.manage_table.setItem(row, 2, qm_item)
            self.manage_table.setItem(row, 3, progress_item)
            self.manage_table.setItem(row, 4, machine_item)
            self.manage_table.setItem(row, 5, needs_item)
            self.manage_table.setItem(row, 6, quality_item)

    def refresh_language_list(self) -> None:
        """Rebuild the language list while preserving the current selection.

        Delegates to ``populate_language_list`` with selection preservation enabled.
        """
        self.populate_language_list(preserve_selection=True)

    def refresh_status_table(self) -> None:
        """Public method to refresh the status table.

        Call this after saving a .ts file to update the progress display.
        """
        self._refresh_status_table()

    def _refresh_status_table(self) -> None:
        """Refresh the status table with current translation progress.

        Queries the localization backend for status of all languages and
        repopulates the table rows with updated progress data.
        """
        result = self.localization_ops.status_report()
        if result.success:
            entries = result.details.get("entries", []) if result.details else []
            if isinstance(entries, list):
                self._update_status_table(entries)
        # Force immediate UI update
        if self.manage_table:
            self.manage_table.update()
            self.manage_table.repaint()
            QApplication.processEvents()

    def _check_for_unused_strings(self, languages: List[str]) -> None:
        """Check extracted .ts files for vanished strings and prompt for cleanup.

        Qt's lupdate marks strings that no longer exist in source code with
        type="vanished". This method:
        1. Recovers translations from vanished duplicates (same source, different context)
        2. Finds remaining vanished strings that have existing translations
        3. Attempts to match them with new unfinished strings (renamed/modified)
        4. Allows transferring translations from vanished to matching new strings
        5. Shows remaining unmatched vanished strings for optional removal

        Args:
            languages: List of language codes that were just extracted.
        """
        translations_dir = self.localization_ops.paths.translations_dir
        total_transferred = 0
        total_files_with_matches = 0
        total_recovered = 0

        # Process each file: recover duplicates, try matching, collect remaining
        remaining_unused_by_file: Dict[Path, List[Tuple[str, str]]] = {}

        for lang in languages:
            ts_file = translations_dir / f"app_{lang}.ts"
            if not ts_file.exists():
                continue

            # First, recover translations from vanished duplicates
            # (where the same source exists as both vanished and active unfinished)
            try:
                recovered_count, recovered_sources = recover_duplicate_translations(
                    ts_file
                )
                if recovered_count > 0:
                    total_recovered += recovered_count
                    if self.manage_log_view:
                        self.manage_log_view.appendPlainText(
                            f"[RECOVER] Auto-recovered {recovered_count} translation(s) "
                            f"from duplicate vanished strings in {ts_file.name}\n"
                        )
            except Exception as e:
                if self.manage_log_view:
                    self.manage_log_view.appendPlainText(
                        f"[WARN] Could not recover duplicates in {ts_file.name}: {e}\n"
                    )

            vanished = self._extract_vanished_strings(ts_file)
            if not vanished:
                continue

            # Get new unfinished strings for potential matching
            new_unfinished = extract_new_unfinished_strings(ts_file)

            # Find potential matches between vanished (with translations) and new strings
            matches = find_potential_matches(
                vanished, new_unfinished, min_similarity=0.6
            )

            # Collect vanished strings that weren't matched
            matched_vanished = {m.vanished_source for m in matches}
            remaining_vanished = [
                (src, trans) for src, trans in vanished if src not in matched_vanished
            ]

            # If we have potential matches, show the matching dialog
            if matches:
                dialog = StringMatchingDialog(
                    self,
                    matches,
                    remaining_vanished,
                    ts_file,
                )
                result = dialog.exec()

                if result == QDialog.Accepted and dialog.accepted_matches:
                    # Apply the accepted matches
                    transferred = apply_matches_to_file(
                        ts_file, dialog.accepted_matches
                    )
                    if transferred > 0:
                        total_transferred += transferred
                        total_files_with_matches += 1
                        if self.manage_log_view:
                            self.manage_log_view.appendPlainText(
                                f"[MATCH] Transferred {transferred} translation(s) "
                                f"in {ts_file.name}\n"
                            )

                    # Update remaining vanished (exclude those that were matched and transferred)
                    transferred_vanished = {
                        m.vanished_source for m in dialog.accepted_matches
                    }
                    remaining_vanished = [
                        (src, trans)
                        for src, trans in remaining_vanished
                        if src not in transferred_vanished
                    ]
                    # Also remove matched ones from original vanished list
                    remaining_vanished = [
                        (src, trans)
                        for src, trans in vanished
                        if src not in matched_vanished
                        and src not in transferred_vanished
                    ]

            # Collect remaining vanished strings for batch cleanup
            if remaining_vanished:
                remaining_unused_by_file[ts_file] = remaining_vanished

        # Show transfer summary if any
        if total_recovered > 0 or total_transferred > 0:
            parts = []
            if total_recovered > 0:
                parts.append(
                    f"Auto-recovered {total_recovered} duplicate translation(s)"
                )
            if total_transferred > 0:
                parts.append(
                    f"Transferred {total_transferred} from vanished "
                    f"to new strings in {total_files_with_matches} file(s)"
                )
            msg = ", ".join(parts)
            if self.status_bar:
                self.status_bar.showMessage(msg, 5000)

        # If there are remaining unmatched vanished strings, show cleanup dialog
        if not remaining_unused_by_file:
            return

        # Show batch cleanup dialog for remaining unmatched strings
        dialog = BatchUnusedStringsDialog(
            self,
            remaining_unused_by_file,
            translations_dir,
        )
        result = dialog.exec()

        if result == QDialog.Accepted:
            cleaned_count = len(dialog.files_cleaned)
            total_removed = sum(
                len(strings) for strings in remaining_unused_by_file.values()
            )
            msg = f"Removed {total_removed} vanished string(s) from {cleaned_count} file(s)"
            if dialog.save_requested and dialog.saved_path:
                msg += f" (saved to {Path(dialog.saved_path).name})"
            if self.manage_log_view:
                self.manage_log_view.appendPlainText(f"[CLEANUP] {msg}\n")
            if self.status_bar:
                self.status_bar.showMessage(msg, 5000)

    def _extract_vanished_strings(self, file_path: Path) -> List[Tuple[str, str]]:
        """Extract vanished/obsolete strings from a .ts file.

        Qt's lupdate marks strings that no longer exist in the source code
        with type="vanished" (newer Qt) or type="obsolete" (older Qt).
        Strings that exist as active entries elsewhere (moved to another context)
        are excluded since they're not truly unused.

        Args:
            file_path: Path to the .ts file.

        Returns:
            List of (source, translation) tuples for vanished/obsolete strings.
        """
        vanished: List[Tuple[str, str]] = []
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # First, collect all active (non-vanished/obsolete) source strings
            active_sources: set[str] = set()
            for message in root.iter("message"):
                translation_elem = message.find("translation")
                trans_type = (
                    translation_elem.get("type", "")
                    if translation_elem is not None
                    else ""
                )
                if trans_type not in ("vanished", "obsolete"):
                    source_elem = message.find("source")
                    if source_elem is not None and source_elem.text:
                        active_sources.add(source_elem.text)

            # Now collect vanished/obsolete strings that don't exist elsewhere
            for message in root.iter("message"):
                translation_elem = message.find("translation")
                if translation_elem is not None:
                    trans_type = translation_elem.get("type", "")
                    if trans_type in ("vanished", "obsolete"):
                        source_elem = message.find("source")
                        source = (
                            source_elem.text
                            if source_elem is not None and source_elem.text
                            else ""
                        )
                        # Skip if this string exists as an active entry (was moved)
                        if source and source not in active_sources:
                            translation = (
                                translation_elem.text if translation_elem.text else ""
                            )
                            vanished.append((source, translation))
        except Exception:
            pass
        return vanished


__all__ = ["ManageTab"]
