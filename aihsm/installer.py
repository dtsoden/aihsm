import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional

from aihsm import log


def hook_command() -> str:
    return '"{0}" -m aihsm.detect'.format(sys.executable)


def _load(settings_path: Path) -> dict:
    if settings_path.exists():
        try:
            return dict(json.loads(settings_path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError, TypeError):
            return {}
    return {}


def _write(settings_path: Path, data: dict) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def merge_hook(settings_path: Path, command: str, timeout: int = 30) -> None:
    # Claude Code requires each UserPromptSubmit entry to be a group object whose
    # own "hooks" key is an array of command objects. A flat {type, command}
    # object at the top level is rejected with a schema error. We also scrub any
    # legacy flat entry of our own so re-running repairs a settings file that an
    # older, buggy version of this installer left in the broken shape.
    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.with_name(settings_path.name + ".bak"))
    data = _load(settings_path)
    hooks = data.setdefault("hooks", {})
    existing = hooks.get("UserPromptSubmit")
    if not isinstance(existing, list):
        existing = []

    cleaned = []
    for entry in existing:
        if not isinstance(entry, dict):
            cleaned.append(entry)
            continue
        # Drop our own legacy flat entry (old broken format).
        if entry.get("type") == "command" and entry.get("command") == command:
            continue
        # Drop any group that already holds our command; we re-add a fresh one.
        sub = entry.get("hooks")
        if isinstance(sub, list) and any(
            isinstance(h, dict) and h.get("command") == command for h in sub
        ):
            continue
        cleaned.append(entry)

    cleaned.append({"hooks": [{"type": "command", "command": command, "timeout": timeout}]})
    hooks["UserPromptSubmit"] = cleaned
    _write(settings_path, data)


def remove_hook(settings_path: Path, command: str) -> None:
    data = _load(settings_path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict) or not isinstance(hooks.get("UserPromptSubmit"), list):
        return
    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.with_name(settings_path.name + ".bak"))
    result = []
    for entry in hooks["UserPromptSubmit"]:
        if not isinstance(entry, dict):
            result.append(entry)
            continue
        # Drop our own legacy flat entry.
        if entry.get("type") == "command" and entry.get("command") == command:
            continue
        sub = entry.get("hooks")
        if isinstance(sub, list):
            kept = [
                h for h in sub
                if not (isinstance(h, dict) and h.get("command") == command)
            ]
            if not kept:
                continue  # group emptied by the removal, drop the whole group
            new_entry = dict(entry)
            new_entry["hooks"] = kept
            result.append(new_entry)
        else:
            result.append(entry)
    hooks["UserPromptSubmit"] = result
    _write(settings_path, data)


def _settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    action = argv[0] if argv else ""
    if action == "install-hook":
        try:
            import keyring  # noqa: F401
        except ImportError:
            log.error("install aborted: keyring not importable")
            sys.stderr.write(
                "keyring is not installed. Run: python -m pip install --user keyring\n"
            )
            return 1
        merge_hook(_settings_path(), hook_command())
        log.info("hook installed")
        sys.stdout.write("aihsm hook installed.\n")
        return 0
    if action == "uninstall-hook":
        remove_hook(_settings_path(), hook_command())
        log.info("hook removed")
        sys.stdout.write("aihsm hook removed.\n")
        return 0
    if action == "selfcheck":
        # Drive the detector through a subprocess so the test input is delivered
        # as clean UTF-8 (shell string piping can mangle the encoding) and so the
        # detector's stderr never trips a shell error-handling mode. The detector
        # exits 2 when it blocks a secret.
        import subprocess

        result = subprocess.run(
            [sys.executable, "-m", "aihsm.detect"],
            input='{"prompt":"ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}',
            capture_output=True,
            text=True,
        )
        if result.returncode == 2:
            sys.stdout.write("Hook self-check passed: a test secret was blocked.\n")
            return 0
        sys.stdout.write(
            "WARNING: the hook did not block a test secret (exit {0}).\n".format(result.returncode)
        )
        return 1
    sys.stderr.write(
        "Usage: python -m aihsm.installer [install-hook|uninstall-hook|selfcheck]\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
