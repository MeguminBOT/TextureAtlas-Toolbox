#!/usr/bin/env python3
"""Dialog for matching vanished translation strings to new unfinished strings.

When Qt's lupdate runs, some strings may be renamed or slightly modified.
This dialog helps match vanished strings (with existing translations) to
new unfinished strings, allowing translation reuse instead of losing work.
"""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


@dataclass
class StringMatch:
    """A potential match between a vanished and a new string.

    Attributes:
        vanished_source: The source text of the vanished string.
        vanished_translation: The existing translation for the vanished string.
        new_source: The source text of the new unfinished string.
        context: The context where the new string appears.
        similarity: Similarity score (0.0 to 1.0).
        selected: Whether the user has selected this match for transfer.
    """

    vanished_source: str
    vanished_translation: str
    new_source: str
    context: str
    similarity: float
    selected: bool = True


def compute_similarity(s1: str, s2: str) -> float:
    """Compute similarity ratio between two strings.

    Uses SequenceMatcher for fuzzy matching. Also considers normalized
    versions (lowercase, stripped) for better matching.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Similarity ratio between 0.0 and 1.0.
    """
    if not s1 or not s2:
        return 0.0

    # Direct comparison
    direct = SequenceMatcher(None, s1, s2).ratio()

    # Normalized comparison (lowercase, stripped, single spaces)
    norm1 = " ".join(s1.lower().split())
    norm2 = " ".join(s2.lower().split())
    normalized = SequenceMatcher(None, norm1, norm2).ratio()

    # Return the better score
    return max(direct, normalized)


def find_potential_matches(
    vanished: List[Tuple[str, str]],
    new_unfinished: List[Tuple[str, str]],  # (source, context)
    min_similarity: float = 0.6,
) -> List[StringMatch]:
    """Find potential matches between vanished and new strings.

    For each vanished string with a translation, find new unfinished strings
    that are similar enough to suggest they might be the same string with
    minor modifications.

    Args:
        vanished: List of (source, translation) tuples for vanished strings.
        new_unfinished: List of (source, context) tuples for new unfinished strings.
        min_similarity: Minimum similarity threshold (0.0-1.0).

    Returns:
        List of StringMatch objects sorted by similarity (highest first).
    """
    matches: List[StringMatch] = []
    used_new: set[str] = set()

    # Only consider vanished strings that have translations
    vanished_with_trans = [(s, t) for s, t in vanished if t.strip()]

    for van_source, van_trans in vanished_with_trans:
        best_match: Optional[StringMatch] = None
        best_similarity = min_similarity

        for new_source, context in new_unfinished:
            if new_source in used_new:
                continue

            sim = compute_similarity(van_source, new_source)
            if sim > best_similarity:
                best_similarity = sim
                best_match = StringMatch(
                    vanished_source=van_source,
                    vanished_translation=van_trans,
                    new_source=new_source,
                    context=context,
                    similarity=sim,
                    selected=sim >= 0.8,  # Auto-select high confidence matches
                )

        if best_match:
            matches.append(best_match)
            used_new.add(best_match.new_source)

    # Sort by similarity (highest first)
    matches.sort(key=lambda m: m.similarity, reverse=True)
    return matches


