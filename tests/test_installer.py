import json

from aihsm import installer


def test_merge_into_empty_creates_nested_hook(tmp_path):
    settings = tmp_path / "settings.json"
    installer.merge_hook(settings, "cmd-x", timeout=30)
    data = json.loads(settings.read_text(encoding="utf-8"))
    entries = data["hooks"]["UserPromptSubmit"]
    # Claude Code requires the nested group form: entry -> hooks[] -> command.
    assert entries[0]["hooks"][0]["command"] == "cmd-x"
    assert entries[0]["hooks"][0]["timeout"] == 30


def test_merge_produces_nested_schema_not_flat(tmp_path):
    # Every UserPromptSubmit entry must be a group with its own "hooks" array,
    # never a flat {type, command} object (which Claude Code rejects).
    settings = tmp_path / "settings.json"
    installer.merge_hook(settings, "cmd-x")
    entries = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]
    for entry in entries:
        assert isinstance(entry.get("hooks"), list)
        assert "command" not in entry
        assert "type" not in entry


def test_merge_repairs_legacy_flat_entry(tmp_path):
    # Simulate a settings file left broken by the old installer: a flat entry.
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {"hooks": {"UserPromptSubmit": [{"type": "command", "command": "OURCMD", "timeout": 30}]}}
        ),
        encoding="utf-8",
    )
    installer.merge_hook(settings, "OURCMD")
    entries = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]
    # The broken flat entry is gone, replaced by exactly one correct group.
    assert len(entries) == 1
    assert entries[0]["hooks"][0]["command"] == "OURCMD"
    assert all("command" not in e for e in entries)


def test_merge_preserves_existing_hooks(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps(
            {"hooks": {"UserPromptSubmit": [{"hooks": [{"type": "command", "command": "other"}]}]}}
        ),
        encoding="utf-8",
    )
    installer.merge_hook(settings, "cmd-x")
    entries = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]
    commands = [h["command"] for e in entries for h in e.get("hooks", [])]
    assert "other" in commands
    assert "cmd-x" in commands


def test_merge_is_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    installer.merge_hook(settings, "cmd-x")
    installer.merge_hook(settings, "cmd-x")
    entries = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]
    commands = [h["command"] for e in entries for h in e.get("hooks", [])]
    assert commands.count("cmd-x") == 1


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
    entries = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]
    commands = [h["command"] for e in entries for h in e.get("hooks", [])]
    assert commands == ["keep-me"]


def test_remove_hook_missing_file_is_noop(tmp_path):
    settings = tmp_path / "settings.json"
    installer.remove_hook(settings, "cmd-x")
    assert not settings.exists()


def test_remove_hook_also_clears_legacy_flat_entry(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(
        json.dumps({"hooks": {"UserPromptSubmit": [{"type": "command", "command": "OURCMD"}]}}),
        encoding="utf-8",
    )
    installer.remove_hook(settings, "OURCMD")
    entries = json.loads(settings.read_text())["hooks"]["UserPromptSubmit"]
    assert entries == []


def test_load_ignores_non_list_json(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text("5", encoding="utf-8")
    assert installer._load(settings) == {}


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
