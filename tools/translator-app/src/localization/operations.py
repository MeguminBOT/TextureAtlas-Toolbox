#!/usr/bin/env python3
"""Backend for Qt translation commands and .ts/.qm file management.

Provides LocalizationOperations, the main engine that wraps lupdate/lrelease
commands, generates resource files, manages machine-translation disclaimers,
and reports progress. Used by both the GUI and CLI.

Usage::

    from localization.operations import LocalizationOperations

    ops = LocalizationOperations()
    result = ops.extract(["fr_FR", "de_DE"])
    if result.success:
        ops.compile(["fr_FR", "de_DE"])
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .registry import LANGUAGE_REGISTRY

ROOT_SENTINELS = ("main.py", "Main.py", "app_config.cfg")


def resolve_language_code(code: Optional[str]) -> Optional[str]:
    """Return the canonical registry key for a language code.

    Performs case-insensitive lookup against LANGUAGE_REGISTRY keys.

    Args:
        code: Language code string to resolve (e.g., "FR_FR", "fr_fr").

    Returns:
        The matching registry key with original casing, or None if not found.
    """

    if not code:
        return None
    normalized = code.strip().lower()
    if not normalized:
        return None
    for registered in LANGUAGE_REGISTRY.keys():
        if registered.lower() == normalized:
            return registered
    return None


def normalize_languages(languages: Optional[Sequence[str]]) -> List[str]:
    """Validate and normalize a list of language codes.

    Resolves each code against the registry. Passing "all" or an empty
    sequence returns all registered languages.

    Args:
        languages: Language codes to validate; None or empty for all.

    Returns:
        List of canonical registry keys. Unknown codes are silently dropped.
    """

    if not languages:
        return list(LANGUAGE_REGISTRY.keys())

    resolved: List[str] = []
    for code in languages:
        if isinstance(code, str) and code.strip().lower() == "all":
            return list(LANGUAGE_REGISTRY.keys())
        canonical = resolve_language_code(code)
        if canonical:
            resolved.append(canonical)
    return resolved or list(LANGUAGE_REGISTRY.keys())


@dataclass
class TranslationPaths:
    """Resolved filesystem paths used by the localization workflow.

    Attributes:
        project_root: Root directory of the main application.
        src_dir: The primary source folder containing Python/UI files.
        translations_dir: Folder where .ts and .qm files are stored.
    """

    project_root: Path
    src_dir: Path
    translations_dir: Path

    @classmethod
    def discover(cls, start: Optional[Path] = None) -> "TranslationPaths":
        """Auto-discover project paths by walking parent directories.

        Searches upward for a src/ folder containing sentinel files
        (Main.py, app_config.cfg) that mark the project root.

        Args:
            start: Starting path for the search; defaults to this module's
                location.

        Returns:
            A TranslationPaths instance with resolved paths. Falls back to
            current working directory layout if no project is found.
        """

        start_path = (start or Path(__file__)).resolve()
        if start_path.is_file():
            start_path = start_path.parent

        fallback: Optional[Tuple[Path, Path, Path]] = None

        for candidate in [start_path, *start_path.parents]:
            src_dir = candidate / "src"
            if not src_dir.exists():
                continue
            translations_dir = src_dir / "translations"
            if cls._looks_like_project_root(src_dir):
                return cls(candidate, src_dir, translations_dir)
            if fallback is None:
                fallback = (candidate, src_dir, translations_dir)

        if fallback:
            return cls(*fallback)

        # Fallback to current working directory layout
        project_root = Path.cwd()
        src_dir = project_root / "src"
        translations_dir = src_dir / "translations"
        return cls(project_root, src_dir, translations_dir)

    @staticmethod
    def _looks_like_project_root(src_dir: Path) -> bool:
        """Check if src_dir contains known TextureAtlas Toolbox markers.

        Args:
            src_dir: Path to a candidate src folder.

        Returns:
            True if any ROOT_SENTINELS file exists in the directory.
        """

        return any((src_dir / marker).exists() for marker in ROOT_SENTINELS)


@dataclass
class CommandResult:
    """Outcome of a subprocess invocation.

    Attributes:
        command: The command-line arguments executed.
        success: True if the process returned exit code 0.
        stdout: Standard output captured from the process.
        stderr: Standard error captured from the process.
        exit_code: Numeric exit code returned by the process.
    """

    command: Sequence[str]
    success: bool
    stdout: str
    stderr: str
    exit_code: int


class CommandRunner:
    """Thin wrapper around subprocess.run for easier test mocking."""

    def run(self, command: Sequence[str], cwd: Optional[Path] = None) -> CommandResult:
        """Execute a shell command and capture its output.

        Args:
            command: Command-line arguments as a sequence.
            cwd: Working directory; uses current directory if omitted.

        Returns:
            A CommandResult with stdout, stderr, and exit code. Returns
            exit code 127 if the executable is not found.
        """
        try:
            process = subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                shell=False,
                check=False,
            )
        except FileNotFoundError as exc:
            return CommandResult(
                command=command,
                success=False,
                stdout="",
                stderr=str(exc),
                exit_code=127,
            )
        return CommandResult(
            command=command,
            success=process.returncode == 0,
            stdout=process.stdout.strip(),
            stderr=process.stderr.strip(),
            exit_code=process.returncode,
        )


@dataclass
class OperationResult:
    """Standard response for translation workflow actions.

    Attributes:
        name: Short identifier for the operation (e.g., 'extract', 'compile').
        success: True if the operation completed without errors.
        logs: Informational log messages produced during the operation.
        errors: Error messages encountered during the operation.
        details: Arbitrary metadata (per-language results, file counts, etc.).
    """

    name: str
    success: bool
    logs: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    details: Dict[str, object] = field(default_factory=dict)

    def add_log(self, message: str) -> None:
        """Append an informational message to the logs.

        Args:
            message: Log message to record.
        """
        self.logs.append(message)

    def add_error(self, message: str) -> None:
        """Record an error and mark the operation as failed.

        Args:
            message: Error message to record.
        """
        self.errors.append(message)
        self.success = False


def _count_messages(ts_path: Path) -> Tuple[int, int, int]:
    """Count translation message statistics in a .ts file.

    Excludes vanished/obsolete strings from the count since they no longer
    exist in the source code.

    Args:
        ts_path: Path to the .ts file to analyze.

    Returns:
        A tuple of (total_active, finished, machine_translated) counts.
    """

    if not ts_path.exists():
        return 0, 0, 0

    content = ts_path.read_text(encoding="utf-8", errors="ignore")
    total = content.count("<message>")
    unfinished = content.count('type="unfinished"')
    # Qt uses both "vanished" (newer) and "obsolete" (older) for removed strings
    vanished = content.count('type="vanished"')
    obsolete = content.count('type="obsolete"')
    # Count machine translated strings (marked with [machine] in comments)
    machine_translated = content.count("[machine]")
    # Exclude vanished/obsolete strings from total count
    active_total = max(total - vanished - obsolete, 0)
    # Finished = active strings that are neither unfinished nor vanished/obsolete
    finished = max(active_total - unfinished, 0)
    return active_total, finished, machine_translated


DISCLAIMER_BLOCK = """<context>
    <name>MachineTranslationDisclaimer</name>
    <message>
        <location filename="../main.py" line="0"/>
        <source>Machine Translation Notice</source>
        <translation type="unfinished">Machine Translation Notice</translation>
    </message>
    <message>
        <location filename="../main.py" line="1"/>
        <source>This language was automatically translated and may contain inaccuracies. If you would like to contribute better translations, please visit our GitHub repository.</source>
        <translation type="unfinished">This language was automatically translated and may contain inaccuracies. If you would like to contribute better translations, please visit our GitHub repository.</translation>
    </message>
