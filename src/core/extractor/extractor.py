"""Multi-threaded spritesheet extraction orchestrator.

This module provides ``Extractor``, which coordinates worker threads to
process batches of spritesheets in parallel. It also defines
``FileProcessorWorker`` (a ``QThread`` subclass) and the
``ExtractionCancelled`` exception.

Type Aliases:
    ProgressCallback: ``Callable[[int, int, str], None]`` for progress updates.
    StatisticsCallback: ``Callable[[int, int, int], None]`` for totals.
    ErrorPromptCallback: ``Callable[[str, BaseException], bool]`` for error prompts.
    StatsUpdate: Dict payload carrying counter deltas between threads.
"""

from __future__ import annotations

import gc
import os
import time
from pathlib import Path
from queue import SimpleQueue, Empty
from threading import Event, Lock
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from PySide6.QtCore import QCoreApplication, QThread, Signal

try:
    import psutil
except ImportError:  # pragma: no cover - psutil is part of app requirements
    psutil = None

# Import our own modules
from core.extractor.animation_exporter import AnimationExporter
from core.extractor.atlas_processor import AtlasProcessor
from core.extractor.frame_exporter import FrameExporter
from core.extractor.frame_pipeline import FramePipeline
from core.extractor.image_utils import ensure_rgba_array, scale_image
from core.extractor.sprite_processor import SpriteProcessor
from core.extractor.animation_processor import AnimationProcessor
from core.extractor.preview_generator import PreviewGenerator
from core.extractor.spritemap import AdobeSpritemapRenderer
from core.extractor.unknown_spritesheet_handler import UnknownSpritesheetHandler
from utils.translation_manager import tr as translate
from utils.utilities import Utilities

ProgressCallback = Callable[[int, int, str], None]
StatisticsCallback = Callable[[int, int, int], None]
ErrorPromptCallback = Callable[[str, BaseException], bool]
StatsUpdate = Dict[str, Any]

SUPPORTED_METADATA_EXTENSIONS: Tuple[str, ...] = (
    ".json",
    ".xml",
    ".txt",
    ".plist",
    ".atlas",
    ".css",
    ".tpsheet",
    ".tpset",
    ".paper2dsprites",
)
SUPPORTED_METADATA_SUFFIXES = {ext.lower() for ext in SUPPORTED_METADATA_EXTENSIONS}


class ExtractionCancelled(Exception):
    """Raised when extraction is cancelled by the user or due to a fatal error."""

    pass


