"""Test call rings exactly the requesting app: its Contact carries ;haphone-dev=<device id>
(app 1.6.3+), the PBX finds it via PJSIP_AOR/PJSIP_CONTACT and dials that URI."""
import asyncio

from backend import ami


def test_pick_contact_by_device_id():
    uris = [
        "sip:11@192.168.7.21:5060",
        "sip:11@192.168.178.22:49660;transport=TLS;ob;haphone-dev=17",
        "sip:11@100.111.167.107:40000;transport=TLS;ob;haphone-dev=170",
    ]
    assert ami.pick_device_contact(uris, 17) == uris[1]
    assert ami.pick_device_contact(uris, 170) == uris[2]
    assert ami.pick_device_contact(uris, 5) == ""
    assert ami.pick_device_contact([], 17) == ""


def test_channel_targets_the_contact_or_falls_back():
    assert ami.test_call_channel("11", "sip:11@1.2.3.4:5;transport=TLS;haphone-dev=17") == \
        "PJSIP/11/sip:11@1.2.3.4:5;transport=TLS;haphone-dev=17"
    assert ami.test_call_channel("11", "") == "PJSIP/11"


class _FakeManager:
    def __init__(self, values):
        self.values = values
        self.sent = []

    async def send_action(self, action, as_list=False):
        self.sent.append(action)
        if action["Action"] == "Getvar":
            return {"Response": "Success", "Value": self.values.get(action["Variable"], "")}
        return {"Response": "Success"}


def test_originate_uses_the_device_contact(monkeypatch):
    fake = _FakeManager({
        "PJSIP_AOR(11,contact)": "11;@aaa,11;@bbb",
        "PJSIP_CONTACT(11;@aaa,uri)": "sip:11@192.168.7.21:5060",
        "PJSIP_CONTACT(11;@bbb,uri)": "sip:11@192.168.178.22:49660;transport=TLS;ob;haphone-dev=17",
    })

    async def _mgr():
        return fake

    monkeypatch.setattr(ami, "_get_manager", _mgr)
    asyncio.run(ami.originate_test_call("11", device_id=17))
    originate = [a for a in fake.sent if a["Action"] == "Originate"][0]
    assert originate["Channel"] == "PJSIP/11/sip:11@192.168.178.22:49660;transport=TLS;ob;haphone-dev=17"


def test_originate_without_match_rings_the_extension(monkeypatch):
    fake = _FakeManager({"PJSIP_AOR(11,contact)": ""})

    async def _mgr():
        return fake

    monkeypatch.setattr(ami, "_get_manager", _mgr)
    asyncio.run(ami.originate_test_call("11", device_id=17))
    originate = [a for a in fake.sent if a["Action"] == "Originate"][0]
    assert originate["Channel"] == "PJSIP/11"
