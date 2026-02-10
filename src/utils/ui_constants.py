#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Centralized UI constants for labels, group titles, tooltips, and widget configurations.

This module provides shared definitions for UI elements that appear across
multiple windows/dialogs, ensuring consistency and single-source-of-truth
for translations and configurations.

Usage:
    from utils.ui_constants import Labels, GroupTitles, Tooltips, SpinBoxConfig

    # Create a label with translation
    label = QLabel(tr_func(Labels.FRAME_RATE))

    # Create a group box with translation
    group = QGroupBox(tr_func(GroupTitles.ANIMATION_EXPORT))

    # Set a tooltip with translation
    widget.setToolTip(tr_func(Tooltips.ALPHA_THRESHOLD))

    # Configure a spinbox with shared defaults
    configure_spinbox(spinbox, SpinBoxConfig.FRAME_RATE)
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QT_TRANSLATE_NOOP


# =============================================================================
# Translation markers for pyside6-lupdate
# =============================================================================
# fmt: off
# Labels - Field labels used across multiple UI files
_LABEL_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Format"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation format"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame format"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame rate"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame scale"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame selection"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame Selection"),  # Title case variant
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Scale"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Cropping method"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Filename format"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Resampling method"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Resampling"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Alpha threshold"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Delay"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Loop delay"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Period"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Minimum period"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Min period"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Variable delay"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Indices"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frames"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Filename"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Position:"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Preview Zoom:"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Background:"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Enable animation export:"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Enable frame export:"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Loop preview"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Edit selected frame only"),
    # Compression settings labels (shared between app_config and compression_settings)
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Quality (0-100):"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Compress Level (0-9):"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Method (0-6):"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Alpha Quality (0-100):"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Speed (0-10):"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Compression Type:"),
    # Generator labels
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Heuristic"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Prefix"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Suffix"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Filename prefix"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Filename suffix"),
)

# Group box titles
_GROUP_TITLE_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation export"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation Export"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation Export Defaults"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation export settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation Settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame export"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame Export"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame Export Defaults"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame export settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "General Export Settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Export"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Export Settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Display"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Alignment Controls"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Display & snapping"),
)

# Button labels - Common button text used across UI
_BUTTON_LABEL_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "OK"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Cancel"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Close"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Save"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Apply"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Reset"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Delete"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Remove"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Continue"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Play"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Pause"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Next"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Previous"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Reset to defaults"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Close and Save"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Preview animation"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Compression settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Apply to All"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Reset Timing"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Force Regenerate Animation"),
    # Editor tab buttons
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Load Animation Files"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Combine Selected"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Reset Zoom"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Center View"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Fit Canvas"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Detach Canvas"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Reattach Canvas"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Reset to Default"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Apply to All Frames"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Save Alignment to Extract Tab"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Export Composite to Sprites"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Load GIF/WebP/APNG/PNG files into the editor"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Create a composite entry from all selected animations for group alignment"),
)

# Dialog titles - Standard dialog/message box titles
_DIALOG_TITLE_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Error"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Warning"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Success"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Information"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Confirm"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Info"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Reset to Defaults"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Settings Saved"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Invalid Input"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Preview Error"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Load failed"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Missing dependency"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Alignment saved"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Export composite"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Composite name"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Need more animations"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Combine failed"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Name conflict"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Parse Issues Detected"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Up to Date"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Update Check Failed"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Launching Updater"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Update Available"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Machine Translation Warning"),
)

# Window titles - Main window and dialog titles
_WINDOW_TITLE_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "App Options"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Compression settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation Preview"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Contributors"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Find and Replace"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Language Settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Current Settings Overview"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Background Color Options"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Unknown Atlas Warning"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Processing..."),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Welcome to TextureAtlas Toolbox"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Alignment Canvas"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "TextureAtlas Toolbox Updater"),
)

# Tab titles
_TAB_TITLE_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "System Resources"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Interface"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Extraction Defaults"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Generator Defaults"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Compression Defaults"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Updates"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Editor"),
)

