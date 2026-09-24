"""Call recording from the app (per-extension opt-in) and call flip (*55)."""
import wave
from unittest.mock import AsyncMock, patch

import pytest

from backend import ami
from backend.routers.mobile_features import recordings_dir
from backend.tests.test_mobile_device_auth import paired  # noqa: F401 (fixture)


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


def _own_id(client):
    return next(e["id"] for e in client.get("/api/extensions").json() if e["number"] == 87)


@pytest.fixture
def allowed(client, paired):
    ext_id = _own_id(client)
    resp = client.patch(f"/api/extensions/{ext_id}", json={"recording_allowed": True})
    assert resp.status_code == 200, resp.text
    yield paired
    client.patch(f"/api/extensions/{ext_id}", json={"recording_allowed": False})


def test_recording_is_off_by_default_and_shown_to_the_app(client, paired):
    assert next(e for e in client.get("/api/extensions").json() if e["number"] == 87)["recording_allowed"] is False
    me = client.get("/api/mobile/directory", headers=_auth(paired)).json()["self"]
    assert me["recording_allowed"] is False


def test_recording_refused_when_not_allowed(client, paired):
    with patch("backend.ami.start_recording", new_callable=AsyncMock) as start:
        resp = client.post("/api/mobile/recording", json={"action": "start"}, headers=_auth(paired))
    assert resp.status_code == 403
    start.assert_not_awaited()


def test_start_recording_runs_mixmonitor_into_own_folder(client, allowed):
    assert client.get("/api/mobile/directory", headers=_auth(allowed)).json()["self"]["recording_allowed"] is True
    with patch("backend.ami.start_recording", new_callable=AsyncMock, return_value="PJSIP/87-0001") as start:
        resp = client.post("/api/mobile/recording", json={"action": "start", "peer": "0171 12;3"}, headers=_auth(allowed))
    assert resp.status_code == 200, resp.text
    number, peer, path = start.await_args.args
    assert (number, peer) == ("87", "0171 12;3")
    assert path.startswith(str(recordings_dir(87)))
    assert path.endswith(f"{resp.json()['id']}.wav") and resp.json()["id"].endswith("_017112" + "3")


def test_start_recording_without_unique_call_is_conflict(client, allowed):
    with patch("backend.ami.start_recording", new_callable=AsyncMock, return_value=None):
        assert client.post("/api/mobile/recording", json={"action": "start"}, headers=_auth(allowed)).status_code == 409
    with patch("backend.ami.stop_recording", new_callable=AsyncMock, return_value=False):
        assert client.post("/api/mobile/recording", json={"action": "stop"}, headers=_auth(allowed)).status_code == 409
    with patch("backend.ami.start_recording", new_callable=AsyncMock, side_effect=TimeoutError()):
        assert client.post("/api/mobile/recording", json={"action": "start"}, headers=_auth(allowed)).status_code == 502


def test_list_play_and_delete_recordings(client, allowed):
    folder = recordings_dir(87)
    folder.mkdir(parents=True, exist_ok=True)
    with wave.open(str(folder / "20260924-101500_0171123.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b"\0\0" * 8000 * 3)
    (folder / "notes.wav").write_bytes(b"")
    h = _auth(allowed)

    body = client.get("/api/mobile/recordings", headers=h).json()
    assert body["allowed"] is True
    assert [(r["id"], r["peer"], r["duration_sec"]) for r in body["recordings"]] == [("20260924-101500_0171123", "0171123", 3)]
    audio = client.get("/api/mobile/recordings/20260924-101500_0171123/audio", headers=h)
    assert audio.status_code == 200 and audio.headers["content-type"] == "audio/wav"
    assert client.get("/api/mobile/recordings/x.wav/audio", headers=h).status_code == 400
    assert client.get("/api/mobile/recordings/20260924-101501_1/audio", headers=h).status_code == 404
    assert client.get("/api/mobile/recordings", headers={}).status_code == 401

    assert client.delete("/api/mobile/recordings/20260924-101500_0171123", headers=h).status_code == 200
    assert client.get("/api/mobile/recordings", headers=h).json()["recordings"] == []


@pytest.mark.parametrize("channels,peer,expected", [
    ([{"channel": "PJSIP/87-1", "connected_line_num": "11"}], "", "PJSIP/87-1"),
    ([{"channel": "PJSIP/87-1", "connected_line_num": "11"}], "99", "PJSIP/87-1"),
    ([{"channel": "PJSIP/87-1", "connected_line_num": "11"}, {"channel": "PJSIP/87-2", "connected_line_num": "12"}], "12", "PJSIP/87-2"),
    ([{"channel": "PJSIP/87-1", "connected_line_num": "11"}, {"channel": "PJSIP/87-2", "connected_line_num": "12"}], "", None),
    ([], "", None),
])
def test_pick_call_channel(channels, peer, expected):
    assert ami.pick_call_channel(channels, peer) == expected


def test_call_flip_code_in_dialplan(client, allowed, tmp_data_dir):
    routing = (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()
    assert "exten => *55,1," in routing
    assert "${CHANNELS(^PJSIP/${CHANNEL(endpoint)}-)}" in routing
    assert "Bridge(${FLIP_PEER},x)" in routing
    flip = routing.split("exten => *55,1,")[1].split("exten => *43")[0]
    # only answered channels, never a multi-party bridge (comma list), no bare Congestion
    assert '$["${IMPORT(${FLIP_CHAN},CHANNEL(state))}" != "Up"]?next' in flip
    assert '$["${FLIP_PEER}" =~ ","]?next' in flip
    assert "Congestion" not in flip and "Playback(beeperr)" in flip
    assert "While(" not in routing  # app_while is not built
