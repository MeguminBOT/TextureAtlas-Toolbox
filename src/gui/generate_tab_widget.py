#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pathlib import Path
from PySide6.QtWidgets import (
    QSpinBox,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QLabel,
    QMenu,
    QPushButton,
    QCheckBox,
    QScrollArea,
)
from PySide6.QtCore import QSize, Qt, QThread, Signal

from gui.base_tab_widget import BaseTabWidget
from gui.job_progress_window import JobProgressWindow

try:
    from PIL import Image, ImageSequence

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# Import our own modules
from gui.generator.animation_tree_widget import AnimationTreeWidget
from parsers.xml_parser import XmlParser
from utils.utilities import Utilities

# Import the new generator system
from core.generator import AtlasGenerator, GeneratorOptions, get_available_algorithms
from utils.translation_manager import tr as translate
from utils.ui_constants import (
    ButtonLabels,
    Labels,
    CheckBoxLabels,
    FileDialogTitles,
    FileFilters,
)

SUPPORTED_ROTATION_FORMATS = frozenset(
    {
        "starling-xml",
        "json-hash",
        "json-array",
        "aseprite",
        "texture-packer-xml",
        "spine",
        "phaser3",
        "plist",
        "paper2d",
        "gdx",
    }
)

SUPPORTED_FLIP_FORMATS = frozenset({"starling-xml"})

# Formats that support storing trim offset data (frameX/frameY, spriteSourceSize, etc.)
# These formats can represent trimmed sprites with offset metadata so consumers
# can reconstruct the original sprite position during playback.
SUPPORTED_TRIM_FORMATS = frozenset(
    {
        "starling-xml",  # frameX, frameY, frameWidth, frameHeight
        "json-hash",  # spriteSourceSize, sourceSize, trimmed
        "json-array",  # spriteSourceSize, sourceSize, trimmed
        "texture-packer-xml",  # oX, oY (offset attributes)
        "spine",  # offset in atlas format
        "phaser3",  # spriteSourceSize, sourceSize
        "plist",  # spriteOffset, spriteSourceSize
        "uikit-plist",  # oX, oY offset fields
        "paper2d",  # spriteSourceSize metadata
        "gdx",  # bounds/offsets fields
    }
)

# Formats whose target engines commonly consume GPU-compressed textures.
# GPU compression controls are only shown when one of these formats is selected.
SUPPORTED_GPU_COMPRESSION_FORMATS = frozenset(
    {
        "json-hash",  # PixiJS, Phaser, Cocos2d-js (WebGL compressed textures)
        "json-array",  # PixiJS, Phaser (WebGL compressed textures)
        "spine",  # Spine runtime supports GPU textures
        "phaser3",  # WebGL engine, compressed texture extensions
        "plist",  # Cocos2d supports PVRTC/ETC textures
        "godot",  # Godot natively supports DDS/KTX2
        "egret2d",  # Egret2D game engine
        "paper2d",  # Unreal Engine uses DDS
        "unity",  # Unity imports DDS/KTX textures
        "gdx",  # libGDX supports GPU textures
    }
)


