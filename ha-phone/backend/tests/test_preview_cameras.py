"""Extra preview cameras: the admin shares HA cameras, paired phones may show them."""
import httpx
import pytest

from backend import preview_cameras
from backend.tests.test_mobile_device_auth import paired  # noqa: F401 (fixture)

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100

STATES = [
    {"entity_id": "camera.garten", "attributes": {"friendly_name": "Garten"}},
    {"entity_id": "camera.einfahrt", "attributes": {}},
    {"entity_id": "person.anna", "attributes": {"friendly_name": "Anna"}},
    {"entity_id": "light.flur", "attributes": {"friendly_name": "Flur"}},
]


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


@pytest.fixture
def ha(monkeypatch):
    """Fake Home Assistant Core: /states and /camera_proxy/<entity>."""
    monkeypatch.setenv("SUPERVISOR_TOKEN", "tok")
    fetched = []

    def handler(req):
        assert req.headers["authorization"] == "Bearer tok"
        if req.url.path.endswith("/states"):
            return httpx.Response(200, json=STATES)
        fetched.append(req.url.path.rsplit("/", 1)[-1])
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
    monkeypatch.setattr(preview_cameras, "_transport", httpx.MockTransport(handler))
    return fetched


@pytest.fixture(autouse=True)
def _no_cache():
    preview_cameras._cache.clear()
    yield
    preview_cameras._cache.clear()


@pytest.fixture
def shared(client):
    yield
    client.put("/api/doorbell/preview-cameras", json={"cameras": []})


# ── HA camera list ──

@pytest.mark.asyncio
async def test_ha_cameras_lists_only_camera_entities_sorted_by_name(ha):
    assert await preview_cameras.list_ha_cameras() == [
        {"entity_id": "camera.einfahrt", "name": "camera.einfahrt"},
        {"entity_id": "camera.garten", "name": "Garten"},
    ]


@pytest.mark.asyncio
async def test_ha_cameras_is_none_outside_home_assistant(monkeypatch):
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    assert await preview_cameras.list_ha_cameras() is None


def test_admin_ha_camera_list_503_without_home_assistant(client, monkeypatch):
    monkeypatch.delenv("SUPERVISOR_TOKEN", raising=False)
    assert client.get("/api/doorbell/ha-cameras").status_code == 503


def test_admin_ha_camera_list(client, ha):
    assert [c["entity_id"] for c in client.get("/api/doorbell/ha-cameras").json()] == [
        "camera.einfahrt", "camera.garten"]


# ── admin share list ──

def test_share_list_is_empty_by_default_and_keeps_order(client, shared):
    assert client.get("/api/doorbell/preview-cameras").json() == []
    body = {"cameras": [{"entity_id": "camera.garten", "name": "Garten"},
                        {"entity_id": "camera.einfahrt", "name": "Einfahrt"}]}
    assert client.put("/api/doorbell/preview-cameras", json=body).status_code == 200
    assert client.get("/api/doorbell/preview-cameras").json() == body["cameras"]
    # Replacing drops what is no longer listed.
    client.put("/api/doorbell/preview-cameras", json={"cameras": [{"entity_id": "camera.einfahrt", "name": ""}]})
    assert client.get("/api/doorbell/preview-cameras").json() == [
        {"entity_id": "camera.einfahrt", "name": "camera.einfahrt"}]


@pytest.mark.parametrize("bad", ["light.flur", "camera.", "camera.Garten", "http://x/cam.jpg", "camera.a/../b"])
def test_share_list_accepts_only_camera_entities(client, shared, bad):
    resp = client.put("/api/doorbell/preview-cameras", json={"cameras": [{"entity_id": bad, "name": "x"}]})
    assert resp.status_code == 422


def test_share_list_rejects_duplicates_and_too_many(client, shared):
    dup = [{"entity_id": "camera.a", "name": "A"}] * 2
    assert client.put("/api/doorbell/preview-cameras", json={"cameras": dup}).status_code == 422
    many = [{"entity_id": f"camera.c{i}", "name": ""} for i in range(preview_cameras.MAX_SHARED + 1)]
    assert client.put("/api/doorbell/preview-cameras", json={"cameras": many}).status_code == 422


