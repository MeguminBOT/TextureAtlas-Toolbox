"""Frame export utilities for saving animation frames to disk.

Provides ``FrameExporter`` which writes individual frames as image files
in various formats (PNG, WebP, AVIF, etc.) with configurable cropping,
scaling, and compression options.
"""

import os
from PIL.PngImagePlugin import PngInfo

from core.extractor.animation_exporter import _build_exif_comment
from core.extractor.image_utils import ensure_pil_image
from utils.utilities import Utilities


class FrameExporter:
    """Export individual animation frames as image files.

    Supports multiple output formats and applies cropping, scaling, and
    compression based on user settings.

    Attributes:
        output_dir: Directory where exported frames are saved.
        current_version: Version string embedded in image metadata.
        scale_image: Callable that scales a PIL image by a given factor.
    """

    def __init__(self, output_dir, current_version, scale_image_func):
        """Initialise the frame exporter.

        Args:
            output_dir: Base directory for exported frame folders.
            current_version: Version string for file metadata comments.
            scale_image_func: Callable ``(image, scale) -> image`` for resizing.
        """
        self.output_dir = output_dir
        self.current_version = current_version
        self.scale_image = scale_image_func

    def save_frames(
        self,
        image_tuples,
        kept_frame_indices,
        spritesheet_name,
        animation_name,
        scale,
        settings,
        is_unknown_spritesheet=False,
        progress_callback=None,
    ):
        """Save selected frames to disk as individual image files.

        Creates a subfolder named after the animation and writes each kept
        frame using the format and compression settings provided.

        Args:
            image_tuples: Sequence of ``(name, image, metadata)`` tuples where
                image is a PIL Image or NumPy array.
            kept_frame_indices: Set of indices indicating which frames to export.
            spritesheet_name: Name used when formatting output filenames.
            animation_name: Subfolder name for the exported frames.
            scale: Default scale factor if not overridden in settings.
            settings: Dict with keys like ``frame_format``, ``crop_option``, etc.
            is_unknown_spritesheet: When ``True``, applies extra cropping.
            progress_callback: Optional ``(current, total)`` callable invoked
                after each frame is saved, for sub-progress display.

        Returns:
            Number of frames successfully exported.
        """
        frames_generated = 0
        if len(image_tuples) == 0:
            return frames_generated

        total_kept = len(kept_frame_indices)
        frame_format = settings.get("frame_format", "PNG")
        frame_scale = settings.get("frame_scale", scale)

        safe_animation_folder = Utilities.sanitize_path_name(animation_name)
        frames_folder = os.path.join(self.output_dir, safe_animation_folder)
        os.makedirs(frames_folder, exist_ok=True)

        crop_option = settings.get("crop_option")

        format_extensions = {
            "AVIF": ".avif",
            "BMP": ".bmp",
            "DDS": ".dds",
            "PNG": ".png",
            "TGA": ".tga",
            "TIFF": ".tiff",
            "WebP": ".webp",
        }
        file_extension = format_extensions.get(frame_format, ".png")

        # Normalize crop_option to lowercase for comparison (supports legacy values)
        crop_option_lower = crop_option.lower() if crop_option else ""

        animation_bbox = None
        if crop_option_lower in ("animation based", "animation"):
            animation_bbox = self._compute_animation_bbox(
                image_tuples, kept_frame_indices
            )
            if animation_bbox is None:
                return frames_generated

        for index, frame in enumerate(image_tuples):
            if index in kept_frame_indices:
                frame_name = Utilities.basename_from_sprite_name(frame[0])
                formatted_frame_name = Utilities.format_filename(
                    settings.get("prefix"),
                    spritesheet_name,
                    frame_name,
                    settings.get("filename_format"),
                    settings.get("replace_rules"),
                    settings.get("suffix"),
                )

                frame_filename = os.path.join(
                    frames_folder, f"{formatted_frame_name}{file_extension}"
                )
                frame_image = ensure_pil_image(frame[1])
                final_frame_image = self._prepare_frame_image(
                    frame_image,
                    crop_option,
                    animation_bbox,
                    frame_scale,
                    is_unknown_spritesheet,
                )
                if final_frame_image is None:
                    continue

                self._save_frame_to_image(
                    final_frame_image,
                    frame_filename,
                    frame_format,
                    settings.get("compression_settings"),
                )
                frames_generated += 1
                if progress_callback:
                    progress_callback(frames_generated, total_kept)
        return frames_generated

    def _prepare_frame_image(
        self,
        frame_image,
        crop_option,
        animation_bbox,
        frame_scale,
        is_unknown_spritesheet,
    ):
        """Crop and scale a frame image before saving.

        Args:
            frame_image: PIL image to process.
            crop_option: ``"frame"``, ``"animation"``, or ``None``.
                Also accepts legacy values ``"Frame based"``, ``"Animation based"``.
            animation_bbox: Precomputed bounding box for animation-based crop.
            frame_scale: Scale factor to apply after cropping.
            is_unknown_spritesheet: When ``True``, runs an extra crop pass.

        Returns:
            Processed PIL image, or ``None`` if the frame is fully transparent.
        """
        bbox = frame_image.getbbox()
        if bbox is None:
            return None

        # Normalize crop_option for comparison (supports legacy values)
        crop_option_lower = crop_option.lower() if crop_option else ""

        working = frame_image
        if crop_option_lower in ("frame based", "frame") and bbox is not None:
            working = working.crop(bbox)
        elif (
            crop_option_lower in ("animation based", "animation")
            and animation_bbox is not None
        ):
            working = working.crop(animation_bbox)

        if is_unknown_spritesheet:
            working = self._apply_extra_crop_pass(working)

        return self.scale_image(working, frame_scale)

    @staticmethod
    def _compute_animation_bbox(image_tuples, kept_frame_indices):
        """Compute the union bounding box across all kept frames.

        Args:
            image_tuples: Sequence of ``(name, image, metadata)`` tuples where
                image is a PIL Image or NumPy array.
            kept_frame_indices: Indices of frames to include in the calculation.

        Returns:
            Tuple ``(left, top, right, bottom)``, or ``None`` if no valid bbox.
        """
        min_x, min_y, max_x, max_y = float("inf"), float("inf"), 0, 0
        for index, frame in enumerate(image_tuples):
            if index in kept_frame_indices:
                bbox = ensure_pil_image(frame[1]).getbbox()
                if bbox:
                    min_x = min(min_x, bbox[0])
                    min_y = min(min_y, bbox[1])
                    max_x = max(max_x, bbox[2])
                    max_y = max(max_y, bbox[3])

        if min_x > max_x or min_y > max_y:
            return None
        return (min_x, min_y, max_x, max_y)

    def _save_frame_to_image(
        self, image, filename, frame_format, compression_settings=None
    ):
        """Write an image to disk in the specified format.

        Falls back to PNG if saving in the requested format fails.

        Args:
            image: PIL image to save.
            filename: Destination path including extension.
            frame_format: Format name (e.g., ``"PNG"``, ``"WebP"``).
            compression_settings: Optional dict of format-specific options.
        """
        save_kwargs = {}

        if compression_settings is None:
            compression_settings = {}

        if frame_format == "AVIF":
            save_kwargs["format"] = "AVIF"
            save_kwargs["lossless"] = compression_settings.get("avif_lossless", True)
            save_kwargs["quality"] = compression_settings.get("avif_quality", 100)
            save_kwargs["speed"] = compression_settings.get("avif_speed", 0)
            exif_bytes = _build_exif_comment(
                f"AVIF generated by TextureAtlas Toolbox v{self.current_version}"
            )
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes

        elif frame_format == "BMP":
            save_kwargs["format"] = "BMP"

        elif frame_format == "DDS":
            save_kwargs["format"] = "DDS"

        elif frame_format == "PNG":
            metadata = PngInfo()
            metadata.add_text(
                "Comment",
                f"PNG generated by TextureAtlas Toolbox v{self.current_version}",
            )
            save_kwargs["pnginfo"] = metadata
            save_kwargs["format"] = "PNG"
            save_kwargs["compress_level"] = compression_settings.get(
                "png_compress_level", 9
            )
            save_kwargs["optimize"] = compression_settings.get("png_optimize", True)

        elif frame_format == "TGA":
            save_kwargs["format"] = "TGA"
            save_kwargs["compression"] = compression_settings.get(
                "tga_compression", "tga_rle"
            )

        elif frame_format == "TIFF":
            save_kwargs["format"] = "TIFF"

            compression_type = compression_settings.get("tiff_compression_type", "lzw")
            save_kwargs["compression"] = (
                compression_type if compression_type != "none" else None
            )

            if compression_type == "jpeg":
                save_kwargs["quality"] = compression_settings.get("tiff_quality", 90)

            save_kwargs["optimize"] = compression_settings.get("tiff_optimize", True)

            if hasattr(image, "info"):
                image.info["description"] = (
                    f"TIFF generated by TextureAtlas Toolbox v{self.current_version}"
                )

        elif frame_format == "WebP":
            save_kwargs["format"] = "WebP"

            save_kwargs["lossless"] = compression_settings.get("webp_lossless", True)
            if not save_kwargs["lossless"]:
                save_kwargs["quality"] = compression_settings.get("webp_quality", 100)
            save_kwargs["method"] = compression_settings.get("webp_method", 6)
            save_kwargs["alpha_quality"] = compression_settings.get(
                "webp_alpha_quality", 100
            )
            save_kwargs["exact"] = compression_settings.get("webp_exact", True)
            exif_bytes = _build_exif_comment(
                f"WebP generated by TextureAtlas Toolbox v{self.current_version}"
            )
            if exif_bytes:
                save_kwargs["exif"] = exif_bytes

        try:
            image.save(filename, **save_kwargs)
            # print(f"Successfully saved {filename} as {frame_format}")

        except Exception as e:
            print(f"Error saving {filename} as {frame_format}: {e}")
            try:
                png_filename = filename.rsplit(".", 1)[0] + ".png"
                metadata = PngInfo()
                metadata.add_text(
                    "Comment",
                    f"PNG generated by TextureAtlas Toolbox v{self.current_version}",
                )
                image.save(
                    png_filename,
                    format="PNG",
                    pnginfo=metadata,
                    compress_level=9,
                    optimize=True,
                )
                print(f"Fallback: Successfully saved {png_filename} as PNG")
            except Exception as fallback_e:
                print(f"Critical error: Could not save image even as PNG: {fallback_e}")

    def _apply_extra_crop_pass(self, image):
        """Remove excess transparent padding if it reduces area significantly.

        Only crops when the new area is less than 75% of the original to avoid
        trimming minor padding.

        Args:
            image: PIL image to crop.

        Returns:
            Cropped image, or the original if cropping was skipped or failed.
        """
        try:
            bbox = image.getbbox()
            if bbox:
                padding = 2
                left, top, right, bottom = bbox
                width, height = image.size

                left = max(0, left - padding)
                top = max(0, top - padding)
                right = min(width, right + padding)
                bottom = min(height, bottom + padding)

                # Only crop if it would actually reduce the canvas size significantly
                # (avoid cropping if the reduction is minimal)
                new_width = right - left
                new_height = bottom - top
                original_area = width * height
                new_area = new_width * new_height

                if new_area < original_area * 0.75:
                    return image.crop((left, top, right, bottom))

            return image
        except Exception as e:
            print(f"Warning: Extra crop failed, using original image: {e}")
            return image
