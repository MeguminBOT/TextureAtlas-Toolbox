"""Centralized application version constants and helpers.

Exports the current version string, GitHub API URLs, and a utility for
parsing semantic version tags into comparable tuples.
"""

from __future__ import annotations

import re

APP_NAME = "TextureAtlas Toolbox"
APP_VERSION = "2.0.2"
REPO_OWNER = "MeguminBOT"
REPO_NAME = "TextureAtlas-Toolbox"

_API_ROOT = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
GITHUB_TAGS_URL = f"{_API_ROOT}/tags"
GITHUB_RELEASES_URL = f"{_API_ROOT}/releases"
GITHUB_RELEASE_BY_TAG_URL = f"{GITHUB_RELEASES_URL}/tags/{{tag}}"
GITHUB_LATEST_RELEASE_URL = f"{GITHUB_RELEASES_URL}/latest"

_SUFFIX_PRIORITY = {"alpha": 0, "beta": 1, "": 2}
_SUFFIX_PATTERN = re.compile(r"-(?P<label>[A-Za-z]+)$")
_SEMVER_PREFIX = re.compile(r"^\s*[vV]?\d")


def version_to_tuple(version: str) -> tuple[int, ...]:
    """Parse a semantic version string into a comparable tuple.

    Supports optional ``v``/``V`` prefix and ``-alpha``/``-beta`` suffixes.
    Non-semantic tags raise ``ValueError``.

    Args:
        version: Version string like ``v1.2.3`` or ``1.2.0-beta``.

    Returns:
        Tuple of version segments with a trailing suffix rank.

    Raises:
        ValueError: If ``version`` is not a valid semantic version.
    """

    if not _SEMVER_PREFIX.match(version or ""):
        raise ValueError("Version tag must begin with a semantic number")

    cleaned = version.strip().lstrip("vV")
    suffix_label = ""

    match = _SUFFIX_PATTERN.search(cleaned)
    if match:
        candidate = match.group("label").lower()
        if candidate in _SUFFIX_PRIORITY:
            suffix_label = candidate
        cleaned = cleaned[: match.start()]

    digit_chunks = re.findall(r"\d+", cleaned)
    parts = tuple(int(chunk) for chunk in digit_chunks) or (0,)
    suffix_rank = _SUFFIX_PRIORITY[suffix_label]
    return parts + (suffix_rank,)


__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "REPO_OWNER",
    "REPO_NAME",
    "GITHUB_TAGS_URL",
    "GITHUB_RELEASES_URL",
    "GITHUB_RELEASE_BY_TAG_URL",
    "GITHUB_LATEST_RELEASE_URL",
    "version_to_tuple",
]
