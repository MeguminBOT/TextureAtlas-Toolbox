"""Temporary animation preview generation for the UI.

Provides ``PreviewGenerator`` which renders a single animation to a temp
file for display in the application's preview pane.
"""

import os
import shutil
import tempfile
from typing import Dict, List, Optional

from core.extractor.animation_exporter import AnimationExporter
from core.extractor.atlas_processor import AtlasProcessor
from core.extractor.frame_pipeline import FramePipeline
from core.extractor.image_utils import scale_image
from core.editor.editor_composite import (
    build_editor_composite_frames,
    clone_animation_map,
)
from core.extractor.sprite_processor import SpriteProcessor
from core.extractor.spritemap import AdobeSpritemapRenderer


class PreviewGenerator:
    """Generate temporary animation previews for the UI.

    Handles standard spritesheets, Adobe Spritemap projects, and editor
    composite animations.

    Attributes:
        settings_manager: Provides per-spritesheet and animation settings.
        current_version: Version string embedded in exported metadata.
    """

    def __init__(self, settings_manager, current_version: str, app_config=None):
        """Initialise the preview generator.

        Args:
            settings_manager: Settings provider for export options.
            current_version: Version string for file metadata.
            app_config: Optional config with interface settings.
        """
        self.settings_manager = settings_manager
        self.current_version = current_version
        self.app_config = app_config
        self._frame_pipeline = FramePipeline()

    def generate_temp_animation(
        self,
        atlas_path: str,
        metadata_path: Optional[str],
        settings: dict,
        animation_name: str,
        temp_dir: Optional[str] = None,
        spritemap_info: Optional[dict] = None,
        spritesheet_label: Optional[str] = None,
    ) -> Optional[str]:
        """Generate a temporary preview file for the requested animation.

        Args:
            atlas_path: Path to the source atlas image.
            metadata_path: Path to metadata, or ``None`` for unknown sheets.
            settings: Export settings dict.
            animation_name: Name of the animation to preview.
            temp_dir: Directory for the temporary file; created if ``None``.
            spritemap_info: Optional Adobe spritemap project info dict.
            spritesheet_label: Friendly display name for the spritesheet.

        Returns:
            Path to the generated preview file, or ``None`` on failure.
        """
        owns_temp_dir = False
        try:
            label = spritesheet_label or os.path.basename(atlas_path)

            animations = self._collect_preview_frames(
                atlas_path,
                metadata_path,
                spritemap_info,
                label,
                animation_name,
                settings,
            )
            if not animations:
                return None

            owns_temp_dir = temp_dir is None
            if owns_temp_dir:
                temp_dir = tempfile.mkdtemp()

            resampling_method = settings.get("resampling_method", "Nearest")

            def scale_fn(img, size):
                return scale_image(img, size, resampling_method=resampling_method)

            animation_exporter = AnimationExporter(
                temp_dir,
                self.current_version,
                scale_fn,
            )

            for anim_name, image_tuples in animations.items():
                preview_settings = self.settings_manager.get_settings(
                    label, f"{label}/{anim_name}"
                )
                merged_settings = {**preview_settings, **settings}

                animation_format = self._resolve_preview_format(merged_settings)
                merged_settings["animation_format"] = animation_format

                filtered_frames = self._filter_preview_frames(
                    image_tuples,
                    merged_settings,
                    label,
                    anim_name,
                )

                animation_exporter.save_animations(
                    filtered_frames, label, anim_name, merged_settings
                )

                target_extension = self._preview_extension_for_format(animation_format)
                generated_file = self._find_generated_preview_file(
                    temp_dir, target_extension
                )
                if generated_file:
                    return generated_file
            return None

        except Exception as exc:
            print(f"Preview animation generation error: {exc}")
            if owns_temp_dir and temp_dir and os.path.isdir(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            return None

    def _collect_preview_frames(
        self,
        atlas_path,
        metadata_path,
        spritemap_info,
        spritesheet_label,
        animation_name,
        settings,
    ) -> Optional[Dict[str, List]]:
        """Collect frames for the requested animation from the appropriate source.

        Checks for editor composite definitions first, then spritemap projects,
        and finally standard spritesheet metadata.

        Returns:
            Dict mapping animation name to frame list, or ``None`` if unavailable.
        """
        definition = self._get_editor_composite_definition(
            spritesheet_label, animation_name
        )
        if definition:
            frames = self._build_editor_composite_preview_frames(
                definition,
                atlas_path,
                metadata_path,
                spritemap_info,
                spritesheet_label,
            )
            return {animation_name: frames} if frames else None

        if spritemap_info:
            frames = self._render_spritemap_preview(
                spritemap_info,
                atlas_path,
                animation_name,
                spritesheet_label,
                settings,
            )
            return {animation_name: frames} if frames else None

        frames = self._render_spritesheet_preview(
            atlas_path, metadata_path, animation_name
        )
        return {animation_name: frames} if frames else None

    def _render_spritemap_preview(
        self,
        spritemap_info,
        atlas_path,
        animation_name,
        spritesheet_label,
        settings,
    ):
        """Render frames for an Adobe Spritemap animation.

        Returns:
            List of frame tuples, or ``None`` if rendering fails.
        """
        animation_json_path = spritemap_info.get("animation_json")
        spritemap_json_path = spritemap_info.get("spritemap_json")
        if not animation_json_path or not spritemap_json_path:
            return None

        renderer = AdobeSpritemapRenderer(
            animation_json_path,
            spritemap_json_path,
            atlas_path,
            filter_single_frame=settings.get("filter_single_frame_spritemaps", True),
        )
        renderer.ensure_animation_defaults(self.settings_manager, spritesheet_label)
        symbol_entry = spritemap_info.get("symbol_map", {}).get(
            animation_name, animation_name
        )
        frames = renderer.render_animation(symbol_entry)
        if not frames:
            print(f"No frames rendered for spritemap animation: {animation_name}")
            return None
        return frames

    def _render_spritesheet_preview(self, atlas_path, metadata_path, animation_name):
        """Render frames for a standard spritesheet animation.

        When smart animation grouping is enabled, uses ``process_sprites``
        so that sub-indexed names (e.g. ``banban1``, ``banban2``) resolve
        correctly.  Falls back to per-animation filtering when grouping is
        disabled.

        Args:
            atlas_path: Path to the source atlas image.
            metadata_path: Path to the spritesheet metadata file
                (``.xml`` or ``.txt``).
            animation_name: Name of the animation to extract frames for.

        Returns:
            List of frame tuples, or ``None`` if parsing fails.
        """
        if not metadata_path:
            return None

        smart = self._get_smart_grouping()

        if smart:
            atlas_processor = AtlasProcessor(atlas_path, metadata_path)
            sprite_processor = SpriteProcessor(
                atlas_processor.atlas,
                atlas_processor.sprites,
                smart_animation_grouping=True,
            )
            all_animations = sprite_processor.process_sprites()
            frames = all_animations.get(animation_name)
            if not frames:
                print(f"Animation {animation_name} not found in processed sprites")
                return None
            return frames

        atlas_processor = AtlasProcessor(atlas_path, metadata_path)
        if metadata_path.endswith(".xml"):
            animation_sprites = atlas_processor.parse_xml_for_preview(animation_name)
        elif metadata_path.endswith(".txt"):
            animation_sprites = atlas_processor.parse_txt_for_preview(animation_name)
        else:
            print(f"Unsupported metadata format for preview: {metadata_path}")
            return None

        if not animation_sprites:
            print(f"No sprites found for animation: {animation_name}")
            return None

        sprite_processor = SpriteProcessor(
            atlas_processor.atlas, animation_sprites, smart_animation_grouping=False
        )
        processed = sprite_processor.process_specific_animation(animation_name)
        frames = processed.get(animation_name)
        if not frames:
            print(f"Animation {animation_name} not found in processed sprites")
            return None
        return frames

    def _build_editor_composite_preview_frames(
        self,
        definition,
        atlas_path,
        metadata_path,
        spritemap_info,
        spritesheet_label,
    ):
        """Build frames for an editor-defined composite animation.

        Returns:
            List of composite frame tuples, or empty list on failure.
        """
        source_frames = self._load_source_frames_for_preview(
            atlas_path,
            metadata_path,
            spritemap_info,
            spritesheet_label,
        )
        if not source_frames:
            print(
                "[PreviewGenerator] Unable to load source frames for composite preview."
            )
            return []
        return build_editor_composite_frames(
            definition,
            source_frames,
            log_warning=lambda message: print(message),
        )

    def _load_source_frames_for_preview(
        self,
        atlas_path,
        metadata_path,
        spritemap_info,
        spritesheet_label,
    ):
        """Load all source animations for composite frame building.

        Returns:
            Dict mapping animation names to frame lists.
        """
        try:
            if spritemap_info:
                return self._load_spritemap_source_frames(
                    spritemap_info,
                    atlas_path,
                    spritesheet_label,
                )

            if not metadata_path:
                return {}

            return self._load_metadata_source_frames(
                atlas_path, metadata_path, self._get_smart_grouping()
            )
        except Exception as exc:
            print(f"[PreviewGenerator] Failed to load source frames for preview: {exc}")
            return {}

    def _load_spritemap_source_frames(
        self, spritemap_info, atlas_path, spritesheet_label
    ):
        """Load all animations from an Adobe Spritemap project.

        Returns:
            Cloned animation map dict.
        """
        animation_json_path = spritemap_info.get("animation_json")
        spritemap_json_path = spritemap_info.get("spritemap_json")
        if not animation_json_path or not spritemap_json_path:
            return {}

        renderer = AdobeSpritemapRenderer(
            animation_json_path,
            spritemap_json_path,
            atlas_path,
            filter_single_frame=False,
        )
        renderer.ensure_animation_defaults(self.settings_manager, spritesheet_label)
        animations = renderer.build_animation_frames()
        return clone_animation_map(animations)

    def _get_smart_grouping(self) -> bool:
        """Return the smart_animation_grouping setting from app_config."""
        if self.app_config:
            return self.app_config.get("interface", {}).get(
                "smart_animation_grouping", True
            )
        return True

    @staticmethod
    def _load_metadata_source_frames(
        atlas_path, metadata_path, smart_animation_grouping: bool = True
    ):
        """Load all animations from standard spritesheet metadata.

        Returns:
            Cloned animation map dict.
        """
        atlas_processor = AtlasProcessor(atlas_path, metadata_path)
        sprite_processor = SpriteProcessor(
            atlas_processor.atlas,
            atlas_processor.sprites,
            smart_animation_grouping=smart_animation_grouping,
        )
        animations = sprite_processor.process_sprites()
        return clone_animation_map(animations)

    @staticmethod
    def _resolve_preview_format(settings):
        """Return the animation format for preview, defaulting to GIF."""
        animation_format = settings.get("animation_format", "GIF")
        if animation_format == "None":
            animation_format = "GIF"
        return animation_format

    @staticmethod
    def _preview_extension_for_format(animation_format: str) -> str:
        """Map an animation format name to its file extension."""
        file_extensions = {"GIF": ".gif", "WebP": ".webp", "APNG": ".png"}
        return file_extensions.get(animation_format, ".gif")

    @staticmethod
    def _find_generated_preview_file(directory: str, extension: str) -> Optional[str]:
        """Locate the first file matching the extension in a directory."""
        for file in os.listdir(directory):
            if file.endswith(extension):
                return os.path.join(directory, file)
        return None

    def _filter_preview_frames(
        self,
        image_tuples,
        merged_settings,
        spritesheet_label,
        animation_name,
    ):
        """Apply frame selection settings and return the kept frames."""
        context = self._frame_pipeline.build_context(
            spritesheet_label or "preview",
            animation_name,
            image_tuples,
            merged_settings,
        )
        return context.selected_frames

    def _get_editor_composite_definition(self, spritesheet_label, animation_name):
        """Retrieve an editor composite definition if one exists.

        Returns:
            Definition dict, or ``None`` if not defined.
        """
        if not self.settings_manager:
            return None
        sheet_settings = self.settings_manager.spritesheet_settings.get(
            spritesheet_label
        )
        if not isinstance(sheet_settings, dict):
            return None
        composites = sheet_settings.get("editor_composites")
        if not isinstance(composites, dict):
            return None
        definition = composites.get(animation_name)
        return definition if isinstance(definition, dict) else None
