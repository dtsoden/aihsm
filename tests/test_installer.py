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


def test_remove_hook_missing_file_is_noop(tmp_path):
    settings = tmp_path / "settings.json"
    installer.remove_hook(settings, "cmd-x")
    assert not settings.exists()


def test_remove_hook_no_userpromptsubmit_is_noop(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"hooks": {"PostToolUse": [{"type": "command", "command": "pt"}]}}),
        encoding="utf-8",
    )
    installer.remove_hook(settings, "cmd-x")
    data = json.loads(settings.read_text())
    assert data["hooks"]["PostToolUse"] == [{"type": "command", "command": "pt"}]
    assert "UserPromptSubmit" not in data["hooks"]
