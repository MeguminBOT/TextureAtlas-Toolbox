# Licenses and Notices

This project is distributed under the GNU Affero General Public License v3.0 or later (see `LICENSE`). The table below lists primary third-party components and their licenses. Always consult the upstream package for the complete, authoritative license text.

> This document is for convenience only and is not legal advice.

## Core Components

| Component | Version | License | Notes |
| --- | --- | --- | --- |
| TextureAtlas Toolbox (this project) | — | AGPL-3.0-or-later | Source available in this repository. |
| PySide6 / Qt | 6.9.2 | LGPL-3.0-or-later | Keep Qt/PySide6 license files with your distribution; dynamic linking is required for LGPL compliance. |
| NumPy | 2.2.0 | BSD-3-Clause | Standard NumPy license. |
| Pillow | 11.3.0 | HPND/PIL | Historical Permission Notice and Disclaimer (PIL License). |
| Wand | 0.6.13 | MIT | Python bindings for ImageMagick. |
| requests | 2.32.3 | Apache-2.0 | HTTP client library. |
| urllib3 | 2.2.3 | MIT | Dependency of `requests`. |
| certifi | 2024.8.30 | MPL-2.0 | Certificate bundle. |
| charset-normalizer | 3.4.0 | MIT | Text encoding detection. |
| colorama | 0.4.6 | BSD-3-Clause | Cross-platform terminal colors. |
| idna | 3.10 | BSD-3-Clause | IDNA support. |
| psutil | 6.1.0 | BSD-3-Clause | Process utilities. |
| py7zr | 1.0.0 | LGPL-2.1-or-later | 7zip archive support. |
| etcpak | 0.9.15 | MIT | GPU texture compression (BC1/BC3/BC7, ETC1/ETC2). |
| tqdm | 4.67.1 | MPL-2.0 | Progress bars. |

## Licenses
Links to licenses:

- [AGPL-3.0](licenses/agpl-3.0.md)
- [LGPL-3.0](licenses/lgpl-3.0.md)
- [LGPL-2.1](licenses/lgpl-2.1.md)
- [MPL-2.0](licenses/mpl-2.0.md)
- [Apache-2.0](licenses/apache-2.0.md)
- [BSD-3-Clause](licenses/bsd-3-clause.md)
- [MIT](licenses/mit.md)
- [HPND/PIL](licenses/hpnd-pil.md)

## Qt / PySide6 notice

- Include the LGPL-3.0 license text with your builds (e.g., `LICENSES/LGPL-3.0.txt` or the `pyside6-licenses` directory shipped with the wheel).
- Do not statically link Qt; keep PySide6/Qt as replaceable shared libraries. If you modify Qt/PySide6 itself, provide corresponding source or a written offer.

## Other dependencies

The versions above come from `setup/requirements.txt`. If you add or upgrade dependencies, update this file accordingly and review their licenses.
