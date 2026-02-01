"""Core pattern extraction and action execution logic."""

import argparse
import os
import re
import shlex
import subprocess
import sys
from typing import NotRequired, TypedDict

import tomllib


class Pattern(TypedDict):
    """Pattern definition from config."""

    name: str
    regex: str
    description: str
    action: str
    enabled: bool


class Action(TypedDict):
    """Action definition from config."""

    command: str
    fallback: NotRequired[str]
    description: NotRequired[str]


class Config(TypedDict):
    """Configuration structure."""

    patterns: list[Pattern]
    actions: dict[str, Action]


def load_config_from_path(config_path: str) -> Config:
    """Load configuration from TOML file path."""
    config_path = os.path.expanduser(config_path)
    with open(config_path, "rb") as f:
        return tomllib.load(f)  # pyright: ignore[reportReturnType]


def load_config() -> Config:
    """Load configuration from environment variable PATTERN_CONFIG."""
    config_path = os.getenv("PATTERN_CONFIG")
    if not config_path:
        raise RuntimeError("PATTERN_CONFIG environment variable not set")
    return load_config_from_path(config_path)


def find_patterns_in_text(text: str, config: Config) -> list[str]:
    """Extract patterns from text and return structured results.

    Args:
        text: Input text to search for patterns
        config: Configuration containing pattern definitions

    Returns:
        List of delimited patterns: ["value|type", ...]
    """
    # Collect all matches with their positions in the text
    all_matches = []

    for pattern in config["patterns"]:
        if not pattern["enabled"]:
            continue

        try:
            regex = re.compile(pattern["regex"])
        except re.error:
            continue

        # Find matches with their positions
        for match_obj in regex.finditer(text):
            # Use first capture group if present, otherwise full match
            match_text = (
                match_obj.group(1) if match_obj.lastindex else match_obj.group(0)
            )
            position = match_obj.start()

            if match_text:
                # Output: value\ttype (tab-delimited, fzf will handle display formatting)
                structured = f"{match_text}\t{pattern['name']}"
                all_matches.append((position, structured))

    # Sort by position (reverse order - recent items first), deduplicate while preserving order
    seen = set()
    results = []
    for _, structured in sorted(all_matches, key=lambda x: x[0], reverse=True):
        if structured not in seen:
            seen.add(structured)
            results.append(structured)

    return results


def parse_selection(selection: str) -> tuple[str, str] | None:
    """Parse tab-delimited selection into (type, value) or None if invalid."""
    parts = selection.rsplit("\t", 1)
    if len(parts) != 2:
        return None
    return (parts[1], parts[0])


def get_action_for_selection(
    selection: str, config: Config
) -> tuple[Action, str] | None:
    """Get action and value for a tab-delimited selection, or None if invalid."""
    parsed = parse_selection(selection)
    if not parsed:
        return None

    pattern_type, value = parsed
    if not value:
        return None

    # Reject values with newlines (breaks shell execution)
    if "\n" in value or "\r" in value:
        print("Warning: Skipping value with newlines", file=sys.stderr)
        return None

    # Find action name for this pattern type
    action_name = next(
        (p["action"] for p in config["patterns"] if p["name"] == pattern_type),
        None,
    )
    if not action_name:
        return None

    action = config["actions"].get(action_name)
    return (action, value) if action else None


def _prepare_command(template: str, value: str) -> str:
    """Prepare command by expanding vars and substituting escaped value."""
    safe_value = shlex.quote(os.path.expanduser(value))
    return os.path.expandvars(template).replace("{value}", safe_value)


def execute_command(action: Action, value: str) -> None:
    """Execute an action command with the given value (shell-escaped for safety)."""
    command = _prepare_command(action["command"], value)

    try:
        subprocess.run(command, shell=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        if fallback := action.get("fallback"):
            try:
                subprocess.run(
                    _prepare_command(fallback, value), shell=True, check=True
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                raise RuntimeError(f"Could not execute action: {e}") from e
        else:
            raise RuntimeError(f"Could not execute action: {e}") from e


def extract_patterns_from_stdin() -> None:
    """Extract patterns from stdin and output tagged results."""
    config = load_config()
    text = sys.stdin.read()
    results = find_patterns_in_text(text, config)

    for result in results:
        print(result)


def execute_action_from_selection(selection: str) -> None:
    """Execute action based on tagged pattern selection."""
    config = load_config()
    result = get_action_for_selection(selection, config)

    if not result:
        print("Error: invalid selection or action not found", file=sys.stderr)
        sys.exit(1)

    action, value = result
    try:
        execute_command(action, value)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def extract_value_from_selection(selection: str) -> None:
    """Extract just the value from a tagged selection."""
    parsed = parse_selection(selection)
    if not parsed:
        print(selection, file=sys.stderr)
        sys.exit(1)
    _, value = parsed
    print(value)


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract patterns from text and execute configurable actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Command to run"
    )

    # Extract subcommand
    subparsers.add_parser(
        "extract", help="Extract patterns from stdin and output tagged results"
    )

    # Execute subcommand
    execute_parser = subparsers.add_parser(
        "execute", help="Execute action based on pattern selection"
    )
    execute_parser.add_argument(
        "selection", help='Tab-delimited selection in format "value\\ttype"'
    )

    # Value subcommand
    value_parser = subparsers.add_parser(
        "value", help="Extract just the value from a selection"
    )
    value_parser.add_argument(
        "selection", help='Tab-delimited selection in format "value\\ttype"'
    )

    args = parser.parse_args()

    if args.command == "extract":
        extract_patterns_from_stdin()
    elif args.command == "execute":
        execute_action_from_selection(args.selection)
    elif args.command == "value":
        extract_value_from_selection(args.selection)
