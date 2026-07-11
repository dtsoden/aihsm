# Claude-Secret-Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a cross-platform tool that blocks secrets typed into Claude Code and pushes them into the OS credential vault instead.

**Architecture:** A `UserPromptSubmit` hook (`detect.py`) scans every message and blocks (exit 2) on a detected secret. A `vault` CLI stores secrets in the OS vault via Python's `keyring` and injects them into commands without printing. A skill teaches Claude the standing rules. All Python, one codebase, installed into `~/.claude/`.

**Tech Stack:** Python 3.9+, `keyring` (OS vault abstraction), standard library only for the detector, pytest, GitHub Actions.

## Global Constraints

- Python 3.9+ (use only syntax valid on 3.9; avoid 3.10+ `X | Y` type hints in runtime code, use `Optional[...]`).
- The detector (`detect.py`, `patterns.py`, `allowlist.py`, `messages.py`) imports ONLY the Python standard library. It must never import `keyring`.
- No secret value is ever written to stdout or to any file. Only names and salted SHA-256 hashes are persisted.
- There is deliberately no command that prints a stored secret value.
- Failure mode is fail closed: any unhandled error in the detector exits 2 (blocks the message).
- Bypass token is the literal string `!secret-ok`.
- Vault service name (keyring) is `claude-secret-harness`.
- Config directory is `~/.claude/secret-harness/` (`Path.home() / ".claude" / "secret-harness"`).
- Repo: `github.com/dtsoden/Claude-Secret-Harness`, public, MIT. Author commits as the machine's configured git identity. No AI attribution in any commit or GitHub artifact.
- No em dashes in any file content or message.

---

### Task 1: Project scaffold

**Files:**
- Create: `LICENSE`
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `secret_harness/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing.
- Produces: an installable package `secret_harness` and a working pytest run. Later tasks add modules under `secret_harness/`.

- [ ] **Step 1: Write the smoke test**

```python
# tests/test_smoke.py
import secret_harness


def test_package_imports():
    assert secret_harness.__version__
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'secret_harness').

- [ ] **Step 3: Create the package and metadata**

```python
# secret_harness/__init__.py
__version__ = "0.1.0"
```

```python
# tests/__init__.py
```

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=61"]
build-backend = "setuptools.build_meta"

[project]
name = "claude-secret-harness"
version = "0.1.0"
description = "Blocks secrets typed into Claude Code and stores them in the OS credential vault."
readme = "README.md"
requires-python = ">=3.9"
license = { text = "MIT" }
authors = [{ name = "David Soden" }]
dependencies = ["keyring>=24"]

[project.optional-dependencies]
dev = ["pytest>=7"]

[project.scripts]
vault = "secret_harness.vault:main"

