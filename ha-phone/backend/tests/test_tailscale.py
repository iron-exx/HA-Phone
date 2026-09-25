"""Tailscale integration: admin page API, key hand-out at QR pairing, cleanup on
unpairing. The Tailscale API is faked with an httpx.MockTransport."""
import json

import httpx
import pytest

from backend import tailnet
from backend.routers import tailscale as ts_router

PBX_V4 = "100.101.102.103"


class FakeTailscale:
    def __init__(self):
        self.valid = ("cid", "csecret")
        self.key_error = None  # (status, message)
        self.devices_status = 200
        self.keys = {}
        self.deleted_keys = []
        self.deleted_devices = []
        self.devices = [
            {"id": "1", "nodeId": "nPBX", "name": "homeassistant.tail1234.ts.net.", "hostname": "homeassistant",
             "addresses": [PBX_V4, "fd7a:115c:a1e0::1"], "tags": ["tag:haphone-pbx"]},
        ]
        self.token_calls = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/v2/oauth/token":
            self.token_calls += 1
            form = dict(x.split("=") for x in request.content.decode().split("&"))
            if (form.get("client_id"), form.get("client_secret")) != self.valid:
                return httpx.Response(401, json={"message": "invalid client"})
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        assert request.headers["Authorization"] == "Bearer tok"
        if path == "/api/v2/tailnet/-/keys" and request.method == "POST":
            if self.key_error:
                return httpx.Response(self.key_error[0], json={"message": self.key_error[1]})
            body = json.loads(request.content)
            caps = body["capabilities"]["devices"]["create"]
            assert caps == {"reusable": False, "ephemeral": False, "preauthorized": True,
                            "tags": ["tag:haphone-phone"]}
            kid = f"k{len(self.keys) + 1}"
            self.keys[kid] = body
            return httpx.Response(200, json={"id": kid, "key": f"tskey-auth-{kid}"})
        if path.startswith("/api/v2/tailnet/-/keys/") and request.method == "DELETE":
            self.deleted_keys.append(path.rsplit("/", 1)[1])
            return httpx.Response(200)
        if path == "/api/v2/tailnet/-/devices":
            if self.devices_status != 200:
                return httpx.Response(self.devices_status, json={"message": "forbidden"})
            return httpx.Response(200, json={"devices": self.devices})
        if path.startswith("/api/v2/device/") and request.method == "DELETE":
            self.deleted_devices.append(path.rsplit("/", 1)[1])
            return httpx.Response(200)
        return httpx.Response(404)


@pytest.fixture
def fake_ts(monkeypatch):
    fake = FakeTailscale()
    monkeypatch.setattr(ts_router, "_transport", httpx.MockTransport(fake.handler))
    monkeypatch.setattr(
        tailnet, "detect_tailnet_address",
        lambda: tailnet.TailnetAddress(ipv4=PBX_V4, ipv6="fd7a:115c:a1e0::1", missing=False),
    )
    tailnet.TailscaleClient.clear_token_cache()
    yield fake
    tailnet.TailscaleClient.clear_token_cache()


@pytest.fixture
def connected(client, fake_ts):
    resp = client.put("/api/tailscale/config", json={"client_id": "cid", "client_secret": "csecret"})
    assert resp.status_code == 200 and resp.json()["ok"], resp.text
    yield fake_ts
    client.delete("/api/tailscale/config")


def _pair(client):
    """Pairs an app on the first free extension number (the test DB is shared)."""
    for number in range(99, 9, -1):
        resp = client.post("/api/extensions", json={"number": number, "display_name": "TS Test",
                                                    "sip_password": "securepass1234567"})
        if resp.status_code in (200, 201):
            break
    else:
        raise AssertionError("no free extension number")
    start = client.post("/api/mobile/provision/start",
                        json={"extension_number": number, "platform": "android", "device_name": "Pixel 6"})
    done = client.post("/api/mobile/provision/complete", json={
        "provisioning_token": start.json()["provisioning_token"],
        "push_token": "", "os_device_id": "emu", "device_name": "Pixel 6",
    })
    assert done.status_code == 200, done.text
    return resp.json()["id"], number, done.json()


# ── unit ──

def test_device_hostname_is_a_dns_label():
    assert tailnet.device_hostname(13, "Pixel 6 (Sandro)") == "haphone-13-pixel-6-sandro"
    assert tailnet.device_hostname(13, "") == "haphone-13"
    assert len(tailnet.device_hostname(13, "x" * 200)) <= 63


