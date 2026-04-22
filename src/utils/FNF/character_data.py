"""Loader for Friday Night Funkin' character data files."""

import os

from PySide6.QtWidgets import QFileDialog

from utils.FNF.engine_detector import detect_engine
from utils.FNF.alignment import build_alignment_overrides
from utils.FNF.anim_utils import parse_indices_attribute, parse_xml_offsets
from utils.utilities import Utilities
from utils.logger import get_logger

logger = get_logger(__name__)


class CharacterData:
    """Import FNF character definitions from Kade, Psych, or Codename Engine.

    Attributes:
        fnf_char_json_directory: Path to the directory containing character files.
    """

    def __init__(self):
        """Initialize with an empty character directory path."""

        self.fnf_char_json_directory = ""

    def fnf_load_char_data_settings(
        self,
        settings_manager,
        data_dict,
        listbox_png_callback=None,
        listbox_data_callback=None,
    ):
        """Load all character files from the configured directory.

        Args:
            settings_manager: Manager to receive animation settings.
            data_dict: Dictionary mapping PNG filenames to data file paths.
            listbox_png_callback: Optional callback to register PNG entries.
            listbox_data_callback: Optional callback to register data entries.
        """
        if not self.fnf_char_json_directory:
            return

        for filename in os.listdir(self.fnf_char_json_directory):
            file_path = os.path.join(self.fnf_char_json_directory, filename)
            self._process_character_file(
                file_path,
                settings_manager,
                data_dict=data_dict,
                listbox_png_callback=listbox_png_callback,
                listbox_data_callback=listbox_data_callback,
            )

    def fnf_select_char_data_directory(
        self,
        settings_manager,
        data_dict,
        listbox_png_callback=None,
        listbox_data_callback=None,
        parent_window=None,
    ):
        """Prompt the user to choose a character data directory and load it.

        Args:
            settings_manager: Manager to receive animation settings.
            data_dict: Dictionary mapping PNG filenames to data file paths.
            listbox_png_callback: Optional callback to register PNG entries.
            listbox_data_callback: Optional callback to register data entries.
            parent_window: Parent widget for the file dialog.
        """
        directory = QFileDialog.getExistingDirectory(
            parent_window, "Select FNF Character Data Directory"
        )
        if directory:
            self.fnf_char_json_directory = directory
            self.fnf_load_char_data_settings(
                settings_manager, data_dict, listbox_png_callback, listbox_data_callback
            )
            logger.info("Animation settings updated in SettingsManager.")

    def import_character_settings(self, file_path, settings_manager):
        """Import a single character file and store its animation settings.

        Args:
            file_path: Path to the character data file.
            settings_manager: Manager to receive animation settings.

        Raises:
            ValueError: If the file format is unsupported or invalid.
        """
        processed = self._process_character_file(file_path, settings_manager)
        if not processed:
            raise ValueError("Unsupported or invalid FNF character data file.")

    def _process_character_file(
        self,
        file_path,
        settings_manager,
        data_dict=None,
        listbox_png_callback=None,
        listbox_data_callback=None,
    ):
        """Parse a character file and register its animation settings.

        Args:
            file_path: Path to the character data file.
            settings_manager: Manager to receive animation settings.
            data_dict: Optional dictionary for PNG-to-data mapping.
            listbox_png_callback: Optional callback to register PNG entries.
            listbox_data_callback: Optional callback to register data entries.

        Returns:
            True if the file was processed successfully, False otherwise.
        """
        if not file_path or not os.path.exists(file_path):
            return False

        engine_type, parsed_data = detect_engine(file_path)
        filename = os.path.basename(file_path)
        logger.info("Found %s data for %s.", engine_type, filename)

        if engine_type == "Psych Engine" and parsed_data:
            png_filename = self._register_spritesheet_entry(
                parsed_data.get("image", ""),
                file_path,
                data_dict,
                listbox_png_callback,
                listbox_data_callback,
            )
            scale = parsed_data.get("scale", 1)
            for anim in parsed_data.get("animations", []):
                anim_name = Utilities.strip_trailing_digits(anim.get("name", ""))
                fps = anim.get("fps", 0)
                indices = anim.get("indices") or None
                loop = bool(anim.get("loop", False))
                offsets = anim.get("offsets")
                self._update_animation_settings(
                    settings_manager,
                    png_filename,
                    anim_name,
                    fps,
                    indices=indices,
                    loop=loop,
                    scale=scale,
                    offsets=offsets,
                    flip_x=parsed_data.get("flip_x", False),
                )
            return True

        if engine_type == "Codename Engine" and parsed_data is not None:
            png_filename = self._register_spritesheet_entry(
                filename,
                file_path,
                data_dict,
                listbox_png_callback,
                listbox_data_callback,
            )
            try:
                scale = float(parsed_data.attrib.get("scale", 1))
            except (TypeError, ValueError):
                scale = 1
            for anim in parsed_data.findall("anim"):
                anim_name = Utilities.strip_trailing_digits(anim.get("name", ""))
                fps = int(anim.get("fps", 0))
                indices = parse_indices_attribute(anim.get("indices"))
                loop = anim.get("loop", "false").lower() == "true"
                offsets = parse_xml_offsets(anim)
                self._update_animation_settings(
                    settings_manager,
                    png_filename,
                    anim_name,
                    fps,
                    indices=indices,
                    loop=loop,
                    scale=scale,
                    offsets=offsets,
                )
            return True

        if engine_type == "Kade Engine" and parsed_data:
            png_filename = self._register_spritesheet_entry(
                filename,
                file_path,
                data_dict,
                listbox_png_callback,
                listbox_data_callback,
            )
            fps = parsed_data.get("frameRate", 0)
            scale_value = parsed_data.get("scale", 1)
            for anim in parsed_data.get("animations", []):
                anim_name = Utilities.strip_trailing_digits(anim.get("name", ""))
                indices = anim.get("frameIndices") or None
                loop = bool(anim.get("looped", False))
                offsets = anim.get("offsets")
                self._update_animation_settings(
                    settings_manager,
                    png_filename,
                    anim_name,
                    fps,
                    indices=indices,
                    loop=loop,
                    scale=scale_value,
                    offsets=offsets,
                )
            return True

        if engine_type == "V-Slice Engine" and parsed_data:
            # The V-Slice ``assetPath`` is typically a path like
            # ``"characters/BOYFRIEND"``; ``_register_spritesheet_entry``
            # already strips the directory and extension.
            png_filename = self._register_spritesheet_entry(
                parsed_data.get("assetPath", ""),
                file_path,
                data_dict,
                listbox_png_callback,
                listbox_data_callback,
            )
            scale_value = parsed_data.get("scale", 1)
            character_flip_x = bool(parsed_data.get("flipX", False))
            for anim in parsed_data.get("animations", []):
                anim_name = Utilities.strip_trailing_digits(anim.get("name", ""))
                # V-Slice stores frame rate per animation; default 24 mirrors
                # the engine's ``DEFAULT_FRAMERATE``.
                fps = anim.get("frameRate", 24)
                indices = anim.get("frameIndices") or None
                loop = bool(anim.get("looped", False))
                offsets = anim.get("offsets")
                # Per-animation ``flipX`` overrides the character-level value
                # when present, otherwise inherit it.
                anim_flip_x = anim.get("flipX")
                flip_x = (
                    bool(anim_flip_x) if anim_flip_x is not None else character_flip_x
                )
                self._update_animation_settings(
                    settings_manager,
                    png_filename,
                    anim_name,
                    fps,
                    indices=indices,
                    loop=loop,
                    scale=scale_value,
                    offsets=offsets,
                    flip_x=flip_x,
                )
            return True

        logger.info(
            "Skipping %s: Not a FNF character data file or unsupported engine type.",
            filename,
        )
        return False

    def _register_spritesheet_entry(
        self,
        image_hint,
        file_path,
        data_dict=None,
        listbox_png_callback=None,
        listbox_data_callback=None,
    ):
        """Register a spritesheet PNG and its data file in the provided dict.

        Args:
            image_hint: Suggested image name from character data.
            file_path: Path to the character data file.
            data_dict: Optional dictionary for PNG-to-data mapping.
            listbox_png_callback: Optional callback to register PNG entries.
            listbox_data_callback: Optional callback to register data entries.

        Returns:
            The PNG filename used as the registry key.
        """
        base_name = image_hint or os.path.splitext(os.path.basename(file_path))[0]
        png_base = os.path.splitext(os.path.basename(base_name))[0]
        png_filename = f"{png_base}.png"

        if data_dict is not None and png_filename not in data_dict:
            data_dict[png_filename] = file_path
            if listbox_png_callback:
                listbox_png_callback(png_filename)
        if listbox_data_callback:
            listbox_data_callback(file_path)
        return png_filename

    def _update_animation_settings(
        self,
        settings_manager,
        png_filename,
        anim_name,
        fps,
        indices=None,
        loop=False,
        scale=1,
        offsets=None,
        flip_x=False,
    ):
        """Store animation settings in the settings manager.

        Args:
            settings_manager: Manager to receive animation settings.
            png_filename: Spritesheet filename prefix.
            anim_name: Animation name within the spritesheet.
            fps: Frame rate for the animation (converted to duration in ms).
            indices: Optional list of frame indices.
            loop: Whether the animation loops continuously.
            scale: Sprite scale factor.
            offsets: Optional (x, y) offset values.
            flip_x: Whether the sprite is horizontally flipped.
        """
        if not settings_manager or not png_filename or not anim_name:
            return

        full_anim_name = f"{png_filename}/{anim_name}"
        # Convert fps to duration in milliseconds
        duration_ms = max(1, round(1000 / fps)) if fps > 0 else 42
        settings = {"duration": duration_ms}

        if scale not in (None, 1):
            settings["scale"] = scale
        if indices:
            settings["indices"] = indices
        if loop:
            settings["delay"] = 0

        alignment = build_alignment_overrides(offsets, scale=scale, flip_x=flip_x)
        if alignment:
            settings["alignment_overrides"] = alignment

        settings_manager.set_animation_settings(full_anim_name, **settings)
