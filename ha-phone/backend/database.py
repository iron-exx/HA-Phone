import os
from sqlmodel import create_engine, Session, SQLModel
from sqlalchemy import text, inspect
from sqlalchemy.engine import Engine


def _make_database_url() -> str:
    """Compute the database URL using BPX_DATA_DIR if set, else /data default."""
    _data_dir = os.environ.get("BPX_DATA_DIR", "")
    if _data_dir:
        return f"sqlite:///{_data_dir}/db/bpx.db"
    return "sqlite:////data/db/bpx.db"


# Lazily initialized — set via init_db() called from lifespan
_engine: Engine | None = None

# Exported value — used in test_models.py to check the path
DATABASE_URL: str = "sqlite:////data/db/bpx.db"


def run_migrations(engine: Engine) -> None:
    """Apply incremental SQLite migrations."""
    with engine.connect() as conn:
        inspector = inspect(engine)
        # Phase 4: add `did` column to timecondition if absent
        tables = inspector.get_table_names()
        if "timecondition" in tables:
            cols = [c["name"] for c in inspector.get_columns("timecondition")]
            if "did" not in cols:
                conn.execute(
                    text("ALTER TABLE timecondition ADD COLUMN did TEXT NOT NULL DEFAULT ''")
                )
                conn.commit()
        if "extension" in tables:
            cols = [c["name"] for c in inspector.get_columns("extension")]
            if "video_capable" not in cols:
                conn.execute(
                    text("ALTER TABLE extension ADD COLUMN video_capable INTEGER NOT NULL DEFAULT 0")
                )
                conn.commit()
            if "internal_only" not in cols:
                conn.execute(
                    text("ALTER TABLE extension ADD COLUMN internal_only INTEGER NOT NULL DEFAULT 0")
                )
                conn.commit()
            if "provisioning_token" not in cols:
                conn.execute(
                    text("ALTER TABLE extension ADD COLUMN provisioning_token TEXT NOT NULL DEFAULT ''")
                )
                conn.commit()
            if "numeric_callerid" not in cols:
                conn.execute(
                    text("ALTER TABLE extension ADD COLUMN numeric_callerid INTEGER NOT NULL DEFAULT 0")
                )
                conn.commit()
            if "enabled" not in cols:
                # Found via test_migrations.py's from-scratch legacy-DB simulation
                # (Roadmap A.8): `enabled` had no migration at all, so upgrading a
                # database that predates it would crash on the very first ORM
                # query touching the extension table.
                conn.execute(
                    text("ALTER TABLE extension ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1")
                )
                conn.commit()
        if "trunk" in tables:
            cols = [c["name"] for c in inspector.get_columns("trunk")]
            if "codecs" not in cols:
                conn.execute(
                    text("ALTER TABLE trunk ADD COLUMN codecs TEXT NOT NULL DEFAULT 'ulaw,alaw'")
                )
                conn.commit()
        if "adminuser" in tables:
            cols = [c["name"] for c in inspector.get_columns("adminuser")]
            if "must_change_password" not in cols:
                conn.execute(
                    text("ALTER TABLE adminuser ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 1")
                )
                conn.commit()
        if "ringgroup" in tables:
            cols = [c["name"] for c in inspector.get_columns("ringgroup")]
            if "number" not in cols:
                conn.execute(
                    text("ALTER TABLE ringgroup ADD COLUMN number INTEGER NOT NULL DEFAULT 0")
                )
                conn.commit()
        if "provisioneddevice" in tables:
            cols = [c["name"] for c in inspector.get_columns("provisioneddevice")]
            if "extension_numbers" not in cols:
                conn.execute(
                    text("ALTER TABLE provisioneddevice ADD COLUMN extension_numbers TEXT NOT NULL DEFAULT ''")
                )
                conn.commit()
                # Backfill from the old single extension_id column (stored the
                # extension's *number*, despite the misleading name) so devices
                # provisioned before multi-line support keep working unchanged.
                if "extension_id" in cols:
                    conn.execute(
                        text(
                            "UPDATE provisioneddevice SET extension_numbers = CAST(extension_id AS TEXT) "
                            "WHERE extension_id IS NOT NULL AND extension_id != 0 AND extension_numbers = ''"
                        )
                    )
                    conn.commit()


def init_db() -> Engine:
    """Initialize the database engine and create all tables.

    Must be called before the first request. lifespan() calls this.
    Tests call this via the TestClient startup sequence.
    """
    global _engine, DATABASE_URL
    DATABASE_URL = _make_database_url()
    _engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(_engine)
    run_migrations(_engine)
    return _engine


def get_engine() -> Engine:
    """Return the engine, initializing if needed."""
    global _engine
    if _engine is None:
        init_db()
    return _engine


def get_session():
    with Session(get_engine()) as session:
        yield session
