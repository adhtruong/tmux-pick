"""Core pattern extraction and action execution logic."""

import argparse
import importlib.resources
import os
import re
import shlex
import subprocess
import sys
from typing import Callable, NotRequired, TypedDict

import tomllib


class Pattern(TypedDict):
    """Pattern definition from config."""

    name: str
    regex: str
    description: str
    action: str
    enabled: bool
    validate: NotRequired[str]


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


DEFAULT_CONFIG_PATH = "~/.config/tmux-pick.toml"


def load_bundled_config() -> Config:
    """Load the bundled default configuration."""
    config_file = importlib.resources.files("tmux_pick").joinpath("config.default.toml")
    return tomllib.loads(config_file.read_text())  # pyright: ignore[reportReturnType]


def load_config() -> Config:
    """Load configuration from PATTERN_CONFIG env var, default location, or bundled default."""
    config_path = os.path.expanduser(os.getenv("PATTERN_CONFIG", DEFAULT_CONFIG_PATH))
    if os.path.exists(config_path):
        return load_config_from_path(config_path)
    return load_bundled_config()


_VALIDATORS: dict[str, "Callable[[str, str], bool]"] = {}


def _validator(
    name: str,
) -> "Callable[[Callable[[str, str], bool]], Callable[[str, str], bool]]":
    def decorator(fn: "Callable[[str, str], bool]") -> "Callable[[str, str], bool]":
        _VALIDATORS[name] = fn
        return fn

    return decorator


@_validator("path")
def _validate_path(match_text: str, pane_path: str) -> bool:
    """True when the matched value (minus optional :line) exists on the filesystem."""
    path = re.sub(r":\d+$", "", match_text)
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.join(pane_path, path)
    return os.path.exists(path)


def find_patterns_in_text(
    text: str, config: Config, pane_path: str | None = None
) -> list[str]:
    """Extract patterns from text and return structured results."""
    all_matches = []

    for pattern in config["patterns"]:
        if not pattern["enabled"]:
            continue

        try:
            regex = re.compile(pattern["regex"])
        except re.error:
            continue

        for match_obj in regex.finditer(text):
            # Use first capture group if present, otherwise full match
            match_text = (
                match_obj.group(1) if match_obj.lastindex else match_obj.group(0)
            )
            position = match_obj.start()

            if match_text:
                if (
                    validator_name := pattern.get("validate")
                ) and pane_path is not None:
                    validator = _VALIDATORS.get(validator_name)
                    if validator and not validator(match_text, pane_path):
                        continue
                structured = f"{match_text}\t{pattern['name']}"
                all_matches.append((position, structured))

    # Sort newest-first (reverse position), deduplicate while preserving order
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
        subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace").strip()
        msg = f"Command failed (exit {e.returncode}): {command}"
        if stderr:
            msg += f"\n{stderr}"
        if fallback := action.get("fallback"):
            print(f"Warning: {msg}, trying fallback", file=sys.stderr)
            try:
                subprocess.run(
                    _prepare_command(fallback, value),
                    shell=True,
                    check=True,
                    stderr=subprocess.PIPE,
                )
            except subprocess.CalledProcessError as fe:
                fb_stderr = fe.stderr.decode(errors="replace").strip()
                raise RuntimeError(f"{msg}\nFallback also failed: {fb_stderr}") from fe
        else:
            raise RuntimeError(msg) from e


def extract_patterns_from_stdin() -> None:
    """Extract patterns from stdin and output tagged results."""
    config = load_config()
    pane_path = os.environ.get("PANE_PATH")
    text = sys.stdin.read()
    results = find_patterns_in_text(text, config, pane_path)

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
