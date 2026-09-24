"""Regression tests for the 0.7.119 audit fixes: config injection, modules/MOH,
multi-device ringing, trunk identify, pjsip_local/TLS transport."""
from pathlib import Path

import pytest

from backend.conf_generator import render_conf
from backend.conf_safety import conf_name, conf_text, strip_line_breaks
from backend.routers.time_conditions import dial_target

ADDON = Path(__file__).resolve().parents[2]
DOCKERFILE = ADDON / "Dockerfile"
MODULES = ADDON / "rootfs/etc/asterisk/modules.conf"


def _routing(tmp_data_dir) -> str:
    return (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()


def _pjsip_ext(tmp_data_dir) -> str:
    return (tmp_data_dir / "asterisk" / "pjsip_extensions.conf").read_text()


def _stanza(content: str, header: str, next_header: str) -> str:
    start = content.index(header)
    return content[start:content.index(next_header, start)]


@pytest.fixture
def ext_factory(client):
    created: list[int] = []

    def make(number: int, **extra):
        resp = client.post("/api/extensions", json={
            "number": number, "display_name": f"Audit {number}",
            "sip_password": "securepass1234567", **extra,
        })
        assert resp.status_code == 200, resp.text
        created.append(resp.json()["id"])
        return resp.json()

    yield make
    for ext_id in created:
        client.delete(f"/api/extensions/{ext_id}")


# ── 2. Config injection ─────────────────────────────────────────────────────

@pytest.mark.parametrize("bad", ["Bob\n[evil]", "Bob\r\ncontext=x", "a\x00b", "tab\there"])
def test_conf_text_rejects_line_breaks_and_control_chars(bad):
    with pytest.raises(ValueError):
        conf_text(bad)


@pytest.mark.parametrize("bad", ["[x]", "a<b>", 'a"b', "a;b", "${SHELL(id)}", "a\\b"])
def test_conf_name_rejects_section_and_callerid_breaking_chars(bad):
    with pytest.raises(ValueError):
        conf_name(bad)


@pytest.mark.parametrize("good", ["Müller, Hans", "Tür-Station (EG)", "Büro 2 / Empfang", "O'Neil"])
def test_conf_name_accepts_normal_names(good):
    assert conf_name(good) == good


def test_finalize_strips_crlf_from_every_rendered_value(tmp_path):
    assert strip_line_breaks("a\r\nb") == "a  b"
    assert strip_line_breaks(5) == 5

    class Ext:  # bypasses all validators, like an old DB row
        number = 10
        display_name = "Bob\n[evil]\ncontext=pwn"
        sip_password = "pw\nx=y"
        enabled = True
        video_capable = False
        internal_only = False
        media_encryption = "none"

    out = tmp_path / "pjsip_extensions.conf"
    render_conf("pjsip_extensions.conf.j2", {"extensions": [Ext()]}, out)
    text = out.read_text()
    assert "\n[evil]" not in text and "\ncontext=pwn" not in text and "\nx=y" not in text
    assert "callerid          = Bob [evil] context=pwn <10>" in text


@pytest.mark.parametrize("field,value", [
    ("display_name", "Evil\n[trunk-endpoint]"),
    ("display_name", "Evil; comment"),
    ("sip_password", "securepass1234567\nallow=all"),
])
def test_extension_api_rejects_injection(client, field, value):
    body = {"number": 58, "display_name": "Ok", "sip_password": "securepass1234567", field: value}
    assert client.post("/api/extensions", json=body).status_code == 422


def test_extension_update_rejects_injection(client, ext_factory):
    ext = ext_factory(25)
    resp = client.patch(f"/api/extensions/{ext['id']}", json={"display_name": "x\ny"})
    assert resp.status_code == 422


@pytest.mark.parametrize("path,body", [
    ("/api/ring-groups", {"number": 0, "name": "RG\n[x]", "extension_numbers": ""}),
    ("/api/ivrs", {"number": 67, "name": "IVR\r\nfoo", "options": "[]"}),
    ("/api/time-conditions", {"name": "TC", "did": "123,1,Hangup()"}),
    ("/api/routes", {"did": "123\n[x]", "destination_type": "hangup"}),
    ("/api/outbound-rules", {"pattern": "0.\nexten=>", "strip": 0, "prepend": ""}),
    ("/api/outbound-rules", {"pattern": "0.", "strip": 0, "prepend": "+35,1"}),
    ("/api/holidays", {"name": "Neujahr\n[x]", "year": 2027, "month": 1, "day": 1}),
])
def test_free_text_fields_reject_injection(client, path, body):
    assert client.post(path, json=body).status_code == 422, path


@pytest.mark.parametrize("field,value", [
    ("registrar_host", "sip.example.com\n[evil]"),
    ("registrar_host", "sip.example.com;transport=tcp"),
    ("auth_username", "123 456"),
    ("phone_number", "0301234\n"),
    ("password", "secret\nmatch=0.0.0.0/0"),
    ("codecs", "ulaw\nallow=all"),
])
def test_trunk_rejects_injection(client, field, value):
    body = {"registrar_host": "sip.example.com", "port": 5060, "auth_username": "123456789",
            "password": "mysecretpassword", "phone_number": "049123456789", "reg_refresh": 60,
            field: value}
    assert client.post("/api/trunk", json=body).status_code == 422


@pytest.mark.parametrize("field,value", [
    ("host", "smtp.example.com\npasswordeval rm -rf /"),
    ("username", "user\nauth off"),
    ("password", "pw\ntls off"),
    ("from_addr", "a@b.c\nlogfile /etc/passwd"),
    ("from_name", "HA\nmailcmd=/bin/sh"),
])
def test_smtp_rejects_injection(client, field, value):
    body = {"host": "smtp.example.com", "port": 587, "encryption": "starttls",
            "username": "u", "password": "p", "from_addr": "a@b.c", "from_name": "HA",
            "enabled": True, field: value}
    assert client.post("/api/settings/smtp", json=body).status_code == 422


def test_voicemail_mailbox_line_survives_comma_in_display_name(client, tmp_data_dir, ext_factory):
    ext_factory(26, display_name="Müller, Hans")
    vm = (tmp_data_dir / "asterisk" / "voicemail_mailboxes.conf").read_text() \
        if (tmp_data_dir / "asterisk" / "voicemail_mailboxes.conf").exists() else None
    if vm is None:  # file name differs per install layout — find the rendered one
        vm = "".join(p.read_text() for p in (tmp_data_dir / "asterisk").glob("voicemail*.conf"))
    assert "26 => 26,Müller  Hans," in vm


# ── 3. Modules + MOH ────────────────────────────────────────────────────────

@pytest.mark.parametrize("module", [
    "res_pjsip_caller_id", "res_pjsip_nat", "res_pjsip_refer", "res_pjsip_mwi",
    "res_pjsip_mwi_body_generator", "res_format_attr_h264", "func_timeout", "res_musiconhold",
])
def test_module_is_built_and_loaded(module):
    assert f"--enable {module} " in DOCKERFILE.read_text() or \
        f"--enable {module}\n" in DOCKERFILE.read_text()
    assert f"load = {module}.so" in MODULES.read_text()


def test_every_loaded_module_is_enabled_in_menuselect():
    """autoload=no + --disable-all: a load line without --enable fails at boot."""
    docker = DOCKERFILE.read_text()
    for line in MODULES.read_text().splitlines():
        if line.startswith("load = "):
            mod = line.split("=", 1)[1].strip().removesuffix(".so")
            assert f"--enable {mod} " in docker or f"--enable {mod}\n" in docker, mod


def test_musiconhold_conf_points_at_installed_moh_files():
    moh = (ADDON / "rootfs/etc/asterisk/musiconhold.conf").read_text()
    assert "[default]" in moh and "mode      = files" in moh
    # MOH-OPSOUND-WAV installs to /opt/asterisk/var/lib/asterisk/moh (DESTDIR) -> /var/lib/asterisk/moh
    assert "directory = /var/lib/asterisk/moh" in moh
    assert "--enable MOH-OPSOUND-WAV" in DOCKERFILE.read_text()
    assert "astdatadir   => /var/lib/asterisk" in (ADDON / "rootfs/etc/asterisk/asterisk.conf").read_text()


def test_extension_endpoint_has_mwi_mailbox(client, tmp_data_dir, ext_factory):
    ext_factory(27)
    stanza = _stanza(_pjsip_ext(tmp_data_dir), "[27]\ntype              = endpoint", "[27-auth]")
    assert "mailboxes         = 27@default" in stanza


# ── 5. Multi-device ringing ─────────────────────────────────────────────────

def test_dial_target_rings_all_contacts_with_fallback():
    target = dial_target(12)
    assert target == "${IF($[${LEN(${PJSIP_DIAL_CONTACTS(12)})} = 0]?PJSIP/12:${PJSIP_DIAL_CONTACTS(12)})}"
    # video extensions keep the verified single-contact path
    assert dial_target(12, {"12"}) == "PJSIP/12"


def test_aor_contacts_non_video_vs_video(client, tmp_data_dir, ext_factory):
    ext_factory(28)
    ext_factory(29, video_capable=True)
    content = _pjsip_ext(tmp_data_dir)
    aor28 = _stanza(content, "[28]\ntype              = aor", "; ---")
    assert "max_contacts      = 3" in aor28
    assert "remove_existing   = yes" in aor28 and "remove_unavailable = yes" in aor28
    aor29 = content[content.index("[29]\ntype              = aor"):]
    aor29 = aor29.split("; ---")[0]
    assert "max_contacts      = 1" in aor29 and "remove_existing   = yes" in aor29
    assert "remove_unavailable" not in aor29


def test_dialplan_uses_dial_contacts_except_for_video(client, tmp_data_dir, ext_factory):
    ext_factory(33)
    ext_factory(34, video_capable=True)
    resp = client.post("/api/ring-groups", json={
        "number": 78, "name": "Audit RG", "extension_numbers": "33,34", "ring_timeout": 20})
    assert resp.status_code == 200, resp.text
    try:
        routing = _routing(tmp_data_dir)
        landing33 = routing.split("[ext-33]")[1].split("\n[")[0]
        landing34 = routing.split("[ext-34]")[1].split("\n[")[0]
        assert f"Dial({dial_target(33)},30)" in landing33
        assert "Dial(PJSIP/34,30)" in landing34 and "PJSIP_DIAL_CONTACTS" not in landing34
        assert f"{dial_target(33)}&PJSIP/34" in routing
        restricted = routing.split("[from-internal-restricted]")[1].split("\n[")[0]
        assert f"exten => 33,1,NoOp(Internal-only call to 33)\n same => n,Dial({dial_target(33)},30)" in restricted
        assert "exten => 34,1," not in restricted  # video callee keeps the _XX PJSIP/${EXTEN} path
        assert " same => n,Dial(PJSIP/${EXTEN},30)" in restricted
    finally:
        client.delete(f"/api/ring-groups/{resp.json()['id']}")


# ── 4. Outbound sanitising ──────────────────────────────────────────────────

def test_outbound_dial_filters_exten(client, tmp_data_dir):
    routing = _routing(tmp_data_dir)
    pstn = routing.split("[outbound-pstn]")[1].split("[from-trunk]")[0]
    assert "PJSIP/${FILTER(0-9+,${EXTEN})}@trunk-endpoint" in pstn
    assert "Dial(PJSIP/${EXTEN}@" not in pstn


# ── 6. Trunk identify ───────────────────────────────────────────────────────

def test_trunk_endpoint_identified_by_ip_only(client, tmp_data_dir):
    resp = client.post("/api/trunk", json={
        "registrar_host": "sip.example.com", "domain": "voip.example.com", "port": 5060,
        "auth_username": "123456789", "password": "mysecretpassword",
        "phone_number": "049123456789", "reg_refresh": 60})
    assert resp.status_code == 200, resp.text
    conf = (tmp_data_dir / "asterisk" / "pjsip_trunk.conf").read_text()
    endpoint = _stanza(conf, "[trunk-endpoint]", "[trunk-identify]")
    assert "identify_by = ip" in endpoint
    identify = conf[conf.index("[trunk-identify]"):]
    assert "endpoint = trunk-endpoint" in identify
    assert "match = sip.example.com" in identify and "match = voip.example.com" in identify


# ── 8. pjsip_local / TLS transport ──────────────────────────────────────────

@pytest.fixture
def tls_cert(tmp_data_dir):
    tls = tmp_data_dir / "asterisk" / "tls"
    tls.mkdir(parents=True, exist_ok=True)
    (tls / "asterisk.crt").write_text("CERT")
    (tls / "asterisk.key").write_text("KEY")
    yield tls
    (tls / "asterisk.crt").unlink()
    (tls / "asterisk.key").unlink()


def _local(tmp_data_dir) -> str:
    return (tmp_data_dir / "asterisk" / "pjsip_local.conf").read_text()


def test_public_ip_save_keeps_transport_tls(client, tmp_data_dir, tls_cert):
    assert client.post("/api/settings/public-ip", json={"ip": "1.2.3.4"}).status_code == 200
    text = _local(tmp_data_dir)
    tls = text[text.index("[transport-tls]"):]
    assert "protocol   = tls" in tls and "bind       = 0.0.0.0:5061" in tls
    assert "external_signaling_address = 1.2.3.4" in tls
    assert "local_net                  = 192.168.0.0/16" in tls
    udp = _stanza(text, "[transport-udp](+)", "[transport-tls]")
    assert "external_media_address     = 1.2.3.4" in udp


def test_ipv6_external_address_only_on_ipv6_transport(tmp_data_dir, tls_cert):
    from backend.pjsip_local import write_pjsip_local
    write_pjsip_local("2a00:1234::5")
    text = _local(tmp_data_dir)
    udp4 = _stanza(text, "[transport-udp](+)", "[transport-udp-ipv6](+)")
    assert "external_signaling_address =" not in udp4 and "local_net" in udp4
    udp6 = _stanza(text, "[transport-udp-ipv6](+)", "[transport-tls]")
    assert "external_signaling_address = 2a00:1234::5" in udp6
    assert "external_signaling_address =" not in text[text.index("[transport-tls]"):]


def test_pjsip_local_without_ip_or_cert_is_lan_only(tmp_data_dir):
    from backend.pjsip_local import write_pjsip_local
    write_pjsip_local("")
    text = _local(tmp_data_dir)
    assert "LAN-only" in text and "external_signaling_address =" not in text
    assert "[transport-tls]" not in text


def test_public_ip_rejects_non_ip(client):
    assert client.post("/api/settings/public-ip", json={"ip": "1.2.3.4\n[x]"}).status_code == 422
    assert client.post("/api/settings/public-ip", json={"ip": "evil.example.com"}).status_code == 422


def test_macro_output_keeps_its_newlines(client, tmp_data_dir, ext_factory):
    """finalize strips CR/LF from values - but a multi-line macro (dest_action) must survive."""
    ext = ext_factory(35)
    resp = client.post("/api/presence-rules", json={
        "extension_id": ext["id"], "status": "available", "direction": "internal",
        "mode": "always_dest", "dest_type": "voicemail", "dest_target": 35})
    assert resp.status_code in (200, 201), resp.text
    rule_id = resp.json()["id"]
    landing = _routing(tmp_data_dir).split("[ext-35]")[1].split("\n[")[0]
    client.delete(f"/api/presence-rules/{rule_id}")
    assert "\n same => n,Voicemail(35@default,u)\n same => n,Hangup()" in landing
