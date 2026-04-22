#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Centralized logging configuration for TextureAtlas Toolbox.

Provides a single setup point that wires Python's :mod:`logging` to both
stderr (so users see live status) and a timestamped file under ``logs/``
(so users can attach the file to bug reports). Modules elsewhere just call
:func:`get_logger` and use the returned logger instance.

Usage:
    from utils.logger import get_logger

    logger = get_logger(__name__)
    logger.info("Starting work")
    logger.warning("Recoverable issue: %s", detail)
    try:
        risky()
    except Exception:
        logger.exception("Unexpected failure in risky()")
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Module-level state so setup is idempotent across re-imports / spawned procs.
_LOG_INITIALIZED = False
_LOG_FILE_PATH: Optional[Path] = None

# Format used for both stderr and file output. Compact enough for terminals,
# detailed enough that users can paste it into bug reports without losing
# context (timestamp + level + logger name + message).
_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Keep the most recent N log files; older ones are deleted on startup so the
# logs/ directory does not grow without bound.
_MAX_LOG_FILES = 20

# Per-file size cap for the rotating handler. Above this the handler will
# rotate within the same session (rare; mainly defends against runaway loops).
_MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3


def _resolve_logs_dir() -> Path:
    """Locate the project-level ``logs/`` directory and create it if missing.

    Mirrors the discovery logic used by ``update_installer._setup_log_file``
    so the main app and the updater write into the same folder regardless of
    whether the app is running from source, from a Nuitka-compiled binary,
    or from an embedded-Python portable build.

    Returns:
        Path to the existing (now-created) ``logs/`` directory.
    """
    if "__compiled__" in globals() or getattr(sys, "frozen", False):
        # Nuitka / PyInstaller: logs sit beside the executable.
        app_dir = Path(sys.executable).parent
    else:
        # Source layout: this file lives in src/utils/logger.py, so logs/
        # is two parents up from this file.
        app_dir = Path(__file__).resolve().parent.parent.parent

    logs_dir = app_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _prune_old_logs(logs_dir: Path) -> None:
    """Delete oldest ``app_*.log`` files beyond ``_MAX_LOG_FILES``.

    Best-effort: any errors are swallowed because logging must never crash
    the application during startup.
    """
    try:
        app_logs = sorted(
            logs_dir.glob("app_*.log"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in app_logs[_MAX_LOG_FILES:]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


def setup_logging(
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> Optional[Path]:
    """Configure the root logger with stderr + rotating file handlers.

    Safe to call multiple times — subsequent calls are no-ops. Should be
    called as early as possible in the application entry point (after Qt
    environment configuration but before importing modules that log on
    import).

    Args:
        console_level: Minimum severity that reaches stderr (default INFO).
        file_level: Minimum severity that reaches the log file (default
            DEBUG so bug reports include full context).

    Returns:
        Path to the active log file, or ``None`` if file logging could not
        be set up (in which case stderr-only logging still works).
    """
    global _LOG_INITIALIZED, _LOG_FILE_PATH
    if _LOG_INITIALIZED:
        return _LOG_FILE_PATH

    root = logging.getLogger()
    # Use the lower of the two levels as the root threshold so handlers can
    # filter independently.
    root.setLevel(min(console_level, file_level))

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # --- stderr handler: keeps console output flowing for users running
    # the app from a terminal (and for Nuitka console builds).
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setLevel(console_level)
    stderr_handler.setFormatter(formatter)
    root.addHandler(stderr_handler)

    # --- file handler: per-launch timestamped file under logs/.
    log_file: Optional[Path] = None
    try:
        logs_dir = _resolve_logs_dir()
        _prune_old_logs(logs_dir)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = logs_dir / f"app_{timestamp}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=_MAX_LOG_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
            delay=True,
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except (OSError, PermissionError) as exc:
        # File logging is best-effort. Surface the failure on stderr so the
        # user notices, but do not raise — the app should still run.
        logging.getLogger(__name__).warning(
            "Could not initialize file logging: %s", exc
        )
        log_file = None

    # Capture otherwise-unhandled exceptions so crash logs end up in the
    # log file too. KeyboardInterrupt is left to Python's default handler so
    # Ctrl+C still terminates cleanly.
    def _excepthook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logging.getLogger("uncaught").critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )

    sys.excepthook = _excepthook

    # Silence chatty third-party libraries that flood DEBUG with per-chunk
    # noise (e.g. PIL emits a STREAM line for every PNG IDAT block, which
    # makes our own DEBUG output unreadable). Pin them at WARNING so real
    # warnings still surface.
    for noisy in ("PIL", "PIL.PngImagePlugin", "PIL.Image", "urllib3", "matplotlib"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _LOG_INITIALIZED = True
    _LOG_FILE_PATH = log_file
    logging.getLogger(__name__).info(
        "Logging initialized (file=%s)", log_file if log_file else "<stderr only>"
    )
    return log_file


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, initializing the logging system on first use.

    Modules should call this at import time::

        from utils.logger import get_logger
        logger = get_logger(__name__)

    Args:
        name: Logger name, typically ``__name__``.

    Returns:
        A :class:`logging.Logger` instance bound to ``name``.
    """
    if not _LOG_INITIALIZED:
        # Lazy-init so modules imported before Main calls setup_logging()
        # still get working loggers (they'll just attach to a default config
        # that Main's later setup_logging() call leaves alone).
        setup_logging()
    return logging.getLogger(name)


def get_log_file_path() -> Optional[Path]:
    """Return the path of the active log file, or ``None`` if unavailable.

    Useful for displaying the location to the user (e.g. in an "About" or
    "Report a bug" dialog).
    """
    return _LOG_FILE_PATH
