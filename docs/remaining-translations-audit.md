# Remaining `self.tr()` Strings Without Constants

This document lists all `self.tr()` calls that are **not** using centralized constants from `utils/ui_constants.py` or `utils/combo_options.py`. These are candidates for future centralization if they appear in multiple files.

> **Generated:** January 17, 2026  
> **Purpose:** Audit for translation consistency and potential centralization

---

## Summary by File

| File | Count |
|------|-------|
| [app_config_window.py](#app_config_windowpy) | ~95 |
| [extract_tab_widget.py](#extract_tab_widgetpy) | ~45 |
| [generate_tab_widget.py](#generate_tab_widgetpy) | ~55 |
| [editor_tab_widget.py](#editor_tab_widgetpy) | ~70 |
| [animation_preview_window.py](#animation_preview_windowpy) | ~25 |
| [compression_settings_window.py](#compression_settings_windowpy) | ~15 |
| [override_settings_window.py](#override_settings_windowpy) | ~20 |
| [processing_window.py](#processing_windowpy) | ~35 |
| [Other files](#other-files) | ~80 |

---

## app_config_window.py

### Window & Tab Titles
- `"App Options"` - Window title
- `"System Resources"` - Tab name
- `"Interface"` - Tab name
- `"Extraction Defaults"` - Tab name
- `"Generator Defaults"` - Tab name
- `"Compression Defaults"` - Tab name
- `"Updates"` - Tab name

### GroupBox Titles
- `"Your Computer"` - System info group
- `"App Resource Limits"` - Resource limits group
- `"Atlas Settings"` - Generator settings (appears twice)
- `"Sprite Optimization"` - Generator optimization group
- `"Output Format"` - Generator output group
- `"PNG Settings"` - Compression group
- `"WebP Settings"` - Compression group
- `"AVIF Settings"` - Compression group
- `"TIFF Settings"` - Compression group
- `"Update Preferences"` - Update settings group
- `"Appearance"` - Interface group
- `"Directory Memory"` - Interface group
- `"Spritemap Settings"` - Interface group
- `"File Picker"` - Interface group
- `"Animation Behavior"` - Interface group

### Labels
- `"CPU: {cpu} (Threads: {threads})"` - System info
- `"RAM: {memory:,} MB"` - System info
- `"CPU threads to use (max: {max_threads}):"` - Dynamic label
- `"Memory limit (MB, max: {max_memory}):"` - Dynamic label
- `"Duration"` - Animation duration label
- `"Packer method"` - Generator setting
- `"Max atlas size"` - Generator setting
- `"Padding:"` - Generator setting
- `"Atlas type"` - Generator output
- `"Image format"` - Generator output
- `"Color scheme:"` - Interface setting
- `"Duration input type:"` - Interface setting

### Checkboxes
- `'Use "Power of 2" sizes'` - Generator option
- `"Allow rotation (90°)"` - Generator option
- `"Allow flip X/Y (non-standard)"` - Generator option
- `"Trim transparent edges"` - Generator option
- `"Optimize PNG"` - Compression option
- `"Lossless WebP"` - Compression option
- `"Exact WebP"` - Compression option
- `"Lossless AVIF"` - Compression option
- `"Optimize TIFF"` - Compression option
- `"Check for updates on startup"` - Update option
- `"Auto-download and install updates"` - Update option
- `"Remember last used input directory"` - Interface option
- `"Remember last used output directory"` - Interface option
- `"Hide single-frame spritemap animations"` - Interface option
- `"Use native file picker when available"` - Interface option
- `"Merge duplicate frames"` - Interface option

### ComboBox Items
- `"Auto (System)"` - Color scheme
- `"Light"` - Color scheme
- `"Dark"` - Color scheme
- `"Format Native"` - Duration input type
- `"FPS (frames per second)"` - Duration input type
- `"Deciseconds"` - Duration input type
- `"Centiseconds"` - Duration input type
- `"Milliseconds"` - Duration input type

### Placeholders
- `"Optional prefix"` - Filename prefix placeholder
- `"Optional suffix"` - Filename suffix placeholder

### Tooltips (Long strings)
- CPU threads tooltip
- Memory limit tooltip
- Packer method tooltip
- Heuristic tooltip
- Max atlas size tooltip
- Padding tooltip
- Power of 2 tooltip
- Allow rotation tooltip
- Allow flip tooltip
- Trim sprites tooltip
- Atlas type tooltip
- Various compression tooltips
- Auto-download updates tooltip
- Directory memory tooltips
- Hide single-frame tooltip
- Native file picker tooltip
- Merge duplicates tooltip
- Duration input type tooltip

### Dialog Messages
- `"Reset to Defaults"` - Dialog title
- `"Are you sure you want to reset all settings to their default values?"` - Confirmation
- `"CPU threads cannot exceed {max_threads}"` - Validation error
- `"Memory limit cannot exceed {max_memory} MB"` - Validation error
- `"Settings Saved"` - Success title
- `"Configuration has been saved successfully."` - Success message
- `"Invalid Input"` - Error title
- `"Error: {error}"` - Error message
- `"Error"` - Error title
- `"Failed to save configuration: {error}"` - Error message

---

## extract_tab_widget.py

### UI Labels
- `"Path or filenames"` - File dialog label
- `"Paste a path or space-separated files"` - Placeholder
- `"Type a path and press Enter"` - Placeholder
- `"Compression Settings"` - Button/section
- `"Select input directory"` - Button
- `"No input directory selected"` - Label
- `"Select output directory"` - Button
- `"No output directory selected"` - Label
- `"Advanced filename options"` - Button
- `"Show override settings"` - Button
- `"Override spritesheet settings"` - Button
- `"Override animation settings"` - Button
- `"Start process"` - Button

### Context Menu Actions
- `"Add to Editor Tab"` - Action
- `"Focus in Editor Tab"` - Action
- `"Override Settings"` - Action
- `"Delete"` - Action
- `"Preview Animation"` - Action
- `"Remove from List"` - Action

### Dialog Messages
- `"Select Input Directory"` - Dialog title
- `"Select Output Directory"` - Dialog title
- `"Select Files"` - Dialog title
- `"Manual selection ({count} files)"` - Label
- `"Composite created in the Editor tab"` - Tooltip
- `"Error"` - Dialog title (multiple)
- `"Please select a spritesheet first."` - Error message
- `"Could not open animation settings: {error}"` - Error message
- `"Could not open spritesheet settings: {error}"` - Error message
- `"Editor"` - Dialog title
- `"No animations were found for this spritesheet."` - Info message
- `"Select a spritesheet first."` - Error message
- `"The spritesheet path could not be determined."` - Error message
- `"No metadata was located for this spritesheet."` - Error message
- `"Please select an animation first."` - Error message
- `"Preview Error"` - Dialog title
- `"Could not find spritesheet file path."` - Error message
- `"Could not preview animation: {error}"` - Error message
- `"Please select an input directory first."` - Validation
- `"Please select an output directory first."` - Validation
- `"Processing..."` - Button state
- `"Start Process"` - Button state

---

## generate_tab_widget.py

### File Filters
- `'All files'` - File filter
- `"Image files ({0})"` - File filter
- `"Atlas image files ({0})"` - File filter
- `"Spritesheet data files ({0})"` - File filter
- `"{format_name} files ({pattern})"` - Dynamic file filter

### Dialog Titles
- `"Select frames"` - File dialog
- `"Select directory with frame images"` - Directory dialog
- `"Select Atlas Image File"` - File dialog
- `"Select Atlas Data File"` - File dialog
- `"Save Atlas As"` - Save dialog

### Status Messages
- `"Created {0} animation(s) from subfolders."` - Success
- `"No image files found in any subfolders."` - Warning
- `"No image files found in the selected directory."` - Warning
- `"No frames found in the selected atlas data file."` - Warning
- `"All frames from this atlas were already added."` - Info
- `"Error importing atlas: {0}"` - Error
- `"No frames loaded"` - Status
- `"{0} animation(s), {1} frame(s) total"` - Status
- `"Please add frames before generating atlas."` - Warning
- `"Generating atlas..."` - Status
- `"Progress: {0}/{1} - {2}"` - Progress
- `"Atlas generated successfully!"` - Success
- `"Atlas: {0}"` - Result info
- `"Size: {0}x{1}"` - Result info
- `"Frames: {0}"` - Result info
- `"Efficiency: {0:.1f}%"` - Result info
- `"Format: {0}"` - Result info
- `"Metadata files: {0}"` - Result info
- `"Generation completed successfully!"` - Status
- `"GENERATION COMPLETED SUCCESSFULLY!"` - Log
- `"Generation failed!"` - Status/Log
- `"Error: {0}"` - Error
- `"Atlas generation failed:\n\n{0}"` - Error dialog

### Labels
- `"Width"` - Atlas size label
- `"Height"` - Atlas size label
- `"Min size"` - Atlas size label
- `"Max size"` - Atlas size label

### Checkboxes
- `"Trim Sprites"` - Option

### Tooltips
- Atlas size method tooltip
- Rotation tooltip
- Compression settings tooltip
- Trim sprites tooltip
- Format-specific warnings

### Other
- `"New animation"` - Default name
- `"N/A"` - Heuristic combo placeholder
- `"Auto (Best Result)"` - Heuristic option

---

## editor_tab_widget.py

### UI Labels
- `"Animations & Frames"` - Section title
- `"Load Animation Files"` - Button
- `"Load GIF/WebP/APNG/PNG files into the editor"` - Tooltip
- `"Combine Selected"` - Button
- `"Reset Zoom"` - Button
- `"Center View"` - Button
- `"Fit Canvas"` - Button
- `"Detach Canvas"` - Button
- `"Reattach Canvas"` - Button
- `"Alignment Controls"` - Group title
- `"Frame offset X"` - Form label
- `"Frame offset Y"` - Form label
- `"Reset to Default"` - Button
- `"Apply to All Frames"` - Button
- `"Canvas width"` - Form label
- `"Canvas height"` - Form label
- `"Save Alignment to Extract Tab"` - Button
- `"Export Composite to Sprites"` - Button
- `"Display & snapping"` - Group title
- `"Canvas origin"` - Form label
- `"Enable"` - Checkbox (ghost frame, snapping)
- `"Ghost frame"` - Form label
- `"Snapping"` - Form label
- `"px"` - Unit label
- `"Zoom: {value}%"` - Status
- `"Alignment Canvas"` - Window title

### ComboBox Items
- `"Centered"` - Origin mode
- `"Top-left (FlxSprite)"` - Origin mode

### Context Menu
- `"Remove animation(s)"` - Action
- `"Remove selected frame(s)"` - Action

### Dialog Messages
- `"Missing dependency"` - Error title
- `"Pillow is required to load animations."` - Error message
- `"Select animation files"` - Dialog title
- `"Animation files (*.gif *.apng *.png *.webp);;All files (*.*)"` - Filter
- `"Frame {index}"` - Frame name
- `"Load failed"` - Error title
- `"{file} did not contain any frames."` - Error
- `"Could not load {file}: {error}"` - Error
- `"Loaded {animation} from {sheet}."` - Status
- `"Editor"` - Dialog title
- `"Need more animations"` - Error title
- `"Select at least two animations to build a composite entry."` - Error
- `"Combine failed"` - Error title
- `"Composite ({count} animations)"` - Display name
- `"Composite: {names}"` - Display name
- `"Composite entry created with {count} frames."` - Status
- `"Applied ({x}, {y}) to {count} animations."` - Status
- `"Applied ({x}, {y}) to every frame."` - Status
- `"Alignment saved"` - Info title
- `"Export composite"` - Dialog title (multiple)
- `"Select a composite entry generated from multiple animations."` - Info
- `"Composite_{count}"` - Default name
- `"Composite name"` - Dialog title
- `"Enter a name for the exported animation"` - Dialog prompt
- `"Unable to capture composite definition for export."` - Error
- `"Exported composite to {name}."` - Status

---

## animation_preview_window.py

### UI Labels
- `"Animation Preview"` - Window title
- `"Frame 1 / 1"` - Frame info
- `"Loading..."` - Progress
- `"Loading... {percent}% ({current}/{total})"` - Progress
- `"Loaded {count} frames"` - Status
- `"Error loading animation"` - Error
- `"Frame {index} / {total}"` - Frame info
- `" ({delay}ms)"` - Delay suffix
- `"Choose Background Color"` - Color dialog title
- `"Failed to regenerate animation."` - Error
- `"Failed to regenerate animation: {error}"` - Error
- `"Animation file not found: {path}"` - Error

### ComboBox Items (Background)
- `"None"` - Background option
- `"Solid Color"` - Background option
- `"Transparency Pattern"` - Background option

### Placeholder
- `"e.g., 0,2,4 or 0-5 (leave empty for all frames)"` - Indices hint

---

## compression_settings_window.py

### Window & Group Titles
- `"Compression settings"` - Window title
- `"Compression settings for {format}"` - Dynamic title
- `"PNG Compression Settings"` - Group title
- `"WebP Compression Settings"` - Group title
- `"AVIF Compression Settings"` - Group title
- `"TIFF Compression Settings"` - Group title

### Checkboxes
- `"Optimize PNG"` - Option
- `"Lossless WebP"` - Option
- `"Exact WebP"` - Option
- `"Lossless AVIF"` - Option
- `"Optimize TIFF"` - Option

### Tooltips
- Compress level tooltip
- Optimize PNG tooltip
- Lossless WebP tooltip
- WebP quality tooltip
- WebP method tooltip
- WebP alpha quality tooltip
- Exact WebP tooltip
- AVIF lossless tooltip
- AVIF quality tooltip
- AVIF speed tooltip
- TIFF compression type tooltip
- TIFF quality tooltip
- Optimize TIFF tooltip

---

## override_settings_window.py

### Window Titles
- `"{prefix} Settings Override - {name}"` - Dynamic window title
- `"Animation Settings Override"` - Window title
- `"Spritesheet Settings Override"` - Window title

### Labels
- `"Name:"` - Form label
- `"Spritesheet:"` - Form label
- `"Filename:"` - Form label
- `"Leave empty for auto-generated filename"` - Placeholder
- `"Indices (comma-separated):"` - Form label
- `"e.g., 0,1,2,3 or leave empty for all"` - Placeholder

### Dialog Messages
- `"Info"` - Dialog title
- `"Preview Error"` - Dialog title
- `"Invalid animation name format."` - Error
- `"Could not find spritesheet: {name}"` - Error
- `"Could not find animation: {name}"` - Error
- `"Could not open preview: {error}"` - Error

---

## processing_window.py

### UI Labels
- `"Processing..."` - Window title
- `"Extracting TextureAtlas Files"` - Title
- `"Current File:"` - Label
- `"Initializing..."` - Status
- `"Worker Status"` - Label
- `"Show worker details"` - Toggle button
- `"Hide worker details"` - Toggle button
- `"Progress: 0 / 0 files"` - Progress label
- `"Statistics:"` - Section title
- `"Frames Generated: 0"` - Stat
- `"Animations Generated: 0"` - Stat
- `"Sprites Failed: 0"` - Stat
- `"Duration: 00:00"` - Stat
- `"Processing Log:"` - Section title
- `"No active workers"` - Worker status
- `"Worker"` - Worker label
- `"Idle"` - Worker status

### Dynamic Messages
- `"Starting extraction of {count} files..."` - Log
- `"Processing: {filename}"` - Log/Status
- `"Progress: {current} / {total} files"` - Progress
- `"Duration: {minutes:02d}:{seconds:02d}"` - Duration
- `"Processing completed successfully!"` - Status
- `"✓ Extraction completed successfully!"` - Log
- `"Processing failed!"` - Status
- `"✗ Extraction failed!"` - Log
- `"Error: {message}"` - Log
- `"Cancelling..."` - Status
- `"Cancellation requested..."` - Log
- `"Forcing cancellation due to timeout..."` - Log
- `"Frames Generated: {count}"` - Stat
- `"Animations Generated: {count}"` - Stat
- `"Sprites Failed: {count}"` - Stat
- `"Processing: {files}"` - Worker status

---

## Other Files

### background_handler_window.py
- `"Background Color Options"` - Window title
- `"Select All"` / `"Select None"` - Buttons
- `"Processing Options:"` - Label
- `"Apply Settings"` / `"Cancel"` - Buttons
- `"📄 {filename}"` - File item
- `"Detected background colors:"` - Label
- `"... and {count} more colors"` - Overflow text
- `"RGB({r}, {g}, {b})"` - Color format
- `"Primary"` / `"Secondary {index}"` - Priority labels

### contributors_window.py
- `"Contributors"` - Window title
- `"TextureAtlas Toolbox\nContributors"` - Title
- `"Close"` - Button

### find_replace_window.py
- `"Find and Replace"` - Window title
- `"Find and Replace Rules"` - Title
- `"Add Rule"` / `"Add Preset Rule"` - Buttons
- `"Remove sprite name"` / `"Shorten frame numbers"` - Preset names
- `"Find:"` / `"Replace:"` - Labels
- `"Text to find..."` / `"Replacement text..."` - Placeholders
- `"Regular Expression"` - Checkbox

### first_start_dialog.py
- `"Welcome to TextureAtlas Toolbox"` - Window title
- `"Welcome to {app_name} {app_version}"` - Title
- `"Language"` - Group title
- `"Select language:"` - Label
- `"New Feature Notice"` - Group title
- `"Update Preferences"` - Group title
- `"Check for updates on startup (recommended)"` - Checkbox
- `"Automatically download updates when available"` - Checkbox
- `"Continue"` - Button
- Translation quality labels: `"Native"`, `"Reviewed"`, `"Unreviewed"`, `"Machine Translated"`, `"Unknown"`
- `"Translation quality: {quality}"` - Label
- `"Machine Translation Warning"` - Dialog title
- `"GitHub issues page"` / `"translation guide"` - Link text

### language_selection_window.py
- `"Language Settings"` - Window title
- `"Select Application Language"` - Title
- `"Language:"` - Label
- `"Auto (System Default): {language}"` - ComboBox item
- `"Error"` - Dialog title
- `"Failed to change language: {}"` - Error

### machine_translation_disclaimer_dialog.py
- `"Don't show this disclaimer again for this language"` - Checkbox
- `"View on GitHub"` - Button

### Main.py
- `"Variable delay"` - Menu action
- `"FNF: Set loop delay on idle animations to 0"` - Menu action
- `"Language..."` - Menu action
- `"Change application language"` - Status tip
- `"Editor"` - Tab name
- `"TextureAtlas Toolbox v{version}"` - Window title
- `"No input directory selected"` / `"No output directory selected"` - Labels
- Various error dialogs and messages

### parse_error_dialog.pyh
- `"Parse Issues Detected"` - Window title
- `"File / Issue"` / `"Type"` / `"Skip"` - Table headers
- `"Skip all files with errors"` - Checkbox
- `"Continue Anyway"` / `"Skip Selected"` / `"Cancel"` - Buttons
- `"Error"` / `"Warning"` - Type labels
- `"Skip this file during extraction"` - Tooltip

### settings_window.py
- `"Current Settings Overview"` - Window title
- `"Animation Settings"` / `"Spritesheet Settings"` - Labels
- `"  {key}: {value}"` - Setting format
- `"  No animation-specific settings configured"` - Empty state
- `"  No spritesheet-specific settings configured"` - Empty state

### unknown_atlas_warning_window.py
- `"Unknown Atlas Warning"` - Window title
- `"Affected files:"` - Label
- `"Proceed anyway"` / `"Skip unknown"` / `"Cancel"` - Buttons
- `"... and {count} more"` - Overflow text

### update_checker.py
- `"Update Available"` - Window title
- `"Update Now"` / `"Cancel"` - Buttons

### update_installer.py
- `"TextureAtlas Toolbox Updater"` - Window title
- `"Initializing..."` - Status
- `"Restart Application"` / `"Close"` - Buttons

### dependencies_checker.py
- `"Error"` - Window title

### animation_tree_widget.py (generator)
- `"Animations & Frames"` - Header
- `"New animation"` - Default name
- `"Add animation group"` - Action
- `"Rename animation"` / `"Delete animation"` - Actions
- `"Remove frame"` - Action
- `"Enter new animation name:"` - Dialog prompt
- `"Name conflict"` - Error title
- `"An animation named '{0}' already exists."` - Error

---

## Recommendations for Centralization

### High Priority (Shared across 3+ files)
1. **Window titles** - Consider a `WindowTitles` class
2. **Common dialog messages** - `"Error"`, `"Warning"`, `"Success"`, `"Info"`
3. **File dialog titles** - `"Select Input Directory"`, `"Select Output Directory"`, etc.
4. **Common actions** - `"Add"`, `"Remove"`, `"Delete"`, `"Rename"`

### Medium Priority (Shared across 2 files)
1. **GroupBox titles** for settings panels
2. **Checkbox labels** for common options
3. **Placeholder text** for common inputs

### Low Priority (File-specific)
1. Dynamic messages with format placeholders
2. Context-specific labels
3. Status messages

---

## Notes

- Strings using constants (e.g., `Labels.FRAME_RATE`, `ButtonLabels.OK`) are already centralized
- Dynamic strings with `.format()` are harder to centralize but could use template constants
- Some strings are intentionally file-specific and don't need centralization
