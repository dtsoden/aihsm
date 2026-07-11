#!/usr/bin/env bash
set -euo pipefail

echo "Installing Claude-Secret-Harness..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found. Install Python 3 and re-run." >&2
  exit 1
fi

python3 -m pip install --user .

SKILL_DIR="$HOME/.claude/skills/secret-harness"
mkdir -p "$SKILL_DIR"
cp "skills/secret-harness/SKILL.md" "$SKILL_DIR/SKILL.md"

python3 -m secret_harness.installer install-hook

echo "Done. Store a secret with:  vault put my-key"