# File dialog titles
_FILE_DIALOG_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select Input Directory"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select Output Directory"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select Files"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select frames"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select directory with frame images"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select Atlas Image File"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select Atlas Data File"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select animation files"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Save Atlas As"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select FNF Character Data File"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Choose Background Color"),
)

# Generator status messages - COMMENTED OUT: These are one-off messages, not worth centralizing
# _GENERATOR_STATUS_STRINGS = (
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "No frames loaded"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "{0} animation(s), {1} frame(s) total"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Generating atlas..."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Progress: {0}/{1} - {2}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Generation completed successfully!"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Generation failed!"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "GENERATION COMPLETED SUCCESSFULLY!"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Atlas generated successfully!"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Atlas: {0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Size: {0}x{1}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frames: {0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Efficiency: {0:.1f}%"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Format: {0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Metadata files: {0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Error: {0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Atlas generation failed:\n\n{0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Created {0} animation(s) from subfolders."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "No image files found in any subfolders."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "No image files found in the selected directory."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "No frames found in the selected atlas data file."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "All frames from this atlas were already added."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Error importing atlas: {0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Please add frames before generating atlas."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Rotation is not supported by {0} format."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Could not open compression settings: {0}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "New animation"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Width"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Height"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Min size"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Max size"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Atlas sizing: Automatic mode selected."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Auto (Best Result)"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "N/A"),
# )

# Filter strings for file dialogs
_FILE_FILTER_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Image files ({0})"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Atlas image files ({0})"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Spritesheet data files ({0})"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animation files (*.gif *.apng *.png *.webp);;All files (*.*)"),
)

# Editor tab labels and messages - COMMENTED OUT: Most are one-off, editor-specific strings
# _EDITOR_LABEL_STRINGS = (
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Animations & Frames"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame offset X"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame offset Y"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Canvas width"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Canvas height"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Canvas origin"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Ghost frame"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Snapping"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "px"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Zoom: {value}%"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Frame {index}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Centered"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Top-left (FlxSprite)"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Pillow is required to load animations."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "{file} did not contain any frames."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Could not load {file}: {error}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Loaded {animation} from {sheet}."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select at least two animations to build a composite entry."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Composite ({count} animations)"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Composite: {names}"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Composite entry created with {count} frames."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Applied ({x}, {y}) to {count} animations."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Applied ({x}, {y}) to every frame."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select a composite entry generated from multiple animations."),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Enter a name for the exported animation"),
#     QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Composite_{count}"),
# )

# Checkbox labels
_CHECKBOX_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Optimize PNG"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Lossless WebP"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Exact WebP"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Lossless AVIF"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Optimize TIFF"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", 'Use "Power of 2" sizes'),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Allow rotation (90°)"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Allow flip X/Y (non-standard)"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Trim transparent edges"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Check for updates on startup"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Auto-download and install updates"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Remember last used input directory"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Remember last used output directory"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Hide single-frame spritemap animations"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Use native file picker when available"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Merge duplicate frames"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Trim Sprites"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Regular Expression"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Enable"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Skip all files with errors"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Check for updates on startup (recommended)"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Automatically download updates when available"),
)

# Placeholder texts
_PLACEHOLDER_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Optional prefix"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Optional suffix"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Text to find..."),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Replacement text..."),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "e.g., 0,2,4 or 0-5 (leave empty for all frames)"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Leave empty for auto-generated filename"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Type a path and press Enter"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Paste a path or space-separated files"),
)

# Context menu / action labels
_ACTION_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Add to Editor Tab"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Focus in Editor Tab"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Override Settings"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Preview Animation"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Remove from List"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Remove animation(s)"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Remove selected frame(s)"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Add animation group"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Rename animation"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Delete animation"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Remove frame"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Add Rule"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Add Preset Rule"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select All"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Select None"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Continue Anyway"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Skip Selected"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Proceed anyway"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Skip unknown"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Update Now"),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp", "Restart Application"),
)

