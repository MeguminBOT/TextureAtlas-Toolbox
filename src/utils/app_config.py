"""Persistent application configuration backed by a JSON file."""

import os
import json


class AppConfig:
    """Manage persistent application settings stored in a JSON file.

    Attributes:
        DEFAULTS: Default values for all configuration keys.
        TYPE_MAP: Expected Python types for each setting key.
        config_path: Filesystem path to the configuration file.
        settings: Current settings dictionary.
    """

    DEFAULTS = {
        "first_run_completed": False,
        "language": "auto",
        "resource_limits": {
            "cpu_cores": "auto",
            "memory_limit_mb": 0,
        },
        "extraction_defaults": {
            "animation_format": "GIF",
            "animation_export": False,
            "duration": 42,
            "duration_display_value": 24,
            "duration_display_type": "fps",
            "delay": 250,
            "period": 0,
            "scale": 1.0,
            "threshold": 0.5,
            "resampling_method": "Nearest",
            "frame_selection": "all",
            "crop_option": "animation",
            "filename_format": "standardized",
            "filename_prefix": "",
            "filename_suffix": "",
            "frame_format": "PNG",
            "frame_export": False,
            "frame_scale": 1.0,
            "variable_delay": False,
            "fnf_idle_loop": False,
        },
        "compression_defaults": {
            "png": {
                "compress_level": 9,
                "optimize": True,
            },
            "webp": {
                "lossless": True,
                "quality": 90,
                "method": 3,
                "alpha_quality": 90,
                "exact": True,
            },
            "avif": {
                "lossless": True,
                "quality": 90,
                "speed": 5,
            },
            "tiff": {
                "compression_type": "lzw",
                "quality": 90,
                "optimize": True,
            },
        },
        "update_settings": {
            "check_updates_on_startup": True,
            "auto_download_updates": False,
        },
        "generator_defaults": {
            "algorithm": "auto",
            "heuristic": "auto",
            "max_size": 4096,
            "padding": 2,
            "power_of_two": False,
            "allow_rotation": False,
            "allow_flip": False,
            "trim_sprites": False,
            "export_format": "starling-xml",
            "image_format": "PNG",
        },
        "editor_settings": {
            "origin_mode": "center",
        },
        "interface": {
            "last_input_directory": "",
            "last_output_directory": "",
            "remember_input_directory": True,
            "remember_output_directory": True,
            "filter_single_frame_spritemaps": True,
            "filter_unused_spritemap_symbols": False,
            "spritemap_root_animation_only": False,
            "use_native_file_dialog": False,
            "merge_duplicate_frames": True,
            "duration_input_type": "fps",
            "color_scheme": "auto",
        },
    }

    TYPE_MAP = {
        "language": str,
        "animation_format": str,
        "animation_export": bool,
        "duration": int,
        "delay": int,
        "period": int,
        "scale": float,
        "threshold": float,
        "crop_option": str,
        "frame_selection": str,
        "filename_format": str,
        "filename_prefix": str,
        "filename_suffix": str,
        "frame_format": str,
        "frame_export": bool,
        "frame_scale": float,
        "resampling_method": str,
        "variable_delay": bool,
        "fnf_idle_loop": bool,
        "check_updates_on_startup": bool,
        "auto_download_updates": bool,
        "png_compress_level": int,
        "png_optimize": bool,
        "webp_lossless": bool,
        "webp_quality": int,
        "webp_method": int,
        "webp_alpha_quality": int,
        "webp_exact": bool,
        "avif_lossless": bool,
        "avif_quality": int,
        "avif_speed": int,
        "tiff_compression_type": str,
        "tiff_quality": int,
        "tiff_optimize": bool,
        "gen_algorithm": str,
        "gen_heuristic": str,
        "gen_max_size": int,
        "gen_padding": int,
        "gen_power_of_two": bool,
        "gen_allow_rotation": bool,
        "gen_allow_flip": bool,
        "gen_trim_sprites": bool,
        "gen_export_format": str,
        "gen_image_format": str,
        "last_input_directory": str,
        "last_output_directory": str,
        "remember_input_directory": bool,
        "remember_output_directory": bool,
        "filter_single_frame_spritemaps": bool,
        "filter_unused_spritemap_symbols": bool,
        "spritemap_root_animation_only": bool,
        "use_native_file_dialog": bool,
        "origin_mode": str,
        "color_scheme": str,
    }

    def __init__(self, config_path=None):
        """Initialize the configuration, loading from disk if available.

        Args:
            config_path: Optional path to the config file. Defaults to
                ``app_config.cfg`` in the parent directory of this module.
        """
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "app_config.cfg"
            )
        self.config_path = os.path.abspath(config_path)
        self.settings = dict(self.DEFAULTS)

        if not os.path.isfile(self.config_path):
            print(
                f"[Config] Configuration file not found at '{self.config_path}'. Creating default config..."
            )
            self.save()
        else:
            print(
                f"[Config] Configuration file found at '{self.config_path}'. Loading settings..."
            )

        self.load()
        self.migrate()

    def get_extraction_defaults(self):
        """Return a copy of the extraction default settings."""

        return dict(
            self.get("extraction_defaults", self.DEFAULTS["extraction_defaults"])
        )

    def set_extraction_defaults(self, **kwargs):
        """Update extraction defaults and persist to disk.

        Args:
            **kwargs: Key-value pairs to merge into extraction defaults.
        """
        defaults = self.get_extraction_defaults()
        defaults.update(kwargs)
        self.set("extraction_defaults", defaults)
        self.save()

    def get_editor_settings(self):
        """Return a copy of the editor settings."""

        return dict(
            self.get("editor_settings", self.DEFAULTS.get("editor_settings", {}))
        )

    def set_editor_settings(self, **kwargs):
        """Update editor settings and persist to disk.

        Args:
            **kwargs: Key-value pairs to merge into editor settings.
        """
        current = self.get_editor_settings()
        current.update(kwargs)
        self.set("editor_settings", current)

    def load(self):
        """Load settings from the config file, merging with current values."""

        if os.path.isfile(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.settings.update(json.load(f))
                print(
                    f"[Config] Configuration loaded successfully from '{self.config_path}'."
                )
            except Exception as e:
                print(f"[Config] Failed to load configuration: {e}")
                pass

    def save(self):
        """Write the current settings to the config file."""

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            print(f"[Config] Configuration saved to '{self.config_path}'.")
        except Exception as e:
            print(f"[Config] Failed to save configuration: {e}")
            pass

    def migrate(self):
        """Add missing defaults and remove obsolete keys, then save if changed."""

        needs_migration = False

        # Migrate fps -> duration (convert fps value to milliseconds)
        extraction = self.settings.get("extraction_defaults", {})
        if "fps" in extraction and "duration" not in extraction:
            fps_value = extraction.pop("fps")
            # Convert fps to milliseconds: 1000 / fps
            duration_ms = max(1, round(1000 / fps_value)) if fps_value > 0 else 42
            extraction["duration"] = duration_ms
            needs_migration = True
            print(
                f"[Config] Migrated 'fps: {fps_value}' to 'duration: {duration_ms}' (milliseconds)"
            )

        def merge_defaults(current, defaults):
            nonlocal needs_migration
            for key, default_value in defaults.items():
                if key not in current:
                    current[key] = default_value
                    needs_migration = True
                    print(
                        f"[Config] Added new setting '{key}' with default value: {default_value}"
                    )
                elif isinstance(default_value, dict) and isinstance(current[key], dict):
                    merge_defaults(current[key], default_value)

            obsolete_keys = []
            for key in current.keys():
                if key not in defaults:
                    obsolete_keys.append(key)
                elif isinstance(defaults[key], dict) and isinstance(current[key], dict):
                    nested_obsolete = []
                    for nested_key in current[key].keys():
                        if nested_key not in defaults[key]:
                            nested_obsolete.append(nested_key)

                    for nested_key in nested_obsolete:
                        del current[key][nested_key]
                        needs_migration = True
                        print(f"[Config] Removed obsolete setting '{key}.{nested_key}'")

            for key in obsolete_keys:
                del current[key]
                needs_migration = True
                print(f"[Config] Removed obsolete setting '{key}'")

        merge_defaults(self.settings, self.DEFAULTS)

        if needs_migration:
            self.save()
            print("[Config] Configuration migration completed successfully.")
        else:
            print("[Config] No migration needed - configuration is up to date.")

    def get(self, key, default=None):
        """Retrieve a setting value by key.

        Args:
            key: Setting name to look up.
            default: Value returned if the key is missing.

        Returns:
            The stored value, or the default.
        """
        return self.settings.get(
            key, default if default is not None else self.DEFAULTS.get(key)
        )

    def set(self, key, value):
        """Store a setting value and persist to disk.

        Args:
            key: Setting name.
            value: New value to store.
        """
        print(f"[Config] Setting '{key}' to: {value}")
        self.settings[key] = value
        self.save()

    def get_compression_defaults(self, format_name=None):
        """Return compression defaults for one or all formats.

        Args:
            format_name: Optional format key (e.g. 'png'). If None, returns
                all compression settings.

        Returns:
            A copy of the compression settings dict.
        """
        compression_defaults = self.get(
            "compression_defaults", self.DEFAULTS["compression_defaults"]
        )

        if format_name:
            return dict(compression_defaults.get(format_name, {}))

        return dict(compression_defaults)

    def set_compression_defaults(self, format_name, **kwargs):
        """Update compression defaults for a format and persist to disk.

        Args:
            format_name: Format key (e.g. 'png', 'webp').
            **kwargs: Key-value pairs to merge into the format's settings.
        """
        compression_defaults = self.get_compression_defaults()

        if format_name not in compression_defaults:
            compression_defaults[format_name] = {}

        compression_defaults[format_name].update(kwargs)
        self.set("compression_defaults", compression_defaults)

    def get_format_compression_settings(self, format_name):
        """Return compression settings keyed for the frame exporter.

        Args:
            format_name: Image format (e.g. 'PNG', 'WEBP').

        Returns:
            Dictionary with prefixed keys like 'png_compress_level'.
        """
        format_lower = format_name.lower()
        defaults = self.get_compression_defaults(format_lower)

        if format_lower == "png":
            return {
                "png_compress_level": defaults.get("compress_level", 9),
                "png_optimize": defaults.get("optimize", True),
            }
        elif format_lower == "webp":
            return {
                "webp_lossless": defaults.get("lossless", True),
                "webp_quality": defaults.get("quality", 90),
                "webp_method": defaults.get("method", 3),
                "webp_alpha_quality": defaults.get("alpha_quality", 90),
                "webp_exact": defaults.get("exact", True),
            }
        elif format_lower == "avif":
            return {
                "avif_lossless": defaults.get("lossless", True),
                "avif_quality": defaults.get("quality", 90),
                "avif_speed": defaults.get("speed", 5),
            }
        elif format_lower == "tiff":
            return {
                "tiff_compression_type": defaults.get("compression_type", "lzw"),
                "tiff_quality": defaults.get("quality", 90),
                "tiff_optimize": defaults.get("optimize", True),
            }

        return {}

    def get_last_input_directory(self):
        """Return the last input directory if remembering is enabled."""

        interface = self.settings.get("interface", {})
        if interface.get("remember_input_directory", True):
            return interface.get("last_input_directory", "")
        return ""

    def set_last_input_directory(self, directory):
        """Store the last input directory if remembering is enabled.

        Args:
            directory: Filesystem path to save.
        """
        interface = self.settings.get("interface", {})
        if interface.get("remember_input_directory", True):
            if "interface" not in self.settings:
                self.settings["interface"] = {}
            self.settings["interface"]["last_input_directory"] = directory
            self.save()

    def get_last_output_directory(self):
        """Return the last output directory if remembering is enabled."""

        interface = self.settings.get("interface", {})
        if interface.get("remember_output_directory", True):
            return interface.get("last_output_directory", "")
        return ""

    def set_last_output_directory(self, directory):
        """Store the last output directory if remembering is enabled.

        Args:
            directory: Filesystem path to save.
        """
        interface = self.settings.get("interface", {})
        if interface.get("remember_output_directory", True):
            if "interface" not in self.settings:
                self.settings["interface"] = {}
            self.settings["interface"]["last_output_directory"] = directory
            self.save()

    def get_remember_input_directory(self):
        """Return True if the last input directory should be remembered."""

        return self.settings.get("interface", {}).get("remember_input_directory", True)

    def set_remember_input_directory(self, remember):
        """Set whether to remember the last input directory.

        Args:
            remember: If False, clears the stored directory.
        """
        if "interface" not in self.settings:
            self.settings["interface"] = {}
        self.settings["interface"]["remember_input_directory"] = remember
        if not remember:
            self.settings["interface"]["last_input_directory"] = ""
        self.save()

    def get_remember_output_directory(self):
        """Return True if the last output directory should be remembered."""

        return self.settings.get("interface", {}).get("remember_output_directory", True)

    def set_remember_output_directory(self, remember):
        """Set whether to remember the last output directory.

        Args:
            remember: If False, clears the stored directory.
        """
        if "interface" not in self.settings:
            self.settings["interface"] = {}
        self.settings["interface"]["remember_output_directory"] = remember
        if not remember:
            self.settings["interface"]["last_output_directory"] = ""
        self.save()

    def get_language(self):
        """Return the stored language code, or 'auto' for system default."""

        return self.settings.get("language", "auto")

    def set_language(self, language_code):
        """Set the application language and persist to disk.

        Args:
            language_code: Language code (e.g. 'en_us', 'es_es') or 'auto'.
        """
        self.settings["language"] = language_code
        self.save()

    def get_effective_language(self):
        """Return the resolved language code.

        If set to 'auto', detects and returns the system locale.
        """
        language = self.get_language()
        if language == "auto":
            from .translation_manager import get_translation_manager

            manager = get_translation_manager()
            return manager.get_system_locale()
        return language

    def get_color_scheme(self):
        """Return the stored color scheme preference.

        Returns:
            One of 'auto', 'light', or 'dark'.
        """
        return self.settings.get("interface", {}).get("color_scheme", "auto")

    def set_color_scheme(self, scheme):
        """Set the application color scheme and persist to disk.

        Args:
            scheme: One of 'auto', 'light', or 'dark'.
        """
        if "interface" not in self.settings:
            self.settings["interface"] = {}
        self.settings["interface"]["color_scheme"] = scheme
        self.save()
