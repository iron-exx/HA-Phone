"""The explicit "Türstation" switch (Extension.is_door): what makes an extension a
door station for the doorbell history and the app, whatever the manufacturer."""
from sqlalchemy import create_engine, text
from sqlmodel import SQLModel, Session, select

from backend import doorbell
from backend.database import run_migrations
from backend.models import Extension


def _create(client, **body):
    """POST an extension on the first free number (the test database is shared)."""
    for number in range(99, 9, -1):
        resp = client.post("/api/extensions", json={
            "number": number, "display_name": "Tür", "sip_password": "securepass1234567", **body})
        if resp.status_code in (200, 201):
            return resp
    raise AssertionError("no free extension number")


def _ext(**kw):
    return Extension(number=kw.pop("number", 16), display_name="x", **kw)


def test_only_the_switch_makes_a_door():
    assert doorbell.is_door(_ext(is_door=True))
    # Door fields alone no longer count: a phone with a camera or a code is not a door.
    assert not doorbell.is_door(_ext(doorbell_camera="camera.haustuer"))
    assert not doorbell.is_door(_ext(door_open_code="*1"))
    assert not doorbell.is_door(_ext())


def test_api_creates_patches_and_returns_the_switch(client):
    created = _create(client, is_door=True)
    ext_id = created.json()["id"]
    try:
        assert created.json()["is_door"] is True
        patched = client.patch(f"/api/extensions/{ext_id}", json={"is_door": False})
        assert patched.status_code == 200 and patched.json()["is_door"] is False
        listed = next(e for e in client.get("/api/extensions").json() if e["id"] == ext_id)
        assert listed["is_door"] is False
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_new_extensions_are_no_doors_by_default(client):
    created = _create(client)
    try:
        assert created.json()["is_door"] is False
    finally:
        client.delete(f"/api/extensions/{created.json()['id']}")


def test_migration_marks_extensions_with_door_settings_as_doors(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE extension (id INTEGER PRIMARY KEY, number INTEGER NOT NULL, "
            "display_name TEXT NOT NULL, sip_password TEXT NOT NULL, "
            "door_open_code TEXT NOT NULL DEFAULT '', door_actions TEXT NOT NULL DEFAULT '[]', "
            "door_open_webhook TEXT NOT NULL DEFAULT '', doorbell_camera TEXT NOT NULL DEFAULT '')"))
        rows = [
            (1, 11, "", "[]", "", ""),                      # plain phone
            (2, 16, "", "[]", "", "camera.haustuer"),       # camera only (the Akuvox case)
            (3, 17, "*1", "[]", "", ""),                    # door code
            (4, 18, "", "[]", "http://ha/api/webhook/x", ""),
            (5, 19, "", '[{"label":"Licht","service":"light.turn_on","entity_id":"light.a"}]', "", ""),
        ]
        for i, n, code, actions, hook, cam in rows:
            conn.execute(text(
                "INSERT INTO extension (id, number, display_name, sip_password, door_open_code, "
                "door_actions, door_open_webhook, doorbell_camera) VALUES (:i, :n, 'x', 'pw', :c, :a, :h, :cam)"),
                {"i": i, "n": n, "c": code, "a": actions, "h": hook, "cam": cam})
    SQLModel.metadata.create_all(engine)
    run_migrations(engine)
    run_migrations(engine)  # idempotent, and must not re-mark a door the admin switched off
    with Session(engine) as s:
        doors = {e.number: e.is_door for e in s.exec(select(Extension)).all()}
    assert doors == {11: False, 16: True, 17: True, 18: True, 19: True}


def test_migration_backfills_only_once(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'new.db'}")
    SQLModel.metadata.create_all(engine)
    run_migrations(engine)
    with Session(engine) as s:
        s.add(_ext(number=20, doorbell_camera="camera.garten", is_door=False))
        s.commit()
    run_migrations(engine)
    with Session(engine) as s:
        assert s.exec(select(Extension)).first().is_door is False