def test_detect_address_ignores_non_tailnet_ips():
    a = tailnet.detect_tailnet_address(lambda _: "192.168.7.10", lambda _: None)
    assert a.missing and a.ipv4 is None
    b = tailnet.detect_tailnet_address(lambda _: PBX_V4, lambda _: None)
    assert not b.missing and b.ipv4 == PBX_V4


def test_ipv6_parsed_from_proc(tmp_path):
    f = tmp_path / "if_inet6"
    f.write_text("fd7a115ca1e000000000000000000001 05 80 00 80 tailscale0\n"
                 "fe800000000000000000000000000001 05 40 20 80 tailscale0\n")
    assert tailnet._ipv6_of_interface("tailscale0", str(f)) == "fd7a:115c:a1e0::1"


# ── admin API ──

def test_config_empty_by_default(client, fake_ts):
    body = client.get("/api/tailscale/config").json()
    assert body["configured"] is False
    assert body["pbx"] == {"ipv4": PBX_V4, "ipv6": "fd7a:115c:a1e0::1", "found": True}
    assert "tag:haphone-phone" in body["acl_snippet"]


def test_wrong_secret_is_reported_and_not_saved(client, fake_ts):
    resp = client.put("/api/tailscale/config", json={"client_id": "cid", "client_secret": "nope"})
    body = resp.json()
    assert body["ok"] is False
    assert any(s["key"] == "login" and not s["ok"] and "falsch" in s["message"] for s in body["steps"])
    assert client.get("/api/tailscale/config").json()["configured"] is False


def test_missing_tag_is_reported(client, fake_ts):
    fake_ts.key_error = (400, "requested tags [tag:haphone-phone] are invalid or not permitted")
    body = client.post("/api/tailscale/test", json={"client_id": "cid", "client_secret": "csecret"}).json()
    step = next(s for s in body["steps"] if s["key"] == "keys")
    assert not step["ok"] and "tag:haphone-phone" in step["message"]


def test_missing_devices_scope_is_reported(client, fake_ts):
    fake_ts.devices_status = 403
    body = client.post("/api/tailscale/test", json={"client_id": "cid", "client_secret": "csecret"}).json()
    step = next(s for s in body["steps"] if s["key"] == "devices")
    assert not step["ok"] and "Devices Core" in step["message"]


def test_connect_saves_and_never_returns_the_secret(client, connected):
    body = client.get("/api/tailscale/config").json()
    assert body["configured"] and body["enabled"] and body["secret_set"]
    assert body["tailnet"] == "tail1234.ts.net"
    assert body["pbx_magicdns"] == "homeassistant.tail1234.ts.net"
    assert "csecret" not in json.dumps(body)
    # The probe key of the connection test was deleted again.
    assert connected.deleted_keys == ["k1"]


def test_retest_with_stored_secret(client, connected):
    body = client.post("/api/tailscale/test", json={"client_id": "cid"}).json()
    assert body["ok"] is True


def test_invalid_tag_rejected(client, fake_ts):
    resp = client.post("/api/tailscale/test", json={"client_id": "cid", "client_secret": "csecret", "tag": "phones"})
    assert resp.status_code == 422


def test_access_token_is_cached(client, connected):
    calls = connected.token_calls
    client.post("/api/tailscale/test", json={"client_id": "cid"})
    assert connected.token_calls == calls


# ── pairing ──

