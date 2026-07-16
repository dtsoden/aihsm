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

There are three ways to install aihsm, and they do not all give you the same thing. Pick from
this table first, then follow that one section.

| | Paste guard (the hook) | Skill | Vault CLI (`put` / `run` / `list` / `rm`) |
| --- | :---: | :---: | :---: |
| **1. Install script** (recommended) | yes | yes | yes |
| **2. Claude Code plugin** | yes | yes | no |
| **3. pipx / pip** | no | no | yes |

The install script is the only single path that gives you everything. The plugin is the quickest
way to get the guard, but it does not include the `aihsm` command. pipx installs the `aihsm`
command and nothing else, so on its own it protects nothing; use it to add the CLI on top of a
plugin install, or if the vault is all you want.

All three need Python 3. If you do not have it, install it from
[python.org](https://www.python.org/downloads/), or `brew install python` on macOS, then confirm
with `python3 --version` (`python --version` on Windows).

### Option 1: Install script (recommended, gives you everything)

The scripts live in this repo, so clone it and change into the folder first:

```bash
git clone https://github.com/dtsoden/aihsm.git
cd aihsm
```

Then run the line for your OS:

```bash
# macOS / Linux
bash install.sh
```

```powershell
# Windows
.\install.ps1
```

The installer checks that Python 3 is present, installs the package and the `aihsm` CLI into a
dedicated environment of its own, registers the `UserPromptSubmit` hook in your Claude Code
settings (backing up the existing settings file first, never overwriting your other hooks),
copies the accompanying skill so Claude knows the rules around it, and adds the `aihsm` command
to your PATH. If Python is missing or the install fails, it stops and tells you what to fix
rather than half-installing. The same steps run on Windows, macOS, and Linux.

**Upgrade:**

```bash
git pull
bash install.sh          # or .\install.ps1 on Windows
```

**Uninstall:**

```bash
bash uninstall.sh        # macOS / Linux
```

```powershell
.\uninstall.ps1          # Windows
```

This removes the hook and the skill and uninstalls the package. It does not touch your OS
credential vault: anything you stored with `aihsm put` stays there until you remove it yourself
with `aihsm rm` or your OS credential manager.

### Option 2: Claude Code plugin (guard and skill, no CLI)

Use this if you would rather enable it from inside Claude Code than run a script. From a Claude
Code session:

```
/plugin marketplace add dtsoden/aihsm
/plugin install aihsm@aihsm
```

Then run `/reload-plugins`, or restart Claude Code, so the hook takes effect.

This registers the same `UserPromptSubmit` guard and the same skill, so pasted secrets get
blocked the moment the plugin is enabled. The detector is pure Python standard library, so it
runs straight from the plugin with nothing else to install. Python 3 still has to be on your PATH.

**What you do not get:** the vault commands. `aihsm put`, `aihsm run`, `aihsm list`, and
`aihsm rm` come from the Python package, which the plugin does not install. If you want them, add
Option 3 on top of this; the guard and the CLI sit side by side happily. If you only want the
paste guard and you manage secrets in your OS credential manager by hand, the plugin alone is
enough.

**Upgrade:** third-party marketplaces do not auto-update by default, so pull new versions
yourself:

```
/plugin marketplace update aihsm
/reload-plugins
```

To have it update itself instead, run `/plugin`, go to the **Marketplaces** tab, select `aihsm`,
and choose **Enable auto-update**.

**Uninstall:**

```
/plugin uninstall aihsm@aihsm
```

### Option 3: pipx (the vault CLI only, no guard)

This installs the `aihsm` command and nothing else. It does **not** register the hook, so by
itself it blocks nothing. Use it to add the vault commands to a plugin install, or if the vault
is all you want.

```bash
# macOS
brew install pipx
pipx ensurepath
pipx install aihsm
```

```bash
# Linux
python3 -m pip install --user pipx
pipx ensurepath
pipx install aihsm
```

```powershell
# Windows
pip install aihsm
```

Open a new terminal after `pipx ensurepath` so the PATH change takes effect.

On macOS, use pipx rather than `pip install aihsm`. Homebrew's Python is marked externally
managed (PEP 668), so a plain `pip install` into it fails with
`error: externally-managed-environment`. That is not a problem with your Mac, your chip, or your
OS version; it is Homebrew protecting its Python from being modified. pipx sidesteps it by giving
the tool its own environment, which is the right way to install a command-line tool anyway.
`pip install aihsm` is still fine on Windows, or inside a virtualenv you made yourself.

**Upgrade:**

```bash
pipx upgrade aihsm       # or: pip install --upgrade aihsm
```

**Uninstall:**

```bash
pipx uninstall aihsm     # or: pip uninstall aihsm
```

Uninstalling leaves your stored secrets alone. They live in your OS vault, not in the package.

### Check that the guard is working

The install script finishes with a self-check: it feeds a fake secret to the hook and confirms it
gets blocked, printing `Hook self-check passed`. So a clean script install has already proven the
guard works.

The hook takes effect in new Claude Code sessions, so restart Claude Code if it is open. To see
it for yourself, paste a fake key like `ghp_` followed by a run of random letters and numbers
into a message. It should be blocked before Claude sees it.

To re-check later that the hook is still registered: for a script install, look in
`~/.claude/settings.json` for a `UserPromptSubmit` entry whose command ends in `-m aihsm.detect`;
for a plugin install, check the `/plugin` menu. Every block also appends a line to
`~/.claude/aihsm/logs/aihsm.log` (the rule name, never the secret), so a fresh `blocked prompt`
line there confirms the hook fired.

On Linux, the OS vault is the Secret Service, so you need a keyring backend running (GNOME
Keyring or KWallet). Most desktop Linux installs already have one. On a headless or minimal box
without it, storing a secret will fail with a clear message telling you what to install.

## Usage

These commands come from the Python package, so you have them after Option 1 or Option 3.

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

Check which version you have, which is the quickest way to confirm an upgrade landed:

```bash
aihsm --version
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

Detection works two ways, and neither is a general "looks random" guess.

**Known shapes.** Anthropic and OpenAI keys, GitHub tokens and PATs, AWS access keys, Slack
tokens, Google API keys, Stripe live keys, JWTs, PEM private key blocks, and connection
strings with an embedded password. These have distinctive prefixes, so they are caught even
when pasted bare with no context.

**Credential context.** A value is flagged when the thing it is assigned to says it is a
credential: `AWS_SECRET_ACCESS_KEY=...`, `"apiKey": "..."`, `client_secret: ...`,
`DATABASE_PASSWORD=...`. This catches keys no prefix rule knows about, and it catches wordy
passwords that no randomness test would ever flag.

There is deliberately **no general high-entropy catch-all**. Earlier versions had one and it
did not work. Entropy measures character diversity, not randomness, and at real-world lengths
a camelCase name (`convertFieldsToString`, 3.82), a random id (`mI9cYRKBnsIGQv4o`, 3.88) and a
hex digest (4.0 maximum, because hex has only sixteen symbols) all sit in the same narrow band.
No threshold separates them. Every setting either blocked ordinary JSON keys, URLs and git
SHAs, or went blind to real keys. Naming solves what entropy cannot: `AWS_SECRET_ACCESS_KEY=`
is a credential whatever its entropy, and `convertFieldsToString` is not, whatever its entropy.

If the match is ever wrong, re-send the same message starting with `secret-ok` (no leading
punctuation; a leading `!` is Claude Code's own bash prefix and would run your message as a
shell command). That message goes through, and the tool remembers the flagged string as a
salted hash, not the raw value, so it will not nag you about it again.

## The log

The tool keeps a small log at `~/.claude/aihsm/logs/` so you can see what happened
when something goes wrong: a blocked key (by type, never the value), a stored or used entry
(by name), an error. It never records a secret value, the prompt text, or a matched string.
The log cleans up after itself: it rolls over at about 1 MB and keeps four old files, so it
stays around 5 MB at most and can never grow into the hundreds of megabytes. To turn it off,
set the environment variable `AIHSM_NO_LOG` to any value.

## What this does not do

aihsm protects future use. It cannot undo exposure that already happened.
If a key was typed into a chat before this tool was installed, or before a detection rule
existed to catch its shape, that key is still compromised and still needs to be rotated at
the provider. The hook is a guard against the next mistake, not a cleanup crew for the
last one.

It does not catch a bare secret pasted with no context from a provider it has no rule for.
If you paste `kD8fH3jQ7pL5xZ2vB6nM4tYrW9gC1sA0` on its own, with nothing naming it, it goes
through. That string is indistinguishable from a session id, a build hash, or a database key,
and the versions that tried to guess blocked all of those too, constantly. Label it
(`API_TOKEN=...`) and it is caught. This is a deliberate trade: a guard that cries wolf on
every URL and config file gets uninstalled, and then it protects nothing at all.

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
