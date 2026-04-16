#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Centralized theme engine for TextureAtlas Toolbox.

Manages 9 theme variants (Clean / Material / Fluent × Light / Dark / AMOLED),
accent colour presets, per-family icon fonts via qtawesome, and QSS generation.

Usage:
    from gui.theme_manager import (
        apply_theme, refresh_icons, icons,
        make_icon_button, ElidedLabel,
        THEME_TOKENS, ACCENT_PRESETS,
    )

    # Apply a theme to the running application
    apply_theme(app, window, "clean", "dark", accent_key="blue")

    # Refresh all child-widget icons after a theme switch
    refresh_icons(window)

    # Get a themed QIcon
    icon = icons.icon("folder_open")
"""

from __future__ import annotations

import os
import tempfile

from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
    QFrame,
)
from PySide6.QtCore import QPointF, Qt, QSize
from PySide6.QtGui import (
    QAction,
    QColor,
    QFont,
    QIcon,
    QPainter,
    QPalette,
    QPen,
    QPixmap,
)

try:
    from qt_material import apply_stylesheet as _qt_material_apply

    _HAS_QT_MATERIAL = True
except ImportError:
    _HAS_QT_MATERIAL = False

try:
    import qtawesome as qta

    _HAS_QTA = True
except ImportError:
    _HAS_QTA = False


# ═══════════════════════════════════════════════════════════════════════════
# Icon Registry
# ═══════════════════════════════════════════════════════════════════════════

# Mapping: icon_key → (msc/Codicons, mdi6/Material Design, ph/Phosphor)
_ICON_NAMES: dict[str, tuple[str, str, str]] = {
    "folder_open": ("msc.folder-opened", "mdi6.folder-open", "ph.folder-open"),
    "folder_plus": ("msc.new-folder", "mdi6.folder-plus", "ph.folder-plus"),
    "file_plus": ("msc.new-file", "mdi6.file-plus", "ph.file-plus"),
    "play": ("msc.play", "mdi6.play", "ph.play"),
    "pause": ("msc.debug-pause", "mdi6.pause", "ph.pause"),
    "stop": ("msc.debug-stop", "mdi6.stop", "ph.stop"),
    "trash": ("msc.trash", "mdi6.delete", "ph.trash"),
    "settings": ("msc.settings-gear", "mdi6.cog", "ph.gear"),
    "zoom_in": ("msc.zoom-in", "mdi6.magnify-plus-outline", "ph.magnifying-glass-plus"),
    "zoom_out": (
        "msc.zoom-out",
        "mdi6.magnify-minus-outline",
        "ph.magnifying-glass-minus",
    ),
    "reset": ("msc.discard", "mdi6.restore", "ph.arrow-counter-clockwise"),
    "save": ("msc.save", "mdi6.content-save", "ph.floppy-disk"),
    "download": ("msc.cloud-download", "mdi6.download", "ph.download-simple"),
    "layers": ("msc.layers", "mdi6.layers", "ph.stack"),
    "grid": ("msc.symbol-misc", "mdi6.view-grid-outline", "ph.grid-four"),
    "crosshair": ("msc.target", "mdi6.crosshairs", "ph.crosshair"),
    "eye": ("msc.eye", "mdi6.eye", "ph.eye"),
    "maximize": ("msc.screen-full", "mdi6.arrow-expand", "ph.arrows-out"),
    "center": (
        "msc.layout-centered",
        "mdi6.image-filter-center-focus",
        "ph.crosshair-simple",
    ),
    "fit": ("msc.layout", "mdi6.fit-to-screen", "ph.frame-corners"),
    "info": ("msc.info", "mdi6.information", "ph.info"),
    "warning": ("msc.warning", "mdi6.alert", "ph.warning"),
    "check": ("msc.check", "mdi6.check", "ph.check"),
    "x": ("msc.close", "mdi6.close", "ph.x"),
    "search": ("msc.search", "mdi6.magnify", "ph.magnifying-glass"),
    "replace": ("msc.replace", "mdi6.swap-horizontal", "ph.arrows-left-right"),
    "copy": ("msc.copy", "mdi6.content-copy", "ph.copy"),
    "image": ("msc.file-media", "mdi6.image-multiple-outline", "ph.image-square"),
    "film": ("msc.device-camera-video", "mdi6.filmstrip", "ph.film-strip"),
    "palette": ("msc.symbol-color", "mdi6.palette", "ph.palette"),
    "plus": ("msc.add", "mdi6.plus", "ph.plus"),
    "minus": ("msc.remove", "mdi6.minus", "ph.minus"),
    "arrow_up": ("msc.arrow-up", "mdi6.arrow-up", "ph.arrow-up"),
    "arrow_down": ("msc.arrow-down", "mdi6.arrow-down", "ph.arrow-down"),
    "tree_view": ("msc.list-tree", "mdi6.file-tree", "ph.tree-structure"),
    "list_view": ("msc.list-flat", "mdi6.format-list-bulleted", "ph.list"),
    "align_left": (
        "msc.layout-sidebar-left",
        "mdi6.format-horizontal-align-left",
        "ph.align-left",
    ),
    "align_h": (
        "msc.layout-centered",
        "mdi6.format-horizontal-align-center",
        "ph.align-center-horizontal",
    ),
    "align_right": (
        "msc.layout-sidebar-right",
        "mdi6.format-horizontal-align-right",
        "ph.align-right",
    ),
    "align_top": ("msc.triangle-up", "mdi6.format-vertical-align-top", "ph.align-top"),
    "align_v": (
        "msc.arrow-both",
        "mdi6.format-vertical-align-center",
        "ph.align-center-vertical",
    ),
    "align_bottom": (
        "msc.triangle-down",
        "mdi6.format-vertical-align-bottom",
        "ph.align-bottom",
    ),
    "undo": ("msc.discard", "mdi6.undo", "ph.arrow-u-up-left"),
    "redo": ("msc.redo", "mdi6.redo", "ph.arrow-u-up-right"),
    "keyboard": ("msc.keyboard", "mdi6.keyboard", "ph.keyboard"),
}

_FAMILY_PREFIX_IDX = {"clean": 0, "material": 1, "fluent": 2}

_ICON_FALLBACK: dict[str, str] = {
    "folder_open": "\U0001f4c2",
    "folder_plus": "\U0001f4c1",
    "file_plus": "\U0001f4c4",
    "play": "\u25b6",
    "pause": "\u23f8",
    "stop": "\u23f9",
    "trash": "\U0001f5d1",
    "settings": "\u2699",
    "zoom_in": "+",
    "zoom_out": "\u2212",
    "reset": "\u21ba",
    "save": "\U0001f4be",
    "download": "\u2b07",
    "layers": "\u2630",
    "grid": "\u2637",
    "crosshair": "\u2295",
    "eye": "\U0001f441",
    "maximize": "\u26f6",
    "center": "\u25ce",
    "fit": "\u2b1c",
    "info": "\u2139",
    "warning": "\u26a0",
    "check": "\u2713",
    "x": "\u2715",
    "search": "\U0001f50e",
    "replace": "\u21c4",
    "copy": "\u2398",
    "image": "\U0001f5bc",
    "film": "\U0001f3ac",
    "palette": "\U0001f3a8",
    "plus": "+",
    "minus": "\u2212",
    "arrow_up": "\u2191",
    "arrow_down": "\u2193",
    "tree_view": "\U0001f332",
    "list_view": "\u2630",
    "align_left": "\u21e4",
    "align_h": "\u2194",
    "align_right": "\u21e5",
    "align_top": "\u2912",
    "align_v": "\u2195",
    "align_bottom": "\u2913",
    "undo": "\u21b6",
    "redo": "\u21b7",
    "keyboard": "\u2328",
}


class ThemeIconProvider:
    """Provides QIcon objects coloured for the active theme family.

    Icons come from three open-source font families:
      - **Codicons** (VS Code) — MIT — for Clean themes
      - **Material Design Icons 6** — Apache 2.0 — for Material themes
      - **Phosphor** — MIT — for Fluent themes
    """

    def __init__(self) -> None:
        self._family = "clean"
        self._color = "#333333"
        self._icon_size = QSize(16, 16)

    def set_theme(self, family: str, icon_color: str) -> None:
        """Update the active theme family and icon colour."""
        self._family = family
        self._color = icon_color

    @property
    def family(self) -> str:
        """The currently active icon family."""
        return self._family

    @property
    def color(self) -> str:
        """The current icon colour hex string."""
        return self._color

    def icon(self, key: str) -> QIcon:
        """Return a QIcon for the given icon key, themed to current family."""
        if not _HAS_QTA:
            return QIcon()
        names = _ICON_NAMES.get(key)
        if not names:
            return QIcon()
        idx = _FAMILY_PREFIX_IDX.get(self._family, 0)
        name = names[idx]
        try:
            return qta.icon(name, color=self._color)
        except Exception:
            try:
                return qta.icon(names[0], color=self._color)
            except Exception:
                return QIcon()

    def fallback_text(self, key: str) -> str:
        """Unicode fallback when qtawesome is unavailable."""
        return _ICON_FALLBACK.get(key, "")


# Global icon provider instance
icons = ThemeIconProvider()


# ═══════════════════════════════════════════════════════════════════════════
# Widget Arrow / Indicator Icon Generation
# ═══════════════════════════════════════════════════════════════════════════

_ARROW_NAMES: dict[str, tuple[str, str, str]] = {
    "arrow-up": ("msc.chevron-up", "mdi6.chevron-up", "ph.caret-up"),
    "arrow-down": ("msc.chevron-down", "mdi6.chevron-down", "ph.caret-down"),
    "branch-closed": ("msc.chevron-right", "mdi6.chevron-right", "ph.caret-right"),
    "branch-open": ("msc.chevron-down", "mdi6.chevron-down", "ph.caret-down"),
}

_arrow_icon_dir: str | None = None


def _generate_widget_arrows(color: str, family: str, branch_color: str = "") -> str:
    """Generate arrow/indicator PNGs for QSS and return the directory path.

    Args:
        color: Colour for spinbox/combo arrows.
        family: Icon family name.
        branch_color: Colour for tree branch indicators.  Falls back to
            *color* when empty.

    Returns forward-slash path suitable for QSS ``image: url(...)`` usage.
    """
    global _arrow_icon_dir
    if not _HAS_QTA:
        return ""
    # Always create a new directory so Qt doesn't serve cached images
    # from a stale URL after a theme/accent change.
    _arrow_icon_dir = tempfile.mkdtemp(prefix="tatgf_arrows_")

    if not branch_color:
        branch_color = color

    idx = _FAMILY_PREFIX_IDX.get(family, 0)
    for name, fonts in _ARROW_NAMES.items():
        c = branch_color if name.startswith("branch-") else color
        icon_obj = qta.icon(fonts[idx], color=c)
        pixmap = icon_obj.pixmap(QSize(16, 16))
        pixmap.save(os.path.join(_arrow_icon_dir, f"{name}.png"))

    # Fluent checkbox checkmark (white on accent background)
    _generate_checkmark_png(_arrow_icon_dir)

    return _arrow_icon_dir.replace("\\", "/")


def _generate_checkmark_png(directory: str, *, size: int = 18) -> None:
    """Generate a white checkmark PNG for Fluent checkbox checked state."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor("#FFFFFF"))
    pen.setWidthF(1.75)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.drawPolyline(
        [
            QPointF(size * 0.22, size * 0.52),
            QPointF(size * 0.42, size * 0.72),
            QPointF(size * 0.78, size * 0.30),
        ]
    )
    painter.end()
    pixmap.save(os.path.join(directory, "checkmark.png"))


