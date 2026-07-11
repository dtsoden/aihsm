#!/usr/bin/env bash
set -euo pipefail

echo "Installing Claude-Secret-Harness..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found. Install Python 3 and re-run." >&2
  exit 1
fi

if ! python3 -m pip install --user .; then
  echo "pip install failed. If you saw 'externally-managed-environment', install with pipx ('pipx install .') or inside a virtualenv instead. See the README Install section." >&2
  exit 1
fi

SKILL_DIR="$HOME/.claude/skills/secret-harness"
mkdir -p "$SKILL_DIR"
cp "skills/secret-harness/SKILL.md" "$SKILL_DIR/SKILL.md"

python3 -m secret_harness.installer install-hook

if ! command -v vault >/dev/null 2>&1; then
  echo "Note: 'vault' is not on your PATH. Add your Python user scripts directory to PATH, or run it as:  python3 -m secret_harness.vault"
fi

echo "Done. Store a secret with:  vault put my-key"
