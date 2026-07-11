import json
import os
import subprocess
import sys


def _run_hook(stdin_text, tmp_path):
    env = os.environ.copy()
    env["HOME"] = str(tmp_path)
    env["USERPROFILE"] = str(tmp_path)
    return subprocess.run(
        [sys.executable, "-m", "aihsm.detect"],
        input=stdin_text,
        capture_output=True,
        text=True,
        env=env,
    )


def test_clean_prompt_passes_through(tmp_path):
    result = _run_hook(json.dumps({"prompt": "refactor the auth module"}), tmp_path)
    assert result.returncode == 0
    assert result.stderr == ""


def test_secret_prompt_is_blocked_and_not_echoed(tmp_path):
    secret = "ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    result = _run_hook(json.dumps({"prompt": secret}), tmp_path)
    assert result.returncode == 2
    assert "Secret detected" in result.stderr
    assert secret not in result.stdout
    assert secret not in result.stderr


def test_malformed_stdin_fails_closed(tmp_path):
    result = _run_hook("not-json", tmp_path)
    assert result.returncode == 2
    assert "aihsm guard could not run" in result.stderr