[tool.setuptools]
packages = ["secret_harness"]
```

```
# .gitignore
__pycache__/
*.pyc
*.egg-info/
.pytest_cache/
build/
dist/
.venv/
```

Create a placeholder `README.md` (one line) so the build backend does not choke; Task 11 fills it in:

```
# Claude-Secret-Harness
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pip install -e ".[dev]" && python -m pytest tests/ -v`
Expected: `test_package_imports` PASS.

- [ ] **Step 5: Commit**

```bash
git add LICENSE pyproject.toml .gitignore secret_harness/ tests/ README.md
git commit -m "chore: scaffold package"
```

For `LICENSE`, use the standard MIT text with copyright line `Copyright (c) 2026 David Soden`.

---

### Task 2: Detection ruleset (`patterns.py`)

**Files:**
- Create: `secret_harness/patterns.py`
- Test: `tests/test_patterns.py`

**Interfaces:**
- Produces:
  - `class Finding(NamedTuple): value: str; rule: str`
  - `shannon_entropy(s: str) -> float`
  - `find_secrets(text: str, entropy_threshold: float = 3.5, min_entropy_len: int = 20) -> List[Finding]`
- Consumed by: `detect.py` (Task 5).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_patterns.py
from secret_harness.patterns import Finding, find_secrets, shannon_entropy


def test_entropy_of_repeated_char_is_zero():
    assert shannon_entropy("aaaa") == 0.0


def test_detects_github_token():
    text = "here is my token ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    rules = [f.rule for f in find_secrets(text)]
    assert "github-token" in rules


def test_detects_anthropic_key_over_openai():
    text = "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA"
    found = find_secrets(text)
    assert any(f.rule == "anthropic-key" for f in found)


def test_detects_aws_access_key():
    assert any(f.rule == "aws-access-key" for f in find_secrets("AKIAIOSFODNN7EXAMPLE"))


def test_detects_pem_block():
    assert any(f.rule == "pem-private-key" for f in find_secrets("-----BEGIN RSA PRIVATE KEY-----"))


def test_high_entropy_catchall():
    # random-looking blob with no known prefix
    blob = "Zx9Qw3Vt7Lp2Rk8Nb4Hs6Md1Gf5Jc0Yy"
    assert any(f.rule == "high-entropy" for f in find_secrets(blob))


def test_plain_english_is_clean():
    assert find_secrets("please add error handling to the auth module") == []


def test_no_duplicate_findings():
    text = "ghp_abcdefghijklmnopqrstuvwxyz0123456789 ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    values = [f.value for f in find_secrets(text)]
    assert len(values) == len(set(values))
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_patterns.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `patterns.py`**

```python
# secret_harness/patterns.py
import math
import re
from collections import Counter
from typing import List, NamedTuple


class Finding(NamedTuple):
    value: str
    rule: str


