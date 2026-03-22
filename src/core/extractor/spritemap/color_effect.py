"""Color effect utilities for Adobe Spritemap support.

Provides the ``ColorEffect`` class which can parse, apply, and compose
RGBA colour transformations defined in Adobe Animate spritemap exports.
"""

from __future__ import annotations

import warnings
import numpy as np
from PIL import Image, ImageColor


class ColorEffect:
    """Encapsulates an RGBA multiplier/offset colour transformation.

    Instances can be applied to PIL images via ``__call__`` and composed
    together using the ``@`` operator.
    """

    def __init__(self, effect=None):
        """Store the multiplier/offset pair representing this effect.

        Args:
            effect: A tuple of (multiplier, offset) NumPy arrays, or ``None``
                for the identity transform.
        """
        self.effect = effect

    @classmethod
    def parse(cls, effect):
        """Convert a Spritemap color effect dictionary into a ColorEffect.
        Supports modes: ``AD`` (advanced), ``CA`` (alpha), ``CBRT`` (brightness),
        and ``T`` (tint). Unsupported modes emit a warning and return identity.

        Args:
            effect: Dict with at least a ``"M"`` (mode) key.

        Returns:
            A configured ``ColorEffect`` instance.
        """

        mode = effect.get("M")
        if mode == "AD":
            multiplier = np.array(
                [effect["RM"], effect["GM"], effect["BM"], effect["AM"]]
            )
            offset = np.array([effect["RO"], effect["GO"], effect["BO"], effect["AO"]])
        elif mode == "CA":
            multiplier = np.array([1, 1, 1, effect["AM"]])
            offset = np.zeros(4)
        elif mode == "CBRT":
            brightness = effect["BRT"]
            if brightness < 0:
                multiplier = np.array(
                    [1 + brightness, 1 + brightness, 1 + brightness, 1]
                )
                offset = np.zeros(4)
            else:
                multiplier = np.array(
                    [1 - brightness, 1 - brightness, 1 - brightness, 1]
                )
                offset = brightness * np.array([255, 255, 255, 0])
        elif mode == "T":
            tint_color = ImageColor.getrgb(effect["TC"])
            tint_multiplier = effect["TM"]
            multiplier = np.array(
                [1 - tint_multiplier, 1 - tint_multiplier, 1 - tint_multiplier, 1]
            )
            offset = tint_multiplier * np.array([*tint_color, 0])
        else:
            warnings.warn(f"Unsupported color effect: {effect}")
            return cls()

        return cls((multiplier, offset))

    def __call__(self, image):
        """Apply the configured color effect to a PIL image.

        Args:
            image: A PIL ``Image`` in any mode.

        Returns:
            A new ``Image`` with the effect applied, converted back to the
            original mode.
        """

        if self.effect is None:
            return image

        mode = image.mode
        image = image.convert("RGBA")
        multiplier, offset = self.effect
        arr = (np.array(image) * multiplier + offset).clip(0, 255).astype("uint8")
        try:
            image = Image.fromarray(arr, mode="RGBA")
        except TypeError:
            h, w = arr.shape[:2]
            image = Image.frombytes("RGBA", (w, h), arr.tobytes())
        return image.convert(mode)

    def __eq__(self, other):
        """Check equality by comparing multiplier and offset arrays.

        Args:
            other: Another object to compare.

        Returns:
            ``True`` if both effects are identical or both are identity.
        """

        if not isinstance(other, ColorEffect):
            return False
        if self.effect is None or other.effect is None:
            return self.effect is other.effect
        multiplier_self, offset_self = self.effect
        multiplier_other, offset_other = other.effect
        return (
            multiplier_self.tobytes() == multiplier_other.tobytes()
            and offset_self.tobytes() == offset_other.tobytes()
        )

    def __hash__(self):
        """Return a hash based on the raw bytes of multiplier and offset."""

        if self.effect is None:
            return hash(None)
        multiplier, offset = self.effect
        return hash((multiplier.tobytes(), offset.tobytes()))

    def __matmul__(self, other):
        """Compose two effects via the ``@`` operator.
        The resulting effect applies ``other`` first, then ``self``.

        Args:
            other: Another ``ColorEffect``.

        Returns:
            A new ``ColorEffect`` representing the composition.

        Raises:
            TypeError: If ``other`` is not a ``ColorEffect``.
        """

        if not isinstance(other, ColorEffect):
            raise TypeError(f"expected ColorEffect, got {type(other)!r}")
        if self.effect is None:
            return other
        if other.effect is None:
            return self
        multiplier_self, offset_self = self.effect
        multiplier_other, offset_other = other.effect
        return ColorEffect(
            (
                multiplier_self * multiplier_other,
                multiplier_self * offset_other + offset_self,
            )
        )

    def __repr__(self):
        """Return a string suitable for debugging."""
        return f"ColorEffect({self.effect!r})"
