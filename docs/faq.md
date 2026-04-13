# Frequently Asked Questions (FAQ)

Welcome to the TextureAtlas Toolbox FAQ! This guide helps you solve common issues when using
our tool to extract and generate texture atlases, convert sprite sheets into animated GIFs, and
export individual frames.

## 📋 Table of Contents

- [Installation Issues](#-installation-issues)
- [File Format Questions](#-file-format-questions)
- [Export Problems](#-export-problems)
- [Performance Issues](#-performance-issues)
- [Friday Night Funkin' Questions](#-friday-night-funkin-questions)
- [General Usage](#️-general-usage)
- [Troubleshooting](#-troubleshooting)
- [Getting More Help](#-getting-more-help)


## 🔧 Installation Issues
*(Not applicable for .exe files)*
If you encounter installation problems (such as Python not being recognized, missing packages, ImageMagick errors, or the application not starting), please see the [Installation Guide](installation-guide.md#-troubleshooting-installation) for detailed troubleshooting steps and solutions to common errors.

This helps keep instructions up to date and avoids duplication. The installation guide covers:
- Python not recognized or not found
- Missing or not found Python packages
- ImageMagick installation and detection issues
- Application startup problems (both .exe and source)
- And more

If you still have trouble after following the installation guide, please open an issue on GitHub or see the rest of this FAQ for additional help.


## 📄 File Format Questions

### Q: What file types can I use with this tool?
**A:** The tool supports both extraction and generation workflows:

**For Extraction (Extract tab):**
- **Image files**: PNG, BMP, DDS, JPEG/JPG, TGA, TIFF, WebP
- **Metadata files**:
  - Starling/Sparrow XML (`.xml`)
  - TexturePacker XML (`.xml`)
  - JSON Hash/Array (`.json`)
  - Phaser 3 (`.json`)
  - Aseprite JSON (`.json`)
  - Spine Atlas (`.atlas`)
  - Plist (Cocos2d) (`.plist`)
  - UIKit Plist (`.plist`)
  - Godot Atlas (`.tpsheet`, `.tpset`)
  - Egret2D (`.json`)
  - Paper2D (`.paper2dsprites`)
  - TexturePacker Unity (`.tpsheet`)
  - CSS Spritesheet (`.css`)
  - TXT (TexturePacker text) (`.txt`)
  - Adobe Animate spritemap pairs (`Animation.json` + `spritemap.json`)
- **FNF files**: JSON or XML character data files from Friday Night Funkin' engines
- **Metadata-free atlases**: PNG/JPEG atlases with no metadata (use chroma key for extraction)

**For Generation (Generate tab):**
- **Input**: Loose PNG/JPEG frames or frame sequences
- **Output metadata formats**: Sparrow/Starling XML, TexturePacker XML, JSON hash/array,
  Aseprite JSON, Spine Atlas, Phaser 3, CSS Spritesheet, TXT, Plist (Cocos2d), UIKit Plist,
  Godot (`.tpsheet`, `.tpset`), Egret2D, Paper2D, TexturePacker Unity (`.tpsheet`)

## 📤 Export Problems

### Q: My GIFs are too large (file size)
**A:** Try these tips to reduce file size:
- **Lower the scale**: Change the scale from 1.0 to 0.75 or lower.
- **Reduce FPS**: Lower the frames per second.

### Q: My GIF animations don't match the speed in the game
**A:** This happens because:
- GIFs can only use whole numbers for frame timing.
- When the program converts FPS to milliseconds, numbers with decimals get rounded.
- Example: 24 FPS = 41.67 ms per frame, which gets rounded to 42 ms.
- This slight difference can make animations appear faster or slower.

### Q: Some animation frames are missing
**A:** Try these solutions:
- **Lower Alpha Threshold**: Decrease the transparency threshold; it may cause some frames to get skipped.
- **Check your sprite sheet**: Make sure all frames are properly defined in your metadata file.

### Q: My exported frames have the wrong size or are misaligned
**A:** Try different cropping options:
- **No crop**: Keeps the original full image size for each frame.
- **Frame-based**: Crops around each individual frame (PNG exports only).
- **Animation-based**: Crops consistently across all frames in an animation to keep frames aligned properly.

### Q: I can't find my exported files
**A:** Look in these locations:
- Files are saved in folders named after your animations.
- Frame images go in a subfolder called `[animation_name]_frames`.
- GIFs/WebP files are saved as `[animation_name].gif` or `[animation_name].webp`.
- Check the output directory you selected in the program.

## ⚡ Performance Issues

### Q: Adobe Animate spritemap extraction is very slow or crashes
**A:** Adobe Animate spritemaps (`Animation.json` + `sheet.json` pairs) require significantly
more memory and CPU than other formats. Try these solutions:
- **Close other applications**: Free up as much RAM as possible.
- **Reduce worker threads**: Lower the thread count in settings; fewer threads = less
  simultaneous memory usage.
- **Use an SSD**: Faster disk access helps with intermediate frame caching.
- **Process smaller batches**: Extract one or two Adobe spritemaps at a time instead of
  batching many together.
- **Upgrade RAM**: 16GB+ is recommended; 32GB+ for large Adobe atlases.

### Q: The program is very slow with big sprite sheets
**A:** Try these speed-up tricks:
- **Increase CPU Threads**: Increase the number in the settings menu. NOTE: This will have the opposite effect if you don't have enough memory.
- **Close other programs**: Free up your computer's memory.
- **Use an SSD**: Processing is faster if your files are on an SSD.

### Q: The program runs out of memory
**A:** Try these memory-saving tips:
- **Reduce CPU Threads**: Lower the number in the settings menu.
- **Make images smaller**: Use a lower scale setting (like 0.5).
- **Close preview windows**: They use up memory.

### Q: Exporting takes a very long time
**A:** Speed up exports with these tips:
- **Temporarily disable antivirus**: It might be scanning each file as it's created.
- **Use your local drive**: Don't save to network or cloud drives.
- **Increase or decrease CPU Threads**: Sometimes fewer threads work better, especially when you're memory-limited.

## 🎵 Friday Night Funkin' Questions

### Q: My FNF character data isn't loading
**A:** Check these things:
- Make sure your character JSON or XML file is correct.
- The image path in your file should match your actual sprite sheet file.
- Your file must match the format for your engine (Kade/Psych/Codename).

## 🛠️ General Usage

### Q: What is GPU texture compression and when should I use it?
**A:** GPU texture compression stores image data in a format that GPUs can decompress directly
during rendering, reducing VRAM usage and improving performance. Use it when generating atlases
for game engines:
- **BC1/BC3/BC7** for desktop games (DirectX, Vulkan)
- **ETC1/ETC2** for mobile games (OpenGL ES)
- **ASTC** for modern mobile and cross-platform (Vulkan, Metal)
- **PVRTC** for legacy iOS (PowerVR GPUs)

If you're just extracting sprites for galleries or web use, you don't need GPU compression.

### Q: My ASTC or PVRTC format says "unavailable"
**A:** ASTC requires the `astcenc` command-line tool and PVRTC requires `PVRTexToolCLI`.
These are not bundled with the application. Download them from:
- **astcenc**: [ARM's GitHub](https://github.com/ARM-software/astc-encoder)
- **PVRTexToolCLI**: [Imagination Technologies](https://developer.imaginationtech.com/pvrtextool/)

BC and ETC formats work out of the box via the included `etcpak` package.

### Q: Why did the padding change when I selected GPU compression?
**A:** GPU compression works on fixed-size blocks (typically 4×4 pixels). If padding between
sprites is smaller than the block size, adjacent sprites can bleed into each other after
compression. The tool automatically increases padding to at least the block size to prevent
this. A one-time informational dialog explains this on first use.

### Q: How can I process a single spritesheet?
**A:** Here's how you do it:
1. In the **Extract** tab, use the menu bar and choose "Select files."
2. Select the metadata file for your sprite sheet.
3. Select the image file containing the sprite sheet.
4. Adjust your settings using global settings, or double-click an animation entry to configure
   per-animation overrides.
5. Click **Start process** to begin extraction.

### Q: How can I generate a new texture atlas from loose frames?
**A:** Use the **Generate** tab:
1. Switch to the **Generate** tab in the main window.
2. Add your loose frame images (PNG/JPEG).
3. Choose your packing algorithm and output metadata format.
4. Configure options like padding, power-of-two sizing, and deduplication.
5. Click the generate button to create your atlas.

### Q: How can I process multiple spritesheets not located in the same folder?
**A:** See the answer to the previous question:
- Anything you add with "Select files" will be added to the processing list.

### Q: How do I handle very large collections of spritesheets?
**A:** The application automatically handles everything:
- Adjust FPS for each individual sprite or animation entry.
- Organize your files in folders before starting.
- Keep an eye on your computer for any error messages. Keep in mind that the app will continue to process and export despite an error occurring, but the CPU worker thread the error happened on will be paused until the user confirms to continue.

### Q: My GIF animations don't match the speed in the game
**A:** This happens because:
- GIFs can only use whole numbers for frame timing.
- When the program converts FPS to milliseconds, numbers with decimals get rounded.
- Example: 24 FPS = 41.67 ms per frame, which gets rounded to 42 ms.
- This slight difference can make animations appear faster or slower.

### Q: Can I add new features to the tool?
**A:** Yes! The tool is open-source:
- Check the [Developer Documentation](developer-docs.md) for details.
- You can add support for new file formats.
- You can add new export options.
- Share your improvements on GitHub.

## 🐛 Troubleshooting

### Q: The program freezes during export
**A:** Try these solutions:
- **Test with smaller files**: Try smaller sprite sheets at first; you may be having memory problems.
- **Reduce amount of CPU Threads**: More CPU threads result in more images being processed at one time, which in return results in more memory usage.
- **Free up memory**: Close other programs.
- **Check your files**: Your sprite sheet or metadata might be corrupted.

### Q: Error: "XML frame dimension data doesn't match"
**A:** This common error can be fixed by:
- **Lower Alpha Threshold**: Try setting it to 0.1 or lower.
- **Check image size**: Make sure your sprite sheet dimensions match what's in the XML.
- **Check coordinates**: Make sure frame coordinates aren't outside the image.

### Q: Find/Replace rules for filenames aren't working
**A:** Check these settings:
- Make sure the "Use regex" checkbox is set if you're using string manipulation.
- Verify your search patterns are correct.
- Remember that uppercase and lowercase letters are treated differently.
- Rules are applied in the order they appear in the list.

### Q: My settings aren't saving
**A:** Try these solutions:
- Make sure you have permission to write to the program's folder.
- Check that the config file path exists.
- Try closing and reopening the program.
- If all else fails, delete `app_config.cfg` to reset everything.

### Q: Updates aren't working
**A:** Try these steps:
- Check your internet connection.
- Download the latest version manually from GitHub.
- Replace all files with the manually downloaded update from GitHub.

## 📞 Getting More Help

### Still having problems?

1. **Check for errors**: Look for error messages in the console window.
2. **Try a simple test**: Use a small, simple sprite sheet.
3. **Update the software**: Make sure you have the latest version.
4. **Check requirements**: Make sure all required software is installed.

### How to report bugs

1. **GitHub Issues**: [Report bugs here](https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames/issues).
2. **Include details**: Share error messages, example files, and your system information (if applicable).
3. **Describe the steps**: Explain exactly how to reproduce the problem.
4. **Add screenshots**: Pictures help show visual problems.

### Where to find more information

- **User Manual**: Read the [User Manual](user-manual.md) for detailed instructions.
- **FNF Guide**: Check the [Friday Night Funkin' Guide](fnf-guide.md) for FNF-specific help.
- **Developer Docs**: See the [Developer Documentation](developer-docs.md) if you want to modify the tool.
- **API Reference**: See the [API Reference](api-reference.md) for more specific things when modifying the tool.

---

*Can't find your answer? Open an issue on [GitHub](https://github.com/MeguminBOT/TextureAtlas-to-GIF-and-Frames/issues) with your question.*

---

*Last updated: December 6, 2025 — TextureAtlas Toolbox v2.0.0*
