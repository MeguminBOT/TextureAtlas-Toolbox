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

Languages are auto-discovered from translation files. To customize display
names or quality levels, add entries to ``LANGUAGE_METADATA``.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtCore import QTranslator, QLocale, QCoreApplication
from PySide6.QtWidgets import QApplication


# Optional metadata for known languages (display names and quality).
# Languages without entries here will use auto-generated names from QLocale.
# English (en_us) is always available as the base language.
LANGUAGE_METADATA: dict[str, dict[str, str]] = {
    "en_us": {"name": "English", "english_name": "English", "quality": "native"},
    "da_dk": {"name": "Dansk", "english_name": "Danish", "quality": "machine"},
    "de_de": {"name": "Deutsch", "english_name": "German", "quality": "machine"},
    "es_es": {"name": "Español", "english_name": "Spanish", "quality": "machine"},
    "fr_fr": {"name": "Français", "english_name": "French", "quality": "reviewed"},
    "it_it": {"name": "Italiano", "english_name": "Italian", "quality": "unreviewed"},
    "ja_jp": {"name": "日本語", "english_name": "Japanese", "quality": "machine"},
    "ko_kr": {"name": "한국어", "english_name": "Korean", "quality": "machine"},
    "nl_nl": {"name": "Nederlands", "english_name": "Dutch", "quality": "machine"},
    "pl_pl": {"name": "Polski", "english_name": "Polish", "quality": "machine"},
    "pt_br": {
        "name": "Português (Brasil)",
        "english_name": "Portuguese (Brazil)",
        "quality": "machine",
    },
    "sv_se": {"name": "Svenska", "english_name": "Swedish", "quality": "machine"},
    "zh_cn": {
        "name": "简体中文",
        "english_name": "Chinese (Simplified)",
        "quality": "machine",
    },
    "zh_tw": {
        "name": "繁體中文",
        "english_name": "Chinese (Traditional)",
        "quality": "machine",
    },
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

    def _discover_translation_files(self) -> set[str]:
        """Scan the translations directory for available language codes.

        Looks for files matching ``app_*.ts`` or ``app_*.qm`` and extracts
        the language code from the filename.

        Returns:
            Set of discovered language codes (e.g., ``{"de_de", "fr_fr"}``).
        """
        if not self.translations_dir.exists():
            return set()

        lang_codes: set[str] = set()
        for pattern in ("app_*.ts", "app_*.qm"):
            for path in self.translations_dir.glob(pattern):
                # Extract language code from "app_{lang_code}.ts/.qm"
                stem = path.stem  # e.g., "app_de_de"
                if stem.startswith("app_"):
                    lang_code = stem[4:]  # Remove "app_" prefix
                    if lang_code:
                        lang_codes.add(lang_code)
        return lang_codes

    def _get_language_info_from_locale(self, lang_code: str) -> dict[str, str]:
        """Generate language info from QLocale for unknown language codes.

        Args:
            lang_code: Language code (e.g., ``de_de``, ``fr``).

        Returns:
            Dictionary with ``name``, ``english_name``, and ``quality`` keys.
        """
        # Convert underscore format to Qt format (e.g., de_de -> de_DE)
        qt_locale_name = lang_code
        if "_" in lang_code:
            parts = lang_code.split("_", 1)
            qt_locale_name = f"{parts[0]}_{parts[1].upper()}"

        locale = QLocale(qt_locale_name)

        # Get native language name (in its own script)
        native_name = locale.nativeLanguageName()
        if not native_name:
            native_name = lang_code.upper()

        # Get English name
        english_name = QLocale.languageToString(locale.language())
        if not english_name or english_name == "C":
            english_name = lang_code.upper()

        # Add territory for regional variants
        # PySide6 < 6.1 uses Country enum; 6.1+ uses Territory
        territory = locale.territory()
        any_territory = getattr(QLocale, "Territory", getattr(QLocale, "Country", None))
        any_territory_value = (
            getattr(any_territory, "AnyTerritory", None) if any_territory else None
        )
        if any_territory_value is None:
            any_territory_value = (
                getattr(any_territory, "AnyCountry", None) if any_territory else None
            )
        if any_territory_value is not None and territory != any_territory_value:
            territory_name = QLocale.territoryToString(territory)
            if territory_name and territory_name not in english_name:
                english_name = f"{english_name} ({territory_name})"

        return {
            "name": native_name,
            "english_name": english_name,
            "quality": "unknown",
        }

    def _has_translation_file(self, lang_code: str) -> bool:
        """Check if a translation file exists for the given language code."""
        ts_file = self.translations_dir / f"app_{lang_code}.ts"
        qm_file = self.translations_dir / f"app_{lang_code}.qm"
        return ts_file.exists() or qm_file.exists()

    def _calculate_completeness(self, lang_code: str) -> int:
        """Calculate translation completeness percentage for a language.

        Parses the ``.ts`` file and counts translated vs total messages.
        A message is considered translated if it has non-empty translation
        text and is not marked as ``type="unfinished"`` or ``type="vanished"``.

        Args:
            lang_code: Language code to check.

        Returns:
            Completeness percentage (0-100), or 100 for English, or 0 if
            the file cannot be parsed.
        """
        if lang_code in ("en", "en_us"):
            return 100

        ts_file = self.translations_dir / f"app_{lang_code}.ts"
        if not ts_file.exists():
            return 0

        try:
            tree = ET.parse(ts_file)
            root = tree.getroot()

            total = 0
            translated = 0

            for message in root.iter("message"):
                source = message.find("source")
                translation = message.find("translation")

                # Skip messages without source text
                if source is None or not source.text:
                    continue

                total += 1

                if translation is not None:
                    # Check for unfinished/vanished/obsolete markers
                    trans_type = translation.get("type", "")
                    if trans_type in ("unfinished", "vanished", "obsolete"):
                        continue
                    # Check if translation has actual content
                    if translation.text and translation.text.strip():
                        translated += 1

            if total == 0:
                return 100  # No strings to translate

            return round((translated / total) * 100)

        except (ET.ParseError, OSError):
            return 0

    def get_available_languages(self) -> dict[str, dict]:
        """Return languages that have translation files available.

        Uses a two-pass approach:
        1. First, include all languages from ``LANGUAGE_METADATA`` that have
           corresponding translation files (ensures consistent metadata).
        2. Then, auto-discover any additional languages from translation files
           not listed in metadata (generates display names from QLocale).

        Results are cached since translation files don't change at runtime.

        Returns:
            Dictionary mapping language codes to info dicts containing:
            ``name`` (native display name), ``english_name``, and ``quality``.
        """
        if self._available_languages_cache is not None:
            return self._available_languages_cache

        available: dict[str, dict] = {}

        # Pass 1: Add all languages from LANGUAGE_METADATA that have files
        for lang_code, info in LANGUAGE_METADATA.items():
            # English (en_us) is always available; others need a translation file
            # Skip 'en' since 'en_us' is the canonical English entry
            if lang_code == "en":
                continue
            if lang_code == "en_us" or self._has_translation_file(lang_code):
                lang_info = dict(info)  # Copy to avoid mutating original
                lang_info["completeness"] = self._calculate_completeness(lang_code)
                available[lang_code] = lang_info

        # Pass 2: Auto-discover languages not in LANGUAGE_METADATA
        discovered_codes = self._discover_translation_files()
        for lang_code in discovered_codes:
            # Skip if already added from metadata or is an "en" variant
            if lang_code in available or lang_code in ("en", "en_us"):
                continue
            # Generate metadata from QLocale for unknown languages
            lang_info = self._get_language_info_from_locale(lang_code)
            lang_info["completeness"] = self._calculate_completeness(lang_code)
            available[lang_code] = lang_info

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
        language_code = system_locale.name().lower()

        if "_" in language_code:
            base_lang, region = language_code.split("_", 1)
            if base_lang == "zh":
                if "cn" in region or "hans" in region:
                    return "zh_cn"
                elif "tw" in region or "hant" in region:
                    return "zh_tw"
            return f"{base_lang}_{region}"

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
                language_code = "en_us"

        if language_code == "en_us":
            self.current_locale = "en_us"
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
        """Return the currently active language code, defaulting to ``en_us``."""

        return self.current_locale or "en_us"

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

    def get_completeness(self, language_code: str) -> int:
        """Get the translation completeness percentage.

        Args:
            language_code: The language code to check.

        Returns:
            Completeness percentage (0-100).
        """
        info = self._get_lang_info(language_code)
        return info.get("completeness", 0) if info else 0

    def get_english_name(self, language_code: str) -> str:
        """Get the English name of a language.

        Args:
            language_code: The language code to look up.

        Returns:
            English name of the language, or ``Unknown`` if not found.
        """
        info = self._get_lang_info(language_code)
        return info.get("english_name", "Unknown") if info else "Unknown"

    def get_display_name(
        self,
        language_code: str,
        show_english: bool = False,
        show_completeness: bool = False,
    ) -> str:
        """Get the display name for a language.

        Args:
            language_code: The language code to look up.
            show_english: If True, append the English name (e.g.,
                ``Deutsch / German``).
            show_completeness: If True, append completeness percentage
                (e.g., ``Deutsch (85%)``).

        Returns:
            Display name in the native script, optionally with English
            and/or completeness percentage.
        """
        info = self._get_lang_info(language_code)
        if not info:
            return "Unknown"

        native_name = info.get("name", "Unknown")
        if show_english and language_code != "en_us":
            english_name = info.get("english_name", "Unknown")
            display = self._format_language_display_name(native_name, english_name)
        else:
            display = native_name

        if show_completeness:
            completeness = info.get("completeness", 100)
            # Only show percentage for non-100% to reduce clutter
            if completeness < 100:
                display = f"{display} ({completeness}%)"

        return display

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

    # Pre-translated machine translation disclaimers for each language
    # These are used when the .ts file translations aren't available
    DISCLAIMER_TRANSLATIONS: dict[str, str] = {
        "de_de": "Diese Sprache wurde automatisch übersetzt und kann Ungenauigkeiten enthalten. "
        "Wenn Sie bessere Übersetzungen beitragen möchten, besuchen Sie bitte unser GitHub-Repository.",
        "es_es": "Este idioma fue traducido automáticamente y puede contener inexactitudes. "
        "Si desea contribuir con mejores traducciones, visite nuestro repositorio de GitHub.",
        "fr_fr": "Cette langue a été traduite automatiquement et peut contenir des inexactitudes. "
        "Si vous souhaitez contribuer à de meilleures traductions, veuillez visiter notre dépôt GitHub.",
        "it_it": "Questa lingua è stata tradotta automaticamente e potrebbe contenere imprecisioni. "
        "Se desideri contribuire con traduzioni migliori, visita il nostro repository GitHub.",
        "ja_jp": "この言語は自動翻訳されており、不正確な部分が含まれている可能性があります。"
        "より良い翻訳に貢献したい場合は、GitHubリポジトリをご覧ください。",
        "ko_kr": "이 언어는 자동 번역되었으며 부정확한 내용이 포함될 수 있습니다. "
        "더 나은 번역에 기여하고 싶으시다면 GitHub 저장소를 방문해 주세요.",
        "nl_nl": "Deze taal is automatisch vertaald en kan onnauwkeurigheden bevatten. "
        "Als u betere vertalingen wilt bijdragen, bezoek dan onze GitHub-repository.",
        "pl_pl": "Ten język został przetłumaczony automatycznie i może zawierać nieścisłości. "
        "Jeśli chcesz przyczynić się do lepszych tłumaczeń, odwiedź nasze repozytorium GitHub.",
        "pt_br": "Este idioma foi traduzido automaticamente e pode conter imprecisões. "
        "Se você gostaria de contribuir com melhores traduções, visite nosso repositório no GitHub.",
        "sv_se": "Detta språk har översatts automatiskt och kan innehålla felaktigheter. "
        "Om du vill bidra med bättre översättningar, besök vårt GitHub-arkiv.",
        "zh_cn": "此语言为自动翻译，可能包含不准确之处。"
        "如果您想贡献更好的翻译，请访问我们的 GitHub 仓库。",
        "da_dk": "Dette sprog er automatisk oversat og kan indeholde unøjagtigheder. "
        "Hvis du gerne vil bidrage med bedre oversættelser, besøg venligst vores GitHub-repository.",
    }

    def get_machine_translation_disclaimer(
        self, target_language_code: str | None = None
    ) -> tuple[str, str, str]:
        """Get the machine translation disclaimer in both target language and English.

        Uses pre-translated disclaimers for machine-translated languages to ensure
        users can preview the translation quality.

        Args:
            target_language_code: Optional language code to get disclaimer in.
                If None, uses current active translation.

        Returns:
            A tuple (title, target_message, english_message) for displaying
            a disclaimer dialog with both language versions.
        """
        english_title = "Machine Translation Notice"
        english_message = (
            "This language was automatically translated and may contain inaccuracies. "
            "If you would like to contribute better translations, please visit our GitHub repository."
        )

        # Use pre-translated disclaimer only for machine-translated languages
        target_message = english_message
        if target_language_code and target_language_code != "en_us":
            if self.is_machine_translated(target_language_code):
                target_message = self.DISCLAIMER_TRANSLATIONS.get(
                    target_language_code, english_message
                )

        return english_title, target_message, english_message


APP_TRANSLATION_CONTEXT = "TextureAtlasToolboxApp"
"""Single unified translation context for all application strings.

All translatable strings should use this context to ensure consistent
lookups in Qt's translation system. This matches the context used in
ui_constants.py QT_TRANSLATE_NOOP markers.
"""

# Legacy alias for backwards compatibility
DEFAULT_TRANSLATION_CONTEXT = APP_TRANSLATION_CONTEXT

_translation_manager: TranslationManager | None = None


def get_translation_manager() -> TranslationManager:
    """Return the global translation manager instance, creating it if needed."""

    global _translation_manager
    if _translation_manager is None:
        _translation_manager = TranslationManager()
    return _translation_manager


class _BoundTranslator:
    """Bound translator that uses a specific context (class name) for lookups."""

    __slots__ = ("_context",)

    def __init__(self, context: str):
        self._context = context

    def __call__(self, text: str) -> str:
        """Translate text, falling back to unified context if not found."""
        # Try class-specific context first (matches existing .ts files)
        result = QCoreApplication.translate(self._context, text)
        if result != text:
            return result
        # Fall back to unified app context (for ui_constants.py strings)
        return QCoreApplication.translate(APP_TRANSLATION_CONTEXT, text)


class _UnifiedTranslator:
    """Translation callable that works both as a function and class attribute.

    This descriptor-enabled callable provides a unified translation interface:
    - As a function: tr("text") - uses unified context
    - As a class attribute: self.tr("text") - uses class name as context with fallback

    When accessed via self.tr(), uses the owning class name as context first,
    then falls back to the unified context. This ensures compatibility with
    existing .ts translation files that use class-name-based contexts.
    """

    def __call__(self, text: str) -> str:
        """Translate text using the unified application context."""
        return QCoreApplication.translate(APP_TRANSLATION_CONTEXT, text)

    def __get__(self, instance, owner):
        """Return a bound translator that uses the class name as context."""
        if owner is None:
            return self
        return _BoundTranslator(owner.__name__)


def tr(text: str) -> str:
    """Translate a string using the unified application context.

    This is the primary translation function for all UI strings. It uses
    a single shared context (TextureAtlasToolboxApp) which matches the
    context used in ui_constants.py and .ts translation files.

    Usage:
        from utils.translation_manager import tr

        # As a standalone function:
        label = QLabel(tr("Your Computer"))
        label = QLabel(tr(Labels.FRAME_RATE))

        # As a class attribute for self.tr() style:
        class MyDialog(QDialog):
            tr = tr  # Enable self.tr("text") syntax

            def setup(self):
                self.setWindowTitle(self.tr("My Title"))

    Args:
        text: The string to translate.

    Returns:
        The translated string, or the original if no translation exists.
    """
    return QCoreApplication.translate(APP_TRANSLATION_CONTEXT, text)


# Create instance for class-attribute usage
tr = _UnifiedTranslator()
# Alias for compatibility with 'from utils.translation_manager import translate' pattern
translate = tr
