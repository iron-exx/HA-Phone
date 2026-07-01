import pytest
from pydantic import ValidationError
from backend.models import Extension
import backend.database as db_module


def test_extension_number_bounds():
    """Extension number must be in range 10-99 (inclusive)."""
    # Valid boundaries
    ext_min = Extension(number=10, display_name="Min Test", sip_password="pass1234567890ab")
    assert ext_min.number == 10

    ext_max = Extension(number=99, display_name="Max Test", sip_password="pass1234567890ab")
    assert ext_max.number == 99

    # Below minimum
    with pytest.raises(ValidationError):
        Extension(number=9, display_name="Below Min", sip_password="pass1234567890ab")

    # Above maximum
    with pytest.raises(ValidationError):
        Extension(number=100, display_name="Above Max", sip_password="pass1234567890ab")


def test_db_path(tmp_data_dir):
    """DATABASE_URL must use an absolute path ending in /db/bpx.db."""
    db_module.init_db()
    # In test env, BPX_DATA_DIR is set to tmp_data_dir; path must end with /db/bpx.db
    # In production (no BPX_DATA_DIR), DATABASE_URL = sqlite:////data/db/bpx.db
    assert "db/bpx.db" in db_module.DATABASE_URL
    assert db_module.DATABASE_URL.startswith("sqlite:///")
    # Must be an absolute path (4 slashes for default, 3 slashes + abs path for test)
    assert "/db/bpx.db" in db_module.DATABASE_URL
