"""'Test-Anruf an mich': the PBX rings the device's own extension after a delay."""
import asyncio
from unittest.mock import AsyncMock, patch

from backend.routers import mobile_features
from backend.tests.test_mobile_device_auth import paired  # noqa: F401 (fixture)


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


def test_test_call_rings_own_extension_and_is_rate_limited(client, paired):
    mobile_features._last_test_call.clear()
    with patch("backend.ami.originate_test_call", new_callable=AsyncMock) as orig:
        resp = client.post("/api/mobile/test-call", json={"delay_sec": 0}, headers=_auth(paired))
        assert resp.status_code == 202, resp.text
        assert resp.json() == {"scheduled": True, "delay_sec": 0, "number": "87"}
        for _ in range(20):
            if orig.await_count:
                break
            client.get("/api/mobile/directory", headers=_auth(paired))  # let the event loop run
        orig.assert_awaited_once_with("87")
        again = client.post("/api/mobile/test-call", json={"delay_sec": 0}, headers=_auth(paired))
    assert again.status_code == 429


def test_test_call_needs_device_auth_and_sane_delay(client, paired):
    mobile_features._last_test_call.clear()
    assert client.post("/api/mobile/test-call", json={}).status_code == 401
    assert client.post("/api/mobile/test-call", json={"delay_sec": 999}, headers=_auth(paired)).status_code == 422


def test_directory_announces_test_call_and_dialplan_has_context(client, paired, tmp_data_dir):
    assert client.get("/api/mobile/directory", headers=_auth(paired)).json()["self"]["test_call"] is True
    routing = (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()
    assert "[haphone-testcall]" in routing and "same => n,Echo()" in routing
    assert routing.index("[haphone-testcall]") < routing.index("[from-internal]")