# Tooltips - Shared tooltip strings
_TOOLTIP_STRINGS = (
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "Alpha threshold for GIF transparency (0-100%):\n"
        "• 0%: All pixels visible\n"
        "• 50%: Default, balanced transparency\n"
        "• 100%: Only fully opaque pixels visible"
    ),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "Which frames to export:\n"
        "• All: Export every frame\n"
        "• No duplicates: Export unique frames only (skip repeated frames)\n"
        "• First: Export only the first frame\n"
        "• Last: Export only the last frame\n"
        "• First, Last: Export first and last frames"
    ),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "How cropping should be done:\n"
        "• None: No cropping, keep original sprite size\n"
        "• Animation based: Crop to fit all frames in an animation\n"
        "• Frame based: Crop each frame individually (frames only)"
    ),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "Resampling filter used when scaling the animation"
    ),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "Resampling algorithm for scaling images."
    ),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "Image format for the atlas texture."
    ),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "Metadata format for the generated atlas."
    ),
    QT_TRANSLATE_NOOP("TextureAtlasToolboxApp",
        "Hold Ctrl and use mouse wheel to zoom in/out"
    ),
)
# fmt: on


class Labels:
    """Field label strings used across UI.

    These are the canonical label texts. Pass through a translation function
    (tr_func) when creating QLabel widgets.

    Example:
        label = QLabel(self.tr(Labels.FRAME_RATE))
    """

    FORMAT = "Format"
    ANIMATION_FORMAT = "Animation format"
    FRAME_FORMAT = "Frame format"
    FRAME_RATE = "Frame rate"
    FRAME_SCALE = "Frame scale"
    FRAME_SELECTION = "Frame selection"
    FRAME_SELECTION_TITLE = "Frame Selection"  # Title case for headings
    SCALE = "Scale"
    CROPPING_METHOD = "Cropping method"
    FILENAME_FORMAT = "Filename format"
    RESAMPLING_METHOD = "Resampling method"
    RESAMPLING = "Resampling"
    ALPHA_THRESHOLD = "Alpha threshold"
    DELAY = "Delay"
    LOOP_DELAY = "Loop delay"
    PERIOD = "Period"
    MINIMUM_PERIOD = "Minimum period"
    MIN_PERIOD = "Min period"
    VARIABLE_DELAY = "Variable delay"
    INDICES = "Indices"
    FRAMES = "Frames"
    FILENAME = "Filename"
    POSITION_COLON = "Position:"
    PREVIEW_ZOOM_COLON = "Preview Zoom:"
    BACKGROUND_COLON = "Background:"
    ENABLE_ANIMATION_EXPORT = "Enable animation export:"
    ENABLE_FRAME_EXPORT = "Enable frame export:"
    LOOP_PREVIEW = "Loop preview"
    EDIT_SELECTED_FRAME_ONLY = "Edit selected frame only"

    # Compression settings labels (shared between app_config and compression_settings)
    QUALITY_0_100 = "Quality (0-100):"
    COMPRESS_LEVEL_0_9 = "Compress Level (0-9):"
    METHOD_0_6 = "Method (0-6):"
    ALPHA_QUALITY_0_100 = "Alpha Quality (0-100):"
    SPEED_0_10 = "Speed (0-10):"
    COMPRESSION_TYPE = "Compression Type:"

    # Generator/filename labels
    HEURISTIC = "Heuristic"
    PREFIX = "Prefix"
    SUFFIX = "Suffix"
    FILENAME_PREFIX = "Filename prefix"
    FILENAME_SUFFIX = "Filename suffix"


class GroupTitles:
    """Group box title strings used across UI.

    These are the canonical group box titles. Pass through a translation
    function when creating QGroupBox widgets.

    Example:
        group = QGroupBox(self.tr(GroupTitles.ANIMATION_EXPORT))
    """

    # Extract tab style (lowercase "export")
    ANIMATION_EXPORT = "Animation export"
    FRAME_EXPORT = "Frame export"

    # App config style (title case)
    ANIMATION_EXPORT_DEFAULTS = "Animation Export Defaults"
    FRAME_EXPORT_DEFAULTS = "Frame Export Defaults"
    GENERAL_EXPORT_SETTINGS = "General Export Settings"

    # Override settings style
    ANIMATION_EXPORT_SETTINGS = "Animation export settings"
    FRAME_EXPORT_SETTINGS = "Frame export settings"

    # Animation preview style
    ANIMATION_SETTINGS = "Animation Settings"
    EXPORT = "Export"
    EXPORT_SETTINGS = "Export Settings"
    DISPLAY = "Display"

    # Editor tab groups
    ALIGNMENT_CONTROLS = "Alignment Controls"
    DISPLAY_SNAPPING = "Display & snapping"


