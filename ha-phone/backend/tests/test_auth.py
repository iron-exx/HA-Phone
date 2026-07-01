"""
SEC-04 — Web UI authentication tests.
These tests use a raw TestClient WITHOUT dependency_overrides
to exercise the real auth middleware.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.database import get_session, get_engine
from backend.models import AdminUser
from backend.auth import hash_password, get_current_user


@pytest.fixture
def unauthed_client(tmp_data_dir, mock_ami):
    """TestClient without auth override — exercises real auth middleware."""
    from backend.main import app
    # Ensure dependency_overrides does NOT contain get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    client = TestClient(app, raise_server_exceptions=True)
    yield client
    # Restore the override so subsequent tests using the default 'client' fixture still work
    fake_admin = AdminUser(id=1, username="admin", hashed_password=b"fake", must_change_password=False)
    app.dependency_overrides[get_current_user] = lambda: fake_admin


@pytest.fixture
def seeded_db(tmp_data_dir):
    """Seed AdminUser with a known password for auth tests."""
    engine = get_engine()
    with Session(engine) as session:
        # Remove any existing AdminUser (test isolation)
        existing = session.exec(select(AdminUser)).all()
        for u in existing:
            session.delete(u)
        session.commit()
        user = AdminUser(
            username="admin",
            hashed_password=hash_password("testpass123"),
            must_change_password=False,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


@pytest.fixture
def seeded_db_must_change(tmp_data_dir):
    """Seed AdminUser with must_change_password=True."""
    engine = get_engine()
    with Session(engine) as session:
        existing = session.exec(select(AdminUser)).all()
        for u in existing:
            session.delete(u)
        session.commit()
        user = AdminUser(
            username="admin",
            hashed_password=hash_password("firstboot"),
            must_change_password=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id


def test_login_success(unauthed_client, seeded_db):
    """SEC-04: Correct password returns 200 and sets bpx_session cookie."""
    resp = unauthed_client.post("/api/auth/login", json={"password": "testpass123"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    assert "bpx_session" in resp.cookies


def test_login_wrong_password(unauthed_client, seeded_db):
    """SEC-04: Wrong password returns 401."""
    resp = unauthed_client.post("/api/auth/login", json={"password": "wrongpass"})
    assert resp.status_code == 401, resp.text


def test_protected_route_unauthed(unauthed_client):
    """SEC-04: GET /api/extensions without session cookie returns 401."""
    resp = unauthed_client.get("/api/extensions")
    assert resp.status_code == 401, resp.text


def test_must_change_password_gate(unauthed_client, seeded_db_must_change):
    """SEC-04: must_change_password=True → protected routes return 403."""
    # Login succeeds
    login_resp = unauthed_client.post("/api/auth/login", json={"password": "firstboot"})
    assert login_resp.status_code == 200
    # Protected route returns 403
    resp = unauthed_client.get("/api/extensions")
    assert resp.status_code == 403, resp.text
    assert resp.headers.get("x-must-change-password") == "true"


def test_change_password(unauthed_client, seeded_db_must_change):
    """SEC-04: change-password clears must_change_password flag."""
    # Login
    unauthed_client.post("/api/auth/login", json={"password": "firstboot"})
    # Change password — this endpoint must NOT use get_current_user (Pitfall 5)
    resp = unauthed_client.post(
        "/api/auth/change-password",
        json={"new_password": "newstrongpass42"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["ok"] is True
    # Verify flag is cleared in DB
    engine = get_engine()
    with Session(engine) as session:
        user = session.exec(select(AdminUser)).first()
        assert user.must_change_password is False
