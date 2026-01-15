# Translation Editor

A comprehensive Qt-based GUI tool for editing translation files (.ts) for the TextureAtlas Toolbox.

## Features

- **Smart String Grouping**: Automatically groups identical source strings across multiple contexts, reducing translation work
- **Syntax Highlighting**: Highlights placeholders (e.g., `{count}`, `{filename}`) in both source and translation text
- **Dark/Light Mode**: Toggle between themes for comfortable editing in any environment
- **Real-time Preview**: See how translations look with actual placeholder values
- **Validation System**: Prevents saving files with missing or extra placeholders
- **Context Information**: Shows all contexts where each string is used
- **Copy Source**: Quick button to copy source text as a starting point for translation
- **Translation Services Integration**: Supports Google Cloud, DeepL and LibreTranslate services
- **Language Management**: Register languages, set quality levels, and manage MT disclaimers
- **CLI Support**: Batch operations for CI/CD integration

## Usage

### Running the Application

**Option 1: Using the launcher script (Recommended)**

*Windows:*
```bash
Launch Translation Editor.bat
```

*Linux/macOS:*
```bash
./launch-translation-editor.sh
```

**Option 2: Running directly with Python**
```bash
# From the src directory
cd src
python Main.py

# Or open a specific .ts file
python Main.py path/to/file.ts
```

### Quick Start

1. **Open a .ts file**: Click "Open .ts File" or use Ctrl+O
2. **Select a translation**: Click on any item in the left list
3. **Edit translation**: Type in the "Translation" field on the right
4. **Preview results**: Use the placeholder fields to see how the translation looks
5. **Save**: Use Ctrl+S or click "Save .ts File"

### Visual Indicators

- Green checkmark: Translation is complete
- Red X: Translation is missing
- Number badge: String appears in multiple contexts (grouped)

### Keyboard Shortcuts

- `Ctrl+O`: Open file
- `Ctrl+S`: Save file
- `Ctrl+Shift+S`: Save as
- `Ctrl+Q`: Exit

## File Structure

```
translator-app/
├── src/
│   ├── Main.py              # Main application entry point
│   ├── cli.py               # Command-line interface
│   ├── core/                # Core translation logic
│   ├── gui/                 # UI components
│   ├── localization/        # Language registry and operations
│   ├── providers/           # Translation service providers
│   └── utils/               # Utilities and preferences
├── setup/
│   ├── build_portable.py    # Portable build script
│   ├── build-portable-windows.bat
│   └── build-portable-unix.sh
├── templates/               # Translation file templates
├── Launch Translation Editor.bat   # Windows launcher
└── README.md
```

## Smart Grouping Feature

When the same source string appears in multiple contexts (e.g., "Save" button appears in multiple dialogs), the tool automatically groups them together. This means:

- You only need to translate each unique string once
- Changes apply to all contexts using that string
- The context panel shows where each string is used
- Saving maintains the original file structure with all contexts

## Validation

The tool validates that:
- All placeholders from source text are included in translation
- No extra placeholders are added in translation
- Files cannot be saved with validation errors

This prevents runtime errors in the main application.

## Command-Line Interface

The Translation Editor includes a CLI for batch operations and CI/CD integration.

### CLI Usage

```bash
# Run CLI through Main.py
python Main.py --cli <command> [options]

# Or run cli.py directly
python cli.py <command> [options]

# Get help
python cli.py help
python cli.py help <command>
```

### Available Commands

| Command | Description |
|---------|-------------|
| `extract` | Run lupdate to extract translatable strings from source |
| `compile` | Run lrelease to compile .ts files to .qm binaries |
| `resource` | Generate translations.qrc file |
| `status` | Show translation progress report |
| `disclaimer` | Add, remove, or toggle MT disclaimers |
| `quality` | Set translation quality level (machine/reviewed/unknown) |
| `help` | Show help for a command |

### CLI Examples

```bash
# Extract strings for specific languages
python cli.py extract fr_FR de_DE

# Compile all languages
python cli.py compile

# Show translation status
python cli.py status

# Add disclaimer to French translation
python cli.py disclaimer --add fr_FR

# Remove disclaimer
python cli.py disclaimer --remove fr_FR

# Toggle disclaimer (add if missing, remove if present)
python cli.py disclaimer --toggle fr_FR

# Set quality level
python cli.py quality fr_FR --set reviewed
python cli.py quality de_DE es_ES --set machine

# Specify custom source directory
python cli.py --src-dir /path/to/project/src status
```
