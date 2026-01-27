"""2-D affine transform helpers for Adobe Spritemap rendering.

Provides ``TransformMatrix``, a thin wrapper around a 3x3 NumPy matrix that
supports parsing Adobe Animate's M3D arrays and composing transforms via the
``@`` operator.
"""

from __future__ import annotations

import numpy as np


class TransformMatrix:
    """2-D affine transformation matrix for Adobe Animate sprite transforms.

    Internally stores a 3x3 homogeneous matrix. Supports composition via
    ``@`` and conversion to PIL's 6-element affine tuple.

    Attributes:
        m: A 3x3 NumPy array representing the affine transform.
    """

    def __init__(self, m=None, a=1, b=0, c=0, d=0, e=1, f=0):
        """Construct a transform from an existing matrix or individual coefficients.

        Args:
            m: Optional 3x3 NumPy array. When provided, coefficient args are
                ignored.
            a: Scale X (default 1).
            b: Shear Y.
            c: Translate X.
            d: Shear X.
            e: Scale Y (default 1).
            f: Translate Y.
        """

        if m is None:
            self.m = np.array([[a, b, c], [d, e, f], [0, 0, 1]], dtype=float)
        else:
            self.m = m

    @classmethod
    def parse(cls, matrix_values):
        """Create a TransformMatrix from an Adobe Animate M3D list.

        Args:
            matrix_values: A 16-element list representing a 4x4 matrix in
                column-major order; only the 2-D affine portion is used.
                If ``None`` or empty, returns an identity transform.

        Returns:
            A new ``TransformMatrix`` instance.
        """
        if not matrix_values:
            return cls()

        return cls(
            a=matrix_values[0],
            b=matrix_values[4],
            c=matrix_values[12],
            d=matrix_values[1],
            e=matrix_values[5],
            f=matrix_values[13],
        )

    def data(self):
        """Return the inverse affine as a 6-element tuple for PIL.

        Returns:
            NumPy array of shape (6,) suitable for ``Image.transform``.
        """
        return np.linalg.inv(self.m).reshape(-1)[:6]

    def __matmul__(self, other):
        """Compose two transforms via the ``@`` operator.

        Args:
            other: Another ``TransformMatrix``.

        Returns:
            A new ``TransformMatrix`` representing ``self`` applied after
            ``other``.

        Raises:
            TypeError: If ``other`` is not a ``TransformMatrix``.
        """

        if not isinstance(other, TransformMatrix):
            raise TypeError(f"expected TransformMatrix, got {type(other)!r}")
        return TransformMatrix(m=self.m @ other.m)

    def __repr__(self):
        """Return a concise repr showing the affine coefficients."""

        a, b, c, d, e, f = self.m.reshape(-1)[:6]
        return f"TransformMatrix(a={a}, b={b}, c={c}, d={d}, e={e}, f={f})"

    def __eq__(self, other):
        """Matrices are equal when their flattened byte buffers match exactly."""
        return (
            isinstance(other, TransformMatrix) and self.m.tobytes() == other.m.tobytes()
        )

    def __hash__(self):
        """Hash matrix by its serialized byte contents."""
        return hash(self.m.tobytes())
