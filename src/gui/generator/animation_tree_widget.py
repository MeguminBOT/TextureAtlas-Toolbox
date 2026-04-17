#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tree widget for organizing frames into named animation groups under atlas jobs."""

from pathlib import Path
from PySide6.QtWidgets import (
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QMessageBox,
    QInputDialog,
    QMenu,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction

from utils.translation_manager import tr as translate


class AnimationTreeWidget(QTreeWidget):
    """Tree widget managing a 3-level Job -> Animation -> Frame hierarchy.

    Each *job* represents a separate atlas to generate.  Animation groups
    live under their parent job, and frames live under their animation.

    Attributes:
        animation_added: Signal(str) emitted when an animation group is created.
        animation_removed: Signal(str) emitted when an animation group is deleted.
        frame_order_changed: Signal emitted when frames are reordered.
        job_added: Signal(str) emitted when a job is created.
        job_removed: Signal(str) emitted when a job is deleted.
    """

    animation_added = Signal(str)
    animation_removed = Signal(str)
    frame_order_changed = Signal()
    job_added = Signal(str)
    job_removed = Signal(str)

    tr = translate

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_tree()

    def setup_tree(self):
        """Configure tree properties, drag-drop, and context menu."""
        self._export_format = "starling-xml"

        self.setColumnCount(2)
        self.setHeaderLabels([self.tr("Name"), self.tr("Frames")])
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.header().resizeSection(1, 60)

        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.itemChanged.connect(self.on_item_changed)

    # ------------------------------------------------------------------
    # Job (spritesheet) management
    # ------------------------------------------------------------------

    def add_job(self, job_name=None):
        """Create a new atlas job at the top level.

        Args:
            job_name: Display name.  Defaults to 'New Spritesheet'.

        Returns:
            The newly created QTreeWidgetItem.
        """
        if job_name is None:
            job_name = self.tr("New Spritesheet")

        if self.find_job(job_name):
            counter = 1
            while self.find_job(f"{job_name} {counter}"):
                counter += 1
            job_name = f"{job_name} {counter}"

        job_item = QTreeWidgetItem(self)
        job_item.setText(0, job_name)
        job_item.setFlags(job_item.flags() | Qt.ItemFlag.ItemIsEditable)

        font = QFont()
        font.setBold(True)
        job_item.setFont(0, font)

        job_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "job"})
        job_item.setExpanded(True)

        self._update_counts(job_item)
        self.setCurrentItem(job_item)
        self.job_added.emit(job_name)
        return job_item

    def find_job(self, job_name):
        """Find a job item by display name.

        Returns:
            Matching QTreeWidgetItem or None.
        """
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "job" and item.text(0) == job_name:
                return item
        return None

    def _ensure_job(self):
        """Return the job for the current selection, or create a default."""
        job = self._get_job_for_selection()
        if job:
            return job

        # Return the first existing job
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "job":
                return item

        # No jobs at all - create a default
        return self.add_job()

    def _get_job_for_selection(self):
        """Walk up from the current selection to find its owning job."""
        current = self.currentItem()
        while current:
            data = current.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "job":
                return current
            current = current.parent()
        return None

    def rename_job(self, job_item):
        """Prompt user to rename a job."""
        old_name = job_item.text(0)
        new_name, ok = QInputDialog.getText(
            self,
            self.tr("Rename spritesheet"),
            self.tr("Enter new spritesheet name:"),
            text=old_name,
        )
        if ok and new_name and new_name != old_name:
            if self.find_job(new_name):
                QMessageBox.warning(
                    self,
                    self.tr("Name conflict"),
                    self.tr("A spritesheet named '{0}' already exists.").format(
                        new_name
                    ),
                )
                return
            job_item.setText(0, new_name)
            self.job_removed.emit(old_name)
            self.job_added.emit(new_name)

    def delete_job(self, job_item):
        """Delete a job after user confirmation."""
        job_name = job_item.text(0)
        reply = QMessageBox.question(
            self,
            self.tr("Delete spritesheet"),
            self.tr(
                "Are you sure you want to delete '{0}' and all its animations?"
            ).format(job_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            root = self.invisibleRootItem()
            root.removeChild(job_item)
            self.job_removed.emit(job_name)
            self.frame_order_changed.emit()

    # ------------------------------------------------------------------
    # Animation group management
    # ------------------------------------------------------------------

    def add_animation_group(self, animation_name=None, job_item=None):
        """Create a new animation group under a job.

        Args:
            animation_name: Display name.  Defaults to 'New animation'.
            job_item: Parent job.  Uses ``_ensure_job()`` when None.

        Returns:
            The newly created QTreeWidgetItem for the group.
        """
        if job_item is None:
            job_item = self._ensure_job()

        if animation_name is None:
            animation_name = self.tr("New animation")

        if self.find_animation_group(animation_name, job_item):
            counter = 1
            while self.find_animation_group(f"{animation_name} {counter}", job_item):
                counter += 1
            animation_name = f"{animation_name} {counter}"

        group_item = QTreeWidgetItem(job_item)
        group_item.setText(0, animation_name)
        group_item.setFlags(group_item.flags() | Qt.ItemFlag.ItemIsEditable)
        group_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "animation_group"})
        group_item.setExpanded(True)

        self._update_counts(job_item)
        self.setCurrentItem(group_item)
        self.animation_added.emit(animation_name)
        return group_item

    def find_animation_group(self, animation_name, job_item=None):
        """Locate an animation group by name.

        Args:
            animation_name: Name of the group.
            job_item: Limit the search to this job.  Searches all jobs
                when None.

        Returns:
            Matching QTreeWidgetItem or None.
        """
        jobs = [job_item] if job_item else list(self._iter_jobs())
        for job in jobs:
            for i in range(job.childCount()):
                item = job.child(i)
                data = item.data(0, Qt.ItemDataRole.UserRole)
                if (
                    data
                    and data.get("type") == "animation_group"
                    and item.text(0) == animation_name
                ):
                    return item
        return None

    def remove_animation_group(self, animation_name):
        """Remove an animation group by name.

        Returns:
            True if removed, False otherwise.
        """
        group_item = self.find_animation_group(animation_name)
        if group_item:
            parent = group_item.parent()
            if parent:
                parent.removeChild(group_item)
                self._update_counts(parent)
            else:
                self.invisibleRootItem().removeChild(group_item)
            self.animation_removed.emit(animation_name)
            return True
        return False

    def rename_animation_group(self, group_item):
        """Prompt user to rename an animation group."""
        old_name = group_item.text(0)
        job_item = group_item.parent()
        new_name, ok = QInputDialog.getText(
            self,
            self.tr("Rename animation"),
            self.tr("Enter new animation name:"),
            text=old_name,
        )
        if ok and new_name and new_name != old_name:
            if self.find_animation_group(new_name, job_item):
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
        """Delete an animation group after user confirmation."""
        animation_name = group_item.text(0)
        reply = QMessageBox.question(
            self,
            self.tr("Delete animation"),
            self.tr(
                "Are you sure you want to delete the animation '{0}' "
                "and all its frames?"
            ).format(animation_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.remove_animation_group(animation_name)

    # ------------------------------------------------------------------
    # Frame management
    # ------------------------------------------------------------------

    def add_frame_to_animation(self, animation_name, frame_path, job_item=None):
        """Add a frame to an animation group, creating the group if needed.

        Args:
            animation_name: Target animation group name.
            frame_path: Filesystem path to the frame image.
            job_item: Parent job to scope the search.  Uses
                ``_ensure_job()`` when None.

        Returns:
            The newly created QTreeWidgetItem for the frame.
        """
        if job_item is None:
            job_item = self._ensure_job()

        group_item = self.find_animation_group(animation_name, job_item)
        if not group_item:
            group_item = self.add_animation_group(animation_name, job_item)

        frame_item = QTreeWidgetItem(group_item)
        frame_item.setText(0, Path(frame_path).name)
        frame_item.setData(
            0, Qt.ItemDataRole.UserRole, {"type": "frame", "path": frame_path}
        )
        frame_item.setFlags(frame_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.update_frame_numbering(group_item)
        self._update_counts(job_item)
        return frame_item

    def remove_frame_from_animation(self, frame_item):
        """Remove a frame from its parent animation group.

        Returns:
            True if removed, False otherwise.
        """
        if not frame_item:
            return False
        parent = frame_item.parent()
        if parent:
            parent.removeChild(frame_item)
            self.update_frame_numbering(parent)
            job = parent.parent()
            if job:
                self._update_counts(job)
            self.frame_order_changed.emit()
            return True
        return False

    def get_frame_paths_for_animation(self, animation_name):
        """Get ordered frame paths for an animation.

        Returns:
            List of filesystem paths in display order.
        """
        group_item = self.find_animation_group(animation_name)
        if not group_item:
            return []
        paths = []
        for i in range(group_item.childCount()):
            frame_item = group_item.child(i)
            data = frame_item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "frame":
                paths.append(data["path"])
        return paths

    # ------------------------------------------------------------------
    # Data retrieval
    # ------------------------------------------------------------------

    def _iter_jobs(self):
        """Yield all job items from the root."""
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            data = item.data(0, Qt.ItemDataRole.UserRole)
            if data and data.get("type") == "job":
                yield item

    def get_jobs(self):
        """Return the full 3-level data structure.

        Returns:
            ``{job_name: {anim_name: [frame_info_dict, ...]}}`` where each
            frame_info dict has 'path', 'name', and 'order' keys.
        """
        jobs = {}
        for job_item in self._iter_jobs():
            job_name = job_item.text(0)
            animations = {}
            for i in range(job_item.childCount()):
                group = job_item.child(i)
                gdata = group.data(0, Qt.ItemDataRole.UserRole)
                if not (gdata and gdata.get("type") == "animation_group"):
                    continue
                anim_name = group.text(0)
                frames = []
                for j in range(group.childCount()):
                    frame = group.child(j)
                    fdata = frame.data(0, Qt.ItemDataRole.UserRole)
                    if fdata and fdata.get("type") == "frame":
                        frames.append(
                            {
                                "path": fdata["path"],
                                "name": frame.text(0),
                                "order": j,
                            }
                        )
                animations[anim_name] = frames
            jobs[job_name] = animations
        return jobs

    def get_animation_groups(self):
        """Retrieve all animations flattened across every job.

        Provided for backward compatibility with callers that expect a
        single-level ``{anim_name: [frame_info]}`` dictionary.

        Returns:
            Dictionary mapping animation names to frame info lists.
        """
        animations = {}
        for _job_name, job_anims in self.get_jobs().items():
            for anim_name, frames in job_anims.items():
                key = anim_name
                if key in animations:
                    key = f"{anim_name} ({_job_name})"
                animations[key] = frames
        return animations

    def get_job_count(self):
        """Return the number of atlas jobs."""
        return sum(1 for _ in self._iter_jobs())

    def get_animation_count(self):
        """Count animation groups across all jobs."""
        count = 0
        for job_item in self._iter_jobs():
            for i in range(job_item.childCount()):
                data = job_item.child(i).data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("type") == "animation_group":
                    count += 1
        return count

    def get_total_frame_count(self):
        """Count all frames across every job and animation."""
        total = 0
        for job_item in self._iter_jobs():
            for i in range(job_item.childCount()):
                group = job_item.child(i)
                gdata = group.data(0, Qt.ItemDataRole.UserRole)
                if gdata and gdata.get("type") == "animation_group":
                    total += group.childCount()
        return total

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def set_export_format(self, export_format: str):
        """Set the active export format and refresh all frame labels."""
        if export_format == self._export_format:
            return
        self._export_format = export_format
        self.refresh_all_frame_numbering()

    def refresh_all_frame_numbering(self):
        """Re-number every frame across all jobs and animation groups."""
        for job_item in self._iter_jobs():
            for i in range(job_item.childCount()):
                group = job_item.child(i)
                data = group.data(0, Qt.ItemDataRole.UserRole)
                if data and data.get("type") == "animation_group":
                    self.update_frame_numbering(group)

    @staticmethod
    def _format_frame_suffix(export_format: str, idx: int) -> str:
        """Build the frame suffix using the numbering convention for *export_format*."""
        if export_format == "starling-xml":
            return f"{idx:04d}"
        if export_format in ("json-hash", "json-array"):
            return f"_{idx + 1:02d}"
        if export_format == "gdx":
            return f"_{idx}"
        return f"_{idx:04d}"

    def update_frame_numbering(self, group_item):
        """Refresh display names to show frame indices within the group."""
        if not group_item:
            return
        animation_name = group_item.text(0)
        for i in range(group_item.childCount()):
            frame_item = group_item.child(i)
            frame_data = frame_item.data(0, Qt.ItemDataRole.UserRole)
            if frame_data and frame_data.get("type") == "frame":
                original_name = Path(frame_data["path"]).name
                suffix = self._format_frame_suffix(self._export_format, i)
                frame_item.setText(
                    0, f"{original_name} \u2192 {animation_name}{suffix}"
                )

    def _update_counts(self, job_item):
        """Refresh the 'Frames' column for a job and its animations."""
        if not job_item:
            return
        total = 0
        for i in range(job_item.childCount()):
            group = job_item.child(i)
            gdata = group.data(0, Qt.ItemDataRole.UserRole)
            if gdata and gdata.get("type") == "animation_group":
                count = group.childCount()
                group.setText(1, str(count) if count else "")
                total += count
        job_item.setText(1, str(total) if total else "")

    def clear_all_animations(self):
        """Remove all jobs, animation groups, and frames."""
        self.clear()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def show_context_menu(self, position):
        """Display a context menu for the item at the given position."""
        item = self.itemAt(position)
        if not item:
            menu = QMenu(self)
            add_job_action = QAction(self.tr("Add spritesheet job"), self)
            add_job_action.triggered.connect(lambda: self.add_job())
            menu.addAction(add_job_action)
            add_anim_action = QAction(self.tr("Add animation group"), self)
            add_anim_action.triggered.connect(lambda: self.add_animation_group())
            menu.addAction(add_anim_action)
            menu.exec(self.mapToGlobal(position))
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return

        if data.get("type") == "job":
            menu = QMenu(self)
            add_anim = QAction(self.tr("Add animation group"), self)
            add_anim.triggered.connect(lambda: self.add_animation_group(job_item=item))
            menu.addAction(add_anim)
            menu.addSeparator()
            rename_action = QAction(self.tr("Rename spritesheet"), self)
            rename_action.triggered.connect(lambda: self.rename_job(item))
            menu.addAction(rename_action)
            delete_action = QAction(self.tr("Delete spritesheet"), self)
            delete_action.triggered.connect(lambda: self.delete_job(item))
            menu.addAction(delete_action)
            menu.exec(self.mapToGlobal(position))

        elif data.get("type") == "animation_group":
            menu = QMenu(self)
            rename_action = QAction(self.tr("Rename animation"), self)
            rename_action.triggered.connect(lambda: self.rename_animation_group(item))
            menu.addAction(rename_action)
            menu.addSeparator()
            delete_action = QAction(self.tr("Delete animation"), self)
            delete_action.triggered.connect(lambda: self.delete_animation_group(item))
            menu.addAction(delete_action)
            menu.exec(self.mapToGlobal(position))

        elif data.get("type") == "frame":
            menu = QMenu(self)
            remove_action = QAction(self.tr("Remove frame"), self)
            remove_action.triggered.connect(
                lambda: self.remove_frame_from_animation(item)
            )
            menu.addAction(remove_action)
            menu.exec(self.mapToGlobal(position))

    # ------------------------------------------------------------------
    # Inline editing / drag-drop
    # ------------------------------------------------------------------

    def on_item_changed(self, item, column):
        """Handle in-place edits to item names."""
        if column != 0:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data.get("type") == "animation_group":
            self.update_frame_numbering(item)
        elif data.get("type") == "job":
            self._update_counts(item)

    def dropEvent(self, event):
        """Handle drop events and refresh numbering afterwards."""
        super().dropEvent(event)
        for job_item in self._iter_jobs():
            for i in range(job_item.childCount()):
                group = job_item.child(i)
                gdata = group.data(0, Qt.ItemDataRole.UserRole)
                if gdata and gdata.get("type") == "animation_group":
                    self.update_frame_numbering(group)
            self._update_counts(job_item)
        self.frame_order_changed.emit()
