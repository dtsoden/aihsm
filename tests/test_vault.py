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


def test_run_redacts_secret_printed_to_stdout(wired, monkeypatch, capsys):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "SUPERSECRETVALUE")
    vault.main(["put", "tok"])
    capsys.readouterr()
    script = "import os,sys; sys.stdout.write(os.environ['TOK']); sys.stdout.flush()"
    rc = vault.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SUPERSECRETVALUE" not in out
    assert "****" in out


def test_run_redacts_secret_printed_to_stderr(wired, monkeypatch, capsys):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "STDERRSECRETVAL")
    vault.main(["put", "tok"])
    capsys.readouterr()
    script = "import os,sys; sys.stderr.write(os.environ['TOK']); sys.stderr.flush()"
    rc = vault.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    err = capsys.readouterr().err
    assert rc == 0
    assert "STDERRSECRETVAL" not in err
    assert "****" in err


def test_run_redacts_secret_split_across_read_boundary(wired, monkeypatch, capsys):
    # A long secret plus a slow, chunked writer makes it likely the value
    # straddles a read boundary; the redactor must catch it regardless.
    secret = "BOUNDARYSTRADDLINGSECRETVALUE1234567890"
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": secret)
    vault.main(["put", "tok"])
    capsys.readouterr()
    script = (
        "import os,sys,time\n"
        "v = os.environ['TOK']\n"
        "for ch in v:\n"
        "    sys.stdout.write(ch)\n"
        "    sys.stdout.flush()\n"
    )
    rc = vault.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    out = capsys.readouterr().out
    assert rc == 0
    assert secret not in out
    assert "****" in out


def test_run_delivers_real_value_to_child_while_masking_stdout(wired, monkeypatch, capsys):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "REALDELIVEREDVALUE")
    vault.main(["put", "tok"])
    capsys.readouterr()
    outfile = wired / "delivered.txt"
    script = (
        "import os,sys\n"
        "v = os.environ['TOK']\n"
        "open(sys.argv[1], 'w').write(v)\n"
        "sys.stdout.write(v)\n"
    )
    rc = vault.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script, str(outfile)])
    out = capsys.readouterr().out
    assert rc == 0
    assert outfile.read_text() == "REALDELIVEREDVALUE"
    assert "REALDELIVEREDVALUE" not in out
    assert "****" in out


def test_run_returns_child_exit_code(wired, monkeypatch, capsys):
    monkeypatch.setattr(vault.getpass, "getpass", lambda prompt="": "v")
    vault.main(["put", "tok"])
    capsys.readouterr()
    script = "import sys; sys.exit(3)"
    rc = vault.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    assert rc == 3


def test_missing_subcommand_returns_int_not_raises(wired):
    try:
        rc = vault.main([])
    except SystemExit:
        pytest.fail("main([]) raised SystemExit instead of returning an int")
    assert isinstance(rc, int)
    assert rc != 0
