import hashlib
import json
import secrets


def get_or_create_salt(salt_path):
    if salt_path.exists():
        return salt_path.read_text(encoding="utf-8").strip()
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(16)
    salt_path.write_text(salt, encoding="utf-8")
    return salt


def _hash(value, salt):
    return hashlib.sha256((salt + value).encode("utf-8")).hexdigest()


class AllowList:
    def __init__(self, path, salt):
        self.path = path
        self.salt = salt
        self._hashes = self._load()

    def _load(self):
        if self.path.exists():
            try:
                return set(json.loads(self.path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, ValueError):
                return set()
        return set()

    def contains(self, value):
        return _hash(value, self.salt) in self._hashes

    def add(self, value):
        self._hashes.add(_hash(value, self.salt))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(sorted(self._hashes)), encoding="utf-8")