# ── phone ──

def test_phone_needs_device_token(client, paired):
    assert client.get("/api/mobile/cameras").status_code == 401
    assert client.get("/api/mobile/cameras/camera.garten/snapshot").status_code == 401


def test_phone_sees_only_shared_cameras(client, paired, shared, ha):
    h = _auth(paired)
    assert client.get("/api/mobile/cameras", headers=h).json() == []
    client.put("/api/doorbell/preview-cameras", json={"cameras": [{"entity_id": "camera.garten", "name": "Garten"}]})
    assert client.get("/api/mobile/cameras", headers=h).json() == [{"entity_id": "camera.garten", "name": "Garten"}]

    img = client.get("/api/mobile/cameras/camera.garten/snapshot", headers=h)
    assert img.status_code == 200 and img.content == JPEG
    assert img.headers["content-type"] == "image/jpeg"
    assert "no-store" in img.headers["cache-control"]
    # Not shared (e.g. a baby monitor): never fetched from HA.
    assert client.get("/api/mobile/cameras/camera.einfahrt/snapshot", headers=h).status_code == 404
    assert ha == ["camera.garten"]


def test_phone_snapshot_502_when_camera_gives_no_picture(client, paired, shared, monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "tok")
    monkeypatch.setattr(preview_cameras, "_transport", httpx.MockTransport(lambda r: httpx.Response(500)))
    client.put("/api/doorbell/preview-cameras", json={"cameras": [{"entity_id": "camera.garten", "name": "Garten"}]})
    assert client.get("/api/mobile/cameras/camera.garten/snapshot", headers=_auth(paired)).status_code == 502


@pytest.mark.asyncio
async def test_snapshot_is_shared_for_a_moment_and_failures_are_not_cached(ha, monkeypatch):
    assert (await preview_cameras.snapshot("camera.garten"))[0] == JPEG
    assert (await preview_cameras.snapshot("camera.garten"))[0] == JPEG
    assert ha == ["camera.garten"]  # second call from the cache
    monkeypatch.setattr(preview_cameras, "CACHE_S", 0.0)
    await preview_cameras.snapshot("camera.garten")
    assert ha == ["camera.garten", "camera.garten"]

    monkeypatch.setattr(preview_cameras, "_transport", httpx.MockTransport(lambda r: httpx.Response(500)))
    assert await preview_cameras.snapshot("camera.garten") is None
    assert "camera.garten" not in preview_cameras._cache


# ── warm-up while a door rings ──

@pytest.fixture
def warm(monkeypatch):
    monkeypatch.setattr(preview_cameras, "WARM_PAUSE_S", 0.01)
    monkeypatch.setattr(preview_cameras, "CACHE_S", 0.0)  # every round really fetches
    yield
    preview_cameras._rings.clear()


@pytest.mark.asyncio
async def test_ring_keeps_shared_cameras_fresh_and_phones_get_them_at_once(ha, warm):
    import asyncio
    preview_cameras.ring_started("1.1", ["camera.garten"])
    for _ in range(50):
        if "camera.garten" in preview_cameras._cache:
            break
        await asyncio.sleep(0.01)
    assert preview_cameras._cache["camera.garten"][1][0] == JPEG
    fetched = len(ha)
    # While ringing, a phone gets the warmed picture without an extra HA fetch of its own.
    preview_cameras._cache["camera.garten"] = (0.0 + preview_cameras.time.monotonic(), (b"old", "image/jpeg"))
    assert (await preview_cameras.snapshot("camera.garten"))[0] == b"old"
    await asyncio.sleep(0.05)
    assert len(ha) > fetched  # the loop keeps fetching
    preview_cameras.ring_ended("1.1")
    await asyncio.sleep(0.05)
    stopped_at = len(ha)
    await asyncio.sleep(0.05)
    assert len(ha) == stopped_at


def test_ring_without_shared_cameras_or_event_loop_is_harmless(warm):
    preview_cameras.ring_started("2.2", [])
    preview_cameras.ring_started("3.3", ["camera.garten"])  # no running loop here
    preview_cameras.ring_ended("3.3")
    preview_cameras.ring_ended("never-started")
    assert not preview_cameras._rings
