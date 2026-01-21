#!/usr/bin/env python3
"""Command-line interface for translation management operations.

Provides CLI access to extract, compile, status, disclaimer, and quality
operations without launching the GUI. Useful for CI/CD pipelines and
batch processing.

Usage:
    python cli.py extract fr_FR de_DE
    python cli.py compile --all
    python cli.py status
    python cli.py disclaimer --add fr_FR
    python cli.py disclaimer --remove fr_FR
    python cli.py disclaimer --toggle fr_FR
    python cli.py quality fr_FR de_DE --set reviewed
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from localization import (
    LocalizationOperations,
    OperationResult,
    LANGUAGE_REGISTRY,
    save_language_registry,
)


def print_result(result: OperationResult) -> None:
    """Print an operation result to stdout.

    Args:
        result: The operation result to display.
    """
    status = "SUCCESS" if result.success else "FAILED"
    print(f"\n[{result.name.upper()}] {status}")

    if result.logs:
        print("\nLogs:")
        for log in result.logs:
            print(f" {log}")

    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f" {error}")

    if result.details:
        if "added" in result.details or "removed" in result.details:
            added = result.details.get("added", 0)
            removed = result.details.get("removed", 0)
            print(f"\nSummary: {added} added, {removed} removed")


def cmd_extract(ops: LocalizationOperations, languages: List[str]) -> int:
    """Run lupdate to extract translatable strings.

    Args:
        ops: LocalizationOperations instance.
        languages: Language codes to process.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    result = ops.extract(languages if languages else None)
    print_result(result)
    return 0 if result.success else 1


def cmd_compile(ops: LocalizationOperations, languages: List[str]) -> int:
    """Run lrelease to compile .ts to .qm files.

    Args:
        ops: LocalizationOperations instance.
        languages: Language codes to process.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    result = ops.compile(languages if languages else None)
    print_result(result)
    return 0 if result.success else 1


def cmd_resource(ops: LocalizationOperations) -> int:
    """Generate translations.qrc file.

    Args:
        ops: LocalizationOperations instance.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    result = ops.create_resource_file()
    print_result(result)
    return 0 if result.success else 1


def cmd_status(ops: LocalizationOperations, languages: List[str]) -> int:
    """Print translation status report.

    Args:
        ops: LocalizationOperations instance.
        languages: Language codes to report on.

    Returns:
        Exit code (0 for success).
    """
    result = ops.status_report(languages if languages else None)

    print("\nTranslation Status Report")
    print("=" * 60)

    entries = result.details.get("entries", [])
    for entry in entries:
        lang = entry.get("language", "?").upper()
        name = entry.get("english_name", entry.get("name", ""))
        total = entry.get("total_messages", 0)
        finished = entry.get("finished_messages", 0)
        ts_exists = "[Y]" if entry.get("ts_exists") else "[N]"
        qm_exists = "[Y]" if entry.get("qm_exists") else "[N]"
        quality = entry.get("quality", "unknown")

        pct = (finished / total * 100) if total > 0 else 0
        bar_len = 20
        filled = int(pct / 100 * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)

        print(f"\n{lang} - {name} [{quality}]")
        print(f"  .ts: {ts_exists}  .qm: {qm_exists}")
        print(f"  Progress: [{bar}] {finished}/{total} ({pct:.1f}%)")

    print("\n" + "=" * 60)
    return 0


