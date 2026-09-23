"""Phone-facing presence, live line state and visual voicemail (/api/mobile/*)."""
from backend.tests.test_mobile_device_auth import paired  # noqa: F401 (fixture)


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


def _inbox(tmp_data_dir, ext, folder="INBOX"):
    d = tmp_data_dir / "voicemail" / "voicemail" / "default" / str(ext) / folder
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
    mock_ami["ext_statuses"].return_value = [
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


# ---- forwarding rules ----

def test_forwarding_roundtrip_replaces_own_rules(client, paired, mock_ami):
    h = _auth(paired)
    assert client.get("/api/mobile/forwarding", headers=h).json() == {"rules": []}
    rules = [
        {"status": "lunch", "direction": "external", "mode": "always_dest", "dest_type": "voicemail", "dest_target": 87, "ring_timeout": 20},
        {"status": "away", "direction": "internal", "mode": "ring_then_dest", "dest_type": "voicemail", "dest_target": 87, "ring_timeout": 15},
    ]
    resp = client.put("/api/mobile/forwarding", json={"rules": rules}, headers=h)
    assert resp.status_code == 200, resp.text
    mock_ami["reload_dialplan"].assert_awaited()
    got = client.get("/api/mobile/forwarding", headers=h).json()["rules"]
    assert sorted(r["status"] for r in got) == ["away", "lunch"]
    # Replacing with one rule drops the other.
    client.put("/api/mobile/forwarding", json={"rules": rules[:1]}, headers=h)
    assert [r["status"] for r in client.get("/api/mobile/forwarding", headers=h).json()["rules"]] == ["lunch"]
    client.put("/api/mobile/forwarding", json={"rules": []}, headers=h)


def test_forwarding_rejects_bad_rules(client, paired):
    h = _auth(paired)
    bad = [
        {"status": "partying", "direction": "external", "mode": "always_dest", "dest_type": "voicemail", "dest_target": 87},
        {"status": "lunch", "direction": "sideways", "mode": "always_dest", "dest_type": "voicemail", "dest_target": 87},
        {"status": "lunch", "direction": "external", "mode": "always_dest", "dest_type": "extension", "dest_target": 5},
        {"status": "lunch", "direction": "external", "mode": "always_dest", "dest_type": "ivr", "dest_target": 1},
    ]
    for rule in bad:
        assert client.put("/api/mobile/forwarding", json={"rules": [rule]}, headers=h).status_code == 422, rule
    dup = [bad[0] | {"status": "lunch"}, bad[0] | {"status": "lunch"}]
    assert client.put("/api/mobile/forwarding", json={"rules": dup}, headers=h).status_code == 422


# ---- call history from CDR ----

_CDR = (
    '"","13","87","from-internal","""Test"" <13>","PJSIP/13-00000001","PJSIP/87-00000002","Dial","PJSIP/87,30",'
    '"2026-09-23 14:02:00","2026-09-23 14:02:05","2026-09-23 14:05:17",197,192,"ANSWERED","DOCUMENTATION","1790000001.1",""\n'
    '"","87","0301234567","from-internal","""Auth Test"" <87>","PJSIP/87-00000003","PJSIP/trunk-endpoint-00000004","Dial","PJSIP/0301234567@trunk-endpoint",'
    '"2026-09-23 15:00:00","","2026-09-23 15:00:20",20,0,"NO ANSWER","DOCUMENTATION","1790000002.2",""\n'
    '"","16","11","from-internal","""tuer"" <16>","PJSIP/16-00000005","PJSIP/11-00000006","Dial","PJSIP/11,30",'
    '"2026-09-23 16:00:00","2026-09-23 16:00:02","2026-09-23 16:00:30",30,28,"ANSWERED","DOCUMENTATION","1790000003.3",""\n'
    '"","16","87","from-internal","""tuer"" <16>","PJSIP/16-00000007","PJSIP/87-00000008","Dial","PJSIP/87,30",'
    '"2026-09-23 17:00:00","","2026-09-23 17:00:30",30,0,"NO ANSWER","DOCUMENTATION","1790000004.4",""\n'
)


def test_call_history_lists_only_own_calls_newest_first(client, paired, tmp_data_dir):
    cdr_dir = tmp_data_dir / "logs" / "asterisk" / "cdr-csv"
    cdr_dir.mkdir(parents=True, exist_ok=True)
    (cdr_dir / "Master.csv").write_text(_CDR)
    calls = client.get("/api/mobile/calls", headers=_auth(paired)).json()["calls"]
    assert [c["id"] for c in calls] == ["1790000004.4", "1790000002.2", "1790000001.1"]
    missed, outgoing, incoming = calls
    assert missed == {
        "id": "1790000004.4", "number": "16", "name": "tuer", "direction": "incoming",
        "answered": False, "started_at": missed["started_at"], "duration_sec": 0,
    }
    assert outgoing["direction"] == "outgoing" and outgoing["number"] == "0301234567" and not outgoing["answered"]
    assert incoming["answered"] and incoming["duration_sec"] == 192 and incoming["name"] == "Test"


def test_call_history_without_cdr_file_is_empty(client, paired, tmp_data_dir):
    master = tmp_data_dir / "logs" / "asterisk" / "cdr-csv" / "Master.csv"
    if master.exists():
        master.unlink()
    assert client.get("/api/mobile/calls", headers=_auth(paired)).json() == {"calls": []}
