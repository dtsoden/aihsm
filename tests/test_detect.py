from aihsm import detect
from aihsm.messages import secret_detected_message, guard_failure_message


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
    assert "aihsm put" in msg


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
