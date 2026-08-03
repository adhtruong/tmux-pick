#!/usr/bin/env bash
# pick.tmux - TPM plugin entry point

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default key binding
default_key="u"
key_binding=$(tmux show-option -gqv @pick-key)
key_binding=${key_binding:-$default_key}

# @pick-config is optional; if unset Python falls back to ~/.config/tmux-pick.toml
# then to the bundled default config
config_path=$(tmux show-option -gqv @pick-config)
if [[ -n "$config_path" ]]; then
	tmux bind-key "$key_binding" run-shell "PATTERN_CONFIG='$config_path' $CURRENT_DIR/tmux-pick"
else
	tmux bind-key "$key_binding" run-shell "$CURRENT_DIR/tmux-pick"
fi
