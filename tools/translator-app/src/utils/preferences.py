"""User preferences persistence for the translator application.

Stores and retrieves settings (dark mode, translations folder, keyboard
shortcuts, API keys) from a JSON file in the user's home directory.
Defaults are provided for all settings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

_PREFERENCES_PATH = Path.home() / ".textureatlastoolbox_translator.json"

# Default keyboard shortcuts for editor actions
DEFAULT_SHORTCUTS: Dict[str, str] = {
    "copy_source": "Ctrl+Shift+C",
    "auto_translate": "Ctrl+T",
    "search": "Ctrl+F",
    "next_item": "Ctrl+Down",
    "prev_item": "Ctrl+Up",
    "mark_none": "Ctrl+Shift+0",
    "mark_unsure": "Ctrl+Shift+1",
    "mark_machine": "Ctrl+Shift+2",
    "mark_complete": "Ctrl+Shift+3",
}

# Default API keys (empty strings, user must configure)
DEFAULT_API_KEYS: Dict[str, str] = {
    "deepl_api_key": "",
    "deepl_api_endpoint": "",  # Leave empty for free API, set for Pro
    "google_translate_api_key": "",
    "libretranslate_endpoint": "",
    "libretranslate_api_key": "",
}

# Default theme/appearance settings
DEFAULT_THEME: Dict[str, Any] = {
    "dark_mode": False,
    "icon_style": "simplified",
    "custom_icons_path": "",
}

# All default preferences combined
DEFAULT_PREFERENCES: Dict[str, Any] = {
    "translations_folder": "",
    "shortcuts": DEFAULT_SHORTCUTS,
    "api_keys": DEFAULT_API_KEYS,
    **DEFAULT_THEME,
}


def get_shortcuts(preferences: Dict[str, Any]) -> Dict[str, str]:
    """Retrieve keyboard shortcuts from preferences with defaults.

    Args:
        preferences: The loaded preferences dictionary.

    Returns:
        A dictionary mapping shortcut keys to their key sequence strings.
    """
    stored = preferences.get("shortcuts", {})
    if not isinstance(stored, dict):
        stored = {}
    # Merge with defaults to ensure all keys exist
    result = DEFAULT_SHORTCUTS.copy()
    result.update(stored)
    return result


def get_api_keys(preferences: Dict[str, Any]) -> Dict[str, str]:
    """Retrieve API keys from preferences with defaults.

    Args:
        preferences: The loaded preferences dictionary.

    Returns:
        A dictionary mapping API key names to their values.
    """
    stored = preferences.get("api_keys", {})
    if not isinstance(stored, dict):
        stored = {}
    result = DEFAULT_API_KEYS.copy()
    result.update(stored)
    return result


def load_preferences() -> Dict[str, Any]:
    """Return stored user preferences, merged with defaults.

    Missing keys are filled in from DEFAULT_PREFERENCES to ensure
    all expected settings exist.

    Returns:
        A dictionary containing all preference keys with their current values.
    """
    defaults = DEFAULT_PREFERENCES.copy()
    defaults["shortcuts"] = DEFAULT_SHORTCUTS.copy()
    defaults["api_keys"] = DEFAULT_API_KEYS.copy()

    if not _PREFERENCES_PATH.exists():
        return defaults

    try:
        raw = _PREFERENCES_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return defaults

    if not isinstance(data, dict):
        return defaults

    # Merge stored data with defaults (stored values take precedence)
    result = defaults.copy()
    for key, value in data.items():
        if key == "shortcuts" and isinstance(value, dict):
            result["shortcuts"] = {**DEFAULT_SHORTCUTS, **value}
        elif key == "api_keys" and isinstance(value, dict):
            result["api_keys"] = {**DEFAULT_API_KEYS, **value}
        else:
            result[key] = value

    return result


def save_preferences(preferences: Dict[str, Any]) -> None:
    """Persist user preferences to disk.

    Args:
        preferences: The complete preferences dictionary to save.
    """
    try:
        _PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(preferences, indent=2, sort_keys=True)
        _PREFERENCES_PATH.write_text(serialized, encoding="utf-8")
    except OSError:
        pass


__all__ = [
    "load_preferences",
    "save_preferences",
    "get_shortcuts",
    "get_api_keys",
    "DEFAULT_SHORTCUTS",
    "DEFAULT_API_KEYS",
    "DEFAULT_THEME",
    "DEFAULT_PREFERENCES",
]
