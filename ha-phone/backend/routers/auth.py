"""
Authentication endpoints for ha-phone admin UI (SEC-04).
Public routes: /api/auth/login, /api/auth/change-password, /api/auth/logout
These routes are intentionally NOT protected by get_current_user.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import AdminUser
from backend.auth import verify_password, hash_password

router = APIRouter()


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
    user = session.exec(select(AdminUser).where(AdminUser.username == "admin")).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Session fixation prevention: clear before setting (RESEARCH.md known threat patterns)
    request.session.clear()
    request.session["user_id"] = user.id
    return {"ok": True, "must_change_password": user.must_change_password}


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
    user = session.get(AdminUser, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    user.hashed_password = hash_password(body.new_password)
    user.must_change_password = False
    session.add(user)
    session.commit()
    return {"ok": True}
