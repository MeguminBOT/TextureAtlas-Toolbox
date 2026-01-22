#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dialog for overriding animation or spritesheet export settings.

Provides a modal dialog that allows users to customize export parameters
for individual animations or spritesheets, overriding global defaults.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QWidget,
    QPushButton,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QGridLayout,
    QSpinBox,
    QDoubleSpinBox,
    QCheckBox,
)
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtGui import QFont

from utils.utilities import Utilities
from utils.translation_manager import tr as translate
from utils.combo_options import (
    ANIMATION_FORMAT_OPTIONS_WITH_NONE,
    FRAME_FORMAT_OPTIONS,
    get_display_texts,
)
from utils.ui_constants import (
    Labels,
    GroupTitles,
    Placeholders,
    SpinBoxConfig,
    Tooltips,
    ButtonLabels,
    configure_spinbox,
)
from utils.duration_utils import (
    DURATION_FPS,
    DURATION_NATIVE,
    duration_to_milliseconds,
    get_duration_display_meta,
    load_duration_display_value,
    milliseconds_to_duration,
)
from utils.resampling import (
    DEFAULT_RESAMPLING_METHOD,
    RESAMPLING_DISPLAY_NAMES,
    get_resampling_index,
    get_resampling_name,
)


class OverrideSettingsWindow(QDialog):
    """Modal dialog for overriding animation or spritesheet export settings.

    Allows users to customize export parameters such as animation format, FPS,
    delay, scale, threshold, and frame indices for a specific animation or
    spritesheet, overriding the global defaults.

    Attributes:
        name: The name of the animation or spritesheet being configured.
        settings_type: Either "animation" or "spritesheet".
        settings_manager: Manager providing access to global and local settings.
        on_store_callback: Callback invoked with the new settings on accept.
        app: Optional reference to the main application for preview support.
        local_settings: Settings specific to this animation/spritesheet.
        settings: Merged settings (local overrides applied to globals).
        spritesheet_name: The parent spritesheet name.
        animation_name: The animation name, or None for spritesheets.
    """

    tr = translate

    UI_CONSTANTS_CONTEXT = "TextureAtlasToolboxApp"
    DURATION_UTILS_CONTEXT = "ExtractTabWidget"

    def trc(self, text: str) -> str:
        """Translate a string from ui_constants using its proper context."""
        return QCoreApplication.translate(self.UI_CONSTANTS_CONTEXT, text)

    def trd(self, text: str) -> str:
        """Translate a string from duration_utils using its proper context."""
        return QCoreApplication.translate(self.DURATION_UTILS_CONTEXT, text)

    def __init__(
        self, parent, name, settings_type, settings_manager, on_store_callback, app=None
    ):
        """Initialize the override settings dialog.

        Args:
            parent: Parent widget for the dialog.
            name: Name of the animation or spritesheet to configure.
            settings_type: Either "animation" or "spritesheet".
            settings_manager: Manager for accessing and storing settings.
            on_store_callback: Callback receiving the settings dict on accept.
            app: Optional main application reference for preview functionality.
        """
        super().__init__(parent)
        self.name = name
        self.settings_type = settings_type
        self.settings_manager = settings_manager
        self.on_store_callback = on_store_callback
        self.app = app

        self.duration_input_type = DURATION_FPS
        if self.app and hasattr(self.app, "app_config"):
            interface = self.app.app_config.get("interface", {})
            self.duration_input_type = interface.get(
                "duration_input_type", DURATION_FPS
            )

        title_prefix = "Animation" if settings_type == "animation" else "Spritesheet"
        self.setWindowTitle(
            self.tr("{prefix} Settings Override - {name}").format(
                prefix=title_prefix, name=name
            )
        )
        self.setModal(True)
        self.resize(500, 650)

        self.animation_format_combo = None
        self.fps_spinbox = None
        self.fps_label = None
        self.delay_spinbox = None
        self.period_spinbox = None
        self.scale_spinbox = None
        self.resampling_combo = None
        self.threshold_spinbox = None
        self.indices_edit = None
        self.frames_edit = None
        self.frame_format_combo = None
        self.frame_scale_spinbox = None
        self.filename_edit = None

        self.get_current_settings()

        self.setup_ui()
        self.load_current_values()

        # Connect to app's preview_settings_saved signal to auto-close
        # when user saves from preview window (avoids overwriting saved settings)
        if self.app and hasattr(self.app, "preview_settings_saved"):
            self.app.preview_settings_saved.connect(self._on_preview_settings_saved)

    def _on_preview_settings_saved(self, animation_name: str):
        """Handle preview settings being saved by closing this dialog.

        When the user saves settings from the animation preview window,
        this dialog should close without saving to avoid overwriting
        those settings with stale values.

        Args:
            animation_name: The full animation name that was saved.
        """
        if animation_name == self.name:
            self.reject()

    def get_current_settings(self):
        """Load current settings for the animation or spritesheet.

        Populates ``local_settings`` with any existing overrides and
        ``settings`` with the merged result of global and local values.
        """
        self.local_settings = {}

        if self.settings_type == "animation":
            if "/" in self.name:
                spritesheet_name = self.name.rsplit("/", 1)[0]
            else:
                spritesheet_name = self.name
            animation_name = self.name
            self.local_settings = self.settings_manager.animation_settings.get(
                animation_name, {}
            )
            self.spritesheet_name = spritesheet_name
            self.animation_name = animation_name
        else:
            spritesheet_name = self.name
            animation_name = None
            self.local_settings = self.settings_manager.spritesheet_settings.get(
                spritesheet_name, {}
            )
            self.spritesheet_name = spritesheet_name
            self.animation_name = None

        self.settings = self.settings_manager.get_settings(
            self.spritesheet_name, self.animation_name
        )

    def setup_ui(self):
        """Build and configure all UI components for the dialog."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        content_layout.setSpacing(15)

        mode_text = (
            self.tr("Animation Settings Override")
            if self.settings_type == "animation"
            else self.tr("Spritesheet Settings Override")
        )
        title_label = QLabel(mode_text)
        title_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("QLabel { color: #333333; }")
        content_layout.addWidget(title_label)

        general_group = self.create_general_section()
        content_layout.addWidget(general_group)

        anim_group = self.create_animation_section()
        content_layout.addWidget(anim_group)

        if self.settings_type == "spritesheet":
            frame_group = self.create_frame_section()
            content_layout.addWidget(frame_group)

        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        ok_btn = QPushButton(self.trc(ButtonLabels.OK))
        ok_btn.clicked.connect(self.store_input)
        ok_btn.setMinimumWidth(100)
        ok_btn.setDefault(True)
        button_layout.addWidget(ok_btn)

        if self.settings_type == "animation":
            preview_btn = QPushButton(self.trc(ButtonLabels.PREVIEW_ANIMATION))
            preview_btn.clicked.connect(self.handle_preview_click)
            preview_btn.setMinimumWidth(130)
            button_layout.addWidget(preview_btn)

        cancel_btn = QPushButton(self.trc(ButtonLabels.CANCEL))
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumWidth(100)
        button_layout.addWidget(cancel_btn)

        main_layout.addLayout(button_layout)

    def create_general_section(self):
        """Create the general settings section.

        Returns:
            QGroupBox containing name display and optional filename input.
        """
        group = QGroupBox(self.trc(GroupTitles.GENERAL_EXPORT_SETTINGS))
        layout = QGridLayout(group)

        row = 0

        layout.addWidget(QLabel(self.tr("Name:")), row, 0)
        name_label = QLabel(self.name)
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(200)
        layout.addWidget(name_label, row, 1)
        row += 1

        if self.settings_type == "animation" and "/" in self.name:
            layout.addWidget(QLabel(self.tr("Spritesheet:")), row, 0)
            spritesheet_label = QLabel(self.spritesheet_name)
            spritesheet_label.setWordWrap(True)
            spritesheet_label.setMaximumWidth(200)
            layout.addWidget(spritesheet_label, row, 1)
            row += 1

        if self.settings_type == "animation":
            layout.addWidget(QLabel(self.tr("Filename:")), row, 0)
            self.filename_edit = QLineEdit()
            self.filename_edit.setPlaceholderText(
                self.tr("Leave empty for auto-generated filename")
            )
            layout.addWidget(self.filename_edit, row, 1)
            row += 1

        return group

    def create_animation_section(self):
        """Create the animation export settings section.

        Returns:
            QGroupBox containing format, FPS, delay, scale, and related controls.
        """
        group = QGroupBox(self.trc(GroupTitles.ANIMATION_EXPORT_SETTINGS))
        layout = QGridLayout(group)

        row = 0

        layout.addWidget(QLabel(self.trc(Labels.ANIMATION_FORMAT)), row, 0)
        self.animation_format_combo = QComboBox()
        self.animation_format_combo.addItems(
            get_display_texts(ANIMATION_FORMAT_OPTIONS_WITH_NONE, self.trc)
        )
        self.animation_format_combo.currentTextChanged.connect(
            self.on_animation_format_change
        )
        layout.addWidget(self.animation_format_combo, row, 1)
        row += 1

        self.fps_label = QLabel(self._get_duration_label())
        layout.addWidget(self.fps_label, row, 0)
        self.fps_spinbox = QSpinBox()
        self._configure_fps_spinbox()
        layout.addWidget(self.fps_spinbox, row, 1)
        row += 1

        layout.addWidget(QLabel(self.trc(Labels.LOOP_DELAY)), row, 0)
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(0, 10000)
        self.delay_spinbox.setSuffix(" ms")
        layout.addWidget(self.delay_spinbox, row, 1)
        row += 1

        layout.addWidget(QLabel(self.trc(Labels.MINIMUM_PERIOD)), row, 0)
        self.period_spinbox = QSpinBox()
        self.period_spinbox.setRange(0, 10000)
        self.period_spinbox.setSuffix(" ms")
        layout.addWidget(self.period_spinbox, row, 1)
        row += 1

        layout.addWidget(QLabel(self.trc(Labels.SCALE)), row, 0)
        self.scale_spinbox = QDoubleSpinBox()
        self.scale_spinbox.setRange(-10.0, 10.0)
        self.scale_spinbox.setSingleStep(0.1)
        self.scale_spinbox.setDecimals(2)
        layout.addWidget(self.scale_spinbox, row, 1)
        row += 1

        layout.addWidget(QLabel(self.trc(Labels.RESAMPLING)), row, 0)
        self.resampling_combo = QComboBox()
        self.resampling_combo.addItems(RESAMPLING_DISPLAY_NAMES)
        self.resampling_combo.setToolTip(self.trc(Tooltips.RESAMPLING_ANIMATION))
        layout.addWidget(self.resampling_combo, row, 1)
        row += 1

        layout.addWidget(QLabel(self.trc(Labels.ALPHA_THRESHOLD)), row, 0)
        self.threshold_spinbox = QSpinBox()
        self.threshold_spinbox.setRange(0, 100)
        self.threshold_spinbox.setSingleStep(1)
        self.threshold_spinbox.setSuffix(" %")
        layout.addWidget(self.threshold_spinbox, row, 1)
        row += 1

        layout.addWidget(QLabel(self.tr("Indices (comma-separated):")), row, 0)
        self.indices_edit = QLineEdit()
        self.indices_edit.setPlaceholderText(
            self.tr("e.g., 0,1,2,3 or leave empty for all")
        )
        layout.addWidget(self.indices_edit, row, 1)
        row += 1

        self.var_delay_check = QCheckBox(self.trc(Labels.VARIABLE_DELAY))
        layout.addWidget(self.var_delay_check, row, 0, 1, 2)
        row += 1

        return group

    def create_frame_section(self):
        """Create the frame export settings section.

        Returns:
            QGroupBox containing frame format, scale, and selection controls.
        """
        group = QGroupBox(self.trc(GroupTitles.FRAME_EXPORT_SETTINGS))
        layout = QGridLayout(group)

        row = 0

        layout.addWidget(QLabel(self.trc(Labels.FRAME_SELECTION)), row, 0)
        self.frames_edit = QLineEdit()
        self.frames_edit.setPlaceholderText(self.trc(Placeholders.INDICES_HINT))
        layout.addWidget(self.frames_edit, row, 1)
        row += 1

        layout.addWidget(QLabel(self.trc(Labels.FRAME_FORMAT)), row, 0)
        self.frame_format_combo = QComboBox()
        self.frame_format_combo.addItems(get_display_texts(FRAME_FORMAT_OPTIONS))
        layout.addWidget(self.frame_format_combo, row, 1)
        row += 1

        layout.addWidget(QLabel(self.trc(Labels.FRAME_SCALE)), row, 0)
        self.frame_scale_spinbox = QDoubleSpinBox()
        configure_spinbox(
            self.frame_scale_spinbox,
            SpinBoxConfig.FRAME_SCALE_OVERRIDE,
            set_default=False,
        )
        layout.addWidget(self.frame_scale_spinbox, row, 1)
        row += 1

        return group

    def _get_animation_format(self) -> str:
        """Return the currently selected animation format in uppercase."""

        if self.animation_format_combo:
            return self.animation_format_combo.currentText().upper()
        return "GIF"

    def _get_duration_display_meta(self):
        """Return display metadata for the current duration configuration."""

        return get_duration_display_meta(
            self.duration_input_type, self._get_animation_format()
        )

    def _get_effective_duration_type(self):
        """Get the effective duration type, resolving 'native' to actual type."""

        return self._get_duration_display_meta().resolved_type

    def _get_duration_label(self):
        """Get the label text for the frame rate/duration spinbox.

        Returns:
            Translated label string based on duration_input_type.
        """
        display_meta = self._get_duration_display_meta()
        return self.trd(display_meta.label)

    def _configure_fps_spinbox(self):
        """Configure the FPS spinbox range, suffix, and tooltip.

        Uses the current duration display metadata to set appropriate
        limits and user-facing text for the spinbox.
        """
        display_meta = self._get_duration_display_meta()
        self.fps_spinbox.setRange(display_meta.min_value, display_meta.max_value)
        self.fps_spinbox.setSuffix(self.trd(display_meta.suffix))
        self.fps_spinbox.setToolTip(self.trd(display_meta.tooltip))

    def _duration_ms_to_display(self, duration_ms: int) -> int:
        """Convert a millisecond duration to the current display unit.

        Args:
            duration_ms: Frame duration in milliseconds.

        Returns:
            The equivalent value in the user's configured duration unit.
        """
        duration_type = self._get_effective_duration_type()
        anim_format = self._get_animation_format()
        return milliseconds_to_duration(
            duration_ms if duration_ms is not None else 42,
            duration_type,
            anim_format,
        )

    def _load_duration_display_value(
        self,
        duration_ms: int,
        stored_display_value: int | None,
        stored_display_type: str | None,
    ) -> int:
        """Load the display value, using stored value when types match.

        This enables lossless FPS round-trips by returning the originally
        stored display value when the target type matches.

        Args:
            duration_ms: The duration in milliseconds (fallback source).
            stored_display_value: The originally stored display value.
            stored_display_type: The type of the stored display value.

        Returns:
            The display value to show in the UI.
        """
        duration_type = self._get_effective_duration_type()
        anim_format = self._get_animation_format()
        return load_duration_display_value(
            duration_ms,
            stored_display_value,
            stored_display_type,
            duration_type,
            anim_format,
        )

    def _display_value_to_duration_ms(self, display_value: int) -> int:
        """Convert a display-unit value back to milliseconds.

        Args:
            display_value: Duration in the user's configured unit.

        Returns:
            The equivalent value in milliseconds.
        """
        duration_type = self._get_effective_duration_type()
        anim_format = self._get_animation_format()
        return duration_to_milliseconds(
            max(1, display_value),
            duration_type,
            anim_format,
        )

    @staticmethod
    def _legacy_fps_to_ms(fps_value) -> int:
        """Convert a legacy FPS value to milliseconds.

        Used when migrating old settings that stored frame rate as FPS
        instead of the canonical millisecond duration.

        Args:
            fps_value: Frames-per-second value (numeric or string).

        Returns:
            Frame duration in milliseconds.
        """
        try:
            fps_numeric = float(fps_value)
        except (TypeError, ValueError):
            fps_numeric = 24.0
        fps_numeric = max(1.0, fps_numeric)
        return max(1, round(1000 / fps_numeric))

    def load_current_values(self):
        """Populate UI controls with current settings values."""

        if self.filename_edit:
            self.filename_edit.setText(self.local_settings.get("filename", ""))

        anim_format = self.local_settings.get("animation_format", "")
        valid_formats = get_display_texts(ANIMATION_FORMAT_OPTIONS_WITH_NONE, self.trc)
        if anim_format and anim_format in valid_formats:
            self.animation_format_combo.setCurrentText(anim_format)
        else:
            self.animation_format_combo.setCurrentText(
                self.settings.get("animation_format", "GIF")
            )

        duration_ms = self.local_settings.get("duration")
        stored_display_value = self.local_settings.get("duration_display_value")
        stored_display_type = self.local_settings.get("duration_display_type")

        if duration_ms is None and "fps" in self.local_settings:
            fps_value = self.local_settings.pop("fps", None)
            duration_ms = self._legacy_fps_to_ms(fps_value)
            self.local_settings["duration"] = duration_ms

        if duration_ms is None:
            duration_ms = self.settings.get("duration")
            stored_display_value = self.settings.get("duration_display_value")
            stored_display_type = self.settings.get("duration_display_type")
            if duration_ms is None and "fps" in self.settings:
                duration_ms = self._legacy_fps_to_ms(self.settings.get("fps"))

        if duration_ms is None:
            duration_ms = 42

        display_value = self._load_duration_display_value(
            int(duration_ms), stored_display_value, stored_display_type
        )
        self.fps_spinbox.setValue(display_value)
        self.delay_spinbox.setValue(
            self.local_settings.get("delay", self.settings.get("delay", 250))
        )
        self.period_spinbox.setValue(
            self.local_settings.get("period", self.settings.get("period", 0))
        )
        self.scale_spinbox.setValue(
            self.local_settings.get("scale", self.settings.get("scale", 1.0))
        )

        resampling_method = self.local_settings.get(
            "resampling_method",
            self.settings.get("resampling_method", DEFAULT_RESAMPLING_METHOD),
        )
        self.resampling_combo.setCurrentIndex(get_resampling_index(resampling_method))

        threshold_value = self.local_settings.get(
            "threshold", self.settings.get("threshold", 0.5)
        )
        self.threshold_spinbox.setValue(int(threshold_value * 100))

        indices = self.local_settings.get("indices", self.settings.get("indices", []))
        if indices:
            self.indices_edit.setText(",".join(map(str, indices)))

        self.var_delay_check.setChecked(
            self.local_settings.get("var_delay", self.settings.get("var_delay", False))
        )

        if self.settings_type == "spritesheet":
            frames = self.local_settings.get("frames", self.settings.get("frames", []))
            if frames:
                self.frames_edit.setText(",".join(map(str, frames)))

            frame_format = self.local_settings.get(
                "frame_format", self.settings.get("frame_format", "PNG")
            )
            self.frame_format_combo.setCurrentText(frame_format)

            self.frame_scale_spinbox.setValue(
                self.local_settings.get(
                    "frame_scale", self.settings.get("frame_scale", 1.0)
                )
            )

        self.on_animation_format_change()

    def on_animation_format_change(self):
        """Update control states based on selected animation format.

        Disables animation-specific controls when format is "None" and
        updates the filename placeholder to reflect current settings.
        Also updates the FPS spinbox label and range when in native mode.
        """
        format_value = self.animation_format_combo.currentText()
        is_animation = format_value not in ["None", ""]

        self.fps_spinbox.setEnabled(is_animation)
        self.delay_spinbox.setEnabled(is_animation)
        self.period_spinbox.setEnabled(is_animation)
        self.var_delay_check.setEnabled(is_animation)

        if self.duration_input_type == DURATION_NATIVE:
            current_ms = self._display_value_to_duration_ms(self.fps_spinbox.value())
            if self.fps_label:
                self.fps_label.setText(self._get_duration_label())
            self._configure_fps_spinbox()
            self.fps_spinbox.blockSignals(True)
            self.fps_spinbox.setValue(self._duration_ms_to_display(current_ms))
            self.fps_spinbox.blockSignals(False)

        if self.filename_edit and self.filename_edit.text() == "":
            if self.settings_type == "animation" and "/" in self.name:
                filename = Utilities.format_filename(
                    self.settings.get("prefix"),
                    self.spritesheet_name,
                    self.name.rsplit("/", 1)[1],
                    self.settings.get("filename_format"),
                    self.settings.get("replace_rules"),
                    self.settings.get("suffix"),
                )
                self.filename_edit.setPlaceholderText(filename)

    def handle_preview_click(self):
        """Open the animation preview window for the current animation.

        Selects the appropriate spritesheet and animation in the main UI,
        then triggers the preview. Only available for animation settings.
        """
        if self.app and hasattr(self.app, "show_animation_preview_window"):
            try:
                if self.settings_type != "animation":
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.information(
                        self,
                        self.tr("Info"),
                        self.tr(
                            "Preview is only available for animations, not spritesheets."
                        ),
                    )
                    return

                if "/" not in self.name:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.warning(
                        self,
                        self.tr("Preview Error"),
                        self.tr("Invalid animation name format."),
                    )
                    return

                spritesheet_name, animation_name = self.name.rsplit("/", 1)

                spritesheet_found = False
                listbox_png = self.app.extract_tab_widget.listbox_png
                for i in range(listbox_png.count()):
                    item = listbox_png.item(i)
                    if item and item.text() == spritesheet_name:
                        listbox_png.setCurrentItem(item)
                        spritesheet_found = True
                        break

                if not spritesheet_found:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.warning(
                        self,
                        self.tr("Preview Error"),
                        self.tr("Could not find spritesheet: {name}").format(
                            name=spritesheet_name
                        ),
                    )
                    return

                self.app.extract_tab_widget.populate_animation_list(spritesheet_name)

                animation_found = False
                listbox_data = self.app.extract_tab_widget.listbox_data
                for i in range(listbox_data.count()):
                    item = listbox_data.item(i)
                    if item and item.text() == animation_name:
                        listbox_data.setCurrentItem(item)
                        animation_found = True
                        break

                if not animation_found:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.warning(
                        self,
                        self.tr("Preview Error"),
                        self.tr("Could not find animation: {name}").format(
                            name=animation_name
                        ),
                    )
                    return

                self.app.extract_tab_widget.preview_selected_animation()

            except Exception as e:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self,
                    self.tr("Preview Error"),
                    self.tr("Could not open preview: {error}").format(error=str(e)),
                )

    def store_input(self):
        """Validate inputs, build settings dict, and invoke the callback.

        Collects all user-entered values, validates indices and frames as
        comma-separated integers, calls the on_store_callback with the
        resulting settings, and closes the dialog on success.
        """
        settings = {}

        # General settings
        if self.filename_edit:
            filename = self.filename_edit.text().strip()
            if filename:
                settings["filename"] = filename

        anim_format = self.animation_format_combo.currentText()
        if anim_format != "None":
            settings["animation_format"] = anim_format

        display_value = self.fps_spinbox.value()
        duration_ms = self._display_value_to_duration_ms(display_value)
        settings["duration"] = duration_ms
        settings["duration_display_value"] = display_value
        settings["duration_display_type"] = self._get_effective_duration_type()
        settings["delay"] = self.delay_spinbox.value()
        settings["period"] = self.period_spinbox.value()
        settings["scale"] = self.scale_spinbox.value()
        settings["resampling_method"] = get_resampling_name(
            self.resampling_combo.currentIndex()
        )
        settings["threshold"] = self.threshold_spinbox.value() / 100.0
        settings["var_delay"] = self.var_delay_check.isChecked()

        indices_text = self.indices_edit.text().strip()
        if indices_text:
            try:
                indices = [int(x.strip()) for x in indices_text.split(",") if x.strip()]
                settings["indices"] = indices
            except ValueError:
                from PySide6.QtWidgets import QMessageBox

                QMessageBox.warning(
                    self, "Invalid Input", "Indices must be comma-separated integers."
                )
                return

        if self.settings_type == "spritesheet":
            frames_text = self.frames_edit.text().strip()
            if frames_text:
                try:
                    frames = [
                        int(x.strip()) for x in frames_text.split(",") if x.strip()
                    ]
                    settings["frames"] = frames
                except ValueError:
                    from PySide6.QtWidgets import QMessageBox

                    QMessageBox.warning(
                        self,
                        "Invalid Input",
                        "Frames must be comma-separated integers.",
                    )
                    return

            settings["frame_format"] = self.frame_format_combo.currentText()
            settings["frame_scale"] = self.frame_scale_spinbox.value()

        self.on_store_callback(settings)
        self.accept()
