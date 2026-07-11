import json

import keyring

SERVICE = "claude-secret-harness"


def _index_path(config_dir):
    return config_dir / "names.json"


def _load_names(config_dir):
    path = _index_path(config_dir)
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError):
            return set()
    return set()


def _save_names(config_dir, names):
    path = _index_path(config_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(names)), encoding="utf-8")


def store_secret(name, value, config_dir):
    keyring.set_password(SERVICE, name, value)
    names = _load_names(config_dir)
    names.add(name)
    _save_names(config_dir, names)


def get_secret(name, config_dir):
    return keyring.get_password(SERVICE, name)


def delete_secret(name, config_dir):
    keyring.delete_password(SERVICE, name)
    names = _load_names(config_dir)
    names.discard(name)
    _save_names(config_dir, names)


def list_names(config_dir):
    return sorted(_load_names(config_dir))