</context>
"""


class LocalizationOperations:
    """High-level operations for managing Qt translation files.

    Wraps lupdate and lrelease commands, generates .qrc resource files,
    injects machine-translation disclaimers, and produces status reports.

    Attributes:
        paths: Resolved project paths for locating source and translation files.
        runner: Command executor (defaults to subprocess-based runner).
    """

    def __init__(
        self,
        paths: Optional[TranslationPaths] = None,
        runner: Optional[CommandRunner] = None,
    ):
        """Initialize the localization operations helper.

        Args:
            paths: Pre-resolved translation paths; auto-discovered if omitted.
            runner: Command runner for subprocess execution; uses standard
                subprocess runner if omitted.
        """
        self.paths = paths or TranslationPaths.discover()
        self.runner = runner or CommandRunner()
        self._tool_cache: Dict[str, List[str]] = {}

    def set_translations_dir(self, translations_dir: Path | str) -> TranslationPaths:
        """Override the translations directory at runtime.

        Clears the tool cache after updating paths.

        Args:
            translations_dir: New path to the translations folder.

        Returns:
            The updated TranslationPaths instance.

        Raises:
            ValueError: If the path does not exist or lacks project markers.
        """
        new_paths = self._build_paths_from_translations(translations_dir)
        self.paths = new_paths
        self._tool_cache.clear()
        return self.paths

    def _build_paths_from_translations(
        self, translations_dir: Path | str
    ) -> TranslationPaths:
        """Construct TranslationPaths from a translations folder.

        Args:
            translations_dir: Path to the translations folder.

        Returns:
            A new TranslationPaths instance.

        Raises:
            ValueError: If the path is invalid or not inside a recognized
                project structure.
        """
        candidate = Path(translations_dir).expanduser().resolve()
        if not candidate.exists() or not candidate.is_dir():
            raise ValueError("Translations directory does not exist.")

        src_dir = candidate.parent
        if not src_dir.exists():
            raise ValueError("Translations directory must live inside a src folder.")

        if not TranslationPaths._looks_like_project_root(src_dir):
            raise ValueError(
                "Selected folder is not part of a recognized TextureAtlas Toolbox source tree."
            )

        project_root = src_dir.parent
        return TranslationPaths(project_root, src_dir, candidate)

    def set_src_dir(self, src_dir: Path | str) -> TranslationPaths:
        """Override the source directory at runtime.

        Use this to manually select the TextureAtlas Toolbox src folder
        when auto-detection fails. Clears the tool cache after updating.

        Args:
            src_dir: Path to the src folder of TextureAtlas Toolbox.

        Returns:
            The updated TranslationPaths instance.

        Raises:
            ValueError: If the path does not exist or lacks project markers.
        """
        candidate = Path(src_dir).expanduser().resolve()
        if not candidate.exists() or not candidate.is_dir():
            raise ValueError("Source directory does not exist.")

        if not TranslationPaths._looks_like_project_root(candidate):
            raise ValueError(
                "Selected folder does not appear to be the TextureAtlas Toolbox src directory. "
                "Expected to find Main.py or app_config.cfg."
            )

        project_root = candidate.parent
        translations_dir = candidate / "translations"
        self.paths = TranslationPaths(project_root, candidate, translations_dir)
        self._tool_cache.clear()
        return self.paths

    def is_project_detected(self) -> bool:
        """Check if a valid TextureAtlas Toolbox project is configured.

        Returns:
            True if src_dir exists and contains expected project markers.
        """
        return (
            self.paths.src_dir.exists()
            and TranslationPaths._looks_like_project_root(self.paths.src_dir)
        )

    def _ensure_translations_dir(self) -> None:
        """Create the translations directory if it does not exist."""
        self.paths.translations_dir.mkdir(parents=True, exist_ok=True)

    def _collect_source_files(self) -> List[Path]:
        """Gather all translatable source files under src_dir.

        Returns:
            Sorted list of unique .py and .ui file paths.
        """
        if not self.paths.src_dir.exists():
            return []

        files: List[Path] = []
        for pattern in ("*.py", "*.ui"):
            files.extend(self.paths.src_dir.rglob(pattern))

        unique_files = {f.resolve() for f in files if f.is_file()}
        return sorted(unique_files)

    def _build_tool_command(self, tool: str, extra_args: Sequence[str]) -> List[str]:
        """Construct a command list for a Qt translation tool.

        Args:
            tool: Tool name ("lupdate" or "lrelease").
            extra_args: Additional arguments to append.

        Returns:
            Complete command list ready for subprocess execution.
        """
        base = self._tool_cache.get(tool)
        if base is None:
            base = self._resolve_tool(tool)
            self._tool_cache[tool] = base
        return base + list(extra_args)

    def _resolve_tool(self, tool: str) -> List[str]:
        """Locate the lupdate or lrelease executable.

        Searches in order: environment variables, PySide6 installation,
        system PATH.

        Args:
            tool: Tool name ("lupdate" or "lrelease").

        Returns:
            Command list for invoking the tool.
        """
        env_key = {"lupdate": "QT_LUPDATE", "lrelease": "QT_LRELEASE"}.get(tool)
        if env_key:
            env_value = os.environ.get(env_key)
            if env_value:
                candidate = Path(env_value)
                if candidate.exists():
                    return [str(candidate)]

        pyside_candidates: List[Path] = []
        try:
            import PySide6  # type: ignore
        except Exception:
            PySide6 = None  # type: ignore
        if PySide6 is not None:
            pyside_dir = Path(PySide6.__file__).resolve().parent
            pyside_candidates.extend(
                [
                    pyside_dir / tool,
                    pyside_dir / f"{tool}.exe",
                    pyside_dir / "Qt" / "libexec" / tool,
                    pyside_dir / "Qt" / "libexec" / f"{tool}.exe",
                ]
            )
        for candidate in pyside_candidates:
            if candidate.exists():
                return [str(candidate)]

        exe_name = f"pyside6-{tool}"
        which_path = shutil.which(exe_name)
        if which_path:
            return [which_path]

        alt_path = shutil.which(tool)
        if alt_path:
            return [alt_path]

        return [exe_name]

    def extract(self, languages: Optional[Sequence[str]] = None) -> OperationResult:
        """Run lupdate to refresh .ts files from source code.

        Scans all .py and .ui files under src_dir for translatable strings
        and updates the corresponding .ts files.

        Args:
            languages: Language codes to update; processes all if omitted.

        Returns:
            An OperationResult with per-language success details.
        """
        self._ensure_translations_dir()
        result = OperationResult("extract", True)
        selected = normalize_languages(languages)
        source_files = self._collect_source_files()

        if not self.paths.src_dir.exists():
            result.add_error(f"Source directory not found: {self.paths.src_dir}")
            return result

        if not source_files:
            result.add_error("No source or UI files found for extraction.")
            return result

        per_language = []
        for lang in selected:
            ts_file = self.paths.translations_dir / f"app_{lang}.ts"
            cmd = self._build_tool_command(
                "lupdate",
                [*(str(f) for f in source_files), "-ts", str(ts_file)],
            )
            run_result = self.runner.run(cmd, cwd=self.paths.project_root)
            per_language.append(
                {
                    "language": lang,
                    "ts_file": str(ts_file),
                    "success": run_result.success,
                    "stdout": run_result.stdout,
                    "stderr": run_result.stderr,
                    "exit_code": run_result.exit_code,
                }
            )
            log_line = (
                f"{'[OK]' if run_result.success else '[FAIL]'} {lang}: wrote {ts_file}"
            )
            result.add_log(log_line)
            if not run_result.success:
                result.add_error(f"Failed to update {ts_file}")
        result.details["per_language"] = per_language
        result.details["files_processed"] = len(source_files)
        return result

    def compile(self, languages: Optional[Sequence[str]] = None) -> OperationResult:
        """Run lrelease to compile .ts files into .qm binaries.

        Args:
            languages: Language codes to compile; processes all if omitted.

        Returns:
            An OperationResult with per-language success details.
        """
        self._ensure_translations_dir()
        result = OperationResult("compile", True)
        selected = normalize_languages(languages)

        per_language = []
        for lang in selected:
            ts_file = self.paths.translations_dir / f"app_{lang}.ts"
            if not ts_file.exists():
                result.add_log(f"Skipping {lang}: missing {ts_file}")
                continue
            qm_file = ts_file.with_suffix(".qm")
            cmd = self._build_tool_command(
                "lrelease", [str(ts_file), "-qm", str(qm_file)]
            )
            run_result = self.runner.run(cmd, cwd=self.paths.project_root)
            per_language.append(
                {
                    "language": lang,
                    "ts_file": str(ts_file),
                    "qm_file": str(qm_file),
                    "success": run_result.success,
                    "stdout": run_result.stdout,
                    "stderr": run_result.stderr,
                    "exit_code": run_result.exit_code,
                }
            )
            log_line = f"{'[OK]' if run_result.success else '[FAIL]'} {lang}: compiled {qm_file.name}"
            result.add_log(log_line)
            if not run_result.success:
                result.add_error(f"Failed to compile {ts_file}")
        result.details["per_language"] = per_language
        return result

    def create_resource_file(self) -> OperationResult:
        """Generate a translations.qrc file listing compiled .qm files.

        Returns:
            An OperationResult indicating success. Fails if no .qm files exist.
        """
        self._ensure_translations_dir()
        result = OperationResult("resource", True)
        qm_files = sorted(self.paths.translations_dir.glob("app_*.qm"))
        if not qm_files:
            result.add_error("No .qm files found. Compile translations first.")
            return result

        qrc_content = [
            "<!DOCTYPE RCC>",
            '<RCC version="1.0">',
            '<qresource prefix="/translations">',
        ]
        for qm_file in qm_files:
            qrc_content.append(f"    <file>{qm_file.name}</file>")
        qrc_content.append("</qresource>")
        qrc_content.append("</RCC>")

        qrc_path = self.paths.translations_dir / "translations.qrc"
        qrc_path.write_text("\n".join(qrc_content), encoding="utf-8")
        result.add_log(f"Wrote resource file: {qrc_path}")
        result.details["qrc"] = str(qrc_path)
        return result

    def status_report(
        self, languages: Optional[Sequence[str]] = None
    ) -> OperationResult:
        """Generate a translation progress report.

        Collects statistics including message counts, completion status,
        and file existence for each language.

        Args:
            languages: Language codes to report; processes all if omitted.

        Returns:
            An OperationResult with detailed entries in result.details["entries"].
        """
        result = OperationResult("status", True)
        selected = normalize_languages(languages)
        entries = []
        for lang in selected:
            meta = LANGUAGE_REGISTRY.get(lang, {})
            ts_file = self.paths.translations_dir / f"app_{lang}.ts"
            qm_file = ts_file.with_suffix(".qm")
            ts_exists = ts_file.exists()
            qm_exists = qm_file.exists()
            total, finished, machine_translated = _count_messages(ts_file)
            unfinished = max(total - finished, 0)
            entry = {
                "language": lang,
                "name": meta.get("name", lang),
                "english_name": meta.get("english_name", meta.get("name", lang)),
                "quality": meta.get("quality", "unknown"),
                "ts_exists": ts_exists,
                "qm_exists": qm_exists,
                "ts_file": str(ts_file),
                "qm_file": str(qm_file),
                "total_messages": total,
                "finished_messages": finished,
                "unfinished_messages": unfinished,
                "machine_translated": machine_translated,
                "needs_update": (not ts_exists) or unfinished > 0,
            }
            entries.append(entry)
            progress = f"{finished}/{total}" if total else "0/0"
            result.add_log(
                f"{lang.upper()} | .ts {'[Y]' if entry['ts_exists'] else '[N]'} | .qm {'[Y]' if entry['qm_exists'] else '[N]'} | {progress}"
            )
        result.details["entries"] = entries
        return result

    def inject_disclaimers(
        self, languages: Optional[Sequence[str]] = None
    ) -> OperationResult:
        """Insert machine-translation disclaimer into .ts files.

        Only applies to languages with quality="machine" in the registry.
        Skips files that already contain the disclaimer.

        Args:
            languages: Language codes to process; processes all if omitted.

        Returns:
            An OperationResult listing which files were modified.
        """
        self._ensure_translations_dir()
        result = OperationResult("disclaimer", True)
        selected = normalize_languages(languages)

        for lang in selected:
            meta = LANGUAGE_REGISTRY.get(lang, {})
            if meta.get("quality") != "machine":
                result.add_log(f"Skipping {lang}: not tagged as machine translated")
                continue

            ts_file = self.paths.translations_dir / f"app_{lang}.ts"
            if not ts_file.exists():
                result.add_log(f"Skipping {lang}: missing {ts_file}")
                continue

            content = ts_file.read_text(encoding="utf-8")
            if "MachineTranslationDisclaimer" in content:
                result.add_log(f"Disclaimer already present in {ts_file.name}")
                continue

            if "</TS>" not in content:
                result.add_error(f"Malformed TS file (missing </TS>): {ts_file}")
                continue

            updated = content.replace("</TS>", DISCLAIMER_BLOCK + "\n</TS>")
            ts_file.write_text(updated, encoding="utf-8")
            result.add_log(f"Inserted disclaimer into {ts_file.name}")
        return result

    def remove_disclaimers(
        self, languages: Optional[Sequence[str]] = None
    ) -> OperationResult:
        """Remove machine-translation disclaimer from .ts files.

        Args:
            languages: Language codes to process; processes all if omitted.

        Returns:
            An OperationResult listing which files were modified.
        """
        import re

        self._ensure_translations_dir()
        result = OperationResult("remove_disclaimer", True)
        selected = normalize_languages(languages)

        for lang in selected:
            ts_file = self.paths.translations_dir / f"app_{lang}.ts"
            if not ts_file.exists():
                result.add_log(f"Skipping {lang}: missing {ts_file}")
                continue

            content = ts_file.read_text(encoding="utf-8")
            if "MachineTranslationDisclaimer" not in content:
                result.add_log(f"No disclaimer found in {ts_file.name}")
                continue

            updated = content
            removed = False

            if DISCLAIMER_BLOCK + "\n" in updated:
                updated = updated.replace(DISCLAIMER_BLOCK + "\n", "")
                removed = True
            elif DISCLAIMER_BLOCK in updated:
                updated = updated.replace(DISCLAIMER_BLOCK, "")
                removed = True

            if not removed or "MachineTranslationDisclaimer</name>" in updated:
                pattern = r"<context>\s*<name>MachineTranslationDisclaimer</name>(?!Dialog).*?</context>\s*"
                updated, count = re.subn(pattern, "", updated, flags=re.DOTALL)
                if count > 0:
                    removed = True

            if "<name>MachineTranslationDisclaimer</name>" in updated:
                result.add_error(
                    f"Failed to remove disclaimer from {ts_file.name} - pattern mismatch"
                )
                continue

            with open(ts_file, "w", encoding="utf-8") as f:
                f.write(updated)
                f.flush()
            result.add_log(f"Removed disclaimer from {ts_file.name}")
        return result

    def toggle_disclaimers(
        self, languages: Optional[Sequence[str]] = None
    ) -> OperationResult:
        """Toggle machine-translation disclaimers in .ts files.

        Removes the disclaimer if present, adds it if absent. Uses regex
        fallback to handle non-standard disclaimer formats.

        Args:
            languages: Language codes to process; processes all if omitted.

        Returns:
            An OperationResult with added/removed counts in details.
        """
        self._ensure_translations_dir()
        result = OperationResult("toggle_disclaimer", True)
        selected = normalize_languages(languages)

        added_count = 0
        removed_count = 0

        for lang in selected:
            ts_file = self.paths.translations_dir / f"app_{lang}.ts"
            if not ts_file.exists():
                result.add_log(f"Skipping {lang}: missing {ts_file}")
                continue

            with open(ts_file, "r", encoding="utf-8") as f:
                content = f.read()
            has_disclaimer = "<name>MachineTranslationDisclaimer</name>" in content

            if has_disclaimer:
                updated = content
                removed = False

                if DISCLAIMER_BLOCK + "\n" in updated:
                    updated = updated.replace(DISCLAIMER_BLOCK + "\n", "")
                    removed = True
                elif DISCLAIMER_BLOCK in updated:
                    updated = updated.replace(DISCLAIMER_BLOCK, "")
                    removed = True

                if not removed or "MachineTranslationDisclaimer</name>" in updated:
                    import re

                    pattern = r"<context>\s*<name>MachineTranslationDisclaimer</name>(?!Dialog).*?</context>\s*"
                    updated, count = re.subn(pattern, "", updated, flags=re.DOTALL)
                    if count > 0:
                        removed = True

                if "<name>MachineTranslationDisclaimer</name>" in updated:
                    result.add_error(
                        f"Failed to remove disclaimer from {ts_file.name} - pattern mismatch"
                    )
                    continue

                with open(ts_file, "w", encoding="utf-8") as f:
                    f.write(updated)
                    f.flush()
                result.add_log(f"Removed disclaimer from {ts_file.name}")
                removed_count += 1
            else:
                if "</TS>" not in content:
                    result.add_error(f"Malformed TS file (missing </TS>): {ts_file}")
                    continue

                updated = content.replace("</TS>", DISCLAIMER_BLOCK + "\n</TS>")
                with open(ts_file, "w", encoding="utf-8") as f:
                    f.write(updated)
                    f.flush()
                result.add_log(f"Inserted disclaimer into {ts_file.name}")
                added_count += 1

        result.details["added"] = added_count
        result.details["removed"] = removed_count
        return result

    def has_disclaimer(self, language: str) -> bool:
        """Check if a language's .ts file contains the MT disclaimer.

        Looks for the exact context name, not the Dialog variant.

        Args:
            language: Language code to check.

        Returns:
            True if the MachineTranslationDisclaimer context is present.
        """
        ts_file = self.paths.translations_dir / f"app_{language}.ts"
        if not ts_file.exists():
            return False
        with open(ts_file, "r", encoding="utf-8") as f:
            content = f.read()
        return "<name>MachineTranslationDisclaimer</name>" in content


__all__ = [
    "LocalizationOperations",
    "TranslationPaths",
    "CommandRunner",
    "CommandResult",
    "OperationResult",
    "resolve_language_code",
    "normalize_languages",
]