# Order matters: more specific rules first so their match wins.
_KNOWN = [
    ("anthropic-key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("openai-key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("github-pat", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("github-token", re.compile(r"gh[posru]_[A-Za-z0-9]{20,}")),
    ("aws-access-key", re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    ("slack-token", re.compile(r"xox[baprs]-[A-Za-z0-9\-]{10,}")),
    ("google-api-key", re.compile(r"AIza[A-Za-z0-9_\-]{35}")),
    ("stripe-key", re.compile(r"(?:sk|rk)_live_[A-Za-z0-9]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+")),
    ("pem-private-key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("connection-string", re.compile(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s:@/]+:[^\s:@/]+@[^\s/]+")),
]

_TOKEN_RE = re.compile(r"[A-Za-z0-9+/=_\-]+")


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def find_secrets(text, entropy_threshold=3.5, min_entropy_len=20):
    findings = []
    seen = set()
    for rule, pattern in _KNOWN:
        for match in pattern.finditer(text):
            value = match.group(0)
            if value not in seen:
                seen.add(value)
                findings.append(Finding(value, rule))
    for match in _TOKEN_RE.finditer(text):
        value = match.group(0)
        if value in seen:
            continue
        if len(value) >= min_entropy_len and shannon_entropy(value) >= entropy_threshold:
            seen.add(value)
            findings.append(Finding(value, "high-entropy"))
    return findings
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_patterns.py -v`
Expected: all PASS. If `test_high_entropy_catchall` fails, confirm the blob's entropy is >= 3.5 with a quick `python -c "from secret_harness.patterns import shannon_entropy; print(shannon_entropy('Zx9Qw3Vt7Lp2Rk8Nb4Hs6Md1Gf5Jc0Yy'))"`.

- [ ] **Step 5: Commit**

```bash
git add secret_harness/patterns.py tests/test_patterns.py
git commit -m "feat: secret detection ruleset"
```

---

### Task 3: False-positive learning store (`allowlist.py`)

**Files:**
- Create: `secret_harness/allowlist.py`
- Test: `tests/test_allowlist.py`

**Interfaces:**
- Produces:
  - `get_or_create_salt(salt_path: Path) -> str`
  - `class AllowList: __init__(self, path: Path, salt: str); contains(self, value: str) -> bool; add(self, value: str) -> None`
- Consumed by: `detect.py` (Task 5).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_allowlist.py
from secret_harness.allowlist import AllowList, get_or_create_salt


def test_salt_is_created_and_stable(tmp_path):
    salt_path = tmp_path / "salt"
    first = get_or_create_salt(salt_path)
    second = get_or_create_salt(salt_path)
    assert first == second
    assert len(first) >= 16


def test_add_then_contains(tmp_path):
    al = AllowList(tmp_path / "allow.json", salt="s")
    assert not al.contains("abc123")
    al.add("abc123")
    assert al.contains("abc123")


def test_persists_across_instances(tmp_path):
    path = tmp_path / "allow.json"
    AllowList(path, salt="s").add("keepme")
    assert AllowList(path, salt="s").contains("keepme")


def test_raw_value_never_stored(tmp_path):
    path = tmp_path / "allow.json"
    al = AllowList(path, salt="s")
    al.add("supersecretvalue")
    assert "supersecretvalue" not in path.read_text(encoding="utf-8")


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "allow.json"
    path.write_text("not json", encoding="utf-8")
    al = AllowList(path, salt="s")
    assert not al.contains("anything")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_allowlist.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `allowlist.py`**

```python
# secret_harness/allowlist.py
import hashlib
import json
import secrets


def get_or_create_salt(salt_path):
    if salt_path.exists():
        return salt_path.read_text(encoding="utf-8").strip()
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(16)
    salt_path.write_text(salt, encoding="utf-8")
    return salt


def _hash(value, salt):
    return hashlib.sha256((salt + value).encode("utf-8")).hexdigest()


class AllowList:
    def __init__(self, path, salt):
        self.path = path
        self.salt = salt
        self._hashes = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return set(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError):
                return set()
        return set()

    def contains(self, value):
        return _hash(value, self.salt) in self._hashes

    def add(self, value):
        self._hashes.add(_hash(value, self.salt))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._hashes)), encoding="utf-8")
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_allowlist.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add secret_harness/allowlist.py tests/test_allowlist.py
git commit -m "feat: salted-hash allowlist for false positives"
```

---

### Task 4: Detector entry point and messages (`detect.py`, `messages.py`)

**Files:**
- Create: `secret_harness/messages.py`
- Create: `secret_harness/detect.py`
- Test: `tests/test_detect.py`

**Interfaces:**
- Produces:
  - `messages.REPO_URL: str`
  - `messages.secret_detected_message(rule: str, suggested_name: str) -> str`
  - `messages.guard_failure_message(error_summary: str, remediation: str, uninstall_cmd: str) -> str`
  - `detect.BYPASS_TOKEN: str`  (value `"!secret-ok"`)
  - `detect.run(payload: dict, config_dir: Path) -> Tuple[int, str]`  (returns exit code and stderr text)
  - `detect.main() -> None`  (reads stdin, writes stderr, calls sys.exit; fail-closed wrapper)
- Consumes: `patterns.find_secrets`, `allowlist.AllowList`, `allowlist.get_or_create_salt`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_detect.py
from secret_harness import detect
from secret_harness.messages import secret_detected_message, guard_failure_message


def test_clean_prompt_allows(tmp_path):
    code, msg = detect.run({"prompt": "refactor the auth module"}, tmp_path)
    assert code == 0
    assert msg == ""


def test_secret_prompt_blocks(tmp_path):
    code, msg = detect.run(
        {"prompt": "key is ghp_abcdefghijklmnopqrstuvwxyz0123456789"}, tmp_path
    )
    assert code == 2
    assert "Secret detected" in msg
    assert "vault put" in msg


def test_bypass_allows_and_remembers(tmp_path):
    secret_line = "!secret-ok ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    code, msg = detect.run({"prompt": secret_line}, tmp_path)
    assert code == 0
    # same string without bypass now passes, because it was remembered
    code2, _ = detect.run(
        {"prompt": "ghp_abcdefghijklmnopqrstuvwxyz0123456789"}, tmp_path
    )
    assert code2 == 0


def test_missing_prompt_key_allows(tmp_path):
    code, msg = detect.run({}, tmp_path)
    assert code == 0


def test_secret_detected_message_contains_steps():
    m = secret_detected_message("github-token", "github-token")
    assert "Revoke or rotate" in m
    assert "!secret-ok" in m


def test_guard_failure_message_has_uninstall():
    m = guard_failure_message("boom", "reinstall", "uninstall cmd")
    assert "uninstall" in m.lower()
    assert "boom" in m
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_detect.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `messages.py`**

```python
# secret_harness/messages.py
REPO_URL = "https://github.com/dtsoden/Claude-Secret-Harness"


