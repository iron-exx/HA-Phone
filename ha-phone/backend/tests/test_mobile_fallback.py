"""Rückfall auf die Handynummer: when none of an extension's devices is registered or
reachable (no contacts / CHANUNAVAIL), the PBX calls the extension's own mobile number
over the trunk instead of going straight to voicemail. Off unless a number is set."""
import pytest


@pytest.fixture
def ext_factory(client):
    created: list[int] = []

    def make(number: int, **extra):
        resp = client.post("/api/extensions", json={
            "number": number, "display_name": f"Fallback {number}",
            "sip_password": "securepass1234567", **extra,
        })
        assert resp.status_code == 200, resp.text
        created.append(resp.json()["id"])
        return resp.json()

    yield make
    for ext_id in created:
        client.delete(f"/api/extensions/{ext_id}")


def _landing(tmp_data_dir, number: int) -> str:
    routing = (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()
    return routing.split(f"[ext-{number}]")[1].split("\n[")[0]


def test_no_fallback_by_default(client, tmp_data_dir, ext_factory):
    ext = ext_factory(36)
    assert ext["mobile_fallback"] == ""
    assert "mobile" not in _landing(tmp_data_dir, 36)


def test_fallback_dials_mobile_in_e164_when_no_device_reachable(client, tmp_data_dir, ext_factory):
    ext = ext_factory(37)
    resp = client.patch(f"/api/extensions/{ext['id']}", json={"mobile_fallback": "0171 555-1234"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["mobile_fallback"] == "0171 555-1234"
    landing = _landing(tmp_data_dir, 37)
    for direction in ("internal", "external"):
        block = landing.split(f"exten => {direction},1")[1].split("exten =>")[0]
        # Nothing registered: skip the (failing) Dial and go to the mobile right away.
        assert "GotoIf($[${LEN(${PJSIP_DIAL_CONTACTS(37)})} = 0]?mobile)" in block
        assert 'GotoIf($["${DIALSTATUS}" = "CHANUNAVAIL"]?mobile)' in block
        assert "n(mobile),NoOp(" in block
        assert "Dial(Local/+491715551234@outbound-pstn/n,30)" in block
        # The trunk CLIP must survive into the Local channel.
        assert "Set(__OUTBOUND_CID=" in block
        # Mobile did not answer either: our own voicemail as before.
        assert block.rstrip().endswith("same => n,Hangup()")
        assert "Voicemail(37@default,u)" in block.split("n(mobile)")[1]


def test_clearing_the_number_turns_it_off(client, tmp_data_dir, ext_factory):
    ext = ext_factory(38, mobile_fallback="+49 171 5551234")
    assert "Local/+491715551234@outbound-pstn" in _landing(tmp_data_dir, 38)
    client.patch(f"/api/extensions/{ext['id']}", json={"mobile_fallback": ""})
    assert "mobile" not in _landing(tmp_data_dir, 38)


@pytest.mark.parametrize("bad", ["abc", "0171;Dial(PJSIP/1)", "0171,1", "12", "+" + "1" * 30])
def test_rejects_non_phone_numbers(client, ext_factory, bad):
    ext = ext_factory(39)
    resp = client.patch(f"/api/extensions/{ext['id']}", json={"mobile_fallback": bad})
    assert resp.status_code == 422, resp.text
