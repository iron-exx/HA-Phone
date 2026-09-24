"""
Authentication endpoints for ha-phone admin UI (SEC-04).
Public routes: /api/auth/login, /api/auth/change-password, /api/auth/logout
These routes are intentionally NOT protected by get_current_user.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import AdminUser
from backend.auth import (
    hash_password,
    is_default_password,
    login_limiter,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter()

PASSWORD_CHANGE_REQUIRED_MSG = "Passwort ändern erforderlich"


def _client_ip(request: Request) -> str:
    """Client IP for rate limiting. Behind HA ingress this is the ingress proxy
    (all ingress users share one bucket) — acceptable for a single-admin UI."""
    return request.client.host if request.client else "unknown"


class LoginRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    new_password: str


@router.post("/auth/login")
def login(
    body: LoginRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    ip = _client_ip(request)
    retry_after = login_limiter.retry_after(ip)
    if retry_after > 0:
        logger.warning("admin login blocked for %s (locked out, %ds left)", ip, retry_after)
        raise HTTPException(
            status_code=429,
            detail=f"Zu viele Fehlversuche — bitte in {retry_after} s erneut versuchen",
            headers={"Retry-After": str(retry_after)},
        )
    user = session.exec(select(AdminUser).where(AdminUser.username == "admin")).first()
    if not user or not verify_password(body.password, user.hashed_password):
        lockout = login_limiter.register_failure(ip)
        if lockout:
            logger.warning("admin login failed from %s — locked out for %ds", ip, lockout)
        else:
            logger.warning("admin login failed from %s", ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    login_limiter.reset(ip)
    # A default password ("changeme"/"admin") is never accepted silently: force the
    # change-password dialog even if the flag had been cleared before.
    if is_default_password(body.password) and not user.must_change_password:
        user.must_change_password = True
        session.add(user)
        session.commit()
    if user.must_change_password:
        logger.warning("admin login with password that must be changed (from %s)", ip)
    # Session fixation prevention: clear before setting (RESEARCH.md known threat patterns)
    request.session.clear()
    request.session["user_id"] = user.id
    must_change = bool(user.must_change_password)
    return {
        "ok": True,
        "must_change_password": must_change,
        "password_change_required": must_change,
        "message": PASSWORD_CHANGE_REQUIRED_MSG if must_change else None,
    }


@router.post("/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.post("/auth/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    """
    CRITICAL: reads user_id from session DIRECTLY — does NOT use get_current_user.
    get_current_user raises 403 when must_change_password=True, which would block
    the very endpoint needed to clear that flag. (RESEARCH.md Pitfall 5, D-09)
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    if len(body.new_password) < 12:
        raise HTTPException(status_code=422, detail="Password must be at least 12 characters")
    if is_default_password(body.new_password):
        raise HTTPException(status_code=422, detail="Standardpasswort nicht erlaubt")
    user = session.get(AdminUser, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = False
    session.add(user)
    session.commit()
    return {"ok": True}
