import json
import shutil
import sys
from pathlib import Path
from typing import List, Optional


def hook_command() -> str:
    return '"{0}" -m secret_harness.detect'.format(sys.executable)


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


def merge_hook(
    settings_path: Path, command: str, timeout: int = 30, shell: Optional[str] = None
) -> None:
    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.with_name(settings_path.name + ".bak"))
    data = _load(settings_path)
    hooks = data.setdefault("hooks", {})
    entries = hooks.setdefault("UserPromptSubmit", [])
    entry = {"type": "command", "command": command, "timeout": timeout}
    if shell:
        entry["shell"] = shell
    for existing in entries:
        if existing.get("command") == command:
            existing.clear()
            existing.update(entry)
            break
    else:
        entries.append(entry)
    _write(settings_path, data)


def remove_hook(settings_path: Path, command: str) -> None:
    data = _load(settings_path)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict) or "UserPromptSubmit" not in hooks:
        return
    if settings_path.exists():
        shutil.copy2(settings_path, settings_path.with_name(settings_path.name + ".bak"))
    entries = hooks["UserPromptSubmit"]
    hooks["UserPromptSubmit"] = [e for e in entries if e.get("command") != command]
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
            sys.stderr.write(
                "keyring is not installed. Run: python -m pip install --user keyring\n"
            )
            return 1
        merge_hook(_settings_path(), hook_command())
        sys.stdout.write("Secret-Harness hook installed.\n")
        return 0
    if action == "uninstall-hook":
        remove_hook(_settings_path(), hook_command())
        sys.stdout.write("Secret-Harness hook removed.\n")
        return 0
    sys.stderr.write("Usage: python -m secret_harness.installer [install-hook|uninstall-hook]\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