class AtlasImportWorker(QThread):
    """Worker thread for importing frames from an existing atlas."""

    progress_updated = Signal(int, int, str)
    import_completed = Signal(dict)
    import_failed = Signal(str)

    def __init__(
        self,
        atlas_file,
        sprites_data,
        animation_groups,
        temp_dir,
        png_format,
        png_format_name,
    ):
        super().__init__()
        self.atlas_file = atlas_file
        self.sprites_data = sprites_data
        self.animation_groups = animation_groups
        self.temp_dir = temp_dir
        self.png_format = png_format
        self.png_format_name = png_format_name

    def run(self):
        """Extract frames from atlas in background thread."""
        try:
            ext = Path(self.atlas_file).suffix.lower()
            if ext in (".dds", ".ktx2"):
                from core.optimizer.texture_compress import load_gpu_texture

                atlas_image = load_gpu_texture(self.atlas_file)
            else:
                atlas_image = Image.open(self.atlas_file)

            results = {}
            total_sprites = sum(
                len(frames) for frames in self.animation_groups.values()
            )
            processed = 0

            for animation_name, frames_data in self.animation_groups.items():
                frames_data.sort(key=lambda x: Utilities.natural_sort_key(x["name"]))

                frame_paths = []
                for sprite_data in frames_data:
                    try:
                        x, y = sprite_data["x"], sprite_data["y"]
                        width, height = sprite_data["width"], sprite_data["height"]
                        rotated = sprite_data.get("rotated", False)

                        sprite_region = atlas_image.crop((x, y, x + width, y + height))

                        if rotated:
                            sprite_region = sprite_region.transpose(
                                Image.Transpose.ROTATE_90
                            )

                        frame_x = int(sprite_data.get("frameX", 0))
                        frame_y = int(sprite_data.get("frameY", 0))
                        frame_w = int(
                            sprite_data.get("frameWidth", sprite_region.width)
                        )
                        frame_h = int(
                            sprite_data.get("frameHeight", sprite_region.height)
                        )

                        if (
                            frame_x != 0
                            or frame_y != 0
                            or frame_w != sprite_region.width
                            or frame_h != sprite_region.height
                        ):
                            dest_x = max(0, -frame_x)
                            dest_y = max(0, -frame_y)
                            required_w = max(frame_w, dest_x + sprite_region.width)
                            required_h = max(frame_h, dest_y + sprite_region.height)

                            canvas = Image.new(
                                "RGBA", (required_w, required_h), (0, 0, 0, 0)
                            )
                            canvas.paste(sprite_region, (dest_x, dest_y))
                            sprite_region = canvas

                        sanitized_name = Utilities.sanitize_path_name(
                            sprite_data["name"]
                        )
                        frame_filename = f"{sanitized_name}{self.png_format}"

                        temp_frame_path = self.temp_dir / frame_filename
                        temp_frame_path.parent.mkdir(parents=True, exist_ok=True)
                        sprite_region.save(temp_frame_path, self.png_format_name)

                        frame_paths.append(str(temp_frame_path))

                    except Exception as e:
                        print(f"Error extracting frame {sprite_data['name']}: {e}")
                        continue

                    processed += 1
                    if processed % max(total_sprites // 20, 1) == 0:
                        self.progress_updated.emit(
                            processed,
                            total_sprites,
                            f"Extracting frame {processed}/{total_sprites}...",
                        )

                results[animation_name] = frame_paths

            atlas_image.close()

            self.progress_updated.emit(total_sprites, total_sprites, "Import complete")
            self.import_completed.emit(results)

        except Exception as e:
            self.import_failed.emit(str(e))


class GeneratorWorker(QThread):
    """Worker thread for atlas generation."""

    progress_updated = Signal(int, int, str)
    generation_completed = Signal(dict)
    generation_failed = Signal(str)

    def __init__(self, input_frames, output_path, atlas_settings, current_version):
        super().__init__()
        self.input_frames = input_frames
        self.output_path = output_path
        self.atlas_settings = atlas_settings
        self.animation_groups = None
        self.current_version = current_version
        self.output_format = "starling-xml"

    def run(self):
        """Execute atlas generation in background thread."""
        try:
            if not self.animation_groups:
                self.generation_failed.emit("No animation groups provided")
                return

            # Build generator options from atlas_settings
            options = GeneratorOptions(
                algorithm=self.atlas_settings.get("preferred_algorithm", "maxrects"),
                heuristic=self.atlas_settings.get("heuristic_hint"),
                max_width=self.atlas_settings.get("max_size", 4096),
                max_height=self.atlas_settings.get("max_size", 4096),
                padding=self.atlas_settings.get("padding", 2),
                power_of_two=self.atlas_settings.get("power_of_2", False),
                allow_rotation=self.atlas_settings.get("allow_rotation", False),
                allow_flip=self.atlas_settings.get("allow_vertical_flip", False),
                trim_sprites=self.atlas_settings.get("trim_sprites", False),
                image_format=self.atlas_settings.get("image_format", "PNG").lower(),
                export_format=self.output_format,
                compression_settings=self.atlas_settings.get("compression_settings"),
                texture_format=self.atlas_settings.get("texture_format"),
                texture_container=self.atlas_settings.get("texture_container", "dds"),
                generate_mipmaps=self.atlas_settings.get("generate_mipmaps", False),
            )

            # Handle manual sizing
            if self.atlas_settings.get("atlas_size_method") == "manual":
                options.max_width = self.atlas_settings.get("forced_width", 4096)
                options.max_height = self.atlas_settings.get("forced_height", 4096)

            # Create generator and set progress callback
            generator = AtlasGenerator()
            generator.set_progress_callback(self.emit_progress)

            # Run generation
            result = generator.generate(
                animation_groups=self.animation_groups,
                output_path=self.output_path,
                options=options,
            )

            if result.success:
                self.generation_completed.emit(result.to_dict())
            else:
                error_msg = (
                    "; ".join(result.errors) if result.errors else "Unknown error"
                )
                self.generation_failed.emit(error_msg)

        except Exception as e:
            self.generation_failed.emit(f"Generation error: {e}")

    def emit_progress(self, current, total, message=""):
        """Thread-safe progress emission."""
        self.progress_updated.emit(current, total, message)


class GenerateTabWidget(BaseTabWidget):
    """Widget containing all Generate tab functionality."""

    # Constants
    tr = translate

    def __init__(self, ui, parent=None):
        """Initialize the Generate tab as a UI controller.

        Args:
            ui: The compiled Qt Designer UI object to bind to.
            parent: Main window providing config and signals.
        """
        # Store ui reference before super().__init__ since we always use existing UI
        self._ui_ref = ui
        super().__init__(parent, use_existing_ui=True)
        self._init_state()
        self._setup_ui()
        self._configure_packer_combo()
        self._configure_atlas_type_combo()
        self.on_algorithm_changed(self.packer_method_combobox.currentText())
        self.on_atlas_size_method_changed(self.atlas_size_method_combobox.currentText())
        self._apply_generator_defaults()
        self._update_rotation_flip_trim_state()

    @property
    def main_app(self):
        """Alias for parent_app for backward compatibility."""
        return self.parent_app

    @property
    def ui(self):
        """Return the UI reference."""
        return self._ui_ref

    def _should_use_existing_ui(self, parent_app, use_existing_ui):
        """Return True unconditionally; this widget always uses existing UI.

        Args:
            parent_app: Ignored.
            use_existing_ui: Ignored.

        Returns:
            Always True.
        """
        return True

    def _init_state(self):
        """Initialize instance state before UI setup."""
        self.input_frames = []
        self._added_frame_paths = set()
        self.output_path = ""
        self.worker = None
        self._progress_window = None
        self.animation_groups = {}
        self.atlas_settings = {}

        self.APP_NAME = Utilities.APP_NAME
        self.ALL_FILES_FILTER = f"{self.tr('All files')} (*.*)"

        # Combined image formats - used for both input and output
        self.IMAGE_FORMATS = {
            ".png": "PNG",
            ".avif": "AVIF",
            ".bmp": "BMP",
            ".dds": "DDS",
            ".jpeg": "JPEG",
            ".jpg": "JPEG",
            ".ktx2": "KTX2",
            ".tga": "TGA",
            ".tif": "TIFF",
            ".tiff": "TIFF",
            ".webp": "WebP",
        }

        # Animated image formats that can be imported as frame sequences
        self.ANIMATED_IMPORT_FORMATS = {".gif", ".apng"}

        # Data formats for spritesheet metadata
        self.DATA_FORMATS = {".xml", ".XML", ".txt", ".TXT", ".json", ".JSON"}

        # Commonly used format constants
        self.PNG_FORMAT = ".png"
        self.PNG_FORMAT_NAME = "PNG"
        self.JPEG_FORMAT_NAME = "JPEG"

    def _setup_with_existing_ui(self):
        """Bind to UI elements and configure custom widgets."""
        self.bind_ui_elements()
        self.setup_custom_widgets()
        self.setup_connections()
        self._relax_generate_constraints()

    # ------------------------------------------------------------------
    # Designer layout overrides
    # ------------------------------------------------------------------

    def _relax_generate_constraints(self):
        """Override Designer size constraints so the Generate tab stays
        usable at smaller window sizes, matching the compact mockup layout.
        """
        ui = self.ui

        # Outer layout – tighter margins
        ui.main_layout.setContentsMargins(6, 6, 6, 6)
        ui.main_layout.setSpacing(6)

        # Splitter – non-collapsible, equal stretch
        ui.main_splitter.setChildrenCollapsible(False)

        # File panel – reduce inner margins
        ui.file_panel_layout.setContentsMargins(6, 6, 6, 6)
        ui.file_panel_layout.setSpacing(6)
        ui.input_layout.setContentsMargins(4, 8, 4, 4)
        ui.input_layout.setSpacing(4)

        # Settings panel – reduce inner margins
        ui.settings_panel_layout.setContentsMargins(6, 6, 6, 6)
        ui.settings_panel_layout.setSpacing(6)

        # Wrap settings panel in a scroll area for overflow handling
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setWidget(ui.settings_panel)
        ui.main_splitter.insertWidget(1, scroll)

        # Equal stretch factors after reparenting
        ui.main_splitter.setStretchFactor(0, 50)
        ui.main_splitter.setStretchFactor(1, 50)

        # Reduce animation tree minimum height
        self.animation_tree.setMinimumHeight(80)

        # Add padding to input buttons
        ui.input_buttons_layout.setSpacing(4)
        ui.input_buttons_layout.setContentsMargins(0, 2, 0, 2)

    def _build_ui(self):
        """Not supported; GenerateTabWidget requires existing UI.

        Raises:
            NotImplementedError: Always raised; standalone mode is not
                supported for this widget.
        """
        raise NotImplementedError(
            "GenerateTabWidget requires existing UI; standalone mode not supported."
        )

    @property
    def INPUT_FORMATS(self):
        """Backward compatibility property for input formats."""
        return set(self.IMAGE_FORMATS.keys())

    @property
    def OUTPUT_FORMATS(self):
        """Generate output formats list from IMAGE_FORMATS."""
        formats = []
        for ext, name in self.IMAGE_FORMATS.items():
            if ext.startswith("."):
                pattern = f"*{ext}"
                formats.append((name, pattern))
        return formats

    def get_image_file_filter(self):
        """Generate file filter string for image files.

        Includes both static image formats and animated formats
        (GIF, APNG) that can be imported as frame sequences.

        Returns:
            Filter string suitable for QFileDialog.
        """
        all_extensions = sorted(
            set(self.IMAGE_FORMATS.keys()) | self.ANIMATED_IMPORT_FORMATS
        )
        extensions = " ".join(f"*{ext}" for ext in all_extensions)
        image_filter = self.tr(FileFilters.IMAGE_FILES).format(extensions)
        return f"{image_filter};;{self.ALL_FILES_FILTER}"

    def get_atlas_image_file_filter(self):
        """Generate file filter string for atlas image files.

        Returns:
            Filter string suitable for QFileDialog.
        """
        # Create the extensions string from the IMAGE_FORMATS constant
        extensions = " ".join(f"*{ext}" for ext in sorted(self.IMAGE_FORMATS.keys()))
        atlas_filter = self.tr(FileFilters.ATLAS_IMAGE_FILES).format(extensions)
        return f"{atlas_filter};;{self.ALL_FILES_FILTER}"

    def get_data_file_filter(self):
        """Generate file filter string for spritesheet data files.

        Returns:
            Filter string suitable for QFileDialog.
        """
        extensions = " ".join(f"*{ext}" for ext in sorted(self.DATA_FORMATS))
        data_filter = self.tr(FileFilters.SPRITESHEET_DATA_FILES).format(extensions)
        return f"{data_filter};;{self.ALL_FILES_FILTER}"

    def get_xml_file_filter(self):
        """Generate file filter string for XML files.

        Provided for backward compatibility; returns the data file filter.

        Returns:
            Filter string suitable for QFileDialog.
        """
        return self.get_data_file_filter()

    def get_output_file_filter(self):
        """Generate file filter string for output formats.

        Returns:
            Filter string suitable for QFileDialog.
        """
        format_filters = []
        for format_name, pattern in self.OUTPUT_FORMATS:
            format_filters.append(f"{format_name} {self.tr('files')} ({pattern})")

        # Join all format filters and add the all files filter
        return ";;".join(format_filters + [self.ALL_FILES_FILTER])

    def bind_ui_elements(self):
        """Bind to UI elements from the compiled UI."""
        # File management — consolidate 3 loading buttons into a single
        # "Add" dropdown, keeping Clear All and New Animation separate.
        self.add_files_button = self.ui.add_files_button
        self.add_directory_button = self.ui.add_directory_button
        self.add_animation_button = self.ui.add_animation_button
        self.add_existing_atlas_button = self.ui.add_existing_atlas_button
        self.clear_frames_button = self.ui.clear_frames_button

        self._create_consolidated_add_button()

        # Frame info
        self.frame_info_label = self.ui.frame_info_label

        # Atlas settings
        self.atlas_size_method_combobox = self.ui.atlas_size_method_combobox
        self.atlas_size_spinbox_1 = self.ui.atlas_size_spinbox_1
        self.atlas_size_spinbox_2 = self.ui.atlas_size_spinbox_2
        self.atlas_size_label_1 = self.ui.atlas_size_label_1
        self.atlas_size_label_2 = self.ui.atlas_size_label_2
        self.padding_spin = self.ui.padding_spin
        self.power_of_2_check = self.ui.power_of_2_check
        self.allow_rotation_check = self.ui.allow_rotation_check
        self.allow_flip_check = self.ui.allow_flip_check

        # Output format
        self.image_format_combo = self.ui.image_format_combo
        self.atlas_type_combo = self.ui.atlas_type_combo
        self.packer_method_combobox = self.ui.packer_method_combobox

        # Generate button
        self.generate_button = self.ui.generate_button

        # Set tooltips for generator tab controls
        self._setup_generator_tooltips()

    def _create_consolidated_add_button(self):
        """Replace the three separate loading buttons with one 'Add' dropdown.

        Hides ``add_files_button``, ``add_directory_button``, and
        ``add_existing_atlas_button`` from the Designer layout and inserts
        a single ``QToolButton`` with a popup menu in their place.
        """
        layout = self.ui.input_buttons_layout

        # Hide the three individual loading buttons
        self.add_files_button.setVisible(False)
        self.add_directory_button.setVisible(False)
        self.add_existing_atlas_button.setVisible(False)

        # Build a dropdown menu with all three actions
        add_menu = QMenu(self.parent_app or self)
        self._add_job_action = add_menu.addAction(self.tr("Add Spritesheet Job"))
        add_menu.addSeparator()
        self._add_files_action = add_menu.addAction(self.tr("Add Files"))
        self._add_directory_action = add_menu.addAction(self.tr("Add Folder"))
        self._add_atlas_action = add_menu.addAction(self.tr("Add Existing Atlas"))

        # Set icons on menu actions for visual clarity
        try:
            from gui.theme_manager import icons as _icons

            self._add_job_action.setIcon(_icons.icon("grid"))
            self._add_files_action.setIcon(_icons.icon("file_plus"))
            self._add_directory_action.setIcon(_icons.icon("folder_plus"))
            self._add_atlas_action.setIcon(_icons.icon("image"))
        except Exception:
            pass

        # Tag actions so refresh_icons() keeps them in sync with the theme
        self._add_job_action.setProperty("iconKey", "grid")
        self._add_files_action.setProperty("iconKey", "file_plus")
        self._add_directory_action.setProperty("iconKey", "folder_plus")
        self._add_atlas_action.setProperty("iconKey", "image")

        self._add_button = QPushButton(self.tr("Add ▾"))
        self._add_button.setMenu(add_menu)
        self._add_button.setMinimumSize(QSize(0, 16))
        self._add_button.setProperty("iconKey", "plus")
        try:
            from gui.theme_manager import icons

            self._add_button.setIcon(icons.icon("plus"))
            self._add_button.setIconSize(QSize(16, 16))
        except Exception:
            pass
        # Clicking the button itself triggers "Add Files" (most common)
        self._add_button.clicked.connect(self.add_files)

        # Insert at position 0 (before the hidden buttons)
        layout.insertWidget(0, self._add_button)

    def _setup_generator_tooltips(self):
        """Set up tooltips for generator tab UI controls."""
        atlas_size_method_tooltip = self.tr(
            "Atlas sizing method:\n"
            "• Automatic: Detects smallest needed pixel size\n"
            "• MinMax: Limits size between min and max resolution\n"
            "• Manual: Enter exact resolution manually\n\n"
            "Automatic is recommended."
        )
        self.atlas_size_method_combobox.setToolTip(atlas_size_method_tooltip)
        self.atlas_size_label_1.setToolTip(atlas_size_method_tooltip)

        self.power_of_2_check.setToolTip(
            self.tr(
                "Force atlas dimensions to be powers of 2 (e.g., 512, 1024, 2048).\n\n"
                "Power-of-two sizes may enable faster loading, better compression,\n"
                "and full support for mipmaps and tiling.\n\n"
                "• Older GPUs and WebGL 1 often require Po2 textures\n"
                "• Modern GPUs and WebGL 2+ fully support non-Po2 textures\n\n"
                "Use Po2 when targeting older devices or using mipmapping,\n"
                "texture wrapping, or GPU compression."
            )
        )

        padding_tip = self.tr(
            "Pixels of padding between sprites.\n\n"
            "Padding helps prevent texture bleeding during rendering,\n"
            "especially when using texture filtering or mipmaps."
        )
        self.padding_spin.setToolTip(padding_tip)
        self.padding_spin.setStatusTip(
            self.tr(
                "Adds some extra whitespace between textures or sprites to ensure they won't overlap"
            )
        )

    def setup_custom_widgets(self):
        """Set up custom widgets that need to replace placeholders."""
        self.animation_tree = AnimationTreeWidget()
        self.animation_tree.setMinimumHeight(200)

        placeholder = self.ui.animation_tree_placeholder
        layout = placeholder.parent().layout()

        index = layout.indexOf(placeholder)

        layout.removeWidget(placeholder)
        placeholder.setParent(None)
        layout.insertWidget(index, self.animation_tree)

        self.jpeg_quality_spin = QSpinBox()
        self.jpeg_quality_spin.setRange(1, 100)
        self.jpeg_quality_spin.setValue(95)
        self.jpeg_quality_spin.setEnabled(False)

        # Create heuristic selection combo box and label
        self._setup_heuristic_combo()

        # Create trim sprites checkbox
        self._setup_trim_checkbox()

        # Create GPU texture compression controls
        self._setup_gpu_compression_controls()

    def setup_connections(self):
        """Set up signal-slot connections."""
        # File management — consolidated Add dropdown menu actions
        self._add_job_action.triggered.connect(self.add_job)
        self._add_files_action.triggered.connect(self.add_files)
        self._add_directory_action.triggered.connect(self.add_directory)
        self._add_atlas_action.triggered.connect(self.add_existing_atlas)
        self.add_animation_button.clicked.connect(self.add_animation_group)
        self.clear_frames_button.clicked.connect(self.clear_frames)

        # Animation tree signals
        self.animation_tree.animation_added.connect(self.on_animation_added)
        self.animation_tree.animation_removed.connect(self.on_animation_removed)
        self.animation_tree.frame_order_changed.connect(self.update_frame_info)

        # Settings
        self.atlas_size_method_combobox.currentTextChanged.connect(
            self.on_atlas_size_method_changed
        )
        self.image_format_combo.currentTextChanged.connect(self.on_format_change)
        self.atlas_type_combo.currentIndexChanged.connect(
            self._update_rotation_flip_trim_state
        )
        self.packer_method_combobox.currentTextChanged.connect(
            self.on_algorithm_changed
        )

        # Generation
        self.generate_button.clicked.connect(self.generate_atlas)

        # Job signals
        self.animation_tree.job_added.connect(lambda _: self.update_frame_info())
        self.animation_tree.job_removed.connect(lambda _: self.update_frame_info())

    def add_job(self):
        """Add a new atlas job (spritesheet)."""
        self.animation_tree.add_job()
        self.update_frame_info()
        self.update_generate_button_state()

    def add_files(self):
        """Add individual files to a new animation group.

        Animated images (GIF, APNG, animated WebP) are automatically
        split into individual frames before being added.
        """
        files, _ = QFileDialog.getOpenFileNames(
            self,
            self.tr(FileDialogTitles.SELECT_FRAMES),
            "",
            self.get_image_file_filter(),
        )

        if files:
            static, animated = self._separate_animated_files(files)
            if static:
                self.add_frames_to_new_animation(static)
            for anim_path in animated:
                extracted = self._extract_animated_frames(anim_path)
                if extracted:
                    self.add_frames_to_new_animation(
                        extracted, animation_name=Path(anim_path).stem
                    )

    def _glob_all_importable(self, folder):
        """Collect all importable files (static + animated) from a folder."""
        all_exts = set(self.IMAGE_FORMATS.keys()) | self.ANIMATED_IMPORT_FORMATS
        files = []
        for ext in all_exts:
            files.extend(folder.glob(f"*{ext}"))
            files.extend(folder.glob(f"*{ext.upper()}"))
        return files

    def add_directory(self):
        """Add all images from a directory to the frame list.

        Animated images (GIF, APNG, animated WebP) found in the
        directory or its subfolders are automatically split into
        individual frame sequences, each placed into its own
        animation group named after the source file.
        """
        directory = QFileDialog.getExistingDirectory(
            self, self.tr(FileDialogTitles.SELECT_FRAME_DIR), ""
        )

        if directory:
            directory_path = Path(directory)

            subfolders = [item for item in directory_path.iterdir() if item.is_dir()]

            if subfolders:
                animations_created = 0
                for subfolder in subfolders:
                    files = self._glob_all_importable(subfolder)

                    if files:
                        static, animated = self._separate_animated_files(
                            [str(f) for f in files]
                        )

                        if static:
                            animation_name = subfolder.name
                            new_animation_item = (
                                self.animation_tree.add_animation_group(animation_name)
                            )
                            actual_animation_name = new_animation_item.text(0)

                            for file_path in static:
                                if not self.is_frame_already_added(file_path):
                                    self.animation_tree.add_frame_to_animation(
                                        actual_animation_name, file_path
                                    )
                                    self.input_frames.append(file_path)
                                    self._added_frame_paths.add(file_path)

                            animations_created += 1

                        for anim_path in animated:
                            extracted = self._extract_animated_frames(anim_path)
                            if extracted:
                                self.add_frames_to_new_animation(
                                    extracted,
                                    animation_name=Path(anim_path).stem,
                                )
                                animations_created += 1

                if animations_created > 0:
                    QMessageBox.information(
                        self,
                        self.APP_NAME,
                        self.tr("Created {0} animation(s) from subfolders.").format(
                            animations_created
                        ),
                    )
                else:
                    QMessageBox.information(
                        self,
                        self.APP_NAME,
                        self.tr("No image files found in any subfolders."),
                    )
            else:
                files = self._glob_all_importable(directory_path)

                if files:
                    static, animated = self._separate_animated_files(
                        [str(f) for f in files]
                    )
                    if static:
                        self.add_frames_to_default_animation(static)
                    for anim_path in animated:
                        extracted = self._extract_animated_frames(anim_path)
                        if extracted:
                            self.add_frames_to_new_animation(
                                extracted, animation_name=Path(anim_path).stem
                            )
                else:
                    QMessageBox.information(
                        self,
                        self.APP_NAME,
                        self.tr("No image files found in the selected folder."),
                    )

            self.update_frame_info()
            self.update_generate_button_state()

    def add_animation_group(self):
        """Add a new animation group."""
        self.animation_tree.add_animation_group()
        self.update_frame_info()
        self.update_generate_button_state()

    def add_existing_atlas(self):
        """Add frames from an existing Sparrow/Starling atlas (image + data file)."""
        # First select the atlas image file (any supported format)
        atlas_file, _ = QFileDialog.getOpenFileName(
            self,
            self.tr(FileDialogTitles.SELECT_ATLAS_IMAGE),
            "",
            self.get_atlas_image_file_filter(),
        )

        if not atlas_file:
            return

        atlas_path = Path(atlas_file)
        atlas_directory = atlas_path.parent
        atlas_name = atlas_path.stem

        # Look for corresponding data file (XML, TXT, JSON)
        data_file = None
        possible_data_names = [f"{atlas_name}{ext}" for ext in self.DATA_FORMATS]

        for data_name in possible_data_names:
            data_path = atlas_directory / data_name
            if data_path.exists():
                data_file = str(data_path)
                break

        # If no data file found automatically, ask user to select one
        if not data_file:
            data_file, _ = QFileDialog.getOpenFileName(
                self,
                self.tr(FileDialogTitles.SELECT_ATLAS_DATA),
                str(atlas_directory),
                self.get_data_file_filter(),
            )

            if not data_file:
                QMessageBox.warning(
                    self,
                    self.APP_NAME,
                    self.tr(
                        "Both atlas image and data files are required to import an atlas."
                    ),
                )
                return

        # Validate prerequisites on main thread before spawning worker
        try:
            sprites_data = XmlParser.parse_xml_data(data_file)
        except Exception as e:
            QMessageBox.critical(
                self,
                self.APP_NAME,
                self.tr("Error importing atlas: {0}").format(str(e)),
            )
            return

        if not sprites_data:
            QMessageBox.warning(
                self,
                self.APP_NAME,
                self.tr("No frames found in the selected atlas data file."),
            )
            return

        if not PIL_AVAILABLE:
            QMessageBox.critical(
                self,
                self.APP_NAME,
                self.tr("PIL (Pillow) is required to extract frames from atlas files."),
            )
            return

        # If frames already exist, ask user how to handle the import
        self._import_target_job = None
        if self.animation_tree.get_total_frame_count() > 0:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setWindowTitle(self.APP_NAME)
            msg.setText(
                self.tr(
                    "An atlas is already loaded. How would you like to " "import '{0}'?"
                ).format(atlas_name)
            )
            combine_btn = msg.addButton(
                self.tr("Combine"), QMessageBox.ButtonRole.AcceptRole
            )
            new_job_btn = msg.addButton(
                self.tr("New Job"), QMessageBox.ButtonRole.ActionRole
            )
            msg.addButton(QMessageBox.StandardButton.Cancel)
            msg.exec()
            clicked = msg.clickedButton()
            if clicked == new_job_btn:
                self._import_target_job = self.animation_tree.add_job(atlas_name)
            elif clicked != combine_btn:
                return

        # Group frames by animation name on main thread (lightweight)
        use_smart_grouping = self.main_app.app_config.get("interface", {}).get(
            "smart_animation_grouping", True
        )

        if use_smart_grouping:
            name_groups = Utilities.group_names_by_animation(
                [s["name"] for s in sprites_data]
            )
            name_to_sprites: dict[str, list] = {}
            for sprite_data in sprites_data:
                name_to_sprites.setdefault(sprite_data["name"], []).append(sprite_data)

            animation_groups: dict[str, list] = {}
            for animation_name, frame_names in name_groups.items():
                group: list = []
                for fname in frame_names:
                    group.extend(name_to_sprites.get(fname, []))
                animation_groups[animation_name] = group
        else:
            animation_groups = {}
            for sprite_data in sprites_data:
                animation_name = self._extract_animation_name(sprite_data["name"])
                animation_groups.setdefault(animation_name, []).append(sprite_data)

        # Create temp dir and launch worker for heavy I/O
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix="atlas_frames_"))

        self._import_worker = AtlasImportWorker(
            atlas_file=atlas_file,
            sprites_data=sprites_data,
            animation_groups=animation_groups,
            temp_dir=temp_dir,
            png_format=self.PNG_FORMAT,
            png_format_name=self.PNG_FORMAT_NAME,
        )
        self._import_atlas_name = atlas_name
        self._import_temp_dir = temp_dir
        self._import_animation_groups = animation_groups

        self._import_worker.progress_updated.connect(self._on_import_progress)
        self._import_worker.import_completed.connect(self._on_import_completed)
        self._import_worker.import_failed.connect(self._on_import_failed)

        self.add_existing_atlas_button.setEnabled(False)
        self._add_atlas_action.setEnabled(False)

        # Open progress window for import
        self._import_progress_window = JobProgressWindow(
            self, title=self.tr("Importing Atlas")
        )
        self._import_progress_window.start()
        self._import_progress_window.show()

        self._import_worker.start()

    def _on_import_progress(self, current, total, message):
        """Handle progress updates from atlas import worker."""
        if self._import_progress_window is not None:
            self._import_progress_window.update_progress(current, total, message)

    def _on_import_completed(self, results):
        """Handle successful atlas import from worker thread."""
        target_job = getattr(self, "_import_target_job", None)
        total_frames_added = 0
        for animation_name, frame_paths in results.items():
            if not frame_paths:
                continue
            self.animation_tree.add_animation_group(animation_name, job_item=target_job)
            for frame_path in frame_paths:
                if not self.is_frame_already_added(frame_path):
                    self.animation_tree.add_frame_to_animation(
                        animation_name, frame_path, job_item=target_job
                    )
                    self.input_frames.append(frame_path)
                    self._added_frame_paths.add(frame_path)
                    total_frames_added += 1

        self.add_existing_atlas_button.setEnabled(True)
        self._add_atlas_action.setEnabled(True)

        if total_frames_added > 0:
            QMessageBox.information(
                self,
                self.APP_NAME,
                self.tr(
                    "Successfully imported {0} frames from atlas '{1}' into {2} animations."
                ).format(
                    total_frames_added,
                    self._import_atlas_name,
                    len(self._import_animation_groups),
                ),
            )

            if not hasattr(self, "temp_atlas_dirs"):
                self.temp_atlas_dirs = []
            self.temp_atlas_dirs.append(self._import_temp_dir)

            self.update_frame_info()
            self.update_generate_button_state()
        else:
            QMessageBox.information(
                self,
                self.APP_NAME,
                self.tr("All frames from this atlas were already added."),
            )
            import shutil

            shutil.rmtree(self._import_temp_dir, ignore_errors=True)

        if self._import_progress_window is not None:
            self._import_progress_window.finish(
                success=total_frames_added > 0,
                message=self.tr("Import completed."),
            )
        self._import_worker = None

    def _on_import_failed(self, error_msg):
        """Handle failed atlas import from worker thread."""
        self.add_existing_atlas_button.setEnabled(True)
        self._add_atlas_action.setEnabled(True)
        if self._import_progress_window is not None:
            self._import_progress_window.finish(success=False, message=str(error_msg))

        if self._import_temp_dir and self._import_temp_dir.exists():
            import shutil

            shutil.rmtree(self._import_temp_dir, ignore_errors=True)

        QMessageBox.critical(
            self,
            self.APP_NAME,
            self.tr("Error importing atlas: {0}").format(error_msg),
        )
        self._import_worker = None

    def _configure_packer_combo(self):
        """Populate the packer combo box with available algorithms from the registry."""
        # Get algorithms from the new packer registry
        algorithms = get_available_algorithms()

        # Add a few legacy/convenience options at the top
        algorithm_options = [
            ("Automatic (Best Fit)", "auto"),
        ]

        # Add registered algorithms
        for algo in algorithms:
            display_name = algo.get("display_name", algo["name"].title())
            algorithm_options.append((display_name, algo["name"]))

        self.packer_method_combobox.blockSignals(True)
        self.packer_method_combobox.clear()
        for label, key in algorithm_options:
            self.packer_method_combobox.addItem(label, key)
        self.packer_method_combobox.setCurrentIndex(0)
        self.packer_method_combobox.blockSignals(False)

    def _apply_generator_defaults(self):
        """Apply user's default generator settings from app config."""
        if not hasattr(self.main_app, "app_config"):
            return

        app_config = self.main_app.app_config
        defaults = app_config.get("generator_defaults", {})
        if not defaults:
            return

        # Mapping from internal format keys to display names
        export_format_display = {
            "starling-xml": "Sparrow/Starling XML",
            "json-hash": "JSON Hash",
            "json-array": "JSON Array",
            "aseprite": "Aseprite JSON",
            "texture-packer-xml": "TexturePacker XML",
            "spine": "Spine Atlas",
            "phaser3": "Phaser 3 JSON",
            "css": "CSS Spritesheet",
            "txt": "Plain Text",
            "plist": "Plist (Cocos2d)",
            "uikit-plist": "UIKit Plist",
            "godot": "Godot Atlas",
            "egret2d": "Egret2D JSON",
            "paper2d": "Paper2D (Unreal)",
            "unity": "Unity TexturePacker",
            "gdx": "libGDX Atlas",
        }

        algorithm_display = {
            "auto": "Automatic (Best Fit)",
            "maxrects": "MaxRects",
            "guillotine": "Guillotine",
            "shelf": "Shelf",
        }

        # Apply algorithm
        if "algorithm" in defaults:
            algo_key = defaults["algorithm"]
            display_name = algorithm_display.get(algo_key)
            if display_name:
                idx = self.packer_method_combobox.findText(display_name)
                if idx >= 0:
                    self.packer_method_combobox.setCurrentIndex(idx)

        # Apply export format
        if "export_format" in defaults:
            fmt_key = defaults["export_format"]
            display_name = export_format_display.get(fmt_key)
            if display_name:
                idx = self.atlas_type_combo.findText(display_name)
                if idx >= 0:
                    self.atlas_type_combo.setCurrentIndex(idx)

        # Apply image format
        if "image_format" in defaults:
            img_fmt = defaults["image_format"]
            idx = self.image_format_combo.findText(img_fmt)
            if idx >= 0:
                self.image_format_combo.setCurrentIndex(idx)

        # Apply max size - find value in atlas_size_spinbox_1
        if "max_size" in defaults:
            max_size = defaults["max_size"]
            self.atlas_size_spinbox_1.setValue(max_size)
            self.atlas_size_spinbox_2.setValue(max_size)

        # Apply padding
        if "padding" in defaults:
            self.padding_spin.setValue(defaults["padding"])

        # Apply checkboxes
        if "power_of_two" in defaults:
            self.power_of_2_check.setChecked(defaults["power_of_two"])

        if "allow_rotation" in defaults:
            self.allow_rotation_check.setChecked(defaults["allow_rotation"])

        if "allow_flip" in defaults:
            self.allow_flip_check.setChecked(defaults["allow_flip"])

        if "trim_sprites" in defaults:
            self.trim_sprites_check.setChecked(defaults["trim_sprites"])

        # Apply GPU texture compression defaults
        if "texture_format" in defaults:
            idx = self.gpu_format_combo.findData(defaults["texture_format"])
            if idx >= 0:
                self.gpu_format_combo.setCurrentIndex(idx)

        if "texture_container" in defaults:
            idx = self.gpu_container_combo.findData(defaults["texture_container"])
            if idx >= 0:
                self.gpu_container_combo.setCurrentIndex(idx)

        if "generate_mipmaps" in defaults:
            self.gpu_mipmap_check.setChecked(defaults["generate_mipmaps"])

    def _setup_heuristic_combo(self):
        """Create and insert the heuristic combo box and compression button."""
        # Create label and combo box for heuristic selection
        self.heuristic_label = QLabel(self.tr(Labels.HEURISTIC))
        self.heuristic_combobox = QComboBox()
        self.heuristic_combobox.setMinimumWidth(140)

        # Create compression settings button
        self.compression_settings_button = QPushButton(
            self.tr(ButtonLabels.COMPRESSION_SETTINGS)
        )
        self.compression_settings_button.setToolTip(
            self.tr(
                "Configure format-specific compression options for the output image"
            )
        )
        self.compression_settings_button.clicked.connect(self.show_compression_settings)

        # Find the packer_method_combobox's parent layout (should be a grid layout)
        packer_combo = self.packer_method_combobox
        parent_widget = packer_combo.parent()
        inserted = False
        if parent_widget and parent_widget.layout():
            layout = parent_widget.layout()
            # Try to find position of packer combo in grid layout
            from PySide6.QtWidgets import QGridLayout

            if isinstance(layout, QGridLayout):
                # Find where the packer combo is
                for row in range(layout.rowCount()):
                    for col in range(layout.columnCount()):
                        item = layout.itemAtPosition(row, col)
                        if item and item.widget() == packer_combo:
                            # Insert heuristic widgets in row 7 (after image_format at row 6)
                            layout.addWidget(self.heuristic_label, 7, 0)
                            layout.addWidget(self.heuristic_combobox, 7, 2)
                            # Insert compression button in row 8
                            layout.addWidget(self.compression_settings_button, 8, 2)
                            inserted = True
                            break
                    if inserted:
                        break

        if not inserted:
            # Fallback: just hide if we can't find the layout
            self.heuristic_label.setVisible(False)
            self.heuristic_combobox.setVisible(False)
            self.compression_settings_button.setVisible(False)

    def _get_heuristic_options(self, algorithm_key: str):
        """Return (label, key) tuples for the given algorithm's heuristics.

        Always includes "Auto (Best Result)" as the first option, which
        will try all heuristics and pick the one with best efficiency.
        """
        # Get heuristics from the packer registry
        from packers import get_heuristics_for_algorithm

        heuristics = get_heuristics_for_algorithm(algorithm_key)

        # Fallback for 'auto' algorithm - show maxrects heuristics
        if not heuristics and algorithm_key == "auto":
            heuristics = get_heuristics_for_algorithm("maxrects")

        if heuristics:
            # Start with Auto option, then add algorithm-specific heuristics
            options = [(self.tr("Auto (Best Result)"), "auto")]
            options.extend([(display, key) for key, display in heuristics])
            return options

        return []

    def _update_heuristic_combo(self, algorithm_key: str):
        """Update the heuristic combo box based on selected algorithm."""
        options = self._get_heuristic_options(algorithm_key)

        self.heuristic_combobox.blockSignals(True)
        self.heuristic_combobox.clear()

        if options:
            for label, key in options:
                self.heuristic_combobox.addItem(label, key)
            self.heuristic_combobox.setCurrentIndex(0)
            self.heuristic_combobox.setEnabled(True)
            self.heuristic_label.setEnabled(True)
            self.heuristic_combobox.setVisible(True)
            self.heuristic_label.setVisible(True)
        else:
            self.heuristic_combobox.addItem(self.tr("N/A"), "")
            self.heuristic_combobox.setEnabled(False)
            self.heuristic_label.setEnabled(False)
            # Keep visible but disabled for consistency
            self.heuristic_combobox.setVisible(True)
            self.heuristic_label.setVisible(True)

        self.heuristic_combobox.blockSignals(False)

    def _configure_atlas_type_combo(self):
        """Populate the atlas type combo box with available export formats."""
        # Define format options with display names and internal keys
        # Format: (Display Name, format_key, file_extension)
        format_options = [
            ("Sparrow/Starling XML", "starling-xml", ".xml"),
            ("JSON Hash", "json-hash", ".json"),
            ("JSON Array", "json-array", ".json"),
            ("Aseprite JSON", "aseprite", ".json"),
            ("TexturePacker XML", "texture-packer-xml", ".xml"),
            ("Spine Atlas", "spine", ".atlas"),
            ("Phaser 3 JSON", "phaser3", ".json"),
            ("CSS Spritesheet", "css", ".css"),
            ("Plain Text", "txt", ".txt"),
            ("Plist (Cocos2d)", "plist", ".plist"),
            ("UIKit Plist", "uikit-plist", ".plist"),
            ("Godot Atlas", "godot", ".tpsheet"),
            ("Egret2D JSON", "egret2d", ".json"),
            ("Paper2D (Unreal)", "paper2d", ".paper2dsprites"),
            ("Unity TexturePacker", "unity", ".tpsheet"),
            ("libGDX Atlas", "gdx", ".atlas"),
        ]

        self.atlas_type_combo.blockSignals(True)
        self.atlas_type_combo.clear()
        for display_name, format_key, extension in format_options:
            # Store both format_key and extension as tuple in userData
            self.atlas_type_combo.addItem(display_name, (format_key, extension))
        self.atlas_type_combo.setCurrentIndex(0)  # Default to Sparrow
        self.atlas_type_combo.blockSignals(False)

    def _get_selected_export_format(self):
        """Get the currently selected export format key and extension.

        Returns:
            tuple: (format_key, extension) for the selected format.
        """
        data = self.atlas_type_combo.currentData()
        if data:
            return data
        # Fallback to Sparrow if no data
        return ("starling-xml", ".xml")

    def _current_algorithm_key(self):
        data = self.packer_method_combobox.currentData()
        if data:
            return data
        text = self.packer_method_combobox.currentText().lower()
        if "max" in text:
            return "maxrects"
        if "guillotine" in text:
            return "guillotine"
        if "shelf" in text:
            return "shelf"
        if "skyline" in text:
            return "skyline"
        if "simple" in text:
            return "simple"
        # Default fallback to auto (best fit)
        return "auto"

    def on_algorithm_changed(self, _text):
        """Handle packer algorithm selection change."""
        key = self._current_algorithm_key()
        # Update heuristic combo box based on selected algorithm
        self._update_heuristic_combo(key)

    def _setup_gpu_compression_controls(self):
        """Create and insert GPU texture compression controls.

        Adds a texture format combo, container combo, and mipmap checkbox
        into the settings grid layout.  Visibility is gated by atlas type
        in ``_update_rotation_flip_trim_state``.
        """
        from utils.combo_options import (
            TEXTURE_COMPRESSION_OPTIONS,
            TEXTURE_CONTAINER_OPTIONS,
        )

        # Texture format combo
        self.gpu_format_label = QLabel(self.tr("GPU Compression (+)"))
        self.gpu_format_combo = QComboBox()
        self.gpu_format_combo.setMinimumWidth(140)
        for opt in TEXTURE_COMPRESSION_OPTIONS:
            self.gpu_format_combo.addItem(self.tr(opt.display_key), opt.internal)
        self.gpu_format_combo.setCurrentIndex(0)  # "None"
        self.gpu_format_combo.setToolTip(
            self.tr(
                "Export an additional GPU-compressed file (DDS / KTX2)\n"
                "alongside the regular atlas image.\n\n"
                "Requires the etcpak package (pip install etcpak) for\n"
                "BC1/BC3/BC7/ETC formats, or external CLI tools for ASTC/PVRTC.\n\n"
                "Select 'None' to only save the regular image."
            )
        )
        self.gpu_format_combo.currentIndexChanged.connect(self._on_gpu_format_changed)

        # Container combo
        self.gpu_container_label = QLabel(self.tr("Container"))
        self.gpu_container_combo = QComboBox()
        self.gpu_container_combo.setMinimumWidth(140)
        for opt in TEXTURE_CONTAINER_OPTIONS:
            self.gpu_container_combo.addItem(self.tr(opt.display_key), opt.internal)
        self.gpu_container_combo.setCurrentIndex(0)  # DDS
        self.gpu_container_combo.setToolTip(
            self.tr(
                "File container for the compressed texture.\n\n"
                "DDS — DirectDraw Surface, widely supported on desktop and consoles.\n"
                "KTX2 — Khronos Texture 2, supports all formats including mobile."
            )
        )

        # Mipmap checkbox
        self.gpu_mipmap_check = QCheckBox(self.tr("Generate Mipmaps"))
        self.gpu_mipmap_check.setChecked(False)
        self.gpu_mipmap_check.setToolTip(
            self.tr(
                "Generate a full mipmap chain for the atlas texture.\n\n"
                "Mipmaps improve rendering quality when the texture is\n"
                "displayed smaller than its native resolution and can\n"
                "reduce aliasing artifacts."
            )
        )

        # Insert into grid layout after the compression button (row 8)
        packer_combo = self.packer_method_combobox
        parent_widget = packer_combo.parent()
        inserted = False
        if parent_widget and parent_widget.layout():
            layout = parent_widget.layout()
            from PySide6.QtWidgets import QGridLayout

            if isinstance(layout, QGridLayout):
                layout.addWidget(self.gpu_format_label, 9, 0)
                layout.addWidget(self.gpu_format_combo, 9, 2)
                layout.addWidget(self.gpu_container_label, 10, 0)
                layout.addWidget(self.gpu_container_combo, 10, 2)
                layout.addWidget(self.gpu_mipmap_check, 11, 0, 1, 3)
                inserted = True

        if not inserted:
            self.gpu_format_label.setVisible(False)
            self.gpu_format_combo.setVisible(False)
            self.gpu_container_label.setVisible(False)
            self.gpu_container_combo.setVisible(False)
            self.gpu_mipmap_check.setVisible(False)

        # Start hidden — shown only for game-engine formats
        self._set_gpu_controls_visible(False)

    def _set_gpu_controls_visible(self, visible: bool):
        """Show or hide all GPU texture compression controls."""
        for widget in (
            self.gpu_format_label,
            self.gpu_format_combo,
            self.gpu_container_label,
            self.gpu_container_combo,
            self.gpu_mipmap_check,
        ):
            widget.setVisible(visible)
        # Container and mipmap only visible when a format is selected
        if visible:
            self._on_gpu_format_changed()

    def _on_gpu_format_changed(self, _index=None):
        """Show/hide container and mipmap controls based on format selection.

        When a GPU format is active the padding spinbox is locked to at
        least the format's block size so compressed blocks never straddle
        two different sprites.
        """
        from core.optimizer.constants import TextureFormat

        fmt = self.gpu_format_combo.currentData()
        has_format = fmt is not None and fmt != "none"
        self.gpu_container_label.setVisible(has_format)
        self.gpu_container_combo.setVisible(has_format)
        self.gpu_mipmap_check.setVisible(has_format)

        # Lock / unlock padding spinbox
        if has_format:
            block_size = TextureFormat(fmt).block_size
            # Remember the user's value so we can restore it later
            if getattr(self, "_padding_before_gpu", None) is None:
                self._padding_before_gpu = self.padding_spin.value()
            self.padding_spin.setMinimum(block_size)
            if self.padding_spin.value() < block_size:
                self.padding_spin.setValue(block_size)
            self.padding_spin.setReadOnly(True)
            self.padding_spin.setToolTip(
                self.tr(
                    "Padding is locked to {0} px (block size) while GPU "
                    "compression is active."
                ).format(block_size)
            )
        else:
            self.padding_spin.setMinimum(0)
            self.padding_spin.setReadOnly(False)
            if getattr(self, "_padding_before_gpu", None) is not None:
                self.padding_spin.setValue(self._padding_before_gpu)
                self._padding_before_gpu = None
            self.padding_spin.setToolTip(
                self.tr(
                    "Pixels of padding between sprites.\n\n"
                    "Padding helps prevent texture bleeding during rendering,\n"
                    "especially when using texture filtering or mipmaps."
                )
            )

        # Show a one-time disclaimer when a GPU format is first selected
        if has_format and not getattr(self, "_gpu_disclaimer_shown", False):
            self._gpu_disclaimer_shown = True
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setWindowTitle(self.tr("GPU Texture Compression"))
            msg.setTextFormat(Qt.TextFormat.RichText)
            msg.setText(
                self.tr(
                    "GPU texture compression produces an <b>additional</b> "
                    "hardware-specific file (DDS / KTX2) alongside the regular "
                    "atlas image.<br><br>"
                    "Only use this when you know your target engine or renderer "
                    "supports the chosen format. Incorrect settings can produce "
                    "files that appear corrupted or fail to load.<br><br>"
                    "Key points:<br>"
                    "• Padding will be automatically raised to at least the "
                    "block size (typically 4 px) to prevent cross-sprite "
                    "bleeding in compressed blocks.<br>"
                    "• DDS containers only support BC (DXT) formats; mobile "
                    "formats (ETC, ASTC, PVRTC) require KTX2.<br>"
                    "• ASTC and PVRTC need external CLI tools installed "
                    "separately (astcenc / PVRTexToolCLI)."
                ),
            )
            msg.exec()

    def _setup_trim_checkbox(self):
        """Create and insert the trim sprites checkbox."""
        self.trim_sprites_check = QCheckBox(self.tr(CheckBoxLabels.TRIM_SPRITES))
        self.trim_sprites_check.setChecked(False)
        self.trim_sprites_check.setToolTip(
            self.tr(
                "Trim transparent edges from sprites for tighter packing.\n\n"
                "When enabled, transparent pixels around each sprite are removed,\n"
                "and offset metadata is stored so the original position can be\n"
                "reconstructed during playback."
            )
        )

        # Find the allow_flip_check's parent layout and insert after it
        flip_check = self.allow_flip_check
        parent_widget = flip_check.parent()
        inserted = False
        if parent_widget and parent_widget.layout():
            layout = parent_widget.layout()
            from PySide6.QtWidgets import QGridLayout

            if isinstance(layout, QGridLayout):
                # Find where the flip check is
                for row in range(layout.rowCount()):
                    for col in range(layout.columnCount()):
                        item = layout.itemAtPosition(row, col)
                        if item and item.widget() == flip_check:
                            # Insert trim checkbox in next row
                            layout.addWidget(
                                self.trim_sprites_check, row + 1, col, 1, 1
                            )
                            inserted = True
                            break
                    if inserted:
                        break

        if not inserted:
            # Fallback: hide if we can't find the layout
            self.trim_sprites_check.setVisible(False)

    def _update_rotation_flip_trim_state(self):
        """Update rotation, flip, and trim checkboxes based on selected atlas format.

        Enables/disables checkboxes based on format support and shows warnings
        for non-standard features.  Also updates the animation tree's frame
        numbering convention to match the chosen format.
        """
        format_key, _ = self._get_selected_export_format()

        # Update tree numbering convention
        self.animation_tree.set_export_format(format_key)

        # Check format support for rotation
        supports_rotation = format_key in SUPPORTED_ROTATION_FORMATS
        self.allow_rotation_check.setEnabled(supports_rotation)
        if supports_rotation:
            self.allow_rotation_check.setToolTip(
                self.tr(
                    "Allow the packer to rotate sprites 90° clockwise for tighter packing."
                )
            )
        else:
            self.allow_rotation_check.setChecked(False)
            self.allow_rotation_check.setToolTip(
                self.tr("Rotation is not supported by {0} format.").format(format_key)
            )

        # Check format support for flip (only starling-xml with HaxeFlixel)
        supports_flip = format_key in SUPPORTED_FLIP_FORMATS
        self.allow_flip_check.setEnabled(supports_flip)
        if supports_flip:
            self.allow_flip_check.setToolTip(
                self.tr(
                    "Detect and deduplicate flipped sprite variants.\n\n"
                    "When enabled, sprites that are horizontally or vertically\n"
                    "flipped versions of other sprites are stored only once,\n"
                    "with flip metadata so engines can reconstruct them.\n\n"
                    "This can significantly reduce atlas size when your sprites\n"
                    "include mirrored variants (e.g., character facing left/right).\n\n"
                    "Warning: This is a non-standard extension only supported by HaxeFlixel.\n"
                    "Most Starling/Sparrow implementations will ignore flip attributes."
                )
            )
        else:
            self.allow_flip_check.setChecked(False)
            self.allow_flip_check.setToolTip(
                self.tr(
                    "Flip is not supported by {0} format.\n"
                    "Only Sparrow/Starling XML with HaxeFlixel supports flip attributes."
                ).format(format_key)
            )

        # Check format support for GPU texture compression
        supports_gpu = format_key in SUPPORTED_GPU_COMPRESSION_FORMATS
        if hasattr(self, "gpu_format_combo"):
            self._set_gpu_controls_visible(supports_gpu)
            if not supports_gpu:
                self.gpu_format_combo.setCurrentIndex(0)  # Reset to "None"

        # Check format support for trim (requires offset metadata storage)
        supports_trim = format_key in SUPPORTED_TRIM_FORMATS
        if hasattr(self, "trim_sprites_check"):
            self.trim_sprites_check.setEnabled(supports_trim)
            if supports_trim:
                self.trim_sprites_check.setToolTip(
                    self.tr(
                        "Trim transparent edges from sprites for tighter packing.\n\n"
                        "When enabled, transparent pixels around each sprite are removed,\n"
                        "and offset metadata is stored so the original position can be\n"
                        "reconstructed during playback."
                    )
                )
            else:
                self.trim_sprites_check.setChecked(False)
                self.trim_sprites_check.setToolTip(
                    self.tr(
                        "Trim is not supported by {0} format.\n\n"
                        "This format cannot store the offset metadata required\n"
                        "to reconstruct sprite positions after trimming."
                    ).format(format_key)
                )

    def _determine_algorithm_hint(self):
        return self._current_algorithm_key()

    def _get_selected_heuristic(self):
        """Get the currently selected heuristic key from the combo box."""
        if hasattr(self, "heuristic_combobox") and self.heuristic_combobox.isEnabled():
            return self.heuristic_combobox.currentData()
        return None

    def show_compression_settings(self):
        """Show the compression settings dialog for the current image format."""
        try:
            from gui.extractor.compression_settings_window import (
                CompressionSettingsWindow,
            )

            # Get current image format from the combo box
            current_format = self.image_format_combo.currentText().upper()

            # Get settings_manager and app_config from main app if available
            settings_manager = None
            app_config = None
            if hasattr(self.main_app, "settings_manager"):
                settings_manager = self.main_app.settings_manager
            if hasattr(self.main_app, "app_config"):
                app_config = self.main_app.app_config

            dialog = CompressionSettingsWindow(
                parent=self,
                settings_manager=settings_manager,
                app_config=app_config,
                current_format=current_format,
            )
            dialog.exec()

        except Exception as e:
            QMessageBox.warning(
                self,
                self.APP_NAME,
                self.tr("Could not open compression settings: {0}").format(str(e)),
            )

    def _get_compression_settings(self):
        """Get compression settings for the current image format.

        Returns a dict of format-specific compression options.
        """
        current_format = self.image_format_combo.currentText().upper()
        settings = {}

        # Try to get settings from app_config (compression settings are stored there)
        if hasattr(self.main_app, "app_config"):
            app_config = self.main_app.app_config
            if hasattr(app_config, "get_format_compression_settings"):
                settings = (
                    app_config.get_format_compression_settings(current_format) or {}
                )

        return settings

    def add_frames_to_default_animation(self, file_paths):
        """Add frame files to a default animation group."""
        # Create or use existing default animation
        default_animation = self.tr("New animation")

        # Add frames to the animation
        for file_path in file_paths:
            # Check if already in any animation
            if not self.is_frame_already_added(file_path):
                self.animation_tree.add_frame_to_animation(default_animation, file_path)
                self.input_frames.append(file_path)
                self._added_frame_paths.add(file_path)

        self.update_frame_info()
        self.update_generate_button_state()

    def add_frames_to_new_animation(self, file_paths, animation_name=None):
        """Add frame files to a new animation group."""
        # Create a new animation group
        new_animation_item = self.animation_tree.add_animation_group(animation_name)
        animation_name = new_animation_item.text(0)  # Get the actual name assigned

        # Add frames to the new animation
        for file_path in file_paths:
            # Check if already in any animation
            if not self.is_frame_already_added(file_path):
                self.animation_tree.add_frame_to_animation(animation_name, file_path)
                self.input_frames.append(file_path)
                self._added_frame_paths.add(file_path)

        self.update_frame_info()
        self.update_generate_button_state()

    def is_frame_already_added(self, file_path):
        """Check if a frame is already added to any animation."""
        return file_path in self._added_frame_paths

    def _is_animated_image(self, file_path):
        """Check whether a file is a multi-frame animated image."""
        ext = Path(file_path).suffix.lower()
        if ext in self.ANIMATED_IMPORT_FORMATS:
            return True
        # WebP can be either static or animated; peek at the frame count
        if ext == ".webp":
            try:
                with Image.open(file_path) as img:
                    return getattr(img, "n_frames", 1) > 1
            except Exception:
                return False
        return False

    def _separate_animated_files(self, file_paths):
        """Split a list of file paths into static images and animated images.

        Returns:
            Tuple of (static_paths, animated_paths).
        """
        static = []
        animated = []
        for fp in file_paths:
            if self._is_animated_image(fp):
                animated.append(fp)
            else:
                static.append(fp)
        return static, animated

    def _extract_animated_frames(self, file_path):
        """Extract individual frames from an animated image to temp PNGs.

        Each frame is saved as a numbered PNG file inside a temporary
        directory that is tracked for cleanup.

        Returns:
            List of extracted frame file paths, or empty list on failure.
        """
        import tempfile

        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="tatgf_anim_"))
            stem = Path(file_path).stem
            frame_paths = []

            with Image.open(file_path) as img:
                for idx, frame in enumerate(ImageSequence.Iterator(img)):
                    frame = frame.convert("RGBA")
                    out_path = temp_dir / f"{stem}_{idx:04d}.png"
                    frame.save(str(out_path), "PNG")
                    frame_paths.append(str(out_path))

            if frame_paths:
                if not hasattr(self, "temp_atlas_dirs"):
                    self.temp_atlas_dirs = []
                self.temp_atlas_dirs.append(temp_dir)
            else:
                import shutil

                shutil.rmtree(temp_dir, ignore_errors=True)

            return frame_paths

        except Exception as e:
            QMessageBox.warning(
                self,
                self.APP_NAME,
                self.tr("Could not extract frames from {0}: {1}").format(
                    Path(file_path).name, str(e)
                ),
            )
            return []

    def clear_frames(self):
        """Clear all frames from all animations."""
        # Clean up temporary atlas directories
        if hasattr(self, "temp_atlas_dirs"):
            import shutil

            for temp_dir in self.temp_atlas_dirs:
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception as e:
                    print(f"Error cleaning up temp directory {temp_dir}: {e}")
            self.temp_atlas_dirs.clear()

        self.input_frames.clear()
        self._added_frame_paths.clear()
        self.animation_tree.clear_all_animations()
        self.update_frame_info()
        self.update_generate_button_state()

    def on_animation_added(self, animation_name):
        """Handle new animation group added."""
        self.update_frame_info()
        self.update_generate_button_state()

    def on_animation_removed(self, animation_name):
        """Handle animation group removed."""
        self.update_frame_info()
        self.update_generate_button_state()

    def update_frame_info(self):
        """Update the frame info label."""
        total_frames = self.animation_tree.get_total_frame_count()
        animation_count = self.animation_tree.get_animation_count()
        job_count = self.animation_tree.get_job_count()

        if total_frames == 0:
            self.frame_info_label.setText(self.tr("No frames loaded"))
        elif job_count > 1:
            self.frame_info_label.setText(
                self.tr("{0} spritesheet(s) | {1} animation(s) | {2} frame(s)").format(
                    job_count, animation_count, total_frames
                )
            )
        else:
            self.frame_info_label.setText(
                self.tr("{0} animation(s), {1} frame(s) total").format(
                    animation_count, total_frames
                )
            )

    def update_generate_button_state(self):
        """Update the generate button enabled state and text."""
        has_frames = self.animation_tree.get_total_frame_count() > 0
        self.generate_button.setEnabled(has_frames)
        job_count = self.animation_tree.get_job_count()
        if job_count > 1:
            self.generate_button.setText(
                self.tr("Generate All ({0} jobs)").format(job_count)
            )
        else:
            self.generate_button.setText(self.tr("Generate"))

    def on_format_change(self, format_text):
        """Handle image format change."""
        self.jpeg_quality_spin.setEnabled(format_text == self.JPEG_FORMAT_NAME)

    def generate_atlas(self):
        """Start the atlas generation process.

        For a single job, behaves like before (save-file dialog).
        For multiple jobs, asks for an output directory and generates
        each spritesheet sequentially.
        """
        if self.animation_tree.get_total_frame_count() == 0:
            QMessageBox.warning(
                self,
                self.APP_NAME,
                self.tr("Please add frames before generating atlas."),
            )
            return

        jobs = self.animation_tree.get_jobs()
        if not jobs:
            return

        atlas_settings = self._build_atlas_settings()
        current_version = getattr(self.main_app, "current_version", "2.0.0")
        format_key, _format_ext = self._get_selected_export_format()

        # Build per-job animation_groups dicts
        job_queue = []
        for job_name, animations in jobs.items():
            animation_groups = {}
            for anim_name, frames in animations.items():
                sorted_frames = sorted(frames, key=lambda x: x["order"])
                animation_groups[anim_name] = [f["path"] for f in sorted_frames]
            if animation_groups:
                job_queue.append((job_name, animation_groups))

        if not job_queue:
            return

        if len(job_queue) == 1:
            # Single job – classic save-file dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                self.tr(FileDialogTitles.SAVE_ATLAS_AS),
                "",
                self.get_output_file_filter(),
            )
            if not file_path:
                return
            selected = Path(file_path)
            if selected.suffix:
                file_path = str(selected.with_suffix(""))
            job_queue[0] = (job_queue[0][0], job_queue[0][1])
            self._job_output_paths = {job_queue[0][0]: file_path}
        else:
            # Multiple jobs – pick output directory
            output_dir = QFileDialog.getExistingDirectory(
                self,
                self.tr("Select output folder for spritesheets"),
                "",
            )
            if not output_dir:
                return
            self._job_output_paths = {}
            for jname, _anims in job_queue:
                self._job_output_paths[jname] = str(Path(output_dir) / jname)

        # Stash state for sequential processing
        self._pending_jobs = list(job_queue)
        self._job_results = []
        self._atlas_settings = atlas_settings
        self._current_version = current_version
        self._output_format_key = format_key

        # Update UI
        self.generate_button.setEnabled(False)

        # Open dedicated progress window
        total_jobs = len(self._pending_jobs)
        self._progress_window = JobProgressWindow(
            self, title=self.tr("Generating Atlas")
        )
        self._progress_window.start(total_steps=total_jobs)
        self._progress_window.show()

        self._start_next_job()

    def _start_next_job(self):
        """Pop the next job from the queue and launch a GeneratorWorker."""
        if not self._pending_jobs:
            self._on_all_jobs_completed()
            return

        job_name, animation_groups = self._pending_jobs.pop(0)
        output_path = self._job_output_paths[job_name]
        total_jobs = len(self._job_results) + len(self._pending_jobs) + 1
        current_idx = len(self._job_results) + 1

        job_status = self.tr("Generating {0} ({1}/{2})...").format(
            job_name, current_idx, total_jobs
        )
        log_entry = self.tr("--- Job {0}/{1}: {2} ---").format(
            current_idx, total_jobs, job_name
        )

        if self._progress_window is not None:
            self._progress_window.update_progress(
                current_idx - 1, total_jobs, job_status
            )
            self._progress_window.append_log(log_entry)

        all_frames = [p for paths in animation_groups.values() for p in paths]

        self.worker = GeneratorWorker(
            all_frames, output_path, self._atlas_settings, self._current_version
        )
        self.worker.animation_groups = animation_groups
        self.worker.output_format = self._output_format_key
        self.worker.progress_updated.connect(self.on_progress_updated)
        self.worker.generation_completed.connect(self._on_job_completed)
        self.worker.generation_failed.connect(self._on_job_failed)
        self._current_job_name = job_name
        self.worker.start()

    def _build_atlas_settings(self):
        """Collect atlas settings from the current UI state."""
        method = self.atlas_size_method_combobox.currentText()
        algorithm_hint = self._determine_algorithm_hint()
        heuristic_hint = self._get_selected_heuristic()
        allow_rotation = self.allow_rotation_check.isChecked()
        allow_vertical_flip = self.allow_flip_check.isChecked()
        trim_sprites = (
            self.trim_sprites_check.isChecked()
            if hasattr(self, "trim_sprites_check")
            else False
        )
        image_format = self.image_format_combo.currentText().upper()

        base = {
            "padding": self.padding_spin.value(),
            "power_of_2": self.power_of_2_check.isChecked(),
            "allow_rotation": allow_rotation,
            "allow_vertical_flip": allow_vertical_flip,
            "trim_sprites": trim_sprites,
            "preferred_algorithm": algorithm_hint,
            "heuristic_hint": heuristic_hint,
            "image_format": image_format,
        }

        if method == "MinMax":
            base.update(
                {
                    "max_size": self.atlas_size_spinbox_2.value(),
                    "min_size": self.atlas_size_spinbox_1.value(),
                    "atlas_size_method": "minmax",
                }
            )
        elif method == "Manual":
            base.update(
                {
                    "max_size": max(
                        self.atlas_size_spinbox_1.value(),
                        self.atlas_size_spinbox_2.value(),
                    ),
                    "min_size": min(
                        self.atlas_size_spinbox_1.value(),
                        self.atlas_size_spinbox_2.value(),
                    ),
                    "atlas_size_method": "manual",
                    "forced_width": self.atlas_size_spinbox_1.value(),
                    "forced_height": self.atlas_size_spinbox_2.value(),
                }
            )
        else:
            base.update(
                {
                    "max_size": 4096,
                    "atlas_size_method": "automatic",
                }
            )

        base["compression_settings"] = self._get_compression_settings()

        if hasattr(self, "gpu_format_combo"):
            gpu_fmt = self.gpu_format_combo.currentData()
            if gpu_fmt and gpu_fmt != "none":
                base["texture_format"] = gpu_fmt
                base["texture_container"] = (
                    self.gpu_container_combo.currentData() or "dds"
                )
                base["generate_mipmaps"] = self.gpu_mipmap_check.isChecked()

        return base

    def _on_job_completed(self, results):
        """Handle a single job finishing; advance to the next."""
        self._job_results.append((self._current_job_name, results))
        log_entry = self.tr("Completed: {0} ({1}x{2}, {3} frames)").format(
            results.get("atlas_path", "?"),
            results.get("atlas_size", [0, 0])[0],
            results.get("atlas_size", [0, 0])[1],
            results.get("frames_count", 0),
        )
        if self._progress_window is not None:
            self._progress_window.append_log(log_entry)
        self._start_next_job()

    def _on_job_failed(self, error_message):
        """Handle a job failure; log and continue with remaining jobs."""
        self._job_results.append((self._current_job_name, {"error": error_message}))
        log_entry = self.tr("FAILED: {0} - {1}").format(
            self._current_job_name, error_message
        )
        if self._progress_window is not None:
            self._progress_window.append_log(log_entry)
        self._start_next_job()

    def _on_all_jobs_completed(self):
        """Called after every queued job has finished (or failed)."""
        self.generate_button.setEnabled(True)

        successes = [(name, r) for name, r in self._job_results if "error" not in r]
        failures = [(name, r) for name, r in self._job_results if "error" in r]

        if len(self._job_results) == 1 and successes:
            # Single-job: show the same detailed message as before
            name, results = successes[0]
            message = self.tr("Atlas generated successfully!") + "\n\n"
            message += self.tr("Atlas: {0}").format(results["atlas_path"]) + "\n"
            message += (
                self.tr("Size: {0}x{1}").format(
                    results["atlas_size"][0], results["atlas_size"][1]
                )
                + "\n"
            )
            message += self.tr("Frames: {0}").format(results["frames_count"]) + "\n"
            message += (
                self.tr("Efficiency: {0:.1f}%").format(results["efficiency"]) + "\n"
            )
            message += (
                self.tr("Format: {0}").format(self.atlas_type_combo.currentText())
                + "\n"
            )
            message += self.tr("Metadata files: {0}").format(
                len(results["metadata_files"])
            )
        elif successes or failures:
            # Multi-job summary
            lines = []
            if successes:
                lines.append(
                    self.tr("{0} spritesheet(s) generated successfully:").format(
                        len(successes)
                    )
                )
                for name, r in successes:
                    lines.append(f"  - {name}: {r.get('atlas_path', '?')}")
            if failures:
                lines.append(
                    self.tr("{0} spritesheet(s) failed:").format(len(failures))
                )
                for name, r in failures:
                    lines.append(f"  - {name}: {r.get('error', '?')}")
            message = "\n".join(lines)
        # Finalize the progress window
        if self._progress_window is not None:
            has_failures = any("error" in r for _, r in self._job_results)
            total_jobs = len(self._job_results)
            self._progress_window.update_progress(total_jobs, total_jobs)
            if has_failures:
                self._progress_window.finish(
                    success=False,
                    message=self.tr("Generation finished: {0} OK, {1} failed").format(
                        len(successes), len(failures)
                    ),
                )
            else:
                self._progress_window.finish(
                    success=True,
                    message=self.tr("Generation completed successfully!"),
                )

        # Show result dialogs after progress window is finalized
        if len(self._job_results) == 1 and successes:
            QMessageBox.information(self, self.APP_NAME, message)
        elif successes or failures:
            if failures:
                QMessageBox.warning(self, self.APP_NAME, message)
            else:
                QMessageBox.information(self, self.APP_NAME, message)

    def on_progress_updated(self, current, total, message):
        """Handle progress updates from the generator worker."""
        status = self.tr("Progress: {0}/{1} - {2}").format(current, total, message)
        if self._progress_window is not None:
            self._progress_window.update_progress(current, total, status)
            self._progress_window.append_log(message)

    def on_generation_completed(self, results):
        """Handle generation completion (legacy single-job path)."""
        self._on_job_completed(results)

    def on_generation_failed(self, error_message):
        """Handle generation failure (legacy single-job path)."""
        self._on_job_failed(error_message)

    def on_atlas_size_method_changed(self, method_text):
        """Handle atlas size method change."""
        if method_text == "Automatic":
            # Grey out spinboxes while automatic sizing is selected
            self.atlas_size_spinbox_1.setEnabled(False)
            self.atlas_size_spinbox_2.setEnabled(False)

            # Change labels
            self.atlas_size_label_1.setText(self.tr("Width"))
            self.atlas_size_label_2.setText(self.tr("Height"))

        elif method_text == "MinMax":
            # Enable spinboxes for min/max size input
            self.atlas_size_spinbox_1.setEnabled(True)
            self.atlas_size_spinbox_2.setEnabled(True)

            # Change labels
            self.atlas_size_label_1.setText(self.tr("Min size"))
            self.atlas_size_label_2.setText(self.tr("Max size"))

            # Set reasonable defaults if not already set
            if self.atlas_size_spinbox_1.value() == 0:
                self.atlas_size_spinbox_1.setValue(512)
            if self.atlas_size_spinbox_2.value() == 0:
                self.atlas_size_spinbox_2.setValue(2048)

        elif method_text == "Manual":
            # Enable spinboxes for manual width/height input
            self.atlas_size_spinbox_1.setEnabled(True)
            self.atlas_size_spinbox_2.setEnabled(True)

            # Change labels
            self.atlas_size_label_1.setText(self.tr("Width"))
            self.atlas_size_label_2.setText(self.tr("Height"))

            # Set reasonable defaults if not already set
            if self.atlas_size_spinbox_1.value() == 0:
                self.atlas_size_spinbox_1.setValue(1024)
            if self.atlas_size_spinbox_2.value() == 0:
                self.atlas_size_spinbox_2.setValue(1024)

    def __del__(self):
        """Cleanup temporary directories and worker thread when widget is destroyed."""
        if hasattr(self, "worker") and self.worker is not None:
            if self.worker.isRunning():
                self.worker.quit()
                self.worker.wait(3000)

        if hasattr(self, "temp_atlas_dirs"):
            import shutil

            for temp_dir in self.temp_atlas_dirs:
                try:
                    if temp_dir.exists():
                        shutil.rmtree(temp_dir, ignore_errors=True)
                except Exception:
                    pass  # Ignore errors during cleanup

    def _extract_animation_name(self, frame_name):
        """
        Extract animation name from frame name.

        Handles common patterns like:
        - "animName_0000" -> "animName"
        - "animName0001" -> "animName"
        - "animName 0" -> "animName"
        - "animName.0" -> "animName"
        - "animName-0" -> "animName"
        - "animName001" -> "animName"
        """
        import re

        # Remove file extension if present
        name = frame_name
        if "." in name:
            name = name.rsplit(".", 1)[0]

        # Pattern to match common frame numbering schemes
        # This regex captures everything before the frame number
        patterns = [
            r"^(.+?)_\d+$",  # name_0000
            r"^(.+?)\s+\d+$",  # name 0000
            r"^(.+?)\.\d+$",  # name.0000
            r"^(.+?)-\d+$",  # name-0000
            r"^(.+?)\d+$",  # name0000 (digits at the end)
        ]

        for pattern in patterns:
            match = re.match(pattern, name)
            if match:
                return match.group(1).strip()

        # If no pattern matches, return the original name (might be a single frame animation)
        return name
