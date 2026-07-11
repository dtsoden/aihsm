# Claude-Secret-Harness

Claude-Secret-Harness stops secrets (API keys, tokens, passwords, connection strings) from
being typed into Claude Code.

Pasting a key into a chat window feels harmless in the moment: you need Claude to see a
value, so you paste it and move on. The problem is that the value is now sitting in a
transcript, a log, maybe a shared session, forever. The habit itself is the risk. This tool
makes that habit impossible instead of asking you to remember not to do it.

A `UserPromptSubmit` hook scans every message before it reaches the model. If the message
contains something that looks like a secret, the hook blocks it: the message never reaches
Claude at all. You get a message back telling you to rotate the exposed key and store the
new one in your operating system's credential vault (Windows Credential Manager, macOS
Keychain, or the Linux Secret Service).

## The core policy

- Secrets get into the system only through `vault put`, from a hidden prompt, never by
  being pasted into chat.
- Stored values are never printed by any command in this tool. There is no `vault show`
  or `vault get`. If you need to see a value, open your OS credential manager yourself.
- When a command needs a secret at runtime, `vault run` injects it and masks the value out
  of that command's output, so the key does not surface in the chat even if the command
  tries to print it.
- Anything that has already been typed into a chat message is compromised, whether the
  hook caught it or not. Rotate it. A key that a human or a model has seen is a key you
  should treat as burned, and no tool can undo that after the fact.

## Install

Python 3 is required. Pick the line for your OS:

```bash
# macOS / Linux
bash install.sh
```

```powershell
# Windows
.\install.ps1
```

The installer checks that Python 3 is present, installs the package and the `vault` CLI,
registers the `UserPromptSubmit` hook in your Claude Code settings (backing up the existing
settings file first, never overwriting your other hooks), and copies the accompanying skill
so Claude knows the rules around it. If Python is missing or the install fails, it stops and
tells you what to fix rather than half-installing.

Once it finishes, the hook is active in new Claude Code sessions (restart Claude Code if it
is already open). To confirm it works, paste a fake key like `ghp_` followed by a run of
random letters and numbers into a message: it should be blocked before Claude sees it. From
then on, store real secrets with `vault put <name>` and refer to them by name.

## Usage

Store a secret. You are prompted for the value; it is never echoed and never appears in
chat.

```bash
vault put github-token
```

Run a command with a secret injected into its environment, without ever printing it:

```bash
vault run --set GITHUB_TOKEN=github-token -- gh api /user
```

`vault run` puts the secret into the child command's environment and redacts it from
everything that command prints. If the command echoes the value in a debug line, an error,
or a full `printenv` dump, it comes back as `****`, so the raw key does not land in the
transcript Claude reads. This holds even when several stored secrets overlap each other or a
value is split across the output stream. The one thing it cannot catch is a value the
command transforms before printing it (base64-encoding it, for example); the accompanying
skill still tells the model never to echo a secret, as a second layer.

If `vault` is not found after install (a PATH issue), run it as a module instead:

```bash
python -m secret_harness.vault list
```

List what is stored, by name only:

```bash
vault list
```

Remove an entry:

```bash
vault rm github-token
```

## How detection works

Every prompt is checked against a set of known secret shapes before it leaves your
machine: Anthropic and OpenAI keys, GitHub tokens, AWS access keys, Slack tokens, Google
API keys, Stripe live keys, JWTs, PEM private key blocks, and connection strings with an
embedded password. Anything that does not match a known shape is still checked against a
high-entropy catch-all, so an unfamiliar-looking token gets flagged too.

Sometimes the match is wrong: a long build hash, a random test fixture, something that
just happens to look like a secret. If that happens, re-send the exact same message but
start it with `!secret-ok`. That one message goes through, and the tool remembers the
flagged string (as a salted hash, not the raw value) so it will not nag you about that
same string again.

## The log

The tool keeps a small log at `~/.claude/secret-harness/logs/` so you can see what happened
when something goes wrong: a blocked key (by type, never the value), a stored or used entry
(by name), an error. It never records a secret value, the prompt text, or a matched string.
The log cleans up after itself: it rolls over at about 1 MB and keeps four old files, so it
stays around 5 MB at most and can never grow into the hundreds of megabytes. To turn it off,
set the environment variable `SECRET_HARNESS_NO_LOG` to any value.

## Uninstall

```bash
# macOS / Linux
bash uninstall.sh
```

```powershell
# Windows
.\uninstall.ps1
```

This removes the hook and the skill and uninstalls the package. It does not touch your OS
credential vault: anything you stored with `vault put` stays there until you remove it
yourself with `vault rm` or your OS credential manager.

## What this does not do

Claude-Secret-Harness protects future use. It cannot undo exposure that already happened.
If a key was typed into a chat before this tool was installed, or before a detection rule
existed to catch its shape, that key is still compromised and still needs to be rotated at
the provider. The hook is a guard against the next mistake, not a cleanup crew for the
last one.