def _build_arrow_qss(arrow_dir: str, *, include_branches: bool = True) -> str:
    """QSS overrides for spinbox/combo arrows and tree branch indicators.

    Args:
        arrow_dir: Forward-slash path to the generated arrow PNGs.
        include_branches: Whether to include tree branch indicator rules.
            Set to False for themes that manage branch icons themselves
            (e.g. qt-material).
    """
    if not arrow_dir:
        return ""
    qss = f"""
/* ── Generated arrow/indicator overrides ── */
QComboBox::down-arrow {{
    image: url({arrow_dir}/arrow-down.png);
    width: 10px; height: 10px;
    border: none;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({arrow_dir}/arrow-up.png);
    width: 10px; height: 10px;
    border: none;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({arrow_dir}/arrow-down.png);
    width: 10px; height: 10px;
    border: none;
}}
"""
    if include_branches:
        qss += f"""
QTreeView::branch:has-children:!has-siblings:closed,
QTreeView::branch:closed:has-children:has-siblings,
QTreeWidget::branch:has-children:!has-siblings:closed,
QTreeWidget::branch:closed:has-children:has-siblings {{
    image: url({arrow_dir}/branch-closed.png);
    width: 12px; height: 12px;
}}
QTreeView::branch:open:has-children:!has-siblings,
QTreeView::branch:open:has-children:has-siblings,
QTreeWidget::branch:open:has-children:!has-siblings,
QTreeWidget::branch:open:has-children:has-siblings {{
    image: url({arrow_dir}/branch-open.png);
    width: 12px; height: 12px;
}}
"""
    return qss


def _build_fluent_checkbox_qss(arrow_dir: str) -> str:
    """QSS overlay adding the checkmark image to Fluent checkbox indicators."""
    if not arrow_dir:
        return ""
    return f"""
/* ── Fluent checkbox checkmark overlay ── */
QCheckBox::indicator:checked,
QGroupBox::indicator:checked {{
    image: url({arrow_dir}/checkmark.png);
}}
QCheckBox::indicator:checked:disabled,
QGroupBox::indicator:checked:disabled {{
    image: url({arrow_dir}/checkmark.png);
}}
"""


# ═══════════════════════════════════════════════════════════════════════════
# ElidedLabel — Long-text overflow helper
# ═══════════════════════════════════════════════════════════════════════════


