"""
Authentication utilities for ha-phone admin UI (SEC-04).
"""
import os
import threading
import time
from pathlib import Path
from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session, select
import bcrypt

from backend.database import get_session
from backend.models import AdminUser

# Session secret — read from /data/asterisk/session_secret (written by cont-init.d).
# DO NOT rely on env var injection from s6 shell to uvicorn process.
_data_dir = Path(os.environ.get("BPX_DATA_DIR", "/data"))
_secret_file = _data_dir / "asterisk" / "session_secret"
try:
    SESSION_SECRET = _secret_file.read_text().strip()
except FileNotFoundError:
    SESSION_SECRET = "dev-fallback-secret-change-me"  # only used in local dev without cont-init.d


def hash_password(plain: str) -> bytes:
    """bcrypt-hash a plaintext password. rounds=12 per RESEARCH.md."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))


def verify_password(plain: str, hashed: bytes) -> bool:
    """Constant-time bcrypt comparison."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed)


# Default passwords shipped in config.yaml / the seed fallback. Never accepted
# silently: logging in with one forces the change-password dialog.
DEFAULT_PASSWORDS = frozenset({"changeme", "admin"})


def is_default_password(plain: str) -> bool:
    return plain.strip().lower() in DEFAULT_PASSWORDS


class LoginRateLimiter:
    """In-memory per-IP failed-login tracker with exponential lockout.

    After ``max_failures`` consecutive failures the IP is locked for
    ``base_lockout`` seconds; every further failure after a lockout doubles the
    lockout, capped at ``max_lockout``. A successful login resets the IP.
    """

    MAX_TRACKED = 1024

    def __init__(self, max_failures: int = 5, base_lockout: int = 60,
                 max_lockout: int = 15 * 60, clock=time.monotonic):
        self.max_failures = max_failures
        self.base_lockout = base_lockout
        self.max_lockout = max_lockout
        self._clock = clock
        self._lock = threading.Lock()
        # ip -> (failures, lockouts_so_far, locked_until)
        self._state: dict[str, tuple[int, int, float]] = {}

    def retry_after(self, ip: str) -> int:
        with self._lock:
            entry = self._state.get(ip)
            if not entry:
                return 0
            remaining = entry[2] - self._clock()
            return int(remaining) + 1 if remaining > 0 else 0

    def register_failure(self, ip: str) -> int:
        """Record a failure. Returns the lockout in seconds if one starts now, else 0."""
        with self._lock:
            if len(self._state) >= self.MAX_TRACKED and ip not in self._state:
                self._evict_expired()
            failures, lockouts, _ = self._state.get(ip, (0, 0, 0.0))
            failures += 1
            if failures < self.max_failures:
                self._state[ip] = (failures, lockouts, 0.0)
                return 0
            duration = min(self.base_lockout * (2 ** lockouts), self.max_lockout)
            # Keep failures at threshold-1: the next failure after the lockout
            # immediately triggers a (doubled) lockout again.
            self._state[ip] = (self.max_failures - 1, lockouts + 1, self._clock() + duration)
            return duration

    def reset(self, ip: str) -> None:
        with self._lock:
            self._state.pop(ip, None)

    def clear(self) -> None:
        with self._lock:
            self._state.clear()

    def _evict_expired(self) -> None:
        now = self._clock()
        for key in [k for k, v in self._state.items() if v[2] <= now]:
            del self._state[key]
        if len(self._state) >= self.MAX_TRACKED:
            self._state.clear()


login_limiter = LoginRateLimiter()


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> AdminUser:
    """
    FastAPI dependency — validates session cookie and returns the AdminUser.
    Raises 401 if no valid session; raises 403 (with X-Must-Change-Password header)
    if must_change_password=True.
    DO NOT use this dependency on /api/auth/change-password (circular block — see RESEARCH.md Pitfall 5).
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = session.get(AdminUser, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.must_change_password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Password change required",
            headers={"X-Must-Change-Password": "true"},
        )
    return user
