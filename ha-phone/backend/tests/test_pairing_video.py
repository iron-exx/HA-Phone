"""Pairing an app turns door video on (video_capable) only when the app is alone on
the extension; the admin list counts paired apps for the "no door video" warning."""
import pytest

from backend import ami


def _ext(client, number):
    r = client.post("/api/extensions", json={"number": number, "display_name": f"V{number}",
                                             "sip_password": "securepass1234567"})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _pair(client, number, os_id):
    start = client.post("/api/mobile/provision/start",
                        json={"extension_number": number, "platform": "android", "device_name": ""})
    assert start.status_code == 200, start.text
    done = client.post("/api/mobile/provision/complete", json={
        "provisioning_token": start.json()["provisioning_token"], "push_token": "", "os_device_id": os_id})
    assert done.status_code == 200, done.text


def _video(client, ext_id):
    return next(e for e in client.get("/api/extensions").json() if e["id"] == ext_id)


@pytest.fixture
def contacts(monkeypatch):
    """Registered contacts per extension as AMI would report them."""
    state: dict[str, int | None] = {}

    async def fake_count(number):
        return state.get(number, 0)

    async def noop():
        return None

    monkeypatch.setattr(ami, "get_contact_count", fake_count)
    monkeypatch.setattr(ami, "ami_reload_pjsip", noop)
    monkeypatch.setattr(ami, "ami_reload_dialplan", noop)
    return state


def test_first_app_on_an_empty_extension_gets_video(client, contacts):
    ext_id = _ext(client, 33)
    _pair(client, 33, "pv-a")
    ext = _video(client, ext_id)
    assert ext["video_capable"] is True and ext["mobile_devices"] == 1
    client.delete(f"/api/extensions/{ext_id}")


def test_registered_desk_phone_keeps_extension_multi_device(client, contacts):
    contacts["34"] = 1  # e.g. a manually set-up Fanvil
    ext_id = _ext(client, 34)
    _pair(client, 34, "pv-b")
    assert _video(client, ext_id)["video_capable"] is False
    client.delete(f"/api/extensions/{ext_id}")


def test_ami_without_answer_changes_nothing(client, contacts):
    contacts["35"] = None
    ext_id = _ext(client, 35)
    _pair(client, 35, "pv-c")
    assert _video(client, ext_id)["video_capable"] is False
    client.delete(f"/api/extensions/{ext_id}")


def test_second_app_on_the_extension_is_not_switched(client, contacts):
    contacts["36"] = 1
    ext_id = _ext(client, 36)
    _pair(client, 36, "pv-d")
    contacts["36"] = 0  # first phone briefly unregistered
    _pair(client, 36, "pv-e")
    ext = _video(client, ext_id)
    assert ext["video_capable"] is False and ext["mobile_devices"] == 2
    client.delete(f"/api/extensions/{ext_id}")


def test_provisioned_desk_phone_keeps_extension_multi_device(client, contacts):
    ext_id = _ext(client, 37)
    tpl = client.post("/api/provisioning/templates", json={"name": "PV", "vendor": "x",
                                                           "file_pattern": "{mac}.cfg", "content": "x"}).json()
    dev = client.post("/api/provisioning/devices", json={"mac": "aa:bb:cc:00:04:85", "extension_numbers": "37",
                                                         "template_id": tpl["id"]}).json()
    _pair(client, 37, "pv-f")
    assert _video(client, ext_id)["video_capable"] is False
    client.delete(f"/api/provisioning/devices/{dev['id']}")
    client.delete(f"/api/provisioning/templates/{tpl['id']}")
    client.delete(f"/api/extensions/{ext_id}")