def secret_detected_message(rule, suggested_name):
    return (
        "Secret detected (matched: {rule}).\n"
        "It is now in this transcript, so treat it as compromised.\n\n"
        "Do this:\n"
        "  1. Revoke or rotate it at the provider now.\n"
        "  2. Store the new one:  vault put {name}\n"
        "  3. Re-send your message, referring to it by name.\n\n"
        "False alarm? Re-send your message starting with !secret-ok and this\n"
        "exact string will stop being flagged."
    ).format(rule=rule, name=suggested_name)


def guard_failure_message(error_summary, remediation, uninstall_cmd):
    return (
        "Secret-Harness guard could not run, so your message was blocked to\n"
        "protect any credentials it might contain.\n\n"
        "What broke: {err}\n\n"
        "Fix it:\n"
        "  {fix}\n\n"
        "Can't fix it right now? Remove the guard:\n"
        "  {uninstall}\n"
        "  Full uninstall guide: {url}#uninstall"
    ).format(err=error_summary, fix=remediation, uninstall=uninstall_cmd, url=REPO_URL)
```

- [ ] **Step 4: Implement `detect.py`**

```python
# secret_harness/detect.py
import json
import sys
from pathlib import Path

from secret_harness import messages
from secret_harness.allowlist import AllowList, get_or_create_salt
from secret_harness.patterns import find_secrets

BYPASS_TOKEN = "!secret-ok"


def _default_config_dir():
    return Path.home() / ".claude" / "secret-harness"


def _suggested_name(rule):
    return "my-secret" if rule == "high-entropy" else rule


def run(payload, config_dir):
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
```

- [ ] **Step 5: Run to verify they pass**

Run: `python -m pytest tests/test_detect.py -v`
Expected: all PASS.

- [ ] **Step 6: Manual fail-closed check**

Run: `echo 'not-json' | python -m secret_harness.detect; echo "exit=$?"`
Expected: guard-failure text on stderr and `exit=2`.

- [ ] **Step 7: Commit**

```bash
git add secret_harness/messages.py secret_harness/detect.py tests/test_detect.py
git commit -m "feat: UserPromptSubmit detector with fail-closed guard"
```

---

### Task 5: Vault storage layer (`store.py`)

**Files:**
- Create: `secret_harness/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Produces:
  - `store.SERVICE: str`  (value `"claude-secret-harness"`)
  - `store.store_secret(name: str, value: str, config_dir: Path) -> None`
  - `store.get_secret(name: str, config_dir: Path) -> Optional[str]`
  - `store.delete_secret(name: str, config_dir: Path) -> None`
  - `store.list_names(config_dir: Path) -> List[str]`
- Consumes: `keyring`.
- Note: `keyring` cannot enumerate stored entries portably, so this module keeps its own name index file (`names.json`) holding names only, never values.

- [ ] **Step 1: Write the failing tests**

Tests use a fake in-memory keyring backend so they run with no OS vault.

```python
# tests/test_store.py
import pytest

from secret_harness import store


class FakeKeyring:
    def __init__(self):
        self.data = {}

    def set_password(self, service, name, value):
        self.data[(service, name)] = value

    def get_password(self, service, name):
        return self.data.get((service, name))

    def delete_password(self, service, name):
        self.data.pop((service, name), None)


@pytest.fixture
def fake(monkeypatch):
    fk = FakeKeyring()
    monkeypatch.setattr(store, "keyring", fk)
    return fk


def test_store_and_get(fake, tmp_path):
    store.store_secret("api", "topsecret", tmp_path)
    assert store.get_secret("api", tmp_path) == "topsecret"


def test_list_names_reflects_stores(fake, tmp_path):
    store.store_secret("one", "a", tmp_path)
    store.store_secret("two", "b", tmp_path)
    assert store.list_names(tmp_path) == ["one", "two"]


def test_delete_removes_name_and_value(fake, tmp_path):
    store.store_secret("gone", "x", tmp_path)
    store.delete_secret("gone", tmp_path)
    assert store.get_secret("gone", tmp_path) is None
    assert store.list_names(tmp_path) == []


def test_index_file_holds_names_not_values(fake, tmp_path):
    store.store_secret("mykey", "verysecret", tmp_path)
    index_text = (tmp_path / "names.json").read_text(encoding="utf-8")
    assert "mykey" in index_text
    assert "verysecret" not in index_text
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_store.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `store.py`**

```python
# secret_harness/store.py
import json

