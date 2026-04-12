"""Sprite extraction and animation grouping from atlas images.

Provides ``SpriteProcessor`` which crops individual sprites from an atlas
and organizes them into animation groups based on naming conventions.
"""

import re

import numpy as np

from utils.utilities import Utilities


class SpriteProcessor:
    """Extract sprites from an atlas and group them into animations.

    Caches an RGBA NumPy view of the atlas so each sprite extraction is a
    cheap array slice rather than repeated PIL conversions.

    Attributes:
        atlas: Source PIL image.
        sprites: List of sprite metadata dicts from a parser.
    """

    def __init__(self, atlas, sprites, smart_animation_grouping: bool = True):
        """Initialise the processor with an atlas image and sprite metadata.

        Args:
            atlas: PIL image of the full atlas.
            sprites: List of sprite dicts with keys like ``name``, ``x``, ``y``, etc.
            smart_animation_grouping: When True, use batch-aware analysis to
                detect animation boundaries for non-tagged sprites. When False,
                fall back to simple trailing-digit stripping.
        """
        self.atlas = atlas
        self._atlas_rgba = atlas if atlas.mode == "RGBA" else atlas.convert("RGBA")
        self._atlas_array = np.ascontiguousarray(np.asarray(self._atlas_rgba))
        self.sprites = sprites
        self.smart_animation_grouping = smart_animation_grouping

    def process_sprites(self):
        """Process all sprites and group them into animations.

        For formats with animation tags (like Aseprite), groups by tag.
        Otherwise, when ``smart_animation_grouping`` is enabled, uses
        batch-aware analysis to detect animation boundaries; when disabled,
        groups by name prefix (strips trailing digits).

        Returns:
            Dict mapping animation names to lists of ``(name, image, metadata)``
            tuples where image is a NumPy array.
        """
        # Separate tagged from untagged sprites
        tagged_frames: dict[str, list] = {}
        untagged_sprites: list = []
        untagged_frame_tuples: dict[str, list[tuple]] = {}

        for sprite in self.sprites:
            frame_tuple = self._build_frame_tuple(sprite)
            if frame_tuple is None:
                continue

            animation_tag = sprite.get("animation_tag")
            if animation_tag:
                tagged_frames.setdefault(animation_tag, []).append(frame_tuple)
            else:
                untagged_sprites.append(sprite)
                name = frame_tuple[0]
                untagged_frame_tuples.setdefault(name, []).append(frame_tuple)

        animations: dict[str, list] = dict(tagged_frames)

        if untagged_sprites:
            if self.smart_animation_grouping:
                name_groups = Utilities.group_names_by_animation(
                    [s["name"] for s in untagged_sprites]
                )
                for animation_name, frame_names in name_groups.items():
                    group: list = []
                    for fname in frame_names:
                        group.extend(untagged_frame_tuples.get(fname, []))
                    animations.setdefault(animation_name, []).extend(group)
            else:
                for sprite in untagged_sprites:
                    frame_tuple = self._build_frame_tuple(sprite)
                    if frame_tuple is None:
                        continue
                    name = frame_tuple[0]
                    folder_name = Utilities.strip_trailing_digits(name)
                    animations.setdefault(folder_name, []).append(frame_tuple)

        return animations

    def process_specific_animation(self, animation_name):
        """Process only sprites belonging to a specific animation.

        For formats with animation tags (like Aseprite), matches by tag.
        Otherwise, uses flexible pattern matching to handle trailing digits
        and separator variations.

        Args:
            animation_name: Animation identifier to match against sprite names or tags.

        Returns:
            Dict mapping matched animation names to frame tuple lists.
        """
        tag_matched_sprites = [
            sprite
            for sprite in self.sprites
            if sprite.get("animation_tag") == animation_name
        ]

        if tag_matched_sprites:
            matching_sprites = tag_matched_sprites
        else:
            patterns = [
                animation_name,
                re.sub(r"\d+$", "", animation_name),
                re.sub(r"_?\d+$", "", animation_name),
                re.sub(r"[-_]?\d+$", "", animation_name),
            ]
            patterns = list(dict.fromkeys(patterns))

            matching_sprites = []
            for sprite in self.sprites:
                sprite_name = sprite.get("name", "")
                if any(
                    sprite_name == pat or sprite_name.startswith(pat)
                    for pat in patterns
                ):
                    matching_sprites.append(sprite)

        if not matching_sprites:
            return {}

        animations = {}
        for sprite in matching_sprites:
            frame_tuple = self._build_frame_tuple(sprite)
            if frame_tuple is None:
                continue

            animation_tag = sprite.get("animation_tag")
            if animation_tag:
                folder_name = animation_tag
            else:
                name = frame_tuple[0]
                folder_name = Utilities.strip_trailing_digits(name)

            animations.setdefault(folder_name, []).append(frame_tuple)

        return animations

    def _build_frame_tuple(self, sprite):
        """Build a frame tuple from a sprite metadata dict.
        Handles rotation, frame offsets, and canvas composition.

        Args:
            sprite: Dict with at least ``name``, ``x``, ``y``, ``width``, ``height``.

        Returns:
            Tuple ``(name, array, metadata)``, or ``None`` if required keys are missing.
        """
        try:
            name = sprite["name"]
            x, y, width, height = (
                sprite["x"],
                sprite["y"],
                sprite["width"],
                sprite["height"],
            )
        except KeyError:
            return None

        frame_x = sprite.get("frameX", 0)
        frame_y = sprite.get("frameY", 0)
        frame_width = sprite.get("frameWidth", width)
        frame_height = sprite.get("frameHeight", height)
        rotated = sprite.get("rotated", False)

        sprite_array = self._atlas_array[y : y + height, x : x + width]
        requires_canvas = rotated or frame_x or frame_y

        if rotated:
            sprite_array = np.rot90(sprite_array)
            sprite_height, sprite_width = sprite_array.shape[:2]
            frame_width = max(height - frame_x, frame_width, 1)
            frame_height = max(width - frame_y, frame_height, 1)
        else:
            sprite_height, sprite_width = sprite_array.shape[:2]
            frame_width = max(width - frame_x, frame_width, 1)
            frame_height = max(height - frame_y, frame_height, 1)

        if frame_width != sprite_width or frame_height != sprite_height:
            requires_canvas = True

        if requires_canvas:
            frame_array = self._compose_frame_array(
                sprite_array,
                frame_width,
                frame_height,
                frame_x,
                frame_y,
            )
        else:
            frame_array = sprite_array

        metadata = (x, y, width, height, frame_x, frame_y)
        return name, frame_array, metadata

    @staticmethod
    def _compose_frame_array(
        sprite_array: np.ndarray,
        frame_width: int,
        frame_height: int,
        frame_x: int,
        frame_y: int,
    ) -> np.ndarray:
        """Place the trimmed sprite onto its logical canvas.

        Args:
            sprite_array: Cropped sprite as a NumPy array.
            frame_width: Target canvas width.
            frame_height: Target canvas height.
            frame_x: Horizontal offset (negative moves sprite right).
            frame_y: Vertical offset (negative moves sprite down).

        Returns:
            RGBA NumPy array of the composed frame.
        """

        canvas = np.zeros(
            (frame_height, frame_width, sprite_array.shape[2]), dtype=np.uint8
        )

        # Negative frame offsets mean the sprite content belongs farther right/down on the canvas.
        dest_x = max(0, -frame_x)
        dest_y = max(0, -frame_y)
        src_x = max(0, frame_x)
        src_y = max(0, frame_y)

        copy_width = max(0, min(frame_width - dest_x, sprite_array.shape[1] - src_x))
        copy_height = max(0, min(frame_height - dest_y, sprite_array.shape[0] - src_y))

        if copy_width > 0 and copy_height > 0:
            canvas[
                dest_y : dest_y + copy_height,
                dest_x : dest_x + copy_width,
            ] = sprite_array[
                src_y : src_y + copy_height,
                src_x : src_x + copy_width,
            ]

        return canvas

    def dispose(self) -> None:
        """Release atlas and sprite references.

        Clears the cached NumPy array view and closes the underlying PIL
        image so large buffers can be garbage-collected.
        """

        self.sprites = None
        self._atlas_array = None
        if getattr(self, "_atlas_rgba", None) is not None:
            try:
                if self._atlas_rgba is not self.atlas and hasattr(
                    self._atlas_rgba, "close"
                ):
                    self._atlas_rgba.close()
            except Exception:
                pass
            finally:
                self._atlas_rgba = None

        if getattr(self, "atlas", None) is not None:
            try:
                if hasattr(self.atlas, "close"):
                    self.atlas.close()
            except Exception:
                pass
            finally:
                self.atlas = None