class StringMatchingDialog(QDialog):
    """Dialog for reviewing and confirming string matches.

    Shows potential matches between vanished strings and new unfinished strings,
    allowing users to accept or reject each match. Accepted matches will have
    their translations transferred.

    Attributes:
        matches: List of potential StringMatch objects.
        accepted_matches: Matches the user confirmed for transfer.
        remaining_vanished: Vanished strings that weren't matched.
    """

    def __init__(
        self,
        parent,
        matches: List[StringMatch],
        remaining_vanished: List[Tuple[str, str]],
        file_path: Path,
    ) -> None:
        """Initialize the string matching dialog.

        Args:
            parent: Parent widget.
            matches: List of potential matches to review.
            remaining_vanished: Vanished strings with no good matches.
            file_path: Path to the .ts file being processed.
        """
        super().__init__(parent)
        self.matches = matches
        self.remaining_vanished = remaining_vanished
        self.file_path = file_path
        self.accepted_matches: List[StringMatch] = []

        self.setWindowTitle(f"Match Vanished Strings - {file_path.name}")
        self.setMinimumSize(900, 600)
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the dialog layout."""
        layout = QVBoxLayout(self)

        # Header
        match_count = len(self.matches)
        remaining_count = len(self.remaining_vanished)
        header = QLabel(
            f"<b>Found {match_count} potential match{'es' if match_count != 1 else ''}</b> "
            f"between vanished strings and new unfinished strings.<br>"
            f"<b>{remaining_count} vanished string{'s' if remaining_count != 1 else ''}</b> "
            f"could not be matched and will be handled separately."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        if self.matches:
            # Splitter for table and preview
            splitter = QSplitter(Qt.Vertical)

            # Match table
            self.table = QTableWidget()
            self.table.setColumnCount(5)
            self.table.setHorizontalHeaderLabels(
                ["Transfer", "Similarity", "Vanished Source", "New Source", "Context"]
            )
            self.table.setRowCount(len(self.matches))
            self.table.setAlternatingRowColors(True)
            self.table.setSelectionBehavior(QTableWidget.SelectRows)
            self.table.setSelectionMode(QTableWidget.SingleSelection)

            header_view = self.table.horizontalHeader()
            header_view.setSectionResizeMode(0, QHeaderView.ResizeToContents)
            header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
            header_view.setSectionResizeMode(2, QHeaderView.Stretch)
            header_view.setSectionResizeMode(3, QHeaderView.Stretch)
            header_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)

            self._checkboxes: List[QCheckBox] = []
            for row, match in enumerate(self.matches):
                # Checkbox for selection
                checkbox = QCheckBox()
                checkbox.setChecked(match.selected)
                checkbox.stateChanged.connect(
                    lambda state, r=row: self._on_checkbox_changed(r, state)
                )
                self._checkboxes.append(checkbox)

                checkbox_widget = QWidget()
                checkbox_layout = QHBoxLayout(checkbox_widget)
                checkbox_layout.addWidget(checkbox)
                checkbox_layout.setAlignment(Qt.AlignCenter)
                checkbox_layout.setContentsMargins(0, 0, 0, 0)
                self.table.setCellWidget(row, 0, checkbox_widget)

                # Similarity percentage
                sim_item = QTableWidgetItem(f"{match.similarity:.0%}")
                sim_item.setTextAlignment(Qt.AlignCenter)
                if match.similarity >= 0.9:
                    sim_item.setBackground(Qt.green)
                elif match.similarity >= 0.75:
                    sim_item.setBackground(Qt.yellow)
                else:
                    sim_item.setBackground(Qt.lightGray)
                self.table.setItem(row, 1, sim_item)

                # Vanished source preview
                van_preview = match.vanished_source[:50]
                if len(match.vanished_source) > 50:
                    van_preview += "..."
                van_item = QTableWidgetItem(van_preview)
                van_item.setToolTip(match.vanished_source)
                self.table.setItem(row, 2, van_item)

                # New source preview
                new_preview = match.new_source[:50]
                if len(match.new_source) > 50:
                    new_preview += "..."
                new_item = QTableWidgetItem(new_preview)
                new_item.setToolTip(match.new_source)
                self.table.setItem(row, 3, new_item)

                # Context
                ctx_item = QTableWidgetItem(match.context)
                self.table.setItem(row, 4, ctx_item)

            self.table.itemSelectionChanged.connect(self._on_selection_changed)
            splitter.addWidget(self.table)

            # Preview panel
            preview_widget = QWidget()
            preview_layout = QVBoxLayout(preview_widget)
            preview_layout.setContentsMargins(0, 5, 0, 0)

            preview_label = QLabel("<b>Selected Match Details:</b>")
            preview_layout.addWidget(preview_label)

            preview_scroll = QScrollArea()
            preview_scroll.setWidgetResizable(True)

            self.preview_content = QWidget()
            self.preview_layout = QVBoxLayout(self.preview_content)

            self.vanished_preview = QTextEdit()
            self.vanished_preview.setReadOnly(True)
            self.vanished_preview.setMaximumHeight(80)
            self.preview_layout.addWidget(QLabel("Vanished Source:"))
            self.preview_layout.addWidget(self.vanished_preview)

            self.new_preview = QTextEdit()
            self.new_preview.setReadOnly(True)
            self.new_preview.setMaximumHeight(80)
            self.preview_layout.addWidget(QLabel("New Source:"))
            self.preview_layout.addWidget(self.new_preview)

            self.translation_preview = QTextEdit()
            self.translation_preview.setReadOnly(True)
            self.translation_preview.setMaximumHeight(80)
            self.preview_layout.addWidget(QLabel("Translation to Transfer:"))
            self.preview_layout.addWidget(self.translation_preview)

            preview_scroll.setWidget(self.preview_content)
            preview_layout.addWidget(preview_scroll)

            splitter.addWidget(preview_widget)
            splitter.setSizes([400, 200])

            layout.addWidget(splitter, 1)

            # Select all / none buttons
            select_layout = QHBoxLayout()
            select_all_btn = QPushButton("Select All")
            select_all_btn.clicked.connect(self._select_all)
            select_layout.addWidget(select_all_btn)

            select_none_btn = QPushButton("Select None")
            select_none_btn.clicked.connect(self._select_none)
            select_layout.addWidget(select_none_btn)

            select_high_btn = QPushButton("Select High Confidence (≥80%)")
            select_high_btn.clicked.connect(self._select_high_confidence)
            select_layout.addWidget(select_high_btn)

            select_layout.addStretch()
            layout.addLayout(select_layout)
        else:
            # No matches found
            no_matches_label = QLabel(
                "<i>No potential matches found between vanished and new strings.</i>"
            )
            layout.addWidget(no_matches_label)

        # Remaining vanished info
        if self.remaining_vanished:
            remaining_label = QLabel(
                f"<br><b>{len(self.remaining_vanished)} unmatched vanished string(s)</b> "
                "will be shown in the next dialog where you can save or remove them."
            )
            remaining_label.setWordWrap(True)
            layout.addWidget(remaining_label)

        # Button row
        button_layout = QHBoxLayout()

        if self.matches:
            apply_btn = QPushButton("Apply Selected Matches")
            apply_btn.setToolTip(
                "Transfer translations from selected vanished strings to new strings"
            )
            apply_btn.clicked.connect(self._apply_matches)
            button_layout.addWidget(apply_btn)

        skip_btn = QPushButton("Skip Matching")
        skip_btn.setToolTip(
            "Don't transfer any translations, proceed to removal dialog"
        )
        skip_btn.clicked.connect(self.reject)
        button_layout.addWidget(skip_btn)

        layout.addLayout(button_layout)

        # Select first row if available
        if self.matches:
            self.table.selectRow(0)

    def _on_checkbox_changed(self, row: int, state: int) -> None:
        """Handle checkbox state change.

        Args:
            row: Row index of the changed checkbox.
            state: New checkbox state (Qt.Checked or Qt.Unchecked).
        """
        self.matches[row].selected = state == Qt.Checked

    def _on_selection_changed(self) -> None:
        """Update preview when table selection changes."""
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        match = self.matches[row]

        self.vanished_preview.setPlainText(match.vanished_source)
        self.new_preview.setPlainText(match.new_source)
        self.translation_preview.setPlainText(match.vanished_translation)

    def _select_all(self) -> None:
        """Select all matches for transfer.

        Marks every match in the table as selected for translation transfer.
        """
        for i, match in enumerate(self.matches):
            match.selected = True
            self._checkboxes[i].setChecked(True)

    def _select_none(self) -> None:
        """Deselect all matches.

        Unchecks every match in the table so none are transferred.
        """
        for i, match in enumerate(self.matches):
            match.selected = False
            self._checkboxes[i].setChecked(False)

    def _select_high_confidence(self) -> None:
        """Select only matches with at least 80% similarity.

        Unchecks lower-confidence matches to avoid accidental transfers.
        """
        for i, match in enumerate(self.matches):
            match.selected = match.similarity >= 0.8
            self._checkboxes[i].setChecked(match.selected)

    def _apply_matches(self) -> None:
        """Accept selected matches and close dialog.

        Populates ``accepted_matches`` with user-confirmed matches and
        closes the dialog with the Accepted result.
        """
        self.accepted_matches = [m for m in self.matches if m.selected]
        self.accept()


def recover_duplicate_translations(file_path: Path) -> Tuple[int, List[str]]:
    """Recover translations from vanished strings that match active unfinished strings.

    When the same source text exists as both a vanished entry (with translation)
    and an active unfinished entry, this function copies the translation from
    the vanished entry to the active one, then removes all vanished/obsolete
    entries from the file to keep it clean.

    This is different from fuzzy matching - it handles exact duplicates where
    the same string was moved to a different context.

    Args:
        file_path: Path to the .ts file.

    Returns:
        Tuple of (number of recovered translations, list of recovered source strings).
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    # First pass: collect vanished strings with translations
    vanished_translations: Dict[str, str] = {}
    for message in root.iter("message"):
        translation_elem = message.find("translation")
        if translation_elem is None:
            continue

        trans_type = translation_elem.get("type", "")
        if trans_type not in ("vanished", "obsolete"):
            continue

        source_elem = message.find("source")
        if source_elem is None or not source_elem.text:
            continue

        translation = translation_elem.text or ""
        if translation.strip():
            # Keep the first (or longest) translation found
            source = source_elem.text
            if source not in vanished_translations or len(translation) > len(
                vanished_translations[source]
            ):
                vanished_translations[source] = translation

    # Second pass: apply translations to active unfinished entries
    recovered = 0
    recovered_sources: List[str] = []

    for message in root.iter("message"):
        translation_elem = message.find("translation")
        if translation_elem is None:
            continue

        trans_type = translation_elem.get("type", "")
        # Skip vanished/obsolete
        if trans_type in ("vanished", "obsolete"):
            continue

        source_elem = message.find("source")
        if source_elem is None or not source_elem.text:
            continue

        source = source_elem.text
        current_trans = translation_elem.text or ""

        # Check if unfinished and we have a vanished translation
        is_unfinished = trans_type == "unfinished" or not current_trans.strip()
        if is_unfinished and source in vanished_translations:
            translation_elem.text = vanished_translations[source]
            # Remove unfinished marker
            if "type" in translation_elem.attrib:
                del translation_elem.attrib["type"]
            recovered += 1
            if source not in recovered_sources:
                recovered_sources.append(source)

    # Third pass: remove all vanished/obsolete entries from the file
    removed_count = 0
    for context in root.findall("context"):
        messages_to_remove = []
        for message in context.findall("message"):
            translation_elem = message.find("translation")
            if translation_elem is not None:
                trans_type = translation_elem.get("type", "")
                if trans_type in ("vanished", "obsolete"):
                    messages_to_remove.append(message)

        for message in messages_to_remove:
            context.remove(message)
            removed_count += 1

        # Remove empty contexts (no messages left)
        if len(context.findall("message")) == 0:
            root.remove(context)

    if recovered > 0 or removed_count > 0:
        ET.indent(tree, space="    ")
        with open(file_path, "w", encoding="utf-8") as f:
            tree.write(f, encoding="unicode", xml_declaration=True)

    return recovered, recovered_sources


