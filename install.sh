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
BIN_DIR=""
if ! command -v aihsm >/dev/null 2>&1; then
  # Do not guess where pip put the executable: query for it and verify it is
  # really there before touching PATH.
  CAND="$(python3 -c 'import sysconfig; print(sysconfig.get_path("scripts","posix_user"))' 2>/dev/null || true)"
  if [ -n "$CAND" ] && [ -x "$CAND/aihsm" ]; then
    BIN_DIR="$CAND"
  else
    # Fallback: search the common per-user bin locations for this interpreter.
    BIN_DIR="$(python3 - <<'PY' 2>/dev/null || true
import os, glob, sysconfig
cands = []
for scheme in ("posix_user", "posix_prefix"):
    try:
        cands.append(sysconfig.get_path("scripts", scheme))
    except Exception:
        pass
cands.append(os.path.expanduser("~/.local/bin"))
cands += glob.glob(os.path.expanduser("~/Library/Python/*/bin"))
for d in cands:
    if d and os.path.exists(os.path.join(d, "aihsm")):
        print(d)
        break
PY
)"
  fi

  if [ -n "$BIN_DIR" ] && [ -x "$BIN_DIR/aihsm" ]; then
    case ":${PATH}:" in
      *":${BIN_DIR}:"*) ;;
      *)
        LINE="export PATH=\"$BIN_DIR:\$PATH\""
        # Pick the startup file for the user's actual login shell, and CREATE
        # it if it does not exist. A fresh macOS account often has no ~/.zshrc
        # yet, so writing only to files that already exist would silently do
        # nothing. zsh (the macOS default) reads ~/.zshrc for interactive shells.
        case "$(basename "${SHELL:-/bin/sh}")" in
          zsh)  PRIMARY_RC="$HOME/.zshrc" ;;
          bash) if [ -f "$HOME/.bash_profile" ]; then PRIMARY_RC="$HOME/.bash_profile"; else PRIMARY_RC="$HOME/.profile"; fi ;;
          *)    PRIMARY_RC="$HOME/.profile" ;;
        esac
        if [ ! -f "$PRIMARY_RC" ] || ! grep -qF "$BIN_DIR" "$PRIMARY_RC"; then
          printf '\n# Added by aihsm installer\n%s\n' "$LINE" >> "$PRIMARY_RC"
        fi
        # Also update any other common startup files that already exist.
        for RC in "$HOME/.profile" "$HOME/.bash_profile" "$HOME/.bashrc" \
                  "$HOME/.zprofile" "$HOME/.zshrc"; do
          if [ "$RC" != "$PRIMARY_RC" ] && [ -f "$RC" ] && ! grep -qF "$BIN_DIR" "$RC"; then
            printf '\n# Added by aihsm installer\n%s\n' "$LINE" >> "$RC"
          fi
        done
        export PATH="$BIN_DIR:$PATH"
        echo "Found aihsm at: $BIN_DIR/aihsm"
        echo "Added it to your PATH via $PRIMARY_RC."
        ;;
    esac
  else
    echo "Could not find the installed 'aihsm' executable. Run it as:  python3 -m aihsm.cli"
  fi
fi

# Final verification: confirm aihsm actually resolves now.
echo ""
if command -v aihsm >/dev/null 2>&1; then
  echo "Done. Verified: 'aihsm' runs from $(command -v aihsm)."
  if [ -n "$PRIMARY_RC" ]; then
    echo "Open a NEW terminal window and it will be there too (this run already made it work here)."
  fi
  echo "Store a secret with:  aihsm put my-key"
elif [ -n "$PRIMARY_RC" ]; then
  echo "Done. 'aihsm' was added to your PATH via $PRIMARY_RC."
  echo "IMPORTANT: open a NEW terminal window, then run:  aihsm put my-key"
  echo "(or in this window:  source $PRIMARY_RC  then  aihsm put my-key)"
else
  echo "Done. Run aihsm as:  python3 -m aihsm.cli"
fi
