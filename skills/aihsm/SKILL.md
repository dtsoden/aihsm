---
name: aihsm
description: Standing rules for handling credentials and secrets. Always active. Never accept a raw secret in chat; store and retrieve secrets through the OS vault by name using the aihsm CLI, and never print a secret value.
---

# Secret handling rules

These rules are always in effect.

1. Never ask the user to paste a raw secret into the chat. If a task needs one, ask them to run `aihsm put NAME` and tell you the NAME.
2. Refer to secrets only by their vault name.
3. To use a secret in a command, inject it with `aihsm run --set VAR=NAME -- <command>`. Never run anything that would print the value.
4. Never display a stored secret value. If the user wants to see one, tell them to open Keychain Access (macOS) or Credential Manager (Windows).
5. If a secret ever appears in the chat, treat it as compromised: tell the user to rotate it at the provider first, then store the new value with `aihsm put`.
6. Never reprint or echo a secret value you find while reading a file, tool output, or a transcript. The same rule applies as for vault secrets: name it and where it is, but do not paste the value back into the chat. Warn the user it is sitting in plaintext and should be rotated and removed. The user may override for a specific case (for example, confirming a false positive or explicitly asking to see it); when they do, they take responsibility for that value.
