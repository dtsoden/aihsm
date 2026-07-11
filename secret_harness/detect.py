import json
import sys
from pathlib import Path
from typing import Tuple

from secret_harness import messages
from secret_harness.allowlist import AllowList, get_or_create_salt
from secret_harness.patterns import find_secrets

BYPASS_TOKEN = "!secret-ok"


def _default_config_dir():
    return Path.home() / ".claude" / "secret-harness"


def _suggested_name(rule):
    return "my-secret" if rule == "high-entropy" else rule


def run(payload, config_dir):
    # type: (dict, Path) -> Tuple[int, str]
    prompt = payload.get("prompt") or ""
    salt = get_or_create_salt(config_dir / "salt")
    allow = AllowList(config_dir / "allowlist.json", salt)
    findings = find_secrets(prompt)

    if prompt.lstrip().startswith(BYPASS_TOKEN):
        for finding in findings:
            allow.add(finding.value)
        return (0, "")

    active = [f for f in findings if not allow.contains(f.value)]
    if active:
        first = active[0]
        return (2, messages.secret_detected_message(first.rule, _suggested_name(first.rule)))
    return (0, "")


def main():
    # type: () -> None
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        code, msg = run(payload, _default_config_dir())
        if msg:
            sys.stderr.write(msg + "\n")
        sys.exit(code)
    except SystemExit:
        raise
    except Exception as exc:  # fail closed
        sys.stderr.write(
            messages.guard_failure_message(
                error_summary="{0}: {1}".format(type(exc).__name__, exc),
                remediation="Re-run the installer, or confirm Python 3 is installed and on PATH.",
                uninstall_cmd="Run the uninstall script from the repo (see link below).",
            )
            + "\n"
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