class ElidedLabel(QLabel):
    """QLabel that elides text with ellipsis and shows full text as tooltip."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = text
        self.setToolTip(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumWidth(30)

    def set_full_text(self, text: str) -> None:
        """Update the displayed text with elision."""
        self._full_text = text
        self.setToolTip(text)
        self._update_elided()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elided()

    def _update_elided(self) -> None:
        metrics = self.fontMetrics()
        elided = metrics.elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, self.width() - 4
        )
        super().setText(elided)


# ═══════════════════════════════════════════════════════════════════════════
# Theme Font Families
# ═══════════════════════════════════════════════════════════════════════════

THEME_FONTS: dict[str, tuple[str, ...]] = {
    "clean": ("Inter", "Segoe UI", "Helvetica Neue", "sans-serif"),
    "material": ("Roboto", "Noto Sans", "Segoe UI", "sans-serif"),
    "fluent": ("Segoe UI Variable", "Segoe UI", "Helvetica Neue", "sans-serif"),
}


# ═══════════════════════════════════════════════════════════════════════════
# qt-material Accent Mapping
# ═══════════════════════════════════════════════════════════════════════════

_QTM_ACCENT_MAP: dict[str, str] = {
    "default": "purple",
    "blue": "blue",
    "purple": "purple",
    "green": "lightgreen",
    "red": "red",
    "orange": "orange",
    "pink": "pink",
    "teal": "teal",
}


# ═══════════════════════════════════════════════════════════════════════════
# Accent Colour Presets
# ═══════════════════════════════════════════════════════════════════════════

ACCENT_PRESETS: dict[str, dict | None] = {
    "default": None,
    "blue": {
        "light": ("#0078D4", "#006CBE", "#FFFFFF"),
        "dark": ("#60CDFF", "#4DB8E8", "#003A5C"),
    },
    "purple": {
        "light": ("#6750A4", "#553B8A", "#FFFFFF"),
        "dark": ("#D0BCFF", "#B69DF8", "#381E72"),
    },
    "green": {
        "light": ("#107C10", "#0E6B0E", "#FFFFFF"),
        "dark": ("#6CCB5F", "#5AB850", "#003D00"),
    },
    "red": {
        "light": ("#D13438", "#B52E31", "#FFFFFF"),
        "dark": ("#FF99A4", "#E88690", "#5C1519"),
    },
    "orange": {
        "light": ("#F7630C", "#D45508", "#000000"),
        "dark": ("#FFA86B", "#ED9457", "#3D1500"),
    },
    "pink": {
        "light": ("#E3008C", "#C10078", "#FFFFFF"),
        "dark": ("#FF8AC4", "#E878B0", "#4A0034"),
    },
    "teal": {
        "light": ("#038387", "#026E72", "#FFFFFF"),
        "dark": ("#4FD1C5", "#3DBCB0", "#003B38"),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Theme Labels (for menus)
# ═══════════════════════════════════════════════════════════════════════════

THEME_LABELS: dict[str, str] = {
    "clean_light": "Clean Light",
    "clean_dark": "Clean Dark",
    "clean_amoled": "Clean AMOLED",
    "material_light": "Material Light",
    "material_dark": "Material Dark",
    "material_amoled": "Material AMOLED",
    "fluent_light": "Fluent Light",
    "fluent_dark": "Fluent Dark",
    "fluent_amoled": "Fluent AMOLED",
}

THEME_LABELS_REV = {v: k for k, v in THEME_LABELS.items()}


# ═══════════════════════════════════════════════════════════════════════════
# Font Menu Options
# ═══════════════════════════════════════════════════════════════════════════

FONT_OPTIONS: list[tuple[str | None, str]] = [
    (None, "Theme Default"),
    ("Inter", "Inter"),
    ("Roboto", "Roboto"),
    ("Segoe UI", "Segoe UI"),
    ("Segoe UI Variable", "Segoe UI Variable"),
    ("Open Sans", "Open Sans"),
    ("Noto Sans", "Noto Sans"),
    ("Consolas", "Monospace (Consolas)"),
]


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _hex_to_rgb(hex_color: str) -> str:
    """Convert ``#RRGGBB`` to ``R, G, B`` for use in QSS ``rgba()``."""
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"


def wrap_in_scroll_area(widget: QWidget) -> QScrollArea:
    """Wrap a widget inside a frameless, resizable QScrollArea."""
    sa = QScrollArea()
    sa.setWidget(widget)
    sa.setWidgetResizable(True)
    sa.setFrameShape(QFrame.Shape.NoFrame)
    return sa


def make_icon_button(
    icon_key: str, text: str, *, tooltip: str | None = None, primary: bool = False
) -> QPushButton:
    """Create a QPushButton with a decoupled icon — translations safe.

    The ``iconKey`` property is stored on the button so that
    :func:`refresh_icons` can re-apply the correct icon after a theme
    change.
    """
    btn = QPushButton(text)
    btn.setProperty("iconKey", icon_key)
    if _HAS_QTA:
        btn.setIcon(icons.icon(icon_key))
        btn.setIconSize(QSize(16, 16))
    else:
        btn.setText(f"{icons.fallback_text(icon_key)}  {text}")
    btn.setToolTip(tooltip or text)
    btn.setMinimumWidth(0)
    if primary:
        btn.setProperty("cssClass", "primary")
        btn.setMinimumHeight(32)
    return btn


def make_primary_button(text: str) -> QPushButton:
    """Create a primary-styled QPushButton (accent background, bold)."""
    btn = QPushButton(text)
    btn.setProperty("cssClass", "primary")
    btn.setMinimumHeight(32)
    return btn


def make_heading(text: str) -> QLabel:
    """Create a heading-styled QLabel."""
    lbl = QLabel(text)
    lbl.setProperty("cssClass", "heading")
    return lbl


def make_secondary_label(text: str) -> QLabel:
    """Create a secondary/muted QLabel."""
    lbl = QLabel(text)
    lbl.setProperty("cssClass", "secondary")
    lbl.setWordWrap(True)
    return lbl


def make_path_label(text: str) -> QLabel:
    """Create a label styled for file/directory paths."""
    lbl = QLabel(text)
    lbl.setProperty("cssClass", "path")
    lbl.setWordWrap(True)
    lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return lbl


def make_shortcut_label(text: str) -> QLabel:
    """Create a small, muted label for keyboard shortcut hints."""
    lbl = QLabel(text)
    lbl.setProperty("cssClass", "shortcut-hint")
    lbl.setWordWrap(True)
    return lbl


# ═══════════════════════════════════════════════════════════════════════════
# QSS Templates
# ═══════════════════════════════════════════════════════════════════════════

_RESET_QSS = """
* {{
    font-size: 13px;
}}
QLabel {{
    background-color: transparent;
    border: none;
    padding: 0px;
    color: {text};
}}
QGroupBox QLabel {{
    background-color: transparent;
    border: none;
    color: {text};
}}
QLabel[cssClass="heading"] {{
    font-size: 15px;
    font-weight: 600;
    color: {text};
}}
QLabel[cssClass="secondary"] {{
    color: {text_secondary};
    font-size: 12px;
}}
QLabel[cssClass="path"] {{
    color: {text_secondary};
    font-size: 12px;
    padding: 2px 4px;
    border: 1px solid {border};
    border-radius: 3px;
    background-color: {input_bg};
}}
QLabel[cssClass="shortcut-hint"] {{
    color: {text_secondary};
    font-size: 11px;
    background-color: transparent;
}}
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {border};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {text_secondary};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: {border};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {text_secondary};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QCheckBox {{
    spacing: 6px;
    background-color: transparent;
    color: {text};
}}
QGroupBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border};
    border-radius: 3px;
    background-color: transparent;
}}
QGroupBox::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
}}
QGroupBox::indicator:hover {{
    border-color: {primary};
}}
"""

