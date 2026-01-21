#!/usr/bin/env python3
"""Qt-based GUI and CLI for editing TextureAtlas Toolbox translation files.

Provides a user-friendly alternative to Qt Linguist for contributors who
prefer not to install developer tools. Features smart string grouping,
placeholder syntax highlighting, and real-time validation.

Machine translation (optional) requires the ``requests`` package and an API key:
    - DeepL: set ``DEEPL_API_KEY`` (and ``DEEPL_API_ENDPOINT`` for Pro).
    - Google Cloud: set ``GOOGLE_TRANSLATE_API_KEY``.
    - LibreTranslate: set ``LIBRETRANSLATE_ENDPOINT`` and optionally the key.

Usage:
    python Main.py                           # Launch GUI
    python Main.py path/to/file.ts           # Open file in GUI
    python Main.py --cli extract fr_FR de_DE # CLI mode
    python Main.py --cli status              # Show translation progress
"""

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from PySide6.QtCore import QThreadPool
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
)

from core import TranslationItem, TranslationMarker, MARKER_LABELS
from core.translation_manager import TranslationManager
from gui import apply_app_theme
from gui.editor_tab import EditorTab
from gui.icon_provider import IconProvider, IconStyle
from gui.manage_tab import ManageTab
from gui.shortcuts_dialog import ShortcutsDialog
from gui.string_matching_dialog import (
    StringMatchingDialog,
    apply_matches_to_file,
    extract_new_unfinished_strings,
    find_potential_matches,
    recover_duplicate_translations,
)
from gui.theme_options_dialog import ThemeOptionsDialog
from gui.unused_strings_dialog import UnusedStringsDialog
from gui.api_keys_dialog import ApiKeysDialog
from localization import LocalizationOperations
from utils.preferences import (
    load_preferences,
    save_preferences,
    get_shortcuts,
    get_api_keys,
)


