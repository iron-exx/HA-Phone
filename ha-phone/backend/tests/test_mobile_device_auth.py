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
