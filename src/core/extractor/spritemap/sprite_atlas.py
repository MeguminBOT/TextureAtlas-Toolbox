"""Sprite atlas slicing and transformation for Adobe Spritemap exports.

Provides ``SpriteAtlas``, which indexes one or more spritemap pages, crops
sprites on demand, and applies affine transforms and colour effects before
returning render-ready images.

Multi-page (Better Texture Atlas) exports write ``spritemap1.json`` ...
``spritemapN.json`` with a matching image per page.  A single ``SpriteAtlas``
indexes every page so a symbol whose sprites straddle several sheets renders
correctly.  Page images are opened lazily and decoded only when a sprite from
that page is first requested, so unused pages never cost resident memory.
"""

from __future__ import annotations

import math
import threading
import warnings
from collections import OrderedDict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

import numpy as np
from PIL import Image

from .transform_matrix import TransformMatrix
from .color_effect import ColorEffect

#: Default ceiling for the decoded-crop cache, in pixels (~64 MB of RGBa).
DEFAULT_CACHE_PIXELS = 16 * 1024 * 1024


class _AtlasPage:
    """One spritemap sheet: its image source and metadata-vs-actual scaling.

    The image is opened lazily.  ``Image.open`` only reads the header, so a
    page that no requested sprite lives on is never decoded.

    Attributes:
        source: Filesystem path, or a pre-opened PIL ``Image``.
        scale_x: Horizontal actual-size / declared-size ratio.
        scale_y: Vertical actual-size / declared-size ratio.
        needs_rescale: ``True`` when the sheet was resized after export.
    """

    __slots__ = ("source", "_img", "_owns_img", "scale_x", "scale_y", "needs_rescale")

    def __init__(self, source: Union[str, Image.Image]) -> None:
        self.source = source
        self._img: Optional[Image.Image] = None
        self._owns_img = not isinstance(source, Image.Image)
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.needs_rescale = False

    def size(self) -> Tuple[int, int]:
        """Return the page's pixel size without forcing a full decode."""
        return self.image().size

    def loaded(self) -> Image.Image:
        """Return the page image with its pixel data decoded.

        Pillow decodes lazily on first pixel access, and that decode is not
        thread-safe: two threads cropping an undecoded PNG race inside the
        plugin's ``load_read``. Callers must hold the atlas lock here so the
        decode happens exactly once; cropping afterwards only reads the
        finished buffer and needs no lock.
        """
        image = self.image()
        image.load()
        return image

    def image(self) -> Image.Image:
        """Return the page image, opening it on first use (header only)."""
        if self._img is None:
            source = self.source
            if isinstance(source, Image.Image):
                self._img = source
            else:
                ext = source.rsplit(".", 1)[-1].lower() if "." in source else ""
                if ext in ("dds", "ktx2"):
                    from core.optimizer.texture_compress import load_gpu_texture

                    self._img = load_gpu_texture(source)
                else:
                    self._img = Image.open(source)
        return self._img

    def calibrate(self, spritemap_json: Dict[str, Any]) -> None:
        """Record how the on-disk sheet size relates to the declared size.

        Guards against sheets that were up/down-scaled after export, where
        the JSON boxes still refer to the original dimensions.
        """
        actual_w, actual_h = self.size()
        meta_size = (spritemap_json.get("meta") or {}).get("size") or {}
        declared_w = meta_size.get("w", actual_w) or actual_w
        declared_h = meta_size.get("h", actual_h) or actual_h
        self.scale_x = actual_w / declared_w if declared_w > 0 else 1.0
        self.scale_y = actual_h / declared_h if declared_h > 0 else 1.0
        self.needs_rescale = not (
            0.99 < self.scale_x < 1.01 and 0.99 < self.scale_y < 1.01
        )

    def close(self) -> None:
        """Close the page image if this page owns it."""
        if self._img is not None and self._owns_img:
            try:
                self._img.close()
            except Exception:
                pass
        self._img = None


