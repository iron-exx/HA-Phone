"""Doorbell history: AMI state machine, snapshot fetching, storage, API."""
from datetime import datetime, timedelta

import httpx
import pytest
from sqlmodel import Session, select

from backend import doorbell
from backend.database import get_engine
from backend.doorbell_listener import DoorbellListener
from backend.models import DoorbellEvent

JPEG = b"\xff\xd8\xff\xe0" + b"x" * 100


def ring(uid="1.1", door="17", exten="30"):
    return {"Event": "Newchannel", "Channel": f"PJSIP/{door}-0001", "Uniqueid": uid,
            "CallerIDNum": door, "Exten": exten}


# ── tracker ──

def test_ring_group_gives_one_event_and_first_answer_wins():
    t = doorbell.DoorbellTracker(lambda n: n == "17")
    assert t.on_event(ring()) == [doorbell.Ring("1.1", "17")]
    assert t.on_event(ring()) == []  # same channel again
    assert t.on_event({"Event": "DialEnd", "Uniqueid": "1.1", "DialStatus": "ANSWER", "DestCallerIDNum": "11"}) \
        == [doorbell.Answered("1.1", "11")]
    assert t.on_event({"Event": "DialEnd", "Uniqueid": "1.1", "DialStatus": "ANSWER", "DestCallerIDNum": "18"}) == []
    assert t.on_event({"Event": "Hangup", "Uniqueid": "1.1"}) == [doorbell.Ended("1.1")]
    assert t.on_event({"Event": "Hangup", "Uniqueid": "1.1"}) == []


def test_calls_to_the_door_and_other_extensions_are_no_rings():
    t = doorbell.DoorbellTracker(lambda n: n == "17")
    # The app calls the door: the door's channel is created for the called leg.
    assert t.on_event({"Event": "Newchannel", "Channel": "PJSIP/17-0002", "Uniqueid": "2.2",
                       "CallerIDNum": "17", "Exten": "17"}) == []
    assert t.on_event(ring(uid="3.3", door="11")) == []  # not a door
    assert t.on_event({"Event": "DialEnd", "Uniqueid": "9.9", "DialStatus": "ANSWER"}) == []


def test_unanswered_dialend_does_not_count():
    t = doorbell.DoorbellTracker(lambda n: True)
    t.on_event(ring())
    assert t.on_event({"Event": "DialEnd", "Uniqueid": "1.1", "DialStatus": "NOANSWER"}) == []


# ── snapshot ──

async def _fetch(handler, source):
    return await doorbell.fetch_snapshot(source, transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_snapshot_from_url_with_basic_auth():
    def handler(req):
        assert req.url.host == "door.local" and "@" not in str(req.url)
        assert req.headers["authorization"].startswith("Basic ")
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
    assert await _fetch(handler, "http://admin:pw@door.local/jpeg") == (JPEG, "image/jpeg")


@pytest.mark.asyncio
async def test_snapshot_retries_with_digest():
    calls = []

    def handler(req):
        calls.append(req.headers.get("authorization", ""))
        if not calls[-1].startswith("Digest"):
            return httpx.Response(401, headers={"www-authenticate": 'Digest realm="x", nonce="abc", qop="auth"'})
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
    assert (await _fetch(handler, "http://admin:pw@door.local/jpeg"))[0] == JPEG
    assert calls[-1].startswith("Digest")


@pytest.mark.asyncio
async def test_snapshot_rejects_errors_non_images_and_huge_files():
    assert await _fetch(lambda r: httpx.Response(500), "http://door.local/x") is None
    assert await _fetch(lambda r: httpx.Response(200, text="<html>", headers={"content-type": "text/html"}),
                        "http://door.local/x") is None
    big = b"\xff" * (doorbell.MAX_IMAGE_BYTES + 1)
    assert await _fetch(lambda r: httpx.Response(200, content=big, headers={"content-type": "image/jpeg"}),
                        "http://door.local/x") is None

    def timeout(req):
        raise httpx.ConnectTimeout("slow")
    assert await _fetch(timeout, "http://door.local/x") is None


@pytest.mark.asyncio
async def test_ha_camera_uses_supervisor_api(monkeypatch):
    monkeypatch.setenv("SUPERVISOR_TOKEN", "tok")

    def handler(req):
        assert req.url.path == "/core/api/camera_proxy/camera.haustuer"
        assert req.headers["authorization"] == "Bearer tok"
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})
    assert (await _fetch(handler, "camera.haustuer"))[0] == JPEG


# ── store + listener + API ──

