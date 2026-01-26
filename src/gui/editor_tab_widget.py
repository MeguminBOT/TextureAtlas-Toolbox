#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive alignment editor tab for animations and spritesheets."""
from __future__ import annotations

import os
import uuid
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import (
    QCoreApplication,
    QEvent,
    QObject,
    QPoint,
    QPointF,
    QRect,
    QSize,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QMenu,
)

from gui.base_tab_widget import BaseTabWidget
from utils.FNF.alignment import resolve_fnf_offset
from utils.translation_manager import translate
from utils.ui_constants import (
    Tooltips,
    ButtonLabels,
    CheckBoxLabels,
    DialogTitles,
    FileDialogTitles,
    FileFilters,
    GroupTitles,
    MenuActions,
    TabTitles,
    WindowTitles,
)

import numpy as np


try:
    from PIL import Image, ImageSequence

    PIL_AVAILABLE = True
except (
    ImportError
):  # pragma: no cover - pillow is expected to be installed with the app
    Image = None  # type: ignore
    ImageSequence = None  # type: ignore
    PIL_AVAILABLE = False

ANIMATION_ID_ROLE = Qt.ItemDataRole.UserRole + 1
FRAME_INDEX_ROLE = Qt.ItemDataRole.UserRole + 2

ORIGIN_MODE_CENTER = "center"
ORIGIN_MODE_TOP_LEFT = "top_left"
VALID_ORIGIN_MODES = {ORIGIN_MODE_CENTER, ORIGIN_MODE_TOP_LEFT}


class _TopLevelOnlyDragFilter(QObject):
    """Block drag-and-drop attempts involving child frame rows."""

    def __init__(self, tree: QTreeWidget):
        super().__init__(tree)
        self._tree = tree

    def eventFilter(self, obj, event):  # noqa: D401 - Qt API
        """Allow moves only when both source and target are top-level."""
        if obj is not self._tree:
            return False
        if event.type() in (
            QEvent.Type.DragEnter,
            QEvent.Type.DragMove,
            QEvent.Type.Drop,
        ):
            selected_items = self._tree.selectedItems()
            if any(item.parent() is not None for item in selected_items):
                event.ignore()
                return True

            if event.type() in (QEvent.Type.DragMove, QEvent.Type.Drop):
                # Guard against dropping onto a child row or stacking onto another top-level item.
                pos = (
                    event.position().toPoint()
                    if hasattr(event, "position")
                    else event.pos()
                )
                target = self._tree.itemAt(pos)
                indicator = self._tree.dropIndicatorPosition()
                if target is not None and target.parent() is not None:
                    event.ignore()
                    return True
                if (
                    indicator == QAbstractItemView.DropIndicatorPosition.OnItem
                    and target is not None
                    and target.parent() is None
                ):
                    event.ignore()
                    return True
            return False
        return False


