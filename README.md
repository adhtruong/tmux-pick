# tmux-pick

Interactive pattern matching and action execution for tmux. Extract URLs, git hashes, IP addresses, file paths, and more from your terminal output and execute context-aware actions.

## Features

- **Pattern Extraction**: Capture URLs, git commits, IP addresses, file paths from tmux panes
- **Interactive Selection**: fzf-powered interface with `[TYPE] value` display
- **Configurable Actions**: Execute shell commands based on pattern type
- **Config-Driven**: TOML configuration for patterns and actions
- **Fallback Support**: Alternative commands for cross-platform compatibility
- **Capture Groups**: Extract specific portions while matching with context

## Installation

### With TPM (Tmux Plugin Manager)

Add to `.tmux.conf`:

```tmux
set -g @plugin 'path/to/tmux-pick'
set -g @pick-config '~/.config/tmux-pick.toml'
set -g @pick-key 'u'  # Optional: customize keybinding (default: u)
```

Then press `prefix + I` to install.

### Manual

1. Clone this repository
2. Copy default config: `cp tmux_pick/config.default.toml ~/.config/tmux-pick.toml`
3. Add to `.tmux.conf`:

```tmux
set -g @pick-config '~/.config/tmux-pick.toml'
bind-key u run-shell 'path/to/tmux-pick/tmux-pick'
```

## Usage

### In Tmux

**Default keybinding**: `prefix + u`

1. Press the keybinding in a tmux pane
2. Patterns are extracted from the last 3000 lines
3. Select a pattern with fzf (`[TYPE] value` display)
4. Press Enter to execute the action

### Standalone

```bash
# Extract patterns from text (outputs value\ttype lines)
echo "Check out https://example.com" | uv run -m tmux_pick extract

# Execute an action (input format: value\ttype)
echo -e "https://example.com\tURL" | xargs -0 uv run -m tmux_pick execute
```

## Configuration

### Config File Location

Set before loading the plugin:

```tmux
set -g @pick-config '~/.config/tmux-pick.toml'
```

Or via environment variable:

```bash
PATTERN_CONFIG=~/.config/tmux-pick.toml tmux-pick
```

### Config Format

```toml
[[patterns]]
name = "URL"
regex = '''https?://[^\s<>"'()]+'''
description = "HTTP/HTTPS URLs"
action = "open_browser"
enabled = true

[[patterns]]
name = "FILE"
# Use capture group to extract just the path from surrounding context
regex = '''(?:^|\s|['"])([/~][a-zA-Z0-9._/\-~]*[a-zA-Z0-9_/\-~])'''
description = "Absolute and home-relative file paths"
action = "open_editor"
enabled = true

# Note: {value} is automatically shell-escaped - do not add extra quotes
[actions.open_browser]
command = 'open {value}'
fallback = 'xdg-open {value}'
description = "Open in default browser"

[actions.open_editor]
command = '''tmux new-window -c "#{pane_current_path}" "${EDITOR:-vim} {value}"'''
description = "Open in text editor"
```

### Pattern Fields

- **`name`**: Pattern type identifier (shown as `[NAME]` in fzf)
- **`regex`**: Regular expression (Python syntax)
  - Use capture groups `(...)` to extract specific portions
  - Use non-capturing groups `(?:...)` for context matching
  - If a capture group exists, `group(1)` is extracted; otherwise the full match is used
- **`description`**: Human-readable description
- **`action`**: Which action to execute (must match a key in `[actions]`)
- **`enabled`**: Whether this pattern is active

### Action Fields

- **`command`**: Shell command to execute. `{value}` is replaced with the matched text, automatically shell-escaped — do not wrap in extra quotes.
  - `#{pane_current_path}` expands to the tmux pane's current directory
- **`fallback`** (optional): Alternative command if the primary fails (e.g. non-macOS)
- **`description`** (optional): Human-readable description

## Default Patterns

The bundled `config.default.toml` includes:

| Pattern | Matches | Action |
|---------|---------|--------|
| **URL** | `https?://...` | Open in browser |
| **FILE** | Absolute/home paths and files with known extensions | Open in editor (sends to pane if shell is zsh, else new window) |
| **GIT** | Hex strings 7–40 chars (with negative lookaround to reduce false positives) | `git show` in new window, falls back to `git log --all \| grep` |
| **IP** | IPv4 addresses, optional `:port` | Copy to clipboard |
| **AGENT** | `cursor-agent\|claude\|agent --resume <uuid>` | Send to current pane |

Copy `tmux_pick/config.default.toml` to `~/.config/tmux-pick.toml` and customize.

## Requirements

- **fzf**: Fuzzy finder for interactive selection
- **tmux**: For tmux integration
- **Python 3.14+**: Core logic (uses stdlib `tomllib`)
- **uv**: Python package manager

## Development

```bash
uv run pytest -v   # Run tests
prek               # Run pre-commit checks (ruff, pyright)
```

### Project Structure

```
tmux-pick/
├── tmux_pick/
│   ├── __init__.py
│   ├── __main__.py          # CLI entry point
│   ├── core.py              # All business logic
│   └── config.default.toml  # Bundled default config
├── bin/
│   └── pattern_select       # Bash wrapper for uv
├── tests/
│   └── test_parser.py       # Parameterized tests including shell injection checks
├── pick.tmux                # TPM plugin entry
└── tmux-pick                # Main bash orchestrator + fzf UI
```

## License

MIT
