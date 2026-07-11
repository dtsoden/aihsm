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

The installer registers the `UserPromptSubmit` hook in your Claude Code settings, installs
the `vault` CLI, and copies the accompanying skill so Claude knows the rules around it.

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

`vault run` puts the secret into the child command's environment; it does not stop that
command from printing the secret itself, say, in a debug log or an error message. Keeping
the child command quiet about the value it was given is a rule for the model to follow, set
out in the accompanying skill, not something the code can enforce.

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