_CLEAN_QSS = """
/* ── Base ── */
QMainWindow, QWidget {{
    background-color: {bg};
    color: {text};
}}

/* ── Tabs ── */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 4px;
    background-color: {surface};
    padding: 2px;
}}
QTabBar {{
    background-color: {bg};
}}
QTabBar::tab {{
    background-color: {bg};
    color: {text_secondary};
    border: 1px solid {border};
    border-bottom: none;
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{
    background-color: {surface};
    color: {text};
    border-bottom: 2px solid {primary};
}}
QTabBar::tab:hover:!selected {{
    background-color: {hover};
}}
QTabBar::tear {{ width: 0; border: none; }}

/* ── Group Boxes ── */
QGroupBox {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
    margin-top: 12px;
    padding: 12px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: {primary};
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
}}

/* ── Buttons ── */
QPushButton {{
    background-color: {btn_bg};
    color: {btn_text};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 24px;
}}
QPushButton:hover {{
    background-color: {btn_hover};
    border-color: {primary};
}}
QPushButton:pressed {{
    background-color: {btn_pressed};
}}
QPushButton:focus {{
    border-color: {primary};
}}
QPushButton:disabled {{
    background-color: {bg};
    color: {text_secondary};
    border-color: {border};
}}
QPushButton[cssClass="primary"] {{
    background-color: {primary};
    color: {primary_text};
    border: none;
    font-weight: 600;
}}
QPushButton[cssClass="primary"]:hover {{
    background-color: {primary_hover};
}}

/* ── Inputs ── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {input_bg};
    color: {text};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 22px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {primary};
}}
QComboBox::drop-down {{ border: none; padding-right: 6px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {text_secondary};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
    selection-background-color: {selection};
    selection-color: {selection_text};
    outline: 0;
    padding: 2px;
}}

/* ── SpinBox sub-controls ── */
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border: none;
    border-left: 1px solid {border};
    background-color: {btn_bg};
    border-top-right-radius: 4px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border: none;
    border-left: 1px solid {border};
    background-color: {btn_bg};
    border-bottom-right-radius: 4px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {hover};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {text_secondary};
    width: 0; height: 0;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {text_secondary};
    width: 0; height: 0;
}}

/* ── Lists / Trees ── */
QListWidget, QTreeWidget, QListView, QTreeView {{
    background-color: {input_bg};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 2px;
    outline: 0;
}}
QListWidget::item, QTreeWidget::item, QListView::item, QTreeView::item {{
    padding: 3px 4px;
    border-radius: 2px;
}}
QListWidget::item:selected, QTreeWidget::item:selected,
QListView::item:selected, QTreeView::item:selected {{
    background-color: {selection};
    color: {selection_text};
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected,
QListView::item:hover:!selected, QTreeView::item:hover:!selected {{
    background-color: {hover};
}}
QHeaderView::section {{
    background-color: {surface};
    color: {text};
    border: none;
    border-bottom: 1px solid {border};
    padding: 4px 8px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
}}

/* ── Splitter — VS Code style, thin line + grab area ── */
QSplitter {{
    background-color: transparent;
}}
QSplitter::handle {{
    background-color: {border};
}}
QSplitter::handle:horizontal {{
    width: 5px;
    border-left: 2px solid transparent;
    border-right: 2px solid transparent;
    background-color: transparent;
    image: none;
}}
QSplitter::handle:vertical {{
    height: 5px;
    border-top: 2px solid transparent;
    border-bottom: 2px solid transparent;
    background-color: transparent;
    image: none;
}}
QSplitter::handle:horizontal:hover {{
    background-color: {primary};
}}
QSplitter::handle:vertical:hover {{
    background-color: {primary};
}}

/* ── Progress ── */
QProgressBar {{
    background-color: {input_bg};
    border: 1px solid {border};
    border-radius: 4px;
    text-align: center;
    color: {text};
    min-height: 18px;
}}
QProgressBar::chunk {{
    background-color: {primary};
    border-radius: 4px;
}}

/* ── Checkbox ── */
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {border};
    border-radius: 3px;
    background-color: {input_bg};
}}
QCheckBox::indicator:hover {{
    border-color: {primary};
}}
QCheckBox::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
}}
QGroupBox QCheckBox {{
    background-color: {surface};
}}

/* ── Text Edit ── */
QTextEdit {{
    background-color: {input_bg};
    color: {text};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 4px;
}}

/* ── Menus ── */
QMenuBar {{
    background-color: {surface};
    color: {text};
    border-bottom: 1px solid {border};
    padding: 2px 0px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
    background-color: transparent;
}}
QMenuBar::item:selected {{
    background-color: {hover};
}}
QMenu {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 28px 5px 12px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {selection};
    color: {selection_text};
}}
QMenu::separator {{
    height: 1px;
    background-color: {border};
    margin: 4px 8px;
}}

/* ── Status Bar ── */
QStatusBar {{
    background-color: {surface};
    color: {text_secondary};
    border-top: 1px solid {border};
    padding: 2px 8px;
}}

/* ── Card Frame ── */
QFrame[cssClass="card"] {{
    background-color: {surface};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 8px;
}}

/* ── Tooltip ── */
QToolTip {{
    background-color: {surface};
    color: {text};
    border: 1px solid {border};
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}}

/* ── Dialog ── */
QDialog {{
    background-color: {bg};
    color: {text};
}}
"""

_MATERIAL_QSS = """
* {{ font-size: 14px; }}
QMainWindow, QWidget {{
    background-color: {bg};
    color: {text};
}}
QTabWidget::pane {{
    border: none;
    background-color: {surface};
    border-radius: 16px;
    padding: 6px;
}}
QTabBar {{ background-color: {bg}; }}
QTabBar::tab {{
    background-color: transparent;
    color: {text_secondary};
    border: none;
    border-bottom: 3px solid transparent;
    padding: 10px 24px;
    margin-right: 4px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {primary};
    border-bottom: 3px solid {primary};
    font-weight: 700;
}}
QTabBar::tab:hover:!selected {{
    color: {text};
    background-color: {hover};
    border-radius: 12px 12px 0px 0px;
}}
QTabBar::tear {{ width: 0; border: none; }}
QGroupBox {{
    background-color: {surface};
    border: none;
    border-left: 4px solid {primary};
    border-radius: 0px 16px 16px 0px;
    margin-top: 16px;
    padding: 16px 14px 12px 14px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 4px 14px;
    color: {primary};
    background-color: {bg};
    border: none;
    border-radius: 10px;
    font-weight: 700;
    left: 12px;
}}
QPushButton {{
    background-color: transparent;
    color: {primary};
    border: 2px solid {primary};
    border-radius: 12px;
    padding: 7px 18px;
    min-height: 28px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {hover};
    border-color: {primary_hover};
}}
QPushButton:pressed {{
    background-color: {btn_pressed};
    border-color: {primary};
}}
QPushButton:disabled {{
    background-color: transparent;
    color: {text_secondary};
    border-color: {border};
}}
QPushButton[cssClass="primary"] {{
    background-color: {primary};
    color: {primary_text};
    border: none;
    border-bottom: 4px solid {primary_hover};
    border-radius: 22px;
    padding: 10px 32px;
    font-weight: 700;
    min-height: 36px;
}}
QPushButton[cssClass="primary"]:hover {{
    background-color: {primary_hover};
    border-bottom-color: {accent};
}}
QPushButton[cssClass="primary"]:pressed {{
    border-bottom: 2px solid {primary_hover};
    padding-top: 12px;
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {input_bg};
    color: {text};
    border: none;
    border-bottom: 2px solid {border};
    border-radius: 12px 12px 0px 0px;
    padding: 7px 12px;
    min-height: 28px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-bottom: 3px solid {primary};
    padding-bottom: 6px;
}}
QComboBox::drop-down {{ border: none; padding-right: 8px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {text_secondary};
    margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {surface};
    border: none;
    border-radius: 12px;
    selection-background-color: {hover};
    selection-color: {primary};
    outline: 0;
    padding: 4px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    border: none;
    border-left: 1px solid {border};
    background-color: {input_bg};
    border-top-right-radius: 12px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    border: none;
    border-left: 1px solid {border};
    background-color: {input_bg};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {hover};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-bottom: 6px solid {text_secondary};
    width: 0; height: 0;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {text_secondary};
    width: 0; height: 0;
}}
QListWidget, QTreeWidget, QListView, QTreeView {{
    background-color: {surface};
    border: none;
    border-radius: 16px;
    padding: 6px;
    outline: 0;
}}
QListWidget::item, QTreeWidget::item, QListView::item, QTreeView::item {{
    padding: 7px 10px;
    border-radius: 10px;
    margin: 2px 4px;
}}
QListWidget::item:selected, QTreeWidget::item:selected,
QListView::item:selected, QTreeView::item:selected {{
    background-color: {selection};
    color: {selection_text};
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected,
QListView::item:hover:!selected, QTreeView::item:hover:!selected {{
    background-color: {hover};
}}
QHeaderView::section {{
    background-color: {surface};
    color: {primary};
    border: none;
    border-bottom: 3px solid {primary};
    padding: 8px 12px;
    font-weight: 700;
    font-size: 11px;
    text-align: left;
}}
QSplitter {{ background-color: transparent; }}
QSplitter::handle {{
    background-color: transparent;
}}
QSplitter::handle:horizontal {{ width: 4px; }}
QSplitter::handle:vertical {{ height: 4px; }}
QSplitter::handle:hover {{ background-color: {hover}; }}
QProgressBar {{
    background-color: {input_bg};
    border: none;
    border-bottom: 2px solid {border};
    border-radius: 12px;
    text-align: center;
    color: {text};
    min-height: 22px;
    font-weight: 500;
}}
QProgressBar::chunk {{
    background-color: {primary};
    border-radius: 12px;
}}
QCheckBox::indicator {{
    width: 22px;
    height: 22px;
    border: 2px solid {border};
    border-radius: 6px;
    background-color: {input_bg};
}}
QCheckBox::indicator:hover {{
    border-color: {primary};
    background-color: {hover};
}}
QCheckBox::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
}}
QGroupBox QCheckBox {{
    background-color: {surface};
}}
QTextEdit {{
    background-color: {input_bg};
    color: {text};
    border: none;
    border-bottom: 2px solid {border};
    border-radius: 12px 12px 0px 0px;
    padding: 8px;
}}
QMenuBar {{
    background-color: {surface};
    color: {text};
    border: none;
    border-bottom: 2px solid {border};
    padding: 4px 0px;
    font-weight: 500;
}}
QMenuBar::item {{
    padding: 6px 14px;
    border-radius: 10px;
    background-color: transparent;
}}
QMenuBar::item:selected {{ background-color: {hover}; }}
QMenu {{
    background-color: {surface};
    color: {text};
    border: none;
    border-radius: 16px;
    padding: 8px;
    border-bottom: 4px solid {border};
    border-right: 2px solid {border};
}}
QMenu::item {{
    padding: 8px 32px 8px 16px;
    border-radius: 10px;
    font-weight: 500;
}}
QMenu::item:selected {{ background-color: {hover}; color: {primary}; }}
QMenu::separator {{
    height: 2px;
    background-color: {border};
    margin: 6px 16px;
    border-radius: 1px;
}}
QStatusBar {{
    background-color: {surface};
    color: {text_secondary};
    border-top: 2px solid {border};
    padding: 4px 12px;
    font-weight: 500;
}}
QFrame[cssClass="card"] {{
    background-color: {surface};
    border: none;
    border-left: 4px solid {primary};
    border-radius: 0px 16px 16px 0px;
    padding: 14px;
    border-bottom: 3px solid {border};
}}
QToolTip {{
    background-color: {surface};
    color: {text};
    border: none;
    padding: 6px 12px;
    border-radius: 8px;
    font-size: 13px;
}}
QDialog {{
    background-color: {bg};
    color: {text};
}}
"""

