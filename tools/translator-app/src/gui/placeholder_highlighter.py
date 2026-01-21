"""Syntax highlighter for brace-delimited placeholder tokens.

Provides visual emphasis for placeholders like ``{value}`` in text edit
widgets, helping translators identify tokens that must remain unchanged.
"""

from __future__ import annotations

import re

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QSyntaxHighlighter


class PlaceholderHighlighter(QSyntaxHighlighter):
    """Highlight brace-delimited placeholders in Qt text widgets.

    Placeholders matching the pattern ``{...}`` are rendered in bold with a
    distinct color that adapts to dark or light themes.

    Attributes:
        dark_mode: Whether the dark theme palette is active.
        placeholder_format: Text format applied to placeholder tokens.
    """

    def __init__(self, parent=None, dark_mode: bool = False) -> None:
        """Initialize the highlighter.

        Args:
            parent: The QTextDocument or QTextEdit to highlight.
            dark_mode: Use dark-theme colors if True.
        """
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.placeholder_format = QTextCharFormat()
        self.setup_formats()

    def setup_formats(self) -> None:
        """Configure text formatting for the current color theme.

        Sets the foreground color (light blue for dark mode, darker blue
        for light mode) and bold weight for placeholder tokens.
        """
        if self.dark_mode:
            self.placeholder_format.setForeground(QColor(100, 200, 255))
        else:
            self.placeholder_format.setForeground(QColor(0, 100, 200))
        self.placeholder_format.setFontWeight(QFont.Bold)

    def highlightBlock(self, text: str) -> None:  # pragma: no cover - Qt painting
        """Apply formatting to placeholder tokens in a text block.

        Args:
            text: The text content of the current block being highlighted.
        """
        pattern = r"\{[^}]*\}"
        for match in re.finditer(pattern, text):
            start = match.start()
            length = match.end() - start
            self.setFormat(start, length, self.placeholder_format)

    def set_dark_mode(self, dark_mode: bool) -> None:
        """Switch the highlight palette and refresh the document.

        Args:
            dark_mode: True to use dark-theme colors, False for light.
        """
        self.dark_mode = dark_mode
        self.setup_formats()
        self.rehighlight()


__all__ = ["PlaceholderHighlighter"]