import keyring

SERVICE = "claude-secret-harness"


def _index_path(config_dir):
    return config_dir / "names.json"


def _load_names(config_dir):
    path = _index_path(config_dir)
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def _save_names(config_dir, names):
    path = _index_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(names)), encoding="utf-8")


def store_secret(name, value, config_dir):
    keyring.set_password(SERVICE, name, value)
    names = _load_names(config_dir)
    names.add(name)
    _save_names(config_dir, names)


def get_secret(name, config_dir):
    return keyring.get_password(SERVICE, name)


def delete_secret(name, config_dir):
    keyring.delete_password(SERVICE, name)
    names = _load_names(config_dir)
    names.discard(name)
    _save_names(config_dir, names)


def list_names(config_dir):
    return sorted(_load_names(config_dir))
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_store.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add secret_harness/store.py tests/test_store.py
git commit -m "feat: OS vault storage with name index"
```

---

### Task 6: Vault CLI (`vault.py`)

**Files:**
- Create: `secret_harness/vault.py`
- Test: `tests/test_vault.py`

**Interfaces:**
- Produces:
  - `vault.build_parser() -> argparse.ArgumentParser`
  - `vault.main(argv: Optional[List[str]] = None) -> int`
  - subcommands `put`, `run`, `list`, `rm`
- Consumes: `store`, `getpass`, `subprocess`.
- `vault run --set VAR=NAME -- <command>` injects secrets into the child env and never prints a value.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_vault.py
import sys

import pytest

from secret_harness import store, vault


class FakeKeyring:
    def __init__(self):
        self.data = {}

    def set_password(self, service, name, value):
        self.data[(service, name)] = value

    def get_password(self, service, name):
        return self.data.get((service, name))

    def delete_password(self, service, name):
        self.data.pop((service, name), None)


@pytest.fixture
def wired(monkeypatch, tmp_path):
    fk = FakeKeyring()
    monkeypatch.setattr(store, "keyring", fk)
    monkeypatch.setattr(vault, "_config_dir", lambda: tmp_path)
    return tmp_path


def test_put_reads_hidden_input(wired, monkeypatch, capsys):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "s3cret")
    rc = vault.main(["put", "mykey"])
    assert rc == 0
    assert store.get_secret("mykey", wired) == "s3cret"


def test_list_prints_names_only(wired, monkeypatch, capsys):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "v")
    vault.main(["put", "alpha"])
    capsys.readouterr()
    vault.main(["list"])
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "v" not in out.split()


def test_run_injects_env_without_printing_value(wired, monkeypatch, capsys):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "INJECTED")
    vault.main(["put", "tok"])
    capsys.readouterr()
    # child prints the env var to a file, not stdout, so we can assert vault itself is quiet
    script = "import os,sys; open(sys.argv[1],'w').write(os.environ['TOK'])"
    outfile = wired / "out.txt"
    rc = vault.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script, str(outfile)])
    assert rc == 0
    assert outfile.read_text() == "INJECTED"
    assert "INJECTED" not in capsys.readouterr().out


def test_rm_deletes(wired, monkeypatch):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "v")
    vault.main(["put", "temp"])
    vault.main(["rm", "temp"])
    assert store.list_names(wired) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_vault.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `vault.py`**

```python
# secret_harness/vault.py
import argparse
import getpass
import os
import subprocess
import sys
from pathlib import Path

from secret_harness import store


def _config_dir():
    return Path.home() / ".claude" / "secret-harness"