class SpriteAtlas:
    """Index sprites across one or more spritemap pages and transform them.

    Sprites are cropped from their owning page on first access and held in a
    size-bounded LRU cache.  Only the crop is promoted to ``RGBa`` — the full
    sheet is never converted, which keeps a 4096x4096 page at its decoded
    ``RGBA`` cost instead of doubling it.

    Attributes:
        canvas_width: Target canvas width in pixels.
        canvas_height: Target canvas height in pixels.
        resample: Pillow resampling filter used for affine transforms.
        sprite_info: Dict mapping sprite names to box, rotation, and page.
    """

    def __init__(
        self,
        spritemap_json: Union[Dict[str, Any], Sequence[Dict[str, Any]]],
        atlas_image: Union[
            str, Image.Image, None, Sequence[Union[str, Image.Image]]
        ] = None,
        canvas_size: Tuple[int, int] = (0, 0),
        resample: int = Image.BICUBIC,
        cache_pixels: int = DEFAULT_CACHE_PIXELS,
    ):
        """Index sprite metadata for every page and prepare for cropping.

        Accepts either a single page (``spritemap_json`` dict plus one image)
        or parallel sequences describing several pages.  When a sprite name
        appears on more than one page the first occurrence wins, matching the
        page order supplied by the caller.

        Args:
            spritemap_json: One parsed spritemap dict, or a sequence of them.
            atlas_image: Matching image path/``Image``, or a sequence of them.
            canvas_size: ``(width, height)`` of the target render canvas.
            resample: Pillow resampling constant (e.g., ``Image.BICUBIC``).
            cache_pixels: Soft ceiling on cached crop pixels before eviction.
        """
        page_jsons = self._as_sequence(spritemap_json)
        page_images = self._as_sequence(atlas_image)

        if len(page_images) < len(page_jsons):
            page_images = list(page_images) + [None] * (
                len(page_jsons) - len(page_images)
            )

        self.canvas_width, self.canvas_height = canvas_size
        self.resample = resample
        self.sprite_info: Dict[str, Dict[str, Any]] = {}
        self.pages: List[_AtlasPage] = []
        self._cache: "OrderedDict[str, Image.Image]" = OrderedDict()
        self._cache_pixels = 0
        self._cache_limit = max(1, int(cache_pixels))
        # Guards the crop cache and lazy page opening so frames can be
        # rendered concurrently.
        self._lock = threading.RLock()

        for index, page_json in enumerate(page_jsons):
            image_source = page_images[index] if index < len(page_images) else None
            if image_source is None:
                continue
            page = _AtlasPage(image_source)
            try:
                page.calibrate(page_json or {})
            except Exception:
                # A page whose image cannot be opened is skipped rather than
                # aborting the whole render; its sprites simply resolve empty.
                page.close()
                continue
            page_index = len(self.pages)
            self.pages.append(page)

            for sprite in (page_json or {}).get("ATLAS", {}).get("SPRITES", []):
                data = sprite["SPRITE"] if "SPRITE" in sprite else sprite
                name = data.get("name")
                if name is None:
                    continue
                name = str(name)
                if name in self.sprite_info:
                    continue
                x = data.get("x", 0)
                y = data.get("y", 0)
                w = data.get("w", 0)
                h = data.get("h", 0)
                self.sprite_info[name] = {
                    "box": (x, y, x + w, y + h),
                    "rotated": bool(data.get("rotated", False)),
                    "page": page_index,
                }

    @staticmethod
    def _as_sequence(value: Any) -> List[Any]:
        """Normalize a scalar-or-sequence argument into a list."""
        if value is None:
            return []
        if isinstance(value, (str, bytes, dict, Image.Image)):
            return [value]
        if isinstance(value, Iterable):
            return list(value)
        return [value]

    @property
    def img(self) -> Optional[Image.Image]:
        """Return the first page image.

        Retained so existing single-page callers that reach for ``.img``
        keep working; multi-page code should go through ``get_sprite``.
        """
        return self.pages[0].image() if self.pages else None

    def _cropped(self, name: str) -> Optional[Image.Image]:
        """Return the cached ``RGBa`` crop for *name*, cropping on first use.

        Safe to call from several render threads. The crop itself happens
        outside the lock so decoding never serialises the pool; two threads
        racing on the same miss simply both produce it and the second insert
        wins, which is harmless.
        """
        with self._lock:
            cached = self._cache.get(name)
            if cached is not None:
                self._cache.move_to_end(name)
                return cached

        info = self.sprite_info.get(name)
        if info is None:
            return None

        page_index = info["page"]
        if page_index >= len(self.pages):
            return None
        page = self.pages[page_index]

        try:
            # Decoding mutates the page image and is not thread-safe, so
            # serialise just that step; the crop below runs unlocked.
            with self._lock:
                source = page.loaded()
        except Exception:
            return None

        box = info["box"]
        if page.needs_rescale:
            scaled_box = (
                round(box[0] * page.scale_x),
                round(box[1] * page.scale_y),
                round(box[2] * page.scale_x),
                round(box[3] * page.scale_y),
            )
            sprite = source.crop(scaled_box)
            orig_w = box[2] - box[0]
            orig_h = box[3] - box[1]
            if sprite.size != (orig_w, orig_h):
                sprite = sprite.resize((orig_w, orig_h), self.resample)
        else:
            sprite = source.crop(box)

        # Promote only the crop, never the whole sheet. "P" needs an
        # explicit RGBA hop first so the palette alpha survives.
        if sprite.mode == "P":
            sprite = sprite.convert("RGBA")
        if sprite.mode != "RGBa":
            sprite = sprite.convert("RGBa")

        if info["rotated"]:
            sprite = sprite.transpose(Image.ROTATE_90)

        self._store(name, sprite)
        return sprite

    def _store(self, name: str, sprite: Image.Image) -> None:
        """Insert a crop into the LRU cache, evicting until under budget.

        Evicted crops are dropped, never closed: another thread may still be
        transforming one, and closing it out from under that thread would
        corrupt the render. Releasing the reference lets the GC reclaim the
        buffer once the last user is finished.
        """
        with self._lock:
            if name in self._cache:
                # Another thread produced the same crop first; keep theirs so
                # the accounting stays consistent.
                self._cache.move_to_end(name)
                return
            self._cache[name] = sprite
            self._cache_pixels += sprite.width * sprite.height
            while self._cache_pixels > self._cache_limit and len(self._cache) > 1:
                evicted_name, evicted = self._cache.popitem(last=False)
                if evicted_name == name:
                    # Never evict the sprite we are about to return.
                    self._cache[name] = evicted
                    self._cache.move_to_end(name)
                    break
                self._cache_pixels -= evicted.width * evicted.height

    def get_sprite(
        self,
        name,
        matrix: TransformMatrix,
        color: ColorEffect,
        clip: Optional[Tuple[int, int]] = None,
    ):
        """Return a transformed sprite image and its canvas offset.

        The sprite is cropped from its page on first access and cached. The
        provided transform and colour effect are then applied.

        Args:
            name: Sprite identifier from the spritemap JSON.
            matrix: Affine transform to apply.
            color: Colour effect chain to apply before transforming.
            clip: ``(width, height)`` of the target canvas. Passed per call
                rather than read from the atlas so concurrent renders at
                different sizes cannot interfere; defaults to the atlas-wide
                canvas when omitted.

        Returns:
            A tuple ``(image, (x, y))`` where ``image`` is an RGBA PIL Image
            and ``(x, y)`` is the top-left canvas coordinate. Returns
            ``(None, None)`` if the sprite is out of bounds or unknown.
        """

        sprite = self._cropped(name) if name is not None else None
        if sprite is None:
            return None, None

        clip_width, clip_height = (
            clip if clip is not None else (self.canvas_width, self.canvas_height)
        )

        width, height = sprite.size
        corners = matrix.m @ np.array(
            [[0, width, 0, width], [0, 0, height, height], [1, 1, 1, 1]]
        )

        min_x = math.floor(min(corners[0]))
        max_x = math.ceil(max(corners[0]))
        min_y = math.floor(min(corners[1]))
        max_y = math.ceil(max(corners[1]))

        if max_x < 0 or clip_width <= min_x or max_y < 0 or clip_height <= min_y:
            warnings.warn(
                f"Sprite `{name}` is out of bounds, increase canvas size: "
                f"({min_x:.2f}, {min_y:.2f}) x ({max_x:.2f}, {max_y:.2f})"
            )
            return None, None

        min_x = max(0, min_x)
        max_x = min(clip_width - 1, max_x)
        min_y = max(0, min_y)
        max_y = min(clip_height - 1, max_y)

        transform_size = (max_x - min_x + 1, max_y - min_y + 1)
        matrix = TransformMatrix(c=-min_x, f=-min_y) @ matrix
        sprite = color(sprite)
        sprite = sprite.transform(
            transform_size, Image.AFFINE, data=matrix.data(), resample=self.resample
        )
        return sprite.convert("RGBA"), (min_x, min_y)

    def close(self) -> None:
        """Release cached crops and every page image."""

        for sprite in list(self._cache.values()):
            try:
                sprite.close()
            except Exception:
                pass
        self._cache.clear()
        self._cache_pixels = 0

        for page in self.pages:
            page.close()
        self.pages = []
