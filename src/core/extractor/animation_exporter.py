"""Export frame sequences to animated image formats.

Provides ``AnimationExporter`` which writes GIF, WebP, and APNG files from
a sequence of frames (PIL Images or NumPy arrays), handling scaling, cropping,
duration calculation, and duplicate frame removal.
"""

import os
from typing import Optional, Sequence, Set

import numpy
from PIL.PngImagePlugin import PngInfo
from wand.color import Color
from wand.image import Image as WandImg

from core.extractor.frame_pipeline import (
    build_frame_durations,
    compute_shared_bbox,
    prepare_scaled_sequence,
)
from core.extractor.image_utils import (
    apply_alpha_threshold,
    FrameSource,
    crop_to_bbox,
    ensure_rgba_array,
    frame_dimensions,
    pad_frames_to_canvas,
)
from utils.resampling import get_wand_resampling_filter
from utils.utilities import Utilities


class AnimationExporter:
    """Export frame sequences to GIF, WebP, or APNG animations.

    Attributes:
        output_dir: Directory where exported animations are saved.
        current_version: Version string embedded in file metadata.
        scale_image: Callable used to resize frames before export.
    """

    def __init__(self, output_dir, current_version, scale_image_func):
        """Initialise the exporter with output path and helpers.

        Args:
            output_dir: Filesystem path for saved animations.
            current_version: Version string for metadata comments.
            scale_image_func: Callable ``(image, scale) -> image`` for resizing.
        """
        self.output_dir = output_dir
        self.current_version = current_version
        self.scale_image = scale_image_func

    def save_animations(self, image_tuples, spritesheet_name, animation_name, settings):
        """Export an animation from the given frame tuples.

        Dispatches to the appropriate format-specific method based on
        ``settings["animation_format"]``.

        Args:
            image_tuples: Sequence of ``(name, image, metadata)`` tuples.
            spritesheet_name: Name of the source spritesheet.
            animation_name: Label for the animation.
            settings: Dict containing fps, delay, scale, format, etc.

        Returns:
            Number of animations successfully exported (0 or 1).
        """
        anims_generated = 0

        if not image_tuples:
            print(
                f"No frames available for animation: {animation_name}, skipping animation export"
            )
            return anims_generated

        animation_format = settings.get("animation_format", "GIF")

        # Duration is stored in milliseconds internally
        delay_ms = settings.get("duration", 42)
        # Convert milliseconds to fps for frame duration calculations
        fps = max(1, round(1000 / delay_ms)) if delay_ms > 0 else 24

        delay = settings.get("delay")
        period = settings.get("period")
        scale = settings.get("scale")
        threshold = settings.get("threshold")

        images = pad_frames_to_canvas([img[1] for img in image_tuples])

        filename = settings.get("filename")

        if not filename:
            filename = Utilities.format_filename(
                settings.get("prefix"),
                spritesheet_name,
                animation_name,
                settings.get("filename_format"),
                settings.get("replace_rules"),
                settings.get("suffix"),
            )

        if animation_format == "GIF":
            self.save_gif(
                images, filename, fps, delay, period, scale, threshold, settings
            )
        elif animation_format == "WebP":
            self.save_webp(images, filename, fps, delay, period, scale, settings)
        elif animation_format == "APNG":
            self.save_apng(images, filename, fps, delay, period, scale, settings)

        anims_generated += 1
        return anims_generated

    def save_webp(
        self,
        images: Sequence[FrameSource],
        filename,
        fps,
        delay,
        period,
        scale,
        settings,
    ):
        """Save frames as a lossless animated WebP.

        Args:
            images: Sequence of frame images.
            filename: Base filename without extension.
            fps: Frames per second for timing.
            delay: Per-frame delay override list or ``None``.
            period: Total loop period in ms, or ``None``.
            scale: Scale factor (negative flips horizontally).
            settings: Additional options such as ``crop_option``.
        """
        final_images = prepare_scaled_sequence(
            images,
            self.scale_image,
            scale,
            settings.get("crop_option"),
        )
        if not final_images:
            return

        custom_durations = settings.get("custom_frame_durations")
        if custom_durations and len(custom_durations) == len(final_images):
            durations = list(custom_durations)
        else:
            durations = build_frame_durations(
                len(final_images),
                fps,
                delay,
                period,
                settings.get("var_delay", False),
            )
        if not durations:
            return

        webp_filename = os.path.join(self.output_dir, f"{filename}.webp")

        final_images[0].save(
            webp_filename,
            save_all=True,
            append_images=final_images[1:],
            disposal=2,
            duration=durations,
            loop=0,
            lossless=True,
        )
        print(f"Saved WEBP animation: {webp_filename}")

    def remove_dups(self, animation):
        """Remove duplicate frames from a Wand animation in place.

        Consecutive frames with zero distortion are merged by accumulating
        their delays onto the preceding frame.

        Args:
            animation: A ``wand.image.Image`` sequence to deduplicate.
        """
        animation.iterator_reset()
        if len(animation.sequence) < 2:
            return

        while animation.iterator_next():
            index = animation.iterator_get()
            if index == 0:
                continue

            if (
                animation.get_image_distortion(
                    animation.sequence[index - 1], metric="absolute"
                )
                == 0
            ):
                delay = animation.delay
                animation.image_remove()
                animation.iterator_set(index - 1)
                animation.delay += delay

    def save_gif(
        self,
        images: Sequence[FrameSource],
        filename,
        fps,
        delay,
        period,
        scale,
        threshold,
        settings,
    ):
        """Save frames as an animated GIF using ImageMagick via Wand.

        Applies optional cropping, alpha thresholding, duplicate removal,
        quantization, and scaling before writing the file.

        Args:
            images: Sequence of frame images.
            filename: Base filename without extension.
            fps: Frames per second for timing.
            delay: Per-frame delay override list or ``None``.
            period: Total loop period in ms, or ``None``.
            scale: Scale factor (negative flips horizontally).
            threshold: Alpha threshold for edge cleanup, or ``None``.
            settings: Additional options such as ``crop_option``.
        """
        custom_durations = settings.get("custom_frame_durations")
        if custom_durations and len(custom_durations) == len(images):
            # Round to 10ms for GIF compatibility
            durations = [max(10, (d // 10) * 10) for d in custom_durations]
        else:
            durations = build_frame_durations(
                len(images),
                fps,
                delay,
                period,
                settings.get("var_delay", False),
                round_to_ten=True,
            )
        if not durations:
            return

        width, height = frame_dimensions(images[0])
        frame_arrays = [ensure_rgba_array(frame) for frame in images]
        crop_option = settings.get("crop_option")
        crop_mode = (crop_option or "None").lower()
        should_crop = crop_mode != "none"
        crop_bounds = None
        if should_crop:
            crop_bounds = compute_shared_bbox(frame_arrays)
            if crop_bounds is None:
                should_crop = False
            else:
                frame_arrays = [
                    crop_to_bbox(array, crop_bounds) for array in frame_arrays
                ]

        apply_threshold = should_crop and threshold is not None
        if apply_threshold:
            try:
                threshold_value = float(threshold)
            except (TypeError, ValueError):
                apply_threshold = False
            else:
                frame_arrays = [
                    apply_alpha_threshold(array, threshold_value)
                    for array in frame_arrays
                ]

        merge_duplicates = settings.get("merge_duplicate_frames", True)
        dedupe_required = False
        signature_cache: Optional[Set[int]] = (
            set() if len(images) > 1 and merge_duplicates else None
        )

        with WandImg(width=width, height=height) as animation:
            animation.image_remove()
            for index, frame in enumerate(images):
                arr = frame_arrays[index]
                if signature_cache is not None and not dedupe_required:
                    signature = self._frame_signature(arr)
                    if signature is None:
                        print(
                            "[AnimationExporter] Unable to hash frame data; falling back to duplicate pruning."
                        )
                        dedupe_required = True
                        signature_cache = None
                    elif signature in signature_cache:
                        dedupe_required = True
                        signature_cache = None
                    else:
                        signature_cache.add(signature)
                with self._wand_from_array(arr) as wand_frame:
                    wand_frame.background_color = Color("None")
                    wand_frame.alpha_channel = "background"

                    wand_frame.delay = int(durations[index] / 10)
                    wand_frame.dispose = "background"
                    animation.sequence.append(wand_frame)
            signature_cache = None
            if dedupe_required and merge_duplicates:
                self.remove_dups(animation)
            animation.quantize(
                number_colors=256, colorspace_type="undefined", dither=False
            )

            if dedupe_required and merge_duplicates:
                self.remove_dups(animation)

            resampling_method = settings.get("resampling_method", "Lanczos")
            wand_filter = get_wand_resampling_filter(resampling_method, abs(scale))

            for i in range(len(animation.sequence)):
                animation.iterator_set(i)
                new_width = int(animation.width * abs(scale))
                new_height = int(animation.height * abs(scale))

                if resampling_method == "Nearest":
                    animation.sample(width=new_width, height=new_height)
                else:
                    animation.resize(
                        width=new_width,
                        height=new_height,
                        filter=wand_filter,
                    )

                if scale < 0:
                    animation.flop()

            gif_filename = os.path.join(self.output_dir, f"{filename}.gif")
            animation.loop = 0
            animation.options["comment"] = (
                f"GIF generated by: TextureAtlas Toolbox v{self.current_version}"
            )
            animation.save(filename=gif_filename)
            print(f"Saved GIF animation: {gif_filename}")

    @staticmethod
    def _frame_signature(frame_array: numpy.ndarray) -> Optional[int]:
        """Compute a fast fingerprint of a frame for duplicate detection.
        Uses coarse spatial sampling to avoid hashing entire pixel buffers.

        Args:
            frame_array: RGBA NumPy array.

        Returns:
            An integer hash, or ``None`` if the array cannot be processed.
        """
        if frame_array.ndim < 2:
            return None

        try:
            step_y = max(1, frame_array.shape[0] // 64)
            step_x = max(1, frame_array.shape[1] // 64)
            sample = frame_array[::step_y, ::step_x]
        except Exception:
            sample = frame_array

        if sample.ndim == 3 and sample.shape[2] > 4:
            sample = sample[..., :4]

        try:
            sample = numpy.ascontiguousarray(sample)
            sample_bytes = sample.tobytes()
        except Exception:
            return None

        prefix = sample_bytes[:512]
        return hash((frame_array.shape, frame_array.dtype.str, prefix))

    @staticmethod
    def _wand_from_array(array: numpy.ndarray) -> WandImg:
        """Create a Wand image from an RGBA NumPy array.
        Ensures the array is contiguous uint8 before passing to Wand.

        Args:
            array: RGBA array with shape ``(H, W, 4)``.

        Returns:
            A new ``wand.image.Image``.

        Raises:
            ValueError: If ``array`` does not have at least 4 channels.
        """
        if array.ndim < 3 or array.shape[2] < 4:
            raise ValueError("Expected RGBA array with shape (H, W, 4)")

        if array.dtype != numpy.uint8 or not array.flags["C_CONTIGUOUS"]:
            array = numpy.ascontiguousarray(array, dtype=numpy.uint8)

        return WandImg.from_array(array)

    def save_apng(self, images, filename, fps, delay, period, scale, settings):
        """Save frames as an animated PNG.

        Args:
            images: Sequence of frame images.
            filename: Base filename without extension.
            fps: Frames per second for timing.
            delay: Per-frame delay override list or ``None``.
            period: Total loop period in ms, or ``None``.
            scale: Scale factor (negative flips horizontally).
            settings: Additional options such as ``crop_option``.
        """
        final_images = prepare_scaled_sequence(
            images,
            self.scale_image,
            scale,
            settings.get("crop_option"),
        )
        if not final_images:
            return

        custom_durations = settings.get("custom_frame_durations")
        if custom_durations and len(custom_durations) == len(final_images):
            durations = list(custom_durations)
        else:
            durations = build_frame_durations(
                len(final_images),
                fps,
                delay,
                period,
                settings.get("var_delay", False),
            )
        if not durations:
            return

        apng_filename = os.path.join(self.output_dir, f"{filename}.png")

        metadata = PngInfo()
        metadata.add_text(
            "Comment",
            f"APNG generated by TextureAtlas Toolbox v{self.current_version}",
        )

        final_images[0].save(
            apng_filename,
            save_all=True,
            append_images=final_images[1:],
            duration=durations,
            loop=0,
            format="PNG",
            disposal=2,
            pnginfo=metadata,
        )
        print(f"Saved APNG animation: {apng_filename}")
