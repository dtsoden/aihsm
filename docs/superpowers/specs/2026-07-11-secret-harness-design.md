# Claude-Secret-Harness — Design

Date: 2026-07-11
Status: Approved design, pre-implementation
Repo: github.com/dtsoden/Claude-Secret-Harness (public, MIT)

## Problem

When working in Claude Code, it is easy to paste an API key, password, token, or connection string straight into the chat. The moment that happens the secret is exposed: it lives in the transcript and may be synced or logged. The habit is the risk. This project makes that mistake hard to commit and pushes every secret into the operating system's own credential vault instead, where it belongs.

## Goals

- Catch secrets the instant they are typed into a Claude Code message, on every message, deterministically.
- Stop the message before Claude processes it and tell the human to rotate the exposed key and store the new one in the OS vault by name.
- Keep all real secrets in the OS credential vault (Windows Credential Manager, macOS Keychain, Linux Secret Service) and let Claude use them by name without ever printing the value.
- Ship as a public, cloneable tool that a stranger can install on Windows, macOS, or Linux from a README, so it can anchor a LinkedIn article.
- Break the habit. The tool exists to change behavior, not just to catch one leak.

## Non-goals

- Scanning files on disk or git history for secrets. Scope is the Claude Code chat input only.
- Managing secret rotation at the provider. The tool tells the human to rotate; it does not call provider APIs.
- Acting as a general password manager. It is a thin, named interface over the OS vault, nothing more.
- Protecting a secret that has already been typed into the chat. Once typed, it is compromised and must be rotated. The tool protects future use, not past exposure.

## Core policy (non-negotiable)

1. Secrets enter the vault through one door only: a hidden terminal prompt, never the chat.
2. Claude never prints a stored secret value to the transcript.
3. To view a stored value, the human opens the OS's own credential manager. Claude is never a display surface for secrets.
4. Any secret that reached the chat is treated as compromised. The standing instruction is rotate first, then store the new value.
5. Credentials take priority over convenience. If the guard cannot verify a message is clean, it blocks (fail closed).

## Architecture

Three cooperating pieces, installed per machine into the user's Claude config directory (`~/.claude/` on macOS/Linux, `%USERPROFILE%\.claude\` on Windows). One shared Python codebase.

### Language choice: Python + keyring

A single implementation, not one per OS. Python's `keyring` library already maps a uniform API onto Windows Credential Manager, macOS Keychain, and Linux Secret Service, so there is no hand-written storage backend per platform. The detector's regex and entropy math are simple in Python. The installer writes the correct interpreter invocation (`python` vs `python3`) and shell into settings.json per OS.

### Piece 1: The detection hook (`detect.py`)

Registered under `hooks.UserPromptSubmit` in `~/.claude/settings.json`. This event has no matcher and fires on every prompt before Claude sees it, which is exactly the deterministic tripwire this needs. Verified against Claude Code hook docs:

- Blocking is done by exiting with code 2. The prompt is erased, Claude never sees it, and the hook's stderr is shown to the human as an error message. The conversation continues.
- The hook cannot rewrite the prompt text, only allow, block, or add context. This is why "redact and continue" was rejected as impossible.
- Input arrives as JSON on stdin with fields including `prompt`, `session_id`, `prompt_id`, `transcript_path`, `cwd`, `permission_mode`, `hook_event_name`.
- Default timeout is 30 seconds. The detector must run well under that.

Logic per message:

1. Read JSON from stdin, extract `prompt`.
2. If the prompt begins with the bypass token `!secret-ok`, allow it: exit 0. Also record a salted hash of any strings the detector would have flagged, so the same strings never flag again (see Learning).
3. Run detection over the prompt text.
4. For each candidate found, check its salted hash against the local allowlist. Drop any that match.
5. If any candidates survive, block: exit 2 with the secret-detected message on stderr.
6. Otherwise allow: exit 0, silent.