class Tooltips:
    """Tooltip strings used across multiple UI files.

    These are the canonical tooltip texts. Pass through a translation
    function when setting tooltips on widgets.

    Example:
        widget.setToolTip(self.tr(Tooltips.ALPHA_THRESHOLD))
    """

    # Export settings tooltips
    ALPHA_THRESHOLD = (
        "Alpha threshold for GIF transparency (0-100%):\n"
        "• 0%: All pixels visible\n"
        "• 50%: Default, balanced transparency\n"
        "• 100%: Only fully opaque pixels visible"
    )

    FRAME_SELECTION = (
        "Which frames to export:\n"
        "• All: Export every frame\n"
        "• No duplicates: Export unique frames only (skip repeated frames)\n"
        "• First: Export only the first frame\n"
        "• Last: Export only the last frame\n"
        "• First, Last: Export first and last frames"
    )

    CROPPING_METHOD = (
        "How cropping should be done:\n"
        "• None: No cropping, keep original sprite size\n"
        "• Animation based: Crop to fit all frames in an animation\n"
        "• Frame based: Crop each frame individually (frames only)"
    )

    # Resampling tooltips
    RESAMPLING_ANIMATION = "Resampling filter used when scaling the animation"
    RESAMPLING_IMAGES = "Resampling algorithm for scaling images."

    # Generator tooltips
    IMAGE_FORMAT = "Image format for the atlas texture."
    EXPORT_FORMAT = "Metadata format for the generated atlas."

    # Interactive tooltips
    CTRL_ZOOM = "Hold Ctrl and use mouse wheel to zoom in/out"

    # Zoom button tooltips
    ZOOM_IN = "Zoom in"
    ZOOM_OUT = "Zoom out"
    ZOOM_100 = "Set zoom to 100%"
    ZOOM_50 = "Set zoom to 50%"
    CENTER_VIEW = "Re-center the viewport"
    FIT_CANVAS = "Fit the entire canvas inside the view"

    # Editor tab tooltips
    LOAD_ANIMATIONS = "Load GIF/WebP/APNG/PNG files into the editor"
    COMBINE_SELECTED = (
        "Create a composite entry from all selected animations for group alignment"
    )


class ButtonLabels:
    """Common button label strings used across UI.

    These are the canonical button texts. Pass through a translation
    function when creating QPushButton widgets.

    Example:
        button = QPushButton(self.tr(ButtonLabels.OK))
    """

    # Standard dialog buttons
    OK = "OK"
    CANCEL = "Cancel"
    CLOSE = "Close"
    SAVE = "Save"
    APPLY = "Apply"
    RESET = "Reset"
    DELETE = "Delete"
    REMOVE = "Remove"
    CONTINUE = "Continue"

    # Playback controls
    PLAY = "Play"
    PAUSE = "Pause"
    NEXT = "Next"
    PREVIOUS = "Previous"

    # Compound buttons
    RESET_TO_DEFAULTS = "Reset to defaults"
    CLOSE_AND_SAVE = "Close and Save"
    PREVIEW_ANIMATION = "Preview animation"
    COMPRESSION_SETTINGS = "Compression settings"
    APPLY_TO_ALL = "Apply to All"
    RESET_TIMING = "Reset Timing"
    FORCE_REGENERATE_ANIMATION = "Force Regenerate Animation"

    # Editor tab buttons
    LOAD_ANIMATION_FILES = "Load Animation Files"
    COMBINE_SELECTED = "Combine Selected"
    RESET_ZOOM = "Reset Zoom"
    CENTER_VIEW = "Center View"
    FIT_CANVAS = "Fit Canvas"
    DETACH_CANVAS = "Detach Canvas"
    REATTACH_CANVAS = "Reattach Canvas"
    RESET_TO_DEFAULT = "Reset to Default"
    APPLY_TO_ALL_FRAMES = "Apply to All Frames"
    SAVE_ALIGNMENT_EXTRACT = "Save Alignment to Extract Tab"
    EXPORT_COMPOSITE_SPRITES = "Export Composite to Sprites"


