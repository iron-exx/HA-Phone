"""Simulates an upgrade from an old HA-Phone database (missing every column
added since) to HEAD, without going through the shared test-session engine.

Roadmap Phase A.8's Fertig-Kriterium: "ein Upgrade von der aeltesten
unterstuetzten Version auf HEAD laeuft in einem Testlauf ohne manuelle
SQL-Eingriffe durch." Nothing exercised this before - each migration was
only ever verified by hand when it was written. This builds a legacy-shaped
SQLite file by hand (raw SQL, the exact old column sets), then runs the real
create_all() + run_migrations() sequence init_db() uses in production and
checks every added column exists with the right default, old data survived,
and the ORM can read the result without crashing.
"""

from sqlalchemy import create_engine, inspect, text
from sqlmodel import SQLModel, Session, select

from backend.database import run_migrations
from backend.models import Extension, Trunk, ProvisionedDevice


def _build_legacy_db(path):
    """Create tables shaped like they were before any of the ALTER TABLE
    migrations in run_migrations() existed - the columns each migration adds
    are deliberately absent."""
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE extension ("
            "id INTEGER PRIMARY KEY, number INTEGER NOT NULL, "
            "display_name TEXT NOT NULL, sip_password TEXT NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO extension (id, number, display_name, sip_password) "
            "VALUES (1, 11, 'Legacy Ext', 'plaintext-legacy-pw')"
        ))
        conn.execute(text(
            "CREATE TABLE timecondition ("
            "id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "open_hours_start TEXT NOT NULL, open_hours_end TEXT NOT NULL, "
            "open_days TEXT NOT NULL, open_destination INTEGER NOT NULL, "
            "closed_destination INTEGER NOT NULL)"
        ))
        conn.execute(text(
            "CREATE TABLE trunk ("
            "id INTEGER PRIMARY KEY, registrar_host TEXT, port INTEGER, "
            "transport TEXT, domain TEXT, auth_username TEXT NOT NULL, "
            "password TEXT NOT NULL, phone_number TEXT NOT NULL, reg_refresh INTEGER)"
        ))
        conn.execute(text(
            "INSERT INTO trunk (id, registrar_host, port, transport, domain, "
            "auth_username, password, phone_number, reg_refresh) VALUES "
            "(1, 'sip.example.com', 5060, 'udp', '', '123', 'legacy-trunk-pw', '0491234', 60)"
        ))
        conn.execute(text(
            "CREATE TABLE adminuser (id INTEGER PRIMARY KEY, username TEXT NOT NULL, "
            "hashed_password BLOB NOT NULL)"
        ))
        conn.execute(text(
            "CREATE TABLE ringgroup (id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
            "extension_numbers TEXT NOT NULL, ring_timeout INTEGER NOT NULL)"
        ))
        conn.execute(text(
            "CREATE TABLE provisioneddevice (id INTEGER PRIMARY KEY, name TEXT, "
            "manufacturer TEXT, model TEXT, mac TEXT, extension_id INTEGER, template_id INTEGER)"
        ))
        conn.execute(text(
            "INSERT INTO provisioneddevice (id, name, manufacturer, model, mac, "
            "extension_id, template_id) VALUES (1, 'Old Phone', 'Yealink', 'T54W', "
            "'aabbccddeeff', 11, 0)"
        ))
    return engine


def test_legacy_database_migrates_to_head_without_manual_sql(tmp_path):
    engine = _build_legacy_db(tmp_path / "legacy.db")

    # Exactly what init_db() does in production: create any brand-new tables
    # that didn't exist at all in the old schema, then run the ALTER TABLE
    # migrations that add columns to tables that DID already exist.
    SQLModel.metadata.create_all(engine)
    run_migrations(engine)

    inspector = inspect(engine)

    ext_cols = {c["name"] for c in inspector.get_columns("extension")}
    assert {"video_capable", "internal_only", "provisioning_token", "numeric_callerid"} <= ext_cols

    tc_cols = {c["name"] for c in inspector.get_columns("timecondition")}
    assert "did" in tc_cols

    trunk_cols = {c["name"] for c in inspector.get_columns("trunk")}
    assert "codecs" in trunk_cols

    admin_cols = {c["name"] for c in inspector.get_columns("adminuser")}
    assert "must_change_password" in admin_cols

    rg_cols = {c["name"] for c in inspector.get_columns("ringgroup")}
    assert "number" in rg_cols

    device_cols = {c["name"] for c in inspector.get_columns("provisioneddevice")}
    assert "extension_numbers" in device_cols

    # Old data must survive migration untouched, and new columns get their
    # documented defaults instead of NULL.
    with engine.connect() as conn:
        display_name = conn.execute(text("SELECT display_name FROM extension WHERE id = 1")).scalar()
        assert display_name == "Legacy Ext"
        codecs = conn.execute(text("SELECT codecs FROM trunk WHERE id = 1")).scalar()
        assert codecs == "ulaw,alaw"

    # The old provisioneddevice.extension_id (single number) must be backfilled
    # into the new extension_numbers (comma list) so pre-upgrade devices keep
    # provisioning correctly instead of silently losing their assignment.
    with engine.connect() as conn:
        numbers = conn.execute(
            text("SELECT extension_numbers FROM provisioneddevice WHERE id = 1")
        ).scalar()
        assert numbers == "11"

    # The ORM must be able to read every migrated row without crashing -
    # including a legacy plaintext secret (EncryptedString's decrypt fallback).
    with Session(engine) as session:
        ext = session.exec(select(Extension)).first()
        assert ext.sip_password == "plaintext-legacy-pw"
        assert ext.numeric_callerid is False

        trunk = session.exec(select(Trunk)).first()
        assert trunk.password == "legacy-trunk-pw"
        assert trunk.codecs == "ulaw,alaw"

        device = session.exec(select(ProvisionedDevice)).first()
        assert device.extension_numbers == "11"


def test_migrations_are_idempotent(tmp_path):
    """Running migrations twice (e.g. a container restarting mid-upgrade)
    must not fail or duplicate columns."""
    engine = _build_legacy_db(tmp_path / "legacy.db")
    SQLModel.metadata.create_all(engine)
    run_migrations(engine)
    run_migrations(engine)  # must be a no-op, not an error

    inspector = inspect(engine)
    ext_cols = [c["name"] for c in inspector.get_columns("extension")]
    assert ext_cols.count("numeric_callerid") == 1
