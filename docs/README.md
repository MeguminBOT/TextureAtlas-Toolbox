# Documentation Hub

TextureAtlas Toolbox v3.0.0 ships with a fully Qt-based (PySide6) user interface covering
extraction, atlas generation, GPU texture compression, and manual alignment. This folder contains the official
documentation that mirrors the current UI and APIs.

## Contents

| Document | Description |
|----------|-------------|
| [Installation Guide](installation-guide.md) | Platform-specific setup for Windows, macOS, and Linux |
| [User Manual](user-manual.md) | Walkthrough of the Extract, Generate, Editor, and Optimize tabs |
| [Format Reference](format-reference.md) | In-depth technical specs for all supported atlas formats |
| [FAQ](faq.md) | Quick answers and troubleshooting steps |
| [Friday Night Funkin' Guide](fnf-guide.md) | Engine-specific workflows and FlxSprite offset tips |
| [Developer Documentation](developer-docs.md) | Architecture overview and contributor onboarding |
| [API Reference](api-reference.md) | Key classes, callbacks, and extension points |
| [Release Notes](release-notes.md) | Version history and migration guidance |
| [Module Dependencies](module-dependencies.md) | Internal module dependency map and impact lookup |
| [Translation Guide](translation-guide.md) | Working with Qt `.ts` files for localization |
| [Licenses](licenses.md) | Project license and third-party license summaries |


## How to Use These Docs

1. **New to the tool?** Start with the [Installation Guide](installation-guide.md), then follow
   the quick-start path in the [User Manual](user-manual.md).
2. **Encountering an issue?** Check the [FAQ](faq.md), then open a GitHub issue if the fix is
   not listed.
3. **Building new exporters or packers?** Review the [Developer Docs](developer-docs.md) and
   [API Reference](api-reference.md) before touching `core/`, `packers/`, or `exporters/`.
4. **Localizing the UI?** The [Translation Guide](translation-guide.md) explains how to edit
   `.ts` files, run the helper scripts, and validate placeholders.

## Screenshots

Screenshots are stored in the `images/` subdirectory. If you notice the UI has changed and screenshots have not been updated, feel free to make a pull request with new screenshots!

<!-- TODO: Add main screenshots here when available -->

## Reporting Issues

If something is unclear or out of date, please open a documentation issue so we can keep the
docs synced with the codebase.

---

*Last updated: April 22, 2026 — TextureAtlas Toolbox v3.0.0*