_FLUENT_QSS = """
QMainWindow {{
    background-color: {bg};
}}
QWidget {{
    background-color: {bg};
    color: {text};
}}
QTabWidget::pane {{
    border: 1px solid rgba({border_rgb}, 0.4);
    background-color: rgba({surface_rgb}, 0.85);
    border-radius: 4px;
    padding: 2px;
}}
QTabBar::tab {{
    background-color: transparent;
    color: {text_secondary};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 7px 14px;
    margin-right: 1px;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {text};
    font-weight: 600;
    border-bottom: 2px solid {primary};
}}
QTabBar::tab:hover:!selected {{
    color: {text};
    background-color: rgba({primary_rgb}, 0.06);
}}
QTabBar::tear {{ width: 0; border: none; }}
QGroupBox {{
    background-color: rgba({surface_rgb}, 0.65);
    border: 1px solid rgba({border_rgb}, 0.25);
    border-top: 2px solid rgba({primary_rgb}, 0.25);
    border-radius: 4px;
    margin-top: 10px;
    padding: 10px 8px 6px 8px;
    font-weight: 600;
    font-size: 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    color: {text};
    background-color: transparent;
    font-size: 12px;
    font-weight: 600;
}}
QPushButton {{
    background-color: rgba({btn_bg_rgb}, 0.55);
    color: {btn_text};
    border: 1px solid rgba({border_rgb}, 0.2);
    border-bottom: 1px solid rgba({border_rgb}, 0.5);
    border-radius: 4px;
    padding: 4px 12px;
    min-height: 22px;
}}
QPushButton:hover {{
    background-color: rgba({primary_rgb}, 0.08);
    border: 1px solid rgba({primary_rgb}, 0.45);
    border-bottom: 1px solid rgba({primary_rgb}, 0.65);
}}
QPushButton:pressed {{
    background-color: rgba({primary_rgb}, 0.04);
    border-color: rgba({primary_rgb}, 0.2);
    color: {text_secondary};
}}
QPushButton:focus {{
    border: 2px solid rgba({primary_rgb}, 0.6);
}}
QPushButton:disabled {{
    background-color: rgba({border_rgb}, 0.15);
    color: {text_secondary};
    border-color: rgba({border_rgb}, 0.15);
}}
QPushButton[cssClass="primary"] {{
    background-color: {primary};
    color: {primary_text};
    border: none;
    border-bottom: 1px solid {primary_hover};
    border-radius: 4px;
    padding: 5px 16px;
    font-weight: 600;
}}
QPushButton[cssClass="primary"]:hover {{
    background-color: {primary_hover};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: rgba({input_bg_rgb}, 0.5);
    color: {text};
    border: 1px solid rgba({border_rgb}, 0.25);
    border-bottom: 2px solid rgba({border_rgb}, 0.65);
    border-radius: 4px;
    padding: 3px 8px;
    min-height: 22px;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-bottom: 2px solid {primary};
    background-color: rgba({input_bg_rgb}, 0.8);
}}
QComboBox::drop-down {{ border: none; padding-right: 6px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {text_secondary};
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: rgba({surface_rgb}, 0.95);
    border: 1px solid rgba({border_rgb}, 0.3);
    border-radius: 8px;
    selection-background-color: rgba({primary_rgb}, 0.1);
    selection-color: {text};
    outline: 0;
    padding: 4px;
}}
QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    border: none;
    border-left: 1px solid rgba({border_rgb}, 0.25);
    background-color: rgba({input_bg_rgb}, 0.3);
    border-top-right-radius: 4px;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    border: none;
    border-left: 1px solid rgba({border_rgb}, 0.25);
    background-color: rgba({input_bg_rgb}, 0.3);
    border-bottom-right-radius: 4px;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: rgba({primary_rgb}, 0.08);
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-bottom: 5px solid {text_secondary};
    width: 0; height: 0;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {text_secondary};
    width: 0; height: 0;
}}
QListWidget, QTreeWidget, QListView, QTreeView {{
    background-color: rgba({input_bg_rgb}, 0.4);
    border: 1px solid rgba({border_rgb}, 0.2);
    border-radius: 4px;
    padding: 2px;
    outline: 0;
}}
QListWidget::item, QTreeWidget::item, QListView::item, QTreeView::item {{
    padding: 3px 6px;
    border-radius: 3px;
    border: 1px solid transparent;
}}
QListWidget::item:selected, QTreeWidget::item:selected,
QListView::item:selected, QTreeView::item:selected {{
    background-color: rgba({primary_rgb}, 0.12);
    color: {text};
    border-left: 2px solid {primary};
}}
QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected,
QListView::item:hover:!selected, QTreeView::item:hover:!selected {{
    background-color: rgba({primary_rgb}, 0.04);
    border: 1px solid rgba({border_rgb}, 0.25);
}}
QHeaderView::section {{
    background-color: transparent;
    color: {text};
    border: none;
    border-bottom: 1px solid rgba({border_rgb}, 0.4);
    padding: 4px 8px;
    font-weight: 600;
    font-size: 12px;
}}
QSplitter {{ background-color: transparent; }}
QSplitter::handle {{
    background-color: transparent;
}}
QSplitter::handle:horizontal {{ width: 5px; }}
QSplitter::handle:vertical {{ height: 5px; }}
QSplitter::handle:hover {{ background-color: rgba({primary_rgb}, 0.25); }}
QProgressBar {{
    background-color: rgba({input_bg_rgb}, 0.4);
    border: 1px solid rgba({border_rgb}, 0.2);
    border-radius: 4px;
    text-align: center;
    color: {text};
    min-height: 16px;
}}
QProgressBar::chunk {{
    background-color: {primary};
    border-radius: 4px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid rgba({border_rgb}, 0.6);
    border-bottom: 1px solid rgba({border_rgb}, 0.9);
    border-radius: 4px;
    background-color: rgba({input_bg_rgb}, 0.45);
}}
QCheckBox::indicator:hover {{
    border-color: rgba({border_rgb}, 0.8);
    border-bottom-color: rgba({border_rgb}, 1.0);
    background-color: rgba({input_bg_rgb}, 0.6);
}}
QCheckBox::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
}}
QCheckBox::indicator:checked:hover {{
    background-color: {primary_hover};
    border-color: {primary_hover};
}}
QCheckBox::indicator:disabled {{
    border-color: rgba({border_rgb}, 0.25);
    background-color: rgba({input_bg_rgb}, 0.15);
}}
QCheckBox::indicator:checked:disabled {{
    background-color: rgba({border_rgb}, 0.35);
    border-color: rgba({border_rgb}, 0.35);
}}
QGroupBox::indicator {{
    width: 18px;
    height: 18px;
    border: 1px solid rgba({border_rgb}, 0.6);
    border-bottom: 1px solid rgba({border_rgb}, 0.9);
    border-radius: 4px;
    background-color: rgba({input_bg_rgb}, 0.45);
}}
QGroupBox::indicator:hover {{
    border-color: rgba({border_rgb}, 0.8);
    border-bottom-color: rgba({border_rgb}, 1.0);
    background-color: rgba({input_bg_rgb}, 0.6);
}}
QGroupBox::indicator:checked {{
    background-color: {primary};
    border-color: {primary};
}}
QGroupBox::indicator:checked:hover {{
    background-color: {primary_hover};
    border-color: {primary_hover};
}}
QGroupBox QCheckBox {{
    background-color: transparent;
}}
QGroupBox QLabel {{
    background-color: transparent;
}}
QGroupBox QComboBox {{
    background-color: rgba({input_bg_rgb}, 0.5);
}}
QGroupBox QSpinBox, QGroupBox QDoubleSpinBox {{
    background-color: rgba({input_bg_rgb}, 0.5);
}}
QTextEdit {{
    background-color: rgba({input_bg_rgb}, 0.5);
    color: {text};
    border: 1px solid rgba({border_rgb}, 0.25);
    border-radius: 4px;
    padding: 4px;
}}
QMenuBar {{
    background-color: rgba({surface_rgb}, 0.75);
    color: {text};
    border-bottom: 1px solid rgba({border_rgb}, 0.2);
    padding: 2px 0px;
}}
QMenuBar::item {{
    padding: 4px 10px;
    border-radius: 4px;
    background-color: transparent;
}}
QMenuBar::item:selected {{
    background-color: rgba({primary_rgb}, 0.08);
}}
QMenu {{
    background-color: rgba({surface_rgb}, 0.92);
    color: {text};
    border: 1px solid rgba({border_rgb}, 0.3);
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 5px 28px 5px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: rgba({primary_rgb}, 0.1);
    color: {text};
}}
QMenu::separator {{
    height: 1px;
    background-color: rgba({border_rgb}, 0.2);
    margin: 4px 8px;
}}
QStatusBar {{
    background-color: rgba({surface_rgb}, 0.65);
    color: {text_secondary};
    border-top: 1px solid rgba({border_rgb}, 0.2);
    padding: 2px 8px;
    font-size: 12px;
}}
QFrame[cssClass="card"] {{
    background-color: rgba({surface_rgb}, 0.6);
    border: 1px solid rgba({border_rgb}, 0.2);
    border-radius: 4px;
    padding: 8px;
}}
QToolTip {{
    background-color: rgba({surface_rgb}, 0.95);
    color: {text};
    border: 1px solid rgba({border_rgb}, 0.3);
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 12px;
}}
QDialog {{
    background-color: {bg};
    color: {text};
}}
"""

