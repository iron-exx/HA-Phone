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


# ── Login rate limiting / default-password enforcement (audit fix) ──────────

class _FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_limiter_locks_after_five_failures_and_doubles():
    from backend.auth import LoginRateLimiter
    clock = _FakeClock()
    lim = LoginRateLimiter(clock=clock)
    for _ in range(4):
        assert lim.register_failure("1.2.3.4") == 0
    assert lim.retry_after("1.2.3.4") == 0
    assert lim.register_failure("1.2.3.4") == 60
    assert 59 <= lim.retry_after("1.2.3.4") <= 61
    clock.now += 61
    assert lim.retry_after("1.2.3.4") == 0
    # next failure after a lockout immediately doubles
    assert lim.register_failure("1.2.3.4") == 120
    clock.now += 121
    assert lim.register_failure("1.2.3.4") == 240
    # other IPs are unaffected
    assert lim.retry_after("5.6.7.8") == 0


def test_limiter_caps_at_15_minutes_and_resets():
    from backend.auth import LoginRateLimiter
    clock = _FakeClock()
    lim = LoginRateLimiter(clock=clock)
    durations = []
    for _ in range(20):
        d = lim.register_failure("ip")
        if d:
            durations.append(d)
            clock.now += d + 1
    assert max(durations) == 900
    lim.reset("ip")
    assert lim.register_failure("ip") == 0


def test_login_returns_429_after_repeated_failures(unauthed_client, seeded_db):
    for _ in range(5):
        r = unauthed_client.post("/api/auth/login", json={"password": "wrong"})
        assert r.status_code == 401
    r = unauthed_client.post("/api/auth/login", json={"password": "wrong"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0
    # even the correct password is refused while locked out
    r = unauthed_client.post("/api/auth/login", json={"password": "testpass123"})
    assert r.status_code == 429


def test_login_failure_is_logged(unauthed_client, seeded_db, caplog):
    import logging
    with caplog.at_level(logging.WARNING, logger="backend.routers.auth"):
        unauthed_client.post("/api/auth/login", json={"password": "wrong"})
    assert any("admin login failed" in rec.message for rec in caplog.records)


def test_successful_login_resets_failure_counter(unauthed_client, seeded_db):
    for _ in range(4):
        unauthed_client.post("/api/auth/login", json={"password": "wrong"})
    assert unauthed_client.post("/api/auth/login", json={"password": "testpass123"}).status_code == 200
    for _ in range(4):
        assert unauthed_client.post("/api/auth/login", json={"password": "wrong"}).status_code == 401


@pytest.mark.parametrize("default_pw", ["changeme", "admin"])
def test_default_password_forces_change(unauthed_client, tmp_data_dir, default_pw):
    engine = get_engine()
    with Session(engine) as session:
        for u in session.exec(select(AdminUser)).all():
            session.delete(u)
        session.commit()
        # flag already cleared — a default password must still force the change
        session.add(AdminUser(username="admin", hashed_password=hash_password(default_pw),
                              must_change_password=False))
        session.commit()
    r = unauthed_client.post("/api/auth/login", json={"password": default_pw})
    assert r.status_code == 200
    body = r.json()
    assert body["must_change_password"] is True
    assert body["password_change_required"] is True
    assert body["message"] == "Passwort ändern erforderlich"
    # protected endpoints now answer 403 + X-Must-Change-Password
    r = unauthed_client.get("/api/extensions")
    assert r.status_code == 403
    assert r.headers.get("x-must-change-password") == "true"


def test_change_password_rejects_default(unauthed_client, seeded_db_must_change):
    unauthed_client.post("/api/auth/login", json={"password": "firstboot"})
    r = unauthed_client.post("/api/auth/change-password", json={"new_password": "admin"})
    assert r.status_code == 422
