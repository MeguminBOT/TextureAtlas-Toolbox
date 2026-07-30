"""Adobe Animate spritemap rendering and extraction utilities.

This subpackage handles texture atlases exported from Adobe Animate, parsing
the JSON metadata and rendering individual symbol animations frame-by-frame.

Modules:
    renderer: High-level ``AdobeSpritemapRenderer`` for extracting animations.
    sprite_atlas: Atlas image slicing and sprite lookup.
    symbols: Symbol hierarchy and timeline management.
    transform_matrix: 2-D affine transform helpers.
    color_effect: Colour/alpha effect application.
    metadata: Frame and symbol metadata structures.

Exports:
    AdobeSpritemapRenderer: Main entry point for rendering spritemap animations.
    discover_spritemap_pages: List every ``spritemap*.json`` page in a folder.
    is_secondary_spritemap_page: Identify follow-on pages of a multi-page set.
"""

from .renderer import (
    AdobeSpritemapRenderer,
    discover_spritemap_pages,
    is_secondary_spritemap_page,
)

__all__ = [
    "AdobeSpritemapRenderer",
    "discover_spritemap_pages",
    "is_secondary_spritemap_page",
]