_MATERIAL_DARK_TEXT_FIX = """
/* Reinforce light text on Material dark/amoled to prevent stale-palette bleed */
QWidget { color: #ffffff; }
QLabel { color: #ffffff; }
QGroupBox { color: #ffffff; }
QCheckBox { color: #ffffff; }
QRadioButton { color: #ffffff; }
QPushButton { color: #ffffff; }
QToolButton { color: #ffffff; }
QComboBox { color: #ffffff; }
QComboBox QAbstractItemView { color: #ffffff; }
QComboBox::item { color: #ffffff; }
QComboBox::item:selected { color: #ffffff; }
QSpinBox { color: #ffffff; }
QDoubleSpinBox { color: #ffffff; }
QLineEdit { color: #ffffff; }
QTextEdit { color: #ffffff; }
QPlainTextEdit { color: #ffffff; }
QListWidget { color: #ffffff; }
QListView { color: #ffffff; }
QTreeWidget { color: #ffffff; }
QTreeView { color: #ffffff; }
QTableWidget { color: #ffffff; }
QTableView { color: #ffffff; }
QHeaderView::section { color: #ffffff; }
QTabBar::tab { color: rgba(255, 255, 255, 0.7); }
QTabBar::tab:selected { color: #ffffff; }
QMenuBar { color: #ffffff; }
QMenuBar::item { color: #ffffff; }
QMenu { color: #ffffff; }
QMenu::item { color: #ffffff; }
QStatusBar { color: #ffffff; }
QToolTip { color: #d4d4d4; }
"""

_MATERIAL_AMOLED_OVERLAY = """
/* Force pure black for OLED screens */
QMainWindow, QDialog, QWidget {
    background-color: #000000;
    color: #CCCCCC;
}
QTabWidget > QWidget { background-color: #050505; }
QTabWidget::pane { background-color: #050505; }
QGroupBox { background-color: #0A0A0A; color: #CCCCCC; }
QListWidget, QTreeWidget, QListView, QTreeView { background-color: #050505; color: #CCCCCC; }
QTextEdit { background-color: #050505; color: #CCCCCC; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox { background-color: #0A0A0A; color: #CCCCCC; }
QMenuBar { background-color: #000000; color: #CCCCCC; }
QMenu { background-color: #0A0A0A; color: #CCCCCC; }
QStatusBar { background-color: #000000; color: #CCCCCC; }
QToolTip { background-color: #1A1A1A; color: #CCCCCC; }
QLabel { background-color: transparent; color: #CCCCCC; }
QCheckBox { background-color: transparent; color: #CCCCCC; }
QGroupBox QCheckBox { background-color: #0A0A0A; }
QProgressBar { background-color: #0A0A0A; color: #CCCCCC; }
QSplitter { background-color: transparent; }
QScrollArea { background-color: transparent; }
QScrollArea > QWidget > QWidget { background-color: transparent; }
"""


# ═══════════════════════════════════════════════════════════════════════════
# Theme Token Dictionaries — 9 variants
# ═══════════════════════════════════════════════════════════════════════════