class DialogTitles:
    """Standard dialog and message box title strings.

    These are the canonical dialog titles. Pass through a translation
    function when creating QMessageBox dialogs.

    Example:
        QMessageBox.warning(self, self.tr(DialogTitles.ERROR), message)
    """

    ERROR = "Error"
    WARNING = "Warning"
    SUCCESS = "Success"
    INFORMATION = "Information"
    CONFIRM = "Confirm"
    INFO = "Info"
    RESET_TO_DEFAULTS = "Reset to Defaults"
    SETTINGS_SAVED = "Settings Saved"
    INVALID_INPUT = "Invalid Input"
    PREVIEW_ERROR = "Preview Error"
    LOAD_FAILED = "Load failed"
    MISSING_DEPENDENCY = "Missing dependency"
    ALIGNMENT_SAVED = "Alignment saved"
    EXPORT_COMPOSITE = "Export composite"
    COMPOSITE_NAME = "Composite name"
    NEED_MORE_ANIMATIONS = "Need more animations"
    COMBINE_FAILED = "Combine failed"
    NAME_CONFLICT = "Name conflict"
    PARSE_ISSUES_DETECTED = "Parse Issues Detected"
    UP_TO_DATE = "Up to Date"
    UPDATE_CHECK_FAILED = "Update Check Failed"
    LAUNCHING_UPDATER = "Launching Updater"
    UPDATE_AVAILABLE = "Update Available"
    MACHINE_TRANSLATION_WARNING = "Machine Translation Warning"


class WindowTitles:
    """Window title strings for main windows and dialogs.

    Example:
        self.setWindowTitle(self.tr(WindowTitles.APP_OPTIONS))
    """

    APP_OPTIONS = "App Options"
    COMPRESSION_SETTINGS = "Compression settings"
    ANIMATION_PREVIEW = "Animation Preview"
    CONTRIBUTORS = "Contributors"
    FIND_AND_REPLACE = "Find and Replace"
    LANGUAGE_SETTINGS = "Language Settings"
    CURRENT_SETTINGS_OVERVIEW = "Current Settings Overview"
    BACKGROUND_COLOR_OPTIONS = "Background Color Options"
    UNKNOWN_ATLAS_WARNING = "Unknown Atlas Warning"
    PROCESSING = "Processing..."
    WELCOME = "Welcome to TextureAtlas Toolbox"
    ALIGNMENT_CANVAS = "Alignment Canvas"
    UPDATER = "TextureAtlas Toolbox Updater"


class TabTitles:
    """Tab title strings for tab widgets.

    Example:
        tab_widget.addTab(widget, self.tr(TabTitles.INTERFACE))
    """

    SYSTEM_RESOURCES = "System Resources"
    INTERFACE = "Interface"
    EXTRACTION_DEFAULTS = "Extraction Defaults"
    GENERATOR_DEFAULTS = "Generator Defaults"
    COMPRESSION_DEFAULTS = "Compression Defaults"
    UPDATES = "Updates"
    EDITOR = "Editor"


class FileDialogTitles:
    """File dialog title strings.

    Example:
        QFileDialog.getExistingDirectory(self, self.tr(FileDialogTitles.SELECT_INPUT_DIR), ...)
    """

    SELECT_INPUT_DIR = "Select Input Directory"
    SELECT_OUTPUT_DIR = "Select Output Directory"
    SELECT_FILES = "Select Files"
    SELECT_FRAMES = "Select frames"
    SELECT_FRAME_DIR = "Select directory with frame images"
    SELECT_ATLAS_IMAGE = "Select Atlas Image File"
    SELECT_ATLAS_DATA = "Select Atlas Data File"
    SELECT_ANIMATION_FILES = "Select animation files"
    SAVE_ATLAS_AS = "Save Atlas As"
    SELECT_FNF_DATA = "Select FNF Character Data File"
    CHOOSE_BG_COLOR = "Choose Background Color"


