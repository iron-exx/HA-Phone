"""Test call rings exactly the requesting app: its Contact carries ;haphone-dev=<device id>
(app 1.6.3+); [haphone-testcall-target] picks that contact from PJSIP_DIAL_CONTACTS."""
from backend import ami


def test_originate_goes_through_the_target_context_with_the_device():
    a = ami.test_call_originate("11", device_id=17)
    assert a["Channel"] == "Local/11@haphone-testcall-target/n"
    assert a["Context"] == "haphone-testcall"
    assert a["Variable"] == "__HAPHONE_DEV=17"


def test_originate_without_device_has_no_variable():
    assert "Variable" not in ami.test_call_originate("11")


def test_target_context_filters_the_app_contact(client, tmp_data_dir):
    client.post("/api/extensions", json={"number": 45, "display_name": "T", "sip_password": "securepass1234567"})
    routing = (tmp_data_dir / "asterisk" / "extensions_routing.conf").read_text()
    ctx = routing.split("[haphone-testcall-target]")[1].split("\n[")[0]
    assert "PJSIP_DIAL_CONTACTS(${EXTEN})" in ctx
    assert 'REGEX("haphone-dev=${HAPHONE_DEV}([^0-9]|$)" ${ITEM})' in ctx
    assert "Dial(${IF($[\"${TARGET}\" = \"\"]?PJSIP/${EXTEN}:${TARGET})},30)" in ctx
    # A ';' would start a comment in extensions.conf and cut the line.
    body = [l for l in ctx.splitlines() if not l.startswith(";")]
    assert not any(";" in l for l in body)