@dataclass
class AlignmentFrame:
    """Sprite frame plus metadata tracked during manual alignment.

    Attributes:
        name (str): Unique label shown in the tree widget.
        original_key (str): Key used to look the frame up in the source data.
        pixmap (QPixmap): Rasterized frame used for display/dragging.
        duration_ms (int): Playback duration for preview loops.
        offset_x (int): User-defined horizontal shift relative to canvas origin.
        offset_y (int): User-defined vertical shift relative to canvas origin.
        metadata (dict): Free-form extras stored by importers.
    """

    name: str
    original_key: str
    pixmap: QPixmap
    duration_ms: int = 100
    offset_x: int = 0
    offset_y: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AlignmentAnimation:
    """Book-keeping bundle for all frames associated with an animation.

    Attributes capture original source info (spritesheet_name, animation_name),
    canvas sizing, default offsets, and optional Friday Night Funkin' metadata
    used during export.
    """

    display_name: str
    frames: List[AlignmentFrame]
    canvas_width: int
    canvas_height: int
    source: str = "manual"  # either "manual" or "extract"
    spritesheet_name: Optional[str] = None
    animation_name: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    default_offset: Tuple[int, int] = (0, 0)
    origin_mode: str = ORIGIN_MODE_CENTER
    fnf_raw_offsets: Optional[Dict[str, Any]] = None

    def ensure_canvas_bounds(self, respect_existing: bool = False):
        """Clamp canvas to multiples of 256 so every frame fits comfortably.

        Args:
            respect_existing (bool): When ``True`` the method only increases the
                canvas; otherwise it resets width/height to the new target.
        """
        step = 256
        max_side_limit = 4096
        required_side = step
        if self.frames:
            max_w = max(frame.pixmap.width() for frame in self.frames)
            max_h = max(frame.pixmap.height() for frame in self.frames)
            required_side = max(step, max(max_w, max_h))
        target_side = ((required_side + step - 1) // step) * step
        target_side = min(max_side_limit, target_side)

        if respect_existing:
            self.canvas_width = max(self.canvas_width, target_side)
            self.canvas_height = max(self.canvas_height, target_side)
        else:
            self.canvas_width = target_side
            self.canvas_height = target_side


class AlignmentCanvas(QWidget):
    """Interactive scene that renders a frame, ghost overlay, and guides."""

    offsetChanged = Signal(int, int)
    zoomChanged = Signal(float)

    def __init__(self):
        """Initialize drawing state, default zoom levels, and input flags."""
        super().__init__()
        self._pixmap: Optional[QPixmap] = None
        self._canvas_width = 512
        self._canvas_height = 512
        self._display_padding = 80
        self._offset_x = 0
        self._offset_y = 0
        self._dragging = False
        self._drag_origin = QPoint()
        self._start_offset = (0, 0)
        self._panning = False
        self._pan_origin = QPoint()
        self._start_view_translation = QPointF(0.0, 0.0)
        self._zoom = 1.0
        self._min_zoom = 0.25
        self._max_zoom = 5.0
        self._ghost_pixmap: Optional[QPixmap] = None
        self._ghost_opacity = 0.35
        self._ghost_offset_x = 0
        self._ghost_offset_y = 0
        self._snapping_enabled = False
        self._snap_step = 1
        self._view_translation = QPointF(0.0, 0.0)
        self._origin_mode = ORIGIN_MODE_CENTER
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(self.sizeHint())

    def sizeHint(self) -> QSize:  # noqa: D401 - Qt API
        """Suggest a QWidget size that leaves padding around the canvas."""
        return QSize(
            max(self._canvas_width + self._display_padding, 240),
            max(self._canvas_height + self._display_padding, 240),
        )

    def minimumSizeHint(self) -> QSize:  # noqa: D401 - Qt API
        """Mirror ``sizeHint`` so layouts never shrink the canvas too far."""
        return self.sizeHint()

    def set_pixmap(self, pixmap: Optional[QPixmap]):
        """Assign the sprite being edited and schedule a repaint."""
        self._pixmap = pixmap
        self.update()

    def set_canvas_size(self, width: int, height: int):
        """Resize the logical canvas while keeping view translation stable."""
        width = max(256, int(width))
        height = max(256, int(height))
        if (width, height) != (self._canvas_width, self._canvas_height):
            previous_rect = self._canvas_rect()
            self._canvas_width = width
            self._canvas_height = height
            if self._origin_mode == ORIGIN_MODE_CENTER:
                self.recenter_view()
            else:
                new_rect = self._canvas_rect()
                delta_x = previous_rect.left() - new_rect.left()
                delta_y = previous_rect.top() - new_rect.top()
                if delta_x or delta_y:
                    # Preserve the visual top-left anchor so offsets remain consistent.
                    self._view_translation = QPointF(
                        self._view_translation.x() + delta_x,
                        self._view_translation.y() + delta_y,
                    )
            hint = self.sizeHint()
            self.setMinimumSize(hint)
            self.updateGeometry()
            self.update()

    def set_origin_mode(self, mode: str):
        """Switch between centered and top-left origin behaviors."""
        if mode not in VALID_ORIGIN_MODES:
            mode = ORIGIN_MODE_CENTER
        if mode == self._origin_mode:
            return
        self._origin_mode = mode
        self.update()

    def set_offsets(self, offset_x: int, offset_y: int, notify: bool = False):
        """Update frame offsets, snapping if enabled, and optionally signal.

        Args:
            offset_x (int): Horizontal offset relative to origin.
            offset_y (int): Vertical offset relative to origin.
            notify (bool): Emit ``offsetChanged`` when ``True``.
        """
        offset_x = self._apply_snapping(int(offset_x))
        offset_y = self._apply_snapping(int(offset_y))
        changed = (offset_x, offset_y) != (self._offset_x, self._offset_y)
        self._offset_x = offset_x
        self._offset_y = offset_y
        if changed and notify:
            self.offsetChanged.emit(self._offset_x, self._offset_y)
        if changed:
            self.update()

    def offsets(self) -> Tuple[int, int]:
        """Return the current (x, y) offsets."""
        return self._offset_x, self._offset_y

    def set_ghost_pixmap(
        self,
        pixmap: Optional[QPixmap],
        opacity: float = 0.35,
        offset_x: int = 0,
        offset_y: int = 0,
    ):
        """Configure the optional translucent ghost overlay.

        Args:
            pixmap (QPixmap | None): Ghost sprite to show or ``None``.
            opacity (float): Fade factor clamped between roughly 0 and 1.
            offset_x (int): Horizontal shift relative to origin.
            offset_y (int): Vertical shift relative to origin.
        """
        self._ghost_pixmap = pixmap
        self._ghost_opacity = max(0.05, min(0.95, opacity))
        self._ghost_offset_x = int(offset_x)
        self._ghost_offset_y = int(offset_y)
        self.update()

    def configure_snapping(self, enabled: bool, snap_step: int):
        """Toggle snapping and reapply it to the current offsets."""
        self._snapping_enabled = enabled
        self._snap_step = max(1, int(snap_step))
        # Re-apply snapping to current offsets to keep UI consistent
        self.set_offsets(self._offset_x, self._offset_y)

    def reset_zoom(self):
        """Recentre the viewport and restore a 1:1 zoom."""
        self.recenter_view()
        self.set_zoom(1.0)

    def set_zoom(self, zoom: float, anchor: Optional[QPointF] = None):
        """Apply a new zoom value, optionally keeping the cursor anchored."""
        zoom = max(self._min_zoom, min(self._max_zoom, zoom))
        if abs(zoom - self._zoom) < 0.001:
            return
        old_zoom = self._zoom
        self._zoom = zoom
        if anchor is not None and old_zoom > 0:
            self._apply_zoom_anchor(anchor, old_zoom, zoom)
        self.zoomChanged.emit(self._zoom)
        self.update()

    def zoom(self) -> float:
        """Expose the active zoom multiplier for other widgets."""
        return self._zoom

    def paintEvent(self, event):  # noqa: D401 - Qt API
        """Paint checkerboard, guides, ghost overlay, and the active sprite."""
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(28, 28, 28))

        painter.save()
        painter.translate(self._view_translation)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(self._zoom, self._zoom)
        painter.translate(-self.width() / 2, -self.height() / 2)

        canvas_rect = self._canvas_rect()
        self._paint_checkerboard(painter, canvas_rect)
        self._paint_crosshair(painter, canvas_rect)

        if self._ghost_pixmap and not self._ghost_pixmap.isNull():
            anchor_x, anchor_y = self._origin_anchor(canvas_rect, self._ghost_pixmap)
            ghost_x = anchor_x + self._ghost_offset_x
            ghost_y = anchor_y + self._ghost_offset_y
            painter.setOpacity(self._ghost_opacity)
            painter.drawPixmap(ghost_x, ghost_y, self._ghost_pixmap)
            painter.setOpacity(1.0)

        if self._pixmap and not self._pixmap.isNull():
            anchor_x, anchor_y = self._origin_anchor(canvas_rect, self._pixmap)
            target_x = anchor_x + self._offset_x
            target_y = anchor_y + self._offset_y
            painter.drawPixmap(target_x, target_y, self._pixmap)

        painter.restore()

    def _canvas_rect(self) -> QRect:
        """Return the rectangle describing the virtual canvas within widget."""
        left = (self.width() - self._canvas_width) // 2
        top = (self.height() - self._canvas_height) // 2
        return QRect(left, top, self._canvas_width, self._canvas_height)

    def _origin_anchor(
        self, canvas_rect: QRect, pixmap: Optional[QPixmap]
    ) -> Tuple[int, int]:
        """Compute the pixel position where (0, 0) should start for a pixmap."""
        if self._origin_mode == ORIGIN_MODE_TOP_LEFT:
            return canvas_rect.left(), canvas_rect.top()
        width = pixmap.width() if pixmap else 0
        height = pixmap.height() if pixmap else 0
        base_x = canvas_rect.center().x() - width // 2
        base_y = canvas_rect.center().y() - height // 2
        return base_x, base_y

    def _paint_checkerboard(self, painter: QPainter, rect):
        """Fill the canvas with alternating squares to show transparency."""
        square = 16
        dark = QColor(60, 60, 60)
        light = QColor(80, 80, 80)
        for x in range(rect.left(), rect.right() + square, square):
            for y in range(rect.top(), rect.bottom() + square, square):
                color = dark if ((x // square + y // square) % 2 == 0) else light
                painter.fillRect(x, y, square, square, color)

    def _paint_crosshair(self, painter: QPainter, rect):
        """Draw either axes through the center or lines along the top-left."""
        painter.setPen(QColor(0, 196, 255, 140))
        if self._origin_mode == ORIGIN_MODE_TOP_LEFT:
            painter.drawLine(rect.left(), rect.top(), rect.right(), rect.top())
            painter.drawLine(rect.left(), rect.top(), rect.left(), rect.bottom())
        else:
            painter.drawLine(
                rect.center().x(), rect.top(), rect.center().x(), rect.bottom()
            )
            painter.drawLine(
                rect.left(), rect.center().y(), rect.right(), rect.center().y()
            )

    def mousePressEvent(self, event):  # noqa: D401 - Qt API
        """Start dragging sprites or panning depending on click target."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._is_point_on_sprite(event.position()):
                self._dragging = True
                self._drag_origin = event.position().toPoint()
                self._start_offset = (self._offset_x, self._offset_y)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            else:
                self._panning = True
                self._pan_origin = event.position().toPoint()
                self._start_view_translation = QPointF(self._view_translation)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: D401 - Qt API
        """Update offsets or pan translation while the mouse is moving."""
        if self._dragging:
            delta = event.position().toPoint() - self._drag_origin
            self.set_offsets(
                self._start_offset[0] + delta.x(),
                self._start_offset[1] + delta.y(),
                notify=True,
            )
            event.accept()
        elif self._panning:
            delta = event.position().toPoint() - self._pan_origin
            self._view_translation = QPointF(
                self._start_view_translation.x() + delta.x(),
                self._start_view_translation.y() + delta.y(),
            )
            self.update()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: D401 - Qt API
        """Stop dragging/panning once the left mouse button is released."""
        if event.button() == Qt.MouseButton.LeftButton:
            if self._dragging:
                self._dragging = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
                return
            if self._panning:
                self._panning = False
                self.setCursor(Qt.CursorShape.ArrowCursor)
                event.accept()
                return
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event):  # noqa: D401 - Qt API
        """Move the sprite using arrow keys with optional shift multiplier."""
        step = 5 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        handled = True
        if event.key() == Qt.Key.Key_Left:
            self.set_offsets(self._offset_x - step, self._offset_y, notify=True)
        elif event.key() == Qt.Key.Key_Right:
            self.set_offsets(self._offset_x + step, self._offset_y, notify=True)
        elif event.key() == Qt.Key.Key_Up:
            self.set_offsets(self._offset_x, self._offset_y - step, notify=True)
        elif event.key() == Qt.Key.Key_Down:
            self.set_offsets(self._offset_x, self._offset_y + step, notify=True)
        else:
            handled = False
        if not handled:
            super().keyPressEvent(event)

    def wheelEvent(self, event):  # noqa: D401 - Qt API
        """Zoom when Ctrl+wheel is used; otherwise defer to scroll area."""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta == 0:
                return
            factor = 1.1 if delta > 0 else 0.9
            self.set_zoom(self._zoom * factor, anchor=event.position())
            event.accept()
        else:
            event.ignore()

    def _apply_snapping(self, value: int) -> int:
        """Round ``value`` to the configured snap grid when enabled."""
        if not self._snapping_enabled or self._snap_step <= 1:
            return value
        snapped = int(round(value / self._snap_step) * self._snap_step)
        return snapped

    def recenter_view(self):
        """Reset manual panning offsets to keep canvas perfectly centered."""
        self._view_translation = QPointF(0.0, 0.0)
        self.update()

    def fit_canvas_to_viewport(self, viewport_size: QSize):
        """Compute a zoom that fits the entire canvas inside the viewport."""
        if viewport_size.width() <= 0 or viewport_size.height() <= 0:
            return
        padded_width = self._canvas_width + self._display_padding
        padded_height = self._canvas_height + self._display_padding
        scale_x = viewport_size.width() / max(1, padded_width)
        scale_y = viewport_size.height() / max(1, padded_height)
        target_zoom = min(scale_x, scale_y)
        target_zoom = max(self._min_zoom, min(self._max_zoom, target_zoom))
        self.recenter_view()
        self.set_zoom(target_zoom)

    def _apply_zoom_anchor(self, anchor: QPointF, old_zoom: float, new_zoom: float):
        """Adjust view translation so the anchor point remains under cursor."""
        if old_zoom <= 0:
            return
        ratio = new_zoom / old_zoom
        center = QPointF(self.width() / 2, self.height() / 2)
        delta = anchor - center
        self._view_translation = QPointF(
            (1 - ratio) * delta.x() + ratio * self._view_translation.x(),
            (1 - ratio) * delta.y() + ratio * self._view_translation.y(),
        )

    def _map_to_canvas(self, point: QPointF) -> QPointF:
        """Convert a widget-space point into canvas space while considering zoom."""
        mapped = QPointF(point)
        mapped -= self._view_translation
        center = QPointF(self.width() / 2, self.height() / 2)
        mapped -= center
        if self._zoom != 0:
            mapped /= self._zoom
        mapped += center
        return mapped

    def _is_point_on_sprite(self, point: QPointF) -> bool:
        """Return ``True`` if the widget-space point intersects the sprite."""
        if not self._pixmap or self._pixmap.isNull():
            return False
        canvas_point = self._map_to_canvas(point)
        canvas_rect = self._canvas_rect()
        anchor_x, anchor_y = self._origin_anchor(canvas_rect, self._pixmap)
        sprite_rect = QRect(
            anchor_x, anchor_y, self._pixmap.width(), self._pixmap.height()
        )
        return sprite_rect.contains(int(canvas_point.x()), int(canvas_point.y()))


class CanvasDetachWindow(QDialog):
    """Auxiliary dialog that hosts the canvas while it is undocked."""

    closed = Signal()

    def closeEvent(self, event):  # noqa: D401 - Qt API
        """Emit ``closed`` so the parent knows the canvas should reattach."""
        self.closed.emit()
        super().closeEvent(event)


class EditorTabWidget(BaseTabWidget):
    """High-level controller for the alignment editor tab UI and logic."""

    tr = translate

    def __init__(self, parent_app, use_existing_ui: bool = False):
        """Instantiate the tab, build or reuse UI, and prime state caches.

        Args:
            parent_app: Main window object that provides config and signals.
            use_existing_ui (bool): When ``True`` attach to widgets created by
                Qt Designer instead of building them programmatically.
        """
        super().__init__(parent_app, use_existing_ui)
        self._init_state()
        self._setup_ui()
        self._configure_animation_tree_drag_reorder()
        self._connect_signals()
        self._update_zoom_label(self.canvas.zoom())
        self._initialize_origin_mode()
        self._reset_multi_drag_baselines()

    def _init_state(self):
        """Initialize instance state before UI setup."""
        self._animations: Dict[str, AlignmentAnimation] = {}
        self._current_animation_id: Optional[str] = None
        self._current_frame_index: int = -1
        self._root_alignment_mode: bool = False
        self._root_display_offset: Tuple[int, int] = (0, 0)
        self._origin_mode: str = ORIGIN_MODE_CENTER
        self._updating_controls = False
        self._detached_window: Optional[CanvasDetachWindow] = None
        self._animation_items: Dict[str, QTreeWidgetItem] = {}
        self._tree_reorder_filter: Optional[QObject] = None
        self._multi_drag_baselines: Optional[Dict[str, Tuple[int, int]]] = None
        self._default_status_text = self.tr(
            "Drag the frame, use arrow keys for fine adjustments, or type offsets manually."
        )

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------
    def _setup_with_existing_ui(self):
        """Bind to widgets exported by the main window's QtDesigner layout.

        Raises:
            RuntimeError: If ``parent_app.ui`` is not available.
        """
        ui = getattr(self.parent_app, "ui", None)
        if ui is None:
            raise RuntimeError("Editor UI is not available on the parent application")

        self.animation_tree = ui.animation_tree
        self.animation_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.animation_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.load_files_button = ui.load_files_button
        self.remove_animation_button = ui.remove_animation_button
        self.combine_button = ui.combine_button

        self.canvas_holder = ui.canvas_holder
        self.canvas_scroll = ui.canvas_scroll
        placeholder = getattr(ui, "canvas_scroll_placeholder", None)
        if placeholder is not None:
            placeholder.setParent(None)
        self.canvas = AlignmentCanvas()
        self.canvas_scroll.setWidget(self.canvas)
        self.canvas_scroll.setWidgetResizable(True)

        self.zoom_out_button = ui.zoom_out_button
        self.zoom_in_button = ui.zoom_in_button
        self.reset_zoom_button = ui.reset_zoom_button
        self.zoom_100_button = ui.zoom_100_button
        self.zoom_50_button = ui.zoom_50_button
        self.center_view_button = ui.center_view_button
        self.fit_canvas_button = ui.fit_canvas_button
        self.zoom_label = ui.zoom_label
        self.detach_canvas_button = ui.detach_canvas_button

        self.status_label = ui.editor_status_label

        self.offset_x_spin = ui.offset_x_spin
        self.offset_y_spin = ui.offset_y_spin
        self.reset_offset_button = ui.reset_offset_button
        self.apply_all_button = ui.apply_all_button
        self.canvas_width_spin = ui.canvas_width_spin
        self.canvas_height_spin = ui.canvas_height_spin
        self.save_overrides_button = ui.save_overrides_button
        self.export_composite_button = ui.export_composite_button

        self.ghost_checkbox = ui.ghost_checkbox
        self.ghost_frame_combo = ui.ghost_frame_combo
        self.snap_checkbox = ui.snap_checkbox
        self.snap_step_spin = ui.snap_step_spin
        self.origin_mode_combo = ui.origin_mode_combo
        self.status_label.setText(self._default_status_text)
        self._configure_origin_selector()

    def _build_ui(self):
        """Create the editor UI programmatically when no prebuilt UI exists."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        layout.addWidget(splitter, 1)

        # Left column: animation + frame lists
        lists_widget = QWidget()
        lists_widget.setMinimumWidth(280)
        lists_widget.setMaximumWidth(420)
        lists_widget.setSizePolicy(
            QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        )
        lists_layout = QVBoxLayout(lists_widget)
        lists_layout.setSpacing(8)

        anim_label = QLabel(self.tr("Animations & Frames"))
        lists_layout.addWidget(anim_label)

        self.animation_tree = QTreeWidget()
        self.animation_tree.setHeaderHidden(True)
        self.animation_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.animation_tree.setSizePolicy(
            QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        )
        self.animation_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        lists_layout.addWidget(self.animation_tree, 1)

        button_row = QHBoxLayout()
        self.load_files_button = QPushButton(self.tr(ButtonLabels.LOAD_ANIMATION_FILES))
        self.load_files_button.setToolTip(self.tr(Tooltips.LOAD_ANIMATIONS))
        button_row.addWidget(self.load_files_button)
        self.remove_animation_button = QPushButton(self.tr(ButtonLabels.REMOVE))
        button_row.addWidget(self.remove_animation_button)
        self.combine_button = QPushButton(self.tr(ButtonLabels.COMBINE_SELECTED))
        self.combine_button.setToolTip(self.tr(Tooltips.COMBINE_SELECTED))
        self.combine_button.setEnabled(False)
        button_row.addWidget(self.combine_button)
        lists_layout.addLayout(button_row)

        splitter.addWidget(lists_widget)

        # Right column: canvas + controls
        editor_splitter = QSplitter(Qt.Orientation.Horizontal)
        editor_splitter.setChildrenCollapsible(False)

        canvas_panel = QWidget()
        canvas_panel.setSizePolicy(
            QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        )
        canvas_column = QVBoxLayout(canvas_panel)
        canvas_column.setSpacing(8)
        canvas_column.setContentsMargins(0, 0, 0, 0)
        self.canvas = AlignmentCanvas()
        self.canvas_scroll = QScrollArea()
        self.canvas_scroll.setWidget(self.canvas)
        self.canvas_scroll.setWidgetResizable(True)
        self.canvas_scroll.setSizePolicy(
            QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        )
        self.canvas_holder = QWidget()
        self.canvas_holder.setLayout(QVBoxLayout())
        self.canvas_holder.layout().setContentsMargins(0, 0, 0, 0)
        self.canvas_holder.layout().addWidget(self.canvas_scroll)
        self.canvas_holder.setSizePolicy(
            QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        )
        canvas_column.addWidget(self.canvas_holder, 1)

        canvas_toolbar = QHBoxLayout()
        self.zoom_out_button = QPushButton("-")
        self.zoom_out_button.setToolTip(self.tr(Tooltips.ZOOM_OUT))
        self.zoom_in_button = QPushButton("+")
        self.zoom_in_button.setToolTip(self.tr(Tooltips.ZOOM_IN))
        self.reset_zoom_button = QPushButton(self.tr(ButtonLabels.RESET_ZOOM))
        self.zoom_100_button = QPushButton("100%")
        self.zoom_100_button.setToolTip(self.tr(Tooltips.ZOOM_100))
        self.zoom_50_button = QPushButton("50%")
        self.zoom_50_button.setToolTip(self.tr(Tooltips.ZOOM_50))
        self.center_view_button = QPushButton(self.tr(ButtonLabels.CENTER_VIEW))
        self.center_view_button.setToolTip(self.tr(Tooltips.CENTER_VIEW))
        self.fit_canvas_button = QPushButton(self.tr(ButtonLabels.FIT_CANVAS))
        self.fit_canvas_button.setToolTip(self.tr(Tooltips.FIT_CANVAS))
        self.zoom_label = QLabel("100%")
        self.detach_canvas_button = QPushButton(self.tr(ButtonLabels.DETACH_CANVAS))
        canvas_toolbar.addWidget(self.zoom_out_button)
        canvas_toolbar.addWidget(self.zoom_in_button)
        canvas_toolbar.addWidget(self.reset_zoom_button)
        canvas_toolbar.addWidget(self.zoom_100_button)
        canvas_toolbar.addWidget(self.zoom_50_button)
        canvas_toolbar.addWidget(self.center_view_button)
        canvas_toolbar.addWidget(self.fit_canvas_button)
        canvas_toolbar.addWidget(self.zoom_label)
        canvas_toolbar.addStretch()
        canvas_toolbar.addWidget(self.detach_canvas_button)
        canvas_column.addLayout(canvas_toolbar)

        controls_group = QGroupBox(self.tr(GroupTitles.ALIGNMENT_CONTROLS))
        controls_layout = QFormLayout(controls_group)

        self.offset_x_spin = QSpinBox()
        self.offset_x_spin.setRange(-4096, 4096)
        controls_layout.addRow(self.tr("Frame offset X"), self.offset_x_spin)

        self.offset_y_spin = QSpinBox()
        self.offset_y_spin.setRange(-4096, 4096)
        controls_layout.addRow(self.tr("Frame offset Y"), self.offset_y_spin)

        control_buttons = QHBoxLayout()
        self.reset_offset_button = QPushButton(self.tr(ButtonLabels.RESET_TO_DEFAULT))
        control_buttons.addWidget(self.reset_offset_button)
        self.apply_all_button = QPushButton(self.tr(ButtonLabels.APPLY_TO_ALL_FRAMES))
        control_buttons.addWidget(self.apply_all_button)
        controls_layout.addRow(control_buttons)

        self.canvas_width_spin = QSpinBox()
        self.canvas_width_spin.setRange(8, 4096)
        controls_layout.addRow(self.tr("Canvas width"), self.canvas_width_spin)

        self.canvas_height_spin = QSpinBox()
        self.canvas_height_spin.setRange(8, 4096)
        controls_layout.addRow(self.tr("Canvas height"), self.canvas_height_spin)

        self.save_overrides_button = QPushButton(
            self.tr(ButtonLabels.SAVE_ALIGNMENT_EXTRACT)
        )
        self.save_overrides_button.setEnabled(False)
        controls_layout.addRow(self.save_overrides_button)

        self.export_composite_button = QPushButton(
            self.tr(ButtonLabels.EXPORT_COMPOSITE_SPRITES)
        )
        self.export_composite_button.setEnabled(False)
        controls_layout.addRow(self.export_composite_button)

        display_group = QGroupBox(self.tr(GroupTitles.DISPLAY_SNAPPING))
        display_layout = QFormLayout(display_group)

        self.origin_mode_combo = QComboBox()
        display_layout.addRow(self.tr("Canvas origin"), self.origin_mode_combo)
        self._configure_origin_selector()

        ghost_widget = QWidget()
        ghost_row = QHBoxLayout(ghost_widget)
        ghost_row.setContentsMargins(0, 0, 0, 0)
        self.ghost_checkbox = QCheckBox(self.tr(CheckBoxLabels.ENABLE))
        self.ghost_frame_combo = QComboBox()
        self.ghost_frame_combo.setEnabled(False)
        ghost_row.addWidget(self.ghost_checkbox)
        ghost_row.addWidget(self.ghost_frame_combo, 1)
        display_layout.addRow(self.tr("Ghost frame"), ghost_widget)

        snap_widget = QWidget()
        snap_row = QHBoxLayout(snap_widget)
        snap_row.setContentsMargins(0, 0, 0, 0)
        self.snap_checkbox = QCheckBox(self.tr(CheckBoxLabels.ENABLE))
        self.snap_step_spin = QSpinBox()
        self.snap_step_spin.setRange(1, 256)
        self.snap_step_spin.setValue(1)
        self.snap_step_spin.setEnabled(False)
        snap_row.addWidget(self.snap_checkbox)
        snap_row.addWidget(QLabel(self.tr("px")))
        snap_row.addWidget(self.snap_step_spin)
        display_layout.addRow(self.tr("Snapping"), snap_widget)

        self.status_label = QLabel(self._default_status_text)
        canvas_column.addWidget(self.status_label)

        controls_panel = QWidget()
        controls_panel.setSizePolicy(
            QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        )
        controls_panel.setMinimumWidth(280)
        controls_panel.setMaximumWidth(320)
        controls_panel_layout = QVBoxLayout(controls_panel)
        controls_panel_layout.setContentsMargins(0, 0, 0, 0)
        controls_panel_layout.setSpacing(8)
        controls_panel_layout.addWidget(controls_group)
        controls_panel_layout.addWidget(display_group)
        controls_panel_layout.addStretch()
        editor_splitter.addWidget(canvas_panel)
        editor_splitter.addWidget(controls_panel)
        editor_splitter.setStretchFactor(0, 1)
        editor_splitter.setStretchFactor(1, 0)
        editor_splitter.setSizes([960, 320])

        splitter.addWidget(editor_splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 960])

    def _configure_animation_tree_drag_reorder(self):
        """Enable drag-to-reorder for animation groups while blocking frame moves."""
        tree = getattr(self, "animation_tree", None)
        if tree is None:
            return

        tree.setDragEnabled(True)
        tree.setAcceptDrops(True)
        tree.setDropIndicatorShown(True)
        tree.setDefaultDropAction(Qt.DropAction.MoveAction)
        tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

        if self._tree_reorder_filter is None:
            self._tree_reorder_filter = _TopLevelOnlyDragFilter(tree)
            tree.installEventFilter(self._tree_reorder_filter)

    def _connect_signals(self):
        """Wire widget signals to handler methods for the editor workflow."""
        self.animation_tree.currentItemChanged.connect(self._on_tree_current_changed)
        self.animation_tree.itemSelectionChanged.connect(
            self._update_combine_button_state
        )
        self.animation_tree.customContextMenuRequested.connect(
            self._show_tree_context_menu
        )
        self.load_files_button.clicked.connect(self._load_manual_files)
        self.remove_animation_button.clicked.connect(self._remove_selected_animation)
        self.combine_button.clicked.connect(self._combine_selected_animations)
        self.offset_x_spin.valueChanged.connect(self._on_manual_offset_changed)
        self.offset_y_spin.valueChanged.connect(self._on_manual_offset_changed)
        self.apply_all_button.clicked.connect(self._apply_offsets_to_all_frames)
        self.reset_offset_button.clicked.connect(self._reset_frame_offset)
        self.canvas_width_spin.valueChanged.connect(self._on_canvas_size_changed)
        self.canvas_height_spin.valueChanged.connect(self._on_canvas_size_changed)
        self.save_overrides_button.clicked.connect(self._save_alignment_to_settings)
        self.export_composite_button.clicked.connect(self._export_composite_to_sprites)
        self.canvas.offsetChanged.connect(self._on_canvas_dragged)
        self.canvas.zoomChanged.connect(self._update_zoom_label)
        self.zoom_in_button.clicked.connect(
            lambda: self.canvas.set_zoom(self.canvas.zoom() * 1.1)
        )
        self.zoom_out_button.clicked.connect(
            lambda: self.canvas.set_zoom(self.canvas.zoom() * 0.9)
        )
        self.reset_zoom_button.clicked.connect(self.canvas.reset_zoom)
        self.zoom_100_button.clicked.connect(lambda: self.canvas.set_zoom(1.0))
        self.zoom_50_button.clicked.connect(lambda: self.canvas.set_zoom(0.5))
        self.center_view_button.clicked.connect(self._center_canvas_view)
        self.fit_canvas_button.clicked.connect(self._fit_canvas_to_viewport)
        self.ghost_checkbox.toggled.connect(self._on_ghost_toggled)
        self.ghost_frame_combo.currentIndexChanged.connect(self._on_ghost_frame_changed)
        self.snap_checkbox.toggled.connect(self._on_snap_toggled)
        self.snap_step_spin.valueChanged.connect(self._on_snap_step_changed)
        self.origin_mode_combo.currentIndexChanged.connect(self._on_origin_mode_changed)
        self.detach_canvas_button.clicked.connect(self._toggle_canvas_detach)

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------
    def _configure_origin_selector(self):
        """Populate the origin combo box with supported modes and tooltips."""
        combo = getattr(self, "origin_mode_combo", None)
        if combo is None:
            return
        previous_block_state = combo.blockSignals(True)
        combo.clear()
        combo.addItem(self.tr("Centered"), ORIGIN_MODE_CENTER)
        combo.addItem(self.tr("Top-left (FlxSprite)"), ORIGIN_MODE_TOP_LEFT)
        combo.setToolTip(
            self.tr(
                "Choose how the editor canvas positions frames when offsets are zero."
            )
        )
        combo.blockSignals(previous_block_state)

    def _initialize_origin_mode(self):
        """Read persisted origin mode and apply it without re-saving."""
        initial_mode = self._load_origin_mode_from_config()
        self._apply_origin_mode(initial_mode, persist=False, reason="ui-init")

    def _load_origin_mode_from_config(self) -> str:
        """Fetch saved origin preference from ``AppConfig`` if available."""
        config = getattr(self.parent_app, "app_config", None)
        if config is None:
            return ORIGIN_MODE_CENTER
        settings: Dict[str, Any] = {}
        getter = getattr(config, "get_editor_settings", None)
        if callable(getter):
            try:
                settings = getter()
            except Exception:
                settings = {}
        elif hasattr(config, "get"):
            raw = config.get("editor_settings", {})
            if isinstance(raw, dict):
                settings = dict(raw)
        mode = settings.get("origin_mode") if isinstance(settings, dict) else None
        if isinstance(mode, str) and mode in VALID_ORIGIN_MODES:
            return mode
        return ORIGIN_MODE_CENTER

    def _save_origin_mode_to_config(self, mode: str):
        """Persist the origin setting back into the app config object."""
        config = getattr(self.parent_app, "app_config", None)
        if config is None:
            return
        setter = getattr(config, "set_editor_settings", None)
        if callable(setter):
            setter(origin_mode=mode)
            return
        if hasattr(config, "get") and hasattr(config, "set"):
            existing = config.get("editor_settings", {})
            if not isinstance(existing, dict):
                existing = {}
            existing = dict(existing)
            existing["origin_mode"] = mode
            config.set("editor_settings", existing)

    def _apply_origin_mode(self, mode: Optional[str], *, persist: bool, reason: str):
        """Update UI/canvas state for a new origin mode and optionally save."""
        target_mode = (
            mode
            if isinstance(mode, str) and mode in VALID_ORIGIN_MODES
            else ORIGIN_MODE_CENTER
        )
        if target_mode == self._origin_mode and reason != "fnf-import":
            return
        previous_state = self._origin_mode
        self._origin_mode = target_mode
        combo = getattr(self, "origin_mode_combo", None)
        if combo is not None:
            previous_flag = self._updating_controls
            self._updating_controls = True
            try:
                index = combo.findData(target_mode)
                if index >= 0 and combo.currentIndex() != index:
                    combo.setCurrentIndex(index)
            finally:
                self._updating_controls = previous_flag
        self.canvas.set_origin_mode(target_mode)
        current_animation = None
        if self._current_animation_id is not None:
            current_animation = self._animations.get(self._current_animation_id)
        if current_animation is not None:
            current_animation.origin_mode = target_mode
        if persist:
            self._save_origin_mode_to_config(target_mode)
        if reason == "fnf-import" and previous_state != target_mode:
            self.status_label.setText(
                self.tr(
                    "FlxSprite origin mode enabled so imported offsets match the preview."
                )
            )

    def _on_origin_mode_changed(self):
        """React to user combo-box changes and propagate to state/config."""
        if self._updating_controls:
            return
        combo = getattr(self, "origin_mode_combo", None)
        if combo is None:
            return
        mode = combo.currentData()
        self._apply_origin_mode(mode, persist=True, reason="manual")

    def enable_flxsprite_origin_mode(self):
        """Force the FlxSprite-compatible mode when FNF imports require it."""
        self._apply_origin_mode(ORIGIN_MODE_TOP_LEFT, persist=True, reason="fnf-import")

    def _update_combine_button_state(self):
        """Enable the combine button only when 2+ top-level animations selected."""
        selected_top_levels = [
            item
            for item in self.animation_tree.selectedItems()
            if item.parent() is None
        ]
        self.combine_button.setEnabled(len(selected_top_levels) >= 2)
        # Changing selection invalidates any cached multi-drag baselines.
        self._multi_drag_baselines = None

    def _show_tree_context_menu(self, pos):
        """Show contextual actions for removing animations or frames."""
        if not self.animation_tree:
            return
        if not self.animation_tree.selectedItems():
            item = self.animation_tree.itemAt(pos)
            if item:
                self.animation_tree.setCurrentItem(item)

        selected_items = self.animation_tree.selectedItems()
        has_animation = any(item.parent() is None for item in selected_items)
        has_frame = any(item.parent() is not None for item in selected_items)
        if not (has_animation or has_frame):
            return

        menu = QMenu(self)
        if has_animation:
            remove_anim_action = menu.addAction(self.tr(MenuActions.REMOVE_ANIMATIONS))
            remove_anim_action.triggered.connect(self._remove_selected_animation)
        if has_frame:
            remove_frames_action = menu.addAction(self.tr(MenuActions.REMOVE_FRAMES))
            remove_frames_action.triggered.connect(self._remove_selected_frames)
        menu.exec(self.animation_tree.viewport().mapToGlobal(pos))

    def _update_zoom_label(self, zoom: float):
        """Reflect the canvas zoom level in the toolbar label."""
        percent = int(round(zoom * 100))
        self.zoom_label.setText(self.tr("Zoom: {value}%").format(value=percent))

    def _is_composite_animation(self, animation: Optional[AlignmentAnimation]) -> bool:
        """Return ``True`` if the animation was generated by combining entries."""
        if animation is None:
            return False
        metadata = animation.metadata or {}
        return bool(metadata.get("source_animation_ids"))

    def _get_composite_translation(
        self, animation: Optional[AlignmentAnimation]
    ) -> Tuple[int, int]:
        """Look up the translation applied to a composite animation, if any."""
        if not self._is_composite_animation(animation):
            return 0, 0
        metadata = animation.metadata or {}
        raw_x = metadata.get("composite_translate_x", 0)
        raw_y = metadata.get("composite_translate_y", 0)
        try:
            translate_x = int(raw_x)
        except (TypeError, ValueError):
            translate_x = 0
        try:
            translate_y = int(raw_y)
        except (TypeError, ValueError):
            translate_y = 0
        return translate_x, translate_y

    def _set_composite_translation(
        self, animation: AlignmentAnimation, translate_x: int, translate_y: int
    ):
        """Store translation offsets inside the animation metadata dict."""
        if animation.metadata is None:
            animation.metadata = {}
        animation.metadata["composite_translate_x"] = str(int(translate_x))
        animation.metadata["composite_translate_y"] = str(int(translate_y))

    def _calculate_display_offset(
        self, animation: AlignmentAnimation, offset_x: int, offset_y: int
    ) -> Tuple[int, int]:
        """Apply composite translation before passing offsets to the canvas."""
        translate_x, translate_y = self._get_composite_translation(animation)
        return offset_x + translate_x, offset_y + translate_y

    def _current_reference_frame(
        self, animation: AlignmentAnimation
    ) -> Optional[AlignmentFrame]:
        """Return the frame referenced by the tree selection, fallback to first."""
        if 0 <= self._current_frame_index < len(animation.frames):
            return animation.frames[self._current_frame_index]
        if animation.frames:
            return animation.frames[0]
        return None

    def _reference_offset_for_composite(
        self,
        animation: AlignmentAnimation,
        reference_frame: Optional[AlignmentFrame] = None,
    ) -> Tuple[int, int]:
        """Determine the base offsets used for calculating composite translation."""
        if reference_frame is not None:
            return reference_frame.offset_x, reference_frame.offset_y
        if animation.frames:
            frame = animation.frames[0]
            return frame.offset_x, frame.offset_y
        return animation.default_offset

    def _apply_composite_translation(
        self,
        animation: AlignmentAnimation,
        target_offset_x: int,
        target_offset_y: int,
        reference_frame: Optional[AlignmentFrame] = None,
    ) -> bool:
        """Update metadata translation so the reference frame lands on target offsets."""
        if not self._is_composite_animation(animation):
            return False
        base_x, base_y = self._reference_offset_for_composite(
            animation, reference_frame
        )
        translate_x = target_offset_x - base_x
        translate_y = target_offset_y - base_y
        self._set_composite_translation(animation, translate_x, translate_y)
        if self.ghost_checkbox.isChecked():
            self._apply_ghost_overlay()
        return True

    def _refresh_ghost_options(self):
        """Rebuild the ghost-frame combo after animations change."""
        current_data = self.ghost_frame_combo.currentData()
        self.ghost_frame_combo.blockSignals(True)
        self.ghost_frame_combo.clear()
        for animation_id, animation in self._animations.items():
            for idx, frame in enumerate(animation.frames):
                label = f"{animation.display_name} - {frame.name} ({frame.pixmap.width()}x{frame.pixmap.height()})"
                self.ghost_frame_combo.addItem(label, (animation_id, idx))
        if current_data is not None:
            for i in range(self.ghost_frame_combo.count()):
                if self.ghost_frame_combo.itemData(i) == current_data:
                    self.ghost_frame_combo.setCurrentIndex(i)
                    break
        self.ghost_frame_combo.blockSignals(False)

        has_frames = self.ghost_frame_combo.count() > 0
        self.ghost_checkbox.blockSignals(True)
        if not has_frames:
            self.ghost_checkbox.setChecked(False)
        self.ghost_checkbox.setEnabled(has_frames)
        self.ghost_checkbox.blockSignals(False)
        self.ghost_frame_combo.setEnabled(
            has_frames and self.ghost_checkbox.isChecked()
        )
        if has_frames and self.ghost_checkbox.isChecked():
            self._apply_ghost_overlay()
        else:
            self.canvas.set_ghost_pixmap(None)

    def _apply_ghost_overlay(self):
        """Apply or clear the ghost overlay based on the combo selection."""
        if not self.ghost_checkbox.isChecked():
            self.canvas.set_ghost_pixmap(None)
            return
        data = self.ghost_frame_combo.currentData()
        if data is None:
            self.canvas.set_ghost_pixmap(None)
            return
        try:
            animation_id, index = data
        except (TypeError, ValueError):
            self.canvas.set_ghost_pixmap(None)
            return
        animation = self._animations.get(animation_id)
        if animation is None or index < 0 or index >= len(animation.frames):
            self.canvas.set_ghost_pixmap(None)
            return
        ghost_frame = animation.frames[index]
        display_x, display_y = self._calculate_display_offset(
            animation, ghost_frame.offset_x, ghost_frame.offset_y
        )
        self.canvas.set_ghost_pixmap(
            ghost_frame.pixmap,
            offset_x=display_x,
            offset_y=display_y,
        )

    def _refresh_ghost_if_frame_changed(self, frame_index: int):
        """Reapply ghost overlay if the selected frame is also being edited."""
        if not self.ghost_checkbox.isChecked():
            return
        data = self.ghost_frame_combo.currentData()
        if data is None:
            return
        try:
            animation_id, selected_index = data
        except (TypeError, ValueError):
            return
        if animation_id == self._current_animation_id and selected_index == frame_index:
            self._apply_ghost_overlay()

    def _on_ghost_toggled(self, checked: bool):
        """Enable/disable the ghost controls and update the overlay state."""
        self.ghost_frame_combo.setEnabled(
            checked and self.ghost_frame_combo.count() > 0
        )
        self._apply_ghost_overlay()

    def _on_ghost_frame_changed(self):
        """Reapply the overlay when the user picks a new ghost frame."""
        if self.ghost_checkbox.isChecked():
            self._apply_ghost_overlay()

    def _on_snap_toggled(self, checked: bool):
        """Toggle snap-step spin box and forward the state to the canvas."""
        self.snap_step_spin.setEnabled(checked)
        self.canvas.configure_snapping(checked, self.snap_step_spin.value())

    def _on_snap_step_changed(self, value: int):
        """Update snap resolution without changing the enable checkbox."""
        self.canvas.configure_snapping(self.snap_checkbox.isChecked(), value)

    def _center_canvas_view(self):
        """Reset panning so the canvas origin is centered in the viewport."""
        self.canvas.recenter_view()
        self.canvas.update()

    def _fit_canvas_to_viewport(self):
        """Scale the canvas so it fits inside the scroll area viewport."""
        viewport_size = self.canvas_scroll.viewport().size()
        self.canvas.fit_canvas_to_viewport(viewport_size)

    def _toggle_canvas_detach(self):
        """Detach the canvas into its own dialog or reattach if already detached."""
        if self._detached_window:
            self._detached_window.close()
            return

        self._detached_window = CanvasDetachWindow(self)
        self._detached_window.setWindowTitle(self.tr(WindowTitles.ALIGNMENT_CANVAS))
        dialog_layout = QVBoxLayout(self._detached_window)
        dialog_layout.setContentsMargins(6, 6, 6, 6)
        if self.canvas_holder.layout():
            self.canvas_holder.layout().removeWidget(self.canvas_scroll)
        self.canvas_scroll.setParent(self._detached_window)
        dialog_layout.addWidget(self.canvas_scroll)
        self._detached_window.closed.connect(self._reattach_canvas)
        self._detached_window.resize(
            self.canvas.sizeHint().width() + 120, self.canvas.sizeHint().height() + 120
        )
        self._detached_window.show()
        self.detach_canvas_button.setText(self.tr(ButtonLabels.REATTACH_CANVAS))

    def _reattach_canvas(self):
        """Return the canvas scroll area back into the main layout."""
        if not self._detached_window:
            return
        dialog = self._detached_window
        self._detached_window = None
        if dialog.layout():
            dialog.layout().removeWidget(self.canvas_scroll)
        self.canvas_scroll.setParent(self.canvas_holder)
        holder_layout = self.canvas_holder.layout()
        if holder_layout is not None:
            holder_layout.addWidget(self.canvas_scroll)
        self.canvas_scroll.show()
        if dialog:
            dialog.deleteLater()
        self.detach_canvas_button.setText(self.tr(ButtonLabels.DETACH_CANVAS))

    # ------------------------------------------------------------------
    # Animation loading helpers
    # ------------------------------------------------------------------
    def _load_manual_files(self):
        """Open a file dialog and register animations from user-chosen files."""
        if not PIL_AVAILABLE:
            QMessageBox.warning(
                self,
                self.tr(DialogTitles.MISSING_DEPENDENCY),
                self.tr("Pillow is required to load animations."),
            )
            return

        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr(FileDialogTitles.SELECT_ANIMATION_FILES),
            "",
            self.tr(FileFilters.ANIMATION_FILES),
        )
        for path in paths:
            animation = self._build_animation_from_file(path)
            if animation:
                self._register_animation(animation)

    def _build_animation_from_file(
        self, file_path: str
    ) -> Optional[AlignmentAnimation]:
        """Convert a GIF/WebP/PNG/APNG file into an ``AlignmentAnimation``."""
        if not file_path:
            return None

        try:
            with Image.open(file_path) as img:
                frames: List[AlignmentFrame] = []
                duration = int(img.info.get("duration", 100))
                for idx, frame in enumerate(ImageSequence.Iterator(img)):
                    frame = frame.convert("RGBA")
                    pixmap = self._pil_to_pixmap(frame)
                    frame_name = f"{os.path.basename(file_path)}#frame_{idx:04d}"
                    frames.append(
                        AlignmentFrame(
                            name=self.tr("Frame {index}").format(index=idx + 1),
                            original_key=frame_name,
                            pixmap=pixmap,
                            duration_ms=duration,
                        )
                    )

            if not frames:
                QMessageBox.warning(
                    self,
                    self.tr(DialogTitles.LOAD_FAILED),
                    self.tr("{file} did not contain any frames.").format(
                        file=os.path.basename(file_path)
                    ),
                )
                return None

            max_w = max(frame.pixmap.width() for frame in frames)
            max_h = max(frame.pixmap.height() for frame in frames)
            animation = AlignmentAnimation(
                display_name=os.path.basename(file_path),
                frames=frames,
                canvas_width=max_w,
                canvas_height=max_h,
                source="manual",
                metadata={"path": file_path},
            )
            animation.ensure_canvas_bounds()
            return animation
        except Exception as exc:
            QMessageBox.warning(
                self,
                self.tr(DialogTitles.LOAD_FAILED),
                self.tr("Could not load {file}: {error}").format(
                    file=os.path.basename(file_path), error=str(exc)
                ),
            )
            return None

    def add_animation_from_extractor(
        self,
        spritesheet_name: str,
        animation_name: str,
        spritesheet_path: str,
        metadata_path: Optional[str],
        spritemap_info: Optional[dict] = None,
        spritemap_target: Optional[dict] = None,
    ):
        """Public entry point used by the extract tab to open an animation."""
        animation = self._build_animation_from_spritesheet(
            spritesheet_name,
            animation_name,
            spritesheet_path,
            metadata_path,
            spritemap_info,
            spritemap_target,
        )
        if animation:
            self._register_animation(animation)
            self.status_label.setText(
                self.tr("Loaded {animation} from {sheet}.").format(
                    animation=animation_name, sheet=spritesheet_name
                )
            )
            self._focus_latest_animation()
        else:
            QMessageBox.warning(
                self,
                self.tr(TabTitles.EDITOR),
                self.tr(
                    "Could not load animation '{animation}' from '{sheet}'."
                ).format(animation=animation_name, sheet=spritesheet_name),
            )

    def _build_animation_from_spritesheet(
        self,
        spritesheet_name: str,
        animation_name: str,
        spritesheet_path: str,
        metadata_path: Optional[str],
        spritemap_info: Optional[dict],
        spritemap_target: Optional[dict],
    ) -> Optional[AlignmentAnimation]:
        """Assemble an animation from atlas metadata or spritemap exports."""
        try:
            frames: List[AlignmentFrame] = []
            frame_duration = 42  # Default 42ms (~24fps)
            if hasattr(self.parent_app, "settings_manager"):
                settings = self.parent_app.settings_manager.get_settings(
                    spritesheet_name, f"{spritesheet_name}/{animation_name}"
                )
                # Support both legacy 'fps' and new 'duration' keys
                if "duration" in settings:
                    frame_duration = settings.get("duration", 42)
                elif "fps" in settings:
                    fps = settings.get("fps", 24)
                    frame_duration = int(round(1000 / max(1, fps)))

            if spritemap_info:
                from core.extractor.spritemap import AdobeSpritemapRenderer

                target = spritemap_target or animation_name
                animation_json = spritemap_info.get("animation_json")
                spritemap_json = spritemap_info.get("spritemap_json")
                if not (animation_json and spritemap_json):
                    raise ValueError("Spritemap metadata is incomplete.")
                renderer = AdobeSpritemapRenderer(
                    animation_json,
                    spritemap_json,
                    spritesheet_path,
                    filter_single_frame=True,
                )
                raw_frames = renderer.render_animation(target)
            else:
                if not metadata_path:
                    raise ValueError("The selected spritesheet does not have metadata.")
                from core.extractor.atlas_processor import AtlasProcessor
                from core.extractor.sprite_processor import SpriteProcessor

                atlas_processor = AtlasProcessor(spritesheet_path, metadata_path)
                if metadata_path.endswith(".xml"):
                    animation_sprites = atlas_processor.parse_xml_for_preview(
                        animation_name
                    )
                elif metadata_path.endswith(".txt"):
                    animation_sprites = atlas_processor.parse_txt_for_preview(
                        animation_name
                    )
                else:
                    animation_sprites = []

                if not animation_sprites:
                    return None

                sprite_processor = SpriteProcessor(
                    atlas_processor.atlas, animation_sprites
                )
                processed = sprite_processor.process_specific_animation(animation_name)
                raw_frames = processed.get(animation_name, [])

            if not raw_frames:
                return None

            for idx, frame_entry in enumerate(raw_frames):
                frame_name, pil_image, _meta = frame_entry
                pil_image = self._ensure_pil_image(pil_image)
                frame_metadata = self._extract_frame_metadata(_meta)
                pixmap = self._pil_to_pixmap(pil_image)
                frames.append(
                    AlignmentFrame(
                        name=frame_name,
                        original_key=frame_name,
                        pixmap=pixmap,
                        duration_ms=frame_duration,
                        metadata=frame_metadata,
                    )
                )

            max_w = max(frame.pixmap.width() for frame in frames)
            max_h = max(frame.pixmap.height() for frame in frames)
            animation = AlignmentAnimation(
                display_name=f"{spritesheet_name}/{animation_name}",
                frames=frames,
                canvas_width=max_w,
                canvas_height=max_h,
                source="extract",
                spritesheet_name=spritesheet_name,
                animation_name=animation_name,
                metadata={
                    "spritesheet_path": spritesheet_path,
                    "metadata_path": metadata_path or "",
                },
            )
            animation.ensure_canvas_bounds()

            overrides = {}
            if hasattr(self.parent_app, "settings_manager"):
                settings = self.parent_app.settings_manager.get_settings(
                    spritesheet_name, f"{spritesheet_name}/{animation_name}"
                )
                overrides = settings.get("alignment_overrides", {})
            if overrides:
                self._apply_alignment_overrides(animation, overrides)

            return animation
        except Exception as exc:
            print(
                f"[EditorTabWidget] Failed to build animation {animation_name}: {exc}"
            )
            return None

    # ------------------------------------------------------------------
    # Animation registration / selection
    # ------------------------------------------------------------------
    def _register_animation(self, animation: AlignmentAnimation) -> str:
        """Assign an ID, add the animation to the tree, and select it."""
        animation_id = uuid.uuid4().hex
        self._animations[animation_id] = animation
        item = QTreeWidgetItem([animation.display_name])
        item.setData(0, ANIMATION_ID_ROLE, animation_id)
        item.setExpanded(True)
        self.animation_tree.addTopLevelItem(item)
        self._animation_items[animation_id] = item
        self._populate_frame_items(item, animation_id, animation)
        target = item.child(0) if item.childCount() > 0 else item
        self.animation_tree.setCurrentItem(target)
        self.animation_tree.scrollToItem(item)
        self._update_combine_button_state()
        self._refresh_ghost_options()
        return animation_id

    def _populate_frame_items(
        self,
        animation_item: QTreeWidgetItem,
        animation_id: str,
        animation: AlignmentAnimation,
    ):
        """Fill the tree item with child entries representing each frame."""
        while animation_item.childCount():
            animation_item.removeChild(animation_item.child(0))
        for idx, frame in enumerate(animation.frames):
            label = f"{frame.name}  ({frame.pixmap.width()}x{frame.pixmap.height()})"
            child = QTreeWidgetItem([label])
            child.setData(0, ANIMATION_ID_ROLE, animation_id)
            child.setData(0, FRAME_INDEX_ROLE, idx)
            animation_item.addChild(child)

    def _focus_latest_animation(self):
        """Scroll to and select the most recently added animation item."""
        count = self.animation_tree.topLevelItemCount()
        if count <= 0:
            return
        item = self.animation_tree.topLevelItem(count - 1)
        target = item.child(0) if item.childCount() > 0 else item
        self.animation_tree.setCurrentItem(target)
        self.animation_tree.scrollToItem(item)

    def _remove_selected_animation(self):
        """Delete highlighted animations and reset state if necessary."""
        selected_items = [
            item
            for item in self.animation_tree.selectedItems()
            if item.parent() is None
        ]
        if not selected_items:
            current_item = self.animation_tree.currentItem()
            if not current_item:
                return
            selected_items = [
                current_item if current_item.parent() is None else current_item.parent()
            ]

        for animation_item in selected_items:
            if animation_item is None:
                continue
            animation_id = animation_item.data(0, ANIMATION_ID_ROLE)
            if animation_id in self._animations:
                del self._animations[animation_id]
            self._animation_items.pop(animation_id, None)
            index = self.animation_tree.indexOfTopLevelItem(animation_item)
            if index >= 0:
                self.animation_tree.takeTopLevelItem(index)
            if animation_id == self._current_animation_id:
                self._current_animation_id = None
                self._current_frame_index = -1
                self.canvas.set_pixmap(None)
        self.save_overrides_button.setEnabled(False)
        self.export_composite_button.setEnabled(False)
        self._update_combine_button_state()
        self._refresh_ghost_options()

    def _combine_selected_animations(self):
        """Build a composite animation entry from the selected ones."""
        selected_items = [
            item
            for item in self.animation_tree.selectedItems()
            if item.parent() is None
        ]
        if len(selected_items) < 2:
            QMessageBox.information(
                self,
                self.tr(DialogTitles.NEED_MORE_ANIMATIONS),
                self.tr("Select at least two animations to build a composite entry."),
            )
            return

        combined_frames: List[AlignmentFrame] = []
        composite_sources: List[str] = []
        source_animation_ids: List[str] = []
        source_animation_names: Dict[str, str] = {}
        max_frame_width = 0
        max_frame_height = 0
        base_sheet_name: Optional[str] = None
        base_spritesheet_path: Optional[str] = None
        base_metadata_path: Optional[str] = None
        export_info_confident = True

        for item in selected_items:
            animation_id = item.data(0, ANIMATION_ID_ROLE)
            animation = self._animations.get(animation_id)
            if not animation:
                continue
            composite_sources.append(animation.display_name)
            if animation_id not in source_animation_ids:
                source_animation_ids.append(animation_id)
                name_hint = animation.animation_name or animation.display_name
                if name_hint:
                    source_animation_names[animation_id] = name_hint

            if animation.source == "extract" and animation.spritesheet_name:
                candidate_sheet = animation.spritesheet_name
                candidate_meta = (animation.metadata or {}).get("metadata_path")
                candidate_sheet_path = (animation.metadata or {}).get(
                    "spritesheet_path"
                )
                if base_sheet_name is None:
                    base_sheet_name = candidate_sheet
                    base_metadata_path = candidate_meta
                    base_spritesheet_path = candidate_sheet_path
                elif base_sheet_name != candidate_sheet:
                    export_info_confident = False
            for index, frame in enumerate(animation.frames):
                max_frame_width = max(max_frame_width, frame.pixmap.width())
                max_frame_height = max(max_frame_height, frame.pixmap.height())
                combined_frames.append(
                    AlignmentFrame(
                        name=f"{animation.display_name} - {frame.name}",
                        original_key=frame.original_key,
                        pixmap=frame.pixmap,
                        duration_ms=frame.duration_ms,
                        offset_x=frame.offset_x,
                        offset_y=frame.offset_y,
                        metadata={
                            "source_animation_id": animation_id,
                            "source_frame_index": str(index),
                            "composite_frame": "1",
                        },
                    )
                )

        if len(composite_sources) < 2 or not combined_frames:
            QMessageBox.warning(
                self,
                self.tr(DialogTitles.COMBINE_FAILED),
                self.tr(
                    "Could not build the composite entry. Ensure the selected animations have frames."
                ),
            )
            return

        if len(composite_sources) > 3:
            display_name = self.tr("Composite ({count} animations)").format(
                count=len(composite_sources)
            )
        else:
            display_name = self.tr("Composite: {names}").format(
                names=", ".join(composite_sources)
            )

        canvas_width = min(4096, max(8, (max_frame_width or 256) * 2))
        canvas_height = min(4096, max(8, (max_frame_height or 256) * 2))

        composite_animation = AlignmentAnimation(
            display_name=display_name,
            frames=combined_frames,
            canvas_width=canvas_width,
            canvas_height=canvas_height,
            source="manual",
            metadata={
                "composite_of": ",".join(composite_sources),
                "source_animation_ids": ",".join(source_animation_ids),
                "composite_translate_x": "0",
                "composite_translate_y": "0",
            },
            default_offset=(0, 0),
        )

        if source_animation_names:
            composite_animation.metadata["source_animation_names"] = json.dumps(
                source_animation_names
            )

        if export_info_confident and base_sheet_name:
            composite_animation.metadata["source_sheet_name"] = base_sheet_name
            if base_spritesheet_path:
                composite_animation.metadata["source_spritesheet_path"] = (
                    base_spritesheet_path
                )
            if base_metadata_path:
                composite_animation.metadata["source_metadata_path"] = (
                    base_metadata_path
                )
        composite_animation.ensure_canvas_bounds()
        self._register_animation(composite_animation)
        self.status_label.setText(
            self.tr("Composite entry created with {count} frames.").format(
                count=len(combined_frames)
            )
        )

    def _remove_selected_frames(self):
        """Delete highlighted frames from their parent animations."""
        frame_items = [
            item
            for item in self.animation_tree.selectedItems()
            if item.parent() is not None
        ]
        if not frame_items:
            return

        frames_by_animation: Dict[str, List[int]] = defaultdict(list)
        for item in frame_items:
            animation_id = item.data(0, ANIMATION_ID_ROLE)
            frame_index = item.data(0, FRAME_INDEX_ROLE)
            if animation_id and frame_index is not None:
                frames_by_animation[str(animation_id)].append(int(frame_index))

        if not frames_by_animation:
            return

        for animation_id, indices in frames_by_animation.items():
            animation = self._animations.get(animation_id)
            if animation is None or not animation.frames:
                continue
            unique_indices = sorted(
                {idx for idx in indices if isinstance(idx, int)}, reverse=True
            )
            if not unique_indices:
                continue

            for idx in unique_indices:
                if 0 <= idx < len(animation.frames):
                    del animation.frames[idx]

            tree_item = self._animation_items.get(animation_id)
            if tree_item:
                self._populate_frame_items(tree_item, animation_id, animation)

            if animation_id == self._current_animation_id:
                preferred_index = unique_indices[-1] if animation.frames else -1
                self._realign_selection_after_frame_removal(
                    animation, tree_item, preferred_index
                )

        self._refresh_after_frame_list_change()

    def _realign_selection_after_frame_removal(
        self,
        animation: AlignmentAnimation,
        tree_item: Optional[QTreeWidgetItem],
        preferred_index: int,
    ):
        """Pick a sensible frame to focus after removing entries."""
        if animation.frames:
            candidate_index = preferred_index if preferred_index >= 0 else 0
            candidate_index = max(0, min(candidate_index, len(animation.frames) - 1))
            self._current_frame_index = candidate_index
            if tree_item and tree_item.childCount() > candidate_index:
                target_item = tree_item.child(candidate_index)
                if target_item:
                    self.animation_tree.setCurrentItem(target_item)
        else:
            self._current_frame_index = -1
            if tree_item:
                self.animation_tree.setCurrentItem(tree_item)
            self.canvas.set_pixmap(None)

    def _refresh_after_frame_list_change(self):
        """Update dependent UI once the frame list mutates."""
        self._refresh_ghost_options()
        self._update_combine_button_state()
        self.status_label.setText(self._default_status_text)
        self._multi_drag_baselines = None

    def _selected_top_level_animation_ids(self) -> List[str]:
        """Return IDs for currently selected top-level animation rows."""
        tree = getattr(self, "animation_tree", None)
        if tree is None:
            return []
        selected_ids: List[str] = []
        for item in tree.selectedItems():
            if item is None or item.parent() is not None:
                continue
            anim_id = item.data(0, ANIMATION_ID_ROLE)
            if isinstance(anim_id, str):
                selected_ids.append(anim_id)
        return selected_ids

    def _reset_multi_drag_baselines(self):
        """Forget cached baseline offsets for group drag."""
        self._multi_drag_baselines = None

    def _ensure_multi_drag_baselines(self, selected_ids: List[str]):
        """Capture current display offsets for each selected animation."""
        if not selected_ids:
            self._multi_drag_baselines = None
            return
        if self._multi_drag_baselines is not None and set(
            self._multi_drag_baselines.keys()
        ) == set(selected_ids):
            return
        baselines: Dict[str, Tuple[int, int]] = {}
        for anim_id in selected_ids:
            animation = self._animations.get(anim_id)
            if animation is None:
                continue
            base_x, base_y = self._determine_root_display_offsets(animation)
            baselines[anim_id] = (base_x, base_y)
        self._multi_drag_baselines = baselines

    def _apply_offsets_to_selected_animations(
        self,
        offset_x: int,
        offset_y: int,
        *,
        update_default: bool,
        status_message: bool,
    ) -> bool:
        """Apply offsets to all selected top-level animations at once."""
        selected_ids = self._selected_top_level_animation_ids()
        if len(selected_ids) <= 1:
            return False

        for anim_id in selected_ids:
            animation = self._animations.get(anim_id)
            if animation is None:
                continue
            if anim_id == self._current_animation_id:
                reference_index = self._current_frame_index
            else:
                reference_index = 0 if animation.frames else None
            self._apply_offsets_to_animation(
                animation,
                offset_x,
                offset_y,
                update_default=update_default,
                reference_frame_index=reference_index,
            )

        if status_message:
            self.status_label.setText(
                self.tr("Applied ({x}, {y}) to {count} animations.").format(
                    x=offset_x, y=offset_y, count=len(selected_ids)
                )
            )
        return True

    def _apply_relative_offsets_to_selected_animations(
        self,
        target_offset_x: int,
        target_offset_y: int,
    ) -> bool:
        """Apply relative delta from the current animation to all selected ones."""
        selected_ids = self._selected_top_level_animation_ids()
        if len(selected_ids) <= 1:
            return False

        self._ensure_multi_drag_baselines(selected_ids)
        if not self._multi_drag_baselines:
            return False

        anchor_base = self._multi_drag_baselines.get(
            self._current_animation_id, (target_offset_x, target_offset_y)
        )
        delta_x = target_offset_x - anchor_base[0]
        delta_y = target_offset_y - anchor_base[1]

        for anim_id, (base_x, base_y) in self._multi_drag_baselines.items():
            animation = self._animations.get(anim_id)
            if animation is None:
                continue
            reference_index = 0 if animation.frames else None
            self._apply_offsets_to_animation(
                animation,
                base_x + delta_x,
                base_y + delta_y,
                update_default=True,
                reference_frame_index=reference_index,
            )
        return True

    # ------------------------------------------------------------------
    # Selection handlers
    # ------------------------------------------------------------------
    def _on_tree_current_changed(
        self, current: Optional[QTreeWidgetItem], previous: Optional[QTreeWidgetItem]
    ):
        """Respond to selection changes in the tree widget."""
        if not current:
            self._current_animation_id = None
            self._current_frame_index = -1
            self._root_alignment_mode = False
            self._reset_multi_drag_baselines()
            self.canvas.set_pixmap(None)
            self.save_overrides_button.setEnabled(False)
            self.export_composite_button.setEnabled(False)
            self._refresh_ghost_options()
            return

        animation_id = current.data(0, ANIMATION_ID_ROLE)
        if not animation_id:
            return

        animation = self._animations.get(animation_id)
        if animation is None:
            return

        self._reset_multi_drag_baselines()

        animation.ensure_canvas_bounds(respect_existing=True)

        frame_index = current.data(0, FRAME_INDEX_ROLE)
        animation_changed = animation_id != self._current_animation_id
        self._current_animation_id = animation_id

        if frame_index is None:
            self._enter_root_alignment_mode(animation, animation_changed)
            return

        self._root_alignment_mode = False
        self._current_frame_index = int(frame_index)
        if not animation.frames or self._current_frame_index >= len(animation.frames):
            # Tree may temporarily reference a frame index that was removed; fall back gracefully.
            self._current_frame_index = 0 if animation.frames else -1
            self.canvas.set_pixmap(None)
            self._refresh_ghost_options()
            self.status_label.setText(self._default_status_text)
            return

        frame = animation.frames[self._current_frame_index]
        self.canvas.set_pixmap(frame.pixmap)
        self.canvas.set_canvas_size(animation.canvas_width, animation.canvas_height)
        display_x, display_y = self._calculate_display_offset(
            animation, frame.offset_x, frame.offset_y
        )
        self._updating_controls = True
        self.offset_x_spin.setValue(display_x)
        self.offset_y_spin.setValue(display_y)
        self._updating_controls = False
        self.canvas.set_offsets(display_x, display_y)
        self.canvas_width_spin.setValue(animation.canvas_width)
        self.canvas_height_spin.setValue(animation.canvas_height)
        self.save_overrides_button.setEnabled(animation.source == "extract")
        self.export_composite_button.setEnabled(
            bool(animation.metadata.get("source_animation_ids"))
        )
        if animation_changed:
            self._refresh_ghost_options()
        self.status_label.setText(self._default_status_text)

    def focus_animation_by_id(self, animation_id: str) -> bool:
        """Select the tree item belonging to ``animation_id`` if present."""
        item = self._animation_items.get(animation_id)
        if item is None:
            return False
        target = item.child(0) if item.childCount() > 0 else item
        self.animation_tree.setCurrentItem(target)
        self.animation_tree.scrollToItem(item)
        return True

    def _determine_root_display_offsets(
        self, animation: AlignmentAnimation
    ) -> Tuple[int, int]:
        """Figure out which offsets to show when the animation root is active."""
        translate_x, translate_y = self._get_composite_translation(animation)
        if self._is_composite_animation(animation):
            reference_frame = self._current_reference_frame(animation)
            base_x, base_y = self._reference_offset_for_composite(
                animation, reference_frame
            )
            return base_x + translate_x, base_y + translate_y
        if not animation.frames:
            base_x, base_y = animation.default_offset
            return base_x + translate_x, base_y + translate_y
        offsets = {
            (frame.offset_x + translate_x, frame.offset_y + translate_y)
            for frame in animation.frames
        }
        if len(offsets) == 1:
            return offsets.pop()
        default_x, default_y = animation.default_offset
        return default_x + translate_x, default_y + translate_y

    def _enter_root_alignment_mode(
        self, animation: AlignmentAnimation, animation_changed: bool
    ):
        """Switch into animation-level editing where offsets apply globally."""
        self._root_alignment_mode = True
        self._multi_drag_baselines = None
        preview_index = 0
        if 0 <= self._current_frame_index < len(animation.frames):
            preview_index = self._current_frame_index
        preview_index = (
            max(0, min(preview_index, len(animation.frames) - 1))
            if animation.frames
            else -1
        )
        self._current_frame_index = preview_index

        animation.ensure_canvas_bounds(respect_existing=True)

        if preview_index >= 0:
            frame = animation.frames[preview_index]
            self.canvas.set_pixmap(frame.pixmap)
            self.canvas.set_canvas_size(animation.canvas_width, animation.canvas_height)
            offset_x, offset_y = self._determine_root_display_offsets(animation)
            self._updating_controls = True
            self.offset_x_spin.setValue(offset_x)
            self.offset_y_spin.setValue(offset_y)
            self._updating_controls = False
            self.canvas.set_offsets(offset_x, offset_y)
        else:
            self.canvas.set_pixmap(None)
            base_x, base_y = animation.default_offset
            offset_x, offset_y = self._calculate_display_offset(
                animation, base_x, base_y
            )
            self._updating_controls = True
            self.offset_x_spin.setValue(offset_x)
            self.offset_y_spin.setValue(offset_y)
            self._updating_controls = False
            self.canvas.set_offsets(offset_x, offset_y)

        self.canvas_width_spin.setValue(animation.canvas_width)
        self.canvas_height_spin.setValue(animation.canvas_height)
        self.save_overrides_button.setEnabled(animation.source == "extract")
        self.export_composite_button.setEnabled(
            bool(animation.metadata.get("source_animation_ids"))
        )
        if animation_changed:
            self._refresh_ghost_options()
        self.status_label.setText(
            self.tr(
                "Root selected: offset changes now apply to every frame in this animation."
            )
        )

    # ------------------------------------------------------------------
    # Offset handling
    # ------------------------------------------------------------------
    def _apply_offsets_to_animation(
        self,
        animation: AlignmentAnimation,
        offset_x: int,
        offset_y: int,
        update_default: bool = False,
        reference_frame_index: Optional[int] = None,
    ):
        """Apply offsets to every frame (or composite metadata) as needed."""
        if self._is_composite_animation(animation):
            reference_frame = None
            if reference_frame_index is not None and 0 <= reference_frame_index < len(
                animation.frames
            ):
                reference_frame = animation.frames[reference_frame_index]
            else:
                reference_frame = self._current_reference_frame(animation)
            self._apply_composite_translation(
                animation, offset_x, offset_y, reference_frame
            )
            return
        for frame in animation.frames:
            frame.offset_x = offset_x
            frame.offset_y = offset_y
            self._propagate_frame_offset(frame)
        if update_default:
            animation.default_offset = (offset_x, offset_y)
        if self.ghost_checkbox.isChecked():
            self._apply_ghost_overlay()

    def _on_manual_offset_changed(self):
        """Handle spin-box edits initiated by the user."""
        if self._updating_controls or self._current_animation_id is None:
            return
        animation = self._animations.get(self._current_animation_id)
        if animation is None or (
            self._current_frame_index < 0 and not self._root_alignment_mode
        ):
            return
        offset_x = self.offset_x_spin.value()
        offset_y = self.offset_y_spin.value()
        self.canvas.set_offsets(offset_x, offset_y)
        if self._root_alignment_mode:
            if self._apply_relative_offsets_to_selected_animations(offset_x, offset_y):
                return
            self._apply_offsets_to_animation(
                animation, offset_x, offset_y, update_default=True
            )
            return
        if self._is_composite_animation(animation):
            translate_x, translate_y = self._get_composite_translation(animation)
            frame = animation.frames[self._current_frame_index]
            frame.offset_x = offset_x - translate_x
            frame.offset_y = offset_y - translate_y
            self._refresh_ghost_if_frame_changed(self._current_frame_index)
            return
        frame = animation.frames[self._current_frame_index]
        frame.offset_x = offset_x
        frame.offset_y = offset_y
        self._propagate_frame_offset(frame)
        self._refresh_ghost_if_frame_changed(self._current_frame_index)

    def _on_canvas_dragged(self, offset_x: int, offset_y: int):
        """Sync UI fields and animation data when the canvas reports drag moves."""
        if self._updating_controls or self._current_animation_id is None:
            return
        animation = self._animations.get(self._current_animation_id)
        if animation is None or (
            self._current_frame_index < 0 and not self._root_alignment_mode
        ):
            return
        self._updating_controls = True
        self.offset_x_spin.setValue(offset_x)
        self.offset_y_spin.setValue(offset_y)
        self._updating_controls = False
        if self._root_alignment_mode:
            if self._apply_relative_offsets_to_selected_animations(offset_x, offset_y):
                return
            self._apply_offsets_to_animation(
                animation, offset_x, offset_y, update_default=True
            )
            return
        if self._is_composite_animation(animation):
            translate_x, translate_y = self._get_composite_translation(animation)
            frame = animation.frames[self._current_frame_index]
            frame.offset_x = offset_x - translate_x
            frame.offset_y = offset_y - translate_y
            self._refresh_ghost_if_frame_changed(self._current_frame_index)
            return
        frame = animation.frames[self._current_frame_index]
        frame.offset_x = offset_x
        frame.offset_y = offset_y
        self._propagate_frame_offset(frame)
        self._refresh_ghost_if_frame_changed(self._current_frame_index)

    def _propagate_frame_offset(self, frame: AlignmentFrame):
        """Copy offsets back to a source animation when editing composite frames."""
        if frame.metadata.get("composite_frame") == "1":
            return
        source_animation_id = frame.metadata.get("source_animation_id")
        if not source_animation_id:
            return
        source_index_value = frame.metadata.get("source_frame_index")
        if source_index_value is None:
            return
        try:
            source_index = int(source_index_value)
        except (TypeError, ValueError):
            return
        target_animation = self._animations.get(source_animation_id)
        if not target_animation or not (
            0 <= source_index < len(target_animation.frames)
        ):
            return
        target_frame = target_animation.frames[source_index]
        target_frame.offset_x = frame.offset_x
        target_frame.offset_y = frame.offset_y

    def _apply_offsets_to_all_frames(self):
        """Copy the current frame's offsets to every frame in the animation."""
        if self._current_animation_id is None:
            return
        animation = self._animations.get(self._current_animation_id)
        if animation is None or self._current_frame_index < 0:
            return
        frame = animation.frames[self._current_frame_index]
        if self._is_composite_animation(animation):
            offset_x, offset_y = self._calculate_display_offset(
                animation, frame.offset_x, frame.offset_y
            )
        else:
            offset_x = frame.offset_x
            offset_y = frame.offset_y
        self._apply_offsets_to_animation(
            animation, offset_x, offset_y, update_default=True
        )
        self._refresh_ghost_if_frame_changed(self._current_frame_index)
        self.status_label.setText(
            self.tr("Applied ({x}, {y}) to every frame.").format(x=offset_x, y=offset_y)
        )
        self.canvas.set_offsets(offset_x, offset_y)
        if self._root_alignment_mode:
            self._updating_controls = True
            self.offset_x_spin.setValue(offset_x)
            self.offset_y_spin.setValue(offset_y)
            self._updating_controls = False

    def _reset_frame_offset(self):
        """Restore default offsets or composite translations for current scope."""
        if self._current_animation_id is None:
            return
        animation = self._animations.get(self._current_animation_id)
        if animation is None:
            return
        default_x, default_y = animation.default_offset
        if self._is_composite_animation(animation):
            self._set_composite_translation(animation, 0, 0)
            reference_frame = self._current_reference_frame(animation)
            if reference_frame is not None:
                display_x, display_y = (
                    reference_frame.offset_x,
                    reference_frame.offset_y,
                )
            else:
                display_x, display_y = default_x, default_y
            self._updating_controls = True
            self.offset_x_spin.setValue(display_x)
            self.offset_y_spin.setValue(display_y)
            self._updating_controls = False
            self.canvas.set_offsets(display_x, display_y)
            if self.ghost_checkbox.isChecked():
                self._apply_ghost_overlay()
            return
        if self._root_alignment_mode:
            self._apply_offsets_to_animation(
                animation, default_x, default_y, update_default=False
            )
            self._updating_controls = True
            self.offset_x_spin.setValue(default_x)
            self.offset_y_spin.setValue(default_y)
            self._updating_controls = False
            self.canvas.set_offsets(default_x, default_y)
            return
        if self._current_frame_index < 0:
            return
        frame = animation.frames[self._current_frame_index]
        frame.offset_x = default_x
        frame.offset_y = default_y
        self._updating_controls = True
        self.offset_x_spin.setValue(default_x)
        self.offset_y_spin.setValue(default_y)
        self._updating_controls = False
        self.canvas.set_offsets(default_x, default_y)
        self._propagate_frame_offset(frame)
        self._refresh_ghost_if_frame_changed(self._current_frame_index)

    def _on_canvas_size_changed(self):
        """Handle spin-box updates and resize the logical canvas."""
        if self._current_animation_id is None:
            return
        animation = self._animations.get(self._current_animation_id)
        if animation is None:
            return
        animation.canvas_width = self.canvas_width_spin.value()
        animation.canvas_height = self.canvas_height_spin.value()
        self.canvas.set_canvas_size(animation.canvas_width, animation.canvas_height)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _save_alignment_to_settings(self):
        """Persist current alignment overrides into the settings manager."""
        if self._current_animation_id is None:
            return
        animation = self._animations.get(self._current_animation_id)
        if animation is None or animation.source != "extract":
            return

        overrides_data = self._build_alignment_overrides(animation)
        full_name = f"{animation.spritesheet_name}/{animation.animation_name}"
        settings = self.parent_app.settings_manager.animation_settings.setdefault(
            full_name, {}
        )
        settings["alignment_overrides"] = overrides_data
        QMessageBox.information(
            self,
            self.tr(DialogTitles.ALIGNMENT_SAVED),
            self.tr(
                "Offsets stored for '{name}'. They will be used on the next extraction run."
            ).format(name=full_name),
        )

    def _export_composite_to_sprites(self):
        """Convert a composite entry back into extractor-aligned animations."""
        if self._current_animation_id is None:
            return
        animation = self._animations.get(self._current_animation_id)
        if animation is None:
            return
        source_ids_value = animation.metadata.get("source_animation_ids")
        if not source_ids_value:
            QMessageBox.information(
                self,
                self.tr(DialogTitles.EXPORT_COMPOSITE),
                self.tr("Select a composite entry generated from multiple animations."),
            )
            return

        source_ids = [item for item in source_ids_value.split(",") if item]
        if not source_ids:
            QMessageBox.warning(
                self,
                self.tr(DialogTitles.EXPORT_COMPOSITE),
                self.tr(
                    "Could not determine the source animations for this composite."
                ),
            )
            return

        source_animations: List[AlignmentAnimation] = []
        for source_id in source_ids:
            item = self._animations.get(source_id)
            if item:
                source_animations.append(item)

        base_spritesheet: Optional[str] = None
        base_metadata: Dict[str, Any] = {}

        if source_animations:
            if any(anim.source != "extract" for anim in source_animations):
                QMessageBox.warning(
                    self,
                    self.tr(DialogTitles.EXPORT_COMPOSITE),
                    self.tr(
                        "Composite export currently supports animations loaded from the extractor only."
                    ),
                )
                return

            base_spritesheet = source_animations[0].spritesheet_name
            base_metadata = dict(source_animations[0].metadata or {})
            different_sheet = any(
                anim.spritesheet_name != base_spritesheet for anim in source_animations
            )
            if not base_spritesheet or different_sheet:
                QMessageBox.warning(
                    self,
                    self.tr(DialogTitles.EXPORT_COMPOSITE),
                    self.tr(
                        "All combined animations must belong to the same spritesheet and originate from the extractor."
                    ),
                )
                return
        else:
            # Fall back to stored metadata captured during combine so export still works
            base_spritesheet = animation.metadata.get("source_sheet_name")
            base_metadata = {
                "spritesheet_path": animation.metadata.get(
                    "source_spritesheet_path", ""
                ),
                "metadata_path": animation.metadata.get("source_metadata_path", ""),
            }
            if not base_spritesheet:
                QMessageBox.warning(
                    self,
                    self.tr(DialogTitles.EXPORT_COMPOSITE),
                    self.tr(
                        "Source animations were removed and no export metadata was stored. Recreate the composite while source animations are present."
                    ),
                )
                return

        spritesheet_path = base_metadata.get("spritesheet_path")
        metadata_path = base_metadata.get("metadata_path")

        composite_count = max(len(source_animations), len(source_ids), 1)
        default_name = self.tr("Composite_{count}").format(count=composite_count)
        animation_name, accepted = QInputDialog.getText(
            self,
            self.tr(DialogTitles.COMPOSITE_NAME),
            self.tr("Enter a name for the exported animation"),
            text=default_name,
        )
        if not accepted or not animation_name.strip():
            return
        animation_name = animation_name.strip()

        composite_definition = self._build_composite_definition(
            animation, animation_name
        )
        if composite_definition is None:
            QMessageBox.warning(
                self,
                self.tr("Export composite"),
                self.tr("Unable to capture composite definition for export."),
            )
            return

        translate_x, translate_y = self._get_composite_translation(animation)
        new_frames: List[AlignmentFrame] = []
        for frame in animation.frames:
            display_x = frame.offset_x + translate_x
            display_y = frame.offset_y + translate_y
            new_frames.append(
                AlignmentFrame(
                    name=frame.name,
                    original_key=frame.original_key,
                    pixmap=frame.pixmap,
                    duration_ms=frame.duration_ms,
                    offset_x=display_x,
                    offset_y=display_y,
                )
            )

        export_metadata = {
            "spritesheet_path": spritesheet_path,
            "metadata_path": metadata_path,
            "exported_from": animation.display_name,
            "composite_sources": animation.metadata.get("composite_of", ""),
        }

        exported_animation = AlignmentAnimation(
            display_name=f"{base_spritesheet}/{animation_name}",
            frames=new_frames,
            canvas_width=animation.canvas_width,
            canvas_height=animation.canvas_height,
            source="extract",
            spritesheet_name=base_spritesheet,
            animation_name=animation_name,
            metadata=export_metadata,
            default_offset=(
                animation.default_offset[0] + translate_x,
                animation.default_offset[1] + translate_y,
            ),
        )
        exported_animation.ensure_canvas_bounds()
        new_animation_id = self._register_animation(exported_animation)
        self.status_label.setText(
            self.tr("Exported composite to {name}.").format(
                name=exported_animation.display_name
            )
        )
        if hasattr(self.parent_app, "extract_tab_widget") and getattr(
            self.parent_app, "extract_tab_widget"
        ):
            try:
                self.parent_app.extract_tab_widget.register_editor_composite(
                    base_spritesheet,
                    animation_name,
                    new_animation_id,
                    composite_definition,
                )
            except Exception as exc:
                print(
                    f"[EditorTabWidget] Failed to register composite in Extract tab: {exc}"
                )

    def _build_alignment_overrides(self, animation: AlignmentAnimation) -> dict:
        """Build the JSON-serializable overrides payload for an animation."""
        frame_overrides = {}
        use_frame_name = self._is_composite_animation(animation)
        for frame in animation.frames:
            override_key = frame.name if use_frame_name else frame.original_key
            frame_overrides[override_key] = {
                "x": frame.offset_x,
                "y": frame.offset_y,
            }
        animation.origin_mode = self._origin_mode
        overrides = {
            "canvas": [animation.canvas_width, animation.canvas_height],
            "default": {
                "x": animation.default_offset[0],
                "y": animation.default_offset[1],
            },
            "frames": frame_overrides,
            "origin_mode": animation.origin_mode,
        }
        translate_x, translate_y = self._get_composite_translation(animation)
        if translate_x or translate_y:
            overrides["composite_translation"] = {"x": translate_x, "y": translate_y}
        if animation.fnf_raw_offsets:
            overrides["_fnf_raw_offsets"] = animation.fnf_raw_offsets
        return overrides

    def _build_composite_definition(
        self, animation: AlignmentAnimation, target_name: str
    ) -> Optional[dict]:
        """Describe how a composite was built so the extract tab can replay it."""
        source_ids_value = animation.metadata.get("source_animation_ids")
        if not source_ids_value:
            return None

        source_map: Dict[str, AlignmentAnimation] = {}
        fallback_names: Dict[str, str] = {}
        fallback_raw = animation.metadata.get("source_animation_names")
        if isinstance(fallback_raw, str):
            try:
                decoded = json.loads(fallback_raw)
                if isinstance(decoded, dict):
                    fallback_names = {
                        str(key): str(value)
                        for key, value in decoded.items()
                        if value is not None
                    }
            except (json.JSONDecodeError, TypeError, ValueError):
                fallback_names = {}
        for source_id in source_ids_value.split(","):
            source_id = source_id.strip()
            if not source_id:
                continue
            source_anim = self._animations.get(source_id)
            if source_anim and source_anim.animation_name:
                source_map[source_id] = source_anim

        sequence: List[dict] = []
        for frame in animation.frames:
            source_id = frame.metadata.get("source_animation_id")
            source_index_value = frame.metadata.get("source_frame_index")
            if source_id is None or source_index_value is None:
                continue
            source_anim = source_map.get(source_id)
            if source_anim is None or source_anim.animation_name is None:
                fallback_name = fallback_names.get(source_id)
                if not fallback_name:
                    continue
            try:
                source_index = int(source_index_value)
            except (TypeError, ValueError):
                continue
            sequence.append(
                {
                    "source_animation": (
                        fallback_name
                        if source_anim is None
                        else source_anim.animation_name
                    ),
                    "source_frame_index": source_index,
                    "original_key": frame.original_key,
                    "name": frame.name,
                    "offset_x": frame.offset_x,
                    "offset_y": frame.offset_y,
                    "duration_ms": frame.duration_ms,
                }
            )

        if not sequence:
            return None

        return {
            "name": target_name,
            "alignment": self._build_alignment_overrides(animation),
            "sequence": sequence,
        }

    @staticmethod
    def _sanitize_canvas_dimension(value: Any, fallback: int) -> int:
        """Convert persisted canvas values to a safe range for the editor UI."""
        try:
            dimension = int(value)
        except (TypeError, ValueError):
            return fallback
        return max(8, min(4096, dimension))

    @staticmethod
    def _extract_frame_metadata(raw_metadata: Any) -> Dict[str, int]:
        """Normalize source frame offsets from atlas metadata blocks."""
        if isinstance(raw_metadata, dict):
            return {
                "source_frame_x": int(
                    raw_metadata.get("source_frame_x", raw_metadata.get("frameX", 0))
                ),
                "source_frame_y": int(
                    raw_metadata.get("source_frame_y", raw_metadata.get("frameY", 0))
                ),
            }
        if isinstance(raw_metadata, (list, tuple)) and len(raw_metadata) >= 6:
            return {
                "source_frame_x": int(raw_metadata[4]),
                "source_frame_y": int(raw_metadata[5]),
            }
        return {"source_frame_x": 0, "source_frame_y": 0}

    @staticmethod
    def _sample_frame_metadata(
        animation: AlignmentAnimation,
    ) -> Optional[Dict[str, int]]:
        """Fetch metadata from the first frame to infer defaults."""
        if not animation.frames:
            return None
        return animation.frames[0].metadata

    def _apply_alignment_overrides(
        self, animation: AlignmentAnimation, overrides: dict
    ):
        """Replay saved overrides when loading from extractor settings."""
        canvas = overrides.get("canvas")
        if canvas and len(canvas) == 2:
            animation.canvas_width = self._sanitize_canvas_dimension(
                canvas[0], animation.canvas_width
            )
            animation.canvas_height = self._sanitize_canvas_dimension(
                canvas[1], animation.canvas_height
            )
        default_values = overrides.get("default", {})
        base_default = (
            int(default_values.get("x", 0)),
            int(default_values.get("y", 0)),
        )
        fnf_default = resolve_fnf_offset(
            overrides, metadata=self._sample_frame_metadata(animation)
        )
        animation.default_offset = fnf_default or base_default
        origin_mode_value = overrides.get("origin_mode")
        if (
            isinstance(origin_mode_value, str)
            and origin_mode_value in VALID_ORIGIN_MODES
        ):
            animation.origin_mode = origin_mode_value
        else:
            animation.origin_mode = ORIGIN_MODE_CENTER
        raw_block = overrides.get("_fnf_raw_offsets")
        if isinstance(raw_block, dict):
            animation.fnf_raw_offsets = {key: value for key, value in raw_block.items()}
        else:
            animation.fnf_raw_offsets = None
        frame_map = overrides.get("frames", {})
        for frame in animation.frames:
            data = frame_map.get(frame.original_key)
            if data is None:
                offset_x, offset_y = animation.default_offset
            else:
                offset_x = int(data.get("x", animation.default_offset[0]))
                offset_y = int(data.get("y", animation.default_offset[1]))

            fnf_override = resolve_fnf_offset(
                overrides, frame.original_key, frame.metadata
            )
            if fnf_override is not None:
                offset_x, offset_y = fnf_override

            frame.offset_x = offset_x
            frame.offset_y = offset_y
        animation.ensure_canvas_bounds(respect_existing=True)

    def closeEvent(self, event):  # noqa: D401 - Qt API
        """Ensure detached windows close when the editor tab is closed."""
        if self._detached_window:
            self._detached_window.close()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _ensure_pil_image(image: Any) -> Any:
        """Normalize frame payloads into Pillow images for preview rendering."""
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow is required to prepare frames for preview")

        if PIL_AVAILABLE and isinstance(image, Image.Image):
            return image

        if isinstance(image, np.ndarray):
            array = image
            if array.dtype != np.uint8:
                array = array.astype(np.uint8)

            channels = array.shape[2] if array.ndim == 3 else 1
            mode = "RGBA" if channels >= 4 else "RGB"
            return Image.fromarray(np.ascontiguousarray(array), mode)

        raise TypeError(
            f"Unsupported frame type {type(image)}; expected Pillow image or ndarray"
        )

    @staticmethod
    def _pil_to_pixmap(image) -> QPixmap:
        """Convert a Pillow image into a ``QPixmap`` for canvas rendering."""
        image = image.convert("RGBA")
        data = image.tobytes("raw", "RGBA")
        bytes_per_line = image.width * 4
        qimage = QImage(
            data,
            image.width,
            image.height,
            bytes_per_line,
            QImage.Format.Format_RGBA8888,
        )
        return QPixmap.fromImage(qimage.copy())

    @staticmethod
    def _pixmap_to_pil(pixmap: QPixmap) -> Any:
        """Convert a pixmap back into a Pillow image for export routines."""
        if not PIL_AVAILABLE:
            raise RuntimeError("Pillow is required to export editor composites")
        if pixmap.isNull():
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        qimage = pixmap.toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        width = qimage.width()
        height = qimage.height()
        buffer = qimage.bits()
        byte_count = qimage.sizeInBytes()
        data = buffer.tobytes(byte_count)
        pil_image = Image.frombuffer("RGBA", (width, height), data, "raw", "RGBA", 0, 1)
        return pil_image.copy()

    def build_canvas_frames(self, animation_id: str) -> List[Tuple[str, Any, dict]]:
        """Render frames as RGBA canvases honoring origin modes and offsets.

        Computes the required canvas size to ensure no frame is clipped,
        then renders each sprite at its proper position.
        """
        if not PIL_AVAILABLE:
            return []
        animation = self._animations.get(animation_id)
        if animation is None or not animation.frames:
            return []

        # Pre-compute paste positions and determine actual canvas bounds needed
        frame_positions: List[Tuple[AlignmentFrame, Any, int, int]] = []
        min_x, min_y = 0, 0
        max_x, max_y = 0, 0

        for frame in animation.frames:
            pixmap_image = self._pixmap_to_pil(frame.pixmap)
            if animation.origin_mode == ORIGIN_MODE_TOP_LEFT:
                paste_x = frame.offset_x
                paste_y = frame.offset_y
            else:
                paste_x = (
                    animation.canvas_width - pixmap_image.width
                ) // 2 + frame.offset_x
                paste_y = (
                    animation.canvas_height - pixmap_image.height
                ) // 2 + frame.offset_y

            frame_positions.append((frame, pixmap_image, paste_x, paste_y))

            # Track bounds needed to fit all sprites
            min_x = min(min_x, paste_x)
            min_y = min(min_y, paste_y)
            max_x = max(max_x, paste_x + pixmap_image.width)
            max_y = max(max_y, paste_y + pixmap_image.height)

        # Determine final canvas size: at least the animation's canvas,
        # but expanded if sprites extend beyond
        final_width = max(animation.canvas_width, max_x - min(0, min_x))
        final_height = max(animation.canvas_height, max_y - min(0, min_y))

        # Offset to apply if any sprite starts at negative coords
        shift_x = -min(0, min_x)
        shift_y = -min(0, min_y)

        aligned_frames: List[Tuple[str, Any, dict]] = []
        for index, (frame, pixmap_image, paste_x, paste_y) in enumerate(
            frame_positions
        ):
            canvas = Image.new("RGBA", (final_width, final_height), (0, 0, 0, 0))
            canvas.paste(
                pixmap_image,
                (paste_x + shift_x, paste_y + shift_y),
                pixmap_image,
            )
            aligned_frames.append(
                (
                    frame.name or f"frame_{index}",
                    canvas,
                    {"duration_ms": frame.duration_ms, **frame.metadata},
                )
            )
        return aligned_frames