class TranslationEditor(QMainWindow):
    """Main application window for the Translation Editor.

    Hosts two tabs: ManageTab for file/language management and EditorTab for
    editing individual translation entries. Manages file open/save, theme
    toggling, keyboard shortcuts, and user preferences.

    Attributes:
        translation_manager: Provider registry for machine translation.
        localization_ops: Backend for Qt lupdate/lrelease commands.
        thread_pool: Shared thread pool for background tasks.
        current_ts_language: Language code of the currently loaded .ts file.
        preferences: Persisted user settings dictionary.
        dark_mode: Whether dark theme is active.
        tabs: Central tab widget holding ManageTab and EditorTab.
        status_bar: Status bar for transient messages.
        editor_tab: Tab for viewing and editing translation entries.
        manage_tab: Tab for language file management.
        dark_mode_action: Menu action for toggling dark mode.
    """

    def __init__(self) -> None:
        """Initialize the main window and its child widgets."""

        super().__init__()
        self.translation_manager = TranslationManager()
        self.localization_ops = LocalizationOperations()
        self.thread_pool = QThreadPool.globalInstance()
        self.current_ts_language: Optional[str] = None
        self.preferences: Dict[str, Any] = load_preferences()
        self._apply_api_keys_to_environment()
        self.dark_mode = bool(self.preferences.get("dark_mode", False))
        self._apply_saved_translations_dir()
        self._init_icon_provider()

        self.tabs: Optional[QTabWidget] = None
        self.status_bar: Optional[QStatusBar] = None
        self.editor_tab: Optional[EditorTab] = None
        self.manage_tab: Optional[ManageTab] = None
        self.dark_mode_action: Optional[QAction] = None

        self.init_ui()
        self.apply_theme()
        if self.editor_tab:
            self.editor_tab.set_dark_mode(self.dark_mode)
            self._apply_shortcuts()

    @staticmethod
    def _find_asset(relative_path: str) -> Optional[Path]:
        """Locate an asset file by searching common project roots.

        Args:
            relative_path: Path relative to the project root (e.g., "assets/icon.ico").

        Returns:
            The resolved Path if found, or None.
        """

        script_path = Path(__file__).resolve()
        candidates = [Path.cwd()]
        candidates.extend(list(script_path.parents)[:4])
        checked = set()
        for base in candidates:
            if base is None:
                continue
            candidate = (base / relative_path).resolve()
            if candidate in checked:
                continue
            checked.add(candidate)
            if candidate.exists():
                return candidate
        return None

    def init_ui(self) -> None:
        """Build the main window layout, tabs, menu bar, and status bar."""

        self.setWindowTitle("Translation Editor - TextureAtlas Toolbox")
        self.setGeometry(100, 100, 1200, 800)

        icon_path = self._find_asset("assets/icon-ts.ico")
        icon_set = False
        if icon_path and icon_path.exists():
            try:
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    self.setWindowIcon(icon)
                    icon_set = True
            except Exception:
                pass
        if not icon_set:
            png_icon_path = self._find_asset("assets/icon-ts.png")
            if png_icon_path and png_icon_path.exists():
                try:
                    icon = QIcon(str(png_icon_path))
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                except Exception:
                    pass

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Open a .ts file to start editing")

        self.editor_tab = EditorTab(
            parent=self,
            translation_manager=self.translation_manager,
            status_bar=self.status_bar,
        )
        self.manage_tab = ManageTab(
            parent=self,
            localization_ops=self.localization_ops,
            thread_pool=self.thread_pool,
            status_bar=self.status_bar,
            on_translations_dir_changed=self._handle_translations_dir_change,
            open_ts_callback=self._open_ts_file_from_manage,
        )

        self.tabs.addTab(self.manage_tab, "Manage Files")
        self.tabs.addTab(self.editor_tab, "Editor")
        self.tabs.setCurrentWidget(self.manage_tab)

        self.create_menu_bar()

    def create_menu_bar(self) -> None:
        """Create the File, Options, and Help menus with their actions."""

        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")

        open_action = file_menu.addAction("Open .ts file...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)

        save_action = file_menu.addAction("Save")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_file)

        save_as_action = file_menu.addAction("Save As...")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_file_as)

        file_menu.addSeparator()

        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

        # Options menu
        options_menu = menubar.addMenu("Options")

        shortcuts_action = options_menu.addAction("Keyboard Shortcuts...")
        shortcuts_action.triggered.connect(self.show_shortcuts_dialog)

        options_menu.addSeparator()
        api_keys_action = options_menu.addAction("API Keys...")
        api_keys_action.triggered.connect(self.show_api_keys_dialog)
        options_menu.addSeparator()

        # Options menu - Theme sub-menu
        theme_menu = options_menu.addMenu("Theme")
        self.dark_mode_action = theme_menu.addAction("Dark Mode")
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.setChecked(self.dark_mode)
        self.dark_mode_action.toggled.connect(self.toggle_dark_mode)
        theme_menu.addSeparator()
        theme_options_action = theme_menu.addAction("Theme Options...")
        theme_options_action.triggered.connect(self.show_theme_options)

        # Advanced menu for bulk operations
        advanced_menu = menubar.addMenu("Advanced")

        # Advanced menu - "Mark All Translations As..." sub-menu
        mark_all_menu = advanced_menu.addMenu("Mark all translations as...")

        mark_all_none = mark_all_menu.addAction("None (Clear Markers)")
        mark_all_none.triggered.connect(self._mark_all_none)

        mark_all_unsure = mark_all_menu.addAction("Unsure")
        mark_all_unsure.triggered.connect(self._mark_all_unsure)

        mark_all_machine = mark_all_menu.addAction("Machine Translated")
        mark_all_machine.triggered.connect(self._mark_all_machine)

        mark_all_complete = mark_all_menu.addAction("Complete")
        mark_all_complete.triggered.connect(self._mark_all_complete)

        # Help menu
        help_menu = menubar.addMenu("Help")

        usage_action = help_menu.addAction("Using the Translator App")
        usage_action.triggered.connect(self.show_usage_help)

        api_help_action = help_menu.addAction("Translation API Keys")
        api_help_action.triggered.connect(self.show_api_key_help)

    def show_usage_help(self) -> None:
        """Show the getting-started help dialog."""

        html = (
            "<h3>Getting started</h3>"
            "<ol>"
            "<li>Use <strong>File &gt; Open</strong> to load a Qt <code>.ts</code> file.</li>"
            "<li>Select a source entry on the left to review and edit its translation.</li>"
            "<li>Keep placeholders such as <code>{value}</code> intact.</li>"
            "<li>Use the placeholder panel to preview strings with sample values.</li>"
            "<li>Click <em>Auto-Translate</em> or <em>Translate All Missing</em> after configuring a provider.</li>"
            "<li>Save regularly with <kbd>Ctrl</kbd>+<kbd>S</kbd> or <strong>File &gt; Save</strong>.</li>"
            "</ol>"
        )
        self.show_help_dialog("Translator App Help", html)

    def show_api_key_help(self) -> None:
        """Show the translation API key configuration help dialog."""

        html = (
            "<p>Machine translation is optional. Provide your own API key.</p>"
            "<h3>DeepL (paid subscription)</h3>"
            "<ul><li>Requires an active DeepL API plan.</li>"
            "<li>Set <code>DEEPL_API_KEY</code> (and <code>DEEPL_API_ENDPOINT</code> for Pro/custom).</li></ul>"
            "<h3>Google Cloud Translation (paid per usage)</h3>"
            "<ul><li>Requires a Google Cloud project with billing enabled.</li>"
            "<li>Set <code>GOOGLE_TRANSLATE_API_KEY</code>.</li></ul>"
            "<h3>LibreTranslate (self-hosted / free)</h3>"
            "<ul><li>Install Docker (<a href='https://docs.docker.com/desktop/setup/install/windows-install/'>Windows guide</a>) and run the official container (see <a href='https://github.com/LibreTranslate/LibreTranslate#docker'>instructions</a>).</li>"
            "<li>Set <code>LIBRETRANSLATE_ENDPOINT</code> if your container exposes a different URL (defaults to http://127.0.0.1:5000/translate).</li>"
            "<li>Set <code>LIBRETRANSLATE_API_KEY</code> only if your instance enforces a key.</li></ul>"
            "<p>Restart the app after changing environment variables so the providers can detect your keys.</p>"
        )
        self.show_help_dialog("Translation API Keys", html)

    def show_help_dialog(self, title: str, html: str) -> None:
        """Display a modal dialog with HTML help content.

        Args:
            title: Dialog window title.
            html: HTML body to render in a QTextBrowser.
        """

        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        layout.addWidget(browser)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.resize(520, 380)
        dialog.exec()

    def _check_unsaved_changes(self) -> bool:
        """Prompt to save unsaved changes before a destructive action.

        Returns:
            True if safe to proceed (no changes, saved, or discarded),
            False if the user cancelled.
        """
        if not self.editor_tab or not self.editor_tab.has_unsaved_changes():
            return True

        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Do you want to save before continuing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )

        if result == QMessageBox.Save:
            self.save_file()
            return not self.editor_tab.has_unsaved_changes()
        elif result == QMessageBox.Discard:
            return True
        else:
            return False

    def open_file(self) -> None:
        """Open a file dialog and load the selected .ts file."""

        if not self._check_unsaved_changes():
            return
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Translation File",
            "src/translations",
            "Qt Translation Files (*.ts);;All Files (*)",
        )
        if file_path:
            self.load_ts_file(file_path)

    def load_ts_file(self, file_path: str, check_unsaved: bool = True) -> None:
        """Parse a Qt .ts file and populate the editor with its entries.

        Groups duplicate source strings across contexts, preserves markers and
        machine-translation flags, and prompts to remove vanished strings.

        Args:
            file_path: Absolute or relative path to the .ts file.
            check_unsaved: If True, prompt before discarding unsaved changes.
        """

        if not self.editor_tab:
            return
        if check_unsaved and not self._check_unsaved_changes():
            return
        try:
            from core import TranslationMarker
            import re

            tree = ET.parse(file_path)
            root = tree.getroot()
            self.current_ts_language = self._extract_language_from_root(root)
            if not self.current_ts_language:
                self.current_ts_language = self._infer_language_from_path(file_path)
            translation_groups: dict[str, TranslationItem] = {}

            for context in root.findall("context"):
                context_name_elem = context.find("name")
                context_name = (
                    context_name_elem.text if context_name_elem is not None else ""
                )

                for message in context.findall("message"):
                    source_elem = message.find("source")
                    translation_elem = message.find("translation")
                    location_elem = message.find("location")
                    comment_elem = message.find("comment")

                    source = (
                        source_elem.text
                        if source_elem is not None and source_elem.text is not None
                        else ""
                    )
                    translation = (
                        translation_elem.text
                        if translation_elem is not None
                        and translation_elem.text is not None
                        else ""
                    )
                    trans_type = (
                        translation_elem.get("type", "")
                        if translation_elem is not None
                        else ""
                    )

                    # Extract marker from comment if present
                    marker = TranslationMarker.NONE
                    is_machine_translated = False
                    if comment_elem is not None and comment_elem.text:
                        marker_match = re.search(r"\[marker:(\w+)\]", comment_elem.text)
                        if marker_match:
                            marker = TranslationMarker.from_string(
                                marker_match.group(1)
                            )

                        if "[machine]" in comment_elem.text:
                            is_machine_translated = True
                    is_vanished = trans_type in ("vanished", "obsolete")

                    filename = ""
                    line = 0
                    if location_elem is not None:
                        filename = location_elem.get("filename", "")
                        line = int(location_elem.get("line", 0))

                    if source.strip():
                        if source in translation_groups:
                            existing_item = translation_groups[source]
                            existing_item.add_context(context_name, filename, line)
                            if (
                                translation.strip()
                                and not existing_item.translation.strip()
                            ):
                                existing_item.translation = translation
                                existing_item.is_translated = True
                            if (
                                existing_item.marker == TranslationMarker.NONE
                                and marker != TranslationMarker.NONE
                            ):
                                existing_item.marker = marker
                            existing_item.is_vanished = (
                                existing_item.is_vanished or is_vanished
                            )
                        else:
                            translation_groups[source] = TranslationItem(
                                source,
                                translation,
                                context_name,
                                filename,
                                line,
                                marker=marker,
                                is_machine_translated=is_machine_translated,
                                is_vanished=is_vanished,
                            )

            # Detect vanished (obsolete) strings marked by lupdate
            # First, try to recover translations from vanished duplicates
            # (where the same source exists as both vanished and active unfinished)
            file_path_obj = Path(file_path)
            try:
                recovered_count, recovered_sources = recover_duplicate_translations(
                    file_path_obj
                )
                if recovered_count > 0:
                    if self.status_bar:
                        self.status_bar.showMessage(
                            f"Auto-recovered {recovered_count} translation(s) "
                            "from duplicate vanished strings",
                            5000,
                        )
                    tree = ET.parse(file_path)
                    root = tree.getroot()

                    # Update translation_groups with recovered translations
                    for source in recovered_sources:
                        if source in translation_groups:
                            item = translation_groups[source]
                            for context in root.findall("context"):
                                context_name = context.find("name")
                                if context_name is not None:
                                    ctx_name = context_name.text
                                else:
                                    ctx_name = ""
                                if ctx_name == item.context:
                                    for message in context.findall("message"):
                                        source_elem = message.find("source")
                                        if (
                                            source_elem is not None
                                            and source_elem.text == source
                                        ):
                                            trans_elem = message.find("translation")
                                            if trans_elem is not None:
                                                item.translation = trans_elem.text or ""
                                                item.marker = None
                                                break
            except Exception as e:
                print(f"Warning: Could not recover duplicate translations: {e}")

            unused_strings = self._extract_vanished_strings(root)

            # If unused strings found, try matching then prompt user
            if unused_strings:
                new_unfinished = extract_new_unfinished_strings(file_path_obj)

                matches = find_potential_matches(
                    unused_strings, new_unfinished, min_similarity=0.6
                )

                matched_vanished = {m.vanished_source for m in matches}
                remaining_unused = [
                    (src, trans)
                    for src, trans in unused_strings
                    if src not in matched_vanished
                ]

                if matches:
                    match_dialog = StringMatchingDialog(
                        self,
                        matches,
                        remaining_unused,
                        file_path_obj,
                    )
                    match_result = match_dialog.exec()

                    if (
                        match_result == QDialog.Accepted
                        and match_dialog.accepted_matches
                    ):
                        transferred = apply_matches_to_file(
                            file_path_obj, match_dialog.accepted_matches
                        )
                        if transferred > 0:
                            if self.status_bar:
                                self.status_bar.showMessage(
                                    f"Transferred {transferred} translation(s) "
                                    "from vanished to new strings",
                                    5000,
                                )

                        transferred_sources = {
                            m.vanished_source for m in match_dialog.accepted_matches
                        }
                        remaining_unused = [
                            (src, trans)
                            for src, trans in unused_strings
                            if src not in matched_vanished
                            and src not in transferred_sources
                        ]

                        tree = ET.parse(file_path)
                        root = tree.getroot()

                if remaining_unused:
                    dialog = UnusedStringsDialog(
                        self,
                        remaining_unused,
                        file_path_obj.name,
                    )
                    result = dialog.exec()

                    if result == QDialog.Accepted:
                        for source, _ in remaining_unused:
                            translation_groups.pop(source, None)

                        msg = f"Removed {len(remaining_unused)} unused string(s)"
                        if dialog.save_requested and dialog.saved_path:
                            msg += f" (saved to {Path(dialog.saved_path).name})"
                        if self.status_bar:
                            self.status_bar.showMessage(msg, 5000)

            translations = list(translation_groups.values())
            self.editor_tab.load_translations(file_path, translations)

        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{exc}")

    def save_file(self) -> None:
        """Save translations to the currently open file, validating first."""

        if not self.editor_tab:
            return
        current_file = self.editor_tab.get_current_file()
        if not current_file:
            self.save_file_as()
            return
        is_valid, errors = self.editor_tab.validate_all_translations()
        if not is_valid:
            error_msg = "Found placeholder validation warnings:\n\n"
            error_msg += "\n\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n\n... and {len(errors) - 5} more warnings."
            error_msg += "\n\nSave anyway?"
            result = QMessageBox.warning(
                self,
                "Validation Warnings",
                error_msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result != QMessageBox.Yes:
                return
        self.save_ts_file(current_file)

    def save_file_as(self) -> None:
        """Open a save dialog and write translations to the chosen path."""

        if not self.editor_tab or not self.editor_tab.get_translations():
            QMessageBox.warning(self, "Warning", "No translations to save.")
            return
        is_valid, errors = self.editor_tab.validate_all_translations()
        if not is_valid:
            error_msg = "Found placeholder validation warnings:\n\n"
            error_msg += "\n\n".join(errors[:5])
            if len(errors) > 5:
                error_msg += f"\n\n... and {len(errors) - 5} more warnings."
            error_msg += "\n\nSave anyway?"
            result = QMessageBox.warning(
                self,
                "Validation Warnings",
                error_msg,
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if result != QMessageBox.Yes:
                return
        current_file = self.editor_tab.get_current_file()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Translation File",
            current_file or "src/translations/app_new.ts",
            "Qt Translation Files (*.ts);;All Files (*)",
        )
        if file_path:
            self.save_ts_file(file_path)

    def save_ts_file(self, file_path: str) -> None:
        """Serialize translations to a Qt .ts file.

        Writes all translation entries grouped by context, preserving markers,
        machine flags, and vanished status. Refreshes the ManageTab status
        table after a successful save.

        Args:
            file_path: Destination path for the .ts file.
        """

        if not self.editor_tab:
            return
        try:
            from core import TranslationMarker

            translations = self.editor_tab.get_translations()
            root = ET.Element("TS")
            root.set("version", "2.1")
            language = (
                self._infer_language_from_path(file_path) or self.current_ts_language
            )
            if language:
                root.set("language", language)
                self.current_ts_language = language

            contexts: dict[str, List[tuple[TranslationItem, int]]] = {}
            for item in translations:
                for i, context_name in enumerate(item.contexts):
                    contexts.setdefault(context_name, [])
                    contexts[context_name].append((item, i))

            for context_name, entries in contexts.items():
                context_elem = ET.SubElement(root, "context")
                name_elem = ET.SubElement(context_elem, "name")
                name_elem.text = context_name

                for item, index in entries:
                    message_elem = ET.SubElement(context_elem, "message")
                    filename = ""
                    line = 0
                    if index < len(item.locations):
                        filename, line = item.locations[index]
                    if filename:
                        location_elem = ET.SubElement(message_elem, "location")
                        location_elem.set("filename", filename)
                        if line:
                            location_elem.set("line", str(line))

                    source_elem = ET.SubElement(message_elem, "source")
                    source_elem.text = item.source

                    # Save translation marker and machine flag as comment with prefixes
                    comment_parts = []
                    if item.marker and item.marker != TranslationMarker.NONE:
                        comment_parts.append(f"[marker:{item.marker.value}]")
                    if item.is_machine_translated:
                        comment_parts.append("[machine]")
                    if comment_parts:
                        comment_elem = ET.SubElement(message_elem, "comment")
                        comment_elem.text = " ".join(comment_parts)

                    translation_elem = ET.SubElement(message_elem, "translation")
                    if item.is_vanished:
                        translation_elem.set("type", "vanished")
                        if item.translation:
                            translation_elem.text = item.translation
                    elif item.translation:
                        translation_elem.text = item.translation
                    else:
                        translation_elem.set("type", "unfinished")

            tree = ET.ElementTree(root)
            ET.indent(tree, space="    ")
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

            self.editor_tab.mark_saved(file_path)
            if self.manage_tab:
                self.manage_tab.refresh_status_table()

        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save file:\n{exc}")

    def _extract_language_from_root(self, root: ET.Element) -> Optional[str]:
        """Return the language code from the TS element's attributes.

        Args:
            root: Root ``<TS>`` element of the parsed XML.

        Returns:
            Value of the ``language`` or ``sourcelanguage`` attribute, or None.
        """

        return root.get("language") or root.get("sourcelanguage")

    def _extract_vanished_strings(self, root: ET.Element) -> List[Tuple[str, str]]:
        """Collect vanished or obsolete strings from a parsed .ts file.

        Qt's lupdate marks removed strings with ``type="vanished"`` (Qt 5+) or
        ``type="obsolete"`` (older Qt). Strings that still exist as active
        entries elsewhere (moved to another context) are excluded.

        Args:
            root: Root ``<TS>`` element of the parsed XML.

        Returns:
            List of (source, translation) tuples for truly unused strings.
        """

        active_sources: set[str] = set()
        for message in root.iter("message"):
            translation_elem = message.find("translation")
            trans_type = (
                translation_elem.get("type", "") if translation_elem is not None else ""
            )
            if trans_type not in ("vanished", "obsolete"):
                source_elem = message.find("source")
                if source_elem is not None and source_elem.text:
                    active_sources.add(source_elem.text)

        vanished: List[Tuple[str, str]] = []
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
                    if source and source not in active_sources:
                        translation = (
                            translation_elem.text if translation_elem.text else ""
                        )
                        vanished.append((source, translation))
        return vanished

    def _infer_language_from_path(self, file_path: str) -> Optional[str]:
        """Infer the language code from a filename like ``app_es.ts``.

        Args:
            file_path: Path to a .ts file.

        Returns:
            Extracted language code (e.g., ``es``), or None if unrecognized.
        """

        filename = Path(file_path).name
        match = re.search(r"app_([A-Za-z0-9_\-]+)\.ts$", filename, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        """Prompt to save unsaved changes before the window closes.

        Args:
            event: The Qt close event to accept or ignore.
        """
        if self.editor_tab and self.editor_tab.has_unsaved_changes():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self.save_file()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

    def toggle_dark_mode(self, checked: bool) -> None:
        """Enable or disable dark mode and refresh the theme.

        Args:
            checked: Whether dark mode should be enabled.
        """

        self.dark_mode = checked
        if self.dark_mode_action and self.dark_mode_action.isChecked() != checked:
            self.dark_mode_action.blockSignals(True)
            self.dark_mode_action.setChecked(checked)
            self.dark_mode_action.blockSignals(False)
        self.apply_theme()
        if self.editor_tab:
            self.editor_tab.set_dark_mode(self.dark_mode)

    def apply_theme(self) -> None:
        """Apply the current light or dark theme stylesheet."""
        apply_app_theme(self, dark_mode=self.dark_mode)

    def _open_ts_file_from_manage(self, ts_path: Path) -> None:
        """Load a .ts file from ManageTab and switch to the Editor tab."""

        if not ts_path.exists():
            QMessageBox.warning(
                self, "File Missing", f"Translation file not found:\n{ts_path}"
            )
            return
        if not self._check_unsaved_changes():
            return
        self.load_ts_file(str(ts_path), check_unsaved=False)
        if self.tabs and self.editor_tab:
            editor_index = self.tabs.indexOf(self.editor_tab)
            if editor_index != -1:
                self.tabs.setCurrentIndex(editor_index)

    def _handle_translations_dir_change(self, path: Path) -> None:
        """Save the new translations directory path to preferences."""

        self.preferences["translations_folder"] = str(path)
        self._persist_preferences()

    def _apply_saved_translations_dir(self) -> None:
        """Restore the translations directory from persisted preferences."""

        saved_path = self.preferences.get("translations_folder")
        if not saved_path:
            return
        try:
            self.localization_ops.set_translations_dir(Path(saved_path))
        except ValueError:
            self.preferences.pop("translations_folder", None)
            self._persist_preferences()

    def _apply_api_keys_to_environment(self) -> None:
        """Set translation API keys from preferences as environment variables.

        This allows the translation providers to pick up configured keys
        without requiring the user to set system environment variables.
        Only sets variables for non-empty values.
        """

        api_keys = get_api_keys(self.preferences)
        env_var_map = {
            "deepl_api_key": "DEEPL_API_KEY",
            "deepl_api_endpoint": "DEEPL_API_ENDPOINT",
            "google_translate_api_key": "GOOGLE_TRANSLATE_API_KEY",
            "libretranslate_endpoint": "LIBRETRANSLATE_ENDPOINT",
            "libretranslate_api_key": "LIBRETRANSLATE_API_KEY",
        }

        for pref_key, env_var in env_var_map.items():
            value = api_keys.get(pref_key, "")
            if value:
                os.environ[env_var] = value

    def _persist_preferences(self) -> None:
        """Write current preferences (theme, paths, shortcuts) to disk."""

        prefs = dict(self.preferences)
        prefs["dark_mode"] = self.dark_mode
        prefs["translations_folder"] = str(self.localization_ops.paths.translations_dir)
        icon_provider = IconProvider.instance()
        prefs["icon_style"] = icon_provider.style.value
        if icon_provider.custom_assets_path:
            prefs["custom_icons_path"] = str(icon_provider.custom_assets_path)
        save_preferences(prefs)
        self.preferences = prefs

    def _init_icon_provider(self) -> None:
        """Initialize the global IconProvider from saved preferences."""

        style_str = self.preferences.get("icon_style", "simplified")
        try:
            style = IconStyle(style_str)
        except ValueError:
            style = IconStyle.SIMPLIFIED

        custom_path_str = self.preferences.get("custom_icons_path", "")
        custom_path = Path(custom_path_str) if custom_path_str else None

        provider = IconProvider(style=style, custom_assets_path=custom_path)
        IconProvider.set_instance(provider)

    def show_api_keys_dialog(self) -> None:
        """Open the API keys configuration dialog.

        Allows users to enter API keys for translation providers. Keys are
        saved to preferences and applied as environment variables for the
        current session only.
        """

        current_keys = get_api_keys(self.preferences)
        dialog = ApiKeysDialog(self, api_keys=current_keys)

        if dialog.exec() == ApiKeysDialog.DialogCode.Accepted:
            new_keys = dialog.get_api_keys()
            self.preferences["api_keys"] = new_keys
            self._persist_preferences()
            self._apply_api_keys_to_environment()

            self.translation_manager = TranslationManager()
            if self.editor_tab:
                self.editor_tab.translation_manager = self.translation_manager

            if self.status_bar:
                self.status_bar.showMessage("API keys saved and applied", 3000)

    def show_theme_options(self) -> None:
        """Open the theme and icon style configuration dialog."""

        icon_provider = IconProvider.instance()
        custom_path = (
            str(icon_provider.custom_assets_path)
            if icon_provider.custom_assets_path
            else ""
        )
        dialog = ThemeOptionsDialog(
            self,
            dark_mode=self.dark_mode,
            icon_style=icon_provider.style.value,
            custom_icons_path=custom_path,
        )
        dialog.settings_changed.connect(self._apply_theme_settings)
        dialog.exec()

    def _apply_theme_settings(self, settings: Dict[str, Any]) -> None:
        """Apply theme settings emitted by the options dialog.

        Args:
            settings: Keys ``dark_mode``, ``icon_style``, ``custom_icons_path``.
        """

        new_dark_mode = settings.get("dark_mode", self.dark_mode)
        if new_dark_mode != self.dark_mode:
            self.toggle_dark_mode(new_dark_mode)

        icon_style_str = settings.get("icon_style", "simplified")
        custom_path_str = settings.get("custom_icons_path", "")

        try:
            icon_style = IconStyle(icon_style_str)
        except ValueError:
            icon_style = IconStyle.SIMPLIFIED

        custom_path = Path(custom_path_str) if custom_path_str else None

        provider = IconProvider.instance()
        provider.style = icon_style
        provider.custom_assets_path = custom_path

        self._persist_preferences()
        self._refresh_ui_icons()

        if self.status_bar:
            self.status_bar.showMessage("Theme settings updated", 3000)

    def _refresh_ui_icons(self) -> None:
        """Refresh icons in both tabs after an icon style change."""

        if self.manage_tab:
            self.manage_tab.populate_language_list(preserve_selection=True)
            self.manage_tab.refresh_status_table()

        if self.editor_tab:
            self.editor_tab.update_translation_list()

    def _mark_all_none(self) -> None:
        """Mark all translations as None (clear markers)."""
        self._mark_all_with_confirmation(TranslationMarker.NONE)

    def _mark_all_unsure(self) -> None:
        """Mark all translations as unsure."""
        self._mark_all_with_confirmation(TranslationMarker.UNSURE)

    def _mark_all_machine(self) -> None:
        """Mark all translations as machine translated."""
        self._mark_all_with_confirmation(TranslationMarker.MACHINE_TRANSLATED)

    def _mark_all_complete(self) -> None:
        """Mark all translations as complete."""
        self._mark_all_with_confirmation(TranslationMarker.COMPLETE)

    def _mark_all_with_confirmation(self, marker: TranslationMarker) -> None:
        """Mark all translations with confirmation dialog.

        Args:
            marker: The TranslationMarker to apply to all items.
        """

        if not self.editor_tab or not self.editor_tab.translations:
            QMessageBox.information(
                self,
                "Mark All Translations",
                "Please load a translation file first.",
            )
            return

        count = len(self.editor_tab.translations)
        marker_label = MARKER_LABELS.get(marker, "None")

        if marker == TranslationMarker.NONE:
            action_text = "clear all markers from"
        else:
            action_text = f"mark as '{marker_label}'"

        reply = QMessageBox.question(
            self,
            "Mark All Translations",
            f"This will {action_text} {count} translation(s).\n\n"
            "Are you sure you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.editor_tab.set_all_markers(marker)

    def _apply_shortcuts(self) -> None:
        """Apply saved keyboard shortcuts to the editor tab."""

        if not self.editor_tab:
            return
        shortcuts = get_shortcuts(self.preferences)
        self.editor_tab.setup_shortcuts(shortcuts)

    def show_shortcuts_dialog(self) -> None:
        """Open the keyboard shortcuts configuration dialog."""

        current_shortcuts = get_shortcuts(self.preferences)
        dialog = ShortcutsDialog(self, current_shortcuts)
        if dialog.exec() == QDialog.Accepted:
            new_shortcuts = dialog.get_shortcuts()
            self.preferences["shortcuts"] = new_shortcuts
            self._persist_preferences()
            self._apply_shortcuts()
            if self.status_bar:
                self.status_bar.showMessage("Keyboard shortcuts updated", 3000)


def main() -> None:
    """Launch the Translation Editor in GUI or CLI mode.

    Pass ``--cli`` as the first argument to invoke the command-line interface;
    otherwise the PySide6 GUI is started. An optional .ts file path opens
    that file directly in the editor.

    Raises:
        SystemExit: Always exits via sys.exit() with the app's return code.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from cli import main as cli_main

        sys.exit(cli_main(sys.argv[2:]))

    app = QApplication(sys.argv)
    app.setApplicationName("Translation Editor")
    app.setApplicationDisplayName("Translation Editor - TextureAtlas Toolbox")
    app.setApplicationVersion("1.1.0")
    app.setOrganizationName("AutisticLulu")

    window = TranslationEditor()
    window.show()

    if window.manage_tab:
        window.manage_tab.check_incomplete_locale_codes()

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path) and file_path.endswith(".ts"):
            window.load_ts_file(file_path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
