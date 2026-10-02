"""Fanvil V65 has 9 DSS keys: builtin template, upgrade of existing templates, rendering."""
from sqlmodel import Session, select

from backend.database import get_engine
from backend.models import ProvisioningTemplate
from backend.routers import provisioning as prov

SIX_KEY_TAIL = "Memory DSS Key6 Label :{{fanvil_dss6_label | default('')}}\n"


def _v65():
    return next(t for t in prov.BUILTIN_TEMPLATES if t["name"] == prov._FANVIL_V65_FULL_NAME)["content"]


def test_builtin_v65_template_has_nine_keys():
    content = _v65()
    for n in range(1, 10):
        assert f"Memory DSS Key{n} Type :{{{{fanvil_dss{n}_type | default('0')}}}}" in content
        assert f"Memory DSS Key{n} Label :{{{{fanvil_dss{n}_label | default('')}}}}" in content
    assert "Memory DSS Key10" not in content


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


def test_key9_renders_with_device_values():
    out = prov._render(_v65(), {"fanvil_dss9_type": "2", "fanvil_dss9_value": "19", "fanvil_dss9_label": "Indoorview",
                                "fanvil_dss9_pickup": "**19", "fanvil_dss9_line": "1"})
    assert "Memory DSS Key9 Type :2" in out and "Memory DSS Key9 Label :Indoorview" in out


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
