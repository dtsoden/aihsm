#!/usr/bin/env bash
set -euo pipefail

echo "Installing aihsm..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found. Install Python 3 and re-run." >&2
  exit 1
fi

APP_DIR="$HOME/.aihsm"
VENV="$APP_DIR/venv"
BIN_LINK_DIR="$HOME/.local/bin"

# Install into a dedicated virtual environment rather than with 'pip --user'.
# The system python on macOS (the Xcode Command Line Tools build) does not
# reliably honor --user installs, and Homebrew/modern Linux pythons refuse
# --user under PEP 668. A venv carries its own working pip and sidesteps all
# of that, on every OS.
echo "Creating an isolated environment at $VENV ..."
rm -rf "$VENV"
if ! python3 -m venv "$VENV"; then
  echo "Failed to create a virtual environment with 'python3 -m venv'." >&2
  echo "Your python3 may be missing the venv module. Install it and re-run." >&2
  exit 1
fi

echo "Installing the package ..."
"$VENV/bin/python" -m pip install --upgrade pip >/dev/null 2>&1 || true
if ! "$VENV/bin/python" -m pip install . ; then
  echo "pip install failed inside the environment. See the output above for why." >&2
  exit 1
fi

if [ ! -x "$VENV/bin/aihsm" ]; then
  echo "Install finished but the aihsm command was not created. Aborting." >&2
  exit 1
fi

# Copy the skill so Claude knows the rules.
SKILL_DIR="$HOME/.claude/skills/aihsm"
mkdir -p "$SKILL_DIR"
cp "skills/aihsm/SKILL.md" "$SKILL_DIR/SKILL.md"

# Register the hook using the venv's python, so the hook can import aihsm.
if ! "$VENV/bin/python" -m aihsm.installer install-hook; then
  echo "Hook install failed. Aborting." >&2
  exit 1
fi

# Expose the aihsm command on PATH via a symlink in ~/.local/bin. We link only
# the aihsm executable, not the whole venv bin, so we never shadow your python.
mkdir -p "$BIN_LINK_DIR"
ln -sf "$VENV/bin/aihsm" "$BIN_LINK_DIR/aihsm"

# Make sure ~/.local/bin is on PATH for the user's login shell, creating the
# startup file if it does not exist yet (a fresh macOS account has no ~/.zshrc).
PRIMARY_RC=""
case ":${PATH}:" in
  *":${BIN_LINK_DIR}:"*) ;;
  *)
    LINE="export PATH=\"$BIN_LINK_DIR:\$PATH\""
    case "$(basename "${SHELL:-/bin/sh}")" in
      zsh)  PRIMARY_RC="$HOME/.zshrc" ;;
      bash) if [ -f "$HOME/.bash_profile" ]; then PRIMARY_RC="$HOME/.bash_profile"; else PRIMARY_RC="$HOME/.profile"; fi ;;
      *)    PRIMARY_RC="$HOME/.profile" ;;
    esac
    if [ ! -f "$PRIMARY_RC" ] || ! grep -qF "$BIN_LINK_DIR" "$PRIMARY_RC"; then
      printf '\n# Added by aihsm installer\n%s\n' "$LINE" >> "$PRIMARY_RC"
    fi
    for RC in "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bashrc" \
              "$HOME/.zprofile" "$HOME/.zshrc"; do
      if [ "$RC" != "$PRIMARY_RC" ] && [ -f "$RC" ] && ! grep -qF "$BIN_LINK_DIR" "$RC"; then
        printf '\n# Added by aihsm installer\n%s\n' "$LINE" >> "$RC"
      fi
    done
    export PATH="$BIN_LINK_DIR:$PATH"
    ;;
esac

echo ""
echo "======================================================"
if "$BIN_LINK_DIR/aihsm" --help >/dev/null 2>&1; then
  echo "SUCCESS: aihsm is installed and verified working."
  echo "Command: $BIN_LINK_DIR/aihsm"
  if [ -n "$PRIMARY_RC" ]; then
    echo ""
    echo "Open a NEW terminal window, then run:  aihsm put my-key"
    echo "(or in this window:  source $PRIMARY_RC  then  aihsm put my-key)"
  else
    echo "Run:  aihsm put my-key"
  fi
else
  echo "aihsm installed to $VENV but did not run. Please copy this output to me."
fi
echo "======================================================"
