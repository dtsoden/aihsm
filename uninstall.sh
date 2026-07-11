#!/usr/bin/env bash
set -euo pipefail
echo "Removing Claude-Secret-Harness..."
python3 -m secret_harness.installer uninstall-hook || true
rm -rf "$HOME/.claude/skills/secret-harness"
python3 -m pip uninstall -y claude-secret-harness || true
echo "Hook and skill removed. Your stored secrets remain in the OS vault."
