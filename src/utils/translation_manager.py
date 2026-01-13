"""Application translation and localization management.

Provides dynamic discovery of available translations, language switching,
and quality metadata for each supported language. Translation files use
Qt's `.qm` (compiled) and `.ts` (source) formats located in
``src/translations/`` with the naming scheme ``app_{language_code}``.

Quality levels:
    native: Approved by multiple native speakers.
    reviewed: Checked by at least one reviewer.
    unreviewed: Human translated but not yet reviewed.
    machine: Auto-generated machine translation.
    unknown: Fallback when quality is not specified.

To add a new language, add its metadata to the ``LANGUAGE_METADATA`` dict
at module level and create the corresponding translation files.
"""

from pathlib import Path
from PySide6.QtCore import QTranslator, QLocale, QCoreApplication
from PySide6.QtWidgets import QApplication


# Single source of truth for all known language metadata.
# Languages are included in get_available_languages() if their .ts/.qm file exists.
# English is always available (no file required).
LANGUAGE_METADATA: dict[str, dict[str, str]] = {
    "en": {"name": "English", "english_name": "English", "quality": "native"},
    "de_de": {"name": "Deutsch", "english_name": "German", "quality": "machine"},
    "es_es": {"name": "Español", "english_name": "Spanish", "quality": "machine"},
    "fr_fr": {"name": "Français", "english_name": "French", "quality": "machine"},
    "id": {"name": "Indonesia", "english_name": "Indonesian", "quality": "machine"},
    "it_it": {"name": "Italiano", "english_name": "Italian", "quality": "machine"},
    "ko_kr": {"name": "한국어", "english_name": "Korean", "quality": "machine"},
    "nl_nl": {"name": "Nederlands", "english_name": "Dutch", "quality": "machine"},
    "pl_pl": {"name": "Polski", "english_name": "Polish", "quality": "machine"},
    "pt_br": {
        "name": "Português (Brasil)",
        "english_name": "Portuguese (Brazil)",
        "quality": "unknown",
    },
    "sv": {"name": "Svenska", "english_name": "Swedish", "quality": "machine"},
    "zh_cn": {
        "name": "简体中文",
        "english_name": "Chinese (Simplified)",
        "quality": "machine",
    },
    # Uncomment to enable when translation files are added:
    # "ar": {"name": "العربية", "english_name": "Arabic", "quality": "machine"},
    # "bg": {"name": "Български", "english_name": "Bulgarian", "quality": "machine"},
    # "cs": {"name": "Čeština", "english_name": "Czech", "quality": "machine"},
    # "da": {"name": "Dansk", "english_name": "Danish", "quality": "machine"},
    # "el": {"name": "Ελληνικά", "english_name": "Greek", "quality": "machine"},
    # "fi": {"name": "Suomi", "english_name": "Finnish", "quality": "machine"},
    # "he": {"name": "עברית", "english_name": "Hebrew", "quality": "machine"},
    # "hi": {"name": "हिन्दी", "english_name": "Hindi", "quality": "machine"},
    # "hu": {"name": "Magyar", "english_name": "Hungarian", "quality": "machine"},
    # "ja": {"name": "日本語", "english_name": "Japanese", "quality": "machine"},
    # "pt": {"name": "Português", "english_name": "Portuguese", "quality": "machine"},
    # "ro": {"name": "Română", "english_name": "Romanian", "quality": "machine"},
    # "ru": {"name": "Русский", "english_name": "Russian", "quality": "machine"},
    # "th": {"name": "ไทย", "english_name": "Thai", "quality": "machine"},
    # "tr": {"name": "Türkçe", "english_name": "Turkish", "quality": "machine"},
    # "uk": {"name": "Українська", "english_name": "Ukrainian", "quality": "machine"},
    # "vi": {"name": "Tiếng Việt", "english_name": "Vietnamese", "quality": "machine"},
    # "zh_tw": {"name": "繁體中文", "english_name": "Chinese (Traditional)", "quality": "machine"},
}