@pytest.fixture
def door(client):
    resp = None
    for number in range(99, 9, -1):
        resp = client.post("/api/extensions", json={
            "number": number, "display_name": "Haustür", "sip_password": "securepass1234567",
            "doorbell_camera": "http://door.local/snap.jpg"})
        if resp.status_code in (200, 201):
            break
    yield resp.json()
    client.delete(f"/api/extensions/{resp.json()['id']}")


def test_camera_source_is_validated(client, door):
    for bad in ("camera.Haus Tür", "ftp://x", "http://a\nb", "camera."):
        assert client.patch(f"/api/extensions/{door['id']}", json={"doorbell_camera": bad}).status_code == 422, bad
    assert client.patch(f"/api/extensions/{door['id']}", json={"doorbell_camera": "camera.haustuer"}).status_code == 200


def test_listener_records_ring_answer_and_end(client, door):
    num = str(door["number"])
    lst = DoorbellListener()
    lst.handle(ring(uid="7.7", door=num))
    lst.handle({"Event": "DialEnd", "Uniqueid": "7.7", "DialStatus": "ANSWER", "DestCallerIDNum": "11"})
    lst.handle({"Event": "Hangup", "Uniqueid": "7.7"})
    with Session(get_engine()) as s:
        ev = s.exec(select(DoorbellEvent).order_by(DoorbellEvent.id.desc())).first()
        assert ev.door_number == door["number"] and ev.door_name == "Haustür"
        assert ev.answered_by == "11" and ev.ended_at is not None


def test_mobile_api_lists_events_and_serves_images(client, door):
    with Session(get_engine()) as s:
        store = doorbell.DoorbellStore(s)
        ev = store.record_ring(door["number"])
        store.save_image(ev.id, JPEG, "image/jpeg")
        event_id = ev.id
    phone = None
    for number in range(10, 99):
        phone = client.post("/api/extensions", json={"number": number, "display_name": "Handy",
                                                     "sip_password": "securepass1234567"})
        if phone.status_code in (200, 201):
            break
    phone_num = phone.json()["number"]
    start = client.post("/api/mobile/provision/start",
                        json={"extension_number": phone_num, "platform": "android", "device_name": ""})
    done = client.post("/api/mobile/provision/complete", json={
        "provisioning_token": start.json()["provisioning_token"], "push_token": "", "os_device_id": "doorbell-test"}).json()
    h = {"X-Device-Id": str(done["device_id"]), "X-Device-Token": done["device_token"]}
    assert client.get("/api/mobile/doorbell").status_code == 401
    events = client.get("/api/mobile/doorbell?limit=5", headers=h).json()
    mine = next(e for e in events if e["id"] == event_id)
    assert mine["has_image"] is True and mine["door_name"] == "Haustür"
    img = client.get(f"/api/mobile/doorbell/{event_id}/image", headers=h)
    assert img.status_code == 200 and img.content == JPEG
    assert client.get("/api/mobile/doorbell/999999/image", headers=h).status_code == 404
    directory = client.get("/api/mobile/directory", headers=h).json()
    assert any(x.get("has_camera") for x in directory["extensions"] if x["number"] == str(door["number"]))
    client.delete(f"/api/extensions/{phone.json()['id']}")


def test_opened_marks_only_a_recent_ring(client, door):
    with Session(get_engine()) as s:
        store = doorbell.DoorbellStore(s)
        ev = store.record_ring(door["number"])
        assert store.mark_opened(door["number"], now=ev.started_at + timedelta(minutes=1)) is True
        assert s.get(DoorbellEvent, ev.id).door_opened is True
        assert store.mark_opened(door["number"], now=ev.started_at + timedelta(minutes=10)) is False


def test_prune_keeps_30_days(client, door):
    with Session(get_engine()) as s:
        store = doorbell.DoorbellStore(s)
        old = store.record_ring(door["number"])
        old.started_at = datetime.utcnow() - timedelta(days=31)
        s.add(old)
        s.commit()
        store.save_image(old.id, JPEG, "image/jpeg")
        path = store.image_path(s.get(DoorbellEvent, old.id))
        assert store.prune() >= 1
        assert s.get(DoorbellEvent, old.id) is None and not path.exists()


def test_admin_snapshot_test(client, monkeypatch):
    from backend.routers import doorbell as router
    monkeypatch.setattr(router, "_transport", httpx.MockTransport(
        lambda r: httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})))
    resp = client.post("/api/doorbell/test-snapshot", json={"source": "http://door.local/snap.jpg"})
    assert resp.status_code == 200 and resp.content == JPEG
    assert client.post("/api/doorbell/test-snapshot", json={"source": "gopher://x"}).status_code == 422
