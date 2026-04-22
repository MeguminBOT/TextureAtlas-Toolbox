"""Background color detection for spritesheets without metadata.

Provides ``UnknownSpritesheetHandler`` which identifies images lacking XML/TXT
metadata, detects their background colors, and prompts the user to choose
how to handle them before extraction.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

from PIL import Image

from gui.extractor.background_handler_window import BackgroundHandlerWindow
from parsers.unknown_parser import UnknownParser


class UnknownSpritesheetHandler:
    """Detect and handle background colors for spritesheets without metadata.

    Identifies images missing XML, TXT, or spritemap JSON files, analyses them
    for transparency and background colors, and shows a dialog for user input.

    Attributes:
        SUPPORTED_IMAGE_SUFFIXES: Tuple of file extensions considered valid.
        SUPPORTED_METADATA_SUFFIXES: Tuple of metadata file extensions to check.
    """

    SUPPORTED_IMAGE_SUFFIXES = (
        ".png",
        ".jpg",
        ".jpeg",
        ".bmp",
        ".tiff",
        ".webp",
        ".dds",
        ".ktx2",
    )

    # All metadata file extensions supported by parsers
    SUPPORTED_METADATA_SUFFIXES = (
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

    def __init__(self, logger: Callable[[str], None] | None = None):
        """Initialise the handler with an optional logger.

        Args:
            logger: Callable for status messages; defaults to ``print``.
        """
        self._log = logger or print

    def collect_and_detect(
        self,
        input_dir: str,
        spritesheet_list: Sequence[str],
        path_map: Optional[Dict[str, str]] = None,
    ) -> List[dict]:
        """Identify unknown spritesheets and analyse their background colors.

        This is the I/O-heavy portion of the detection workflow and is safe to
        call from a background thread.  It does **not** show any dialogs.

        Args:
            input_dir: Root directory containing the images. Used as a
                fallback when ``path_map`` is not supplied or does not
                cover an entry.
            spritesheet_list: Relative filenames to check.
            path_map: Optional ``{display_name: absolute_path}`` mapping.
                Required when sources span multiple directories (drag
                and drop, manual file picker), since ``input_dir`` is
                then a UI label rather than a real directory.

        Returns:
            List of detection result dicts (``filename``, ``colors``,
            ``has_transparency``), or an empty list when every file has
            recognised metadata.
        """
        self._log(
            f"[UnknownSpritesheetHandler] Checking {len(spritesheet_list)} spritesheets for unknown files..."
        )
        base_directory = Path(input_dir)
        resolved_paths = self._resolve_paths(base_directory, spritesheet_list, path_map)
        unknown_sheets = self._collect_unknown_spritesheets(
            spritesheet_list, resolved_paths
        )
        if not unknown_sheets:
            self._log("[UnknownSpritesheetHandler] No unknown spritesheets found")
            return []

        self._log(
            f"[UnknownSpritesheetHandler] Found {len(unknown_sheets)} unknown spritesheet(s), detecting background colors..."
        )
        return self._detect_background_colors(unknown_sheets, resolved_paths)

    def apply_detection_results(
        self, detection_results: List[dict], parent_window
    ) -> bool:
        """Show the background-options dialog and store the user's choices.

        Must be called on the main (GUI) thread after ``collect_and_detect``
        has finished.

        Args:
            detection_results: The list returned by ``collect_and_detect``.
            parent_window: Parent widget for the dialog.

        Returns:
            ``True`` if the user cancelled extraction, ``False`` otherwise.
        """
        try:
            if not detection_results:
                self._log("[UnknownSpritesheetHandler] No detection results to show")
                return False

            for result in detection_results:
                self._log(
                    f"  - {result['filename']}: {len(result['colors'])} colors, transparency: {result['has_transparency']}"
                )

            needs_background_handling = any(
                (not result["has_transparency"]) and result["colors"]
                for result in detection_results
            )

            if needs_background_handling:
                self._log(
                    "[UnknownSpritesheetHandler] Some images have backgrounds that need handling - showing background handler window..."
                )
                background_choices = BackgroundHandlerWindow.show_background_options(
                    parent_window, detection_results
                )
                self._log(
                    f"[UnknownSpritesheetHandler] User choices: {background_choices}"
                )

                if background_choices.get("_cancelled", False):
                    self._log(
                        "[UnknownSpritesheetHandler] Background handler was cancelled by user - stopping extraction"
                    )
                    return True

                if background_choices:
                    if not hasattr(BackgroundHandlerWindow, "_file_choices"):
                        BackgroundHandlerWindow._file_choices = {}
                    BackgroundHandlerWindow._file_choices.update(background_choices)
                    self._log(
                        f"[UnknownSpritesheetHandler] Background handling preferences set for {len(background_choices)} files"
                    )
            else:
                self._log(
                    "[UnknownSpritesheetHandler] All images either have transparency or no detectable backgrounds - skipping background handler window"
                )

        except Exception as exc:
            self._log(
                f"[UnknownSpritesheetHandler] Error applying detection results: {exc}"
            )

        return False

    def handle_background_detection(
        self,
        input_dir: str,
        spritesheet_list: Sequence[str],
        parent_window,
    ) -> bool:
        """Run the background detection workflow for unknown spritesheets.

        Scans for images lacking metadata, detects background colors, and
        displays a dialog if user input is required.

        Args:
            input_dir: Root directory containing the images.
            spritesheet_list: Relative filenames to check.
            parent_window: Parent widget for the dialog.

        Returns:
            ``True`` if the user cancelled extraction, ``False`` otherwise.
        """
        try:
            BackgroundHandlerWindow.reset_batch_state()
            detection_results = self.collect_and_detect(input_dir, spritesheet_list)
            return self.apply_detection_results(detection_results, parent_window)
        except Exception as exc:
            self._log(
                f"[UnknownSpritesheetHandler] Error in background color detection: {exc}"
            )
        return False

    def _collect_unknown_spritesheets(
        self,
        spritesheet_list: Sequence[str],
        resolved_paths: Dict[str, Path],
    ) -> List[str]:
        """Identify spritesheets that lack accompanying metadata files.

        Args:
            spritesheet_list: Display names to check.
            resolved_paths: Mapping from display name to absolute atlas
                path, as produced by :py:meth:`_resolve_paths`.

        Returns:
            List of filenames with no recognized metadata files.
        """
        unknown_sheets: List[str] = []
        for filename in spritesheet_list:
            atlas_path = resolved_paths.get(filename)
            if atlas_path is None:
                continue
            base_filename = atlas_path.stem
            atlas_dir = atlas_path.parent

            # Check for any supported metadata file extension
            has_metadata = False
            for ext in self.SUPPORTED_METADATA_SUFFIXES:
                metadata_path = atlas_dir / f"{base_filename}{ext}"
                if metadata_path.is_file():
                    has_metadata = True
                    break

            # Also check for Adobe Animate spritemap (Animation.json + spritemap.json)
            if not has_metadata:
                animation_json_path = atlas_dir / "Animation.json"
                spritemap_json_path = atlas_dir / f"{base_filename}.json"
                if animation_json_path.is_file() and spritemap_json_path.is_file():
                    has_metadata = True

            if (
                not has_metadata
                and atlas_path.is_file()
                and atlas_path.suffix.lower() in self.SUPPORTED_IMAGE_SUFFIXES
            ):
                unknown_sheets.append(filename)
                self._log(
                    f"[UnknownSpritesheetHandler] Found unknown spritesheet: {filename}"
                )
        return unknown_sheets

    @staticmethod
    def _resolve_paths(
        base_directory: Path,
        spritesheet_list: Sequence[str],
        path_map: Optional[Dict[str, str]],
    ) -> Dict[str, Path]:
        """Resolve display names to absolute atlas paths.

        Each entry is looked up in ``path_map`` first; otherwise it is
        joined onto ``base_directory``. Names with no usable path
        (mapped value is empty) are dropped.

        Args:
            base_directory: Fallback root for joining display names.
            spritesheet_list: Display names to resolve.
            path_map: Optional explicit mapping from display name to
                absolute path. Empty or missing entries fall back.

        Returns:
            ``{display_name: absolute_path}`` for every entry that
            resolved to a non-empty path.
        """
        path_map = path_map or {}
        resolved: Dict[str, Path] = {}
        for filename in spritesheet_list:
            mapped = path_map.get(filename)
            if mapped:
                resolved[filename] = Path(mapped)
            else:
                resolved[filename] = base_directory / Path(filename)
        return resolved

    def _detect_background_colors(
        self,
        unknown_sheets: Sequence[str],
        resolved_paths: Dict[str, Path],
    ):
        """Analyse unknown spritesheets for transparency and background colors.

        Args:
            unknown_sheets: Display names previously identified as
                lacking metadata.
            resolved_paths: Mapping from display name to absolute atlas
                path, as produced by :py:meth:`_resolve_paths`.

        Returns:
            List of dicts with ``filename``, ``colors``, and ``has_transparency``.
        """
        detection_results = []
        for filename in unknown_sheets:
            atlas_path = resolved_paths.get(filename)
            if atlas_path is None:
                continue
            image_path = str(atlas_path)
            try:
                image = Image.open(image_path)
                if image.mode != "RGBA":
                    image = image.convert("RGBA")

                has_transparency = UnknownParser._has_transparency(image)
                detected_colors = []
                if not has_transparency:
                    detected_colors = UnknownParser._detect_background_colors(
                        image, max_colors=3
                    )

                detection_results.append(
                    {
                        "filename": filename,
                        "colors": detected_colors,
                        "has_transparency": has_transparency,
                    }
                )

            except Exception as exc:
                self._log(
                    f"[UnknownSpritesheetHandler] Error detecting background colors for {filename}: {exc}"
                )
                detection_results.append(
                    {"filename": filename, "colors": [], "has_transparency": False}
                )
        return detection_results
