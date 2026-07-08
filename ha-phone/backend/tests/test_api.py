import re
import pytest
from pathlib import Path
from unittest.mock import patch


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
    assert 'xmlns="http://www.linphone.org/xsds/lpconfig.xsd"' in xml
    assert "&lt;sip:testserver;transport=udp&gt;" in xml
    assert "&lt;sip:testserver;transport=udp;lr&gt;" in xml
    assert '<entry name="realm" overwrite="true">testserver</entry>' in xml
    assert "securepass1234567" in xml
    assert '<entry name="enabled" overwrite="true">1</entry>' in xml
    assert '<entry name="capture" overwrite="true">1</entry>' in xml
    assert '<entry name="push_notification_allowed" overwrite="true">0</entry>' in xml
    assert '<entry name="remote_push_notification_allowed" overwrite="true">0</entry>' in xml


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


def test_diagnostics_overview(client, mock_ami):
    mock_ami["trunk_status"].return_value = "Registered"
    mock_ami["trunk_debug"].return_value = {
        "Status": "Registered",
        "NextReg": "2026-07-06 15:30:00",
    }
    mock_ami["ext_diagnostics"].return_value = [
        {
            "number": "11",
            "status": "Online",
            "device_state": "Not in use",
            "active_channels": 0,
            "aor": "11",
            "contacts": 1,
            "contact_status": "Reachable",
            "contact_uri": "sip:11@192.168.7.50:5060",
            "roundtrip_usec": 3200,
            "user_agent": "MicroSIP",
        }
    ]
    mock_ami["active_calls"].return_value = 1
    mock_ami["channel_details"].return_value = [
        {
            "channel": "PJSIP/11-00000001",
            "state": "Up",
            "caller_id_num": "11",
            "caller_id_name": "sandro",
            "connected_line_num": "12",
            "connected_line_name": "larissa",
            "application": "Dial",
            "context": "from-internal",
            "extension": "12",
            "duration": "00:00:04",
        }
    ]

    resp = client.get("/api/diagnostics/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert data["trunk_status"] == "Registered"
    assert data["trunk_debug"]["Status"] == "Registered"
    assert data["active_calls"] == 1
    assert len(data["extensions"]) == 1
    assert data["extensions"][0]["number"] == "11"
    assert data["extensions"][0]["contact_status"] == "Reachable"
    assert len(data["channels"]) == 1
    assert data["channels"][0]["channel"] == "PJSIP/11-00000001"
    assert data["config_regeneration"]["ok"] is True


def test_config_regeneration_status_endpoint_records_success(client, tmp_data_dir):
    status_path = tmp_data_dir / "asterisk" / "config_regeneration_status.json"
    status_path.unlink(missing_ok=True)

    resp = client.post(
        "/api/extensions",
        json={
            "number": 31,
            "display_name": "Status Probe",
            "sip_password": "statusprobe12345",
        },
    )
    assert resp.status_code == 200

    status_resp = client.get("/api/diagnostics/config-regeneration")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["ok"] is True
    assert data["source"] == "extensions.create:31"
    steps = {step["name"]: step for step in data["steps"]}
    assert steps["extensions"]["ok"] is True
    assert steps["voicemail"]["ok"] is True
    assert steps["routing"]["ok"] is True


def test_extension_regeneration_failure_is_isolated(client, mock_ami, tmp_data_dir):
    status_path = tmp_data_dir / "asterisk" / "config_regeneration_status.json"
    status_path.unlink(missing_ok=True)

    with patch(
        "backend.routers.extensions._regenerate_routing_conf",
        side_effect=RuntimeError("routing exploded"),
    ):
        resp = client.post(
            "/api/extensions",
            json={
                "number": 32,
                "display_name": "Partial Regen",
                "sip_password": "partialregen123",
            },
        )

    assert resp.status_code == 200
    assert (tmp_data_dir / "asterisk" / "pjsip_extensions.conf").read_text().find("[32]") != -1
    assert (tmp_data_dir / "asterisk" / "voicemail_mailboxes.conf").read_text().find("32 =>") != -1
    mock_ami["reload_pjsip"].assert_called_once()
    mock_ami["reload_voicemail"].assert_called_once()
    mock_ami["reload_dialplan"].assert_not_called()

    status_resp = client.get("/api/diagnostics/config-regeneration")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["ok"] is False
    assert data["source"] == "extensions.create:32"
    steps = {step["name"]: step for step in data["steps"]}
    assert steps["extensions"]["ok"] is True
    assert steps["voicemail"]["ok"] is True
    assert steps["routing"]["ok"] is False
    assert "routing exploded" in steps["routing"]["message"]


def test_boot_regeneration_isolates_trunk_and_mail_from_routing_failures(client, tmp_data_dir):
    status_path = tmp_data_dir / "asterisk" / "config_regeneration_status.json"
    status_path.unlink(missing_ok=True)

    trunk_resp = client.post(
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
    assert trunk_resp.status_code == 200

    smtp_resp = client.post(
        "/api/settings/smtp",
        json={
            "host": "smtp.example.com",
            "port": 587,
            "encryption": "starttls",
            "username": "mailer",
            "password": "mailsecret",
            "from_addr": "pbx@example.com",
            "from_name": "HA-Phone",
            "enabled": True,
        },
    )
    assert smtp_resp.status_code == 200

    from sqlmodel import Session, select

    from backend.database import get_engine
    from backend.models import Trunk
    from backend.regeneration import run_regeneration_steps
    from backend.routers.extensions import _regenerate_extensions_conf, _regenerate_voicemail_conf
    from backend.routers.settings import regenerate_mail_configs
    from backend.routers.trunk import _regenerate_trunk_conf
    import backend.routers.time_conditions as time_conditions_module

    with Session(get_engine()) as session:
        trunk = session.exec(select(Trunk)).first()
        assert trunk is not None
        with patch(
            "backend.routers.time_conditions._regenerate_routing_conf",
            side_effect=RuntimeError("boot routing exploded"),
        ):
            summary = run_regeneration_steps(
                "boot.init",
                [
                    ("extensions", lambda: _regenerate_extensions_conf(session)),
                    ("voicemail", lambda: _regenerate_voicemail_conf(session)),
                    ("routing", lambda: time_conditions_module._regenerate_routing_conf(session)),
                    ("mail", lambda: regenerate_mail_configs(session)),
                    ("trunk", lambda trunk=trunk: _regenerate_trunk_conf(trunk)),
                ],
            )

    assert summary["ok"] is False
    assert (tmp_data_dir / "asterisk" / "pjsip_trunk.conf").exists()
    assert (tmp_data_dir / "asterisk" / "voicemail_general.conf").exists()
    assert (tmp_data_dir / "asterisk" / "msmtprc").exists()
    assert "type = registration" in (tmp_data_dir / "asterisk" / "pjsip_trunk.conf").read_text()
    assert "smtp.example.com" in (tmp_data_dir / "asterisk" / "msmtprc").read_text()
    steps = {step["name"]: step for step in summary["steps"]}
    assert steps["routing"]["ok"] is False
    assert steps["mail"]["ok"] is True
    assert steps["trunk"]["ok"] is True


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
    """video_capable=True keeps normal dial context and enables video codecs."""
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
    assert "context           = from-internal" in stanza
    assert "trust_id_outbound = yes" in stanza
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
    assert "context           = from-internal" in stanza


def test_internal_only_extension_conf(client, mock_ami, tmp_data_dir):
    """internal_only=True uses the restricted dial context regardless of video support."""
    resp = client.post("/api/extensions", json={
        "number": 95, "display_name": "Nur intern", "sip_password": "internalpass12345",
        "video_capable": True, "internal_only": True
    })
    assert resp.status_code == 200
    conf_path = tmp_data_dir / "asterisk" / "pjsip_extensions.conf"
    stanza = _get_extension_stanza(conf_path.read_text(), 95)
    assert "context           = from-internal-restricted" in stanza
    assert "allow             = h264" in stanza


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


def test_outbound_plus_pattern_is_rendered(client, tmp_data_dir):
    """Outbound trunk context must also accept already-normalized +49 numbers."""
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
    conf_path = tmp_data_dir / "asterisk" / "extensions_routing.conf"
    content = conf_path.read_text()
    assert "exten => _+X.,1,NoOp(Outbound via SIP trunk (E.164): ${EXTEN})" in content
    assert "same => n,Goto(outbound-pstn,${EXTEN:1},1)" in content


def test_trunk_conf_keeps_auth_username_separate_from_registered_number(client, tmp_data_dir):
    """Registration identity must stay the phone number while auth uses the provider account."""
    resp = client.post(
        "/api/trunk",
        json={
            "registrar_host": "sip.example.com",
            "port": 5060,
            "transport": "udp",
            "domain": "voice.example.net",
            "auth_username": "30501827343",
            "password": "mysecretpassword",
            "phone_number": "063483260104",
            "reg_refresh": 60,
        },
    )
    assert resp.status_code == 200
    conf_path = tmp_data_dir / "asterisk" / "pjsip_trunk.conf"
    content = conf_path.read_text()
    assert "server_uri = sip:sip.example.com" in content
    assert "client_uri = sip:063483260104@voice.example.net" in content
    assert "contact_user = 063483260104" in content
    assert "username = 30501827343" in content
    assert "from_user = 063483260104" in content
    assert "from_domain = voice.example.net" in content
    assert "send_pai = yes" in content
    assert "send_rpid = yes" in content
    assert "trust_id_inbound = yes" in content


def test_trunk_conf_omits_default_port_but_keeps_custom_port(client, tmp_data_dir):
    """SRV lookup requires omitting :5060, but custom ports must still be rendered."""
    resp = client.post(
        "/api/trunk",
        json={
            "registrar_host": "sip.example.com",
            "port": 5060,
            "transport": "udp",
            "domain": "",
            "auth_username": "123456789",
            "password": "mysecretpassword",
            "phone_number": "049123456789",
            "reg_refresh": 60,
        },
    )
    assert resp.status_code == 200
    conf_path = tmp_data_dir / "asterisk" / "pjsip_trunk.conf"
    content = conf_path.read_text()
    assert "server_uri = sip:sip.example.com" in content
    assert "server_uri = sip:sip.example.com:5060" not in content
    assert "contact = sip:sip.example.com" in content
    assert "contact = sip:sip.example.com:5060" not in content

    resp = client.post(
        "/api/trunk",
        json={
            "registrar_host": "sip.example.com",
            "port": 5070,
            "transport": "udp",
            "domain": "",
            "auth_username": "123456789",
            "password": "mysecretpassword",
            "phone_number": "049123456789",
            "reg_refresh": 60,
        },
    )
    assert resp.status_code == 200
    content = conf_path.read_text()
    assert "server_uri = sip:sip.example.com:5070" in content
    assert "contact = sip:sip.example.com:5070" in content


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


def _make_wav_bytes(sample_rate: int, channels: int, sample_width: int = 2, seconds: float = 0.2) -> bytes:
    """Build a real, valid WAV file in memory so upload tests exercise actual
    sox conversion instead of just checking the file extension."""
    import io
    import wave

    n_frames = int(sample_rate * seconds)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00" * n_frames * channels * sample_width)
    return buf.getvalue()


def test_ivr_greeting_upload_normalizes_sample_rate_and_channels(client, tmp_data_dir):
    """D7: a 44.1kHz stereo WAV (typical Audacity/phone export) must be
    converted to the 8kHz mono format Asterisk's Background() expects,
    not just accepted as-is because the extension is .wav."""
    import wave

    resp = client.post("/api/ivrs", json={
        "number": 60, "name": "Greeting Test", "timeout": 10, "max_invalid_tries": 3, "options": "[]",
    })
    assert resp.status_code == 200
    ivr_id = resp.json()["id"]

    wav_bytes = _make_wav_bytes(sample_rate=44100, channels=2)
    resp = client.post(
        f"/api/ivrs/{ivr_id}/greeting",
        files={"file": ("greeting.wav", wav_bytes, "audio/wav")},
    )
    assert resp.status_code == 200
    filename = resp.json()["filename"]

    stored_path = tmp_data_dir / "sounds" / "custom" / "ivr" / filename
    assert stored_path.exists()
    with wave.open(str(stored_path), "rb") as wav_file:
        assert wav_file.getframerate() == 8000
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == 2


def test_ivr_greeting_upload_rejects_non_audio_content(client):
    """A .wav-named file that isn't actually audio must be rejected, not
    silently stored as a greeting Asterisk can't play."""
    resp = client.post("/api/ivrs", json={
        "number": 61, "name": "Bad Upload", "timeout": 10, "max_invalid_tries": 3, "options": "[]",
    })
    assert resp.status_code == 200
    ivr_id = resp.json()["id"]

    resp = client.post(
        f"/api/ivrs/{ivr_id}/greeting",
        files={"file": ("greeting.wav", b"this is not a wav file", "audio/wav")},
    )
    assert resp.status_code == 422


def test_ivr_greeting_upload_rejects_empty_file(client):
    resp = client.post("/api/ivrs", json={
        "number": 62, "name": "Empty Upload", "timeout": 10, "max_invalid_tries": 3, "options": "[]",
    })
    assert resp.status_code == 200
    ivr_id = resp.json()["id"]

    resp = client.post(
        f"/api/ivrs/{ivr_id}/greeting",
        files={"file": ("greeting.wav", b"", "audio/wav")},
    )
    assert resp.status_code == 422


# ---- Referential integrity on delete (Roadmap Phase A.3) ----
# Deleting a ring group or IVR menu that's still referenced by an inbound
# route (or, for IVR, by another menu's submenu option) used to succeed
# silently - the route/option was left pointing at a dead id, which the
# dialplan either quietly Congestion()'d (ring group) or could Goto() into an
# invalid context (IVR). Both are now blocked with a 409 naming what's still
# using it.

def test_ring_group_delete_blocked_by_route(client, mock_ami):
    for number in (10, 11):
        _ensure_extension(client, number)
    resp = client.post("/api/ring-groups", json={
        "number": 63, "name": "Support", "extension_numbers": "10,11", "ring_timeout": 30
    })
    assert resp.status_code == 200
    rg_id = resp.json()["id"]

    resp = client.post("/api/routes", json={
        "did": "+4933333333", "destination_type": "ring_group", "destination_id": rg_id,
    })
    assert resp.status_code == 200
    route_id = resp.json()["id"]

    resp = client.delete(f"/api/ring-groups/{rg_id}")
    assert resp.status_code == 409
    assert "+4933333333" in resp.json()["detail"]

    # Cleanup path still works once the blocking route is gone.
    assert client.delete(f"/api/routes/{route_id}").status_code == 200
    assert client.delete(f"/api/ring-groups/{rg_id}").status_code == 200


def test_ivr_delete_blocked_by_route(client, tmp_data_dir):
    resp = client.post("/api/ivrs", json={
        "number": 64, "name": "Empfang", "timeout": 10, "max_invalid_tries": 3, "options": "[]",
    })
    assert resp.status_code == 200
    ivr_id = resp.json()["id"]

    resp = client.post("/api/routes", json={
        "did": "+4944444444", "destination_type": "ivr", "destination_id": ivr_id,
    })
    assert resp.status_code == 200
    route_id = resp.json()["id"]

    resp = client.delete(f"/api/ivrs/{ivr_id}")
    assert resp.status_code == 409
    assert "+4944444444" in resp.json()["detail"]

    assert client.delete(f"/api/routes/{route_id}").status_code == 200
    assert client.delete(f"/api/ivrs/{ivr_id}").status_code == 200


def test_ivr_delete_blocked_by_submenu_reference(client, tmp_data_dir):
    resp = client.post("/api/ivrs", json={
        "number": 65, "name": "Zielmenu", "timeout": 10, "max_invalid_tries": 3, "options": "[]",
    })
    assert resp.status_code == 200
    target_id = resp.json()["id"]

    resp = client.post("/api/ivrs", json={
        "number": 66, "name": "Hauptmenu", "timeout": 10, "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"ivr","target":65}]',
    })
    assert resp.status_code == 200

    resp = client.delete(f"/api/ivrs/{target_id}")
    assert resp.status_code == 409
    assert "Hauptmenu" in resp.json()["detail"]


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


# ---- Numbering-space service (Roadmap Phase A.1 / D5) ----
# Extension, RingGroup and IVRMenu all share the 10-99 dial-number space.
# Before backend/numbering.py existed, ring_groups.py and ivr.py each carried
# their own near-identical cross-table check, and extensions.py had NONE at
# all - an extension could be created with a number already used by a ring
# group or IVR menu. These tests lock in that a collision between any two of
# the three types is now rejected consistently, regardless of which side is
# created first.

def test_extension_number_conflicts_with_existing_ring_group(client, mock_ami):
    for number in (10, 11):
        _ensure_extension(client, number)
    resp = client.post("/api/ring-groups", json={
        "number": 80, "name": "Support", "extension_numbers": "10,11", "ring_timeout": 30
    })
    assert resp.status_code == 200

    resp = client.post("/api/extensions", json={
        "number": 80, "display_name": "Clash", "sip_password": "clashpassword1234"
    })
    assert resp.status_code == 422
    assert "ring group" in resp.json()["detail"]


def test_extension_number_conflicts_with_existing_ivr(client, tmp_data_dir):
    resp = client.post("/api/ivrs", json={
        "number": 81, "name": "Empfang", "timeout": 10, "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"hangup"}]',
    })
    assert resp.status_code == 200

    resp = client.post("/api/extensions", json={
        "number": 81, "display_name": "Clash", "sip_password": "clashpassword1234"
    })
    assert resp.status_code == 422
    assert "IVR menu" in resp.json()["detail"]


def test_ring_group_number_conflicts_with_existing_ivr(client, tmp_data_dir):
    """Previously unchecked: ring_groups.py never looked at IVRMenu at all."""
    resp = client.post("/api/ivrs", json={
        "number": 82, "name": "Empfang", "timeout": 10, "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"hangup"}]',
    })
    assert resp.status_code == 200

    for number in (10, 11):
        _ensure_extension(client, number)
    resp = client.post("/api/ring-groups", json={
        "number": 82, "name": "Clash", "extension_numbers": "10,11", "ring_timeout": 30
    })
    assert resp.status_code == 422
    assert "IVR menu" in resp.json()["detail"]


def test_ivr_number_conflicts_with_existing_extension(client):
    _ensure_extension(client, 83)
    resp = client.post("/api/ivrs", json={
        "number": 83, "name": "Clash", "timeout": 10, "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"hangup"}]',
    })
    assert resp.status_code == 422
    assert "extension" in resp.json()["detail"]


def test_extension_update_number_conflicts_across_types(client, mock_ami, tmp_data_dir):
    """Updating an extension's number must also check ring groups/IVR menus."""
    ext = _ensure_extension(client, 84)
    resp = client.post("/api/ivrs", json={
        "number": 85, "name": "Empfang", "timeout": 10, "max_invalid_tries": 3,
        "options": '[{"key":"1","action":"hangup"}]',
    })
    assert resp.status_code == 200

    resp = client.patch(f"/api/extensions/{ext['id']}", json={"number": 85})
    assert resp.status_code == 422
    assert "IVR menu" in resp.json()["detail"]


def test_all_routing_domains_combined_after_ivr_exists(client, mock_ami, tmp_data_dir):
    """Roadmap Phase A.4 'Fertig, wenn': re-creates the exact combination that
    caused D1 (IVR existing, then creating an extension/ring group/route
    cascades _regenerate_routing_conf for everyone) plus every other routing
    domain in one pass, and asserts the final dialplan actually contains all
    of it - not just that no request 500'd."""
    resp = client.post("/api/ivrs", json={
        "number": 90, "name": "Hauptmenu", "timeout": 8, "max_invalid_tries": 2,
        "options": '[{"key":"9","action":"hangup"}]',
    })
    assert resp.status_code == 200

    ext = _ensure_extension(client, 40, "Kombitest")
    _ensure_extension(client, 41)

    resp = client.post("/api/ring-groups", json={
        "number": 91, "name": "Kombi-Gruppe", "extension_numbers": "40,41", "ring_timeout": 20
    })
    assert resp.status_code == 200
    rg_id = resp.json()["id"]

    resp = client.post("/api/outbound-rules", json={
        "pattern": "9.", "strip": 1, "prepend": "+49", "priority": 5,
    })
    assert resp.status_code == 200

    resp = client.post("/api/routes", json={
        "did": "+4955555555", "destination_type": "ring_group", "destination_id": rg_id,
    })
    assert resp.status_code == 200

    resp = client.post("/api/time-conditions", json={
        "name": "Kombi-Zeiten", "did": "+4966666666",
        "open_hours_start": "08:00", "open_hours_end": "18:00", "open_days": "mon-fri",
        "open_destination": 40, "closed_destination": 41,
    })
    assert resp.status_code == 200

    # The scenario that actually broke in D1: updating the extension after
    # everything else exists re-triggers the full regeneration bundle again.
    resp = client.patch(f"/api/extensions/{ext['id']}", json={"display_name": "Kombitest Renamed"})
    assert resp.status_code == 200

    content = (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()
    assert "[ivr-1]" in content
    assert "exten => 91,1,NoOp(Internal ring group Kombi-Gruppe)" in content
    assert "exten => _9.,1,NoOp(Outbound rule '9.' strip 1 prepend '+49': ${EXTEN})" in content
    assert "+4955555555" in content
    assert "+4966666666" in content

    regen_status = client.get("/api/diagnostics/config-regeneration").json()
    assert regen_status["ok"] is True
    assert all(step["ok"] for step in regen_status["steps"])


# ---- Multi-line device provisioning (DECT base with several handsets) ----
# A DECT base can register several physical handsets, each needing its own
# SIP account - sharing one extension across handsets hits the AOR's
# max_contacts and leaves any handset beyond the limit with no line to dial
# out on at all (confirmed live: zero SIP traffic from the device, instant
# local busy tone). ProvisionedDevice.extension_numbers replaces the old
# single extension_id so a device can be assigned more than one extension.

# Builtin templates are only seeded from main.py's lifespan hook, which the
# `client` fixture doesn't run - tests create their own templates explicitly
# instead of depending on that seeding.

def _create_multiline_template(client) -> int:
    resp = client.post("/api/provisioning/templates", json={
        "name": "Test Multi-Line DECT",
        "vendor": "Test",
        "file_pattern": "{mac}.xml",
        "content": (
            "{% for account in accounts %}"
            'SipProvider.{{ loop.index0 }}.Name={{ account.number }}\n'
            'Handset.{{ loop.index0 }}.SIP.AuthPassword={{ account.sip_password }}\n'
            'Handset.{{ loop.index0 }}.SIP.DisplayName={{ account.display_name }}\n'
            "{% endfor %}"
        ),
    })
    assert resp.status_code == 200
    return resp.json()["id"]


def _create_singleline_template(client) -> int:
    resp = client.post("/api/provisioning/templates", json={
        "name": "Test Single-Line Desk Phone",
        "vendor": "Test",
        "file_pattern": "{mac}.cfg",
        "content": "auth_name={{sip_username}}\ndisplay_name={{display_name}}\n",
    })
    assert resp.status_code == 200
    return resp.json()["id"]


def test_provisioned_device_accepts_multiple_extensions(client):
    _ensure_extension(client, 50)
    _ensure_extension(client, 51)
    tpl_id = _create_multiline_template(client)

    resp = client.post("/api/provisioning/devices", json={
        "name": "DECT Basis", "manufacturer": "Gigaset", "model": "N610 IP PRO",
        "mac": "aabbccddeeff", "extension_numbers": "50,51", "template_id": tpl_id,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["extension_numbers"] == [50, 51]


def test_provisioned_device_rejects_unknown_extension(client):
    tpl_id = _create_multiline_template(client)
    resp = client.post("/api/provisioning/devices", json={
        "name": "DECT Basis", "manufacturer": "Gigaset", "model": "N610 IP PRO",
        "mac": "aabbccddeeaa", "extension_numbers": "999", "template_id": tpl_id,
    })
    assert resp.status_code == 422
    assert "999" in resp.json()["detail"]


def test_provisioning_renders_one_sip_provider_per_extension(client):
    """The exact live bug: a base with N handsets needs N SipProvider/Handset
    blocks, not one shared account. Verifies the multi-line template loop."""
    _ensure_extension(client, 52, "Erster")
    _ensure_extension(client, 53, "Zweiter")
    tpl_id = _create_multiline_template(client)

    resp = client.post("/api/provisioning/devices", json={
        "name": "DECT Basis", "manufacturer": "Gigaset", "model": "N610 IP PRO",
        "mac": "112233445566", "extension_numbers": "52,53", "template_id": tpl_id,
    })
    assert resp.status_code == 200

    resp = client.get("/api/autoprovision/112233445566.xml")
    assert resp.status_code == 200
    xml = resp.text
    assert "SipProvider.0.Name=52" in xml
    assert "SipProvider.1.Name=53" in xml
    assert "Handset.0.SIP.AuthPassword=securepass1234567" in xml
    assert "Handset.1.SIP.DisplayName=Zweiter" in xml


def test_provisioning_single_extension_still_works_on_simple_template(client):
    """Non-looping templates (desk phones) must keep working unchanged via the
    top-level {{sip_username}} etc. vars mapped to the one assigned extension."""
    _ensure_extension(client, 54, "Solo")
    tpl_id = _create_singleline_template(client)

    resp = client.post("/api/provisioning/devices", json={
        "name": "Desk Phone", "manufacturer": "Yealink", "model": "T54W",
        "mac": "aa11bb22cc33", "extension_numbers": "54", "template_id": tpl_id,
    })
    assert resp.status_code == 200

    resp = client.get("/api/autoprovision/aa11bb22cc33.cfg")
    assert resp.status_code == 200
    body = resp.text
    assert "auth_name=54" in body
    assert "display_name=Solo" in body


def test_provisioned_device_extension_assignment_editable(client):
    """A device's extension assignment must be changeable at any time, not
    just fixed at creation."""
    _ensure_extension(client, 57, "First")
    _ensure_extension(client, 58, "Second")
    tpl_id = _create_singleline_template(client)

    resp = client.post("/api/provisioning/devices", json={
        "name": "Reassignable", "mac": "cc11dd22ee33",
        "extension_numbers": "57", "template_id": tpl_id,
    })
    assert resp.status_code == 200
    device_id = resp.json()["id"]

    resp = client.patch(f"/api/provisioning/devices/{device_id}", json={"extension_numbers": "58"})
    assert resp.status_code == 200
    assert resp.json()["extension_numbers"] == [58]

    resp = client.get("/api/provisioning/devices")
    updated = next(d for d in resp.json() if d["id"] == device_id)
    assert updated["extension_numbers"] == [58]


def test_deleting_provisioned_device_hangs_up_active_calls(client, mock_ami):
    """Roadmap live-feedback: deleting a device must disconnect it. Asterisk
    has no way to force-expire an idle registration, so the achievable,
    honest behavior is hanging up any call in progress right now."""
    _ensure_extension(client, 59, "Ringing")
    tpl_id = _create_singleline_template(client)
    resp = client.post("/api/provisioning/devices", json={
        "name": "Busy Phone", "mac": "dd22ee33ff44",
        "extension_numbers": "59", "template_id": tpl_id,
    })
    device_id = resp.json()["id"]

    mock_ami["hangup"].return_value = 1
    resp = client.delete(f"/api/provisioning/devices/{device_id}")
    assert resp.status_code == 200
    assert resp.json()["hung_up_calls"] == 1
    mock_ami["hangup"].assert_called_once_with("59")

    assert client.get("/api/provisioning/devices").json() == [] or all(
        d["id"] != device_id for d in client.get("/api/provisioning/devices").json()
    )


# ---- Secrets encryption at rest (D8) ----
# Trunk password, SMTP password, and SIP passwords used to sit in SQLite as
# plain text. These tests read the RAW database file directly (bypassing the
# ORM, which transparently decrypts) to prove the stored bytes are actually
# encrypted, then confirm the application still gets correct plaintext where
# it needs it (config generation), and that pre-existing plaintext rows
# (from before this feature existed) keep working during the transition.

def _raw_db_path(tmp_data_dir):
    return tmp_data_dir / "db" / "bpx.db"


def _raw_sqlite_value(tmp_data_dir, table: str, column: str, row_id: int):
    import sqlite3
    conn = sqlite3.connect(str(_raw_db_path(tmp_data_dir)))
    try:
        cur = conn.execute(f"SELECT {column} FROM {table} WHERE id = ?", (row_id,))
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def test_trunk_password_encrypted_at_rest(client, tmp_data_dir):
    resp = client.post("/api/trunk", json={
        "registrar_host": "sip.example.com", "port": 5060, "auth_username": "123456789",
        "password": "supersecrettrunkpw", "phone_number": "049123456789", "reg_refresh": 60,
    })
    assert resp.status_code == 200
    trunk_id = resp.json()["id"]

    raw = _raw_sqlite_value(tmp_data_dir, "trunk", "password", trunk_id)
    assert raw != "supersecrettrunkpw"
    assert raw.startswith("gAAAAA")  # Fernet token prefix

    # Config generation must still see the real password (Asterisk needs it).
    conf_path = tmp_data_dir / "asterisk" / "pjsip_trunk.conf"
    assert "password = supersecrettrunkpw" in conf_path.read_text()


def test_extension_sip_password_encrypted_at_rest(client, tmp_data_dir):
    resp = client.post("/api/extensions", json={
        "number": 55, "display_name": "Secret Test", "sip_password": "mysecretsippassword",
    })
    assert resp.status_code == 200
    ext_id = resp.json()["id"]

    raw = _raw_sqlite_value(tmp_data_dir, "extension", "sip_password", ext_id)
    assert raw != "mysecretsippassword"
    assert raw.startswith("gAAAAA")

    conf_path = tmp_data_dir / "asterisk" / "pjsip_extensions.conf"
    assert "password          = mysecretsippassword" in conf_path.read_text()


def test_decrypt_secret_falls_back_for_legacy_plaintext():
    """A value written before encryption existed (plain text, not a Fernet
    token) must decrypt to itself instead of raising - otherwise every
    pre-upgrade row would crash the app on first read."""
    from backend.crypto import decrypt_secret, encrypt_secret

    assert decrypt_secret("plain-old-password") == "plain-old-password"
    encrypted = encrypt_secret("plain-old-password")
    assert encrypted != "plain-old-password"
    assert decrypt_secret(encrypted) == "plain-old-password"


def test_legacy_plaintext_trunk_row_readable_without_crashing(client, tmp_data_dir):
    """Reading a Trunk row whose password column still holds legacy plain
    text (e.g. a row from before this feature existed) must not crash the
    ORM read path - EncryptedString.process_result_value falls back via
    decrypt_secret instead of raising on InvalidToken."""
    resp = client.post("/api/trunk", json={
        "registrar_host": "sip.example.com", "port": 5060, "auth_username": "123456789",
        "password": "placeholder", "phone_number": "049123456789", "reg_refresh": 60,
    })
    trunk_id = resp.json()["id"]

    import sqlite3
    conn = sqlite3.connect(str(_raw_db_path(tmp_data_dir)))
    conn.execute("UPDATE trunk SET password = ? WHERE id = ?", ("legacy-plaintext-pw", trunk_id))
    conn.commit()
    conn.close()

    # Creating an extension triggers _regenerate_routing_conf, which loads
    # the Trunk row via the ORM (for outbound CLIP) - that SELECT eagerly
    # decrypts every column of the row, including password, regardless of
    # whether the caller ever reads that attribute.
    resp = client.post("/api/extensions", json={
        "number": 56, "display_name": "Trigger Regen", "sip_password": "irrelevantpassword",
    })
    assert resp.status_code == 200


# ---- Backup / Restore (Roadmap Phase B.4) ----
# The core promise: a backup restored on a completely fresh instance must
# produce a working PBX, and secrets must survive the round-trip even
# though the target host has a DIFFERENT local encryption key than the
# source (D8's local Fernet key never leaves the host - the backup itself
# is protected by a separate, user-chosen password instead).

import io
import zipfile


def test_backup_export_produces_password_protected_zip(client, mock_ami):
    _ensure_extension(client, 45, "Backup Ext")
    resp = client.post("/api/backup/export", data={"password": "correcthorsebattery"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"

    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    assert set(zf.namelist()) == {"meta.json", "data.enc"}
    import json as _json
    meta = _json.loads(zf.read("meta.json"))
    assert meta["format_version"] == 1
    # The plaintext extension name/password must not appear anywhere in the
    # zip unencrypted - only inside the encrypted data.enc blob.
    assert b"Backup Ext" not in zf.read("meta.json")
    assert b"Backup Ext" not in zf.read("data.enc")


def test_backup_export_rejects_short_password(client, mock_ami):
    resp = client.post("/api/backup/export", data={"password": "short"})
    assert resp.status_code == 422


def test_backup_restore_round_trip_on_fresh_instance(client, mock_ami, tmp_data_dir):
    """The actual Fertig-Kriterium: export, then restore onto a database that
    has been wiped clean (simulating a fresh instance), and confirm the
    restored data - including a secret - is byte-for-byte correct despite
    the fresh instance having generated its own new local encryption key."""
    _ensure_extension(client, 46, "Round Trip")
    resp = client.post("/api/trunk", json={
        "registrar_host": "sip.example.com", "port": 5060, "auth_username": "123456789",
        "password": "originaltrunksecret", "phone_number": "049123456789", "reg_refresh": 60,
    })
    assert resp.status_code == 200

    export_resp = client.post("/api/backup/export", data={"password": "correcthorsebattery"})
    assert export_resp.status_code == 200
    backup_bytes = export_resp.content

    # Simulate a fresh instance: wipe the local encryption key so a new one
    # gets generated on next use, proving secrets don't depend on the
    # source host's key surviving.
    from backend.crypto import _key_path, reset_fernet_cache
    _key_path().unlink(missing_ok=True)
    reset_fernet_cache()

    # /api/backup/import wipes every covered table itself before re-inserting,
    # so restoring is exercised exactly as it would run on a truly empty DB.
    import_resp = client.post(
        "/api/backup/import",
        data={"password": "correcthorsebattery"},
        files={"file": ("backup.zip", backup_bytes, "application/zip")},
    )
    assert import_resp.status_code == 200
    body = import_resp.json()
    assert body["ok"] is True
    assert body["restored"]["extension"] >= 1

    resp = client.get("/api/extensions")
    numbers = [e["number"] for e in resp.json()]
    assert 46 in numbers

    # The trunk password must decrypt correctly under the FRESH instance's
    # NEW local key - it was never encrypted with that key in the backup,
    # proving the password-derived re-encryption round-trip actually works.
    conf_path = tmp_data_dir / "asterisk" / "pjsip_trunk.conf"
    assert "password = originaltrunksecret" in conf_path.read_text()


def test_backup_restore_rejects_wrong_password(client, mock_ami):
    export_resp = client.post("/api/backup/export", data={"password": "correcthorsebattery"})
    backup_bytes = export_resp.content

    import_resp = client.post(
        "/api/backup/import",
        data={"password": "totallywrongpassword"},
        files={"file": ("backup.zip", backup_bytes, "application/zip")},
    )
    assert import_resp.status_code == 422
    assert "password" in import_resp.json()["detail"].lower()


def test_backup_restore_rejects_non_backup_file(client, mock_ami):
    import_resp = client.post(
        "/api/backup/import",
        data={"password": "whatever123"},
        files={"file": ("not-a-backup.zip", b"this is not a zip file at all", "application/zip")},
    )
    assert import_resp.status_code == 422


def test_backup_restore_resolves_custom_provisioning_template_by_name(client, mock_ami):
    """Custom template ids are dropped on export (Phase B.4 design note: a
    fresh instance's re-seeded builtins already occupy low ids) - devices
    must still end up pointing at the right template after restore, matched
    by name rather than the now-meaningless old id."""
    tpl_resp = client.post("/api/provisioning/templates", json={
        "name": "Custom Backup Template", "vendor": "Test",
        "file_pattern": "{mac}.cfg", "content": "auth_name={{sip_username}}\n",
    })
    assert tpl_resp.status_code == 200
    tpl_id = tpl_resp.json()["id"]
    _ensure_extension(client, 47, "Device Owner")
    dev_resp = client.post("/api/provisioning/devices", json={
        "name": "Backup Device", "mac": "aa00bb11cc22",
        "extension_numbers": "47", "template_id": tpl_id,
    })
    assert dev_resp.status_code == 200

    export_resp = client.post("/api/backup/export", data={"password": "correcthorsebattery"})
    backup_bytes = export_resp.content

    import_resp = client.post(
        "/api/backup/import",
        data={"password": "correcthorsebattery"},
        files={"file": ("backup.zip", backup_bytes, "application/zip")},
    )
    assert import_resp.status_code == 200

    devices = client.get("/api/provisioning/devices").json()
    restored = next(d for d in devices if d["mac"] == "aa00bb11cc22")
    templates = client.get("/api/provisioning/templates").json()
    restored_tpl = next(t for t in templates if t["name"] == "Custom Backup Template")
    assert restored["template_id"] == restored_tpl["id"]


# ---- Holidays (Roadmap Phase B.3: Business Hours + Feiertage) ----
# A holiday is a recurring month/day override applied to every TimeCondition:
# on that date, calls go to closed_destination no matter what open_hours/
# open_days say ("klare Regelprioritaet" - holiday always wins).

def test_holiday_crud(client, mock_ami):
    resp = client.post("/api/holidays", json={"name": "Weihnachten", "month": 12, "day": 25})
    assert resp.status_code == 200
    holiday = resp.json()
    assert holiday["month"] == 12
    assert holiday["day"] == 25
    holiday_id = holiday["id"]

    resp = client.get("/api/holidays")
    assert resp.status_code == 200
    assert any(h["id"] == holiday_id for h in resp.json())

    resp = client.patch(f"/api/holidays/{holiday_id}", json={"name": "1. Weihnachtstag"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "1. Weihnachtstag"

    resp = client.delete(f"/api/holidays/{holiday_id}")
    assert resp.status_code == 200
    assert client.get("/api/holidays").json() == []


def test_holiday_rejects_invalid_month_or_day(client):
    resp = client.post("/api/holidays", json={"name": "Bad", "month": 13, "day": 1})
    assert resp.status_code == 422
    resp = client.post("/api/holidays", json={"name": "Bad", "month": 1, "day": 32})
    assert resp.status_code == 422


def test_holiday_takes_priority_over_open_hours_in_dialplan(client, mock_ami, tmp_data_dir):
    """The exact 'klare Regelprioritaet' requirement: the holiday GotoIfTime
    check must render BEFORE the normal open_hours/open_days check, so it
    always wins regardless of what the business hours say."""
    resp = client.post("/api/holidays", json={"name": "Neujahr", "month": 1, "day": 1})
    assert resp.status_code == 200
    holiday_id = resp.json()["id"]

    resp = client.post("/api/time-conditions", json={
        "name": "Hours", "did": "+4977777777",
        "open_hours_start": "00:00", "open_hours_end": "23:59", "open_days": "mon-sun",
        "open_destination": 10, "closed_destination": 10,
    })
    assert resp.status_code == 200
    tc_id = resp.json()["id"]

    try:
        content = (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()
        assert f"exten => +4977777777,1,NoOp(Inbound (time): +4977777777)" in content

        holiday_line = f"GotoIfTime(*|*|1|jan?closed-{tc_id},1,1)"
        hours_line = f"GotoIfTime(00:00-23:59|*|*|mon-sun?open-{tc_id},1,1:closed-{tc_id},1,1)"
        assert holiday_line in content
        assert hours_line in content
        # Order matters: the holiday check must come first in the same extension.
        assert content.index(holiday_line) < content.index(hours_line)
    finally:
        # This holiday would otherwise leak into every other test's generated
        # dialplan (holidays apply globally to every time condition).
        client.delete(f"/api/holidays/{holiday_id}")
        client.delete(f"/api/time-conditions/{tc_id}")


def test_holiday_absent_from_dialplan_when_none_configured(client, mock_ami, tmp_data_dir):
    resp = client.post("/api/time-conditions", json={
        "name": "Hours", "did": "+4988888888",
        "open_hours_start": "09:00", "open_hours_end": "18:00", "open_days": "mon-fri",
        "open_destination": 10, "closed_destination": 10,
    })
    assert resp.status_code == 200
    content = (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()
    assert "GotoIfTime(*|*|" not in content


def test_holiday_included_in_backup_restore(client, mock_ami):
    resp = client.post("/api/holidays", json={"name": "Tag der Arbeit", "month": 5, "day": 1})
    assert resp.status_code == 200
    holiday_id = resp.json()["id"]

    export_resp = client.post("/api/backup/export", data={"password": "correcthorsebattery"})
    assert export_resp.status_code == 200

    client.delete(f"/api/holidays/{holiday_id}")
    assert client.get("/api/holidays").json() == []

    import_resp = client.post(
        "/api/backup/import",
        data={"password": "correcthorsebattery"},
        files={"file": ("backup.zip", export_resp.content, "application/zip")},
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["restored"]["holiday"] == 1

    holidays = client.get("/api/holidays").json()
    assert any(h["name"] == "Tag der Arbeit" and h["month"] == 5 and h["day"] == 1 for h in holidays)


# ---- Phonebook (Roadmap: Telefonbuch mit CSV-Import/Export) ----

def test_phonebook_crud(client):
    resp = client.post("/api/phonebook", json={"name": "Pizza Service", "number": "+4933334444", "notes": "Lieferung"})
    assert resp.status_code == 200
    entry = resp.json()
    assert entry["name"] == "Pizza Service"
    entry_id = entry["id"]

    resp = client.get("/api/phonebook")
    assert resp.status_code == 200
    assert any(e["id"] == entry_id for e in resp.json())

    resp = client.patch(f"/api/phonebook/{entry_id}", json={"notes": "Lieferung + Abholung"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Lieferung + Abholung"

    resp = client.delete(f"/api/phonebook/{entry_id}")
    assert resp.status_code == 200
    assert client.get("/api/phonebook").json() == []


def test_phonebook_requires_name_and_number(client):
    resp = client.post("/api/phonebook", json={"name": "", "number": "+491234"})
    assert resp.status_code == 422
    resp = client.post("/api/phonebook", json={"name": "Nobody", "number": ""})
    assert resp.status_code == 422


def test_phonebook_export_csv(client):
    client.post("/api/phonebook", json={"name": "Taxi Zentrale", "number": "+4933335555", "notes": "24h"})
    resp = client.get("/api/phonebook/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    body = resp.text
    assert "name,number,notes" in body
    assert "Taxi Zentrale,+4933335555,24h" in body


def test_phonebook_import_creates_and_updates(client):
    import io

    csv_content = "name,number,notes\nApotheke,+4933336666,Notdienst\n"
    resp = client.post(
        "/api/phonebook/import",
        files={"file": ("contacts.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["updated"] == 0

    entries = client.get("/api/phonebook").json()
    apotheke = next(e for e in entries if e["number"] == "+4933336666")
    assert apotheke["name"] == "Apotheke"

    # Re-importing the same number with a changed name updates instead of duplicating.
    csv_content_2 = "name,number,notes\nApotheke am Markt,+4933336666,Notdienst 24h\n"
    resp = client.post(
        "/api/phonebook/import",
        files={"file": ("contacts.csv", io.BytesIO(csv_content_2.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 0
    assert body["updated"] == 1

    entries = client.get("/api/phonebook").json()
    matching = [e for e in entries if e["number"] == "+4933336666"]
    assert len(matching) == 1
    assert matching[0]["name"] == "Apotheke am Markt"


def test_phonebook_import_rejects_missing_columns(client):
    import io

    resp = client.post(
        "/api/phonebook/import",
        files={"file": ("bad.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")},
    )
    assert resp.status_code == 422


def test_phonebook_import_skips_rows_missing_required_fields(client):
    import io

    csv_content = "name,number,notes\n,+4900000000,missing name\nValid Entry,+4911112222,ok\n"
    resp = client.post(
        "/api/phonebook/import",
        files={"file": ("contacts.csv", io.BytesIO(csv_content.encode()), "text/csv")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["skipped"] == 1


def test_phonebook_included_in_backup_restore(client):
    resp = client.post("/api/phonebook", json={"name": "Backup Contact", "number": "+4922223333", "notes": ""})
    assert resp.status_code == 200
    entry_id = resp.json()["id"]

    export_resp = client.post("/api/backup/export", data={"password": "correcthorsebattery"})
    assert export_resp.status_code == 200

    client.delete(f"/api/phonebook/{entry_id}")
    assert not any(e["name"] == "Backup Contact" for e in client.get("/api/phonebook").json())

    import_resp = client.post(
        "/api/backup/import",
        data={"password": "correcthorsebattery"},
        files={"file": ("backup.zip", export_resp.content, "application/zip")},
    )
    assert import_resp.status_code == 200
    assert import_resp.json()["restored"]["phonebookentry"] >= 1

    entries = client.get("/api/phonebook").json()
    assert any(e["name"] == "Backup Contact" for e in entries)
