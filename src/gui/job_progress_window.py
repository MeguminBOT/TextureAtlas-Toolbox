#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reusable progress dialog for background job cycles.

Provides real-time progress feedback, a scrolling log, elapsed time
tracking, and cancellation support.  Used by the generator and optimizer
tabs (and any future tool that runs a batch job in a worker thread).

Usage:
    from gui.job_progress_window import JobProgressWindow

    dlg = JobProgressWindow(parent, title="Generating Atlas")
    dlg.cancellation_requested.connect(worker.request_cancel)
    dlg.start(total_steps=len(files))
    # … worker emits progress …
    dlg.update_progress(current, total, "Packing frame 3/10")
    dlg.append_log("Processing sprite.png")
    dlg.finish(success=True, message="Done!")
"""

from __future__ import annotations

import time
from typing import Optional

from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent, QFont

from utils.translation_manager import tr as translate
from utils.ui_constants import ButtonLabels


class JobProgressWindow(QDialog):
    """Modal progress dialog for long-running batch jobs.

    Attributes:
        cancellation_requested: Emitted when the user clicks *Cancel*.
    """

    cancellation_requested = Signal()

    tr = translate

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        title: str = "Processing...",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setMinimumSize(420, 320)
        self.resize(520, 420)

        self._is_cancelled = False
        self._is_finished = False
        self._start_time: Optional[float] = None

        self._setup_ui()

        self._duration_timer = QTimer(self)
        self._duration_timer.setInterval(1000)
        self._duration_timer.timeout.connect(self._update_duration)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Title
        self._title_label = QLabel(self.windowTitle())
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        self._title_label.setFont(title_font)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title_label)

        # Status + progress bar
        status_frame = QFrame()
        status_frame.setFrameStyle(QFrame.Shape.StyledPanel)
        status_layout = QVBoxLayout(status_frame)

        self._status_label = QLabel(self.tr("Initializing..."))
        self._status_label.setWordWrap(True)
        status_layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        status_layout.addWidget(self._progress_bar)

        self._duration_label = QLabel(self.tr("Duration: 00:00"))
        status_layout.addWidget(self._duration_label)

        layout.addWidget(status_frame)

        # Log
        log_label = QLabel(self.tr("Log:"))
        layout.addWidget(log_label)

        self._log_text = QTextEdit()
        self._log_text.setReadOnly(True)
        self._log_text.setMaximumHeight(160)
        layout.addWidget(self._log_text)

        # Buttons
        btn_layout = QHBoxLayout()

        self._cancel_btn = QPushButton(self.tr(ButtonLabels.CANCEL))
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_layout.addWidget(self._cancel_btn)

        btn_layout.addStretch()

        self._close_btn = QPushButton(self.tr(ButtonLabels.CLOSE))
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        btn_layout.addWidget(self._close_btn)

        layout.addLayout(btn_layout)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self, total_steps: int = 0) -> None:
        """Reset state and begin tracking a new job.

        Args:
            total_steps: Expected number of work items (0 for indeterminate).
        """
        self._is_cancelled = False
        self._is_finished = False
        self._start_time = time.time()
        self._progress_bar.setValue(0)
        if total_steps > 0:
            self._progress_bar.setRange(0, total_steps)
        else:
            self._progress_bar.setRange(0, 0)  # indeterminate
        self._cancel_btn.setEnabled(True)
        self._close_btn.setEnabled(False)
        self._log_text.clear()
        self._duration_timer.start()

    def update_progress(self, current: int, total: int, message: str = "") -> None:
        """Update the progress bar and status label.

        Args:
            current: Number of items completed.
            total: Total number of items.
            message: Short status message.
        """
        if total > 0:
            if self._progress_bar.maximum() != total:
                self._progress_bar.setRange(0, total)
            self._progress_bar.setValue(current)
        if message:
            self._status_label.setText(message)

    def append_log(self, text: str) -> None:
        """Append a line to the log area and auto-scroll."""
        self._log_text.append(text)
        cursor = self._log_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self._log_text.setTextCursor(cursor)

    def finish(self, success: bool = True, message: str = "") -> None:
        """Mark the job as finished and update the UI accordingly.

        Args:
            success: Whether the job completed without critical errors.
            message: Summary message shown in the status label and log.
        """
        self._is_finished = True
        self._duration_timer.stop()

        if success:
            status = message or self.tr("Completed successfully!")
            self._status_label.setText(status)
            self.append_log(self.tr("✓ {message}").format(message=status))
        else:
            status = message or self.tr("Job failed.")
            self._status_label.setText(status)
            self.append_log(self.tr("✗ {message}").format(message=status))

        self._cancel_btn.setEnabled(False)
        self._close_btn.setEnabled(True)

    @property
    def is_cancelled(self) -> bool:
        return self._is_cancelled

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_cancel(self) -> None:
        self._is_cancelled = True
        self._cancel_btn.setEnabled(False)
        self._status_label.setText(self.tr("Cancelling..."))
        self.append_log(self.tr("Cancellation requested..."))
        self.cancellation_requested.emit()

    def _update_duration(self) -> None:
        if self._start_time is not None:
            elapsed = int(time.time() - self._start_time)
            minutes, seconds = divmod(elapsed, 60)
            self._duration_label.setText(
                self.tr("Duration: {minutes:02d}:{seconds:02d}").format(
                    minutes=minutes, seconds=seconds
                )
            )

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._is_finished:
            self._on_cancel()
        event.accept()
