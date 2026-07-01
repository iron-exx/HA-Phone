"""
Authentication utilities for ha-phone admin UI (SEC-04).
"""
import os
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