class TranslationManager:
    """Manages application translations and language switching.

    Handles discovery of available translation files, loading translations,
    and providing metadata about translation quality.

    Attributes:
        app_instance: The QApplication instance for translator installation.
        current_translator: Currently installed QTranslator, if any.
        current_locale: Language code of the active translation.
        translations_dir: Path to the translations directory.
    """

    def __init__(self, app_instance: QApplication | None = None) -> None:
        """Initialize the translation manager.

        Args:
            app_instance: QApplication to install translators on. Defaults to
                the current application instance.
        """
        self.app_instance = app_instance or QApplication.instance()
        self.current_translator: QTranslator | None = None
        self.current_locale: str | None = None
        self.translations_dir = Path(__file__).parent.parent / "translations"
        self._available_languages_cache: dict[str, dict] | None = None

    def _has_translation_file(self, lang_code: str) -> bool:
        """Check if a translation file exists for the given language code."""
        ts_file = self.translations_dir / f"app_{lang_code}.ts"
        qm_file = self.translations_dir / f"app_{lang_code}.qm"
        return ts_file.exists() or qm_file.exists()

    def get_available_languages(self) -> dict[str, dict]:
        """Return languages that have translation files available.

        Results are cached since translation files don't change at runtime.

        Returns:
            Dictionary mapping language codes to info dicts containing:
            ``name`` (native display name), ``english_name``, and ``quality``.
        """
        if self._available_languages_cache is not None:
            return self._available_languages_cache

        available: dict[str, dict] = {}
        for lang_code, info in LANGUAGE_METADATA.items():
            # English is always available; others need a translation file.
            if lang_code == "en" or self._has_translation_file(lang_code):
                available[lang_code] = info

        self._available_languages_cache = available
        return available

    def invalidate_cache(self) -> None:
        """Clear the cached available languages (e.g., after adding new files)."""
        self._available_languages_cache = None

    def get_system_locale(self) -> str:
        """Get the system's default locale as a language code.

        Converts Qt locale format (e.g., ``en_US``) to the application's
        format (e.g., ``en``). Chinese locales preserve region codes to
        distinguish Simplified (``zh_CN``) from Traditional (``zh_TW``).

        Returns:
            Language code suitable for :meth:`load_translation`.
        """

        system_locale = QLocale.system()
        language_code = system_locale.name()

        if "_" in language_code:
            base_lang = language_code.split("_")[0]
            if base_lang == "zh":
                if "CN" in language_code or "Hans" in language_code:
                    return "zh_CN"
                elif "TW" in language_code or "Hant" in language_code:
                    return "zh_TW"
            return base_lang

        return language_code

    def load_translation(self, language_code: str) -> bool:
        """Load translation for the specified language code.

        Removes any existing translator, then installs the new one. The
        ``auto`` code triggers system locale detection with English fallback.
        Prefers compiled ``.qm`` files over source ``.ts`` files.

        Args:
            language_code: Language code (e.g., ``en``, ``es``, ``auto``).

        Returns:
            True if translation loaded successfully, False otherwise.
        """

        if self.current_translator:
            self.app_instance.removeTranslator(self.current_translator)
            self.current_translator = None

        if language_code == "auto":
            detected_language = self.get_system_locale()
            available_languages = self.get_available_languages()
            if detected_language in available_languages:
                language_code = detected_language
            else:
                language_code = "en"

        if language_code == "en":
            self.current_locale = "en"
            return True

        translator = QTranslator()

        qm_file = self.translations_dir / f"app_{language_code}.qm"
        if qm_file.exists():
            if translator.load(str(qm_file)):
                self.app_instance.installTranslator(translator)
                self.current_translator = translator
                self.current_locale = language_code
                return True

        ts_file = self.translations_dir / f"app_{language_code}.ts"
        if ts_file.exists():
            if translator.load(str(ts_file)):
                self.app_instance.installTranslator(translator)
                self.current_translator = translator
                self.current_locale = language_code
                return True

        print(f"Warning: Could not load translation for language '{language_code}'")
        return False

    def get_current_language(self) -> str:
        """Return the currently active language code, defaulting to ``en``."""

        return self.current_locale or "en"

    def refresh_ui(self, main_window) -> None:
        """Refresh the UI to apply the current translation.

        Call after changing languages. Invokes ``retranslateUi`` on the
        window's UI and emits the ``language_changed`` signal if present.

        Args:
            main_window: The main application window instance.
        """

        if hasattr(main_window, "ui"):
            main_window.ui.retranslateUi(main_window)

        if hasattr(main_window, "language_changed"):
            main_window.language_changed.emit(self.current_locale or "en")

    def _get_lang_info(self, language_code: str) -> dict | None:
        """Return cached language info dict, or None if unavailable."""
        return self.get_available_languages().get(language_code)

    def is_machine_translated(self, language_code: str) -> bool:
        """Check if a language uses machine translation.

        Args:
            language_code: The language code to check.

        Returns:
            True if the language quality is ``machine``, False otherwise.
        """
        info = self._get_lang_info(language_code)
        return info.get("quality") == "machine" if info else False

    def get_quality_level(self, language_code: str) -> str:
        """Get the quality level of a translation.

        Args:
            language_code: The language code to check.

        Returns:
            Quality level (``native``, ``reviewed``, ``unreviewed``, ``machine``)
            or ``unknown`` if not found.
        """
        info = self._get_lang_info(language_code)
        return info.get("quality", "unknown") if info else "unknown"

    def get_english_name(self, language_code: str) -> str:
        """Get the English name of a language.

        Args:
            language_code: The language code to look up.

        Returns:
            English name of the language, or ``Unknown`` if not found.
        """
        info = self._get_lang_info(language_code)
        return info.get("english_name", "Unknown") if info else "Unknown"

    def get_display_name(self, language_code: str, show_english: bool = False) -> str:
        """Get the display name for a language.

        Args:
            language_code: The language code to look up.
            show_english: If True, append the English name (e.g.,
                ``Deutsch / German``).

        Returns:
            Display name in the native script, optionally with English.
        """
        info = self._get_lang_info(language_code)
        if not info:
            return "Unknown"

        native_name = info.get("name", "Unknown")
        if show_english and language_code != "en":
            english_name = info.get("english_name", "Unknown")
            return self._format_language_display_name(native_name, english_name)
        return native_name

    def _format_language_display_name(self, native_name: str, english_name: str) -> str:
        """Format a bilingual language display name.

        Combines native and English names with a slash separator, unless
        the English name is empty, identical, or already present in the
        native name.

        Args:
            native_name: Language name in its native script.
            english_name: Language name in English.

        Returns:
            Formatted display name (e.g., ``Français / French``).
        """

        if not english_name or english_name == native_name:
            return native_name

        if english_name.lower() in native_name.lower():
            return native_name

        return f"{native_name} / {english_name}"

    def get_machine_translation_disclaimer(self) -> tuple[str, str]:
        """Get the machine translation disclaimer in the current language.

        Returns:
            A tuple (title, message) for displaying a disclaimer dialog.
        """

        title = QCoreApplication.translate(
            "MachineTranslationDisclaimer", "Machine Translation Notice"
        )
        message = QCoreApplication.translate(
            "MachineTranslationDisclaimer",
            "This language was automatically translated and may contain inaccuracies. "
            "If you would like to contribute better translations, please visit our GitHub repository.",
        )
        return title, message


DEFAULT_TRANSLATION_CONTEXT = "TextureAtlasExtractorApp"

_translation_manager: TranslationManager | None = None


def get_translation_manager() -> TranslationManager:
    """Return the global translation manager instance, creating it if needed."""

    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager()
    return _translation_manager


class _Translator:
    """Callable descriptor that binds translation context per class instance."""

    def __call__(self, text: str, context: str | None = None) -> str:
        """Translate text using the application's current locale."""

        translation_context = (
            context if context is not None else DEFAULT_TRANSLATION_CONTEXT
        )
        return QCoreApplication.translate(translation_context, text)

    def _resolve_context(self, owner: type | None) -> str:
        if owner is None:
            return DEFAULT_TRANSLATION_CONTEXT
        custom_context = getattr(owner, "TRANSLATION_CONTEXT", None)
        if isinstance(custom_context, str) and custom_context:
            return custom_context
        return owner.__name__

    def __get__(self, instance, owner):
        context = self._resolve_context(owner)

        def bound(text: str, context_override: str | None = None) -> str:
            translation_context = context_override or context
            return self(text, context=translation_context)

        return bound


tr = _Translator()
