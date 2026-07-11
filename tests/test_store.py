import json

import keyring.errors
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


class StrictFakeKeyring(FakeKeyring):
    """Faithful to real backends (e.g. Windows WinVaultKeyring): raises
    PasswordDeleteError when deleting an entry that is not present."""

    def delete_password(self, service, name):
        if (service, name) not in self.data:
            raise keyring.errors.PasswordDeleteError("not found")
        del self.data[(service, name)]


@pytest.fixture
def fake(monkeypatch):
    fk = FakeKeyring()
    monkeypatch.setattr(store, "keyring", fk)
    return fk


@pytest.fixture
def strict_fake(monkeypatch):
    fk = StrictFakeKeyring()
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


def test_target_is_consistent_name_at_service(fake, tmp_path):
    # Every entry is stored under "<name>@claude-secret-harness", the same on
    # any OS, never a bare service name.
    assert store._target("github-token") == "github-token@claude-secret-harness"
    store.store_secret("github-token", "v", tmp_path)
    assert ("github-token@claude-secret-harness", "github-token") in fake.data
    # no bare "claude-secret-harness" target is ever written.
    assert all(key[0] != store.SERVICE for key in fake.data)


def test_list_prunes_names_deleted_outside_the_tool(fake, tmp_path):
    # User stores two, then deletes one directly in the OS credential manager
    # (bypassing store.delete_secret, so the name index is now stale).
    store.store_secret("keep", "v1", tmp_path)
    store.store_secret("gone", "v2", tmp_path)
    fake.data.pop((store._target("gone"), "gone"), None)  # external deletion
    # list must reflect reality, not the stale index.
    assert store.list_names(tmp_path) == ["keep"]
    # and it must have healed the index on disk.
    healed = json.loads((tmp_path / "names.json").read_text(encoding="utf-8"))
    assert "gone" not in healed
    assert "keep" in healed


def test_delete_missing_name_does_not_raise(strict_fake, tmp_path):
    # Deleting a name that was never stored (or whose credential was removed
    # out of band) must not raise, and must leave the index consistent.
    store.delete_secret("never", tmp_path)
    assert store.list_names(tmp_path) == []


def test_delete_twice_is_idempotent(strict_fake, tmp_path):
    store.store_secret("dup", "v", tmp_path)
    store.delete_secret("dup", tmp_path)
    assert store.list_names(tmp_path) == []
    # Second delete against the now-absent entry must not raise.
    store.delete_secret("dup", tmp_path)
    assert store.list_names(tmp_path) == []
    assert store.get_secret("dup", tmp_path) is None


def test_delete_stranded_name_clears_index(strict_fake, tmp_path):
    # Credential removed out of band: name is in the index but not the vault.
    store.store_secret("stranded", "v", tmp_path)
    strict_fake.data.pop((store._target("stranded"), "stranded"), None)
    store.delete_secret("stranded", tmp_path)
    assert store.list_names(tmp_path) == []
