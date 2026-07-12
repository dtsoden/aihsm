<p align="center">
  <img src="Logo.png" alt="aihsm logo" width="180">
</p>

# AIHSM - (AI Harness Manager)

AI Harness Secret Manager: keep API keys out of Claude Code and in your OS credential vault.

aihsm stops secrets (API keys, tokens, passwords, connection strings) from
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

aihsm is not the only tool in this space. For an honest look at how it stacks up against the
alternatives, with the pros and cons of each, see [how aihsm compares](#how-aihsm-compares).

## The core policy

* Secrets get into the system only through `aihsm put`, from a hidden prompt, never by
  being pasted into chat.

* Stored values are never printed by any command in this tool. There is no `aihsm show`
  or `aihsm get`. If you need to see a value, open your OS credential manager yourself.
  Each secret is filed there under the name `<yourname>@aihsm`, the same on Windows,
  macOS, and Linux. On macOS, open Keychain Access and look under the **Passwords**
  category (or type `aihsm` in the search box); the entry is easy to miss otherwise.
  On Windows it is under Credential Manager, Windows Credentials, Generic Credentials.

* When a command needs a secret at runtime, `aihsm run` injects it and masks the value out
  of that command's output, so the key does not surface in the chat even if the command
  tries to print it.

* Anything that has already been typed into a chat message is compromised, whether the
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

The installer checks that Python 3 is present, installs the package and the `aihsm` CLI,
registers the `UserPromptSubmit` hook in your Claude Code settings (backing up the existing
settings file first, never overwriting your other hooks), copies the accompanying skill so
Claude knows the rules around it, and adds the `aihsm` command to your PATH. If Python is
missing or the install fails, it stops and tells you what to fix rather than half-installing.
The same steps run on Windows, macOS, and Linux.

On Linux, the OS vault is the Secret Service, so you need a keyring backend running
(GNOME Keyring or KWallet). Most desktop Linux installs already have one. On a headless or
minimal box without it, storing a secret will fail with a clear message telling you what to
install.

When it finishes, the installer runs a self-check: it feeds a fake secret to the hook and
confirms it gets blocked, printing `Hook self-check passed`. So a clean install has already
proven the guard works. The hook takes effect in new Claude Code sessions, so restart Claude
Code if it is open, then to see it yourself paste a fake key like `ghp_` followed by a run of
random letters and numbers into a message: it should be blocked before Claude sees it. From
then on, store real secrets with `aihsm put <name>` and refer to them by name.

To re-check later that the hook is still registered, look in `~/.claude/settings.json` for a
`UserPromptSubmit` entry whose command ends in `-m aihsm.detect`. Every block also appends a
line to `~/.claude/aihsm/logs/aihsm.log` (the rule name, never the secret), so a fresh
`blocked prompt` line there confirms the hook fired.

### Install as a Claude Code plugin

The install script is one way in. The other is the Claude Code plugin, if you would rather
enable it from inside Claude Code than run a script. From a Claude Code session:

```
/plugin marketplace add dtsoden/aihsm
/plugin install aihsm@aihsm
```

This registers the same `UserPromptSubmit` guard and copies the same skill, so pasted secrets
get blocked the moment the plugin is enabled. The detector is pure Python standard library, so
it runs straight from the plugin with nothing else to install. Python 3 still has to be on your
PATH, and you restart Claude Code once so the hook takes effect in a new session.

There is one difference from the script install. The plugin gives you the guard and the skill,
not the vault commands. `aihsm put`, `aihsm run`, and `aihsm list` come from the Python package,
which the plugin does not install. Run the install script above to get them; the guard and the
CLI are happy to sit side by side. If you only want the paste guard and you keep your secrets
in your OS credential manager by hand, the plugin on its own is enough.

## Usage

Store a secret. You give the name on the command line; the value is never passed as an
argument (that would leave it in your shell history). You are prompted for the value twice,
hidden both times, so a typo can't be saved by mistake. Nothing shows as you type or paste,
which is normal; when it saves, it confirms how many characters it stored so you know your
paste landed.

```bash
aihsm put github-token
```

Run a command with a secret injected into its environment, without ever printing it:

```bash
aihsm run --set GITHUB_TOKEN=github-token -- gh api /user
```

`aihsm run` puts the secret into the child command's environment and redacts it from
everything that command prints. If the command echoes the value in a debug line, an error,
or a full `printenv` dump, it comes back as `****`, so the raw key does not land in the
transcript Claude reads. This holds even when several stored secrets overlap each other or a
value is split across the output stream. The one thing it cannot catch is a value the
command transforms before printing it (base64-encoding it, for example); the accompanying
skill still tells the model never to echo a secret, as a second layer.

If `aihsm` is not found right after install, open a new terminal window: the PATH change
only takes effect in new shells. The installer prints the full path to the command at the
end if you ever need to run it directly.

List what is stored, by name only. This checks your OS vault directly, so if you remove an
entry in your OS credential manager, `aihsm list` stops showing it:

```bash
aihsm list
```

Remove an entry:

```bash
aihsm rm github-token
```

## Using a stored secret in a Claude Code prompt

This is the part that changes your habit. You never paste the key into the chat. You refer
to it by the name you gave it, and let Claude pull it from the vault for you.

Say you stored a token with `aihsm put github-token`. In a prompt, you just name it:

> Use my github-token from the vault to list my GitHub repositories.

Claude runs the command through `aihsm run`, which reads the secret from the OS vault,
puts it into that command's environment, and masks it out of the output:

```bash
aihsm run --set GITHUB_TOKEN=github-token -- gh api /user/repos
```

`GITHUB_TOKEN` is the environment variable the command expects; `github-token` is the name
you stored it under. The value never appears in your message, in Claude's reply, or in the
command's output. The accompanying skill teaches Claude these rules, so it reaches for
`aihsm run` and refers to secrets by name on its own. If you forget and paste the raw key,
the hook blocks the message before it reaches Claude.

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

The tool keeps a small log at `~/.claude/aihsm/logs/` so you can see what happened
when something goes wrong: a blocked key (by type, never the value), a stored or used entry
(by name), an error. It never records a secret value, the prompt text, or a matched string.
The log cleans up after itself: it rolls over at about 1 MB and keeps four old files, so it
stays around 5 MB at most and can never grow into the hundreds of megabytes. To turn it off,
set the environment variable `AIHSM_NO_LOG` to any value.

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
credential vault: anything you stored with `aihsm put` stays there until you remove it
yourself with `aihsm rm` or your OS credential manager.

## What this does not do

aihsm protects future use. It cannot undo exposure that already happened.
If a key was typed into a chat before this tool was installed, or before a detection rule
existed to catch its shape, that key is still compromised and still needs to be rotated at
the provider. The hook is a guard against the next mistake, not a cleanup crew for the
last one.

## How aihsm compares

Plenty of tools touch this problem, and each is good at what it was built for. Here is an
honest snapshot of where aihsm sits next to the main alternatives, as of July 2026.

| Capability | sensitive-canary | vaultry / claude-secrets | 1Password op run | Doppler | aihsm |
| --- | :---: | :---: | :---: | :---: | :---: |
| Blocks keys pasted into chat | Yes | No | No | No | Yes |
| Blocks the assistant reading keys from files | Yes | Partial | No | No | No |
| Stores keys in the OS-native vault | No | Yes | Yes | No | Yes |
| Masks keys in command output | n/a | Partial | Partial | No | Yes |
| Cross-platform (Windows / macOS / Linux) | Yes | No | Yes | Yes | Yes |
| Fully open source (MIT) | Yes | No | No | No | Yes |
| Local, no cloud account | Yes | Yes | Partial | No | Yes |

The tools, so you can judge for yourself:

* [sensitive-canary](https://github.com/coo-quack/sensitive-canary) - Claude Code hooks with
  strong detection (31 rules from gitleaks and TruffleHog) and a second hook that blocks the
  assistant from reading `.env` files. Detection only; there is no vault behind it.
* [vaultry / claude-secrets](https://glama.ai/mcp/servers/vaultry/claude-secrets) - an
  encrypted store with a macOS Keychain master key and per-project allowlists. macOS only,
  and source-available rather than fully open.
* [1Password op run](https://developer.1password.com/docs/cli/secrets-environment-variables) -
  mature, cross-platform, strong team features. Needs a paid account, and its usual env
  injection can still leak the value into a chatty command's output.
* [Doppler](https://www.doppler.com) - a cloud secret manager with runtime injection.
  Cloud-hosted, account required, aimed at teams and CI.
* [HashiCorp Vault](https://www.vaultproject.io) - the enterprise standard for secrets at
  scale. Server software; heavy for one developer on a laptop.
* [gitleaks](https://github.com/gitleaks/gitleaks) and
  [TruffleHog](https://github.com/trufflesecurity/trufflehog) - the standard for finding
  secrets already committed to git. A different door: they scan code at rest, not the live
  chat channel.

aihsm is deliberately the small one: a single free cross-platform MIT tool that keeps keys
out of the chat and in your own OS vault, with no account and one command to install. It
does not try to be enterprise data-loss prevention, and it does not scan every file the
assistant reads. If that file-read path matters to you, sensitive-canary is the better
answer there, and the two can run side by side.
