#!/usr/bin/env bash
set -euo pipefail

echo "Installing aihsm..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found. Install Python 3 and re-run." >&2
  exit 1
fi

if ! python3 -m pip install --user .; then
  echo "pip install failed. If you saw 'externally-managed-environment', install with pipx ('pipx install .') or inside a virtualenv instead. See the README Install section." >&2
  exit 1
fi

SKILL_DIR="$HOME/.claude/skills/aihsm"
mkdir -p "$SKILL_DIR"
cp "skills/aihsm/SKILL.md" "$SKILL_DIR/SKILL.md"

if ! python3 -m aihsm.installer install-hook; then
  echo "Hook install failed. Aborting." >&2
  exit 1
fi

PRIMARY_RC=""
if ! command -v aihsm >/dev/null 2>&1; then
  SCRIPTS="$(python3 -c 'import sysconfig; print(sysconfig.get_path("scripts","posix_user"))' 2>/dev/null || true)"
  if [ -n "$SCRIPTS" ] && [ -d "$SCRIPTS" ]; then
    case ":${PATH}:" in
      *":${SCRIPTS}:"*) ;;
      *)
        LINE="export PATH=\"$SCRIPTS:\$PATH\""
        # Pick the startup file for the user's actual login shell, and CREATE
        # it if it does not exist. A fresh macOS account often has no ~/.zshrc
        # yet, so writing only to files that already exist would silently do
        # nothing. zsh (the macOS default) reads ~/.zshrc for interactive shells.
        case "$(basename "${SHELL:-/bin/sh}")" in
          zsh)  PRIMARY_RC="$HOME/.zshrc" ;;
          bash) if [ -f "$HOME/.bash_profile" ]; then PRIMARY_RC="$HOME/.bash_profile"; else PRIMARY_RC="$HOME/.profile"; fi ;;
          *)    PRIMARY_RC="$HOME/.profile" ;;
        esac
        if [ ! -f "$PRIMARY_RC" ] || ! grep -qF "$SCRIPTS" "$PRIMARY_RC"; then
          printf '\n# Added by aihsm installer\n%s\n' "$LINE" >> "$PRIMARY_RC"
        fi
        # Also update any other common startup files that already exist, so a
        # different shell picks it up too. Harmless if redundant.
        for RC in "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bashrc" \
                  "$HOME/.zprofile" "$HOME/.zshrc"; do
          if [ "$RC" != "$PRIMARY_RC" ] && [ -f "$RC" ] && ! grep -qF "$SCRIPTS" "$RC"; then
            printf '\n# Added by aihsm installer\n%s\n' "$LINE" >> "$RC"
          fi
        done
        # Make it available in THIS shell too, in case the script is sourced.
        export PATH="$SCRIPTS:$PATH"
        echo "Added $SCRIPTS to your PATH via $PRIMARY_RC."
        ;;
    esac
  else
    echo "Note: could not locate the scripts directory. Run aihsm as:  python3 -m aihsm.cli"
  fi
fi

echo ""
echo "Done."
if [ -n "$PRIMARY_RC" ]; then
  echo "IMPORTANT: open a NEW terminal window, then run:  aihsm put my-key"
  echo "(or, in this same window, run:  source $PRIMARY_RC  then  aihsm put my-key)"
else
  echo "Store a secret with:  aihsm put my-key"
fi
