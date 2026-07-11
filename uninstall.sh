#!/usr/bin/env bash
set -euo pipefail
echo "Removing aihsm..."

VENV="$HOME/.aihsm/venv"
if [ -x "$VENV/bin/python" ]; then
  "$VENV/bin/python" -m aihsm.installer uninstall-hook || true
fi

rm -f "$HOME/.local/bin/aihsm"
rm -rf "$HOME/.aihsm"
rm -rf "$HOME/.claude/skills/aihsm"

echo "Removed aihsm, its environment, and the skill. Your stored secrets remain in the OS vault."
