"""Phone-facing presence, live line state and visual voicemail (/api/mobile/*)."""
from backend.tests.test_mobile_device_auth import paired  # noqa: F401 (fixture)


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


def _inbox(tmp_data_dir, ext, folder="INBOX"):
    d = tmp_data_dir / "asterisk" / "spool" / "voicemail" / "default" / str(ext) / folder
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_message(folder, name, callerid='"Pizzeria" <0301234567>', duration="42", origtime="1790000000"):
    (folder / f"{name}.wav").write_bytes(b"RIFF....WAVEfmt ")
    (folder / f"{name}.txt").write_text(
        ";\n; Message Information file\n;\n[message]\n"
        f"origmailbox=87\ncontext=from-internal\ncallerid={callerid}\n"
        f"origtime={origtime}\nduration={duration}\n"
    )


# ---- presence ----

def test_presence_requires_device_token(client, paired):
    assert client.get("/api/mobile/presence").status_code == 401
    assert client.put("/api/mobile/presence", json={"status": "away"}).status_code == 401


def test_presence_lists_status_and_live_line_state(client, paired, mock_ami):
    # The test DB is shared across the session (ring groups/IVRs hold numbers too),
    # so take the first three numbers the API accepts.
    ids, free = [], []
    for n in range(40, 80):
        resp = client.post("/api/extensions", json={"number": n, "display_name": f"E{n}", "sip_password": "securepass1234567"})
        if resp.status_code == 200:
            ids.append(resp.json()["id"])
            free.append(n)
        if len(free) == 3:
            break
    busy, ringing, offline = (str(n) for n in free)
    mock_ami["ext_diagnostics"].return_value = [
        {"number": "87", "device_state": "Not in use", "contacts": 1},
        {"number": busy, "device_state": "In use", "contacts": 1},
        {"number": ringing, "device_state": "Ringing", "contacts": 1},
    ]
    try:
        body = client.get("/api/mobile/presence", headers=_auth(paired)).json()
        assert body["self"] == {"number": "87", "presence": "available", "line": "idle"}
        lines = {e["number"]: e["line"] for e in body["extensions"]}
        # the third one has no registration at all -> offline.
        assert (lines[busy], lines[ringing], lines[offline]) == ("busy", "ringing", "offline")
    finally:
        for i in ids:
            client.delete(f"/api/extensions/{i}")


def test_line_state_mapping():
    from backend.routers.mobile_features import line_state
    assert line_state("Not in use") == "idle"
    assert line_state("Ringing") == "ringing"
    assert line_state("RINGINUSE") == "busy"
    assert line_state("On Hold") == "busy"
    assert line_state("Unavailable") == "offline"
    assert line_state(None) == "offline"


def test_set_own_presence_regenerates_dialplan(client, paired, mock_ami):
    resp = client.put("/api/mobile/presence", json={"status": "lunch"}, headers=_auth(paired))
    assert resp.status_code == 200, resp.text
    assert resp.json()["presence"] == "lunch"
    mock_ami["reload_dialplan"].assert_awaited()
    exts = client.get("/api/extensions").json()
    assert next(e for e in exts if e["number"] == 87)["presence_status"] == "lunch"


def test_set_presence_rejects_unknown_status(client, paired):
    resp = client.put("/api/mobile/presence", json={"status": "partying"}, headers=_auth(paired))
    assert resp.status_code == 422


# ---- voicemail ----

def test_voicemail_lists_own_mailbox_with_envelope_data(client, paired, tmp_data_dir):
    _write_message(_inbox(tmp_data_dir, 87), "msg0000")
    _write_message(_inbox(tmp_data_dir, 87, "Old"), "msg0000", callerid="<13>", duration="5", origtime="1789000000")
    body = client.get("/api/mobile/voicemail", headers=_auth(paired)).json()
    assert [m["id"] for m in body["messages"]] == ["INBOX/msg0000", "Old/msg0000"]
    new = body["messages"][0]
    assert new == {
        "id": "INBOX/msg0000", "new": True, "caller_number": "0301234567",
        "caller_name": "Pizzeria", "duration_sec": 42, "received_at": 1790000000,
    }
    assert body["messages"][1]["caller_name"] == ""
    assert body["new_count"] == 1


def test_voicemail_audio_and_delete(client, paired, tmp_data_dir):
    inbox = _inbox(tmp_data_dir, 87)
    _write_message(inbox, "msg0001")
    audio = client.get("/api/mobile/voicemail/INBOX/msg0001/audio", headers=_auth(paired))
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/wav"
    assert client.delete("/api/mobile/voicemail/INBOX/msg0001", headers=_auth(paired)).status_code == 200
    assert not (inbox / "msg0001.wav").exists()
    assert not (inbox / "msg0001.txt").exists()


def test_voicemail_rejects_other_folders_and_bad_names(client, paired):
    h = _auth(paired)
    assert client.get("/api/mobile/voicemail/Work/msg0000/audio", headers=h).status_code == 404
    traversal = client.get("/api/mobile/voicemail/INBOX/..%2Fx/audio", headers=h)
    assert traversal.headers.get("content-type") != "audio/wav"
    assert client.get("/api/mobile/voicemail/INBOX/msg9/audio", headers=h).status_code == 400


def test_voicemail_requires_device_token(client, paired):
    assert client.get("/api/mobile/voicemail").status_code == 401
