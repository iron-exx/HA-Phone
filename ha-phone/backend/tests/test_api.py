import re
import pytest
from pathlib import Path


def _ensure_extension(client, number: int, name: str | None = None):
    existing = client.get("/api/extensions")
    if existing.status_code == 200:
        for ext in existing.json():
            if ext["number"] == number:
                return ext
    resp = client.post(
        "/api/extensions",
        json={
            "number": number,
            "display_name": name or f"Ext {number}",
            "sip_password": "securepass1234567",
        },
    )
    assert resp.status_code == 200
    return resp.json()


def test_extension_crud(client, tmp_data_dir):
    """POST /api/extensions creates extension and GET returns it in list."""
    # Create extension
    resp = client.post(
        "/api/extensions",
        json={"number": 20, "display_name": "Test User", "sip_password": "securepass1234567"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["number"] == 20

    # List extensions — should contain newly created one
    resp_list = client.get("/api/extensions")
    assert resp_list.status_code == 200
    numbers = [e["number"] for e in resp_list.json()]
    assert 20 in numbers

    # pjsip_extensions.conf must have been written
    conf_path = tmp_data_dir / "asterisk" / "pjsip_extensions.conf"
    assert conf_path.exists()
    content = conf_path.read_text()
    assert "[20]" in content


def test_trunk_save(client, tmp_data_dir):
    """POST /api/trunk saves to DB and writes pjsip_trunk.conf."""
    resp = client.post(
        "/api/trunk",
        json={
            "registrar_host": "sip.example.com",
            "port": 5060,
            "auth_username": "123456789",
            "password": "mysecretpassword",
            "phone_number": "049123456789",
            "reg_refresh": 60,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    # Password must NOT be in response (T-03-03)
    assert "password" not in data or data.get("password") is None

    # pjsip_trunk.conf must have been written
    conf_path = tmp_data_dir / "asterisk" / "pjsip_trunk.conf"
    assert conf_path.exists()
    content = conf_path.read_text()
    assert "type = registration" in content


def test_public_ip(client, tmp_data_dir):
    """POST /api/settings/public-ip writes pjsip_local.conf."""
    resp = client.post(
        "/api/settings/public-ip",
        json={"ip": "1.2.3.4"},
    )
    assert resp.status_code == 200

    conf_path = tmp_data_dir / "asterisk" / "pjsip_local.conf"
    assert conf_path.exists()
    content = conf_path.read_text()
    assert "1.2.3.4" in content
    assert "transport-udp" in content


def test_extension_status(client):
    """GET /api/extensions/status returns JSON list."""
    resp = client.get("/api/extensions/status")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_linphone_qr_metadata_and_public_provisioning(client):
    resp = client.post(
        "/api/extensions",
        json={
            "number": 21,
            "display_name": "Linphone User",
            "sip_password": "securepass1234567",
            "video_capable": True,
        },
    )
    assert resp.status_code == 200
    extension = resp.json()

    qr_resp = client.get(f"/api/extensions/{extension['id']}/linphone-qr")
    assert qr_resp.status_code == 200
    payload = qr_resp.json()
    assert payload["extension_number"] == 21
    assert payload["display_name"] == "Linphone User"
    assert payload["provisioning_path"].startswith("/api/linphone/provision/")

    token = payload["provisioning_path"].rsplit("/", 1)[-1]
    xml_resp = client.get(f"/api/linphone/provision/{token}")
    assert xml_resp.status_code == 200
    assert xml_resp.headers["content-type"].startswith("application/xml")
    xml = xml_resp.text
    assert '<section name="proxy_0">' in xml
    assert "sip:21@testserver" in xml
    assert "sip:testserver;transport=udp" in xml
    assert "securepass1234567" in xml
    assert '<entry name="capture" overwrite="true">1</entry>' in xml


def test_trunk_ami_reload(client, mock_ami):
    """POST /api/trunk calls ami_reload_pjsip (mock asserted)."""
    client.post(
        "/api/trunk",
        json={
            "registrar_host": "sip.example.com",
            "port": 5060,
            "auth_username": "987654321",
            "password": "anothersecret",
            "phone_number": "049987654321",
            "reg_refresh": 60,
        },
    )
    mock_ami["reload_pjsip"].assert_called()


def test_routing_crud(client, mock_ami):
    # POST creates route
    resp = client.post("/api/routes", json={
        "did": "+4922222222",
        "destination_type": "extension",
        "destination_id": 10
    })
    assert resp.status_code == 200
    route = resp.json()
    assert route["did"] == "+4922222222"
    assert route["destination_type"] == "extension"
    route_id = route["id"]

    # GET returns the created route
    resp = client.get("/api/routes")
    assert resp.status_code == 200
    dids = [r["did"] for r in resp.json()]
    assert "+4922222222" in dids

    # DELETE removes the route
    resp = client.delete(f"/api/routes/{route_id}")
    assert resp.status_code == 200

    resp = client.get("/api/routes")
    dids = [r["did"] for r in resp.json()]
    assert "+4922222222" not in dids


def test_active_calls(client):
    """GET /api/status/active-calls returns JSON with 'count' integer key."""
    resp = client.get("/api/status/active-calls")
    assert resp.status_code == 200
    data = resp.json()
    assert "count" in data
    assert isinstance(data["count"], int)


def test_time_condition_crud(client, tmp_data_dir):
    """TimeCondition CRUD: POST creates, PATCH updates, DELETE removes."""
    # Create
    resp = client.post("/api/time-conditions", json={
        "name": "Business Hours",
        "did": "+4922222222",
        "open_hours_start": "07:00",
        "open_hours_end": "22:00",
        "open_days": "mon-sun",
        "open_destination": 10,
        "closed_destination": 10,
    })
    assert resp.status_code == 200
    tc = resp.json()
    assert tc["did"] == "+4922222222"
    tc_id = tc["id"]

    # Verify conf was regenerated
    conf_path = tmp_data_dir / "asterisk" / "extensions_routing.conf"
    assert conf_path.exists()
    content = conf_path.read_text()
    assert "+4922222222" in content

    # Patch
    resp2 = client.patch(f"/api/time-conditions/{tc_id}", json={"open_hours_end": "20:00"})
    assert resp2.status_code == 200
    assert resp2.json()["open_hours_end"] == "20:00"

    # Delete
    resp3 = client.delete(f"/api/time-conditions/{tc_id}")
    assert resp3.status_code == 200

    # List should be empty
    resp4 = client.get("/api/time-conditions")
    assert resp4.status_code == 200
    assert resp4.json() == []


def test_time_condition_conf_regen(client, tmp_data_dir):
    """GotoIfTime and Voicemail() appear in generated extensions_routing.conf."""
    client.post("/api/time-conditions", json={
        "name": "Hours",
        "did": "+4900000000",
        "open_hours_start": "07:00",
        "open_hours_end": "22:00",
        "open_days": "mon-sun",
        "open_destination": 10,
        "closed_destination": 10,
    })
    conf_path = tmp_data_dir / "asterisk" / "extensions_routing.conf"
    content = conf_path.read_text()
    assert "GotoIfTime" in content
    assert "Voicemail(10@default,u)" in content
    assert "Dial(PJSIP/10,30)" in content
    assert "exten => _XX,1,NoOp(Internal call" in content


def test_extension_creates_vm_settings(client, tmp_data_dir):
    """POST /api/extensions auto-creates VoicemailSettings and regenerates voicemail conf."""
    resp = client.post("/api/extensions", json={
        "number": 15,
        "display_name": "Test VM User",
        "sip_password": "securepass1234567",
    })
    assert resp.status_code == 200
    ext_id = resp.json()["id"]

    # VoicemailSettings must exist for this extension
    vm_resp = client.get("/api/voicemail-settings")
    assert vm_resp.status_code == 200
    vm_list = vm_resp.json()
    ext_vm = [v for v in vm_list if v["extension_id"] == ext_id]
    assert len(ext_vm) == 1
    assert ext_vm[0]["mailbox"] == "15@default"

    # voicemail_mailboxes.conf must exist and contain extension 15
    mailbox_conf = tmp_data_dir / "asterisk" / "voicemail_mailboxes.conf"
    assert mailbox_conf.exists()
    content = mailbox_conf.read_text()
    assert "15 =>" in content


def test_voicemail_messages(client, tmp_data_dir):
    """GET /api/voicemail/messages/{ext_num} returns [] when inbox empty; 200 with file after creation."""
    # Create extension first
    resp = client.post("/api/extensions", json={
        "number": 10, "display_name": "Alice", "sip_password": "securepass1234567"
    })
    assert resp.status_code == 200

    # Empty inbox → [] not 500 (Pitfall 4)
    resp_list = client.get("/api/voicemail/messages/10")
    assert resp_list.status_code == 200
    assert resp_list.json() == []

    # Create a fake WAV file in the INBOX
    inbox = tmp_data_dir / "asterisk" / "spool" / "voicemail" / "default" / "10" / "INBOX"
    inbox.mkdir(parents=True, exist_ok=True)
    (inbox / "msg0000.wav").write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")

    resp_list2 = client.get("/api/voicemail/messages/10")
    assert resp_list2.status_code == 200
    data = resp_list2.json()
    assert len(data) == 1
    assert data[0]["filename"] == "msg0000.wav"


def test_voicemail_path_traversal(client, tmp_data_dir):
    """GET /api/voicemail/messages/{ext_num}/{filename} rejects traversal attempts."""
    client.post("/api/extensions", json={
        "number": 11, "display_name": "Bob", "sip_password": "securepass1234567"
    })
    # Non-matching filename pattern → 400
    resp2 = client.get("/api/voicemail/messages/11/etc_passwd")
    assert resp2.status_code == 400


def test_greeting_upload(client, tmp_data_dir):
    """POST /api/voicemail-settings/{id}/greeting writes unavail.wav to spool path."""
    # Create extension + VM settings
    resp = client.post("/api/extensions", json={
        "number": 12, "display_name": "Carol", "sip_password": "securepass1234567"
    })
    assert resp.status_code == 200

    # Get the VM settings id
    vm_resp = client.get("/api/voicemail-settings")
    vm_list = vm_resp.json()
    carol_vm = next((v for v in vm_list if v["mailbox"] == "12@default"), None)
    assert carol_vm is not None
    vm_id = carol_vm["id"]

    # Upload greeting
    fake_wav = b"RIFF\x00\x00\x00\x00WAVEfmt "
    resp_upload = client.post(
        f"/api/voicemail-settings/{vm_id}/greeting",
        files={"file": ("greeting.wav", fake_wav, "audio/wav")},
    )
    assert resp_upload.status_code == 200
    assert resp_upload.json() == {"ok": True}

    # File must exist at expected spool path
    greeting_path = tmp_data_dir / "asterisk" / "spool" / "voicemail" / "default" / "12" / "unavail.wav"
    assert greeting_path.exists()

    # GET greeting returns 200
    resp_get = client.get("/api/voicemail/greeting/12")
    assert resp_get.status_code == 200


def test_video_capable_field(client, mock_ami):
    """video_capable field defaults to False and can be set to True."""
    resp = client.post("/api/extensions", json={
        "number": 99, "display_name": "Doorbell", "sip_password": "doorbellpass12345"
    })
    assert resp.status_code == 200
    assert resp.json()["video_capable"] is False

    resp = client.post("/api/extensions", json={
        "number": 98, "display_name": "Video Phone", "sip_password": "videopass1234567",
        "video_capable": True
    })
    assert resp.status_code == 200
    assert resp.json()["video_capable"] is True


def _get_extension_stanza(conf_content: str, ext_number: int) -> str:
    """Extract the stanza block for a specific extension number from pjsip conf."""
    import re
    # Find the section starting at [ext_number] up to the next top-level [section]
    # or end of file, but only the endpoint stanza (not -auth or -aors)
    lines = conf_content.split("\n")
    in_stanza = False
    stanza_lines = []
    for line in lines:
        if not in_stanza and line.strip() == f"[{ext_number}]":
            in_stanza = True
            stanza_lines = [line]
        elif in_stanza:
            # Stop at next section header (but not -auth or -aors for this ext)
            if line.startswith("[") and line.strip() not in (f"[{ext_number}-auth]", f"[{ext_number}-aors]"):
                break
            stanza_lines.append(line)
    return "\n".join(stanza_lines)


def test_doorbell_extension_conf(client, mock_ami, tmp_data_dir):
    """video_capable=True generates h264 + max_video_streams=1 in pjsip conf."""
    resp = client.post("/api/extensions", json={
        "number": 97, "display_name": "Doorbell2", "sip_password": "doorbellpass12345",
        "video_capable": True
    })
    assert resp.status_code == 200
    conf_path = tmp_data_dir / "asterisk" / "pjsip_extensions.conf"
    full_content = conf_path.read_text()
    stanza = _get_extension_stanza(full_content, 97)
    assert "allow             = h264" in stanza
    assert "max_video_streams = 1" in stanza
    assert "doorbell-out" in stanza
    assert "max_video_streams = 0" not in stanza


def test_non_video_extension_conf(client, mock_ami, tmp_data_dir):
    """video_capable=False generates max_video_streams=0, no h264."""
    resp = client.post("/api/extensions", json={
        "number": 96, "display_name": "Alice2", "sip_password": "alicepass123456789",
        "video_capable": False
    })
    assert resp.status_code == 200
    conf_path = tmp_data_dir / "asterisk" / "pjsip_extensions.conf"
    full_content = conf_path.read_text()
    stanza = _get_extension_stanza(full_content, 96)
    assert "max_video_streams = 0" in stanza
    assert "allow             = h264" not in stanza
    assert "internal" in stanza


def test_ring_group_crud(client, mock_ami):
    """RingGroup CRUD creates, lists, and deletes."""
    for number in (10, 11, 12):
        _ensure_extension(client, number)
    resp = client.post("/api/ring-groups", json={
        "number": 70, "name": "All Phones", "extension_numbers": "10,11,12", "ring_timeout": 30
    })
    assert resp.status_code == 200
    rg_id = resp.json()["id"]
    assert resp.json()["number"] == 70

    resp = client.get("/api/ring-groups")
    assert resp.status_code == 200
    assert any(rg["id"] == rg_id for rg in resp.json())

    resp = client.delete(f"/api/ring-groups/{rg_id}")
    assert resp.status_code == 200


def test_doorbell_dialplan_context(client, mock_ami, tmp_data_dir):
    """RingGroup creates [doorbell-out] context in extensions_routing.conf."""
    for number in (10, 11):
        _ensure_extension(client, number)
    resp = client.post("/api/ring-groups", json={
        "number": 71, "name": "Doorbell Ring", "extension_numbers": "10,11", "ring_timeout": 30
    })
    assert resp.status_code == 200
    conf_path = tmp_data_dir / "asterisk" / "extensions_routing.conf"
    content = conf_path.read_text()
    assert "[doorbell-out]" in content
    assert "PJSIP/10&PJSIP/11" in content
    assert "exten => 71,1,NoOp(Internal ring group Doorbell Ring)" in content
    assert "Dial(PJSIP/10&PJSIP/11,30)" in content


def test_extension_numbers_validation(client, mock_ami):
    """extension_numbers field rejects empty and non-numeric values."""
    for number in (10, 11, 12):
        _ensure_extension(client, number)
    # Valid: comma-separated integers
    resp = client.post("/api/ring-groups", json={
        "number": 72,
        "name": "All Phones",
        "extension_numbers": "10,11,12",
        "ring_timeout": 30,
    })
    assert resp.status_code == 200

    # Valid: single member
    resp = client.post("/api/ring-groups", json={
        "number": 73,
        "name": "Solo",
        "extension_numbers": "10",
        "ring_timeout": 20,
    })
    assert resp.status_code == 200

    # Invalid: empty
    resp = client.post("/api/ring-groups", json={
        "number": 74,
        "name": "Empty",
        "extension_numbers": "",
        "ring_timeout": 30,
    })
    assert resp.status_code == 422

    # Invalid: contains non-numeric
    resp = client.post("/api/ring-groups", json={
        "number": 75,
        "name": "Bad",
        "extension_numbers": "10,abc,12",
        "ring_timeout": 30,
    })
    assert resp.status_code == 422

    # Invalid: extension number does not exist
    resp = client.post("/api/ring-groups", json={
        "number": 76,
        "name": "Unknown",
        "extension_numbers": "10,88",
        "ring_timeout": 30,
    })
    assert resp.status_code == 422

    # Invalid: group number collides with an existing extension
    resp = client.post("/api/ring-groups", json={
        "number": 10,
        "name": "Collision",
        "extension_numbers": "10,11",
        "ring_timeout": 30,
    })
    assert resp.status_code == 422

    # Invalid: group number collides with another ring group
    resp = client.post("/api/ring-groups", json={
        "number": 72,
        "name": "Duplicate",
        "extension_numbers": "10,11",
        "ring_timeout": 30,
    })
    assert resp.status_code == 422


def test_extension_auto_password(client, tmp_data_dir):
    """SEC-03: Creating extension without sip_password auto-generates 16-char SIP-safe password."""
    resp = client.post(
        "/api/extensions",
        json={"number": 30, "display_name": "Auto PW Test"},
    )
    assert resp.status_code == 200
    pw = resp.json()["sip_password"]
    assert len(pw) == 16, f"Expected 16-char password, got {len(pw)}: {pw!r}"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", pw) is not None, f"Password contains SIP-unsafe chars: {pw!r}"


def test_generate_password_endpoint(client):
    """SEC-03: GET /api/extensions/generate-password returns 16-char SIP-safe token."""
    resp = client.get("/api/extensions/generate-password")
    assert resp.status_code == 200
    pw = resp.json()["password"]
    assert len(pw) == 16, f"Expected 16-char password, got {len(pw)}: {pw!r}"
    assert re.fullmatch(r"[A-Za-z0-9_-]+", pw) is not None, f"Password contains SIP-unsafe chars: {pw!r}"


def test_ivr_submenu_target_is_supported(client, tmp_data_dir):
    resp_main = client.post("/api/ivrs", json={
        "number": 23,
        "name": "Hauptmenu",
        "timeout": 10,
        "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"hangup"}]',
    })
    assert resp_main.status_code == 200

    resp_sub = client.post("/api/ivrs", json={
        "number": 24,
        "name": "Untermenu",
        "timeout": 10,
        "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"ivr","target":23}]',
    })
    assert resp_sub.status_code == 200

    conf_path = tmp_data_dir / "asterisk" / "extensions_routing.conf"
    content = conf_path.read_text()
    assert "[ivr-1]" in content
    assert "[ivr-2]" in content
    assert "exten => 1,1,Goto(ivr-1,s,1)" in content


def test_ivr_submenu_cannot_point_to_itself(client):
    resp = client.post("/api/ivrs", json={
        "number": 22,
        "name": "Self Loop",
        "timeout": 10,
        "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"ivr","target":22}]',
    })
    assert resp.status_code == 422


# ── GAP-INGRESS regression tests (06-04) ───────────────────────────────────────
# These exercise the SPA catch-all injection against a REAL index.html fixture
# (via BPX_DIST_DIR / _dist_index), NOT the "Frontend not built" stub. They prove:
#   - X-Ingress-Path is injected into window.__INGRESS_PATH__
#   - relative ./assets refs are rewritten to the ingress prefix (asset-resolution fix)
#   - a malformed/hostile ingress path is treated as empty (T-06-01)

# Fixture index.html mirrors the shipped Vite build: unminified fallback line,
# the stable marker anchor, and relative ./assets refs.
_FIXTURE_INDEX_HTML = """<!DOCTYPE html>
<html lang="de" class="dark">
  <head>
    <meta charset="UTF-8" />
    <title>ha-phone</title>
    <!--INGRESS_PATH-->
    <script>
      window.__INGRESS_PATH__ = window.__INGRESS_PATH__ || "";
    </script>
    <script type="module" crossorigin src="./assets/index-TEST.js"></script>
    <link rel="stylesheet" crossorigin href="./assets/index-TEST.css">
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>
"""


@pytest.fixture
def ingress_client(tmp_path, monkeypatch):
    """A TestClient whose SPA catch-all reads a REAL fixture index.html."""
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(_FIXTURE_INDEX_HTML)
    import backend.main as main
    monkeypatch.setattr(main, "_dist_index", dist / "index.html")
    from fastapi.testclient import TestClient
    return TestClient(main.app)


def test_ingress_path_injected(ingress_client):
    """GET / with X-Ingress-Path injects the populated path (not the not-built stub)."""
    token_path = "/api/hassio_ingress/TOKEN"
    resp = ingress_client.get("/", headers={"X-Ingress-Path": token_path})
    assert resp.status_code == 200
    body = resp.text
    # Injection landed — exact populated assignment present
    assert f'window.__INGRESS_PATH__ = "{token_path}"' in body
    # NOT the not-built stub
    assert "Frontend not built" not in body
    # Asset refs rewritten to the ingress prefix so they resolve on deep routes
    assert f'{token_path}/assets/index-TEST.js' in body
    assert "./assets/index-TEST.js" not in body


def test_ingress_no_header_renders_empty(ingress_client):
    """GET / without the header still serves renderable HTML with empty ingress path."""
    resp = ingress_client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert 'window.__INGRESS_PATH__ = ""' in body
    assert "Frontend not built" not in body
    # With no prefix, relative asset refs stay relative (resolve against root)
    assert "./assets/index-TEST.js" in body


def test_ingress_path_malformed_rejected(ingress_client):
    """A hostile/malformed X-Ingress-Path is treated as empty (T-06-01)."""
    resp = ingress_client.get(
        "/", headers={"X-Ingress-Path": '"><script>alert(1)</script>'}
    )
    assert resp.status_code == 200
    body = resp.text
    assert 'window.__INGRESS_PATH__ = ""' in body
    assert "<script>alert(1)</script>" not in body
