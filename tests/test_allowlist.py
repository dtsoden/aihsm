from aihsm.allowlist import AllowList, get_or_create_salt


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


def test_non_list_json_is_ignored(tmp_path):
    path = tmp_path / "allow.json"
    path.write_text("5", encoding="utf-8")
    al = AllowList(path, salt="s")
    assert not al.contains("anything")