def cmd_put(args):
    value = getpass.getpass("Value for '{0}' (input hidden): ".format(args.name))
    if not value:
        sys.stderr.write("Aborted: empty value.\n")
        return 1
    store.store_secret(args.name, value, _config_dir())
    sys.stdout.write("Stored '{0}' in the OS vault.\n".format(args.name))
    return 0


def cmd_run(args):
    env = os.environ.copy()
    for pair in args.set:
        var, sep, name = pair.partition("=")
        if not var or not sep or not name:
            sys.stderr.write("Bad --set '{0}', expected VAR=NAME.\n".format(pair))
            return 1
        secret = store.get_secret(name, _config_dir())
        if secret is None:
            sys.stderr.write("No vault entry named '{0}'.\n".format(name))
            return 1
        env[var] = secret
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        sys.stderr.write("No command given after --.\n")
        return 1
    return subprocess.run(command, env=env).returncode


def cmd_list(args):
    for name in store.list_names(_config_dir()):
        sys.stdout.write(name + "\n")
    return 0


def cmd_rm(args):
    store.delete_secret(args.name, _config_dir())
    sys.stdout.write("Removed '{0}'.\n".format(args.name))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        prog="vault",
        description="Store and use secrets in the OS credential vault.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_put = sub.add_parser("put", help="Store a secret via a hidden prompt.")
    p_put.add_argument("name")
    p_put.set_defaults(func=cmd_put)

    p_run = sub.add_parser("run", help="Inject secrets into a command's env and run it.")
    p_run.add_argument("--set", action="append", default=[], metavar="VAR=NAME")
    p_run.add_argument("command", nargs=argparse.REMAINDER)
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="List stored names (never values).")
    p_list.set_defaults(func=cmd_list)

    p_rm = sub.add_parser("rm", help="Delete a stored secret.")
    p_rm.add_argument("name")
    p_rm.set_defaults(func=cmd_rm)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_vault.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add secret_harness/vault.py tests/test_vault.py
git commit -m "feat: vault CLI (put/run/list/rm)"
```

---

### Task 7: Hook installer (`installer.py`)

**Files:**
- Create: `secret_harness/installer.py`
- Test: `tests/test_installer.py`

**Interfaces:**
- Produces:
  - `installer.merge_hook(settings_path: Path, command: str, timeout: int = 30, shell: Optional[str] = None) -> None`
  - `installer.remove_hook(settings_path: Path, command: str) -> None`
  - `installer.hook_command() -> str`  (returns `"<sys.executable> -m secret_harness.detect"`, quoted)
  - `installer.main(argv: Optional[List[str]] = None) -> int`  (subcommands `install-hook`, `uninstall-hook`; `install-hook` verifies `keyring` imports and prints a clear error if not)
- Consumes: standard library plus a runtime import check of `keyring`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_installer.py
import json

from secret_harness import installer


def test_merge_into_empty_creates_hook(tmp_path):
    settings = tmp_path / "settings.json"
    installer.merge_hook(settings, "cmd-x", timeout=30)
    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = data["hooks"]["UserPromptSubmit"]
    assert entries[0]["command"] == "cmd-x"
    assert entries[0]["timeout"] == 30


def test_merge_preserves_existing_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"hooks": {"UserPromptSubmit": [{"type": "command", "command": "other"}]}}),
        encoding="utf-8",
    )
    installer.merge_hook(settings, "cmd-x")
    commands = [e["command"] for e in json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]]
    assert "other" in commands
    assert "cmd-x" in commands


def test_merge_is_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    installer.merge_hook(settings, "cmd-x")
    installer.merge_hook(settings, "cmd-x")
    entries = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]
    assert len([e for e in entries if e["command"] == "cmd-x"]) == 1


def test_merge_backs_up_existing_file(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("{}", encoding="utf-8")
    installer.merge_hook(settings, "cmd-x")
    assert (tmp_path / "settings.json.bak").exists()


def test_remove_hook_leaves_others(tmp_path):
    settings = tmp_path / "settings.json"
    installer.merge_hook(settings, "cmd-x")
    installer.merge_hook(settings, "keep-me")
    installer.remove_hook(settings, "cmd-x")
    commands = [e["command"] for e in json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]]
    assert commands == ["keep-me"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/test_installer.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Implement `installer.py`**

```python
# secret_harness/installer.py
import json
import shutil
import sys
from pathlib import Path