THEME_TOKENS: dict[str, dict[str, str]] = {
    "clean_light": {
        "bg": "#FAFAFA",
        "surface": "#FFFFFF",
        "border": "#E0E0E0",
        "text": "#333333",
        "text_secondary": "#737373",
        "primary": "#1976D2",
        "primary_hover": "#1565C0",
        "primary_text": "#FFFFFF",
        "accent": "#0D47A1",
        "btn_bg": "#F5F5F5",
        "btn_text": "#333333",
        "btn_hover": "#E8E8E8",
        "btn_pressed": "#D6D6D6",
        "input_bg": "#FFFFFF",
        "hover": "#F0F0F0",
        "selection": "#ADD6FF",
        "selection_text": "#333333",
        "error": "#D32F2F",
        "success": "#388E3C",
        "warning": "#F57C00",
    },
    "clean_dark": {
        "bg": "#1E1E1E",
        "surface": "#252526",
        "border": "#3C3C3C",
        "text": "#CCCCCC",
        "text_secondary": "#808080",
        "primary": "#569CD6",
        "primary_hover": "#4A8AC4",
        "primary_text": "#1E1E1E",
        "accent": "#9CDCFE",
        "btn_bg": "#333333",
        "btn_text": "#CCCCCC",
        "btn_hover": "#3D3D3D",
        "btn_pressed": "#505050",
        "input_bg": "#1E1E1E",
        "hover": "#2A2D2E",
        "selection": "#264F78",
        "selection_text": "#FFFFFF",
        "error": "#F48771",
        "success": "#89D185",
        "warning": "#CCA700",
    },
    "clean_amoled": {
        "bg": "#000000",
        "surface": "#0A0A0A",
        "border": "#2A2A2A",
        "text": "#E0E0E0",
        "text_secondary": "#888888",
        "primary": "#569CD6",
        "primary_hover": "#4A8AC4",
        "primary_text": "#000000",
        "accent": "#9CDCFE",
        "btn_bg": "#1A1A1A",
        "btn_text": "#E0E0E0",
        "btn_hover": "#252525",
        "btn_pressed": "#333333",
        "input_bg": "#0D0D0D",
        "hover": "#1A1A1A",
        "selection": "#264F78",
        "selection_text": "#FFFFFF",
        "error": "#F48771",
        "success": "#89D185",
        "warning": "#CCA700",
    },
    "material_light": {
        "bg": "#FEF7FF",
        "surface": "#FFFBFE",
        "border": "#CAC4D0",
        "text": "#1C1B1F",
        "text_secondary": "#49454F",
        "primary": "#6750A4",
        "primary_hover": "#553B8A",
        "primary_text": "#FFFFFF",
        "accent": "#7D5260",
        "btn_bg": "#E8DEF8",
        "btn_text": "#1C1B1F",
        "btn_hover": "#E8DEF8",
        "btn_pressed": "#D0BCFF",
        "input_bg": "#E7E0EC",
        "hover": "#F3EDF7",
        "selection": "#6750A4",
        "selection_text": "#FFFFFF",
        "error": "#B3261E",
        "success": "#386A20",
        "warning": "#7D5700",
    },
    "material_dark": {
        "bg": "#141218",
        "surface": "#1D1B20",
        "border": "#49454F",
        "text": "#E6E1E5",
        "text_secondary": "#CAC4D0",
        "primary": "#D0BCFF",
        "primary_hover": "#B69DF8",
        "primary_text": "#381E72",
        "accent": "#EFB8C8",
        "btn_bg": "#4A4458",
        "btn_text": "#E6E1E5",
        "btn_hover": "#4A4458",
        "btn_pressed": "#635B70",
        "input_bg": "#211F26",
        "hover": "#332D41",
        "selection": "#D0BCFF",
        "selection_text": "#381E72",
        "error": "#F2B8B5",
        "success": "#A8DB8F",
        "warning": "#FFB95A",
    },
    "material_amoled": {
        "bg": "#000000",
        "surface": "#0C0A12",
        "border": "#3A3540",
        "text": "#F0ECF0",
        "text_secondary": "#B8B3BD",
        "primary": "#D0BCFF",
        "primary_hover": "#B69DF8",
        "primary_text": "#381E72",
        "accent": "#EFB8C8",
        "btn_bg": "#2A2534",
        "btn_text": "#F0ECF0",
        "btn_hover": "#352F40",
        "btn_pressed": "#4A4458",
        "input_bg": "#0D0B14",
        "hover": "#1E1A28",
        "selection": "#D0BCFF",
        "selection_text": "#381E72",
        "error": "#F2B8B5",
        "success": "#A8DB8F",
        "warning": "#FFB95A",
    },
    "fluent_light": {
        "bg": "#F3F3F3",
        "surface": "#FFFFFF",
        "border": "#E5E5E5",
        "text": "#1A1A1A",
        "text_secondary": "#5C5C5C",
        "primary": "#0078D4",
        "primary_hover": "#006CBE",
        "primary_text": "#FFFFFF",
        "accent": "#005A9E",
        "btn_bg": "#FAFAFA",
        "btn_text": "#1A1A1A",
        "btn_hover": "#F0F0F0",
        "btn_pressed": "#E0E0E0",
        "input_bg": "#FFFFFF",
        "hover": "#F0F0F0",
        "selection": "#0078D4",
        "selection_text": "#FFFFFF",
        "error": "#D13438",
        "success": "#107C10",
        "warning": "#D83B01",
    },
    "fluent_dark": {
        "bg": "#202020",
        "surface": "#2B2B2B",
        "border": "#3B3B3B",
        "text": "#FFFFFF",
        "text_secondary": "#C5C5C5",
        "primary": "#60CDFF",
        "primary_hover": "#4DB8E8",
        "primary_text": "#003A5C",
        "accent": "#0078D4",
        "btn_bg": "#2D2D2D",
        "btn_text": "#FFFFFF",
        "btn_hover": "#383838",
        "btn_pressed": "#444444",
        "input_bg": "#1C1C1C",
        "hover": "#333333",
        "selection": "#0078D4",
        "selection_text": "#FFFFFF",
        "error": "#FF99A4",
        "success": "#6CCB5F",
        "warning": "#F7630C",
    },
    "fluent_amoled": {
        "bg": "#000000",
        "surface": "#0A0A0A",
        "border": "#2C2C2C",
        "text": "#FFFFFF",
        "text_secondary": "#A0A0A0",
        "primary": "#60CDFF",
        "primary_hover": "#4DB8E8",
        "primary_text": "#003A5C",
        "accent": "#0078D4",
        "btn_bg": "#1A1A1A",
        "btn_text": "#FFFFFF",
        "btn_hover": "#252525",
        "btn_pressed": "#333333",
        "input_bg": "#0D0D0D",
        "hover": "#1A1A1A",
        "selection": "#0078D4",
        "selection_text": "#FFFFFF",
        "error": "#FF99A4",
        "success": "#6CCB5F",
        "warning": "#F7630C",
    },
}

_FAMILY_QSS = {
    "clean": _CLEAN_QSS,
    "material": _MATERIAL_QSS,
    "fluent": _FLUENT_QSS,
}


# ═══════════════════════════════════════════════════════════════════════════
# QPalette Builder
# ═══════════════════════════════════════════════════════════════════════════


