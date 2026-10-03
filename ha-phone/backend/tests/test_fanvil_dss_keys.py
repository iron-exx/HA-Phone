"""Fanvil V65: verified config format, 9 DSS keys, upgrade of existing templates, rendering."""
from sqlmodel import Session, select

from backend.database import get_engine
from backend.models import ProvisioningTemplate
from backend.routers import provisioning as prov

SIX_KEY_TAIL = "Memory DSS Key6 Label :{{fanvil_dss6_label | default('')}}\n"


def _v65():
    return next(t for t in prov.BUILTIN_TEMPLATES if t["name"] == prov._FANVIL_V65_FULL_NAME)["content"]


def _device_cfg(extra, accounts=None):
    accounts = accounts or [{"number": "14", "display_name": "Büro", "sip_username": "14", "sip_auth": "14",
                             "sip_password": "geheim", "label": "Büro"}]
    subs = {"accounts": accounts, "sip_server": "192.168.7.10", "sip_port": "5060"}
    subs.update(prov._fanvil_vars(extra))
    subs.update(extra)
    return prov._fanvil_cfg_normalize(prov._render(_v65(), subs))


def test_v65_file_has_the_frame_the_phone_requires():
    out = _device_cfg({})
    header = out.split("\r\n")[0]
    assert header.startswith("<<VOIP CONFIG FILE>>Version:2.0000000000")
    assert len(header) + 2 == 64
    assert out.endswith("<<END OF FILE>>\r\n")
    assert "\n" not in out.replace("\r\n", "")


def test_v65_uses_the_key_names_of_the_phones_own_export():
    out = _device_cfg({})
    for line in ("SIP1 Phone Number       :14", "SIP1 Register Addr      :192.168.7.10",
                 "SIP1 Register User      :14", "SIP1 Register Pswd      :geheim", "SIP1 Enable Reg         :1",
                 "SIP1 Proxy Addr         :192.168.7.10", "Default Language   :de", "--Sidekey Config1--:"):
        assert line + "\r\n" in out
    for invented in ("Register Enable", "PREFERENCE", "Memory DSS"):
        assert invented not in out


def test_v65_keys_map_to_fanvil_memory_and_line_keys():
    out = _device_cfg({"fanvil_dss1_type": "1", "fanvil_dss1_value": "+49 525 2448013", "fanvil_dss1_label": "Larissa",
                       "fanvil_dss2_type": "2", "fanvil_dss2_value": "19", "fanvil_dss2_label": "Tür",
                       "fanvil_dss3_type": "line", "fanvil_dss3_line": "2",
                       "fanvil_dss4_type": "1", "fanvil_dss4_value": "",
                       "fanvil_dss9_type": "16", "fanvil_dss9_value": "700"})
    assert "Fkey1 Type               :1\r\nFkey1 Value              :+495252448013@1/f\r\n" in out
    assert "Fkey1 Title              :Larissa\r\n" in out
    assert "Fkey2 Value              :19@1/bc\r\n" in out
    assert "Fkey3 Type               :2\r\nFkey3 Value              :SIP2\r\n" in out
    assert "Fkey4 Type               :0\r\n" in out  # speed dial without number = empty
    assert "Fkey9 Value              :700@1/c\r\n" in out
    assert "Fkey10" not in out


def test_v65_provisions_every_assigned_extension_as_a_line():
    accounts = [{"number": n, "display_name": f"N{n}", "sip_username": n, "sip_auth": n, "sip_password": "pw",
                 "label": f"N{n}"} for n in ("14", "15")]
    out = _device_cfg({}, accounts)
    assert "SIP2 Phone Number       :15\r\n" in out and "SIP2 Enable Reg         :1\r\n" in out


def test_shipped_fanvil_v65_revisions_are_upgraded_even_when_renamed(client):
    with Session(get_engine()) as s:
        rows = [ProvisioningTemplate(name=f"Fanvil V65 (angepasst {i})", vendor="Fanvil", file_pattern="{mac}.cfg",
                                     content=old, builtin=True)
                for i, old in enumerate(prov._FANVIL_V65_MEMORY_DSS_CONTENTS)]
        edited = ProvisioningTemplate(name="Fanvil V65 eigene", vendor="Fanvil", file_pattern="{mac}.cfg",
                                      content=prov._FANVIL_V65_MEMORY_DSS_CONTENTS[1] + "## eigene Zeile\n")
        for r in [*rows, edited]:
            s.add(r)
        s.commit()
        assert prov.repair_broken_builtin_templates(s) is True
        for r in [*rows, edited]:
            s.refresh(r)
        assert all(r.content == _v65() for r in rows)
        assert edited.content.endswith("## eigene Zeile\n")
        for r in [*rows, edited]:
            s.delete(r)
        s.commit()


