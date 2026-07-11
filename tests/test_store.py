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


@pytest.fixture
def fake(monkeypatch):
    fk = FakeKeyring()
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
