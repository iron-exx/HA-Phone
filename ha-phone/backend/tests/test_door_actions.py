"""Home Assistant quick actions for door stations (light, garage, alarm) from the app."""
from unittest.mock import AsyncMock, patch

import pytest

from backend.tests.test_mobile_device_auth import paired  # noqa: F401 (fixture)

ACTIONS = [
    {"label": "Licht", "service": "light.turn_on", "entity_id": "light.hausflur"},
    {"label": "Garage", "service": "cover.open_cover", "entity_id": "cover.garage"},
]


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


@pytest.fixture
def door(client):
    for n in range(40, 80):
        resp = client.post("/api/extensions", json={
            "number": n, "display_name": "Haustür", "sip_password": "securepass1234567",
            "door_open_code": "*1", "door_actions": ACTIONS,
        })
        if resp.status_code == 200:
            break
    assert resp.status_code == 200, resp.text
    yield resp.json()
    client.delete(f"/api/extensions/{resp.json()['id']}")


def test_door_actions_are_stored_and_returned_to_admin(client, door):
    assert door["door_actions"] == ACTIONS
    patched = client.patch(f"/api/extensions/{door['id']}", json={"door_actions": ACTIONS[:1]})
    assert patched.status_code == 200, patched.text
    assert patched.json()["door_actions"] == ACTIONS[:1]


@pytest.mark.parametrize("bad", [
    [{"label": "x", "service": "light.turn_on; rm", "entity_id": "light.a"}],
    [{"label": "x", "service": "light.turn_on", "entity_id": "light.A B"}],
    [{"label": "", "service": "light.turn_on", "entity_id": "light.a"}],
    [{"label": "x" * 30, "service": "light.turn_on", "entity_id": "light.a"}],
    [{"label": "x", "service": "light.turn_on", "entity_id": "light.a"}] * 5,
])
def test_invalid_door_actions_are_rejected(client, door, bad):
    assert client.patch(f"/api/extensions/{door['id']}", json={"door_actions": bad}).status_code == 422


def test_directory_lists_action_labels_only(client, paired, door):
    body = client.get("/api/mobile/directory", headers=_auth(paired)).json()
    entry = next(e for e in body["extensions"] if e["number"] == str(door["number"]))
    assert entry["door_actions"] == [{"index": 0, "label": "Licht"}, {"index": 1, "label": "Garage"}]


def test_run_door_action_calls_home_assistant(client, paired, door):
    with patch("backend.ha_api.call_service", new_callable=AsyncMock) as call:
        resp = client.post("/api/mobile/door-action", json={"extension": str(door["number"]), "index": 1}, headers=_auth(paired))
    assert resp.status_code == 200, resp.text
    call.assert_awaited_once_with("cover.open_cover", "cover.garage")


def test_run_door_action_validates_input(client, paired, door):
    h = _auth(paired)
    with patch("backend.ha_api.call_service", new_callable=AsyncMock) as call:
        assert client.post("/api/mobile/door-action", json={"extension": str(door["number"]), "index": 7}, headers=h).status_code == 404
        assert client.post("/api/mobile/door-action", json={"extension": "5", "index": 0}, headers=h).status_code == 404
        assert client.post("/api/mobile/door-action", json={"extension": str(door["number"]), "index": 0}).status_code == 401
    call.assert_not_awaited()


def test_run_door_action_reports_home_assistant_failure(client, paired, door):
    from fastapi import HTTPException
    with patch("backend.ha_api.call_service", new_callable=AsyncMock, side_effect=HTTPException(502, "HA down")):
        resp = client.post("/api/mobile/door-action", json={"extension": str(door["number"]), "index": 0}, headers=_auth(paired))
    assert resp.status_code == 502


def test_door_open_webhook_is_called_without_a_call(client, paired, door):
    url = "http://homeassistant.local:8123/api/webhook/haustuer"
    assert client.patch(f"/api/extensions/{door['id']}", json={"door_open_webhook": url}).json()["door_open_webhook"] == url
    entry = next(e for e in client.get("/api/mobile/directory", headers=_auth(paired)).json()["extensions"] if e["number"] == str(door["number"]))
    assert entry["door_open_remote"] is True and url not in str(entry)
    with patch("backend.ha_api.call_webhook", new_callable=AsyncMock) as hook:
        resp = client.post("/api/mobile/door-open", json={"extension": str(door["number"])}, headers=_auth(paired))
    assert resp.status_code == 200, resp.text
    called_url, payload = hook.await_args.args
    assert called_url == url and payload["event"] == "door_open" and payload["door_extension"] == str(door["number"])
    assert payload["by_extension"] == "87"


def test_door_open_needs_webhook_auth_and_valid_url(client, paired, door):
    client.patch(f"/api/extensions/{door['id']}", json={"door_open_webhook": ""})
    with patch("backend.ha_api.call_webhook", new_callable=AsyncMock) as hook:
        assert client.post("/api/mobile/door-open", json={"extension": str(door["number"])}, headers=_auth(paired)).status_code == 404
        assert client.post("/api/mobile/door-open", json={"extension": str(door["number"])}).status_code == 401
    hook.assert_not_awaited()
    for bad in ("ftp://x/y", "javascript:alert(1)", "http://a b"):
        assert client.patch(f"/api/extensions/{door['id']}", json={"door_open_webhook": bad}).status_code == 422