Failure mode is fail closed. If the detector throws, cannot be launched because Python is missing, or hits any unexpected error, it exits 2 and blocks the message. Credentials take priority over the human's flow. The detector itself depends only on the Python standard library (it does not import `keyring`; that dependency belongs to the vault), which keeps its failure surface small. The block message in this case is different from the secret-detected message: it explains that the guard itself failed, how to fix it, and if it cannot be fixed, the exact steps to uninstall, printed on disk and linked to the uninstall section of the GitHub repo. The human is never trapped; they either fix the guard or make the conscious choice to remove it. Because fail closed means a missing interpreter would bounce every message, the installer verifies Python is present before it enables the hook, and verifies `keyring` too so the vault works on first use.

### Piece 2: The vault CLI (`vault`)

A small command-line tool put on the user's PATH by the installer. Subcommands:

- `vault put NAME` — reads the secret from a hidden terminal prompt (`getpass`, no echo, never the chat) and writes it to the OS vault under NAME. The only way secrets enter the vault.
- `vault run --set VAR=NAME [--set VAR2=NAME2 ...] -- <command> [args]` — reads the named secrets from the vault, puts them into the child process's environment, and runs the command. The value is never printed to stdout or the transcript. This is how Claude uses a secret without seeing it.
- `vault list` — lists stored entry names (names only, never values).
- `vault rm NAME` — deletes an entry.
- `vault allow-last` (optional helper) — adds the most recently dismissed false-positive string's hash to the allowlist, for the case where the human wants to remember without re-sending. Primary learning path is the `!secret-ok` token; this is a convenience.

There is deliberately no `vault get` that prints a value to stdout. Removing it removes the temptation and the accident. To read a value, the human uses the OS credential manager UI.

If the OS vault backend is unavailable (for example a headless Linux box with no Secret Service), `vault` fails with a clear message naming the missing backend and how to install it.

### Piece 3: The skill (`SKILL.md`)

Installed into `~/.claude/skills/secret-harness/`. It teaches Claude the standing rules so behavior is consistent across sessions:

- Never ask the human to paste a raw secret. If a task needs one, ask them to store it with `vault put NAME` and tell you the name.
- Always refer to secrets by their vault name.
- Use `vault run` to inject secrets into commands. Never run anything that prints a value.
- Never display a stored value. If the human wants to see it, point them at Keychain Access (macOS) or Credential Manager (Windows).
- If a secret ever appears in the chat, treat it as compromised: tell the human to rotate it at the provider first, then store the new value.

## Detection ruleset

Aggressive by design, per the requirement to catch as much as possible while keeping the human in the loop through the bypass. Two layers:

1. Known shapes (high confidence): provider-prefixed tokens (`sk-`, `sk-ant-`, `ghp_`, `gho_`, `github_pat_`, `AKIA`, `ASIA`, `xox[baprs]-`, Google `AIza`, Slack, Stripe `sk_live_`/`rk_live_`), PEM private-key blocks (`-----BEGIN ... PRIVATE KEY-----`), JWTs (three base64url segments separated by dots), and database connection strings with embedded credentials (`scheme://user:password@host`).
2. High-entropy catch-all: any token of sufficient length whose Shannon entropy crosses a threshold, to catch keys with no recognizable prefix. This layer is what produces occasional false positives on hashes, UUIDs, and non-secret base64. That cost is accepted in exchange for coverage; the bypass and learning absorb it.

The ruleset lives in one place (`patterns.py` or a `patterns.json` the detector reads) so it is easy to audit and extend.

## The messages the human sees

### On a detected secret (deliberate block)

```
Secret detected (matched: <rule name>).
It is now in this transcript, so treat it as compromised.

Do this:
  1. Revoke or rotate it at the provider now.
  2. Store the new one:  vault put <suggested-name>
  3. Re-send your message, referring to it by name.

False alarm? Re-send your message starting with !secret-ok and this
exact string will stop being flagged.
```

