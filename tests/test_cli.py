import sys

import pytest

from aihsm import store, cli


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
    monkeypatch.setattr(cli, "_config_dir", lambda: tmp_path)
    return tmp_path


def test_put_reads_hidden_input(wired, monkeypatch, capsys):
    # Entered twice for confirmation; both match.
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "s3cret")
    rc = cli.main(["put", "mykey"])
    assert rc == 0
    assert store.get_secret("mykey", wired) == "s3cret"


def test_put_reports_length_on_success(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "abcdef")
    rc = cli.main(["put", "k"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "6 characters" in out


def test_put_mismatch_aborts_and_stores_nothing(wired, monkeypatch, capsys):
    entries = iter(["first-value", "second-value"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(entries))
    rc = cli.main(["put", "mykey"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "did not match" in err
    assert store.get_secret("mykey", wired) is None


def test_put_rejects_value_on_command_line(wired, monkeypatch, capsys):
    # Passing the value as an argument must be refused (it would leak into shell history).
    called = {"n": 0}

    def _boom(prompt=""):
        called["n"] += 1
        return "should-not-be-called"

    monkeypatch.setattr(cli.getpass, "getpass", _boom)
    rc = cli.main(["put", "mykey", "my-secret-value"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "command line" in err
    assert called["n"] == 0
    assert store.get_secret("mykey", wired) is None


def test_list_prints_names_only(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "v")
    cli.main(["put", "alpha"])
    capsys.readouterr()
    cli.main(["list"])
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "v" not in out.split()


def test_run_injects_env_without_printing_value(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "INJECTED")
    cli.main(["put", "tok"])
    capsys.readouterr()
    # child prints the env var to a file, not stdout, so we can assert aihsm itself is quiet
    script = "import os,sys; open(sys.argv[1],'w').write(os.environ['TOK'])"
    outfile = wired / "out.txt"
    rc = cli.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script, str(outfile)])
    assert rc == 0
    assert outfile.read_text() == "INJECTED"
    assert "INJECTED" not in capsys.readouterr().out


def test_rm_deletes(wired, monkeypatch):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "v")
    cli.main(["put", "temp"])
    cli.main(["rm", "temp"])
    assert store.list_names(wired) == []


def test_run_redacts_secret_printed_to_stdout(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "SUPERSECRETVALUE")
    cli.main(["put", "tok"])
    capsys.readouterr()
    script = "import os,sys; sys.stdout.write(os.environ['TOK']); sys.stdout.flush()"
    rc = cli.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    out = capsys.readouterr().out
    assert rc == 0
    assert "SUPERSECRETVALUE" not in out
    assert "****" in out


def test_run_redacts_secret_printed_to_stderr(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "STDERRSECRETVAL")
    cli.main(["put", "tok"])
    capsys.readouterr()
    script = "import os,sys; sys.stderr.write(os.environ['TOK']); sys.stderr.flush()"
    rc = cli.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    err = capsys.readouterr().err
    assert rc == 0
    assert "STDERRSECRETVAL" not in err
    assert "****" in err


def test_run_redacts_secret_split_across_read_boundary(wired, monkeypatch, capsys):
    # A long secret plus a slow, chunked writer makes it likely the value
    # straddles a read boundary; the redactor must catch it regardless.
    secret = "BOUNDARYSTRADDLINGSECRETVALUE1234567890"
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": secret)
    cli.main(["put", "tok"])
    capsys.readouterr()
    script = (
        "import os,sys,time\n"
        "v = os.environ['TOK']\n"
        "for ch in v:\n"
        "    sys.stdout.write(ch)\n"
        "    sys.stdout.flush()\n"
    )
    rc = cli.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    out = capsys.readouterr().out
    assert rc == 0
    assert secret not in out
    assert "****" in out


def test_run_delivers_real_value_to_child_while_masking_stdout(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "REALDELIVEREDVALUE")
    cli.main(["put", "tok"])
    capsys.readouterr()
    outfile = wired / "delivered.txt"
    script = (
        "import os,sys\n"
        "v = os.environ['TOK']\n"
        "open(sys.argv[1], 'w').write(v)\n"
        "sys.stdout.write(v)\n"
    )
    rc = cli.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script, str(outfile)])
    out = capsys.readouterr().out
    assert rc == 0
    assert outfile.read_text() == "REALDELIVEREDVALUE"
    assert "REALDELIVEREDVALUE" not in out
    assert "****" in out


def test_run_bad_command_returns_nonzero_without_raising(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "v")
    cli.main(["put", "tok"])
    capsys.readouterr()
    try:
        rc = cli.main(["run", "--set", "TOK=tok", "--", "this-command-does-not-exist-xyz"])
    except OSError:
        pytest.fail("aihsm run raised OSError instead of returning an error code")
    assert isinstance(rc, int)
    assert rc != 0
    assert "Cannot run command" in capsys.readouterr().err


def test_run_returns_child_exit_code(wired, monkeypatch, capsys):
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "v")
    cli.main(["put", "tok"])
    capsys.readouterr()
    script = "import sys; sys.exit(3)"
    rc = cli.main(["run", "--set", "TOK=tok", "--", sys.executable, "-c", script])
    assert rc == 3


def test_missing_subcommand_prints_help_returns_zero(wired, capsys):
    try:
        rc = cli.main([])
    except SystemExit:
        pytest.fail("main([]) raised SystemExit instead of returning an int")
    out = capsys.readouterr().out
    assert isinstance(rc, int)
    assert rc == 0
    # Bare `aihsm` shows friendly help (usage + examples), not a terse error.
    assert "usage: aihsm" in out
    assert "Examples:" in out


def test_help_flag_returns_zero(wired, capsys):
    try:
        rc = cli.main(["-h"])
    except SystemExit:
        pytest.fail("main(['-h']) raised SystemExit instead of returning an int")
    out = capsys.readouterr().out
    assert rc == 0
    assert "usage: aihsm" in out


# --- Version reporting ---

def test_version_flags_report_the_version(capsys):
    for flag in ("--version", "-V", "-v"):
        code = cli.main([flag])
        out = capsys.readouterr().out
        assert code == 0, "%s exited %s" % (flag, code)
        assert "aihsm" in out, "%s printed no version: %r" % (flag, out)


def test_version_is_not_hardcoded_and_matches_package_metadata():
    # Regression: __init__ used to hardcode __version__, which silently drifted
    # from pyproject.toml (it said 0.1.0 after 0.1.1 shipped). The version must
    # come from installed package metadata so pyproject stays the only source.
    import aihsm
    from importlib.metadata import version

    assert aihsm.__version__ == version("aihsm")
