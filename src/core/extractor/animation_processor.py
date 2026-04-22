"""Orchestrate frame and animation export from parsed texture atlases.

Provides ``AnimationProcessor`` which iterates over animations, applies
alignment overrides, injects editor-defined composites, and delegates to
``FrameExporter`` and ``AnimationExporter`` for file output.
"""

import os
from typing import Set

from PIL import Image

from core.extractor.animation_exporter import AnimationExporter
from core.extractor.frame_exporter import FrameExporter
from core.extractor.frame_pipeline import FramePipeline
from core.extractor.image_utils import (
    ensure_pil_image,
    frame_dimensions,
    scale_image,
    scale_image_nearest,
)
from core.editor.editor_composite import (
    clone_animation_map,
    build_editor_composite_frames,
)
from utils.FNF.alignment import resolve_fnf_offset
from utils.logger import get_logger

logger = get_logger(__name__)


class AnimationProcessor:
    """Export frames and animations from a parsed texture atlas.

    Clones incoming animation data, injects any editor-defined composite
    animations, then iterates each animation to export individual frames
    and/or animated files based on user settings.

    Attributes:
        animations: Working copy of animation name to frame-tuple list.
        atlas_path: Filesystem path to the source atlas image.
        output_dir: Directory where exported files are written.
        settings_manager: Provides global and per-animation settings.
        current_version: Version string for metadata comments.
        spritesheet_label: Display name for the spritesheet.
        frame_exporter: ``FrameExporter`` instance for static frames.
        animation_exporter: ``AnimationExporter`` instance for animations.
    """

    def __init__(
        self,
        animations,
        atlas_path,
        output_dir,
        settings_manager,
        current_version,
        spritesheet_label=None,
    ):
        """Initialise the processor and inject editor composites.

        Args:
            animations: Dict mapping animation names to frame-tuple sequences.
            atlas_path: Path to the source texture atlas.
            output_dir: Directory for exported files.
            settings_manager: Settings provider for export options.
            current_version: Version string embedded in output metadata.
            spritesheet_label: Optional display name; defaults to atlas filename.
        """
        base_animations = clone_animation_map(animations)
        self._source_frames = clone_animation_map(base_animations)
        self.animations = clone_animation_map(base_animations)
        self.atlas_path = atlas_path
        self.output_dir = output_dir
        self.settings_manager = settings_manager
        self.current_version = current_version
        self.spritesheet_label = spritesheet_label or os.path.split(self.atlas_path)[1]
        self.frame_exporter = FrameExporter(
            self.output_dir, self.current_version, self.scale_image
        )
        self.animation_exporter = AnimationExporter(
            self.output_dir, self.current_version, self.scale_image
        )
        self._frame_pipeline = FramePipeline()
        self._editor_composite_names: Set[str] = set()
        self._inject_editor_composites()

    def process_animations(
        self, is_unknown_spritesheet=False, sub_progress_callback=None
    ):
        """Export all animations as frames and/or animated files.

        Iterates each animation, retrieves settings, applies alignment
        overrides for editor composites, and delegates to the appropriate
        exporter.

        Args:
            is_unknown_spritesheet: When ``True``, applies extra cropping
                heuristics for spritesheets without known metadata.
            sub_progress_callback: Optional ``(current, total)`` callable
                invoked after each frame is saved, for live progress display.

        Returns:
            A tuple ``(frames_generated, anims_generated)`` with counts of
            exported files.
        """
        frames_generated = 0
        anims_generated = 0

        spritesheet_name = self.spritesheet_label

        for animation_name, image_tuples in self.animations.items():

            settings = self.settings_manager.get_settings(
                spritesheet_name, f"{spritesheet_name}/{animation_name}"
            )
            context = self._frame_pipeline.build_context(
                spritesheet_name,
                animation_name,
                image_tuples,
                settings,
            )

            alignment_overrides = settings.get("alignment_overrides")
            use_overrides = (
                alignment_overrides
                if self._is_editor_composite(animation_name)
                else None
            )
            if use_overrides:
                aligned_tuples = self._apply_alignment_overrides(
                    context.frames, use_overrides
                )
                context = context.with_frames(aligned_tuples)

            if settings.get("fnf_idle_loop") and "idle" in animation_name.lower():
                settings["delay"] = 0

            frame_export = settings.get("frame_export", False)
            if frame_export and settings.get("frame_format") != "None":
                frames_generated += self.frame_exporter.save_frames(
                    context.frames,
                    context.kept_indices,
                    spritesheet_name,
                    animation_name,
                    settings.get("scale"),
                    settings,
                    is_unknown_spritesheet,
                    progress_callback=sub_progress_callback,
                )

            animation_export = settings.get("animation_export", False)
            animation_format = settings.get("animation_format")
            if (
                not context.single_frame
                and animation_export
                and animation_format != "None"
            ):
                anims_generated += self.animation_exporter.save_animations(
                    context.frames,
                    spritesheet_name,
                    animation_name,
                    settings,
                    progress_callback=sub_progress_callback,
                )

        return frames_generated, anims_generated

    def _inject_editor_composites(self):
        """Build and register editor-defined composite animations.

        Composites are assembled from existing source frames according to
        definitions stored in settings. Successfully built composites are
        added to ``self.animations`` so they export alongside parsed ones.
        """
        definitions = self._get_editor_composites()
        if not definitions:
            return

        injected = 0
        for animation_name, definition in definitions.items():
            frames = build_editor_composite_frames(
                definition,
                self._source_frames,
                log_warning=lambda message: logger.warning("%s", message),
            )
            if not frames:
                continue
            self.animations[animation_name] = frames
            self._editor_composite_names.add(animation_name)
            injected += 1

        if injected:
            logger.info(
                "[AnimationProcessor] Injected %s editor composite animation(s) for %s.",
                injected,
                self.spritesheet_label,
            )

    def _get_editor_composites(self):
        """Retrieve editor composite definitions from spritesheet settings.

        Returns:
            Dict mapping composite names to definition dicts, or empty dict.
        """
        if not self.settings_manager or not self.spritesheet_label:
            return {}
        spritesheet_settings = self.settings_manager.get_settings(
            self.spritesheet_label
        )
        composites = spritesheet_settings.get("editor_composites")
        return composites if isinstance(composites, dict) else {}

    def _is_editor_composite(self, animation_name: str) -> bool:
        """Return ``True`` if ``animation_name`` was injected as a composite."""
        return animation_name in self._editor_composite_names

    def _apply_alignment_overrides(self, image_tuples, overrides):
        """Reposition frames onto a common canvas using editor offsets.

        Supports per-frame offsets, a default offset, FNF-specific overrides,
        and optional top-left origin mode.

        Args:
            image_tuples: Sequence of ``(name, image, metadata)`` tuples.
            overrides: Dict with ``canvas``, ``default``, ``frames``, etc.

        Returns:
            List of ``(name, canvas_image, metadata)`` tuples with adjusted
            positioning.
        """
        canvas = overrides.get("canvas") or []
        default_offset = overrides.get("default", {})
        default_x = int(default_offset.get("x", 0))
        default_y = int(default_offset.get("y", 0))
        frames_map = overrides.get("frames", {})
        origin_mode = overrides.get("origin_mode")
        top_left_origin = (
            isinstance(origin_mode, str) and origin_mode.lower() == "top_left"
        )
        translation_block = overrides.get("composite_translation", {})
        translate_x = (
            int(translation_block.get("x", 0))
            if isinstance(translation_block, dict)
            else 0
        )
        translate_y = (
            int(translation_block.get("y", 0))
            if isinstance(translation_block, dict)
            else 0
        )

        if len(canvas) == 2:
            canvas_width = max(1, int(canvas[0]))
            canvas_height = max(1, int(canvas[1]))
        else:
            widths = [frame_dimensions(img[1])[0] for img in image_tuples]
            heights = [frame_dimensions(img[1])[1] for img in image_tuples]
            canvas_width = max(widths) if widths else 1
            canvas_height = max(heights) if heights else 1

        adjusted = []
        for name, frame_image, metadata in image_tuples:
            frame_image = ensure_pil_image(frame_image)
            offset_data = frames_map.get(name, {})
            offset_x = int(offset_data.get("x", default_x))
            offset_y = int(offset_data.get("y", default_y))
            fnf_override = resolve_fnf_offset(overrides, name, metadata)
            if fnf_override is not None:
                offset_x, offset_y = fnf_override
            offset_x += translate_x
            offset_y += translate_y
            canvas_image = Image.new("RGBA", (canvas_width, canvas_height))
            if top_left_origin:
                target_x = offset_x
                target_y = offset_y
            else:
                # Anchor around the center so offsets nudge relative to the origin crosshair
                target_x = (canvas_width - frame_image.width) // 2 + offset_x
                target_y = (canvas_height - frame_image.height) // 2 + offset_y
            canvas_image.paste(frame_image, (target_x, target_y), frame_image)
            adjusted.append((name, canvas_image, metadata))

        return adjusted

    def scale_image(self, img, size):
        """Scale an image using the configured resampling method.

        Args:
            img: Source PIL Image or NumPy array.
            size: Scale factor; negative values flip horizontally.

        Returns:
            Scaled PIL Image.
        """
        resampling_method = self.settings_manager.global_settings.get(
            "resampling_method", "Lanczos"
        )
        return scale_image(img, size, resampling_method=resampling_method)

    def dispose(self) -> None:
        """Release cached data and child exporters.

        Clears animation frame dicts, source frames, and composite name
        tracking. Drops references to the frame pipeline and exporters so
        their buffers can be reclaimed.
        """

        if isinstance(getattr(self, "animations", None), dict):
            self.animations.clear()
        if isinstance(getattr(self, "_source_frames", None), dict):
            self._source_frames.clear()

        self.animations = None
        self._source_frames = None
        if hasattr(self, "_editor_composite_names"):
            self._editor_composite_names.clear()
        self._frame_pipeline = None
        self.frame_exporter = None
        self.animation_exporter = None
