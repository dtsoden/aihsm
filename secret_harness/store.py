import json

import keyring
from keyring.errors import PasswordDeleteError

SERVICE = "claude-secret-harness"


def _index_path(config_dir):
    return config_dir / "names.json"


def _load_names(config_dir):
    path = _index_path(config_dir)
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError, TypeError):
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
    try:
        keyring.delete_password(SERVICE, name)
    except PasswordDeleteError:
        # Real backends (e.g. Windows WinVaultKeyring) raise when the entry is
        # already absent. Treat "already gone" as success and always fall
        # through so the name index stays consistent.
        pass
    names = _load_names(config_dir)
    names.discard(name)
    _save_names(config_dir, names)


def list_names(config_dir):
    """Return the stored names, reconciled against the real OS vault.

    The name index is only a hint: a user can delete an entry directly in
    their OS credential manager, which leaves the index stale. So we verify
    each name against the vault, drop any that no longer resolve, and heal
    the index. A name we cannot verify (an unexpected backend error) is kept
    rather than hidden, so a transient failure never makes a real secret
    vanish from the list.
    """
    names = _load_names(config_dir)
    live = set()
    stale = False
    for name in names:
        try:
            present = keyring.get_password(SERVICE, name) is not None
        except Exception:
            present = True
        if present:
            live.add(name)
        else:
            stale = True
    if stale:
        _save_names(config_dir, live)
    return sorted(live)
