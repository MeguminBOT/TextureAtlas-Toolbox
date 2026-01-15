"""General-purpose utility functions for the application.

Provides static methods for path resolution, filename sanitization,
and format string processing.
"""

import re
import os
import sys
from string import Template
from PySide6.QtCore import QCoreApplication


class Utilities:
    """Static utility methods for common application tasks.

    Attributes:
        APP_NAME: Translated application display name.
    """

    APP_NAME = QCoreApplication.translate("Utilities", "TextureAtlas Toolbox")

    @staticmethod
    def find_root(target_name: str) -> str | None:
        """Find the directory containing a target file or folder.

        Walks up the directory tree from the executable (if compiled) or
        this module's location until finding a directory containing the
        target.

        Args:
            target_name: Name of the file or folder to locate.

        Returns:
            Path to the directory containing the target, or None if not found.
        """

        if Utilities.is_compiled():
            root_path = os.path.dirname(sys.executable)
        else:
            root_path = os.path.abspath(os.path.dirname(__file__))

        target_path = os.path.join(root_path, target_name)
        if os.path.exists(target_path):
            print(f"[find_root] Found '{target_name}' at: {target_path}")
            return root_path

        while True:
            target_path = os.path.join(root_path, target_name)
            if os.path.exists(target_path):
                print(f"[find_root] Found '{target_name}' at: {target_path}")
                return root_path
            new_root = os.path.dirname(root_path)
            if new_root == root_path:
                break
            root_path = new_root

        print(f"[find_root] Could not find '{target_name}' in directory tree")
        return None

    @staticmethod
    def is_compiled() -> bool:
        """Check if the application is running as a Nuitka-compiled executable.

        Returns:
            ``True`` when running from a compiled Nuitka binary, ``False`` otherwise.
        """

        if "__compiled__" in globals():
            return True
        else:
            return False

    @staticmethod
    def count_spritesheets(spritesheet_list: list) -> int:
        """Return the number of spritesheets in a list.

        Args:
            spritesheet_list: List of spritesheet entries.

        Returns:
            Length of the input list.
        """

        return len(spritesheet_list)

    @staticmethod
    def replace_invalid_chars(name: str) -> str:
        """Replace filesystem-invalid characters with underscores.

        Replaces ``\\ / : * ? " < > |`` and strips trailing whitespace.

        Args:
            name: Filename or path component to sanitize.

        Returns:
            Sanitized string safe for use in filesystem paths.
        """

        return re.sub(r'[\\/:*?"<>|]', "_", name).rstrip()

    @staticmethod
    def strip_trailing_digits(name: str) -> str:
        """Remove trailing frame numbers and optional ``.png`` extension.

        Strips any number of trailing digits, preceding underscores/spaces,
        and any trailing underscores or whitespace.

        Args:
            name: Sprite or frame name (e.g., ``"idle_0001"`` or ``"run 5.png"``).

        Returns:
            Base animation name with trailing digits removed.
        """

        return (
            re.sub(
                r"[_\s]*\d+(?:\.(?:png|jpe?g|gif|webp|bmp|tiff?|tga|avif|dds))?$",
                "",
                name,
                flags=re.IGNORECASE,
            )
            .rstrip("_")
            .rstrip()
        )

    _NATURAL_SORT_PATTERN = re.compile(r"(\d+)")

    @staticmethod
    def natural_sort_key(text: str) -> tuple:
        """Generate a sort key for natural (human-friendly) ordering.

        Splits the input into alternating text and numeric segments, converting
        numeric parts to integers so that ``"frame2"`` sorts before ``"frame10"``.

        Handles common spritesheet naming patterns:
        - Zero-padded: ``Idle0001``, ``Idle0002``, ...
        - Unpadded: ``scroll 0``, ``scroll 1``, ``scroll 10``, ...
        - Multi-prefix: ``Pico shoot 10000``, ``Pico shoot 20001``, ...

        Args:
            text: String to generate a sort key for.

        Returns:
            Tuple of strings and integers suitable for comparison.
        """
        parts = Utilities._NATURAL_SORT_PATTERN.split(text)
        return tuple(int(part) if part.isdigit() else part.lower() for part in parts)

    @staticmethod
    def format_filename(
        prefix: str | None,
        sprite_name: str,
        animation_name: str,
        filename_format: str | None,
        replace_rules: list[dict],
        suffix: str | None = None,
    ) -> str:
        """Build a sanitized filename from components and format rules.

        Supports preset formats (``Standardized``, ``No spaces``,
        ``No special characters``) and custom templates using ``$sprite``
        and ``$anim`` placeholders. Applies find/replace rules afterward.

        Args:
            prefix: Optional prefix prepended to the name.
            sprite_name: Spritesheet name (extension stripped).
            animation_name: Animation name.
            filename_format: Format preset or template string.
            replace_rules: List of dicts with ``find``, ``replace``, and
                ``regex`` keys.
            suffix: Optional suffix appended to the name.

        Returns:
            Sanitized filename with invalid characters replaced.
        """

        if filename_format is None:
            filename_format = "standardized"
        if not replace_rules:
            replace_rules = []

        format_lower = filename_format.lower() if filename_format else "standardized"

        sprite_name = os.path.splitext(sprite_name)[0]

        include_sprite = not Utilities._has_placeholder_removal_rule(
            replace_rules,
            ("$sprite", "$spritesheet", "$spritemap", "$atlas", "$textureatlas"),
        )
        include_anim = not Utilities._has_placeholder_removal_rule(
            replace_rules, ("$anim", "$animation")
        )

        if format_lower in (
            "standardized",
            "no_spaces",
            "no_special",
            "no spaces",
            "no special characters",
        ):
            parts = [prefix]
            if include_sprite:
                parts.append(sprite_name)
            if include_anim:
                parts.append(animation_name)
            parts.append(suffix)
            parts = [p for p in parts if p]
            base_name = " - ".join(parts)

            if format_lower in ("no_spaces", "no spaces"):
                base_name = base_name.replace(" ", "")
            elif format_lower in ("no_special", "no special characters"):
                base_name = base_name.replace(" ", "").replace("-", "").replace("_", "")
        else:
            base_name = Template(filename_format).safe_substitute(
                sprite=sprite_name, anim=animation_name
            )
            if prefix:
                base_name = f"{prefix} - {base_name}"
            if suffix:
                base_name = f"{base_name} - {suffix}"

        for rule in replace_rules:
            find_pattern = rule["find"]
            find_pattern = Utilities._expand_filename_placeholders(
                find_pattern, sprite_name, animation_name
            )

            if rule["regex"]:
                base_name = re.sub(find_pattern, rule["replace"], base_name)
            else:
                base_name = base_name.replace(find_pattern, rule["replace"])

        return Utilities.replace_invalid_chars(base_name)

    @staticmethod
    def _expand_filename_placeholders(
        pattern: str,
        sprite_name: str,
        animation_name: str,
    ) -> str:
        """Expand filename placeholders to their actual values.

        Supports placeholders for sprite/spritesheet and animation names,
        allowing find/replace rules to target specific filename components.

        Args:
            pattern: The find pattern potentially containing placeholders.
            sprite_name: The spritesheet/atlas name to substitute.
            animation_name: The animation name to substitute.

        Returns:
            Pattern with all placeholders expanded to actual values.
        """
        for placeholder in (
            "$sprite",
            "$spritesheet",
            "$spritemap",
            "$atlas",
            "$textureatlas",
        ):
            pattern = pattern.replace(placeholder, sprite_name)

        for placeholder in ("$anim", "$animation"):
            pattern = pattern.replace(placeholder, animation_name)

        return pattern

    @staticmethod
    def _has_placeholder_removal_rule(
        replace_rules: list[dict],
        placeholders: tuple[str, ...],
    ) -> bool:
        """Check if any rule removes a placeholder (find=placeholder, replace='').

        Args:
            replace_rules: List of rule dicts with 'find' and 'replace' keys.
            placeholders: Tuple of placeholder strings to check for.

        Returns:
            True if a removal rule exists for any of the placeholders.
        """
        for rule in replace_rules:
            find_val = rule.get("find", "")
            replace_val = rule.get("replace", "")
            if find_val in placeholders and replace_val == "":
                return True
        return False
