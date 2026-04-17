# Release Notes
Version history and changelog for TextureAtlas Toolbox (formerly TextureAtlas to GIF and Frames).

## Table of Contents (Major Versions)

- [Version 3.0.x](#version-30x)
- [Version 2.0.x](#version-20x)
- [Version 1.9.x](#version-19x)
- [Version 1.8.x](#version-18x)
- [Version 1.7.x](#version-17x)
- [Version 1.6.x](#version-16x)
- [Version 1.5.x](#version-15x)
- [Version 1.4.x](#version-14x)
- [Version 1.3.x](#version-13x)
- [Version 1.2.x](#version-12x)
- [Version 1.1.x](#version-11x)
- [Version 1.0.x](#version-10x)

---

## Current Version

### Version 3.0.0 (Current)
Release date: **TBD**

---

## Version History

### Version 3.0.x

_

#### Version 3.0.0
Release date: **TBD**

##### Highlights
- **UI overhaul**: 
    - App now works on 1280x720 screens.
    - Polished UI layout
    - Themes added (Clean, Material, Fluent, Windows 95, Windows XP) each with Light, Dark, and AMOLED variants
    - **Accent colour presets**: Eight accent colour options (Default, Blue, Purple, Green, Red, Orange, Pink, Teal) applied across all theme families
    - **Step-based setup wizard**: Three-step first-launch wizard (Language → What's New → Theme) with a live preview panel showing sample widgets that restyle in real-time

##### New Features
- Experimental Feature: **GPU Texture Extraction & Compression**
    - Load and extract sprites from DDS and KTX2 GPU-compressed atlas images (BC1/BC3/BC7, ETC1, ETC2, ASTC, PVRTC) using `texture2ddecoder`
    - Generate GPU-compressed atlas images in BC1/DXT1, BC3/DXT5, BC7, ETC1, ETC2, ASTC, and PVRTC formats
    - Optionally generate full mipmap chains with Lanczos downsampling
    - Post-process optimized images with GPU texture compression in the optimizer tab
    - Store compressed textures in industry-standard DDS (DirectX) or KTX2 (Khronos) containers
    - Automatic padding enforcement — padding auto-clamped to block size when GPU format is active
    - Format-gated GPU controls — options only appear for metadata formats used by game engines
    - One-time disclaimer dialog on first GPU format selection
- Feature: **libGDX TexturePacker format**: New parser and exporter for libGDX TexturePacker `.atlas` files
- Feature: **EXIF metadata in WebP/AVIF**: Extracted WebP and AVIF frames now include EXIF metadata
- Feature: **Hierarchical sprite name paths**: Support hierarchical sprite names (e.g. `folder/sprite`) in export paths, preserving directory structure
- Feature: **Job progress window**: Dedicated batch-job progress tracking dialog

##### Enhancements
- Enhancement: **Screen-adaptive sizing**: Initial window dimensions scale to the user's display resolution
- Enhancement: **Extract tab tree overhaul**: Frame counts and stats displayed per-animation in the tree view
- Enhancement: **Dialog consistency overhaul**: All dialog windows restyled for visual consistency across theme families
- Enhancement: **Directory → Folder standardisation**: All user-facing strings changed from "directory" to "folder" for consistency
- Enhancement: **Background atlas import**: Atlas import moved to background thread with progress indicator
- Enhancement: **Granular progress reporting**: Sub-progress reporting in atlas generator for more responsive progress bars
- Enhancement: **Format-specific sprite naming**: Generator now uses format-appropriate naming conventions for exported sprites (hopefully..)
- Enhancement: **JSON parser improvements**: JSON parsers now handle rotated dimensions, `frameTags`, and per-frame duration fields
- Enhancement: **Path sanitization utilities**: New `sanitize_path_name` and `basename_from_sprite_name` helpers
- Enhancement: **Frame signature accuracy**: Increase frame signature prefix from 512 to 2048 bytes for better deduplication


##### Bugfixes
- Bugfix: **Exporter spec compliance**: Spec-compliance fixes for Plist, Spine, and Aseprite exporters
- Bugfix: **Image.fromarray TypeError**: Fix TypeError in standalone/compiled builds when using `Image.fromarray`
- Bugfix: **ImageMagick errors**: Fix ImageMagick path issues on compiled/standalone builds
- Bugfix: **Error popup not displaying**: Fix `show_error_popup` never displaying when QApplication already exists
- Bugfix: **Preview generator variable**: Fix `UnboundLocalError` for `owns_temp_dir` in preview generator
- Bugfix: **Extract tab reset**: Remove duplicate `.clear()` calls in extract tab reset
- Bugfix: **Generator thread leak**: Stop generator worker thread on widget destruction
- Bugfix: **Temp directory leak**: Fix temp directory leak in `add_existing_atlas` on exception
- Bugfix: **Atlas size guard**: Add atlas size guard to prevent excessive memory allocation
- Bugfix: **Image load failure reporting**: Surface image load failures as warnings in generator result instead of silently failing
- Bugfix: **Parser error chaining**: Add exception chaining in base parser catch-all handler
- Bugfix: **File I/O error handling**: Add error handling for file I/O in Aseprite, TXT, and CSS legacy parsers

##### Optimizations
- Optimization: **O(1) frame dedup lookup**: Use set for O(1) `is_frame_already_added` lookup instead of list scan
- Optimization: **Faster single-frame check**: Use `np.array_equal` instead of `.tobytes()` in `is_single_frame`
- Optimization: **Flip hash reuse**: Reuse `flip_y` result when computing `flip_xy` hash
- Optimization: **Frame tuple caching**: Reuse cached frame tuples instead of rebuilding in non-smart grouping
- Optimization: **Memory management**: Close source images after atlas compositing to free memory

##### Tweaks / Removals
- Tweak: **CPU detection**: Grab CPU and thread count directly from registry as primary method, fallback to wmic
- Removed: **In-app User Manual**: Remove in-app manual and link to GitHub docs.

##### Dependencies
- Added: **etcpak** pip package for BC1/BC3/BC7/ETC1/ETC2 compression
- Added: **qt-material** for Material Design theme support
- Added: **qtawesome** for icon font integration

_

### Version 2.0.x

_

#### Version 2.0.5
Release date: **March 22, 2026**

##### New Features
- Feature: **Optimizer tab**: New quantization methods for optimizing atlas images (color reduction, palette generation)
- Feature: **Indonesian language**: Added Indonesian language metadata and translations (community contribution)

##### Bugfixes
- Bugfix: **Animation list after deletion**: Animation list not updating correctly after deleting a spritesheet (#61)
- Bugfix: **Override settings**: Override settings storing redundant global values (#62)
- Bugfix: **PySide6 DLL/plugin errors**: Resolve PySide6 DLL/plugin errors for certain users on Windows portable builds
- Bugfix: **Animation grouping**: Fix animation grouping for spritesheets with sub-indexed frame numbers
- Bugfix: **Spritemap extraction**: Fix spritemap extraction for loosely organized animations prior to export
- Bugfix: **Spritemap symbol filtering**: Filter spritemap symbols to direct children of root timeline
- Bugfix: **Sprite crop rescaling**: Rescale sprite crop coordinates when atlas size mismatches metadata
- Bugfix: **Minimum period padding**: Apply minimum period as last-frame padding instead of per-frame clamp

##### Enhancements
- Enhancement: **Spritemap streaming**: Optimize spritemap extraction by streaming the assets instead of loading all at once
- Enhancement: **Root animation detection**: Improved spritemap root animation detection and symbol filtering
- Enhancement: **Startup messages**: Standardize startup debug print messages with clear prefixes
- Enhancement: **Dependency fixes**: Dependency fixes and build script improvements

_

#### Version 2.0.4
Release date: **February 01, 2026**

##### New Features
- Feature: **6-element matrix spritemaps**: Add support for 3×2 6-element matrix spritemaps

##### Enhancements
- Enhancement: **Translation system cleanup**: Removed temp translation workaround; no more duplicate translation functions required
- Enhancement: **Build scripts**: Replaced unicode checkmarks with ASCII `[OK]` and `[FAIL]` in build scripts for Windows compatibility
- Enhancement: **Build scripts safety**: Flush prints and charmap error fix for Windows workflow
- Enhancement: **Unix builds**: Strip unnecessary PySide6 components on Unix releases as well
- Enhancement: **GitHub Actions**: Added CI workflow for the Translation Editor tool
- Enhancement: **Updated languages**: Refreshed translation files

_

#### Version 2.0.3
Release date: **January 23, 2026**

##### New Features
- Feature: **Translation Editor tool**: Full-featured Translation Editor with API key support, language templates, MT disclaimer management, advanced menubar, and portable build scripts
- Feature: **Quick find/replace presets**: Add presets to remove sprite names or shorten frame digits in the editor
- Feature: **French translations**: French (France) translations are complete

##### Bugfixes
- Bugfix: **Generator animation renaming**: Fix generator not renaming animations properly in exports
- Bugfix: **Translation display**: Fix items not being translated correctly due to QT framework limitations with `ui_constants`
- Bugfix: **Frame number padding**: Proper fix for spritesheets not using zeros for padding the frame number
- Bugfix: **Indices input**: Fix a bug with indices input
- Bugfix: **Small screens**: Band-aid fix for users with screens smaller than 850px in height

##### Enhancements
- Enhancement: **Translateable strings file**: Define translateable strings in a dedicated file for consistency across multiple menus
- Enhancement: **Alpha threshold display**: Make alpha threshold display value consistent, use percentage everywhere
- Enhancement: **Global settings**: Ensure global settings are applied correctly
- Enhancement: **Language auto-detection**: Improvements to language selection and auto-detect languages
- Enhancement: **Build debloat**: Debloat unneeded PySide6 components from builds

_

#### Version 2.0.2
Release date: **January 12, 2026**

##### Bugfixes
- Bugfix: **Bin packing algorithms**: Bin packing algorithms now use their proper logic
- Bugfix: **Generator options**: Generator rotate/alpha/trim and more options have been fixed
- Bugfix: **Combobox refresh**: Fix comboboxes not refreshing data as intended

##### Enhancements
- Enhancement: **Bin packing improvement**: Further improve bin packing by testing aspect ratios and auto-expanding if needed
- Enhancement: **Update installer**: Improve update installer with retry using elevated permissions if needed
- Enhancement: **Build scripts**: New build-portable workflow and embedded Python elevated permission scripts

_

#### Version 2.0.1
Release date: **January 10, 2026**

##### Features
- Feature: **Allow forcing dark or light mode**

##### Bugfixes
- Bugfix: **Frame offset drift**: Prevent offset creep when editing composite animations in the editor tab
- Bugfix: **ImageMagick for embedded builds**: Resolved path issues when running from embedded python releases
- Bugfix: **Update System:** Fixed detection of the available assets from the repository

_

#### Version 2.0.0 
Release date: **January 06, 2026**

*This is the biggest update yet.*


##### Highlights
- **Rebranded to TextureAtlas Toolbox**: The project has been renamed from "TextureAtlas to GIF and
  Frames" to better reflect its expanded capabilities beyond just extraction.

- **Complete UI rewrite in Qt (PySide6)**: The entire interface has been remade
  for improved responsiveness, accessibility, and cross-platform consistency.


- **New "Embedded Python" release variant**: 

  A new portable release option that bundles
  a complete and isolated Python environment.

  This is now the recommended way to run the application, as
  standalone `.exe` builds almost always trigger false positives in the most common antivirus softwares. This release type works as if it were an executable release by using `.bat` or `.sh` scripts to launch.

##### New Features
- Feature: **Automatic Dark/Light mode detection** 

- Feature: **Extended format support**: *Now supports 15+ TextureAtlas/Spritesheet formats and more image formats*

- Feature: **Generator Tab**: 
*Create texture atlases/spritesheets from individual frames—not just extract them.*

- Feature: **Editor Tab**: *Adjust per-frame offsets or combine frames from multiple animations into a single animation output.*

- Feature: **Multi-language support**: *Most languages are currently machine translated until community translations get added.*

- Feature: **Per-frame delay editing**: *Set custom durations for individual frames in animations through the Animation Preview window.*

- Feature: **Multiple duration input formats**: *Specify frame timing as fps, milliseconds (ms), centiseconds (cs), deciseconds (ds), or format-native units*

- Feature: **First-startup dialog**: *Asks user wheter they want to update notifications and language settings*

- Feature: **Resampling options**: *Support common resampling options for image scaling*

##### Enhancements
- Enhancement: **Significantly improved processing time**. Optimized the Extractor logic.

- Enhancement: **Frame duration precision**: Refactored calculations to hopefully prevent floating-point errors

##### Internal / Developer
- Added both quick and extensive tests which can be found in the `tests/` directory

- Setup scripts updated to install Python 3.14.0

- Rewritten most of the documentation instead of having fully AI generated documentation.

##### Translation Editor Tool (`tools/translator-app/`)
A new GUI application to help contributors translate TextureAtlas Toolbox into other languages without
needing developer tools like Qt Linguist.

- **Visual translation editor**: Edit `.ts` translation files with a clean, user-friendly interface

- **Smart string grouping**: Related strings are organized together for context

- **Placeholder syntax highlighting**: Visual feedback for `{variable}` placeholders

- **Real-time validation**: Warns about missing or malformed placeholders before saving

- **Machine translation support**: Optional DeepL, Google Translate, and LibreTranslate API integration

- **Customizable keyboard shortcuts**: Configure hotkeys to match your workflow

- **Theme support**: Light/dark themes.

- **Keyword filtering**: Quickly find specific translation strings

- **Obsolete string detection**: Identifies unused translations for cleanup

I may have missed some bugfixes/enhancements or features, but if I have, then this doc will be updated soon.

---

### Version 1.9.x

#### Version 1.9.5
Release date: **June 2025**

- Bugfix: **Start process button can no longer be pressed if there's an extraction already started**
- Bugfix: **CPU Thread amount is now properly using the value from AppConfig**
- Enhancement: **Debug console can now be shown for .exe releases if started through Command Prompt / PowerShell**
- Enhancement: **Added support for AVIF, BMP, DDS, TGA and TIFF for frame exporting**
- Enhancement: **Extraction settings are now greyed out if it's unneeded or a format not supporting that specific setting**
- Feature: **Added compression settings for frame exporting.**
- Feature: **Attempt to extract unsupported spritesheets**
    - *App can now in **theory** extract any spritesheet type despite not officially supporting them*
    - *Background keying for non transparent images*
    - *Warns if unsupported spritesheet is detected*
    - *Warns if non transparent background is detected*
    - *NOTE: This feature only supports exporting as frames and not animations due to limitations*
- Feature: **Added support for tooltips**
    - *Currently only implemented on compression settings*
- Feature/Tweak: **Update system overhaul**
    - *Show changelog on update notifications*
    - *App can now download updates and replace itself*
    - *Check for updates button in Menubar > Options*
    - *Log update process to a logs folder*
- Feature: **App configuration menu**: 
    - *Modify default extraction settings*
    - *Modify processing threads*
    - *Toggle Automatic update checks*
    - *Toggle Automatically install new updates*
    - *Automatic config file migration between versions*
- Tweak: **Updated in-app help menu**
    - *Added missing option descriptions and the new ones*
    - *FNF Settings advice updated*
- Misc: **Contributors Menu**
- Misc: **New app icon by [Julnz](https://www.julnz.com/)**
  

#### Version 1.9.4
- Bugfix: **Fixed "Invalid Palette Size" error for good by swapping GIF generation to Wand**
- Enhancement: **Improve single frame handling, clear spritesheet settings along with user settings**
- Feature: **Deleting spritesheets from the list by right clicking is now possible**.
- Feature: **Custom filename formats**
- Feature: **Make animation cropping optional, add find and replace feature**
- Feature: **Preview GIFs from Override settings window.**
- Feature: **Filename formatting presets.**

#### Version 1.9.3
- Feature: **Different crop methods for png frames depending on your needs. Defaults to cropping based on animation bounding box.**
- Bugfix: **Fix bug causing user_settings not being applied correctly.**
- Bugfix: **Fix bug involving animations with transparency, all shades of gray and no other colors. (Should solve most gray/black/white spritesheets having problems) Still minor issues on some sprites.**

#### Version 1.9.2  
- Enhancement: **User settings list is now scrollable**
- Enhancement: **User settings no longer show "NONE" values.**
- Bugfix: **Setting scale to 0 actually raises an error** 
- Bugfix: **Blank animations no longer prevents remaining animations from being processed.**
- Bugfix: **Fix GIFs being blank when using HQ color mode on grayscale spritesheets and spritesheets with low color data.**

#### Version 1.9.1
- Tweak: **Crop individual frames is no longer automatic, added a checkbox to let users decide**
- Tweak: **Default Minimum Duration changed from 500 to 0**
- Bugfix: **Fix spritesheet_settings not being cleared for a specific sheet**
- Bugfix: **Windows users with ImageMagick already installed had an issue where the paths clashed, now we're checking if it's already in path**

#### Version 1.9.0
- Enhancement: **Crop individual frames**
- Enhancement: **Frames are only saved when necessary**
- Enhancement: **User settings are only accessed when necessary**
- Enhancement: **Single-frame animations are saved as PNG, no matter what**
- Enhancement: **Instead of being all-or-nothing, specific frames can be chosen to be saved**
- Enhancement: **Use Wand/ImageMagick to achieve better color quality for GIFs, can be turned on under the 'Advanced' tab in the app.**
- Feature: **Advanced delay option: vary some frame delays slightly for more accurate fps, can be turned on under the 'Advanced' tab in the app**
- Feature: **Resize frames and animations, with an option to flip by using negative numbers**
- Experimental Feature: **Set total animation duration to be at least a certain value*- (Not sure if this will be necessary to use at all but w/e)


### Version 1.8.x

#### Version 1.8.1
- Enhancement: **Shows time processed, gif and frames generated**
- Bugfix: **Fixed GIF/WebPs not using correct frame order if the spritesheets xml is unsorted (Like when using Free Packer Tool)**

#### Version 1.8.0
- Feature: **(FNF Specific): Import character animation fps from character json files. Located within the "import" menu**
- Feature: **Support for spritesheets using txt packer (Like Spirit in FNF)**
- Feature: **You can now select individual spritesheets instead of directories. Located within the "file" menu**
- Feature: **Help and advice on the application. Located within the "help" menu**
- Bugfix: **Force all cpu threads now work as intended**
- Bugfix: **Fix cropping for sprites that end up having an empty frame after threshold is applied*- _(does not work for all sprites)_


### Version 1.7.x

#### Version 1.7.1
- Improvement: **If Alpha threshold is set to 1, keep all fully-opaque pixels**
- Improvement: **Alpha threshold is set between 0 and 1 inclusive**
- Bugfix/Improvement: **Frame dimensions are enlarged to hold the entire sprite when necessary, like rotated sprites.**
- Improvement: **Apply Alpha threshold before cropping on GIFs**
- Improvement: **Throw an error when sprite dimensions don't match xml data**
- Bugfix: **Windows .exe having errors**

#### Version 1.7.0
- Feature: **GIFs now automatically gets trimmed/cropped.**
- Feature: **Force max CPU threads**

### Version 1.6.x

#### Version 1.6.0
- Feature: **Indices option (individual animations only) formatted as CSV**
- Feature: **Option to remove png frames**
- Feature: **Show User Settings button.**
- Enhancement: **Allow local settings to be reset to global settings by entering blank values in the popup dialog**
- Enhancement: **Fps now accepts non-integer values**
- Adjustment: **Delay option adds to the final frame duration**
- Adjustment: **Animation names are now in the form of [spritesheet name] [animation name]**
- Bugfix: **Progress bar considers xml files instead of png files**
- Bugfix: **Non-positive width/height no longer trigger errors**
- Bugfix: **Changing the input directory now resets the user settings**
- Bugfix: **Png files without corresponding xml files no longer cause a crash**


### Version 1.5.x

#### Version 1.5.0
- Bugfix: Fix crash when an animation has different size frames
- Bugfix: Fix animations of the same name from different spritesheets not having their settings set independently
- Add threshold option for handling semi-transparent pixels
- Improve handling of some XMLs with unusual SubTexture names, such as those with ".png" suffix or more than 4 digits at the end


### Version 1.4.x

#### Version 1.4.1
- Bugfix: Now properly rounds the loop delay value. GIFs and WebPs should now always have the same loop delay (if not override is used of course)

#### Version 1.4.0
- Enhancement: Now processes multiple files at once (based on your CPU threads divided by two)
- Feature: Setting FPS and delay for individual animations is now possible through a scrollable filelist

```
Performance increase benchmark: 
Processing 106 spritesheets and generating GIFs on an AMD Ryzen 9 3900X and exporting to a regular hard drive.

v1.3.1: 377.82 seconds
v1.4.0: 52.55 seconds
```


### Version 1.3.x

#### Version 1.3.1
- Bugfix: Some spritesheets ended up making a "space" after the file name, this caused an error causing the script to not find the file and directory.
- Enhancement: Show error message when xml files are badly formatted and other errors.
- Enhancement: WebPs are now lossless.

#### Version 1.3.0
- Feature: Added support for framerate.
- Feature: Added support for loop delay.


### Version 1.2.x

#### Version 1.2.0
- Feature: Added support for exporting animated WebPs.
- Feature: Added Update notifications system added
- Enhancement: Frames of animations are now sorted into folders. GIFs/WebPs are now in the main folder of the extracted sprite.
- Enhancement: Now properly supports 'rotated' variable of some spritesheets.


### Version 1.1.x

#### Version 1.1.0
- Bugfix: Frame extraction now properly uses `frameX` / `frameY` / `frameWidth` / `frameHeight` if present in the XML files.
- Bugfix: No longer adds black background to transparent sprites
- Bugfix: GIFs are now properly aligned.


### Version 1.0.x

#### Version 1.0.0
- Initial Release
- Currently only takes folders as input and not individually selected sprites.

---

## Known Issues
- **Memory issues**: Adobe Spritemaps require a lot of processing time to be extracted, some spritemaps may take up to several minutes before it actually starts generating any output. This process takes more time depending on your RAM and CPU.

- **Incorrect output on Adobe Spritemaps**: In some cases depending on how the spritemap was made in Adobe Flash/Animate, output may either miss something or straight up have incorrect alignment, please report a new issue [here](https://github.com/MeguminBOT/TextureAtlas-Toolbox/issues) and attach your extracted output and the affected spritemap file(s) so it can be investigated. 

---

Check out the "[Documentation Hub](docs/README.md)" for more information related to installing, usage, contributing and licenses etc.



Last updated: January 10, 2026 — TextureAtlas Toolbox v2.0.1