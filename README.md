# tmux-pick

Interactive pattern matching and action execution for tmux. Extract URLs, git hashes, IP addresses, file paths, and more from your terminal output and execute context-aware actions.

## Features

- **Pattern Extraction**: Capture URLs, git commits, IP addresses, file paths from tmux panes
- **Interactive Selection**: fzf-powered interface
- **Configurable Actions**: Execute shell commands based on pattern type
- **Config-Driven**: TOML configuration for patterns and actions
- **Fallback Support**: Alternative commands for cross-platform compatibility
- **Capture Groups**: Extract specific portions while matching with context

## Installation

### With TPM (Tmux Plugin Manager)

Add to `.tmux.conf`:

```tmux
set -g @plugin 'path/to/tmux-pick'
set -g @pick-config '~/.config/pattern-matcher.toml'
set -g @pick-key 'u'  # Optional: customize keybinding (default: u)
```

Then press `prefix + I` to install.

### Manual

1. Clone this repository
2. Add to `.tmux.conf`:

```tmux
set -g @pick-config '~/.config/pattern-matcher.toml'
run-shell 'path/to/tmux-pick/pick.tmux'
```

## Usage

### In Tmux

**Default keybinding**: `prefix + u`

1. Press the keybinding in a tmux pane
2. Patterns are extracted from the last 3000 lines
3. Select a pattern with fzf
4. Press Enter to execute the action

### Standalone

The Python module can be used outside of tmux:

```bash
# Extract patterns from text
echo "Check out https://example.com" | uv run -m tmux_pick extract

# Execute an action
uv run -m tmux_pick execute "[URL] https://example.com"
```

## Configuration

### Required: Config File Location

**Must be set before loading the plugin:**

```tmux
set -g @pick-config '~/.config/pattern-matcher.toml'
```

### Optional: Custom Keybinding

```tmux
set -g @pick-key 'o'  # Use prefix + o instead of u
```

### Config Format

Create a TOML file with patterns and actions:

```toml
[[patterns]]
name = "URL"
regex = '''https?://[^\s<>"'()]+'''
description = "HTTP/HTTPS URLs"
action = "open_browser"
enabled = true

[[patterns]]
name = "FILE"
regex = '''([a-zA-Z0-9_./\-]+\.(?:py|js|ts|jsx|tsx))'''
description = "File paths"
action = "open_editor"
enabled = true

[actions.open_browser]
command = 'open "{value}"'
fallback = 'xdg-open "{value}"'
description = "Open in default browser"

[actions.open_editor]
command = '''tmux new-window -c "#{pane_current_path}" "${EDITOR:-vim} '{value}'"'''
description = "Open in text editor"
```

### Pattern Fields

- **`name`**: Pattern type identifier (used in tags like `[URL]`)
- **`regex`**: Regular expression (Python syntax)
  - Use capture groups `(...)` to extract specific portions
  - Use non-capturing groups `(?:...)` for context matching
  - If capture group exists, group(1) is extracted; otherwise full match is used
- **`description`**: Human-readable description
- **`action`**: Which action to execute
- **`enabled`**: Whether this pattern is active

### Action Fields

- **`command`**: Shell command to execute
  - `{value}` is replaced with the matched text
  - Use `#{pane_current_path}` for tmux pane's directory
- **`fallback`** (optional): Alternative command if primary fails
- **`description`** (optional): Human-readable description

### Environment Variables

- **`$PATTERN_CONFIG`**: Path to config file

## Regex and Capture Groups

Extract specific portions while matching with context:

```toml
[[patterns]]
name = "FILE"
# group(1) extracts just the filename
regex = '''(?:^|\s)([a-zA-Z0-9_./\-]+\.py)(?:\s|$)'''
```

- **Capturing group** `(...)`: Extracted as the value
- **Non-capturing group** `(?:...)`: Used for matching but not extracted
- First capture group is used; if none exist, entire match is extracted

## Default Patterns

Common pattern examples:

- **URL**: HTTP/HTTPS URLs → Open in browser
- **FILE**: File paths → Open in editor (new tmux window)
- **GIT**: Git commit hashes → Show commit details
- **IP**: IPv4 addresses → Copy to clipboard

## Requirements

- **fzf**: Fuzzy finder for interactive selection
- **tmux**: For tmux integration
- **Python 3.14+**: Core logic
- **uv**: Python package manager

## Development

### Run tests

```bash
uv run pytest -v
```

### Run checks

```bash
prek  # Runs pre-commit hooks
```

### Project Structure

```
tmux-pick/
├── tmux_pick/
│   ├── __init__.py
│   ├── __main__.py      # CLI entry point (single call to main)
│   └── core.py          # All business logic
├── bin/
│   └── pattern_select   # Bash wrapper for uv
├── tests/
│   └── test_parser.py   # Parameterized tests
├── pick.tmux            # TPM plugin entry
└── tmux-pick            # Main bash orchestrator
```

## License

MIT