# class GeneratorLabels - COMMENTED OUT: One-off generator-specific labels
# class GeneratorLabels:
#     """Generator-specific label strings."""
#     WIDTH = "Width"
#     HEIGHT = "Height"
#     MIN_SIZE = "Min size"
#     MAX_SIZE = "Max size"
#     NEW_ANIMATION = "New animation"
#     AUTO_BEST_RESULT = "Auto (Best Result)"
#     NOT_AVAILABLE = "N/A"


# class GeneratorMessages - COMMENTED OUT: One-off generator-specific messages
# class GeneratorMessages:
#     """Generator status and progress messages."""
#     NO_FRAMES_LOADED = "No frames loaded"
#     ANIMATIONS_FRAMES_COUNT = "{0} animation(s), {1} frame(s) total"
#     GENERATING = "Generating atlas..."
#     PROGRESS = "Progress: {0}/{1} - {2}"
#     COMPLETED = "Generation completed successfully!"
#     FAILED = "Generation failed!"
#     COMPLETED_UPPER = "GENERATION COMPLETED SUCCESSFULLY!"
#     SUCCESS_HEADER = "Atlas generated successfully!"
#     ATLAS_PATH = "Atlas: {0}"
#     SIZE_DIMS = "Size: {0}x{1}"
#     FRAMES_COUNT = "Frames: {0}"
#     EFFICIENCY = "Efficiency: {0:.1f}%"
#     FORMAT_INFO = "Format: {0}"
#     METADATA_FILES = "Metadata files: {0}"
#     ERROR_PREFIX = "Error: {0}"
#     FAILED_DETAIL = "Atlas generation failed:\n\n{0}"
#     CREATED_FROM_SUBFOLDERS = "Created {0} animation(s) from subfolders."
#     NO_IMAGES_SUBFOLDERS = "No image files found in any subfolders."
#     NO_IMAGES_DIR = "No image files found in the selected directory."
#     NO_FRAMES_ATLAS = "No frames found in the selected atlas data file."
#     ALL_FRAMES_ADDED = "All frames from this atlas were already added."
#     ERROR_IMPORTING = "Error importing atlas: {0}"
#     ADD_FRAMES_FIRST = "Please add frames before generating atlas."
#     ROTATION_NOT_SUPPORTED = "Rotation is not supported by {0} format."
#     COMPRESSION_ERROR = "Could not open compression settings: {0}"
#     AUTO_MODE_SELECTED = "Atlas sizing: Automatic mode selected."


class FileFilters:
    """File filter format strings for file dialogs.

    Example:
        filter = self.tr(FileFilters.IMAGE_FILES).format(extensions)
    """

    IMAGE_FILES = "Image files ({0})"
    ATLAS_IMAGE_FILES = "Atlas image files ({0})"
    SPRITESHEET_DATA_FILES = "Spritesheet data files ({0})"
    ANIMATION_FILES = "Animation files (*.gif *.apng *.png *.webp);;All files (*.*)"


# class EditorLabels - COMMENTED OUT: One-off editor-specific labels
# class EditorLabels:
#     """Editor tab label strings."""
#     ANIMATIONS_FRAMES = "Animations & Frames"
#     FRAME_OFFSET_X = "Frame offset X"
#     FRAME_OFFSET_Y = "Frame offset Y"
#     CANVAS_WIDTH = "Canvas width"
#     CANVAS_HEIGHT = "Canvas height"
#     CANVAS_ORIGIN = "Canvas origin"
#     GHOST_FRAME = "Ghost frame"
#     SNAPPING = "Snapping"
#     PX = "px"
#     ZOOM_PERCENT = "Zoom: {value}%"
#     FRAME_INDEX = "Frame {index}"
#     CENTERED = "Centered"
#     TOP_LEFT_FLXSPRITE = "Top-left (FlxSprite)"