def test_pairing_without_oauth_client_asks_the_phone_to_log_in(client, fake_ts):
    ext_id, num, body = _pair(client)
    try:
        ts = body["tailscale"]
        assert ts["login"] == "interactive" and ts["auth_key"] is None
        assert ts["pbx_tailnet_ip"] == PBX_V4
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_pairing_without_tailscale_on_the_box_has_no_block(client, fake_ts, monkeypatch):
    monkeypatch.setattr(tailnet, "detect_tailnet_address", lambda: tailnet.TailnetAddress())
    ext_id, num, body = _pair(client)
    try:
        assert body["tailscale"] is None
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_device_list_without_oauth_client_comes_from_the_apps(client, fake_ts):
    ext_id, num, body = _pair(client)
    try:
        client.post("/api/mobile/device/tailscale", json={
            "device_id": body["device_id"], "device_token": body["device_token"],
            "node_id": "nSELF1", "ip": "100.80.9.9"})
        devs = [d for d in client.get("/api/tailscale/devices").json() if d["id"] == "nSELF1"]
        assert devs and devs[0]["extension_number"] == num
        assert devs[0]["addresses"] == ["100.80.9.9"] and devs[0]["removable"] is False
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_pairing_hands_out_a_one_time_key(client, connected):
    ext_id, num, body = _pair(client)
    try:
        ts = body["tailscale"]
        assert ts["login"] == "auth_key" and ts["auth_key"].startswith("tskey-auth-")
        assert ts["hostname"] == f"haphone-{num}-pixel-6"
        assert ts["pbx_tailnet_ip"] == PBX_V4
        assert ts["sip_domain_tailnet"] == f"{PBX_V4}:5061"
        assert ts["api_base_tailnet"] == f"http://{PBX_V4}"
        created = list(connected.keys.values())[-1]
        assert created["expirySeconds"] == 3600
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_pairing_still_works_when_tailscale_fails(client, connected):
    connected.key_error = (500, "boom")
    ext_id, num, body = _pair(client)
    try:
        assert body["tailscale"]["login"] == "interactive"
        assert body["sip_password"]
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_switched_off_hands_out_no_key(client, connected):
    client.patch("/api/tailscale/config", json={"enabled": False})
    ext_id, num, body = _pair(client)
    try:
        assert body["tailscale"] is None
    finally:
        client.patch("/api/tailscale/config", json={"enabled": True})
        client.delete(f"/api/extensions/{ext_id}")


def test_node_report_and_revoke_deletes_node(client, connected):
    ext_id, num, body = _pair(client)
    try:
        auth = {"device_id": body["device_id"], "device_token": body["device_token"]}
        assert client.post("/api/mobile/device/tailscale",
                           json={**auth, "node_id": "nPHONE45", "ip": "100.80.1.2"}).status_code == 200
        assert client.post("/api/mobile/device/tailscale",
                           json={**auth, "device_token": "wrong", "node_id": "x"}).status_code == 401
        assert client.post("/api/mobile/device/tailscale",
                           json={**auth, "node_id": "../evil"}).status_code == 422
        devs = client.get(f"/api/mobile/devices/{num}").json()
        assert devs[0]["tailscale_ip"] == "100.80.1.2"
        client.post("/api/mobile/device/revoke", json={"extension_number": num, "device_id": body["device_id"]})
        assert "nPHONE45" in connected.deleted_devices
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_key_retrofit_is_rate_limited(client, connected):
    ext_id, num, body = _pair(client)
    try:
        auth = {"device_id": body["device_id"], "device_token": body["device_token"]}
        first = client.post("/api/mobile/device/tailscale-key", json=auth)
        assert first.status_code == 200 and first.json()["tailscale"]["auth_key"]
        assert client.post("/api/mobile/device/tailscale-key", json=auth).status_code == 429
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_device_list_matches_paired_phones(client, connected):
    ext_id, num, body = _pair(client)
    try:
        client.post("/api/mobile/device/tailscale", json={
            "device_id": body["device_id"], "device_token": body["device_token"],
            "node_id": "nPHONE47", "ip": "100.80.1.7"})
        connected.devices.append({"id": "2", "nodeId": "nPHONE47", "name": f"haphone-{num}-pixel-6.tail1234.ts.net.",
                                  "hostname": f"haphone-{num}-pixel-6", "addresses": ["100.80.1.7"],
                                  "tags": ["tag:haphone-phone"], "lastSeen": "2026-09-25T08:00:00Z"})
        devs = client.get("/api/tailscale/devices").json()
        assert [d["id"] for d in devs] == ["nPHONE47"]  # the PBX itself is not listed
        assert devs[0]["extension_number"] == num
        assert client.delete("/api/tailscale/devices/nPHONE47").json() == {"removed": True}
        assert "nPHONE47" in connected.deleted_devices
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_disconnect_can_remove_all_phones(client, connected):
    ext_id, num, body = _pair(client)
    try:
        client.post("/api/mobile/device/tailscale", json={
            "device_id": body["device_id"], "device_token": body["device_token"], "node_id": "nPHONE48"})
        assert client.delete("/api/tailscale/config?remove_devices=true").json()["removed"] == 1
        assert "nPHONE48" in connected.deleted_devices
        assert client.get("/api/tailscale/config").json()["configured"] is False
    finally:
        client.delete(f"/api/extensions/{ext_id}")
