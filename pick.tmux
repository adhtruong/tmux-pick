#!/usr/bin/env bash
# pick.tmux - TPM plugin entry point

CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default key binding
default_key="u"
key_binding=$(tmux show-option -gqv @pick-key)
key_binding=${key_binding:-$default_key}

# Get config path from tmux option (required)
config_path=$(tmux show-option -gqv @pick-config)
if [[ -z "$config_path" ]]; then
	tmux display-message "Error: @pick-config not set"
	exit 1
fi

# Set up key binding with config path
tmux bind-key "$key_binding" run-shell "PATTERN_CONFIG='$config_path' $CURRENT_DIR/tmux-pick"
