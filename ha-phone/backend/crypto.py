"""Encryption-at-rest for stored secrets (D8, Roadmap Phase A / decision before
Phase B backup work).

Trunk password, SMTP password, and SIP passwords used to sit in SQLite as
plain text - anyone with filesystem access to /data (or a copy of the DB
file) could read them directly. This is the branchenueblich baseline for a
self-hosted system with no external secrets manager: symmetric encryption
(Fernet/AES) with a key generated on first boot and stored outside the
database, in its own file with restrictive permissions.

This does NOT protect against an attacker with full root access to the same
host (the key sits right next to the encrypted data) - no purely local
scheme can. It DOES protect the common real-world exposure: a copied/leaked
database file, a misconfigured backup, or a SQLite file browsed without
realizing it contains credentials. A future Backup/Restore export can layer
a second, user-password-derived encryption on top of the exported blobs;
that's out of scope here since Backup/Restore doesn't exist yet.
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

_fernet: Fernet | None = None


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _key_path() -> Path:
    return _data_dir() / ".secret_key"


def _load_or_create_key() -> bytes:
    path = _key_path()
    if path.exists():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    path.write_bytes(key)
    os.chmod(path, 0o600)
    return key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_or_create_key())
    return _fernet


def reset_fernet_cache() -> None:
    """Test-only: force the next get_fernet() to reload the key from disk."""
    global _fernet
    _fernet = None


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    """Decrypt a value written by encrypt_secret. Returns legacy plain-text
    values unchanged (pre-encryption DB rows) so existing data keeps working
    until the next write re-saves it encrypted (see database.py migration)."""
    if not value:
        return ""
    try:
        return get_fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return value


class EncryptedString(TypeDecorator):
    """SQLAlchemy column type: transparently encrypts on write, decrypts on
    read. Application code (routers, Jinja2 templates) keeps using the field
    as a plain string - no call-site changes needed."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return encrypt_secret(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return decrypt_secret(value)
