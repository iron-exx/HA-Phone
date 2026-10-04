"""Pairing an app always makes its extension video capable (door video before and
after answering); the admin list counts paired apps for the "no door video" warning."""
def _ext(client, number, **extra):
    r = client.post("/api/extensions", json={"number": number, "display_name": f"V{number}",
                                             "sip_password": "securepass1234567", **extra})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _pair(client, number, os_id):
    start = client.post("/api/mobile/provision/start",
                        json={"extension_number": number, "platform": "android", "device_name": ""})
    assert start.status_code == 200, start.text
    done = client.post("/api/mobile/provision/complete", json={
        "provisioning_token": start.json()["provisioning_token"], "push_token": "", "os_device_id": os_id})
    assert done.status_code == 200, done.text


def _get(client, ext_id):
    return next(e for e in client.get("/api/extensions").json() if e["id"] == ext_id)


def test_pairing_makes_the_extension_video_capable(client):
    ext_id = _ext(client, 33)
    assert _get(client, ext_id)["video_capable"] is False
    _pair(client, 33, "pv-a")
    ext = _get(client, ext_id)
    assert ext["video_capable"] is True and ext["mobile_devices"] == 1
    client.delete(f"/api/extensions/{ext_id}")


def test_also_next_to_a_desk_phone(client):
    ext_id = _ext(client, 34)
    _pair(client, 34, "pv-b")
    _pair(client, 34, "pv-c")
    ext = _get(client, ext_id)
    assert ext["video_capable"] is True and ext["mobile_devices"] == 2
    client.delete(f"/api/extensions/{ext_id}")


def test_video_extension_keeps_several_devices(client):
    import os
    from pathlib import Path
    ext_id = _ext(client, 35, video_capable=True)
    conf = (Path(os.environ["BPX_DATA_DIR"]) / "asterisk" / "pjsip_extensions.conf").read_text()
    block = conf[conf.index("\n[35]\ntype              = aor"):]
    block = block[:block.index("\n\n")]
    assert "max_contacts      = 3" in block
    client.delete(f"/api/extensions/{ext_id}")


def test_door_station_is_not_switched(client):
    ext_id = _ext(client, 36, is_door=True, internal_only=True)
    r = client.post("/api/mobile/provision/start", json={"extension_number": 36, "platform": "android", "device_name": ""})
    if r.status_code == 200:
        client.post("/api/mobile/provision/complete", json={
            "provisioning_token": r.json()["provisioning_token"], "push_token": "", "os_device_id": "pv-d"})
    assert _get(client, ext_id)["video_capable"] is False
    client.delete(f"/api/extensions/{ext_id}")