def apply_matches_to_file(file_path: Path, matches: List[StringMatch]) -> int:
    """Apply accepted matches to a .ts file.

    Transfers translations from vanished strings to matching new strings.

    Args:
        file_path: Path to the .ts file.
        matches: List of accepted StringMatch objects.

    Returns:
        Number of translations transferred.
    """
    if not matches:
        return 0

    tree = ET.parse(file_path)
    root = tree.getroot()

    # Build lookup from new source to translation
    new_source_to_translation = {m.new_source: m.vanished_translation for m in matches}

    transferred = 0
    for context in root.findall("context"):
        for message in context.findall("message"):
            source_elem = message.find("source")
            if source_elem is None or not source_elem.text:
                continue

            source = source_elem.text
            if source not in new_source_to_translation:
                continue

            translation_elem = message.find("translation")
            if translation_elem is None:
                continue

            # Only transfer if the string is unfinished/empty
            trans_type = translation_elem.get("type", "")
            current_trans = translation_elem.text or ""

            if trans_type == "unfinished" or not current_trans.strip():
                translation_elem.text = new_source_to_translation[source]
                # Remove unfinished marker since we now have a translation
                if "type" in translation_elem.attrib:
                    del translation_elem.attrib["type"]
                transferred += 1

    if transferred > 0:
        ET.indent(tree, space="    ")
        with open(file_path, "w", encoding="utf-8") as f:
            tree.write(f, encoding="unicode", xml_declaration=True)

    return transferred


