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
