#!/usr/bin/env bash
set -euo pipefail
echo "Removing aihsm..."
python3 -m aihsm.installer uninstall-hook || true
rm -rf "$HOME/.claude/skills/aihsm"
python3 -m pip uninstall -y aihsm || true
echo "Hook and skill removed. Your stored secrets remain in the OS vault."