# class EditorMessages - COMMENTED OUT: One-off editor-specific messages
# class EditorMessages:
#     """Editor tab status and info messages."""
#     PILLOW_REQUIRED = "Pillow is required to load animations."
#     NO_FRAMES_IN_FILE = "{file} did not contain any frames."
#     LOAD_ERROR = "Could not load {file}: {error}"
#     LOADED_FROM_SHEET = "Loaded {animation} from {sheet}."
#     SELECT_TWO_ANIMATIONS = "Select at least two animations to build a composite entry."
#     COMPOSITE_MANY = "Composite ({count} animations)"
#     COMPOSITE_NAMES = "Composite: {names}"
#     COMPOSITE_CREATED = "Composite entry created with {count} frames."
#     APPLIED_TO_ANIMATIONS = "Applied ({x}, {y}) to {count} animations."
#     APPLIED_TO_FRAMES = "Applied ({x}, {y}) to every frame."
#     SELECT_COMPOSITE = "Select a composite entry generated from multiple animations."
#     ENTER_COMPOSITE_NAME = "Enter a name for the exported animation"
#     COMPOSITE_DEFAULT_NAME = "Composite_{count}"


class CheckBoxLabels:
    """Checkbox label strings used across UI.

    Example:
        checkbox = QCheckBox(self.tr(CheckBoxLabels.OPTIMIZE_PNG))
    """

    # Compression options
    OPTIMIZE_PNG = "Optimize PNG"
    LOSSLESS_WEBP = "Lossless WebP"
    EXACT_WEBP = "Exact WebP"
    LOSSLESS_AVIF = "Lossless AVIF"
    OPTIMIZE_TIFF = "Optimize TIFF"

    # Generator options
    POWER_OF_TWO = 'Use "Power of 2" sizes'
    ALLOW_ROTATION = "Allow rotation (90°)"
    ALLOW_FLIP = "Allow flip X/Y (non-standard)"
    TRIM_TRANSPARENT = "Trim transparent edges"
    TRIM_SPRITES = "Trim Sprites"

    # Update options
    CHECK_UPDATES_STARTUP = "Check for updates on startup"
    AUTO_DOWNLOAD_UPDATES = "Auto-download and install updates"
    CHECK_UPDATES_RECOMMENDED = "Check for updates on startup (recommended)"
    AUTO_DOWNLOAD_AVAILABLE = "Automatically download updates when available"

    # Interface options
    REMEMBER_INPUT_DIR = "Remember last used input directory"
    REMEMBER_OUTPUT_DIR = "Remember last used output directory"
    HIDE_SINGLE_FRAME = "Hide single-frame spritemap animations"
    HIDE_UNUSED_SYMBOLS = "Hide symbols not used by the main animation"
    ROOT_ANIMATION_ONLY = "Only detect main animation"
    USE_NATIVE_FILE_PICKER = "Use native file picker when available"
    MERGE_DUPLICATES = "Merge duplicate frames"

    # Other
    REGEX = "Regular Expression"
    ENABLE = "Enable"
    SKIP_ALL_ERRORS = "Skip all files with errors"


class Placeholders:
    """Placeholder text strings for input fields.

    Example:
        line_edit.setPlaceholderText(self.tr(Placeholders.OPTIONAL_PREFIX))
    """

    OPTIONAL_PREFIX = "Optional prefix"
    OPTIONAL_SUFFIX = "Optional suffix"
    TEXT_TO_FIND = "Text to find..."
    REPLACEMENT_TEXT = "Replacement text..."
    INDICES_HINT = "e.g., 0,2,4 or 0-5 (leave empty for all frames)"
    AUTO_FILENAME = "Leave empty for auto-generated filename"
    TYPE_PATH = "Type a path and press Enter"
    PASTE_PATH = "Paste a path or space-separated files"


