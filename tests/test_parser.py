"""Tests for pattern extraction and parsing logic."""

import pytest

from tmux_pick.core import (
    Config,
    find_patterns_in_text,
    get_action_for_selection,
    parse_selection,
)


@pytest.fixture
def sample_config() -> Config:
    """Sample configuration for testing."""
    return {
        "patterns": [
            {
                "name": "URL",
                "regex": r"https?://[^\s]+",
                "description": "HTTP/HTTPS URLs",
                "action": "open_url",
                "enabled": True,
            },
            {
                "name": "FILE",
                "regex": r"([a-zA-Z0-9_/.-]+\.(py|js|md))",
                "description": "File paths",
                "action": "open_file",
                "enabled": True,
            },
            {
                "name": "DISABLED",
                "regex": r"disabled",
                "description": "Disabled pattern",
                "action": "noop",
                "enabled": False,
            },
        ],
        "actions": {
            "open_url": {
                "command": "open {value}",
            },
            "open_file": {
                "command": "vim {value}",
            },
        },
    }


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Check out https://example.com and http://test.org",
            [
                "[URL] http://test.org",
                "[URL] https://example.com",
            ],
        ),
        (
            "See main.py and docs/readme.md for details",
            [
                "[FILE] docs/readme.md",
                "[FILE] main.py",
            ],
        ),
        ("This has a disabled pattern", []),
        ("", []),
    ],
)
def test_find_patterns_in_text(
    sample_config: Config, text: str, expected: list[str]
) -> None:
    """Test extracting patterns from text."""
    result = find_patterns_in_text(text, sample_config)
    assert result == expected


def test_find_patterns_deduplication(sample_config: Config) -> None:
    """Test that duplicate matches are deduplicated."""
    text = "https://example.com and https://example.com again"
    result = find_patterns_in_text(text, sample_config)
    assert result == ["[URL] https://example.com"]


def test_find_patterns_capture_group(sample_config: Config) -> None:
    """Test that regex capture groups are used if present."""
    text = "Check out src/main.py"
    result = find_patterns_in_text(text, sample_config)
    assert result == ["[FILE] src/main.py"]


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("[URL] https://example.com", ("URL", "https://example.com")),
        ("[FILE]   main.py   ", ("FILE", "main.py")),
        ("[URL]", ("URL", "")),
    ],
)
def test_parse_selection_valid(selection: str, expected: tuple[str, str]) -> None:
    """Test parsing valid selection formats."""
    result = parse_selection(selection)
    assert result == expected


@pytest.mark.parametrize(
    "selection",
    [
        "[URL https://example.com",
        "",
    ],
)
def test_parse_selection_invalid(selection: str) -> None:
    """Test parsing invalid selection formats."""
    result = parse_selection(selection)
    assert result is None


# Get action for selection tests


@pytest.mark.parametrize(
    ("selection", "expected_command", "expected_value"),
    [
        ("[URL] https://example.com", "open {value}", "https://example.com"),
        ("[FILE] main.py", "vim {value}", "main.py"),
    ],
)
def test_get_action_for_selection_valid(
    sample_config: Config,
    selection: str,
    expected_command: str,
    expected_value: str,
) -> None:
    """Test getting action for valid selections."""
    result = get_action_for_selection(selection, sample_config)
    assert result is not None
    action, value = result
    assert action["command"] == expected_command
    assert value == expected_value


@pytest.mark.parametrize(
    "selection",
    [
        "[UNKNOWN] test",
        "[URL] ",
        "not a valid selection",
    ],
)
def test_get_action_for_selection_invalid(
    sample_config: Config, selection: str
) -> None:
    """Test getting action for invalid selections."""
    result = get_action_for_selection(selection, sample_config)
    assert result is None