class Extractor:
    """Orchestrate parallel spritesheet parsing and animation export.

    Manages a pool of ``FileProcessorWorker`` threads, dispatches files from
    a queue, aggregates statistics, and supports pause/cancel semantics.

    Attributes:
        settings_manager: Provides per-spritesheet and global settings.
        progress_callback: Invoked with ``(current, total, status)`` during runs.
        statistics_callback: Invoked with ``(frames, anims, failed)`` totals.
        current_version: Version string embedded in exported metadata.
        app_config: Optional application configuration for resource limits.
        cancel_event: ``Event`` signalling cancellation requests.
        preview_generator: Helper for generating animation previews.
        unknown_handler: Handles spritesheets without recognised metadata.
    """

    def __init__(
        self,
        progress_callback,
        current_version,
        settings_manager,
        app_config=None,
        statistics_callback=None,
        cancel_event=None,
        error_prompt_callback=None,
    ):
        """Initialise the extractor with callbacks and configuration.

        Args:
            progress_callback: Callable receiving ``(current, total, status)``.
            current_version: Version string for file metadata.
            settings_manager: Settings provider for export options.
            app_config: Optional config with resource limit overrides.
            statistics_callback: Optional callable receiving totals after runs.
            cancel_event: Optional ``Event`` for signalling cancellation.
            error_prompt_callback: Optional callback for error prompts.
        """
        self.settings_manager = settings_manager
        self.progress_callback = progress_callback
        self.statistics_callback = statistics_callback
        self.current_version = current_version
        self.app_config = app_config
        self.cancel_event = cancel_event or Event()
        self.error_prompt_callback = error_prompt_callback
        self._cancel_reason = None
        self.fnf_idle_loop = False
        self.preview_generator = PreviewGenerator(settings_manager, current_version)
        self.unknown_handler = UnknownSpritesheetHandler()
        self._trace_stats = False
        # UI updates and worker management
        self._stats_queue = SimpleQueue()
        self._progress_callback = None
        self.work_in_progress = {}
        self._worker_labels = {}
        self._last_started_file = None
        self._progress_dirty = False
        self._last_progress_emit = 0.0
        self._progress_emit_interval = 0.12  # seconds between UI payloads
        self._qt_event_interval = 0.04
        self._last_qt_event_pump = 0.0
        self._pause_event = Event()
        self._pause_event.set()
        self._awaiting_error_decision = False
        self._error_prompt_lock = Lock()
        # Memory Management
        self._memory_limit_mb = self._resolve_memory_limit()
        self._psutil_process = None
        self._memory_check_interval = 0.2
        self._memory_resume_ratio = 0.96
        self._memory_overage_logged = False
        self._last_gc_collect = 0.0
        self._gc_collect_interval = 0.75

    def process_directory(
        self,
        input_dir,
        output_dir,
        progress_callback=None,
        parent_window=None,
        spritesheet_list=None,
    ):
        """Process a batch of spritesheets using a worker pool.

        Enqueues files, starts workers, monitors progress, and aggregates
        statistics until all work completes or cancellation is requested.

        Args:
            input_dir: Root directory containing source atlas files.
            output_dir: Destination directory for exported assets.
            progress_callback: Optional override for instance callback.
            parent_window: Optional parent for modal dialogs.
            spritesheet_list: Iterable of relative filenames to process.

        Raises:
            ExtractionCancelled: If the run is aborted mid-flight.
        """

        self._initialize_processing_state()
        self._raise_if_cancelled()
        total_files = Utilities.count_spritesheets(spritesheet_list)
        self._progress_callback = self._choose_progress_callback(progress_callback)
        if self._progress_callback:
            self._progress_callback(0, total_files, "Initializing...")

        cpu_threads = self._resolve_cpu_threads()
        filenames = list(spritesheet_list or [])
        if filenames:
            filenames = self._prioritize_spritesheets(input_dir, filenames)
        self.total_files = len(filenames)
        self.work_in_progress.clear()
        for filename in filenames:
            self.file_queue.put(filename)
        # Push sentinel entries so workers know when to stop.
        # These will only be consumed once all real work is done because they are enqueued last.
        # Using None avoids extra allocations and still keeps intent clear.
        self.start_time = time.time()

        max_threads = self._determine_worker_budget(cpu_threads, len(filenames))
        if max_threads:
            for _ in range(max_threads):
                self.file_queue.put(None)
        else:
            self._workers_done_event.set()
        self._start_worker_pool(
            max_threads,
            input_dir,
            output_dir,
            parent_window,
        )
        self._monitor_workers()
        self._finalize_directory_processing()
        self._raise_if_cancelled()

        if self.statistics_callback:
            self.statistics_callback(
                self.total_frames_generated,
                self.total_anims_generated,
                self.total_sprites_failed,
            )

    def _initialize_processing_state(self):
        """Reset counters, queues, and events before processing a new batch."""
        self.total_frames_generated = 0
        self.total_anims_generated = 0
        self.total_sprites_failed = 0
        self._memory_limit_mb = self._resolve_memory_limit()
        self._memory_overage_logged = False
        self.processed_count = 0
        self.active_workers = []
        self._stats_queue = SimpleQueue()
        self.file_queue = SimpleQueue()
        self.work_in_progress = {}
        self._worker_labels = {}
        self._last_started_file = None
        if hasattr(self, "_workers_done_event"):
            self._workers_done_event.clear()
        else:
            self._workers_done_event = Event()
        if hasattr(self, "_stats_available_event"):
            self._stats_available_event.clear()
        else:
            self._stats_available_event = Event()
        self._progress_dirty = False
        self._last_progress_emit = 0.0
        self._last_qt_event_pump = 0.0

    def _choose_progress_callback(self, override_callback):
        """Return an explicit override or fall back to the instance callback.

        Args:
            override_callback: Caller-supplied callback, or ``None``.

        Returns:
            The override if provided, otherwise ``self.progress_callback``.
        """
        return self.progress_callback or override_callback

    def _resolve_cpu_threads(self) -> int:
        """Resolve how many worker threads to spin up based on config and hardware.

        Returns:
            int: Planned worker count honoring ``app_config`` constraints.
        """
        cpu_threads = max(1, os.cpu_count() // 2)
        if not self.app_config:
            return cpu_threads

        try:
            resource_limits = self.app_config.settings.get("resource_limits", {})
            cpu_cores_val = resource_limits.get("cpu_cores", "auto")

            if cpu_cores_val != "auto":
                configured_threads = int(cpu_cores_val)
                cpu_threads = max(1, min(configured_threads, os.cpu_count()))
            else:
                cpu_threads = max(1, os.cpu_count() // 2)
        except (ValueError, TypeError, KeyError):
            cpu_threads = max(1, os.cpu_count() // 2)
        return cpu_threads

    def _resolve_memory_limit(self) -> int:
        """Return the configured memory threshold in megabytes.

        Reads ``resource_limits.memory_limit_mb`` from ``app_config``. Returns
        ``0`` when no limit is configured or if reading the value fails.
        """

        if not self.app_config:
            return 0

        try:
            resource_limits = self.app_config.settings.get("resource_limits", {})
            limit_value = resource_limits.get("memory_limit_mb", 0)
            return max(0, int(limit_value or 0))
        except (ValueError, TypeError, KeyError, AttributeError):
            return 0

    def _memory_budget_enabled(self) -> bool:
        """Check whether memory-based worker throttling is active.

        Returns:
            ``True`` when a non-zero limit is set and ``psutil`` is available.
        """

        return bool(self._memory_limit_mb and psutil is not None)

    def _get_process_memory_usage_mb(self) -> float:
        """Query the current Resident Set Size of this process.

        RSS represents the portion of memory held in RAM. The value is
        returned in megabytes. Returns ``0.0`` when throttling is disabled.
        """

        if not self._memory_budget_enabled():
            return 0.0

        try:
            if self._psutil_process is None:
                self._psutil_process = psutil.Process(os.getpid())
            rss = self._psutil_process.memory_info().rss
        except psutil.Error:
            self._psutil_process = psutil.Process(os.getpid())
            rss = self._psutil_process.memory_info().rss

        return rss / (1024 * 1024)

    def _maybe_collect_garbage(self, *, force: bool = False) -> None:
        """Run garbage collection with a cooldown to reduce memory pressure.

        Args:
            force: Bypass the cooldown interval and collect immediately.
        """

        if not self._memory_budget_enabled():
            return

        now = time.monotonic()
        if force or (now - self._last_gc_collect) >= self._gc_collect_interval:
            gc.collect()
            self._last_gc_collect = now

    def wait_for_memory_budget(self) -> bool:
        """Block until process memory drops below the configured threshold.

        Uses hysteresis so workers resume only after memory falls to 85-96%
        of the limit (whichever is lower). Periodically triggers garbage
        collection while waiting.

        Returns:
            ``True`` when memory is within budget, ``False`` on cancellation.
        """

        if not self._memory_budget_enabled():
            return True

        resume_threshold = max(
            self._memory_limit_mb * self._memory_resume_ratio,
            self._memory_limit_mb - 64,
        )
        overage_start = None

        while True:
            if self.cancel_event.is_set():
                return False

            usage = self._get_process_memory_usage_mb()
            if usage <= max(resume_threshold, self._memory_limit_mb * 0.85):
                self._memory_overage_logged = False
                return True

            if overage_start is None:
                overage_start = time.monotonic()

            elapsed = time.monotonic() - overage_start
            if not self._memory_overage_logged and elapsed > 1.5:
                print(
                    f"[Extractor] Waiting for memory to drop below {self._memory_limit_mb} MB (current {usage:.1f} MB)"
                )
                self._memory_overage_logged = True

            self._maybe_collect_garbage()
            time.sleep(self._memory_check_interval)

    def _after_file_processed(self) -> None:
        """Post-processing hook invoked after each spritesheet completes.

        Forces a garbage collection pass when memory throttling is enabled
        so freed buffers are reclaimed before the next file is dequeued.
        """

        if not self._memory_budget_enabled():
            return
        self._maybe_collect_garbage(force=True)

    @staticmethod
    def _determine_worker_budget(cpu_threads, file_count):
        """Return the smaller of available threads and pending files.

        Args:
            cpu_threads: Maximum threads allowed by hardware/config.
            file_count: Number of files queued for processing.

        Returns:
            Worker count capped to avoid idle threads.
        """
        return min(cpu_threads, file_count)

    def _prioritize_spritesheets(
        self, input_dir: str, filenames: Sequence[str]
    ) -> List[str]:
        """Reorder filenames so heavy spritemap projects process last.

        Adobe spritemap projects are CPU and memory intensive, so deferring
        them reduces peak resource contention when mixed with lighter atlases.

        Args:
            input_dir: Root directory containing atlas files.
            filenames: Unordered sequence of relative paths.

        Returns:
            List with standard atlases first, followed by spritemap projects.
        """

        if not filenames:
            return []

        regular: List[str] = []
        spritemaps: List[str] = []
        for name in filenames:
            try:
                target = (
                    spritemaps
                    if self._looks_like_spritemap(input_dir, name)
                    else regular
                )
            except Exception:
                target = regular
            target.append(name)

        return regular + spritemaps

    @staticmethod
    def _looks_like_spritemap(input_dir: str, filename: str) -> bool:
        """Detect whether a file belongs to an Adobe spritemap project.

        A spritemap project is identified by the presence of both an
        ``Animation.json`` and a matching ``<stem>.json`` in the same folder.

        Args:
            input_dir: Root directory containing atlas files.
            filename: Relative path to the candidate image.

        Returns:
            ``True`` when companion metadata files exist, ``False`` otherwise.
        """

        atlas_path = Path(input_dir) / Path(filename)
        atlas_dir = atlas_path.parent
        base_name = atlas_path.stem
        animation_json = atlas_dir / "Animation.json"
        spritemap_json = atlas_dir / f"{base_name}.json"
        return animation_json.is_file() and spritemap_json.is_file()

    def _start_worker_pool(
        self,
        max_threads,
        input_dir,
        output_dir,
        parent_window,
    ):
        """Spawn worker threads and wire up their signals.

        Args:
            max_threads: Number of workers to create.
            input_dir: Root folder for atlas files.
            output_dir: Destination folder for exports.
            parent_window: UI parent for modal dialogs.
        """
        if not max_threads:
            return

        self._planned_worker_count = max_threads

        for i in range(max_threads):
            worker = FileProcessorWorker(
                input_dir,
                output_dir,
                parent_window,
                self,
                self.file_queue,
            )

            label = f"Worker {i + 1}"
            worker.setObjectName(label)
            self._worker_labels[worker] = label

            worker.file_completed.connect(self._on_file_completed)
            worker.file_failed.connect(self._on_file_failed)
            worker.task_started.connect(
                lambda filename, w=worker: self._on_worker_task_started(w, filename)
            )
            worker.task_finished.connect(
                lambda filename, w=worker: self._on_worker_task_finished(w, filename)
            )
            worker.finished.connect(lambda w=worker: self._worker_finished(w))

            self.active_workers.append(worker)
            worker.start()

    def _monitor_workers(self) -> None:
        """Drain statistics queue and update progress until workers finish.

        Uses blocking waits with timeouts to reduce idle spin while keeping
        the UI responsive. Exits once all workers signal completion and the
        stats queue is empty.
        """
        while True:
            if self.cancel_event.is_set():
                self._capture_cancel_reason()
                self._wake_workers()
            processed = self._drain_stats_queue()
            if not processed:
                timeout = self._compute_wait_timeout()
                if self.cancel_event.is_set():
                    timeout = min(timeout, 0.02)
                woke_for_stats = self._stats_available_event.wait(timeout)
                if not woke_for_stats:
                    self._maybe_process_qt_events(force=True)
                else:
                    self._maybe_process_qt_events()
            else:
                self._maybe_process_qt_events()

            self._update_progress_text()

            if self._workers_done_event.is_set() and self._stats_queue_empty():
                break

        self._drain_stats_queue()
        self._update_progress_text(force=True)

    @staticmethod
    def _process_qt_events() -> None:
        """Pump pending UI events so the interface stays responsive."""
        app = QCoreApplication.instance()
        if app is not None:
            QCoreApplication.processEvents()

    def _maybe_process_qt_events(self, *, force: bool = False) -> None:
        """Throttle event processing so high-volume batches do not starve the UI.

        Args:
            force: When ``True``, bypass throttling and pump events immediately.
        """
        now = time.monotonic()
        if force or (now - self._last_qt_event_pump) >= self._qt_event_interval:
            self._process_qt_events()
            self._last_qt_event_pump = now

    def _compute_wait_timeout(self) -> float:
        """Pick the next wait duration based on queued work and worker state.

        Returns:
            Timeout in seconds, shorter when work is in progress.
        """
        active_tasks = len(self.work_in_progress)
        if active_tasks:
            return 0.015
        if self.active_workers:
            return 0.05
        return 0.08

    def _finalize_directory_processing(self) -> None:
        """Capture timing and aggregate stats once all workers have stopped.

        Stores elapsed duration and totals in instance attributes for later
        retrieval by UI components or diagnostics.
        """
        end_time = time.time()
        duration = end_time - self.start_time
        self._last_processing_finished = end_time
        self._last_processing_duration = duration
        self._last_processing_totals = (
            self.total_frames_generated,
            self.total_anims_generated,
            self.total_sprites_failed,
        )

    def request_cancel(self, reason: Optional[str] = None) -> None:
        """Set the cancel flag, wake workers, and optionally note the reason.

        Args:
            reason (str | None): Human-readable message describing why work stopped.
        """
        if reason and not self._cancel_reason:
            self._cancel_reason = reason
        if reason:
            setattr(self.cancel_event, "reason", reason)
        if self.cancel_event.is_set():
            self._wake_workers()
            return
        self.cancel_event.set()
        self._resume_workers()
        self._wake_workers()

    def _capture_cancel_reason(self) -> None:
        """Mirror the event's reason attribute so we can surface it later."""
        if self.cancel_event.is_set() and not self._cancel_reason:
            self._cancel_reason = getattr(self.cancel_event, "reason", None)

    def _wake_workers(self) -> None:
        """Push sentinel work items so blocked workers break out quickly."""
        if getattr(self, "file_queue", None) is None:
            return
        if getattr(self, "_cancel_wake_sent", False):
            return
        sentinel_count = (
            self._planned_worker_count or len(getattr(self, "active_workers", [])) or 1
        )
        try:
            for _ in range(sentinel_count):
                self.file_queue.put(None)
        finally:
            self._cancel_wake_sent = True

    def _raise_if_cancelled(self) -> None:
        """Abort the current operation if a cancellation was requested."""
        if self.cancel_event.is_set():
            self._capture_cancel_reason()
            reason = self._cancel_reason or "Processing cancelled"
            raise ExtractionCancelled(reason)

    def wait_for_resume(self) -> bool:
        """Block workers while paused and exit early if cancellation occurs.

        Returns:
            bool: ``True`` when resume occurs, ``False`` if cancellation intervenes.
        """
        while True:
            if self.cancel_event.is_set():
                return False
            if self._pause_event.wait(timeout=0.05):
                if self.cancel_event.is_set():
                    return False
                return True

    def _pause_workers(self) -> None:
        """Clear the pause event so workers temporarily yield the CPU."""
        if self._pause_event.is_set():
            self._pause_event.clear()

    def _resume_workers(self) -> None:
        """Allow paused workers to resume by setting the pause event."""
        if not self._pause_event.is_set():
            self._pause_event.set()

    def _handle_worker_error_prompt(self, filename: str, error: BaseException) -> bool:
        """Synchronously ask the UI whether processing should continue after errors.

        Args:
            filename (str): File being processed when the failure occurred.
            error (BaseException): Exception raised by the worker thread.

        Returns:
            bool: ``True`` when the user chooses to continue, ``False`` otherwise.
        """
        if not self.error_prompt_callback:
            return False
        with self._error_prompt_lock:
            if self._awaiting_error_decision:
                return False
            self._awaiting_error_decision = True

        continue_processing = False
        try:
            self._pause_workers()
            continue_processing = bool(self.error_prompt_callback(filename, error))
        except Exception as prompt_exc:
            print(
                f"[_handle_worker_error_prompt] Failed to prompt on error: {prompt_exc}"
            )
            continue_processing = False
        finally:
            with self._error_prompt_lock:
                self._awaiting_error_decision = False
            if continue_processing:
                self._resume_workers()

        return continue_processing

    def _queue_stats_update(
        self,
        *,
        frames_delta: int = 0,
        anims_delta: int = 0,
        failed_delta: int = 0,
        processed_delta: int = 1,
        debug_message: Optional[str] = None,
    ) -> None:
        """Push a stats delta into the queue consumed by the monitor thread.

        Args:
            frames_delta (int): Change in exported frame count.
            anims_delta (int): Change in exported animation count.
            failed_delta (int): Change in failure count.
            processed_delta (int): Increment applied to processed file count.
            debug_message (str | None): Optional trace string for verbose logging.
        """

        update: StatsUpdate = {
            "frames_delta": frames_delta,
            "anims_delta": anims_delta,
            "failed_delta": failed_delta,
            "processed_delta": processed_delta,
            "debug_message": debug_message,
        }
        self._stats_queue.put(update)
        if hasattr(self, "_stats_available_event"):
            self._stats_available_event.set()

    def _drain_stats_queue(self) -> bool:
        """Flush pending stats updates and apply them sequentially.

        Returns:
            bool: ``True`` when at least one update was processed.
        """
        processed = False
        while True:
            try:
                update = self._stats_queue.get(block=False)
            except Empty:
                break
            self._apply_stats_update(update)
            processed = True

        if processed:
            self._update_progress_text()

        if not self._stats_queue_empty() and hasattr(self, "_stats_available_event"):
            # Leave event set so waiters wake immediately for remaining items.
            pass
        elif hasattr(self, "_stats_available_event"):
            self._stats_available_event.clear()

        return processed

    def _stats_queue_empty(self) -> bool:
        """Return ``True`` when no pending stats updates remain."""
        return self._stats_queue.empty()

    def _apply_stats_update(self, update: StatsUpdate) -> None:
        """Update global counters and emit statistics callbacks for a delta.

        Args:
            update (StatsUpdate): Queued dictionary describing counter deltas.
        """

        frames_delta = int(update.get("frames_delta", 0))
        anims_delta = int(update.get("anims_delta", 0))
        failed_delta = int(update.get("failed_delta", 0))

        processed_delta = int(update.get("processed_delta", 0))

        self.total_frames_generated += frames_delta
        self.total_anims_generated += anims_delta
        self.total_sprites_failed += failed_delta
        self.processed_count += processed_delta

        stats_snapshot = (
            self.total_frames_generated,
            self.total_anims_generated,
            self.total_sprites_failed,
        )

        if self._trace_stats:
            print(
                f"[_apply_stats_update] Totals: {stats_snapshot[0]} frames, {stats_snapshot[1]} anims, {stats_snapshot[2]} failed"
            )

        if self.statistics_callback:
            self.statistics_callback(*stats_snapshot)

        self._progress_dirty = True

    def _on_worker_task_started(self, worker: QThread, filename: str) -> None:
        """Record which worker claimed a file so progress summaries stay accurate.

        Args:
            worker (QThread): Worker instance that began processing.
            filename (str): Path claimed by the worker.
        """
        if worker:
            self.work_in_progress[worker] = filename
        if filename:
            self._last_started_file = str(filename)
        self._progress_dirty = True
        self._update_progress_text(force=True)

    def _on_worker_task_finished(self, worker: QThread, filename: str) -> None:
        """Drop worker bookkeeping once a file completes.

        Args:
            worker: Worker instance that finished its task.
            filename: Path that was being processed.
        """
        if worker in self.work_in_progress:
            self.work_in_progress.pop(worker, None)
        self._progress_dirty = True
        self._update_progress_text(force=True)

    def _update_progress_text(self, *, force: bool = False) -> None:
        """Emit throttled progress updates with human-friendly worker summaries.

        Args:
            force: When ``True``, bypass throttling and emit immediately.
        """
        if not self._progress_callback:
            return

        if not force and not self._progress_dirty:
            return

        now = time.monotonic()
        if (
            not force
            and (now - self._last_progress_emit) < self._progress_emit_interval
        ):
            return

        snapshot = self._build_worker_status_snapshot()
        summary_text = snapshot.get("summary") if snapshot else ""
        if summary_text:
            current_files_text = summary_text
        elif self.active_workers:
            current_files_text = "Initializing..."
        else:
            current_files_text = "Completing..."

        total = getattr(self, "total_files", 0)
        if snapshot is not None:
            snapshot["fallback"] = current_files_text
        self._progress_callback(
            self.processed_count, total, snapshot or current_files_text
        )
        self._progress_dirty = False
        self._last_progress_emit = now

    def _build_worker_status_snapshot(self, limit: int = 4) -> Dict[str, Any]:
        """Capture a structured snapshot of worker state for the UI overlay.

        Args:
            limit: Maximum number of workers to include in the ``workers`` list.

        Returns:
            Dictionary containing ``summary``, ``workers``, and metadata keys.
        """
        worker_rows: List[Dict[str, Any]] = []
        processing_count = 0

        for idx, worker in enumerate(self.active_workers):
            label = self._worker_labels.get(worker, f"Worker {idx + 1}")
            current = self.work_in_progress.get(worker)
            display_name = Path(current).name if current else "idle"
            if current:
                processing_count += 1
            worker_rows.append(
                {
                    "label": label,
                    "display": display_name,
                    "path": str(current) if current else "",
                    "state": "processing" if current else "idle",
                }
            )

        worker_count = len(self.active_workers)
        if worker_count:
            summary = self._format_worker_summary(processing_count, worker_count)
        else:
            summary = "No workers active"

        recent_full_path = self._last_started_file
        recent_display = Path(recent_full_path).name if recent_full_path else None

        return {
            "summary": summary,
            "workers": worker_rows,
            "hidden_count": 0,
            "worker_count": worker_count,
            "recent_full_path": recent_full_path,
            "recent_display": recent_display,
        }

    @staticmethod
    def _format_worker_summary(processing_count: int, worker_count: int) -> str:
        """Format a concise summary string describing worker utilization.

        Args:
            processing_count: Number of workers currently processing files.
            worker_count: Total number of active worker threads.

        Returns:
            Human-readable status like "2 workers running (of 4 total workers)".
        """
        running_plural = "s" if processing_count != 1 else ""
        total_plural = "s" if worker_count != 1 else ""
        return (
            f"{processing_count} worker{running_plural} running "
            f"(of {worker_count} total worker{total_plural})"
        )

    def _on_file_completed(
        self, filename: str, result: Optional[Dict[str, int]]
    ) -> None:
        """Handle successful file completion by relaying stats deltas.

        Args:
            filename (str): Processed file path.
            result (dict[str, int] | None): Result payload from the worker thread.
        """
        debug_message = None
        frames_added = 0
        anims_added = 0
        failed_added = 0

        if result:
            frames_added = result.get("frames_generated", 0)
            anims_added = result.get("anims_generated", 0)
            failed_added = result.get("sprites_failed", 0)
        else:
            failed_added = 1

        self._queue_stats_update(
            frames_delta=frames_added,
            anims_delta=anims_added,
            failed_delta=failed_added,
            processed_delta=1,
            debug_message=debug_message,
        )

    def _on_file_failed(self, filename: str, error: BaseException | str) -> None:
        """Handle file processing failure and decide whether to abort.

        Args:
            filename (str): File that failed to process.
            error (BaseException | str): Failure details for logging and prompts.
        """
        print(f"Error processing {filename}: {error}")

        self._queue_stats_update(failed_delta=1, processed_delta=1)
        if self._handle_worker_error_prompt(filename, error):
            return

        reason_template = QCoreApplication.translate(
            self.__class__.__name__,
            "Processing halted due to an error in {filename}",
        )
        self.request_cancel(reason=reason_template.format(filename=Path(filename).name))

    def _worker_finished(self, worker: QThread) -> None:
        """Handle worker shutdown once it has consumed its sentinel.

        Args:
            worker (QThread): Worker thread that just emitted ``finished``.
        """
        if worker in self.active_workers:
            worker.wait()
            worker.deleteLater()
            self.active_workers.remove(worker)
            self._worker_labels.pop(worker, None)

        self.work_in_progress.pop(worker, None)
        if not self.active_workers:
            self._workers_done_event.set()

        self._progress_dirty = True
        self._update_progress_text(force=True)

    def extract_sprites(
        self,
        atlas_path: str,
        metadata_path: Optional[str],
        output_dir: str,
        settings: Dict[str, Any],
        parent_window: Optional[Any] = None,
        spritesheet_label: Optional[str] = None,
    ) -> Dict[str, int]:
        """Extract sprites and animations from a standard atlas + metadata pair.

        Args:
            atlas_path (str): Path to the source atlas image.
            metadata_path (str | None): Path to metadata or ``None`` for autodetect.
            output_dir (str): Directory receiving exported assets.
            settings (dict): Overrides controlling exports.
            parent_window (Any | None): Parent object for any prompts.
            spritesheet_label (str | None): Friendly name overriding file stem.

        Returns:
            dict[str, int]: Result dictionary containing frame/animation totals and failures.
        """
        frames_generated = 0
        anims_generated = 0
        sprites_failed = 0
        atlas_processor: Optional[AtlasProcessor] = None
        sprite_processor: Optional[SpriteProcessor] = None
        animation_processor: Optional[AnimationProcessor] = None
        animations = None
        result = {
            "frames_generated": 0,
            "anims_generated": 0,
            "sprites_failed": 0,
        }

        try:
            is_unknown_spritesheet = metadata_path is None

            atlas_processor = AtlasProcessor(atlas_path, metadata_path, parent_window)
            sprite_processor = SpriteProcessor(
                atlas_processor.atlas, atlas_processor.sprites
            )
            animations = sprite_processor.process_sprites()
            animation_processor = AnimationProcessor(
                animations,
                atlas_path,
                output_dir,
                self.settings_manager,
                self.current_version,
                spritesheet_label=spritesheet_label,
            )

            frames_generated, anims_generated = animation_processor.process_animations(
                is_unknown_spritesheet
            )
            result["frames_generated"] = frames_generated
            result["anims_generated"] = anims_generated

        except Exception as general_error:
            sprites_failed += 1
            result["sprites_failed"] = sprites_failed
            print(
                f"[extract_sprites] Exception for {atlas_path}: {str(general_error)}, sprites_failed = {sprites_failed}"
            )
            print(
                f"[extract_sprites] Returning error result: frames_generated=0, anims_generated=0, sprites_failed={sprites_failed}"
            )
        finally:
            if animation_processor is not None:
                try:
                    animation_processor.dispose()
                except Exception:
                    pass
            if sprite_processor is not None:
                try:
                    sprite_processor.dispose()
                except Exception:
                    pass
            if atlas_processor is not None:
                try:
                    atlas_processor.close()
                except Exception:
                    pass
            if isinstance(animations, dict):
                animations.clear()
            animations = None
            animation_processor = None
            sprite_processor = None
            atlas_processor = None

        return result

    def extract_spritemap_project(
        self,
        atlas_path: str,
        animation_json_path: str,
        spritemap_json_path: str,
        output_dir: str,
        settings: Dict[str, Any],
        spritesheet_label: Optional[str] = None,
    ) -> Dict[str, int]:
        """Process an Adobe Spritemap project (Animation.json + per-sheet JSON).

        Uses a streaming approach when no editor composites are defined:
        each animation is rendered, exported, and freed before the next one
        begins, keeping peak memory proportional to the largest single
        animation instead of the sum of all animations.

        Falls back to the buffered ``AnimationProcessor`` path when editor
        composites are present (they need cross-animation frame references).

        Args:
            atlas_path (str): Path to atlas image referenced by the project.
            animation_json_path (str): Path to Animation.json.
            spritemap_json_path (str): Path to the per-spritesheet JSON.
            output_dir (str): Directory where exports are stored.
            settings (dict): User overrides controlling export behavior.
            spritesheet_label (str | None): Optional friendly label.

        Returns:
            dict[str, int]: Counts dictionary similar to ``extract_sprites``.
        """
        result: Dict[str, int] = {
            "frames_generated": 0,
            "anims_generated": 0,
            "sprites_failed": 0,
        }
        renderer: Optional[AdobeSpritemapRenderer] = None

        try:
            spritesheet_name = spritesheet_label or os.path.basename(atlas_path)
            renderer = AdobeSpritemapRenderer(
                animation_json_path,
                spritemap_json_path,
                atlas_path,
                filter_single_frame=settings.get(
                    "filter_single_frame_spritemaps", True
                ),
                filter_unused_symbols=settings.get(
                    "filter_unused_spritemap_symbols", False
                ),
                root_animation_only=settings.get(
                    "spritemap_root_animation_only", False
                ),
            )
            renderer.ensure_animation_defaults(self.settings_manager, spritesheet_name)

            if self._has_editor_composites(spritesheet_name):
                self._extract_spritemap_buffered(
                    renderer, atlas_path, output_dir, spritesheet_name, result
                )
            else:
                self._extract_spritemap_streaming(
                    renderer, atlas_path, output_dir, spritesheet_name, result
                )

        except Exception as exc:
            result["sprites_failed"] = result.get("sprites_failed", 0) + 1
            print(f"[extract_spritemap_project] Error processing {atlas_path}: {exc}")
        finally:
            if renderer is not None:
                try:
                    renderer.close()
                except Exception:
                    pass
            renderer = None

        return result

    def _has_editor_composites(self, spritesheet_name: str) -> bool:
        """Check whether any editor composites are defined for this spritesheet."""
        if not self.settings_manager:
            return False
        sheet_settings = self.settings_manager.get_settings(spritesheet_name)
        composites = sheet_settings.get("editor_composites")
        return isinstance(composites, dict) and bool(composites)

    def _extract_spritemap_streaming(
        self,
        renderer: AdobeSpritemapRenderer,
        atlas_path: str,
        output_dir: str,
        spritesheet_name: str,
        result: Dict[str, int],
    ) -> None:
        """Stream animations one at a time — render, export, free.

        Frames are rendered lazily: each PIL image is converted to a NumPy
        array and the PIL image is closed immediately, so at most one
        compact canvas is alive during rendering.  Peak memory during the
        render phase is O(1) per frame instead of O(N).
        """
        resampling_method = self.settings_manager.global_settings.get(
            "resampling_method", "Lanczos"
        )

        def _scale(img, size):
            return scale_image(img, size, resampling_method=resampling_method)

        frame_pipeline = FramePipeline()
        frame_exporter = FrameExporter(output_dir, self.current_version, _scale)
        animation_exporter = AnimationExporter(output_dir, self.current_version, _scale)

        frames_generated = 0
        anims_generated = 0

        for animation_name, frame_iter in renderer.iter_animations():
            # Eagerly consume the lazy frame iterator, converting each
            # PIL image to a numpy array and closing the PIL image so
            # only lightweight numpy arrays accumulate.
            numpy_frames = []
            for frame_name, pil_img, bounds in frame_iter:
                arr = ensure_rgba_array(pil_img)
                pil_img.close()
                numpy_frames.append((frame_name, arr, bounds))

            if not numpy_frames:
                continue

            anim_settings = self.settings_manager.get_settings(
                spritesheet_name, f"{spritesheet_name}/{animation_name}"
            )
            context = frame_pipeline.build_context(
                spritesheet_name,
                animation_name,
                numpy_frames,
                anim_settings,
            )

            if anim_settings.get("fnf_idle_loop") and "idle" in animation_name.lower():
                anim_settings["delay"] = 0

            frame_export = anim_settings.get("frame_export", False)
            if frame_export and anim_settings.get("frame_format") != "None":
                frames_generated += frame_exporter.save_frames(
                    context.frames,
                    context.kept_indices,
                    spritesheet_name,
                    animation_name,
                    anim_settings.get("scale"),
                    anim_settings,
                    False,
                )

            animation_export = anim_settings.get("animation_export", False)
            animation_format = anim_settings.get("animation_format")
            if (
                not context.single_frame
                and animation_export
                and animation_format != "None"
            ):
                anims_generated += animation_exporter.save_animations(
                    context.frames, spritesheet_name, animation_name, anim_settings
                )

            # Free this animation's frames before rendering the next one
            del numpy_frames
            del context
            gc.collect()

        result["frames_generated"] = frames_generated
        result["anims_generated"] = anims_generated

    def _extract_spritemap_buffered(
        self,
        renderer: AdobeSpritemapRenderer,
        atlas_path: str,
        output_dir: str,
        spritesheet_name: str,
        result: Dict[str, int],
    ) -> None:
        """Buffered fallback that loads all animations for editor composite support.

        Editor composites require cross-animation frame references, so the
        full ``AnimationProcessor`` path is used instead of streaming.
        """
        animation_processor: Optional[AnimationProcessor] = None
        animations = None
        try:
            animations = renderer.build_animation_frames()

            if not animations:
                return

            animation_processor = AnimationProcessor(
                animations,
                atlas_path,
                output_dir,
                self.settings_manager,
                self.current_version,
                spritesheet_label=spritesheet_name,
            )
            frames_generated, anims_generated = animation_processor.process_animations()
            result["frames_generated"] = frames_generated
            result["anims_generated"] = anims_generated
        finally:
            if animation_processor is not None:
                try:
                    animation_processor.dispose()
                except Exception:
                    pass
            if isinstance(animations, dict):
                animations.clear()
            animations = None
            animation_processor = None

    def generate_temp_animation_for_preview(
        self,
        atlas_path: str,
        metadata_path: Optional[str],
        settings: Dict[str, Any],
        animation_name: str,
        temp_dir: Optional[str] = None,
        spritemap_info: Optional[Dict[str, Any]] = None,
        spritesheet_label: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a temporary animation file for UI preview.

        Delegates to ``PreviewGenerator`` so preview logic is reusable.

        Args:
            atlas_path: Path to the source atlas.
            metadata_path: Path to metadata, or ``None`` for unknown sheets.
            settings: Export options dict.
            animation_name: Name of the animation to preview.
            temp_dir: Directory for the temporary file.
            spritemap_info: Optional Adobe spritemap project info.
            spritesheet_label: Friendly display name.

        Returns:
            Path to the generated preview file, or ``None`` on failure.
        """
        return self.preview_generator.generate_temp_animation(
            atlas_path,
            metadata_path,
            settings,
            animation_name,
            temp_dir=temp_dir,
            spritemap_info=spritemap_info,
            spritesheet_label=spritesheet_label,
        )

    def _handle_unknown_spritesheets_background_detection(
        self,
        input_dir: str,
        spritesheet_list: Sequence[str],
        parent_window: Optional[Any],
    ) -> Optional[Dict[str, Any]]:
        """Detect background colours for unknown spritesheets.

        Args:
            input_dir: Root directory containing the images.
            spritesheet_list: Filenames to analyse.
            parent_window: UI parent for dialogs.

        Returns:
            Detection results dict, or ``None`` if skipped.
        """
        return self.unknown_handler.handle_background_detection(
            input_dir,
            spritesheet_list,
            parent_window,
        )


class FileProcessorWorker(QThread):
    """Worker thread that pulls filenames from a queue and processes them.

    Emits Qt signals on completion or failure so the main thread can update
    statistics and progress displays.

    Signals:
        file_completed: ``(filename, result_dict)`` on success.
        file_failed: ``(filename, error_str)`` on failure.
        task_started: ``(filename)`` when a file is claimed.
        task_finished: ``(filename)`` when processing ends.
    """

    file_completed = Signal(str, dict)  # filename, result
    file_failed = Signal(str, object)  # filename, error detail
    task_started = Signal(str)
    task_finished = Signal(str)

    tr = translate

    def __init__(
        self,
        input_dir: str,
        output_dir: str,
        parent_window: Optional[Any],
        extractor_instance: Extractor,
        task_queue: SimpleQueue,
    ) -> None:
        """Wire worker thread to shared queues and parent extractor instance.

        Args:
            input_dir (str): Root folder containing atlas files.
            output_dir (str): Destination folder for exported assets.
            parent_window (Any | None): UI parent used for modal dialogs.
            extractor_instance (Extractor): Owning extractor orchestrator.
            task_queue (SimpleQueue): Queue of filenames plus sentinels.
        """
        super().__init__()
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.parent_window = parent_window
        self.extractor = extractor_instance
        self.task_queue = task_queue
        self.current_filename = None

    def run(self) -> None:
        """Pull files from the queue until a sentinel or cancellation.

        Emits ``task_started`` and ``task_finished`` around each file.
        Exits cleanly when the extractor requests cancellation.
        """
        import threading

        thread_id = threading.get_ident()
        while True:
            if not self.extractor.wait_for_resume():
                break

            if not self.extractor.wait_for_memory_budget():
                break

            filename = self.task_queue.get()
            if filename is None or self.extractor.cancel_event.is_set():
                break

            self.current_filename = filename
            self.task_started.emit(filename)
            try:
                if self.extractor.cancel_event.is_set():
                    break
                self._process_single_file(filename, thread_id)
            finally:
                self.task_finished.emit(filename)
                self.current_filename = None

            if self.extractor.cancel_event.is_set():
                break

    def _process_single_file(self, filename: str, thread_id: int) -> None:
        """Process a single atlas file or spritemap project pulled from the queue.

        Args:
            filename (str): Relative filename as enqueued by the orchestrator.
            thread_id (int): Worker thread identifier, useful for diagnostics.
        """
        if self.extractor.cancel_event.is_set():
            self.extractor._after_file_processed()
            return
        try:
            relative_path = Path(filename)
            atlas_path = Path(self.input_dir) / relative_path
            atlas_dir = atlas_path.parent
            base_filename = relative_path.stem
            image_path = str(atlas_path)
            sprite_output_dir = Path(self.output_dir) / relative_path.with_suffix("")
            animation_json_path = atlas_dir / "Animation.json"
            spritemap_json_path = atlas_dir / f"{base_filename}.json"

            os.makedirs(sprite_output_dir, exist_ok=True)
            sprite_output_dir = str(sprite_output_dir)

            has_animation_project = (
                animation_json_path.is_file() and spritemap_json_path.is_file()
            )
            metadata_file = None
            if not has_animation_project:
                metadata_candidates: Dict[str, str] = {}
                try:
                    for candidate in atlas_dir.glob(f"{base_filename}.*"):
                        suffix = candidate.suffix.lower()
                        if suffix in SUPPORTED_METADATA_SUFFIXES:
                            metadata_candidates.setdefault(suffix, str(candidate))
                except Exception:
                    metadata_candidates = {}

                for ext in SUPPORTED_METADATA_EXTENSIONS:
                    chosen = metadata_candidates.get(ext)
                    if chosen:
                        metadata_file = chosen
                        break

            has_metadata = metadata_file is not None
            image_is_supported = filename.lower().endswith(
                (".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp")
            )

            if (
                not has_animation_project
                and not has_metadata
                and not (os.path.isfile(image_path) and image_is_supported)
            ):
                self.file_failed.emit(filename, "No valid processing path found")
                return

            settings = self.extractor.settings_manager.get_settings(filename)

            if has_animation_project:
                result = self.extractor.extract_spritemap_project(
                    image_path,
                    str(animation_json_path),
                    str(spritemap_json_path),
                    sprite_output_dir,
                    settings,
                    spritesheet_label=filename,
                )
                self.file_completed.emit(filename, result)

            elif has_metadata:
                result = self.extractor.extract_sprites(
                    image_path,
                    metadata_file,
                    sprite_output_dir,
                    settings,
                    None,
                    spritesheet_label=filename,
                )
                self.file_completed.emit(filename, result)

            else:
                result = self.extractor.extract_sprites(
                    image_path,
                    None,
                    sprite_output_dir,
                    settings,
                    None,
                    spritesheet_label=filename,
                )
                self.file_completed.emit(filename, result)

        except Exception as e:
            print(f"[FileProcessorWorker] Error processing {filename}: {str(e)}")
            import traceback

            traceback.print_exc()
            self.file_failed.emit(filename, e)
        finally:
            self.extractor._after_file_processed()
