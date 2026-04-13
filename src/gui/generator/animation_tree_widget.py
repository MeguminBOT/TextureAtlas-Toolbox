#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tree widget for organizing frames into named animation groups."""

from pathlib import Path
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QMessageBox,
    QInputDialog,
    QMenu,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction

from utils.translation_manager import tr as translate


class AnimationTreeWidget(QTreeWidget):
    """Tree widget for managing animation groups and their frame order.

    Supports drag-and-drop reordering, renaming, and context menu actions.

    Attributes:
        animation_added: Signal emitted with the name when a group is created.
        animation_removed: Signal emitted with the name when a group is deleted.
        frame_order_changed: Signal emitted when frames are reordered.
    """

    animation_added = Signal(str)
    animation_removed = Signal(str)
    frame_order_changed = Signal()

    tr = translate

    def __init__(self, parent=None):
        """Initialize the animation tree widget.

        Args:
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setup_tree()

    def setup_tree(self):
        """Configure tree properties, drag-drop, and context menu."""
        self._export_format = "starling-xml"

        self.setHeaderLabel(self.tr("Animations & Frames"))
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.itemChanged.connect(self.on_item_changed)

    def add_animation_group(self, animation_name=None):
        """Create a new animation group in the tree.

        Args:
            animation_name: Display name for the group. Defaults to
                'New animation' with a numeric suffix if needed.

        Returns:
            The newly created QTreeWidgetItem for the group.
        """
        if animation_name is None:
            animation_name = self.tr("New animation")

        if self.find_animation_group(animation_name):
            counter = 1
            while self.find_animation_group(f"{animation_name} {counter}"):
                counter += 1
            animation_name = f"{animation_name} {counter}"

        group_item = QTreeWidgetItem(self)
        group_item.setText(0, animation_name)
        group_item.setFlags(group_item.flags() | Qt.ItemFlag.ItemIsEditable)

        font = QFont()
        font.setBold(True)
        group_item.setFont(0, font)

        group_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "animation_group"})

        group_item.setExpanded(True)

        self.setCurrentItem(group_item)

        self.animation_added.emit(animation_name)

        return group_item

    def add_frame_to_animation(self, animation_name, frame_path):
        """Add a frame to an animation group, creating it if necessary.

        Args:
            animation_name: Name of the target animation group.
            frame_path: Filesystem path to the frame image.

        Returns:
            The newly created QTreeWidgetItem for the frame.
        """
        group_item = self.find_animation_group(animation_name)
        if not group_item:
            group_item = self.add_animation_group(animation_name)

        frame_item = QTreeWidgetItem(group_item)
        frame_item.setText(0, Path(frame_path).name)
        frame_item.setData(
            0, Qt.ItemDataRole.UserRole, {"type": "frame", "path": frame_path}
        )

        frame_item.setFlags(frame_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.update_frame_numbering(group_item)

        return frame_item

    def remove_animation_group(self, animation_name):
        """Remove an animation group and all its frames.

        Args:
            animation_name: Name of the group to remove.

        Returns:
            True if the group was found and removed, False otherwise.
        """
        group_item = self.find_animation_group(animation_name)
        if group_item:
            root = self.invisibleRootItem()
            root.removeChild(group_item)

            self.animation_removed.emit(animation_name)

            return True
        return False

    def remove_frame_from_animation(self, frame_item):
        """Remove a frame from its parent animation group.

        Args:
            frame_item: QTreeWidgetItem representing the frame.

        Returns:
            True if the frame was removed, False otherwise.
        """
        if frame_item:
            parent = frame_item.parent()
            if parent:
                parent.removeChild(frame_item)
                self.update_frame_numbering(parent)
                self.frame_order_changed.emit()
                return True
        return False

    def find_animation_group(self, animation_name):
        """Locate an animation group by its display name.

        Args:
            animation_name: Name of the group to find.

        Returns:
            The matching QTreeWidgetItem, or None if not found.
        """
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.text(0) == animation_name:
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("type") == "animation_group":
                    return item
        return None

    def get_animation_groups(self):
        """Retrieve all animation groups with their ordered frame data.

        Returns:
            Dictionary mapping animation names to lists of frame info dicts,
            each containing 'path', 'name', and 'order' keys.
        """
        animations = {}
        root = self.invisibleRootItem()

        for i in range(root.childCount()):
            group_item = root.child(i)
            data = group_item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get("type") == "animation_group":
                animation_name = group_item.text(0)
                frames = []

                for j in range(group_item.childCount()):
                    frame_item = group_item.child(j)
                    frame_data = frame_item.data(0, Qt.ItemDataRole.UserRole)

                    if frame_data and frame_data.get("type") == "frame":
                        frames.append(
                            {
                                "path": frame_data["path"],
                                "name": frame_item.text(0),
                                "order": j,
                            }
                        )

                animations[animation_name] = frames

        return animations

    def set_export_format(self, export_format: str):
        """Set the active export format and refresh all frame labels.

        Args:
            export_format: Format key (e.g. ``"starling-xml"``, ``"json-hash"``).
        """
        if export_format == self._export_format:
            return
        self._export_format = export_format
        self.refresh_all_frame_numbering()

    def refresh_all_frame_numbering(self):
        """Re-number every frame across all animation groups."""
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            data = group_item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "animation_group":
                self.update_frame_numbering(group_item)

    @staticmethod
    def _format_frame_suffix(export_format: str, idx: int) -> str:
        """Build the frame suffix using the numbering convention for *export_format*.

        Mirrors :meth:`AtlasGenerator._format_sprite_name` so the tree
        preview matches the actual output names.
        """
        if export_format == "starling-xml":
            return f"{idx:04d}"
        if export_format in ("json-hash", "json-array"):
            return f"_{idx + 1:02d}"
        if export_format == "gdx":
            return f"_{idx}"
        return f"_{idx:04d}"

    def update_frame_numbering(self, group_item):
        """Refresh display names to show frame indices within the group.

        Args:
            group_item: QTreeWidgetItem representing the animation group.
        """
        if not group_item:
            return

        animation_name = group_item.text(0)

        for i in range(group_item.childCount()):
            frame_item = group_item.child(i)
            frame_data = frame_item.data(0, Qt.ItemDataRole.UserRole)

            if frame_data and frame_data.get("type") == "frame":
                original_path = frame_data["path"]
                original_name = Path(original_path).name

                suffix = self._format_frame_suffix(self._export_format, i)
                display_name = f"{original_name} \u2192 {animation_name}{suffix}"

                frame_item.setText(0, display_name)

    def clear_all_animations(self):
        """Remove all animation groups and frames from the tree."""

        self.clear()

    def get_frame_paths_for_animation(self, animation_name):
        """Get the ordered frame paths for an animation.

        Args:
            animation_name: Name of the animation group.

        Returns:
            List of filesystem paths in display order, or empty list if
            the group does not exist.
        """
        group_item = self.find_animation_group(animation_name)
        if not group_item:
            return []

        frame_paths = []
        for i in range(group_item.childCount()):
            frame_item = group_item.child(i)
            frame_data = frame_item.data(0, Qt.ItemDataRole.UserRole)

            if frame_data and frame_data.get("type") == "frame":
                frame_paths.append(frame_data["path"])

        return frame_paths

    def show_context_menu(self, position):
        """Display a context menu for the item at the given position.

        Args:
            position: Local coordinates where the menu was requested.
        """
        item = self.itemAt(position)
        if not item:
            menu = QMenu(self)

            add_action = QAction(self.tr("Add animation group"), self)
            add_action.triggered.connect(self.add_animation_group)
            menu.addAction(add_action)

            menu.exec(self.mapToGlobal(position))
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)

        if data and data.get("type") == "animation_group":
            menu = QMenu(self)

            rename_action = QAction(self.tr("Rename animation"), self)
            rename_action.triggered.connect(lambda: self.rename_animation_group(item))
            menu.addAction(rename_action)

            menu.addSeparator()

            delete_action = QAction(self.tr("Delete animation"), self)
            delete_action.triggered.connect(lambda: self.delete_animation_group(item))
            menu.addAction(delete_action)

            menu.exec(self.mapToGlobal(position))

        elif data and data.get("type") == "frame":
            menu = QMenu(self)

            remove_action = QAction(self.tr("Remove frame"), self)
            remove_action.triggered.connect(
                lambda: self.remove_frame_from_animation(item)
            )
            menu.addAction(remove_action)

            menu.exec(self.mapToGlobal(position))

    def rename_animation_group(self, group_item):
        """Prompt the user to rename an animation group.

        Args:
            group_item: QTreeWidgetItem representing the group to rename.
        """
        old_name = group_item.text(0)
        new_name, ok = QInputDialog.getText(
            self,
            self.tr("Rename animation"),
            self.tr("Enter new animation name:"),
            text=old_name,
        )

        if ok and new_name and new_name != old_name:
            if self.find_animation_group(new_name):
                QMessageBox.warning(
                    self,
                    self.tr("Name conflict"),
                    self.tr("An animation named '{0}' already exists.").format(
                        new_name
                    ),
                )
                return

            group_item.setText(0, new_name)

            self.update_frame_numbering(group_item)

            self.animation_removed.emit(old_name)
            self.animation_added.emit(new_name)

    def delete_animation_group(self, group_item):
        """Delete an animation group after user confirmation.

        Args:
            group_item: QTreeWidgetItem representing the group to delete.
        """
        animation_name = group_item.text(0)

        reply = QMessageBox.question(
            self,
            self.tr("Delete animation"),
            self.tr(
                "Are you sure you want to delete the animation '{0}' and all its frames?"
            ).format(animation_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.remove_animation_group(animation_name)

    def on_item_changed(self, item, column):
        """Handle in-place edits to item names.

        Args:
            item: The modified QTreeWidgetItem.
            column: Column index that changed.
        """
        if column == 0:
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "animation_group":
                self.update_frame_numbering(item)

    def dropEvent(self, event):
        """Handle drop events to update frame numbering after reordering.

        Args:
            event: QDropEvent describing the drop action.
        """
        super().dropEvent(event)

        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            group_item = root.child(i)
            data = group_item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get("type") == "animation_group":
                self.update_frame_numbering(group_item)

        self.frame_order_changed.emit()

    def get_total_frame_count(self):
        """Count all frames across every animation group.

        Returns:
            Total number of frame items in the tree.
        """
        total = 0
        root = self.invisibleRootItem()

        for i in range(root.childCount()):
            group_item = root.child(i)
            data = group_item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get("type") == "animation_group":
                total += group_item.childCount()

        return total

    def get_animation_count(self):
        """Count the animation groups in the tree.

        Returns:
            Number of top-level animation group items.
        """
        count = 0
        root = self.invisibleRootItem()

        for i in range(root.childCount()):
            group_item = root.child(i)
            data = group_item.data(0, Qt.ItemDataRole.UserRole)

            if data and data.get("type") == "animation_group":
                count += 1

        return count