def hook_command():
    return '"{0}" -m secret_harness.detect'.format(sys.executable)


def _load(settings_path):
    if settings_path.exists():
        try:
            return json.loads(settings_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def _write(settings_path, data):
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def merge_hook(settings_path, command, timeout=30, shell=None):
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


def remove_hook(settings_path, command):
    data = _load(settings_path)
    entries = data.get("hooks", {}).get("UserPromptSubmit", [])
    data["hooks"]["UserPromptSubmit"] = [e for e in entries if e.get("command") != command]
    _write(settings_path, data)


def _settings_path():
    return Path.home() / ".claude" / "settings.json"


def main(argv=None):
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/test_installer.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add secret_harness/installer.py tests/test_installer.py
git commit -m "feat: settings.json hook merge and removal"
```

---

### Task 8: Shell installers and the skill

**Files:**
- Create: `install.sh`
- Create: `install.ps1`
- Create: `uninstall.sh`
- Create: `uninstall.ps1`
- Create: `skills/secret-harness/SKILL.md`

**Interfaces:**
- Consumes: `python -m secret_harness.installer`, the `pip`-installed package, the `vault` console script.
- Produces: a working end-to-end install. No unit tests (shell + real OS vault); verified by the manual smoke test in Step 6.

- [ ] **Step 1: Write `install.sh` (macOS/Linux)**

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "Installing Claude-Secret-Harness..."

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found. Install Python 3 and re-run." >&2
  exit 1
fi

python3 -m pip install --user .

SKILL_DIR="$HOME/.claude/skills/secret-harness"
mkdir -p "$SKILL_DIR"
cp "skills/secret-harness/SKILL.md" "$SKILL_DIR/SKILL.md"

python3 -m secret_harness.installer install-hook

echo "Done. Store a secret with:  vault put my-key"
```

- [ ] **Step 2: Write `install.ps1` (Windows)**

```powershell
$ErrorActionPreference = "Stop"
Write-Host "Installing Claude-Secret-Harness..."

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
  Write-Error "Python 3 is required but was not found. Install Python 3 and re-run."
  exit 1
}

python -m pip install --user .

$skillDir = Join-Path $HOME ".claude\skills\secret-harness"
New-Item -ItemType Directory -Force -Path $skillDir | Out-Null
Copy-Item "skills\secret-harness\SKILL.md" (Join-Path $skillDir "SKILL.md") -Force

python -m secret_harness.installer install-hook

Write-Host "Done. Store a secret with:  vault put my-key"
```

- [ ] **Step 3: Write `uninstall.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
echo "Removing Claude-Secret-Harness..."
python3 -m secret_harness.installer uninstall-hook || true
rm -rf "$HOME/.claude/skills/secret-harness"
python3 -m pip uninstall -y claude-secret-harness || true
echo "Hook and skill removed. Your stored secrets remain in the OS vault."
```

- [ ] **Step 4: Write `uninstall.ps1`**

```powershell
$ErrorActionPreference = "Continue"
Write-Host "Removing Claude-Secret-Harness..."
python -m secret_harness.installer uninstall-hook
Remove-Item -Recurse -Force (Join-Path $HOME ".claude\skills\secret-harness") -ErrorAction SilentlyContinue
python -m pip uninstall -y claude-secret-harness
Write-Host "Hook and skill removed. Your stored secrets remain in the OS vault."
```

- [ ] **Step 5: Write the skill**

```markdown
---
name: secret-harness
description: Standing rules for handling credentials and secrets. Always active. Never accept a raw secret in chat; store and retrieve secrets through the OS vault by name using the vault CLI, and never print a secret value.
---

# Secret handling rules

These rules are always in effect.

1. Never ask the user to paste a raw secret into the chat. If a task needs one, ask them to run `vault put NAME` and tell you the NAME.
2. Refer to secrets only by their vault name.
3. To use a secret in a command, inject it with `vault run --set VAR=NAME -- <command>`. Never run anything that would print the value.
4. Never display a stored secret value. If the user wants to see one, tell them to open Keychain Access (macOS) or Credential Manager (Windows).
5. If a secret ever appears in the chat, treat it as compromised: tell the user to rotate it at the provider first, then store the new value with `vault put`.
```

- [ ] **Step 6: Manual end-to-end smoke test**

```bash
# from the repo root, on your own machine
bash install.sh
vault put smoke-test        # type any value at the hidden prompt
vault list                  # shows: smoke-test
vault run --set X=smoke-test -- printenv X   # prints the value you typed (child command, your choice)
vault rm smoke-test
```

Then open a new Claude Code session and paste a fake key like `ghp_abcdefghijklmnopqrstuvwxyz0123456789`. Expected: the message is blocked and the secret-detected text appears. Re-send prefixed with `!secret-ok`. Expected: it goes through.

- [ ] **Step 7: Commit**

```bash
git add install.sh install.ps1 uninstall.sh uninstall.ps1 skills/
git commit -m "feat: installers and secret-harness skill"
```

---

### Task 9: CI and README

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md` (replace the placeholder)

**Interfaces:**
- Consumes: the test suite from Tasks 1 to 7.
- Produces: passing CI on Windows, macOS, Linux; a README that tells the whole story for the LinkedIn article.

- [ ] **Step 1: Write the CI workflow**

```yaml
# .github/workflows/ci.yml
name: ci
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        python-version: ["3.9", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: python -m pip install -e ".[dev]"
      - name: Test
        run: python -m pytest tests/ -v
```

- [ ] **Step 2: Run the full suite locally**

Run: `python -m pytest tests/ -v`
Expected: all tests from Tasks 1 to 7 PASS.

Note on Linux CI: the storage tests use a fake keyring backend and do not need a real Secret Service, so they pass on headless runners.

- [ ] **Step 3: Write the README**

Write `README.md` covering, in prose and short lists: what the tool does and why the habit is the risk; the core policy (secrets enter only through `vault put`, values are never printed, view them in the OS manager, anything typed into chat must be rotated); one-line install per OS (`bash install.sh` / `.\install.ps1`); how to store and use a secret (`vault put`, `vault run`, `vault list`, `vault rm`); how detection and the `!secret-ok` bypass work; an `## Uninstall` section with the exact `uninstall.sh` / `uninstall.ps1` commands and a note that stored secrets stay in the OS vault; and the caveat that the tool protects future use, not a key already exposed. No em dashes.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci.yml README.md
git commit -m "ci: cross-platform test matrix and README"
```

---

## Self-Review

**Spec coverage:**
- Detection hook, block on detection, fail closed: Task 4. Detection ruleset (known shapes + entropy): Task 2. Bypass + salted-hash learning: Tasks 3 and 4. Vault store/retrieve, never print, name index: Tasks 5 and 6. Skill rules: Task 8. Installer with settings merge, backup, Python/keyring check, per-OS scripts, uninstall: Tasks 7 and 8. Both human-facing messages: Task 4. Distribution, MIT, CI matrix, README: Tasks 1 and 9. All spec sections map to a task.
- Deliberately omitted: `vault allow-last` (spec marked it optional; the `!secret-ok` token is the primary learning path). Prompt-rewriting/redaction (verified impossible in the hook).

**Placeholder scan:** No TBD/TODO. Every code step shows complete code. The README step (Task 9 Step 3) describes required sections rather than full prose, which is acceptable for a docs deliverable; every section it must contain is listed.

**Type consistency:** `find_secrets` returns `List[Finding]` and is consumed as such in Task 4. `store_secret/get_secret/delete_secret/list_names` signatures match between Tasks 5 and 6. `merge_hook/remove_hook/hook_command` match between Task 7 and the installers in Task 8. `config_dir` is a `Path` throughout. Bypass token, service name, and config dir match the Global Constraints.