def _build_palette(tokens: dict[str, str]) -> QPalette:
    """Build a QPalette from theme tokens for native widget integration."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(tokens["bg"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(tokens["text"]))
    p.setColor(QPalette.ColorRole.Base, QColor(tokens["input_bg"]))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(tokens["surface"]))
    p.setColor(QPalette.ColorRole.Text, QColor(tokens["text"]))
    p.setColor(QPalette.ColorRole.Button, QColor(tokens["btn_bg"]))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(tokens["btn_text"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(tokens["primary"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(tokens["primary_text"]))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(tokens["surface"]))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor(tokens["text"]))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(tokens["text_secondary"]))
    p.setColor(QPalette.ColorRole.Link, QColor(tokens["primary"]))
    for role, key in [
        (QPalette.ColorRole.WindowText, "text_secondary"),
        (QPalette.ColorRole.Text, "text_secondary"),
        (QPalette.ColorRole.ButtonText, "text_secondary"),
    ]:
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(tokens[key]))
    return p


def _build_custom_qss(family: str, tokens: dict[str, str]) -> str:
    """Build the full QSS string for Clean or Fluent (or Material fallback)."""
    t = dict(tokens)
    for name in (
        "bg",
        "surface",
        "border",
        "primary",
        "input_bg",
        "btn_bg",
        "hover",
        "selection",
    ):
        if name in t:
            t[f"{name}_rgb"] = _hex_to_rgb(t[name])
    return (_RESET_QSS + _FAMILY_QSS[family]).format(**t)


# ═══════════════════════════════════════════════════════════════════════════
# Master Theme Application
# ═══════════════════════════════════════════════════════════════════════════


def apply_theme(
    app: QApplication,
    window: QMainWindow,
    family: str,
    variant: str,
    *,
    accent_key: str = "default",
    font_override: str = "",
) -> None:
    """Apply a complete theme to the application.

    Args:
        app: The running QApplication instance.
        window: The main window (used for icon refresh).
        family: Theme family — 'clean', 'material', or 'fluent'.
        variant: Theme variant — 'light', 'dark', or 'amoled'.
        accent_key: Accent colour preset name from :data:`ACCENT_PRESETS`.
        font_override: Font family name; empty string uses the theme default.
    """
    theme_key = f"{family}_{variant}"

    # 1. Reset to clean slate
    app.setStyle("Fusion")
    app.setStyleSheet("")
    app.setPalette(app.style().standardPalette())

    # 2. Font
    fname = font_override or THEME_FONTS[family][0]
    font = QFont(fname)
    font.setPixelSize(14 if family == "material" else 13)
    app.setFont(font)

    # 3. Determine icon colour (needed for arrow generation)
    if family == "material" and _HAS_QT_MATERIAL:
        icon_color = "#333333" if variant == "light" else "#CCCCCC"
        brightness = "light" if variant == "light" else "dark"
        preset = ACCENT_PRESETS.get(accent_key)
        accent_color = preset[brightness][0] if preset else icon_color
    else:
        tokens = dict(THEME_TOKENS[theme_key])
        preset = ACCENT_PRESETS.get(accent_key)
        if preset:
            brightness = "light" if variant == "light" else "dark"
            p, ph, pt = preset[brightness]
            tokens["primary"] = p
            tokens["primary_hover"] = ph
            tokens["primary_text"] = pt
        icon_color = tokens["text"]
        accent_color = tokens["primary"]

    # 4. Generate themed arrow icons for QSS
    is_material = family == "material" and _HAS_QT_MATERIAL
    arrow_dir = _generate_widget_arrows(icon_color, family, branch_color=accent_color)
    arrow_qss = _build_arrow_qss(arrow_dir, include_branches=not is_material)

    # 5. Apply theme
    if family == "material" and _HAS_QT_MATERIAL:
        brightness = "light" if variant == "light" else "dark"
        accent = _QTM_ACCENT_MAP.get(accent_key, "purple")
        xml_name = f"{brightness}_{accent}.xml"
        extra = {
            "density_scale": "0",
            "font_family": fname,
            "font_size": "14px",
        }
        _qt_material_apply(app, theme=xml_name, extra=extra)
        # qt-material sets its own palette but may miss some roles;
        # explicitly reinforce text colours to prevent stale light-palette
        # entries from bleeding through after a theme switch.
        if variant in ("dark", "amoled"):
            pal = app.palette()
            _light = QColor("#CCCCCC")
            _dim = QColor("#808080")
            pal.setColor(QPalette.ColorRole.WindowText, _light)
            pal.setColor(QPalette.ColorRole.Text, _light)
            pal.setColor(QPalette.ColorRole.ButtonText, _light)
            pal.setColor(QPalette.ColorRole.ToolTipText, _light)
            pal.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
            pal.setColor(QPalette.ColorRole.PlaceholderText, _dim)
            app.setPalette(pal)
        elif variant == "light":
            pal = app.palette()
            _dark = QColor("#333333")
            pal.setColor(QPalette.ColorRole.WindowText, _dark)
            pal.setColor(QPalette.ColorRole.Text, _dark)
            pal.setColor(QPalette.ColorRole.ButtonText, _dark)
            pal.setColor(QPalette.ColorRole.ToolTipText, _dark)
            pal.setColor(QPalette.ColorRole.BrightText, QColor("#000000"))
            pal.setColor(QPalette.ColorRole.PlaceholderText, QColor("#808080"))
            app.setPalette(pal)
        # Only overlay specific fixes on top of qt-material's stylesheet
        _header_fix = (
            "QHeaderView::section {" "  font-size: 11px;" "  text-align: left;" "}"
        )
        overlay = _header_fix + arrow_qss
        if variant in ("dark", "amoled"):
            overlay = _MATERIAL_DARK_TEXT_FIX + overlay
        if variant == "amoled":
            overlay = _MATERIAL_AMOLED_OVERLAY + overlay
        if overlay:
            app.setStyleSheet(app.styleSheet() + overlay)
    else:
        if family != "material":
            # Clean/Fluent: use tokens (possibly accent-overridden)
            pass
        else:
            # Material without qt-material: use fallback QSS
            tokens = dict(THEME_TOKENS[theme_key])
        palette = _build_palette(tokens)
        app.setPalette(palette)
        checkbox_qss = (
            _build_fluent_checkbox_qss(arrow_dir) if family == "fluent" else ""
        )
        qss = _build_custom_qss(family, tokens) + arrow_qss + checkbox_qss
        app.setStyleSheet(qss)

    # 6. Update icon provider and refresh all icons
    if _HAS_QTA:
        icons.set_theme(family, icon_color)
        refresh_icons(window)


def refresh_icons(window: QMainWindow) -> None:
    """Re-apply all icons on the window after a theme/family change.

    Walks all child QPushButtons and QActions that have an ``iconKey``
    property and updates their icon from the global :data:`icons` provider.
    """
    if not _HAS_QTA:
        return
    # Tab icons
    from PySide6.QtWidgets import QTabWidget

    for tab_widget in window.findChildren(QTabWidget):
        # Only refresh if tabs have icon keys stored
        for idx in range(tab_widget.count()):
            widget = tab_widget.widget(idx)
            if widget:
                key = widget.property("tabIconKey")
                if key:
                    tab_widget.setTabIcon(idx, icons.icon(key))

    # Buttons
    for widget in window.findChildren(QPushButton):
        key = widget.property("iconKey")
        if key:
            widget.setIcon(icons.icon(key))
            widget.setIconSize(QSize(16, 16))

    # Menu actions (direct QAction children of the window)
    for action in window.findChildren(QAction):
        key = action.property("iconKey")
        if key:
            action.setIcon(icons.icon(key))

    # QMenu-owned actions (may not appear in findChildren from ancestor)
    from PySide6.QtWidgets import QMenu

    for menu in window.findChildren(QMenu):
        for action in menu.actions():
            key = action.property("iconKey")
            if key:
                action.setIcon(icons.icon(key))


def get_current_tokens(
    family: str, variant: str, accent_key: str = "default"
) -> dict[str, str]:
    """Return the resolved token dict for the given theme settings.

    Useful for widgets that need to read theme colours directly.
    """
    theme_key = f"{family}_{variant}"
    tokens = dict(THEME_TOKENS.get(theme_key, THEME_TOKENS["clean_dark"]))
    preset = ACCENT_PRESETS.get(accent_key)
    if preset:
        brightness = "light" if variant == "light" else "dark"
        p, ph, pt = preset[brightness]
        tokens["primary"] = p
        tokens["primary_hover"] = ph
        tokens["primary_text"] = pt
    return tokens