def cmd_disclaimer(
    ops: LocalizationOperations,
    languages: List[str],
    action: str,
) -> int:
    """Add, remove, or toggle MT disclaimers.

    Args:
        ops: LocalizationOperations instance.
        languages: Language codes to process.
        action: One of "add", "remove", or "toggle".

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    if action == "add":
        result = ops.inject_disclaimers(languages if languages else None)
    elif action == "remove":
        result = ops.remove_disclaimers(languages if languages else None)
    else:  # toggle
        result = ops.toggle_disclaimers(languages if languages else None)

    print_result(result)
    return 0 if result.success else 1


VALID_QUALITY_VALUES = ("machine", "reviewed", "unknown")


def cmd_quality(languages: List[str], quality: str) -> int:
    """Set the quality level for languages in the registry.

    Args:
        languages: Language codes to update.
        quality: Quality value ("machine", "reviewed", or "unknown").

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    if quality not in VALID_QUALITY_VALUES:
        print(
            f"Error: Invalid quality '{quality}'. Must be one of: {', '.join(VALID_QUALITY_VALUES)}",
            file=sys.stderr,
        )
        return 1

    if not languages:
        print(
            "Error: No languages specified. Provide at least one language code.",
            file=sys.stderr,
        )
        return 1

    updated = []
    not_found = []

    for lang in languages:
        # Case-insensitive lookup
        matched_key = None
        for key in LANGUAGE_REGISTRY:
            if key.lower() == lang.lower():
                matched_key = key
                break

        if matched_key:
            LANGUAGE_REGISTRY[matched_key]["quality"] = quality
            updated.append(matched_key)
        else:
            not_found.append(lang)

    if updated:
        save_language_registry(LANGUAGE_REGISTRY)
        print("\n[QUALITY] SUCCESS")
        print(f"\nUpdated {len(updated)} language(s) to quality='{quality}':")
        for lang in updated:
            name = LANGUAGE_REGISTRY[lang].get(
                "english_name", LANGUAGE_REGISTRY[lang].get("name", lang)
            )
            print(f"  [OK] {lang.upper()} - {name}")

    if not_found:
        print(f"\nNot found in registry ({len(not_found)}):")
        for lang in not_found:
            print(f" [!] {lang}")

    return 0 if updated else 1


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog="translator-cli",
        description="Translation management CLI for TextureAtlas Toolbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s extract fr_FR de_DE     Extract strings for French and German
  %(prog)s compile --all           Compile all languages
  %(prog)s status                  Show translation progress
  %(prog)s disclaimer --toggle fr  Toggle disclaimer for French
  %(prog)s quality fr_FR --set reviewed  Mark French as reviewed
        """,
    )

    parser.add_argument(
        "--src-dir",
        type=Path,
        help="Path to TextureAtlas Toolbox src directory",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Extract command
    extract_parser = subparsers.add_parser(
        "extract",
        help="Run lupdate to extract translatable strings",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  translator-cli extract                 Extract for all languages
  translator-cli extract fr_FR de_DE     Extract for French and German only
        """,
    )
    extract_parser.add_argument(
        "languages",
        nargs="*",
        help="Language codes to process (default: all)",
    )
    extract_parser.add_argument(
        "--all",
        action="store_true",
        help="Process all registered languages",
    )

    # Compile command
    compile_parser = subparsers.add_parser(
        "compile",
        help="Run lrelease to compile .ts to .qm",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  translator-cli compile                 Compile all languages
  translator-cli compile fr_FR de_DE     Compile French and German only
        """,
    )
    compile_parser.add_argument(
        "languages",
        nargs="*",
        help="Language codes to process (default: all)",
    )
    compile_parser.add_argument(
        "--all",
        action="store_true",
        help="Process all registered languages",
    )

    # Resource command
    subparsers.add_parser(
        "resource",
        help="Generate translations.qrc file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  translator-cli resource                Generate .qrc from all .qm files
        """,
    )

    # Status command
    status_parser = subparsers.add_parser(
        "status",
        help="Show translation progress report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  translator-cli status                  Show status for all languages
  translator-cli status fr_FR de_DE      Show status for French and German
        """,
    )
    status_parser.add_argument(
        "languages",
        nargs="*",
        help="Language codes to report (default: all)",
    )

    # Disclaimer command
    disclaimer_parser = subparsers.add_parser(
        "disclaimer",
        help="Manage MT disclaimers in .ts files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  translator-cli disclaimer --add fr_FR       Add disclaimer to French
  translator-cli disclaimer --remove fr_FR    Remove disclaimer from French
  translator-cli disclaimer --toggle fr_FR    Toggle (add if missing, remove if present)
  translator-cli disclaimer --toggle          Toggle for all languages
        """,
    )
    disclaimer_parser.add_argument(
        "languages",
        nargs="*",
        help="Language codes to process (default: all)",
    )
    disclaimer_group = disclaimer_parser.add_mutually_exclusive_group(required=True)
    disclaimer_group.add_argument(
        "--add",
        action="store_const",
        const="add",
        dest="action",
        help="Add disclaimer to files",
    )
    disclaimer_group.add_argument(
        "--remove",
        action="store_const",
        const="remove",
        dest="action",
        help="Remove disclaimer from files",
    )
    disclaimer_group.add_argument(
        "--toggle",
        action="store_const",
        const="toggle",
        dest="action",
        help="Toggle disclaimer (add if absent, remove if present)",
    )

    # Quality command
    quality_parser = subparsers.add_parser(
        "quality",
        help="Set translation quality level for languages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  translator-cli quality fr_FR --set reviewed      Mark French as reviewed
  translator-cli quality de_DE es_ES --set machine Mark German and Spanish as machine
  translator-cli quality ja_JP --set unknown       Mark Japanese as unknown
        """,
    )
    quality_parser.add_argument(
        "languages",
        nargs="+",
        help="Language codes to update (required)",
    )
    quality_parser.add_argument(
        "--set",
        required=True,
        choices=["machine", "reviewed", "unknown"],
        dest="quality_value",
        help="Quality level to set",
    )

    # Help command
    help_parser = subparsers.add_parser(
        "help",
        help="Show help for a command",
    )
    help_parser.add_argument(
        "help_command",
        nargs="?",
        choices=["extract", "compile", "resource", "status", "disclaimer", "quality"],
        help="Command to get help for",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point.

    Args:
        argv: Command-line arguments; uses sys.argv if None.

    Returns:
        Exit code for the process.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # Initialize operations
    ops = LocalizationOperations()

    # Override src directory if specified
    if args.src_dir:
        try:
            ops.set_src_dir(args.src_dir)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    # Check project detection
    if not ops.is_project_detected():
        print(
            "Warning: TextureAtlas Toolbox project not detected. "
            "Use --src-dir to specify the src directory.",
            file=sys.stderr,
        )

    # Get languages from args
    languages: List[str] = getattr(args, "languages", []) or []

    # Execute command
    if args.command == "extract":
        return cmd_extract(ops, languages)
    elif args.command == "compile":
        return cmd_compile(ops, languages)
    elif args.command == "resource":
        return cmd_resource(ops)
    elif args.command == "status":
        return cmd_status(ops, languages)
    elif args.command == "disclaimer":
        return cmd_disclaimer(ops, languages, args.action)
    elif args.command == "quality":
        return cmd_quality(languages, args.quality_value)
    elif args.command == "help":
        if args.help_command:
            # Show help for specific command
            help_parser = build_parser()
            help_parser.parse_args([args.help_command, "--help"])
        else:
            parser.print_help()
        return 0
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