class MenuActions:
    """Menu and context menu action strings.

    Example:
        action = QAction(self.tr(MenuActions.ADD_TO_EDITOR), self)
    """

    # Editor tab actions
    ADD_TO_EDITOR = "Add to Editor Tab"
    FOCUS_IN_EDITOR = "Focus in Editor Tab"
    REMOVE_FROM_LIST = "Remove from List"
    REMOVE_ANIMATIONS = "Remove animation(s)"
    REMOVE_FRAMES = "Remove selected frame(s)"

    # Override settings
    OVERRIDE_SETTINGS = "Override Settings"
    PREVIEW_ANIMATION = "Preview Animation"

    # Animation tree actions
    ADD_ANIMATION_GROUP = "Add animation group"
    RENAME_ANIMATION = "Rename animation"
    DELETE_ANIMATION = "Delete animation"
    REMOVE_FRAME = "Remove frame"

    # Find/replace actions
    ADD_RULE = "Add Rule"
    ADD_PRESET_RULE = "Add Preset Rule"

    # Selection actions
    SELECT_ALL = "Select All"
    SELECT_NONE = "Select None"

    # Parse error dialog actions
    CONTINUE_ANYWAY = "Continue Anyway"
    SKIP_SELECTED = "Skip Selected"

    # Warning dialog actions
    PROCEED_ANYWAY = "Proceed anyway"
    SKIP_UNKNOWN = "Skip unknown"

    # Update actions
    UPDATE_NOW = "Update Now"
    RESTART_APPLICATION = "Restart Application"


@dataclass(frozen=True)
class SpinBoxRange:
    """Defines min, max, and optional default/step for a spinbox."""

    min_val: float
    max_val: float
    default: float = 0.0
    step: float = 1.0
    decimals: int = 0


class SpinBoxConfig:
    """Shared spinbox configurations for consistent behavior across UI.

    Usage:
        spinbox.setRange(SpinBoxConfig.FRAME_RATE.min_val, SpinBoxConfig.FRAME_RATE.max_val)
        spinbox.setValue(SpinBoxConfig.FRAME_RATE.default)

    Or use the helper:
        configure_spinbox(spinbox, SpinBoxConfig.FRAME_RATE)
    """

    # Frame rate: 1-1000 FPS (extract tab), 1-100000 (animation preview)
    FRAME_RATE = SpinBoxRange(min_val=1, max_val=1000, default=24, step=1)
    FRAME_RATE_EXTENDED = SpinBoxRange(min_val=1, max_val=100000, default=24, step=1)

    # Scale factors: 0.01x to 100x
    SCALE = SpinBoxRange(
        min_val=0.01, max_val=100.0, default=1.0, step=0.01, decimals=2
    )
    FRAME_SCALE = SpinBoxRange(
        min_val=0.01, max_val=100.0, default=1.0, step=0.01, decimals=2
    )

    # Override settings frame scale (allows negative for "use default")
    FRAME_SCALE_OVERRIDE = SpinBoxRange(
        min_val=-10.0, max_val=10.0, default=1.0, step=0.1, decimals=2
    )

    # Threshold: 0-255 for alpha threshold
    THRESHOLD = SpinBoxRange(min_val=0, max_val=255, default=0, step=1)

    # Delay in milliseconds
    DELAY_MS = SpinBoxRange(min_val=1, max_val=100000, default=42, step=1)

    # Period in milliseconds
    PERIOD_MS = SpinBoxRange(min_val=1, max_val=100000, default=42, step=1)


def configure_spinbox(
    spinbox,
    config: SpinBoxRange,
    set_default: bool = True,
) -> None:
    """Configure a QSpinBox or QDoubleSpinBox with shared settings.

    Args:
        spinbox: QSpinBox or QDoubleSpinBox instance.
        config: SpinBoxRange configuration to apply.
        set_default: If True, also sets the default value.
    """
    spinbox.setRange(config.min_val, config.max_val)
    spinbox.setSingleStep(config.step)

    # Only QDoubleSpinBox has setDecimals
    if hasattr(spinbox, "setDecimals") and config.decimals > 0:
        spinbox.setDecimals(config.decimals)

    if set_default:
        spinbox.setValue(config.default)
