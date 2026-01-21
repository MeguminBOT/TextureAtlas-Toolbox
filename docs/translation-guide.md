# Translation Guide

This guide explains how to contribute translations to the TextureAtlas Toolbox application. The
project uses Qt's translation system with `.ts` (Translation Source) files that can be edited
with various tools.

## Table of Contents

-   [Translation System Overview](#translation-system-overview)
-   [Getting Started](#getting-started)
-   [TS File Structure](#ts-file-structure)
-   [What to Translate](#what-to-translate)
-   [Placeholder Variables](#placeholder-variables)
-   [Translation Tools](#translation-tools)
-   [Working with TS Files](#working-with-ts-files)
-   [Testing Your Translations](#testing-your-translations)
-   [Translation Management Scripts](#translation-management-scripts)
-   [Best Practices](#best-practices)
-   [Troubleshooting](#troubleshooting)

## Translation System Overview

The TextureAtlas Toolbox uses Qt's internationalization (i18n) system:

-   **Source Language**: English (en_US)
-   **Translation Files**: Located in `src/translations/`
-   **File Format**: Qt TS files (XML-based)
-   **Compiled Files**: QM files (binary, generated automatically)

Any language supported by Qt can be added. Current translations include:

### File Structure

```
src/translations/
├── app_en.ts      # English (reference/source)
├── app_sv.ts      # Swedish
├── app_es.ts      # Spanish
├── app_fr.ts      # French
├── app_de.ts      # German
├── app_ja.ts      # Japanese
└── app_zh.ts      # Chinese
```

## Getting Started

### Prerequisites

-   Basic understanding of the target language
-   A text editor, or one of the translation tools described below
-   Git for version control (if contributing)

### Quick Start

**Option A: Using TextureAtlas Toolbox - Translation Editor (Recommended)**

1. Run the Translation Editor from `tools/translator-app/`
2. Open a `.ts` file (e.g., `src/translations/app_es.ts`)
3. Click on untranslated entries (marked with a red indicator)
4. Type your translation and press `Ctrl+S` to save

**Option B: Using a Text Editor**

1. Open a language file from `src/translations/` (e.g., `app_es.ts`)
2. Search for `<translation type="unfinished"></translation>`
3. Add your translation between the `<translation>` tags
4. Save the file

**Option C: Using the Simple Text Format**

1. Run `tools\convert ts to txt.bat` (Windows) and select "Extract"
2. Edit the generated `.txt` file with any text editor
3. Run the batch file again and select "Apply"

After translating, compile your changes:

```bash
python tools/translate.py compile
```

## TS File Structure

TS files are XML-based with a specific structure:

```xml
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="sv">
<context>
    <name>WindowClassName</name>
    <message>
        <location filename="../gui/window.py" line="42"/>
        <source>Original English Text</source>
        <translation>Your Translation Here</translation>
    </message>
</context>
</TS>
```

### Key Elements

#### File Header

```xml
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE TS>
<TS version="2.1" language="sv">
```

-   **version**: Qt TS format version (always 2.1)
-   **language**: ISO language code (e.g., `sv` for Swedish, `es` for Spanish)

#### Context Blocks

```xml
<context>
    <name>TextureAtlasExtractorApp</name>
    <!-- Messages for this class/context -->
</context>
```

-   **name**: The Python class or context where the text appears
-   Groups related translations together
-   Common contexts: `TextureAtlasExtractorApp`, `ProcessingWindow`, `SettingsWindow`

#### Message Entries

```xml
<message>
    <location filename="../Main.py" line="147"/>
    <source>Variable delay</source>
    <translation>Variabel fördröjning</translation>
</message>
```

-   **location**: Source file and line number (for reference only)
-   **source**: Original English text (DO NOT MODIFY)
-   **translation**: Your translated text

#### Translation States

```xml
<!-- Not yet translated -->
<translation type="unfinished"></translation>

<!-- Translated -->
<translation>Your Translation</translation>

<!-- Obsolete/removed from source -->
<translation type="vanished">Old Translation</translation>
```

## What to Translate

### Translate These Elements

**User Interface Text**

-   Button labels: "Start process", "Cancel", "OK"
-   Menu items: "File", "Settings", "Help"
-   Tab titles: "Animation Settings", "Compression"
-   Dialog titles: "Error", "Warning", "Success"

**User Messages**

-   Error messages: "No input directory selected"
-   Success messages: "Processing completed successfully!"
-   Warning messages: "Could not load language"
-   Information text: "Select files to process"

**Tooltips and Help Text**

-   Explanatory text for UI elements
-   Status descriptions
-   Guide text

**File Dialog Labels**

-   "Select Input Directory"
-   "Select Output Directory"
-   "Image files (_.png _.jpg _.jpeg);;All files (_.\*)"

### Do NOT Translate

**Technical Terms**

-   File extensions: ".png", ".xml", ".ts"
-   Format names: "TextureAtlas", "GIF", "WebP"
-   Technical settings: "FPS", "RGB", "alpha"

**Variable Names and Placeholders**

-   `{version}`, `{filename}`, `{count}` (see Placeholder Variables section)
-   Code-related terms that would break functionality

**Source Elements**

-   Never modify `<source>` content
-   Never change `<location>` attributes
-   Don't alter XML structure

## Placeholder Variables

Many strings contain placeholder variables that get replaced with actual values at runtime.

### Common Placeholders

```xml
<!-- Version numbers -->
<source>TextureAtlas Toolbox v{version}</source>
<translation>TextureAtlas Toolbox v{version}</translation>

<!-- File names (Swedish example) -->
<source>Processing: {filename}</source>
<translation>Bearbetar: {filename}</translation>

<!-- Counts and numbers (Swedish example) -->
<source>Progress: {current} / {total} files</source>
<translation>Framsteg: {current} / {total} filer</translation>

<!-- Multiple variables (Swedish example) -->
<source>CPU: {cpu} (Threads: {threads})</source>
<translation>Processor: {cpu} (Trådar: {threads})</translation>
```

### Rules for Placeholders

1. **Always preserve the exact placeholder text**: `{version}`, `{filename}`, etc.
2. **You can reorder placeholders** to match your language's grammar
3. **You can adjust surrounding text** but keep the `{placeholder}` intact
4. **Common placeholders**:
    - `{version}` - Version numbers
    - `{filename}` - File names
    - `{count}`, `{current}`, `{total}` - Numbers
    - `{error}` - Error messages
    - `{cpu}`, `{threads}`, `{memory}` - System information

### Examples by Language

**English (Original)**

```xml
<source>Found {count} unknown spritesheet(s) with background colors.</source>
```

**Swedish**

```xml
<translation>Hittade {count} okända spritesheet(s) med bakgrundsfärger.</translation>
```

**German**

```xml
<translation>Es wurden {count} unbekannte Spritesheet(s) mit Hintergrundfarben gefunden.</translation>
```

**French**

```xml
<translation>Trouvé {count} spritesheet(s) inconnue(s) avec des couleurs d'arrière-plan.</translation>
```

## Translation Tools

There are several ways to edit translation files for TextureAtlas Toolbox. Choose the method
that works best for your workflow:

| Tool                                          | Best For                            | Interface       |
| --------------------------------------------- | ----------------------------------- | --------------- |
| **TextureAtlas Toolbox - Translation Editor** | Visual editing with validation      | GUI or CLI      |
| **Simple Text Format**                        | Contributors who prefer plain text  | CLI/Interactive |
| **Qt Linguist**                               | Advanced translation workflows      | GUI             |
| **Text Editor**                               | Quick edits when familiar with XML  | Any             |

---

### Option 1: TextureAtlas Toolbox - Translation Editor (Recommended)

The project includes a standalone GUI application specifically designed for managing and editing `.ts` files in a way that makes it easy for people who are less experienced and has several safe checks when saving translations.
It's located in `tools/translator-app/`. For portable versions that are ready to run, check the releases page, they are listed together with TextureAtlas Toolbox releases.

**Features**

-   **Smart String Grouping**: Automatically groups identical source strings across multiple contexts, reducing translation work
-   **Syntax Highlighting**: Highlights placeholders (e.g., `{count}`, `{filename}`) in both source and translation text
-   **Dark/Light Mode**: Toggle between themes for comfortable editing in any environment
-   **Real-time Preview**: See how translations look with actual placeholder values
-   **Validation System**: Prevents saving files with missing or extra placeholders
-   **Context Information**: Shows all contexts where each string is used
-   **Copy Source**: Quick button to copy source text as a starting point for translation
-   **Filter Syntax**: Search with keywords like `is:missing`, `mark:unsure`, `has:placeholder`, `ctx:name`
-   **Quality Markers**: Mark translations as Unsure, Machine Translated, or Complete with keyboard shortcuts
-   **Translation Services Integration**: Supports Google Cloud, DeepL and LibreTranslate services
-   **Language Management**: Register languages, set quality levels, and manage MT disclaimers
-   **CLI Support**: Batch operations for CI/CD integration

**Running the Editor**

_Windows (Portable - Recommended):_

Run the `Translation Editor.bat` file in `tools/translator-app/`

_Linux/macOS:_

Run the `translation-editor.sh` file by double clicking it (check execution permission)

_Python (Any OS):_

```bash
cd tools/translator-app/src
python Main.py

# Or open a specific file directly
python Main.py path/to/app_sv.ts
```

**Quick Start**

1. Run the app
2. Select existing language or add a new one
3. Add translation
4. Save: Use `Ctrl+S` or click "Save .ts File"

**Visual Indicators**

The editor uses colored indicators to show translation status:

| Color  | Meaning                                       |
| ------ | --------------------------------------------- |
| Green  | Translation complete                          |
| Purple | Machine translation                           |
| Yellow | Unsure                                        |
| Red    | Translation missing                           |
| Number badge | String appears in multiple contexts (grouped) |

**Translation Quality Colors**

When viewing language files in the Manage tab, colors indicate the overall translation quality level:

| Color  | Quality Level | Description                           |
| ------ | ------------- | ------------------------------------- |
| Blue   | Native        | Approved by multiple native speakers  |
| Cyan   | Reviewed      | Checked by at least one reviewer      |
| Orange | Unreviewed    | Human translated but not yet reviewed |
| Purple | Machine       | Auto-generated machine translation    |
| Gray   | Unknown       | Quality level not specified           |

**Keyboard Shortcuts**

| Shortcut       | Action                            |
| -------------- | --------------------------------- |
| `Ctrl+O`       | Open file                         |
| `Ctrl+S`       | Save file                         |
| `Ctrl+Shift+S` | Save as                           |
| `Ctrl+Q`       | Exit                              |
| `Ctrl+Shift+C` | Copy source text to translation   |
| `Ctrl+T`       | Auto-translate (requires API key) |
| `Ctrl+F`       | Search translations               |
| `Ctrl+Down`    | Navigate to next item             |
| `Ctrl+Up`      | Navigate to previous item         |
| `Ctrl+Shift+0` | Clear marker (None)               |
| `Ctrl+Shift+1` | Mark as Unsure                    |
| `Ctrl+Shift+2` | Mark as Machine Translated        |
| `Ctrl+Shift+3` | Mark as Complete                  |

**Filter Syntax**

The search box supports structured filter keywords:

| Filter | Description |
| ------ | ----------- |
| `is:translated` / `is:done` | Show translated items |
| `is:missing` / `is:untranslated` | Show untranslated items |
| `is:mt` / `is:machine` | Show machine translated items |
| `is:vanished` | Show obsolete/vanished items |
| `mark:unsure` | Items marked as unsure |
| `mark:complete` | Items marked as complete |
| `mark:none` | Items with no marker |
| `has:placeholder` / `has:ph` | Items containing placeholders |
| `ctx:<name>` / `context:<name>` | Items in a specific context |

Examples:
- `is:missing` — Show only untranslated items
- `is:mt has:ph` — Machine translated items with placeholders
- `ctx:SettingsWindow` — Items in the SettingsWindow context

**Advanced Menu**

The **Advanced** menu provides bulk operations:

- **Mark all translations as...** — Apply a marker to all entries in the current file:
  - None (Clear Markers)
  - Unsure
  - Machine Translated
  - Complete

**Machine Translation API Setup (Optional)**

The Translation Editor supports optional machine translation via DeepL, Google Cloud, or LibreTranslate. Configure API keys via environment variables or the preferences file.

For detailed setup instructions, see the [Translation Editor README](../tools/translator-app/README.md#optional-machine-translation-api-setup).

---

### Option 2: CLI Translation Script (`translate.py`)

The primary command-line tool for extracting, compiling, and managing translation files.
Use this for batch operations, CI/CD pipelines, or when you prefer the terminal.

**Location**: `tools/translate.py` (or `tools/translate.bat` on Windows)

**Quick Start**

```bash
# Run the full update cycle (extract → compile → resource → status)
python tools/translate.py all

# Windows batch wrapper
tools\translate.bat all
```

**Available Commands**

| Command      | Description                                                      |
| ------------ | ---------------------------------------------------------------- |
| `extract`    | Extract translatable strings from Python source into `.ts` files |
| `compile`    | Compile `.ts` files to binary `.qm` files for the application    |
| `resource`   | Create/update Qt resource file for translations                  |
| `status`     | Show translation progress for each language                      |
| `disclaimer` | Add machine translation disclaimers to `.ts` files               |
| `all`        | Run extract → compile → resource → status in sequence            |

**Usage Examples**

```bash
# Extract strings for all languages
python tools/translate.py extract

# Extract only for Swedish and English
python tools/translate.py extract sv en

# Compile Swedish translations
python tools/translate.py compile sv

# Check status for Spanish, French, and German
python tools/translate.py status es fr de
```

**Understanding Status Output**

```
Translation Status Report
========================

Swedish (sv): 131/201 translated (65%) [machine]
Spanish (es): 19/205 translated (9%) [native]
French (fr): 13/200 translated (6%) [machine]
```

-   `[machine]` indicates machine-translated languages
-   `[native]` indicates native/human-translated languages

Run `python tools/translate.py` without arguments to see all available language codes.

---

### Option 3: Simple Text Format (`convert ts to txt.py`)

For contributors who prefer editing translations in plain text rather than XML. This tool
converts between `.ts` files and a simple `original := translated` text format.

**Text Format Example** (`sv.txt`):

```
Language Settings := Språkinställningar
Select Application Language := Välj applikationsspråk
Save := Spara
```

**Interactive Mode (Windows)**

Double-click `tools\convert ts to txt.bat` for an interactive menu:

1. **Extract** — Export `.ts` translations to `.txt` format
2. **Create Template** — Generate a new language template
3. **Apply** — Import `.txt` translations back into `.ts` files

**Command Line Usage**

```bash
# Extract Swedish translations to simple format
python "tools/convert ts to txt.py" sv --extract

# Create a template for a new language
python "tools/convert ts to txt.py" de --create-example

# Apply translations from .txt back to .ts
python "tools/convert ts to txt.py" sv
```

---

### Option 4: Qt Linguist

Qt Linguist is the official tool for editing TS files. It's more complex but offers advanced
features like translation memory and spell checking.

**Installation**

-   _Windows:_ Download the Qt installer and select "Qt Linguist"
-   _Linux:_ `sudo apt install qttools5-dev-tools` (or equivalent)
-   _macOS:_ Install Qt via Homebrew

**Usage**

1. Open Qt Linguist
2. File → Open → Select your `.ts` file
3. Navigate through messages in the left panel
4. Enter translations in the bottom panel
5. File → Save

---

### Option 5: Text Editor

Any text editor can edit TS files directly, but be careful with XML syntax.

**Recommended Editors**: VS Code, Sublime Text, Notepad++

**Pros**: Simple, fast, no additional software  
**Cons**: No validation, easy to break XML etc.

Look for entries with `<translation type="unfinished"></translation>` and add your translation
between the tags.

## Working with TS Files

### Finding Untranslated Strings

Look for entries like this:

```xml
<translation type="unfinished"></translation>
```

### Adding a Translation

Change from:

```xml
<translation type="unfinished"></translation>
```

To:

```xml
<translation>Your Translation Here</translation>
```

### Updating Existing Translations

Simply replace the text between `<translation>` tags:

```xml
<!-- Before -->
<translation>Old Translation</translation>

<!-- After -->
<translation>New Improved Translation</translation>
```

### Handling Special Characters

**Quotes and Apostrophes**
Use XML entities for special characters:

```xml
<!-- Use &apos; for apostrophes in XML -->
<source>animations with &apos;idle&apos; in their name</source>
<translation>animationer med &apos;idle&apos; i namnet</translation>

<!-- Use &quot; for quotes -->
<source>Select &quot;Advanced&quot; options</source>
<translation>Välj &quot;Avancerade&quot; alternativ</translation>
```

**Other Special Characters**

-   `&lt;` for `<`
-   `&gt;` for `>`
-   `&amp;` for `&`

### Multi-line Translations

For longer text, you can use line breaks:

```xml
<translation>This is a longer translation
that spans multiple lines for
better readability.</translation>
```

## Testing Your Translations

### Using the Application

1. Save your TS file
2. Compile the translation:
    ```bash
    python tools/translate.py compile sv
    ```
3. Launch the application
4. Go to **Settings → Language** → Select your language
5. Verify your translations appear correctly

### Validation Checklist

-   [ ] All placeholders (`{variable}`) are preserved
-   [ ] No XML syntax errors
-   [ ] Text fits in the UI (not too long)
-   [ ] Special characters are properly escaped
-   [ ] Context makes sense for the UI element
-   [ ] Grammar and spelling are correct

## Translation Management Scripts

The CLI script `tools/translate.py` handles all translation management tasks. On Windows, you
can also use the `tools/translate.bat` wrapper.

### Quick Reference

| Task                | Command                              |
| ------------------- | ------------------------------------ |
| Full update cycle   | `python tools/translate.py all`      |
| Extract new strings | `python tools/translate.py extract`  |
| Compile to `.qm`    | `python tools/translate.py compile`  |
| Check progress      | `python tools/translate.py status`   |
| Update Qt resources | `python tools/translate.py resource` |

### Common Commands

**Check Translation Status**

```bash
# Status for all languages
python tools/translate.py status

# Status for specific languages
python tools/translate.py status sv es fr
```

**Extract New Strings**

```bash
# Extract for all languages
python tools/translate.py extract

# Extract for specific languages
python tools/translate.py extract sv es
```

**Compile Translations**

```bash
# Compile all languages
python tools/translate.py compile

# Compile specific languages
python tools/translate.py compile sv fr
```

### Windows Batch Wrapper

Windows users can use the batch script for convenience:

```batch
tools\translate.bat status sv
tools\translate.bat extract sv
tools\translate.bat compile sv
tools\translate.bat all
```

## Best Practices

### Language-Specific Guidelines Example.

**Swedish (sv)**

-   Use formal address ("ni" forms) in UI
-   Keep compound words reasonable length
-   Maintain consistent terminology

**Spanish (es)**

-   Consider regional variations (prefer neutral Spanish)
-   Use consistent gender for technical terms
-   Watch for text expansion (Spanish ~20% longer than English)

**French (fr)**

-   Follow proper capitalization rules
-   Consider formal vs informal address
-   Account for text length changes

**German (de)**

-   Handle compound words appropriately
-   Consider formal address (Sie/Du)
-   Watch for significant text expansion

**Japanese (ja)**

-   Consider context for politeness levels
-   Keep technical terms in katakana when appropriate
-   Be mindful of vertical text limitations

**Chinese (zh)**

-   Use Simplified Chinese unless specified
-   Keep technical terms consistent
-   Consider character width in UI layouts

### General Guidelines

**Consistency**

-   Maintain consistent terminology throughout
-   Use the same translation for repeated phrases
-   Keep UI element names consistent

**Context Awareness**

-   Consider where the text appears (button, dialog, menu)
-   Ensure translations fit the UI space
-   Match the tone of the original text

**User Experience**

-   Prioritize clarity over literal translation
-   Use familiar terms for your target audience
-   Consider cultural differences in software interaction

**Technical Accuracy**

-   Don't translate technical terms that users expect in English
-   Preserve software-specific terminology
-   Maintain functional aspects (like file extensions)

## Advanced Troubleshooting

### Common Issues

**XML Syntax Errors**

```
Error: XML parse error at line 45
```

**Solution**: Check for:

-   Unclosed tags: `<translation>text`
-   Unescaped special characters: `<translation>Bill's file</translation>`
-   Should be: `<translation>Bill&apos;s file</translation>`

**Missing Translations**
Your translations don't appear in the application.

**Solution**:

1. Ensure the TS file is saved
2. Compile: `python tools/translate.py compile sv`
3. Restart the application
4. Check language selection in settings

**Text Too Long**
Your translation doesn't fit in the UI.

**Solution**:

-   Use shorter synonyms
-   Abbreviate where appropriate
-   Check the UI element context
-   Consider redesigning long phrases

**Placeholder Issues**
Variables like `{filename}` don't work.

**Solution**:

-   Ensure exact placeholder spelling: `{filename}`, not `{file_name}`
-   Check for extra spaces: `{ filename }` won't work
-   Verify placeholder is inside translation tags

### Getting Help

**Translation Questions**

-   Check existing translations in other languages for reference
-   Look at the source code context in the `<location>` attribute
-   Test changes in the application to see context

**Technical Issues**

-   Check the project's issue tracker
-   Verify your Python environment has required packages
-   Ensure file permissions allow writing

**File Corruption**
If your TS file becomes corrupted:

1. If you are using Git, then restore from Git: `git checkout HEAD -- src/translations/app_sv.ts`
2. Re-extract strings: `python tools/translate.py extract sv`
3. Reapply your translations

### Validation Commands

**Check XML Syntax**

```bash
# Linux/Mac
xmllint --noout src/translations/app_sv.ts

# Windows: use an online XML validator or the TextureAtlas Toolbox - Translation Editor's built-in validation
```

**Test Compilation**

```bash
python tools/translate.py compile sv
```

If this fails, there's likely an XML syntax error.

**Compare with Reference**

```bash
# Show differences from last commit
git diff src/translations/app_sv.ts

# Compare with English reference
# (manual comparison recommended)
```

## Additional Resources

### Qt Documentation

-   [Qt Linguist Manual](https://doc.qt.io/qt-6/qtlinguist-index.html)
-   [Qt Internationalization](https://doc.qt.io/qt-6/internationalization.html)

### Translation Tools

-   [Qt Linguist](https://doc.qt.io/qt-6/qtlinguist-linguist.html) - Official Qt translation tool
-   [Poedit](https://poedit.net/) - General translation editor (with TS support)
-   [OmegaT](https://omegat.org/) - Open source translation memory tool

### Language Resources

-   [ISO 639-1 Language Codes](https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)
-   [Unicode Character Reference](https://unicode-table.com/)
-   [XML Entity Reference](https://www.w3.org/TR/xml-entity-names/)

### Project Specific

-   [User Manual](user-manual.md) - Understanding the application
-   [Developer Documentation](developer-docs.md) - Technical details

---

_Thank you for contributing to the TextureAtlas Toolbox translations! Your work helps make the software accessible to users worldwide._