def test_existing_six_key_templates_get_keys_7_to_9_and_keep_user_edits(client):
    old = prov.fanvil_dss_lines(range(1, 7))
    edited = "## meine Notiz\nSIP1 Display Name :{{display_name}}\n<DSSKEY MODULE>\n" + old + "## danach\n"
    with Session(get_engine()) as s:
        tpl = ProvisioningTemplate(name="Fanvil V65 (Test angepasst)", vendor="Fanvil", file_pattern="{mac}.cfg",
                                   content=edited, builtin=False)
        s.add(tpl)
        s.commit()
        assert prov.extend_fanvil_dss_keys(s) is True
        s.refresh(tpl)
        assert "## meine Notiz" in tpl.content and tpl.content.endswith("## danach\n")
        assert "Memory DSS Key9 Label :{{fanvil_dss9_label | default('')}}" in tpl.content
        # Key 7 follows directly after key 6, in order.
        assert tpl.content.index("Memory DSS Key7 Type") > tpl.content.index(SIX_KEY_TAIL)
        # Idempotent.
        before = tpl.content
        prov.extend_fanvil_dss_keys(s)
        s.refresh(tpl)
        assert tpl.content == before
        s.delete(tpl)
        s.commit()


def test_templates_without_the_standard_block_are_not_touched(client):
    with Session(get_engine()) as s:
        others = {t.id: t.content for t in s.exec(select(ProvisioningTemplate)).all() if SIX_KEY_TAIL not in t.content}
        prov.extend_fanvil_dss_keys(s)
        for t in s.exec(select(ProvisioningTemplate)).all():
            if t.id in others:
                assert t.content == others[t.id]


def test_extensions_are_listed_by_number(client):
    created = []
    for n in (58, 51, 55):
        r = client.post("/api/extensions", json={"number": n, "display_name": f"S{n}", "sip_password": "securepass1234567"})
        if r.status_code == 200:
            created.append(r.json()["id"])
    numbers = [e["number"] for e in client.get("/api/extensions").json()]
    assert numbers == sorted(numbers)
    for i in created:
        client.delete(f"/api/extensions/{i}")


def test_v65_door_preview_uses_early_media_not_background_answer():
    out = _device_cfg({})
    assert "SIP1 Enable Preview     :1\r\n" in out
    assert "SIP1 Preview Mode       :0\r\n" in out  # 1 = "2XX" answers and cancels the other devices
    assert "SIP1 Enable Deal 180    :1\r\n" in out
    assert "Notify Reboot      :1\r\n" in out
    assert "SIP1 Enable Preview     :0\r\n" in _device_cfg({"fanvil_early_media": "0"})


def test_0_7_152_fanvil_templates_are_upgraded(client):
    old = prov._fanvil_v65_content(prov._FANVIL_SIP_LINES_0_7_152)
    with Session(get_engine()) as s:
        tpl = ProvisioningTemplate(name="Fanvil V65 (angepasst)", vendor="Fanvil", file_pattern="{mac}.cfg",
                                   content=old, builtin=True)
        s.add(tpl)
        s.commit()
        prov.repair_broken_builtin_templates(s)
        s.refresh(tpl)
        assert tpl.content == _v65()
        s.delete(tpl)
        s.commit()


def test_resync_sends_check_sync_to_every_extension_of_the_device(client, monkeypatch):
    sent = []

    async def fake_send(number):
        sent.append(number)

    monkeypatch.setattr(prov.ami, "send_check_sync", fake_send)
    ext = client.post("/api/extensions", json={"number": 63, "display_name": "Tisch", "sip_password": "securepass1234567"})
    assert ext.status_code == 200, ext.text
    tpl_id = client.post("/api/provisioning/templates", json={"name": "Resync-Test", "vendor": "Fanvil",
                                                              "file_pattern": "{mac}.cfg", "content": "x"}).json()["id"]
    dev = client.post("/api/provisioning/devices", json={"mac": "0c:38:3e:00:00:63", "extension_numbers": "63",
                                                         "template_id": tpl_id})
    assert dev.status_code == 200, dev.text
    dev = dev.json()
    r = client.post(f"/api/provisioning/devices/{dev['id']}/resync")
    assert r.status_code == 200 and sent == ["63"]
    assert client.post("/api/provisioning/devices/99999/resync").status_code == 404
    client.delete(f"/api/provisioning/devices/{dev['id']}")
    client.delete(f"/api/extensions/{ext.json()['id']}")
    client.delete(f"/api/provisioning/templates/{tpl_id}")


def test_check_sync_notify_action():
    from backend import ami
    assert ami.check_sync_notify("14") == {"Action": "PJSIPNotify", "Endpoint": "14",
                                           "Variable": "Event=check-sync;reboot=true"}
