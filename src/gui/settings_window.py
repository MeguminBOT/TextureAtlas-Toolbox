#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog displaying current animation and spritesheet override settings."""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels, WindowTitles

# Keys that are internal metadata and should not be shown in the overview.
_HIDDEN_KEYS = frozenset(
    {
        "duration_display_value",
        "duration_display_type",
        "fps",
    }
)

# Human-readable labels for settings keys.
_KEY_LABELS: dict[str, str] = {
    "animation_format": "Animation Format",
    "duration": "Duration (ms)",
    "delay": "Loop Delay (ms)",
    "period": "Min Period (ms)",
    "scale": "Scale",
    "resampling_method": "Resampling",
    "threshold": "Threshold",
    "var_delay": "Variable Delay",
    "indices": "Indices",
    "filename": "Filename",
    "frame_format": "Frame Format",
    "frame_scale": "Frame Scale",
    "frames": "Frames",
}


class SettingsWindow(QDialog):
    """Modal dialog listing user-defined animation and spritesheet overrides.

    Attributes:
        settings_manager: Manager holding the current override dictionaries.
        content_widget: Scrollable container for settings labels.
        content_layout: Vertical layout inside the content widget.
    """

    tr = translate

    def __init__(self, parent, settings_manager):
        """Initialize the settings overview dialog.

        Args:
            parent: Parent widget for the dialog.
            settings_manager: Manager containing override settings to display.
        """
        super().__init__(parent)
        self.settings_manager = settings_manager
        self.setWindowTitle(self.tr(WindowTitles.CURRENT_SETTINGS_OVERVIEW))
        self.setModal(True)
        self.resize(500, 400)

        main_layout = QVBoxLayout(self)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.update_settings()

        scroll_area.setWidget(self.content_widget)
        main_layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        close_button = QPushButton(self.tr(ButtonLabels.CLOSE))
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        main_layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_value(key: str, value) -> str:
        """Return a human-readable representation of *value*."""

        if key == "threshold":
            return f"{value * 100:.0f} %"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, list):
            return ", ".join(str(v) for v in value)
        return str(value)

    def _add_override_block(
        self,
        name: str,
        overrides: dict,
        settings_dict: dict,
        settings_type: str,
    ):
        """Add a single collapsible override entry with per-key values and a Clear button.

        Args:
            name: Override name (animation or spritesheet identifier).
            overrides: The stored override dict for this entry.
            settings_dict: Reference to the parent dict so Clear can remove it.
            settings_type: ``"animation"`` or ``"spritesheet"``, for styling.
        """

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(4, 0, 4, 0)
        container_layout.setSpacing(0)

        # Header row: collapse toggle + name + clear button
        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(2)

        visible_count = sum(1 for k in overrides if k not in _HIDDEN_KEYS)
        toggle_btn = QPushButton(f"▶ {name}  ({visible_count})")
        toggle_btn.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        toggle_btn.setFlat(True)
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet(
            "QPushButton { text-align: left; padding: 0; margin: 0; border: none; }"
        )
        toggle_btn.setFixedHeight(18)
        header_row.addWidget(toggle_btn)
        header_row.addStretch()

        clear_btn = QPushButton(self.tr("Clear"))
        clear_btn.setFixedWidth(44)
        clear_btn.setFixedHeight(16)
        clear_btn.setToolTip(self.tr("Remove all overrides for this entry"))
        clear_btn.clicked.connect(
            lambda _checked=False, n=name, d=settings_dict: self._clear_override(n, d)
        )
        header_row.addWidget(clear_btn)
        container_layout.addLayout(header_row)

        # Collapsible details widget
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(0)

        small_font = QFont("Arial", 8)

        visible_keys = [k for k in overrides if k not in _HIDDEN_KEYS]
        if visible_keys:
            for key in visible_keys:
                display_key = _KEY_LABELS.get(key, key)
                display_val = self._format_value(key, overrides[key])
                kv_label = QLabel(f"  {display_key}: {display_val}")
                kv_label.setFont(small_font)
                kv_label.setStyleSheet("QLabel { margin: 0 0 0 12px; padding: 0; }")
                kv_label.setFixedHeight(14)
                details_layout.addWidget(kv_label)
        else:
            empty_label = QLabel(self.tr("  (no overrides)"))
            empty_label.setFont(small_font)
            empty_label.setStyleSheet(
                "QLabel { margin: 0 0 0 12px; color: palette(placeholderText); font-style: italic; padding: 0; }"
            )
            empty_label.setFixedHeight(14)
            details_layout.addWidget(empty_label)

        container_layout.addWidget(details_widget)

        # Start collapsed
        details_widget.setVisible(False)

        # Wire up the toggle
        def _toggle(_checked=False, dw=details_widget, btn=toggle_btn):
            collapsed = dw.isVisible()
            dw.setVisible(not collapsed)
            arrow = "▶" if collapsed else "▼"
            btn.setText(f"{arrow} {name}  ({visible_count})")

        toggle_btn.clicked.connect(_toggle)

        self.content_layout.addWidget(container)

    def _clear_override(self, name: str, settings_dict: dict):
        """Remove an override entry and refresh the display."""

        if name in settings_dict:
            del settings_dict[name]
        self.update_settings()

    # ------------------------------------------------------------------
    # Main refresh
    # ------------------------------------------------------------------

    def update_settings(self):
        """Refresh the displayed animation and spritesheet settings."""

        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # --- Animation overrides ---
        animation_label = QLabel(self.tr("Animation Settings"))
        animation_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        animation_label.setStyleSheet(
            "QLabel { color: palette(highlight); margin: 6px 0 3px 0; }"
        )
        self.content_layout.addWidget(animation_label)

        if self.settings_manager.animation_settings:
            for name, overrides in self.settings_manager.animation_settings.items():
                self._add_override_block(
                    name,
                    overrides,
                    self.settings_manager.animation_settings,
                    "animation",
                )
        else:
            no_settings_label = QLabel(
                self.tr("  No animation-specific settings configured")
            )
            no_settings_label.setFont(QFont("Arial", 8))
            no_settings_label.setStyleSheet(
                "QLabel { margin-left: 16px; color: palette(placeholderText); font-style: italic; }"
            )
            self.content_layout.addWidget(no_settings_label)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setStyleSheet("QFrame { margin: 10px 0; }")
        self.content_layout.addWidget(separator)

        # --- Spritesheet overrides ---
        spritesheet_label = QLabel(self.tr("Spritesheet Settings"))
        spritesheet_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        spritesheet_label.setStyleSheet(
            "QLabel { color: palette(highlight); margin: 6px 0 3px 0; }"
        )
        self.content_layout.addWidget(spritesheet_label)

        if self.settings_manager.spritesheet_settings:
            for name, overrides in self.settings_manager.spritesheet_settings.items():
                self._add_override_block(
                    name,
                    overrides,
                    self.settings_manager.spritesheet_settings,
                    "spritesheet",
                )
        else:
            no_settings_label = QLabel(
                self.tr("  No spritesheet-specific settings configured")
            )
            no_settings_label.setFont(QFont("Arial", 8))
            no_settings_label.setStyleSheet(
                "QLabel { margin-left: 16px; color: palette(placeholderText); font-style: italic; }"
            )
            self.content_layout.addWidget(no_settings_label)

        self.content_layout.addStretch()
