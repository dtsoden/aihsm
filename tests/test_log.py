import sys

import pytest

from secret_harness import detect, log, vault

# Global logger reset between tests is handled by the autouse fixture in
# tests/conftest.py (isolate_secret_harness_log), so each test here only
# needs to call log.get_logger(..., force=True) with its own path.


def _log_files(base_log_path):
    d = base_log_path.parent
    stem = base_log_path.name
    return sorted(p for p in d.iterdir() if p.name.startswith(stem))


def test_rotation_caps_files(tmp_path):
    target = tmp_path / "a.log"
    log.get_logger(target, max_bytes=500, backups=2, force=True)

    long_line = "x" * 200
    for i in range(100):
        log.info("entry {0} {1}".format(i, long_line))

    files = _log_files(target)
    assert len(files) <= 3


def test_disabled_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_HARNESS_NO_LOG", "1")
    target = tmp_path / "disabled.log"
    log.get_logger(target, force=True)

    log.info("should not be written anywhere")

    assert not target.exists()


def test_best_effort_no_raise(tmp_path):
    # Make the parent of the log path an existing file, not a directory, so
    # mkdir(parents=True) inside get_logger fails and it falls back to a
    # NullHandler. log.info must still never raise.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")
    impossible_path = blocker / "sub" / "secret-harness.log"

    log.get_logger(impossible_path, force=True)

    try:
        log.info("this must not raise")
        log.error("neither must this")
    except Exception as exc:  # pragma: no cover - failure path
        pytest.fail("log.info/error raised: {0}".format(exc))


def test_no_secret_value_in_block_log(tmp_path):
    log_file = tmp_path / "detect.log"
    log.get_logger(log_file, force=True)

    secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    config_dir = tmp_path / "config"
    code, msg = detect.run({"prompt": "key is " + secret}, config_dir)

    assert code == 2
    contents = log_file.read_text(encoding="utf-8")
    assert "github-token" in contents
    assert secret not in contents
    assert "key is " + secret not in contents


class FakeKeyring:
    def __init__(self):
        self.data = {}

    def set_password(self, service, name, value):
        self.data[(service, name)] = value

    def get_password(self, service, name):
        return self.data.get((service, name))

    def delete_password(self, service, name):
        self.data.pop((service, name), None)


def test_vault_run_logs_names_not_values(tmp_path, monkeypatch):
    from secret_harness import store

    log_file = tmp_path / "vault.log"
    log.get_logger(log_file, force=True)

    fk = FakeKeyring()
    monkeypatch.setattr(store, "keyring", fk)
    monkeypatch.setattr(vault, "_config_dir", lambda: tmp_path)
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "SECRETVALUE12345")

    vault.main(["put", "name"])

    script = "import sys; sys.exit(0)"
    rc = vault.main(["run", "--set", "TOK=name", "--", sys.executable, "-c", script])
    assert rc == 0

    contents = log_file.read_text(encoding="utf-8")
    assert "name" in contents
    assert "SECRETVALUE12345" not in contents
