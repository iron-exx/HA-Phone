import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

# Override /data paths before importing app
@pytest.fixture(scope="session", autouse=True)
def tmp_data_dir(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    (data_dir / "db").mkdir()
    (data_dir / "asterisk").mkdir()
    # Write a fake ami_secret
    (data_dir / "asterisk" / "ami_secret").write_text("test-secret-abc123")
    # Write a fake session_secret (needed by SessionMiddleware in Plan 02+)
    (data_dir / "asterisk" / "session_secret").write_text("test-session-secret-xyz")
    os.environ["BPX_DATA_DIR"] = str(data_dir)
    return data_dir

@pytest.fixture
def mock_ami():
    with patch("backend.ami.ami_reload_pjsip", new_callable=AsyncMock) as mock_reload, \
         patch("backend.ami.ami_reload_dialplan", new_callable=AsyncMock) as mock_dialplan, \
         patch("backend.ami.ami_reload_voicemail", new_callable=AsyncMock) as mock_vm, \
         patch("backend.ami.get_trunk_status", new_callable=AsyncMock, return_value="Registered") as mock_status, \
         patch("backend.ami.get_trunk_debug", new_callable=AsyncMock, return_value={"Status": "Registered"}) as mock_trunk_debug, \
         patch("backend.ami.get_extension_statuses", new_callable=AsyncMock, return_value=[]) as mock_exts, \
         patch("backend.ami.get_extension_diagnostics", new_callable=AsyncMock, return_value=[]) as mock_ext_diag, \
         patch("backend.ami.get_active_call_count", new_callable=AsyncMock, return_value=0) as mock_calls, \
         patch("backend.ami.get_active_channel_details", new_callable=AsyncMock, return_value=[]) as mock_channels, \
         patch("backend.ami.hangup_channels_for_extension", new_callable=AsyncMock, return_value=0) as mock_hangup:
        yield {"reload_pjsip": mock_reload, "reload_dialplan": mock_dialplan,
               "reload_voicemail": mock_vm, "trunk_status": mock_status,
               "trunk_debug": mock_trunk_debug, "ext_statuses": mock_exts,
               "ext_diagnostics": mock_ext_diag, "active_calls": mock_calls,
               "channel_details": mock_channels, "hangup": mock_hangup}

@pytest.fixture
def client(tmp_data_dir, mock_ami):
    from backend.main import app
    from backend.auth import get_current_user
    from backend.models import AdminUser

    fake_admin = AdminUser(
        id=1,
        username="admin",
        hashed_password=b"fake",
        must_change_password=False,
    )
    app.dependency_overrides[get_current_user] = lambda: fake_admin

    yield TestClient(app)

    app.dependency_overrides.pop(get_current_user, None)