def extract_new_unfinished_strings(file_path: Path) -> List[Tuple[str, str]]:
    """Extract new unfinished strings from a .ts file.

    Args:
        file_path: Path to the .ts file.

    Returns:
        List of (source, context) tuples for unfinished/empty translations.
    """
    unfinished: List[Tuple[str, str]] = []

    try:
        tree = ET.parse(file_path)
        root = tree.getroot()

        for context in root.findall("context"):
            context_name_elem = context.find("name")
            context_name = (
                context_name_elem.text if context_name_elem is not None else ""
            )

            for message in context.findall("message"):
                source_elem = message.find("source")
                translation_elem = message.find("translation")

                if source_elem is None or translation_elem is None:
                    continue

                source = source_elem.text or ""
                trans_type = translation_elem.get("type", "")
                translation = translation_elem.text or ""

                # Skip vanished/obsolete strings
                if trans_type in ("vanished", "obsolete"):
                    continue

                # Include unfinished or empty translations
                if trans_type == "unfinished" or not translation.strip():
                    unfinished.append((source, context_name))

    except Exception:
        pass

    return unfinished


__all__ = [
    "StringMatch",
    "StringMatchingDialog",
    "apply_matches_to_file",
    "compute_similarity",
    "extract_new_unfinished_strings",
    "find_potential_matches",
    "recover_duplicate_translations",
]
