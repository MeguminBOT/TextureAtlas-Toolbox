"""Utility modules for background tasks and user preferences.

Provides thread-safe workers for long-running operations and persistent
storage for user settings like shortcuts, API keys, and theme choices.
"""

from .background_tasks import BackgroundTaskWorker, BackgroundTaskSignals

__all__ = [
    "BackgroundTaskWorker",
    "BackgroundTaskSignals",
]