### On a guard failure (fail-closed block)

```
Secret-Harness guard could not run, so your message was blocked to
protect any credentials it might contain.

What broke: <error summary, e.g. Python not found / keyring missing>

Fix it:
  <specific remediation for the detected cause>

Can't fix it right now? Remove the guard:
  <exact uninstall command for this OS>
  Full uninstall guide: https://github.com/dtsoden/Claude-Secret-Harness#uninstall
```

## Learning (false-positive memory)

When the human dismisses with `!secret-ok`, the detector computes a salted SHA-256 hash of each flagged string and stores the hashes in `~/.claude/secret-harness/allowlist.json`. The salt is generated once at install time and kept in the same directory. Only hashes are stored, never the strings themselves, so the allowlist can never leak a secret. On future messages, any candidate whose salted hash is in the allowlist passes silently. One-off random false positives (a fresh UUID) never recur, so this mainly silences repeat offenders such as a specific public key or a fixed test fixture.

## Distribution and install

Public MIT repo `dtsoden/Claude-Secret-Harness`. Two installers driven by a shared file layout:

- `install.sh` (macOS/Linux) and `install.ps1` (Windows).
- Each installer: detect OS, confirm Python 3 and install the `keyring` dependency, copy the Python package into `~/.claude/secret-harness/`, generate the per-install salt, merge the `UserPromptSubmit` hook into `~/.claude/settings.json` after backing that file up (never clobber an existing config), install the skill into `~/.claude/skills/secret-harness/`, and put `vault` on PATH via a small shim.
- The installer refuses to enable the hook if Python or `keyring` is missing, since fail-closed would otherwise bounce every message. It reports what to install and stops.
- `uninstall.sh` / `uninstall.ps1` reverse every step and restore the settings.json backup. The uninstall steps are also documented in the README so a trapped user can recover by hand.

README covers: what it does and why, the core policy, one-line install per OS, how to store and use a secret, how false positives and `!secret-ok` work, how to uninstall, and the security caveat that anything already typed must be rotated.

CI (GitHub Actions) runs the test suite on Windows, macOS, and Linux runners.

## Testing

- Unit tests (pytest) for the detector: each known pattern matches, entropy threshold behaves, bypass token allows and records, allowlist hits pass, clean text passes, malformed stdin fails closed.
- Vault round-trip tests per OS: `put` then `run` then `rm`, asserting values are never written to stdout.
- Hook integration tests: feed sample JSON payloads to `detect.py` and assert exit codes (0 vs 2) and message content.
- Installer tests: settings.json merge preserves existing hooks and is reversible by the uninstaller.

## Repo layout (proposed)

```
Claude-Secret-Harness/
  README.md
  LICENSE                     # MIT
  install.sh
  install.ps1
  uninstall.sh
  uninstall.ps1
  secret_harness/
    __init__.py
    detect.py                 # the hook entry point
    patterns.py               # detection ruleset
    vault.py                  # the vault CLI
    allowlist.py              # salted-hash learning store
    messages.py               # the human-facing block messages
  skills/
    secret-harness/
      SKILL.md
  tests/
    test_detect.py
    test_vault.py
    test_allowlist.py
    test_install.py
  docs/
    superpowers/specs/2026-07-11-secret-harness-design.md
  .github/workflows/ci.yml
```

## Decisions locked during design

- Surface: global, installed per machine, all projects.
- Hook action on detection: block the turn (exit 2).
- Store path: human runs `vault put`, hidden input, never the chat.
- Retrieval: never print; inject via `vault run`; to view, use the OS manager.
- Detection: aggressive (known shapes + entropy) with `!secret-ok` bypass.
- Failure mode: fail closed, with a guard-failure message that always carries fix and uninstall instructions.
- Learning: `!secret-ok` allows once and remembers via salted hash.
- Repo: `dtsoden/Claude-Secret-Harness`, public, MIT.
