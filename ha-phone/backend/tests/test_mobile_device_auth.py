"""Phone-facing /api/mobile endpoints are unauthenticated at the router level
(the phone never has an admin session), so each one must authenticate the
device itself via device_id + the secret handed out by /provision/complete."""
import pytest


@pytest.fixture
def paired(client):
    resp = client.post(
        "/api/extensions",
        json={"number": 87, "display_name": "Auth Test", "sip_password": "securepass1234567"},
    )
    assert resp.status_code in (200, 201), resp.text
    start = client.post(
        "/api/mobile/provision/start",
        json={"extension_number": 87, "platform": "android", "device_name": ""},
    )
    assert start.status_code == 200, start.text
    done = client.post(
        "/api/mobile/provision/complete",
        json={
            "provisioning_token": start.json()["provisioning_token"],
            "push_token": "fcm-test",
            "os_device_id": "android-test",
        },
    )
    assert done.status_code == 200, done.text
    body = done.json()
    yield body
    client.delete(f"/api/extensions/{resp.json()['id']}")


def test_complete_returns_device_token(paired):
    assert len(paired["device_token"]) >= 32


def test_config_requires_device_token(client, paired):
    assert client.get("/api/mobile/config").status_code == 401
    assert client.get("/api/mobile/config?extension_number=57").status_code == 401
    wrong = client.get(
        "/api/mobile/config",
        headers={"X-Device-Id": str(paired["device_id"]), "X-Device-Token": "wrong"},
    )
    assert wrong.status_code == 401


def test_config_with_valid_token_returns_own_extension(client, paired):
    resp = client.get(
        "/api/mobile/config",
        headers={"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]},
    )
    assert resp.status_code == 200
    assert resp.json()["extension_number"] == 87
    assert resp.json()["sip_password"] == paired["sip_password"]


def test_register_device_requires_device_token(client, paired):
    payload = {"device_id": paired["device_id"], "push_token": "x", "os_device_id": "y"}
    assert client.post("/api/mobile/device/register", json={**payload, "device_token": "nope"}).status_code == 401
    ok = client.post("/api/mobile/device/register", json={**payload, "device_token": paired["device_token"]})
    assert ok.status_code == 200


def test_directory_requires_device_token(client, paired):
    assert client.get("/api/mobile/directory").status_code == 401


def test_directory_lists_other_extensions_and_phonebook(client, paired):
    client.post("/api/phonebook", json={"name": "Pizzeria Test", "number": "0301234567"})
    resp = client.get(
        "/api/mobile/directory",
        headers={"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "87" not in [e["number"] for e in body["extensions"]]  # not the device's own extension
    assert {"name": "Pizzeria Test", "number": "0301234567"} in body["phonebook"]


def test_revoked_device_cannot_authenticate(client, paired):
    revoke = client.post(
        "/api/mobile/device/revoke",
        json={"device_id": paired["device_id"], "extension_number": 87},
    )
    assert revoke.status_code == 200
    resp = client.get(
        "/api/mobile/config",
        headers={"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]},
    )
    assert resp.status_code == 401


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


def test_door_open_code_is_stored_and_listed_for_admin(client):
    resp = client.post(
        "/api/extensions",
        json={"number": 88, "display_name": "Tür", "sip_password": "securepass1234567", "door_open_code": "*1"},
    )
    assert resp.status_code in (200, 201), resp.text
    ext_id = resp.json()["id"]
    try:
        assert resp.json()["door_open_code"] == "*1"
        patched = client.patch(f"/api/extensions/{ext_id}", json={"door_open_code": "0#"})
        assert patched.status_code == 200, patched.text
        assert patched.json()["door_open_code"] == "0#"
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_door_open_code_rejects_non_dtmf_characters(client):
    resp = client.post(
        "/api/extensions",
        json={"number": 89, "display_name": "Tür", "sip_password": "securepass1234567", "door_open_code": "12a"},
    )
    assert resp.status_code == 422


def test_door_open_code_is_validated_on_update(client):
    resp = client.post(
        "/api/extensions",
        json={"number": 88, "display_name": "Tür", "sip_password": "securepass1234567"},
    )
    ext_id = resp.json()["id"]
    try:
        assert client.patch(f"/api/extensions/{ext_id}", json={"door_open_code": "12a"}).status_code == 422
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_door_open_code_can_be_cleared(client):
    resp = client.post(
        "/api/extensions",
        json={"number": 88, "display_name": "Tür", "sip_password": "securepass1234567", "door_open_code": "1"},
    )
    ext_id = resp.json()["id"]
    try:
        patched = client.patch(f"/api/extensions/{ext_id}", json={"door_open_code": ""})
        assert patched.json()["door_open_code"] == ""
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_directory_includes_door_code_video_presence_and_self(client, paired):
    door = client.post(
        "/api/extensions",
        json={
            "number": 88, "display_name": "Haustür", "sip_password": "securepass1234567",
            "door_open_code": "*1", "video_capable": True,
        },
    )
    try:
        body = client.get("/api/mobile/directory", headers=_auth(paired)).json()
        entry = next(e for e in body["extensions"] if e["number"] == "88")
        assert entry == {
            "number": "88", "name": "Haustür", "video": True,
            "door_open_code": "*1", "door_open_remote": False, "presence": "available", "door_actions": [],
        }
        assert body["self"] == {"number": "87", "name": "Auth Test", "presence": "available", "recording_allowed": False, "test_call": True}
    finally:
        client.delete(f"/api/extensions/{door.json()['id']}")
