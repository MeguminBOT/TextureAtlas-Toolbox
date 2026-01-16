"""Editor tab widget for viewing and translating strings.

Provides the main translation editing interface: a list of source strings,
a translation text area with placeholder highlighting, machine translation
controls, and a live preview panel.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QModelIndex
from PySide6.QtGui import QFont, QKeySequence, QShortcut, QStandardItemModel, QStandardItem
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core import TranslationError, TranslationItem, TranslationMarker, MARKER_LABELS
from core.translation_manager import TranslationManager
from .icon_provider import IconProvider, IconStyle, IconType
from .placeholder_highlighter import PlaceholderHighlighter
from .translation_filter_model import TranslationFilterProxyModel, TranslationRoles


class EditorTab(QWidget):
    """Widget tab for editing translation entries.

    Displays a filterable list of source strings, allows editing translations,
    validates placeholder consistency, and integrates with machine translation
    providers for automatic translation.

    Attributes:
        translations: List of TranslationItem entries currently loaded.
        current_item: The TranslationItem selected for editing.
        current_file: Path to the currently open .ts file.
        is_modified: True if unsaved changes exist.
        dark_mode: Whether dark-mode styling is active.
    """

    def __init__(
        self,
        *,
        parent: QWidget,
        translation_manager: TranslationManager,
        status_bar: Optional[QStatusBar] = None,
    ) -> None:
        """Initialize the editor tab.

        Args:
            parent: Parent widget (typically the main window).
            translation_manager: Manager for translation providers.
            status_bar: Optional status bar to display messages.
        """
        super().__init__(parent)
        self.window = parent
        self.translation_manager = translation_manager
        self.status_bar = status_bar

        self.translations: List[TranslationItem] = []
        self.current_item: Optional[TranslationItem] = None
        self.current_file: Optional[str] = None
        self.is_modified = False
        self.dark_mode = False
        self.selected_provider_key: Optional[str] = None
        self.auto_translate_all_btn: Optional[QPushButton] = None

        self.source_highlighter: Optional[PlaceholderHighlighter] = None
        self.translation_highlighter: Optional[PlaceholderHighlighter] = None
        self._shortcuts: Dict[str, QShortcut] = {}

        self._list_model = QStandardItemModel(self)
        self._filter_proxy = TranslationFilterProxyModel(self)
        self._filter_proxy.setSourceModel(self._list_model)

        self._build_ui()
        self._setup_connections()
        self.populate_language_combos()
        self.populate_provider_combo()

    def load_translations(
        self, file_path: str, translations: List[TranslationItem]
    ) -> None:
        """Load translations from a .ts file into the editor.

        Args:
            file_path: Path to the .ts file.
            translations: Parsed TranslationItem entries.
        """
        # Clear current item before updating to avoid accessing deleted objects
        self.current_item = None
        self.translations = translations
        self.current_file = file_path
        self.is_modified = False
        self.update_translation_list()
        self.update_stats()

        total_entries = sum(len(item.contexts) for item in self.translations)
        filename = Path(file_path).name
        if self.status_bar:
            self.status_bar.showMessage(
                f"Loaded {len(self.translations)} unique translations "
                f"({total_entries} total entries) from {filename}"
            )
        if hasattr(self.window, "setWindowTitle"):
            self.window.setWindowTitle(f"Translation Editor - {filename}")

        if self.provider_combo:
            self.update_provider_status(self.provider_combo.currentData())

    def mark_saved(self, file_path: str) -> None:
        """Update state after a successful file save.

        Args:
            file_path: Path where the file was saved.
        """
        self.current_file = file_path
        self.is_modified = False
        total_entries = sum(len(item.contexts) for item in self.translations)
        filename = Path(file_path).name
        if self.status_bar:
            self.status_bar.showMessage(
                f"Saved {len(self.translations)} unique translations "
                f"({total_entries} total entries) to {filename}"
            )
        if hasattr(self.window, "setWindowTitle"):
            self.window.setWindowTitle(f"Translation Editor - {filename}")

    def validate_all_translations(self) -> tuple[bool, List[str]]:
        """Check all translations for placeholder mismatches.

        Returns:
            A tuple (all_valid, error_messages) where all_valid is True if
            every entry passes validation.
        """
        errors: List[str] = []
        for i, item in enumerate(self.translations):
            if item.translation.strip():
                is_valid, error_msg = item.validate_translation()
                if not is_valid:
                    preview = item.source[:50]
                    if len(item.source) > 50:
                        preview += "..."
                    errors.append(f"Line {i + 1}: {preview}\n  → {error_msg}")
        return len(errors) == 0, errors

    def has_unsaved_changes(self) -> bool:
        """Check for unsaved modifications.

        Returns:
            True if there are unsaved changes in the current session.
        """
        return self.is_modified

    def get_current_file(self) -> Optional[str]:
        """Retrieve the path to the currently loaded .ts file.

        Returns:
            The file path as a string, or None if no file is loaded.
        """
        return self.current_file

    def get_translations(self) -> List[TranslationItem]:
        """Retrieve the list of translation entries currently loaded.

        Returns:
            A list of TranslationItem objects for the current session.
        """
        return self.translations

    def clear_translations(self) -> None:
        """Reset the editor to an empty state."""
        self.translations.clear()
        self._list_model.clear()
        self.current_item = None
        self.current_file = None
        self.is_modified = False
        self.clear_editor()
        self.update_stats()
        if hasattr(self.window, "setWindowTitle"):
            self.window.setWindowTitle("Translation Editor")
        if self.status_bar:
            self.status_bar.showMessage("Ready - Open a .ts file to start editing")

    def set_dark_mode(self, enabled: bool) -> None:
        """Toggle dark-mode styling for this tab.

        Args:
            enabled: True to enable dark mode, False for light mode.
        """
        self.dark_mode = enabled
        if self.source_highlighter:
            self.source_highlighter.set_dark_mode(enabled)
        if self.translation_highlighter:
            self.translation_highlighter.set_dark_mode(enabled)
        if self.placeholder_group.isVisible():
            self.setup_placeholders()
        self._apply_preview_theme()

    def _build_ui(self) -> None:
        """Construct the main layout with left and right panels."""

        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        self._create_left_panel(splitter)
        self._create_right_panel(splitter)
        splitter.setSizes([360, 840])

    def _create_left_panel(self, parent: QSplitter) -> None:
        """Build the left panel with filter input, translation list, and stats.

        Args:
            parent: Splitter widget to add the panel to.
        """

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        filter_layout = QHBoxLayout()
        filter_label = QLabel("Filter:")
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Search or use is:missing, has:ph...")
        self.filter_input.setToolTip(
            "Filter syntax:\n"
            "• is:translated / is:done - Translated items\n"
            "• is:missing / is:untranslated - Untranslated items\n"
            "• is:mt / is:machine - Machine translated\n"
            "• is:unsure - Marked as unsure\n"
            "• is:vanished - Obsolete/vanished items\n"
            "• has:placeholder / has:ph - Items with placeholders\n"
            "• ctx:<name> - Items in specific context\n"
            "• Plain text searches in source and translation"
        )
        filter_layout.addWidget(filter_label)
        filter_layout.addWidget(self.filter_input)
        left_layout.addLayout(filter_layout)

        self.translation_list = QListView()
        self.translation_list.setAlternatingRowColors(True)
        self.translation_list.setModel(self._filter_proxy)
        self.translation_list.setSelectionMode(QListView.SingleSelection)
        left_layout.addWidget(self.translation_list)

        self.stats_label = QLabel("No file loaded")
        self.stats_label.setStyleSheet("font-weight: bold; padding: 5px;")
        left_layout.addWidget(self.stats_label)

        parent.addWidget(left_widget)

    def _create_right_panel(self, parent: QSplitter) -> None:
        """Build the right panel with source, translation, preview, and context.

        Args:
            parent: Splitter widget to add the panel to.
        """

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        source_group = QGroupBox("Source Text")
        source_layout = QVBoxLayout(source_group)
        self.source_text = QTextEdit()
        self.source_text.setReadOnly(True)
        self.source_text.setMaximumHeight(100)
        self.source_text.setFont(QFont("Consolas", 10))
        self.source_highlighter = PlaceholderHighlighter(
            self.source_text.document(), self.dark_mode
        )
        source_layout.addWidget(self.source_text)
        right_layout.addWidget(source_group)

        translation_group = QGroupBox("Translation")
        translation_layout = QVBoxLayout(translation_group)
        controls = QGridLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setHorizontalSpacing(12)
        controls.setVerticalSpacing(6)

        self.copy_source_btn = QPushButton("Copy Source")
        self.copy_source_btn.setToolTip("Copy source text to translation field")
        self.copy_source_btn.setEnabled(False)
        controls.addWidget(self.copy_source_btn, 0, 0, 1, 2)

        provider_label = QLabel("Service:")
        controls.addWidget(provider_label, 0, 2, alignment=Qt.AlignRight)

        self.provider_combo = QComboBox()
        self.provider_combo.setToolTip("Select a machine translation provider")
        controls.addWidget(self.provider_combo, 0, 3)

        self.translate_btn = QPushButton("Auto-Translate")
        self.translate_btn.setEnabled(False)
        controls.addWidget(self.translate_btn, 0, 4)

        self.auto_translate_all_btn = QPushButton("Translate All Missing")
        self.auto_translate_all_btn.setEnabled(False)
        self.auto_translate_all_btn.setToolTip(
            "Machine translate every unfinished entry in the current file."
        )
        self.auto_translate_all_btn.clicked.connect(self.auto_translate_all_entries)
        controls.addWidget(self.auto_translate_all_btn, 0, 5, alignment=Qt.AlignRight)

        from_label = QLabel("From:")
        controls.addWidget(from_label, 1, 0, alignment=Qt.AlignRight)
        self.source_lang_combo = QComboBox()
        controls.addWidget(self.source_lang_combo, 1, 1)

        to_label = QLabel("To:")
        controls.addWidget(to_label, 1, 2, alignment=Qt.AlignRight)
        self.target_lang_combo = QComboBox()
        controls.addWidget(self.target_lang_combo, 1, 3)

        marker_label = QLabel("Mark as:")
        controls.addWidget(marker_label, 1, 4, alignment=Qt.AlignRight)
        self.marker_combo = QComboBox()
        self.marker_combo.setToolTip(
            "Mark this translation with a quality indicator:\n"
            "• None: No marker\n"
            "• Unsure: You're not confident about this translation\n"
            "• Needs Review: Should be reviewed by others\n"
            "• Could Be Improved: Works but could be better"
        )
        for marker in TranslationMarker:
            self.marker_combo.addItem(MARKER_LABELS[marker], marker)
        self.marker_combo.setEnabled(False)
        self.marker_combo.currentIndexChanged.connect(self._on_marker_changed)
        controls.addWidget(self.marker_combo, 1, 5)

        controls.setColumnStretch(1, 1)
        controls.setColumnStretch(3, 1)
        translation_layout.addLayout(controls)

        self.provider_status_label = QLabel(
            "Machine translation disabled. Configure an API key to enable providers."
        )
        self.provider_status_label.setWordWrap(True)
        self.provider_status_label.setStyleSheet(
            "font-size: 11px; padding: 2px 0; color: #666666;"
        )
        translation_layout.addWidget(self.provider_status_label)

        self.translation_text = QTextEdit()
        self.translation_text.setMaximumHeight(100)
        self.translation_text.setFont(QFont("Consolas", 10))
        self.translation_highlighter = PlaceholderHighlighter(
            self.translation_text.document(), self.dark_mode
        )
        translation_layout.addWidget(self.translation_text)
        right_layout.addWidget(translation_group)

        self.placeholder_group = QGroupBox("Placeholder Values (for preview)")
        placeholder_layout = QVBoxLayout(self.placeholder_group)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.placeholder_widget = QWidget()
        self.placeholder_layout = QVBoxLayout(self.placeholder_widget)
        scroll_area.setWidget(self.placeholder_widget)
        placeholder_layout.addWidget(scroll_area)
        self.placeholder_group.setVisible(False)
        right_layout.addWidget(self.placeholder_group)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        self.preview_text.setFont(QFont("Consolas", 10))
        preview_layout.addWidget(self.preview_text)
        right_layout.addWidget(preview_group)

        context_group = QGroupBox("Context Information")
        context_layout = QVBoxLayout(context_group)
        self.context_label = QTextBrowser()
        self.context_label.setOpenExternalLinks(False)
        self.context_label.setMaximumHeight(120)
        self.context_label.setStyleSheet("padding: 5px;")
        context_layout.addWidget(self.context_label)
        right_layout.addWidget(context_group)

        parent.addWidget(right_widget)
        self._apply_preview_theme()

    def _setup_connections(self) -> None:
        """Wire up signals and slots for user interaction."""

        selection_model = self.translation_list.selectionModel()
        if selection_model:
            selection_model.currentChanged.connect(self._on_selection_changed)
        self.translation_text.textChanged.connect(self.on_translation_changed)
        self.filter_input.textChanged.connect(self._on_filter_text_changed)
        self.copy_source_btn.clicked.connect(self.copy_source_to_translation)
        self.translate_btn.clicked.connect(self.handle_auto_translate)
        self.provider_combo.currentIndexChanged.connect(self.on_provider_changed)

    def _on_filter_text_changed(self, text: str) -> None:
        """Handle filter text changes by updating the proxy model.

        Args:
            text: The new filter string.
        """

        self._filter_proxy.set_filter_text(text)

    def _on_selection_changed(self, current: QModelIndex, previous: QModelIndex) -> None:
        """Handle selection changes in the translation list view.

        Args:
            current: The newly selected model index.
            previous: The previously selected model index (unused).
        """

        if not current.isValid():
            self.current_item = None
            self.clear_editor()
            return

        item = current.data(TranslationRoles.ItemRole)
        if not isinstance(item, TranslationItem):
            self.current_item = None
            self.clear_editor()
            return

        self.current_item = item
        self.load_translation_in_editor()

    def update_translation_list(self) -> None:
        """Rebuild the translation list model from scratch."""

        self._list_model.clear()
        icon_provider = IconProvider.instance()

        for item in self.translations:
            list_item = self._create_model_item(item, icon_provider)
            self._list_model.appendRow(list_item)

    def _create_model_item(
        self, item: TranslationItem, icon_provider: IconProvider
    ) -> QStandardItem:
        """Create a QStandardItem for a TranslationItem.

        Args:
            item: The TranslationItem data.
            icon_provider: The icon provider instance.

        Returns:
            A configured QStandardItem for the model.
        """
        list_item = QStandardItem()
        self._update_model_item_display(list_item, item, icon_provider)
        list_item.setData(item, TranslationRoles.ItemRole)
        list_item.setData(item.source.lower(), TranslationRoles.SourceRole)
        list_item.setData(item.translation.lower(), TranslationRoles.TranslationRole)
        list_item.setData(item.has_placeholders(), TranslationRoles.HasPlaceholdersRole)
        list_item.setData(item.is_machine_translated, TranslationRoles.IsMachineTranslatedRole)
        list_item.setData(item.is_translated, TranslationRoles.IsTranslatedRole)
        list_item.setData(item.marker, TranslationRoles.MarkerRole)
        list_item.setData(getattr(item, "is_vanished", False), TranslationRoles.IsVanishedRole)
        list_item.setData([ctx.lower() for ctx in item.contexts], TranslationRoles.ContextsRole)

        return list_item

    def _update_model_item_display(
        self,
        list_item: QStandardItem,
        item: TranslationItem,
        icon_provider: IconProvider,
    ) -> None:
        """Update the display text and icon for a model item.

        Args:
            list_item: The QStandardItem to configure.
            item: The TranslationItem data.
            icon_provider: The icon provider instance.
        """
        # Icon priority: not translated > unsure > machine translated > success
        if not item.is_translated:
            icon_type = IconType.ERROR
        elif item.marker == TranslationMarker.UNSURE:
            icon_type = IconType.MARKER_UNSURE
        elif item.is_machine_translated:
            icon_type = IconType.MACHINE_TRANSLATED
        else:
            icon_type = IconType.SUCCESS

        if icon_provider.style == IconStyle.EMOJI:
            status_text = icon_provider.get_text(icon_type)
            group_text = (
                f" {icon_provider.get_text(IconType.GROUP)}{len(item.contexts)}"
                if len(item.contexts) > 1
                else ""
            )
            display_text = (
                f"{status_text}{group_text} {item.source[:70]}"
                f"{'...' if len(item.source) > 70 else ''}"
            )
            list_item.setText(display_text)
        else:
            list_item.setIcon(icon_provider.get_icon(icon_type))
            group_indicator = (
                f" [{len(item.contexts)}]" if len(item.contexts) > 1 else ""
            )
            display_text = (
                f"{group_indicator} {item.source[:70]}"
                f"{'...' if len(item.source) > 70 else ''}"
            ).strip()
            list_item.setText(display_text)

    def update_stats(self) -> None:
        """Refresh the progress label with current translation counts."""

        total = len(self.translations)
        translated = sum(1 for item in self.translations if item.is_translated)
        percentage = (translated / total * 100) if total else 0
        self.stats_label.setText(f"Progress: {translated}/{total} ({percentage:.1f}%)")

    def clear_editor(self) -> None:
        """Reset editor fields to their default empty state."""

        self.source_text.clear()
        self.translation_text.clear()
        self.preview_text.clear()
        self.context_label.setPlainText("No translation selected")
        self.placeholder_group.setVisible(False)
        self.copy_source_btn.setEnabled(False)
        self.marker_combo.setEnabled(False)
        self.marker_combo.blockSignals(True)
        self.marker_combo.setCurrentIndex(0)
        self.marker_combo.blockSignals(False)

    def load_translation_in_editor(self) -> None:
        """Populate editor fields with the currently selected item."""

        if not self.current_item:
            return
        self.copy_source_btn.setEnabled(True)
        self.marker_combo.setEnabled(True)
        self.source_text.setPlainText(self.current_item.source)
        self.translation_text.blockSignals(True)
        self.translation_text.setPlainText(self.current_item.translation)
        self.translation_text.blockSignals(False)
        self.marker_combo.blockSignals(True)
        for i in range(self.marker_combo.count()):
            if self.marker_combo.itemData(i) == self.current_item.marker:
                self.marker_combo.setCurrentIndex(i)
                break
        self.marker_combo.blockSignals(False)
        if len(self.current_item.contexts) == 1:
            context_info = f"Context: {self.current_item.contexts[0]}\n"
            context_info += (
                f"File: {self.current_item.filename}:{self.current_item.line}"
            )
        else:
            context_info = f"Used in {len(self.current_item.contexts)} contexts:\n\n"
            context_info += self.current_item.get_all_contexts_info()
        self.context_label.setPlainText(context_info)
        self.setup_placeholders()
        self.update_preview()

    def setup_placeholders(self) -> None:
        """Create input fields for placeholders found in the current item."""

        if not self.current_item or not self.current_item.has_placeholders():
            self.placeholder_group.setVisible(False)
            return
        for i in reversed(range(self.placeholder_layout.count())):
            child = self.placeholder_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        placeholders = self.current_item.get_placeholders()
        for placeholder in placeholders:
            placeholder_key = placeholder.strip("{}")
            label = QLabel(f"{placeholder}:")
            input_field = QLineEdit()
            input_field.setPlaceholderText(f"Example value for {placeholder}")
            input_field.textChanged.connect(self.update_preview)
            if self.dark_mode:
                input_field.setStyleSheet(
                    "QLineEdit { color: #FFA500; background-color: #3a3a3a; }"
                )
            else:
                input_field.setStyleSheet(
                    "QLineEdit { color: #FF6600; background-color: #ffffff; }"
                )
            lower_key = placeholder_key.lower()
            if "name" in lower_key:
                input_field.setText("John Doe")
            elif "count" in lower_key or "number" in lower_key:
                input_field.setText("42")
            elif "file" in lower_key:
                input_field.setText("example.txt")
            elif "percent" in lower_key:
                input_field.setText("75%")
            elif "cpu" in lower_key:
                input_field.setText("AMD Ryzen 9 3900X 12-Core Processor")
            elif "memory" in lower_key or "ram" in lower_key:
                input_field.setText("16384")
            elif "threads" in lower_key:
                input_field.setText("24")
            else:
                input_field.setText(f"[{placeholder_key}]")
            self.placeholder_layout.addWidget(label)
            self.placeholder_layout.addWidget(input_field)
        self.placeholder_group.setVisible(True)

    def _apply_preview_theme(self) -> None:
        """Apply dark or light theme styling to the preview area."""

        if not hasattr(self, "preview_text") or self.preview_text is None:
            return
        if self.dark_mode:
            self.preview_text.setStyleSheet(
                "QTextEdit { background-color: #2f2f2f; color: #ffffff; border: 1px solid #555555; }"
            )
        else:
            self.preview_text.setStyleSheet(
                "QTextEdit { background-color: #f0f0f0; color: #000000; border: 1px solid #cccccc; }"
            )

    def get_placeholder_values(self) -> Dict[str, str]:
        """Collect sample values for placeholders from the input fields.

        Returns:
            A dictionary mapping placeholder keys to their sample values.
        """
        values: Dict[str, str] = {}
        for i in range(0, self.placeholder_layout.count(), 2):
            label_item = self.placeholder_layout.itemAt(i)
            input_item = self.placeholder_layout.itemAt(i + 1)
            if not label_item or not input_item:
                continue
            label_widget = label_item.widget()
            input_widget = input_item.widget()
            if isinstance(label_widget, QLabel) and isinstance(input_widget, QLineEdit):
                label_text = label_widget.text().rstrip(":")
                placeholder_key = label_text.strip("{}")
                values[label_text] = input_widget.text()
                values[placeholder_key] = input_widget.text()
        return values

    def populate_language_combos(self, provider_key: Optional[str] = None) -> None:
        """Fill source and target language combo boxes for the selected provider.

        Args:
            provider_key: Provider identifier, or None to use the current selection.
        """

        if not self.source_lang_combo or not self.target_lang_combo:
            return
        provider_choice = (
            provider_key if provider_key is not None else self.selected_provider_key
        )
        previous_source = (
            self.source_lang_combo.currentData()
            if self.source_lang_combo.count()
            else None
        )
        previous_target = (
            self.target_lang_combo.currentData()
            if self.target_lang_combo.count()
            else None
        )
        language_choices = self.translation_manager.get_provider_language_choices(
            provider_choice
        )
        # Sort by language name (second element of tuple)
        language_choices = sorted(language_choices, key=lambda x: x[1].lower())
        available_codes = {code for code, _ in language_choices}
        self.source_lang_combo.blockSignals(True)
        self.target_lang_combo.blockSignals(True)
        self.source_lang_combo.clear()
        self.target_lang_combo.clear()
        self.source_lang_combo.addItem("Auto detect", None)
        for code, name in language_choices:
            display_code = code.lower().replace("-", "_")
            label = f"{name} ({display_code})"
            self.source_lang_combo.addItem(label, code)
            self.target_lang_combo.addItem(label, code)
        if previous_source and previous_source in available_codes:
            source_index = self.source_lang_combo.findData(previous_source)
            self.source_lang_combo.setCurrentIndex(
                source_index if source_index >= 0 else 0
            )
        else:
            self.source_lang_combo.setCurrentIndex(0)
        preferred_target: Optional[str] = None
        if previous_target and previous_target in available_codes:
            preferred_target = previous_target
        elif "EN" in available_codes:
            preferred_target = "EN"
        elif language_choices:
            preferred_target = language_choices[0][0]
        if preferred_target is not None:
            target_index = self.target_lang_combo.findData(preferred_target)
            if target_index >= 0:
                self.target_lang_combo.setCurrentIndex(target_index)
        self.source_lang_combo.blockSignals(False)
        self.target_lang_combo.blockSignals(False)

    def populate_provider_combo(self) -> None:
        """Fill the provider combo box with available translation services."""

        if not self.provider_combo:
            return
        self.provider_combo.blockSignals(True)
        self.provider_combo.clear()
        self.provider_combo.addItem("Manual (disabled)", None)
        for key, provider in self.translation_manager.providers.items():
            available, message = provider.is_available()
            label = provider.name if available else f"{provider.name} (setup required)"
            self.provider_combo.addItem(label, key)
            index = self.provider_combo.count() - 1
            self.provider_combo.setItemData(index, message, Qt.ToolTipRole)
        self.provider_combo.blockSignals(False)
        self.provider_combo.setCurrentIndex(0)
        self.update_provider_status(None)

    def on_provider_changed(self) -> None:
        """Handle provider combo box selection change."""

        provider_key = (
            self.provider_combo.currentData() if self.provider_combo else None
        )
        self.selected_provider_key = provider_key
        self.update_provider_status(provider_key)

    def update_provider_status(self, provider_key: Optional[str]) -> None:
        """Update status label and button states for the given provider.

        Args:
            provider_key: Provider identifier, or None if disabled.
        """

        if not self.provider_status_label or not self.translate_btn:
            return
        if not provider_key:
            self.provider_status_label.setText(
                "Machine translation disabled. Select a provider and configure its API key to enable auto-translate."
            )
            self.translate_btn.setEnabled(False)
            if self.auto_translate_all_btn:
                self.auto_translate_all_btn.setEnabled(False)
            self.selected_provider_key = None
            self.populate_language_combos(None)
            return
        available, message = self.translation_manager.is_provider_available(
            provider_key
        )
        provider_name = self.translation_manager.get_provider_name(provider_key)
        if available:
            self.provider_status_label.setText(f"{provider_name} ready: {message}")
        else:
            self.provider_status_label.setText(message)
        self.translate_btn.setEnabled(available)
        if self.auto_translate_all_btn:
            self.auto_translate_all_btn.setEnabled(
                available and bool(self.translations)
            )
        self.selected_provider_key = provider_key
        self.populate_language_combos(provider_key)

    def handle_auto_translate(self) -> None:
        """Translate the current item using the selected provider."""

        if not self.current_item:
            QMessageBox.information(
                self, "Auto-Translate", "Select a source string first."
            )
            return
        provider_key = (
            self.provider_combo.currentData() if self.provider_combo else None
        )
        if not provider_key:
            QMessageBox.information(
                self,
                "Auto-Translate",
                "Select a translation provider and configure its API key before using auto-translate.",
            )
            return
        target_lang = (
            self.target_lang_combo.currentData() if self.target_lang_combo else None
        )
        if not target_lang:
            QMessageBox.warning(
                self, "Missing Target Language", "Please select a target language."
            )
            return
        source_lang = (
            self.source_lang_combo.currentData() if self.source_lang_combo else None
        )
        source_text = self.current_item.source
        if not source_text.strip():
            QMessageBox.information(self, "Auto-Translate", "Source text is empty.")
            return
        protected_text, placeholder_map = self.translation_manager.protect_placeholders(
            source_text
        )
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            translated = self.translation_manager.translate(
                provider_key,
                protected_text,
                target_lang,
                source_lang,
            )
        except TranslationError as exc:
            QMessageBox.warning(self, "Translation Failed", str(exc))
            if self.status_bar:
                self.status_bar.showMessage(f"Translation failed: {exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        restored = self.translation_manager.restore_placeholders(
            translated, placeholder_map
        )
        self.translation_text.setPlainText(restored)
        if self.current_item:
            self.current_item.is_machine_translated = True
        if self.status_bar:
            self.status_bar.showMessage(
                f"Translated using {self.translation_manager.get_provider_name(provider_key)}"
            )

    def auto_translate_all_entries(self) -> None:
        """Machine-translate all untranslated entries in the current file."""

        if not self.translations:
            QMessageBox.information(
                self,
                "Translate All Missing",
                "Load a translation file before running this action.",
            )
            return
        provider_key = (
            self.provider_combo.currentData() if self.provider_combo else None
        )
        if not provider_key:
            QMessageBox.information(
                self,
                "Translate All Missing",
                "Select a translation provider and configure its API key before translating.",
            )
            return
        target_lang = (
            self.target_lang_combo.currentData() if self.target_lang_combo else None
        )
        if not target_lang:
            QMessageBox.warning(
                self, "Missing Target Language", "Please select a target language."
            )
            return
        source_lang = (
            self.source_lang_combo.currentData() if self.source_lang_combo else None
        )
        items_to_translate = [
            item for item in self.translations if not item.translation.strip()
        ]
        if not items_to_translate:
            QMessageBox.information(
                self, "Translate All Missing", "Every entry already has a translation."
            )
            return
        confirm = QMessageBox.question(
            self,
            "Translate All Missing",
            (
                "This will send all untranslated strings to the selected provider.\n\n"
                "Placeholder values may need manual review, and automatic translations may overwrite manual work.\n\n"
                "Do you want to continue?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        if self.auto_translate_all_btn:
            self.auto_translate_all_btn.setEnabled(False)
        translated_count = 0
        errors: List[str] = []
        provider_name = self.translation_manager.get_provider_name(provider_key)
        for item in items_to_translate:
            protected_text, mapping = self.translation_manager.protect_placeholders(
                item.source
            )
            try:
                translated = self.translation_manager.translate(
                    provider_key,
                    protected_text,
                    target_lang,
                    source_lang,
                )
            except TranslationError as exc:
                errors.append(f"{item.source[:40]}…: {exc}")
                continue
            except (
                Exception
            ) as exc:  # Defensive: catch any unexpected provider/requests issues
                errors.append(f"{item.source[:40]}…: {exc}")
                continue
            try:
                restored = self.translation_manager.restore_placeholders(
                    translated, mapping
                )
            except Exception as exc:  # Defensive: never crash on placeholder restore
                errors.append(f"{item.source[:40]}…: restore failed ({exc})")
                continue
            item.translation = restored or ""
            item.is_translated = bool(item.translation.strip())
            item.is_machine_translated = True
            translated_count += 1
        QApplication.restoreOverrideCursor()
        if self.provider_combo:
            self.update_provider_status(self.provider_combo.currentData())
        if translated_count:
            self.is_modified = True
            saved_item = self.current_item
            self.update_translation_list()
            self.update_stats()

            if saved_item:
                for row in range(self._filter_proxy.rowCount()):
                    proxy_index = self._filter_proxy.index(row, 0)
                    item = proxy_index.data(TranslationRoles.ItemRole)
                    if item is saved_item:
                        self.translation_list.setCurrentIndex(proxy_index)
                        self.current_item = saved_item
                        self.translation_text.blockSignals(True)
                        self.translation_text.setPlainText(self.current_item.translation)
                        self.translation_text.blockSignals(False)
                        break
                else:
                    self.current_item = None
                    self.clear_editor()
            else:
                self.current_item = None
                self.clear_editor()

            if self.status_bar:
                self.status_bar.showMessage(
                    f"Auto-translated {translated_count} entries using {provider_name}."
                )
        if errors:
            preview = "\n".join(errors[:5])
            message = f"Completed with {len(errors)} issue(s)."
            if preview:
                message += f"\n\n{preview}"
            QMessageBox.warning(self, "Translate All Missing", message)
        elif not translated_count:
            QMessageBox.warning(
                self,
                "Translate All Missing",
                "No entries were translated. Verify the provider configuration and try again.",
            )
        if self.auto_translate_all_btn:
            self.auto_translate_all_btn.setEnabled(bool(self.translations))

    def update_preview(self) -> None:
        """Render the translation with placeholder values in the preview area."""

        if not self.current_item:
            self.preview_text.clear()
            return
        placeholder_values = self.get_placeholder_values()
        preview = self.current_item.preview_with_placeholders(placeholder_values)
        self.preview_text.setPlainText(
            preview if preview else "(No translation provided)"
        )

    def on_translation_changed(self) -> None:
        """Sync translation text changes to the current item and model."""

        if not self.current_item:
            return
        new_translation = self.translation_text.toPlainText()
        if new_translation != self.current_item.translation:
            self.current_item.translation = new_translation
            self.current_item.is_translated = bool(new_translation.strip())
            self.is_modified = True
            self._update_current_model_item()

            self.update_stats()
            self.update_preview()
            if self.current_file and hasattr(self.window, "setWindowTitle"):
                filename = Path(self.current_file).name
                self.window.setWindowTitle(f"Translation Editor - {filename} *")
            if self.current_item.translation.strip():
                is_valid, error_msg = self.current_item.validate_translation()
                if not is_valid and self.status_bar:
                    self.status_bar.showMessage(f"Validation Error: {error_msg}")
                elif self.status_bar:
                    self.status_bar.showMessage("Translation valid")
            elif self.status_bar:
                self.status_bar.showMessage("Ready")

    def _update_current_model_item(self) -> None:
        """Sync current_item's data to the corresponding model item."""

        if not self.current_item:
            return

        current_index = self.translation_list.currentIndex()
        if not current_index.isValid():
            return

        source_index = self._filter_proxy.mapToSource(current_index)
        if not source_index.isValid():
            return

        model_item = self._list_model.itemFromIndex(source_index)
        if model_item:
            icon_provider = IconProvider.instance()
            self._update_model_item_display(model_item, self.current_item, icon_provider)
            model_item.setData(self.current_item.translation.lower(), TranslationRoles.TranslationRole)
            model_item.setData(self.current_item.is_translated, TranslationRoles.IsTranslatedRole)
            model_item.setData(self.current_item.is_machine_translated, TranslationRoles.IsMachineTranslatedRole)
            model_item.setData(self.current_item.marker, TranslationRoles.MarkerRole)

    def _on_marker_changed(self) -> None:
        """Handle marker combo box selection change."""
        if not self.current_item:
            return
        new_marker = self.marker_combo.currentData()
        if new_marker != self.current_item.marker:
            self.current_item.marker = new_marker
            self.current_item.is_machine_translated = False
            self.is_modified = True
            self._update_current_model_item()

            if self.current_file and hasattr(self.window, "setWindowTitle"):
                filename = Path(self.current_file).name
                self.window.setWindowTitle(f"Translation Editor - {filename} *")
            if self.status_bar:
                marker_label = MARKER_LABELS.get(new_marker, "")
                if new_marker == TranslationMarker.NONE:
                    self.status_bar.showMessage("Marker removed")
                else:
                    self.status_bar.showMessage(f"Marked as: {marker_label}")

    def copy_source_to_translation(self) -> None:
        """Copy source text to translation field and focus the input."""
        if self.current_item:
            self.translation_text.setPlainText(self.current_item.source)
            self.translation_text.setFocus()

    def focus_search(self) -> None:
        """Focus the search/filter input field."""
        if self.filter_input:
            self.filter_input.setFocus()
            self.filter_input.selectAll()

    def select_next_item(self) -> None:
        """Move to the next item in the translation list."""
        if not self.translation_list:
            return
        current_index = self.translation_list.currentIndex()
        row_count = self._filter_proxy.rowCount()
        if current_index.isValid() and current_index.row() < row_count - 1:
            next_index = self._filter_proxy.index(current_index.row() + 1, 0)
            self.translation_list.setCurrentIndex(next_index)
            self.translation_text.setFocus()
        elif not current_index.isValid() and row_count > 0:
            # No selection, select first item
            first_index = self._filter_proxy.index(0, 0)
            self.translation_list.setCurrentIndex(first_index)
            self.translation_text.setFocus()

    def select_prev_item(self) -> None:
        """Move to the previous item in the translation list."""
        if not self.translation_list:
            return
        current_index = self.translation_list.currentIndex()
        if current_index.isValid() and current_index.row() > 0:
            prev_index = self._filter_proxy.index(current_index.row() - 1, 0)
            self.translation_list.setCurrentIndex(prev_index)
            self.translation_text.setFocus()

    def handle_auto_translate_with_focus(self) -> None:
        """Run auto-translate and focus the translation input afterwards."""
        self.handle_auto_translate()
        if self.current_item and self.current_item.translation:
            self.translation_text.setFocus()

    def setup_shortcuts(self, shortcuts: Dict[str, str]) -> None:
        """Configure keyboard shortcuts for editor actions.

        Args:
            shortcuts: Dictionary mapping shortcut keys to key sequences.
        """
        for shortcut in self._shortcuts.values():
            shortcut.setEnabled(False)
            shortcut.deleteLater()
        self._shortcuts.clear()

        shortcut_actions = {
            "copy_source": self.copy_source_to_translation,
            "auto_translate": self.handle_auto_translate_with_focus,
            "search": self.focus_search,
            "next_item": self.select_next_item,
            "prev_item": self.select_prev_item,
        }

        for key, action in shortcut_actions.items():
            sequence = shortcuts.get(key, "")
            if sequence:
                shortcut = QShortcut(QKeySequence(sequence), self)
                shortcut.activated.connect(action)
                self._shortcuts[key] = shortcut

    def update_provider_state_after_load(self) -> None:
        """Refresh provider status after loading a new file."""

        if self.provider_combo:
            self.update_provider_status(self.provider_combo.currentData())


__all__ = ["EditorTab"]
