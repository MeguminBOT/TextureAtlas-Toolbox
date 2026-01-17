"""Progress dialog displaying extraction status and worker activity.

Shows real-time progress, statistics, and log messages while extractor
workers process spritesheets in parallel.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QToolButton,
    QFrame,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QFont

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels


class ProcessingWindow(QDialog):
    """Modal dialog displaying extraction progress, statistics, and logs.

    Provides real-time feedback during spritesheet extraction including
    file progress, worker status, generated frame/animation counts, and
    a scrolling log of processed files.

    Attributes:
        cancellation_requested: Signal emitted when user clicks Cancel.
        current_file_index: Number of files processed so far.
        total_files: Total number of files to process.
        current_filename: Display name of the file currently being processed.
        is_cancelled: True if user requested cancellation.
        frames_generated: Running count of extracted frames.
        animations_generated: Running count of created animations.
        sprites_failed: Running count of failed sprite extractions.
        start_time: Epoch timestamp when processing began.
    """

    cancellation_requested = Signal()

    tr = translate

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Initialize the processing dialog with progress indicators and timers.

        Args:
            parent: Parent widget for modal behavior.
        """
        super().__init__(parent)
        self.setWindowTitle(self.tr("Processing..."))
        self.setWindowModality(Qt.ApplicationModal)
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

        self.current_file_index: int = 0
        self.total_files: int = 0
        self.current_filename: str = ""
        self.is_cancelled = False

        self.frames_generated: int = 0
        self.animations_generated: int = 0
        self.sprites_failed: int = 0
        self.start_time: Optional[float] = None

        self.setup_ui()
        self._progress_dirty = False
        self._stats_dirty = False
        self._pending_current_files_text: Optional[str] = None
        self._log_buffer: List[str] = []
        self._pending_worker_entries: Optional[List[Dict[str, Any]]] = None
        self._latest_worker_entries: List[Dict[str, Any]] = []
        self._last_logged_recent_path: Optional[str] = None

        self._ui_update_timer = QTimer(self)
        self._ui_update_timer.setInterval(100)
        self._ui_update_timer.timeout.connect(self._flush_pending_updates)

    def setup_ui(self) -> None:
        """Build and configure all UI components for the dialog."""
        layout = QVBoxLayout(self)

        title_label = QLabel(self.tr("Extracting TextureAtlas Files"))
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        current_file_frame = QFrame()
        current_file_frame.setFrameStyle(QFrame.StyledPanel)
        current_file_layout = QVBoxLayout(current_file_frame)

        self.current_file_label = QLabel(self.tr("Current File:"))
        current_file_layout.addWidget(self.current_file_label)

        self.current_filename_label = QLabel(self.tr("Initializing..."))
        self.current_filename_label.setWordWrap(True)
        current_filename_font = QFont()
        current_filename_font.setBold(True)
        self.current_filename_label.setFont(current_filename_font)
        current_file_layout.addWidget(self.current_filename_label)

        worker_header_layout = QHBoxLayout()
        worker_header_layout.setContentsMargins(0, 0, 0, 0)

        worker_status_label = QLabel(self.tr("Worker Status"))
        worker_status_label.setFont(current_filename_font)
        worker_header_layout.addWidget(worker_status_label)
        worker_header_layout.addStretch()

        self.worker_toggle_button = QToolButton()
        self.worker_toggle_button.setCheckable(True)
        self.worker_toggle_button.setArrowType(Qt.RightArrow)
        self.worker_toggle_button.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.worker_toggle_button.setText(self.tr("Show worker details"))
        self.worker_toggle_button.clicked.connect(self._toggle_worker_details)
        worker_header_layout.addWidget(self.worker_toggle_button)

        current_file_layout.addLayout(worker_header_layout)

        self.worker_details_frame = QFrame()
        self.worker_details_frame.setFrameStyle(QFrame.NoFrame)
        self.worker_details_frame.setVisible(False)
        worker_details_layout = QVBoxLayout(self.worker_details_frame)
        worker_details_layout.setContentsMargins(0, 0, 0, 0)

        self.worker_list = QListWidget()
        self.worker_list.setAlternatingRowColors(True)
        self.worker_list.setSelectionMode(QAbstractItemView.NoSelection)
        self.worker_list.setUniformItemSizes(True)
        self.worker_list.setFocusPolicy(Qt.NoFocus)
        worker_details_layout.addWidget(self.worker_list)

        current_file_layout.addWidget(self.worker_details_frame)

        layout.addWidget(current_file_frame)

        progress_frame = QFrame()
        progress_frame.setFrameStyle(QFrame.StyledPanel)
        progress_layout = QVBoxLayout(progress_frame)

        self.progress_label = QLabel(self.tr("Progress: 0 / 0 files"))
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)

        layout.addWidget(progress_frame)

        stats_frame = QFrame()
        stats_frame.setFrameStyle(QFrame.StyledPanel)
        stats_layout = QVBoxLayout(stats_frame)

        stats_title = QLabel(self.tr("Statistics:"))
        stats_title_font = QFont()
        stats_title_font.setBold(True)
        stats_title.setFont(stats_title_font)
        stats_layout.addWidget(stats_title)

        self.frames_label = QLabel(self.tr("Frames Generated: 0"))
        self.animations_label = QLabel(self.tr("Animations Generated: 0"))
        self.failed_label = QLabel(self.tr("Sprites Failed: 0"))
        self.duration_label = QLabel(self.tr("Duration: 00:00"))

        stats_layout.addWidget(self.frames_label)
        stats_layout.addWidget(self.animations_label)
        stats_layout.addWidget(self.failed_label)
        stats_layout.addWidget(self.duration_label)

        layout.addWidget(stats_frame)

        log_label = QLabel(self.tr("Processing Log:"))
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton(self.tr(ButtonLabels.CANCEL))
        self.cancel_button.clicked.connect(self.cancel_processing)
        button_layout.addWidget(self.cancel_button)

        button_layout.addStretch()

        self.close_button = QPushButton(self.tr(ButtonLabels.CLOSE))
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        button_layout.addWidget(self.close_button)

        layout.addLayout(button_layout)

    def start_processing(self, total_files: int) -> None:
        """Reset statistics and begin tracking a new extraction batch.

        Args:
            total_files: Number of spritesheets to process.
        """
        self.total_files = total_files
        self.current_file_index = 0
        self.progress_bar.setMaximum(max(total_files, 1))
        self.progress_bar.setValue(0)

        self.frames_generated = 0
        self.animations_generated = 0
        self.sprites_failed = 0
        import time

        self.start_time = time.time()
        self._pending_worker_entries = None
        self._latest_worker_entries = []
        self._last_logged_recent_path = None
        if hasattr(self, "worker_list"):
            self._update_worker_list([], force=True)

        if not self._ui_update_timer.isActive():
            self._ui_update_timer.start()

        self.update_display()
        self.log_text.append(
            self.tr("Starting extraction of {count} files...").format(count=total_files)
        )

        self.duration_timer = QTimer(self)
        self.duration_timer.timeout.connect(self.update_duration)
        self.duration_timer.start(1000)

    def update_progress(
        self,
        current_file: int,
        total_files: int,
        status: Any = "",
    ) -> None:
        """Buffer progress updates for coalesced UI refresh.

        Args:
            current_file: Number of files completed so far.
            total_files: Total files in the batch.
            status: Either a status string or dict with worker details.
        """
        self.current_file_index = current_file
        self.total_files = total_files
        worker_entries = None
        recent_path = None
        recent_display = None

        if isinstance(status, dict):
            summary_text = status.get("summary") or status.get("fallback") or ""
            worker_entries = status.get("workers")
            recent_path = status.get("recent_full_path")
            recent_display = status.get("recent_display")
        else:
            summary_text = status or ""

        self.current_filename = summary_text
        self._pending_current_files_text = summary_text

        if worker_entries is not None:
            self._pending_worker_entries = worker_entries

        if recent_path and recent_path != self._last_logged_recent_path:
            display_name = recent_display or Path(recent_path).name
            log_entry = self.tr("Processing: {filename}").format(filename=display_name)
            self._log_buffer.append(log_entry)
            self._last_logged_recent_path = recent_path
        elif isinstance(status, str):
            filename = status
            if (
                filename
                and not filename.startswith("Processing:")
                and not filename.endswith("...")
            ):
                log_entry = self.tr("Processing: {filename}").format(filename=filename)
                self._log_buffer.append(log_entry)

        self._progress_dirty = True

    def update_display(self) -> None:
        """Refresh the progress label and bar to reflect current state."""

        self.progress_label.setText(
            self.tr("Progress: {current} / {total} files").format(
                current=self.current_file_index, total=self.total_files
            )
        )

        if self.total_files > 0:
            if self.progress_bar.maximum() != self.total_files:
                self.progress_bar.setMaximum(self.total_files)
            self.progress_bar.setValue(self.current_file_index)
        else:
            self.progress_bar.setValue(0)

        self.repaint()
        self.update()

    def update_duration(self) -> None:
        """Refresh the elapsed time display."""

        if self.start_time:
            import time

            current_time = time.time()
            duration = current_time - self.start_time
            minutes, seconds = divmod(int(duration), 60)
            self.duration_label.setText(
                self.tr("Duration: {minutes:02d}:{seconds:02d}").format(
                    minutes=minutes, seconds=seconds
                )
            )

    def update_statistics(
        self,
        frames_generated: Optional[int] = None,
        animations_generated: Optional[int] = None,
        sprites_failed: Optional[int] = None,
    ) -> None:
        """Update extraction counters and mark the stats display as dirty.

        Args:
            frames_generated: New frame count, or None to keep current.
            animations_generated: New animation count, or None to keep current.
            sprites_failed: New failure count, or None to keep current.
        """
        if frames_generated is not None:
            self.frames_generated = frames_generated
        if animations_generated is not None:
            self.animations_generated = animations_generated
        if sprites_failed is not None:
            self.sprites_failed = sprites_failed

        self._stats_dirty = True

    def processing_completed(self, success: bool = True, message: str = "") -> None:
        """Finalize progress UI after all workers have stopped.

        Args:
            success: True if extraction completed without critical errors.
            message: Optional status message to append to the log.
        """

        if hasattr(self, "duration_timer"):
            self.duration_timer.stop()

        if hasattr(self, "cancel_timer") and self.cancel_timer.isActive():
            self.cancel_timer.stop()

        if success:
            self.current_filename_label.setText(
                self.tr("Processing completed successfully!")
            )
            self.log_text.append(self.tr("✓ Extraction completed successfully!"))
            if message:
                self.log_text.append(message)
        else:
            self.current_filename_label.setText(self.tr("Processing failed!"))
            self.log_text.append(self.tr("✗ Extraction failed!"))
            if message:
                self.log_text.append(
                    self.tr("Error: {message}").format(message=message)
                )

        self.progress_bar.setValue(self.total_files)
        self._flush_pending_updates()
        if self._ui_update_timer.isActive():
            self._ui_update_timer.stop()
        self._pending_worker_entries = None
        self._latest_worker_entries = []
        self._update_worker_list([], force=True)
        self.cancel_button.setEnabled(False)
        self.close_button.setEnabled(True)

        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)

    def cancel_processing(self) -> None:
        """Request cancellation and start a timeout for forced closure."""

        self.is_cancelled = True
        self.current_filename_label.setText(self.tr("Cancelling..."))
        self.cancel_button.setEnabled(False)
        self.log_text.append(self.tr("Cancellation requested..."))

        self.cancellation_requested.emit()

        if not hasattr(self, "cancel_timer"):
            self.cancel_timer = QTimer(self)
            self.cancel_timer.timeout.connect(self.force_close)
            self.cancel_timer.setSingleShot(True)

        self.cancel_timer.start(5000)

    def force_close(self) -> None:
        """Terminate and close the dialog after cancellation timeout."""

        self.log_text.append(self.tr("Forcing cancellation due to timeout..."))
        self.processing_completed(
            False, "Processing was forcefully cancelled due to timeout"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        """Trigger cancellation if processing is still active on close."""

        if self.cancel_button.isEnabled():
            self.cancel_processing()
        event.accept()

    def add_debug_message(self, message: str) -> None:
        """Append a debug entry to the log buffer.

        Args:
            message: Text to display in the processing log.
        """
        self._log_buffer.append(message)

    def _flush_pending_updates(self) -> None:
        """Apply buffered progress, stats, and log updates to the UI."""

        if self._progress_dirty:
            self.update_display()
            if self._pending_current_files_text is not None:
                self.update_current_files(self._pending_current_files_text)
                self._pending_current_files_text = None
            if self._pending_worker_entries is not None:
                self._update_worker_list(self._pending_worker_entries)
                self._pending_worker_entries = None
            self._progress_dirty = False

        if self._stats_dirty:
            self.frames_label.setText(
                self.tr("Frames Generated: {count}").format(count=self.frames_generated)
            )
            self.animations_label.setText(
                self.tr("Animations Generated: {count}").format(
                    count=self.animations_generated
                )
            )
            self.failed_label.setText(
                self.tr("Sprites Failed: {count}").format(count=self.sprites_failed)
            )
            self.repaint()
            self.update()
            self._stats_dirty = False

        if self._log_buffer:
            for entry in self._log_buffer:
                self.log_text.append(entry)
            self._log_buffer.clear()
            cursor = self.log_text.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)

    def _toggle_worker_details(self) -> None:
        """Show or hide the worker status list."""

        is_visible = self.worker_toggle_button.isChecked()
        self.worker_details_frame.setVisible(is_visible)
        self.worker_toggle_button.setArrowType(
            Qt.DownArrow if is_visible else Qt.RightArrow
        )
        self.worker_toggle_button.setText(
            self.tr("Hide worker details")
            if is_visible
            else self.tr("Show worker details")
        )
        if is_visible:
            self._refresh_worker_list()

    def _refresh_worker_list(self) -> None:
        """Force an immediate refresh of the worker list display."""

        self._update_worker_list(self._latest_worker_entries, force=True)

    def _update_worker_list(
        self,
        worker_entries: Optional[List[Dict[str, Any]]],
        force: bool = False,
    ) -> None:
        """Rebuild the worker list widget with current worker states.

        Args:
            worker_entries: List of dicts containing label, display, state, path.
            force: If True, update even when the details frame is hidden.
        """
        self._latest_worker_entries = worker_entries or []
        if not self.worker_details_frame.isVisible() and not force:
            return

        self.worker_list.setUpdatesEnabled(False)
        self.worker_list.clear()

        if not self._latest_worker_entries:
            placeholder = QListWidgetItem(self.tr("No active workers"))
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self.worker_list.addItem(placeholder)
            self.worker_list.setUpdatesEnabled(True)
            return

        for entry in self._latest_worker_entries:
            label = entry.get("label", self.tr("Worker"))
            display_name = entry.get("display") or self.tr("Idle")
            state = entry.get("state", "processing")
            list_item = QListWidgetItem(f"{label}: {display_name}")
            tooltip_parts = []
            path_value = entry.get("path")
            if path_value:
                tooltip_parts.append(path_value)
            if state == "idle":
                tooltip_parts.append(self.tr("Idle"))
            if tooltip_parts:
                list_item.setToolTip("\n".join(tooltip_parts))
            self.worker_list.addItem(list_item)

        self.worker_list.setUpdatesEnabled(True)

    def update_current_files(self, current_files_text: str) -> None:
        """Update the label showing which file(s) are being processed.

        Args:
            current_files_text: Comma-separated list of filenames or single name.
        """
        if current_files_text:
            if ", " in current_files_text:
                self.current_filename_label.setText(
                    self.tr("Processing: {files}").format(files=current_files_text)
                )
            else:
                self.current_filename_label.setText(current_files_text)
        else:
            self.current_filename_label.setText(self.tr("Initializing..."))
