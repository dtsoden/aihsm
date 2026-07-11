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

if ! python3 -m secret_harness.installer install-hook; then
  echo "Hook install failed. Aborting." >&2
  exit 1
fi

if ! command -v vault >/dev/null 2>&1; then
  SCRIPTS="$(python3 -c 'import sysconfig; print(sysconfig.get_path("scripts","posix_user"))' 2>/dev/null || true)"
  if [ -n "$SCRIPTS" ] && [ -d "$SCRIPTS" ]; then
    case ":${PATH}:" in
      *":${SCRIPTS}:"*) ;;
      *)
        added=0
        # Cover login and interactive shells on both Linux and macOS:
        # bash logins read .bash_profile, zsh logins read .zprofile.
        for RC in "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bashrc" \
                  "$HOME/.zprofile" "$HOME/.zshrc"; do
          if [ -f "$RC" ] && ! grep -qF "$SCRIPTS" "$RC"; then
            printf '\n# Added by Claude-Secret-Harness installer\nexport PATH="%s:$PATH"\n' "$SCRIPTS" >> "$RC"
            added=1
          fi
        done
        if [ "$added" -eq 1 ]; then
          echo "Added $SCRIPTS to your shell profile so 'vault' works."
          echo "Open a new terminal, or run 'source ~/.profile', for 'vault' to be available."
        else
          echo "Note: 'vault' is not on PATH and no shell profile was found to update. Run it as:  python3 -m secret_harness.vault"
        fi
        ;;
    esac
  fi
fi

echo "Done. Store a secret with:  vault put my-key"
