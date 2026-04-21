"""Hierarchical settings manager for spritesheets and animations.

Provides a three-tier settings hierarchy: global defaults, per-spritesheet
overrides, and per-animation overrides. When retrieving settings, values
merge from global → spritesheet → animation, with later tiers taking
precedence.
"""

import os


class SettingsManager:
    """Manages layered settings for spritesheets and animations.

    Settings cascade from global defaults through spritesheet-specific values
    to animation-specific overrides.

    Attributes:
        global_settings: Default settings applied to all sprites and animations.
        spritesheet_settings: Per-spritesheet setting overrides keyed by filename.
        animation_settings: Per-animation setting overrides keyed by animation name.
    """

    def __init__(self) -> None:
        """Initialize with empty settings dictionaries."""

        self.global_settings: dict = {}
        self.spritesheet_settings: dict = {}
        self.animation_settings: dict = {}

    def set_global_settings(self, **kwargs) -> None:
        """Update global settings with the provided key-value pairs.

        Args:
            **kwargs: Setting names and values to merge into global settings.
        """

        self.global_settings.update(kwargs)

    def set_spritesheet_settings(self, spritesheet_name: str, **kwargs) -> None:
        """Set or replace settings for a specific spritesheet.

        If no settings are provided, any existing entry for the spritesheet
        is removed.

        Args:
            spritesheet_name: Identifier for the spritesheet (typically filename).
            **kwargs: Setting names and values to store.
        """

        if kwargs:
            self.spritesheet_settings[spritesheet_name] = dict(kwargs)
        else:
            self.spritesheet_settings.pop(spritesheet_name, None)

    def set_animation_settings(self, animation_name: str, **kwargs) -> None:
        """Set or replace settings for a specific animation.

        If no settings are provided, any existing entry for the animation
        is removed.

        Args:
            animation_name: Identifier for the animation.
            **kwargs: Setting names and values to store.
        """

        if kwargs:
            self.animation_settings[animation_name] = dict(kwargs)
        else:
            self.animation_settings.pop(animation_name, None)

    def delete_spritesheet_settings(self, spritesheet_name: str) -> None:
        """Remove stored settings for a spritesheet if present.

        Args:
            spritesheet_name: Identifier for the spritesheet to remove.
        """

        if spritesheet_name in self.spritesheet_settings:
            del self.spritesheet_settings[spritesheet_name]

    def delete_animation_settings(self, animation_name: str) -> None:
        """Remove stored settings for an animation if present.

        Args:
            animation_name: Identifier for the animation to remove.
        """

        if animation_name in self.animation_settings:
            del self.animation_settings[animation_name]

    def get_parent_settings(self, settings_type: str, spritesheet_name: str) -> dict:
        """Return the settings a local override would inherit.

        For spritesheet overrides the parent is the global settings.
        For animation overrides the parent is global + spritesheet settings.

        Args:
            settings_type: Either ``"spritesheet"`` or ``"animation"``.
            spritesheet_name: Spritesheet filename used to look up
                spritesheet-level overrides when *settings_type* is
                ``"animation"``.

        Returns:
            A settings dict representing the inherited values.
        """

        parent = self.global_settings.copy()
        if settings_type == "animation":
            ss_settings = self.spritesheet_settings.get(spritesheet_name)
            if not ss_settings:
                basename = os.path.basename(spritesheet_name)
                if basename != spritesheet_name:
                    ss_settings = self.spritesheet_settings.get(basename)
            parent.update(ss_settings or {})
        return parent

    def get_settings(self, filename: str, animation_name: str | None = None) -> dict:
        """Retrieve merged settings for a spritesheet or animation.

        Builds a settings dictionary by layering global defaults, then
        spritesheet overrides, then animation overrides. Lookups fall back
        to basename matching if a full path doesn't match stored keys.

        Args:
            filename: Spritesheet filename or path.
            animation_name: Optional animation identifier for animation-level
                settings.

        Returns:
            Merged settings dictionary with all applicable overrides applied.
        """

        settings = self.global_settings.copy()

        spritesheet_settings = self.spritesheet_settings.get(filename)
        if not spritesheet_settings:
            basename = os.path.basename(filename)
            if basename != filename:
                spritesheet_settings = self.spritesheet_settings.get(basename)
        settings.update(spritesheet_settings or {})

        if animation_name:
            animation_settings = self.animation_settings.get(animation_name)
            if not animation_settings:
                normalized = animation_name.replace("\\", "/")
                if "/" in normalized:
                    prefix, suffix = normalized.rsplit("/", 1)
                    fallback_name = f"{os.path.basename(prefix)}/{suffix}"
                    animation_settings = self.animation_settings.get(fallback_name)
            settings.update(animation_settings or {})

        return settings
