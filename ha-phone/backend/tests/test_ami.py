"""Directly exercises ami.py's own response-parsing logic, which the rest of
the test suite always mocks away at the router level (conftest.py's mock_ami
patches get_extension_diagnostics wholesale). That hid a real bug: an
extension with more than one registered contact (e.g. a DECT base AND a
softphone both on the same extension) had each new contact silently
overwrite the previous one, so only the last-processed contact ever showed
up anywhere in the UI."""

from unittest.mock import AsyncMock, patch

import pytest

import backend.ami as ami


def _endpoint_list(number: str, contacts: int) -> dict:
    return {
        "Event": "EndpointList",
        "ObjectName": number,
        "DeviceState": "Not in use",
        "ActiveChannels": "0",
        "Aor": number,
        "Contacts": str(contacts),
    }


def _contact_list(number: str, uri: str, user_agent: str, status: str = "Reachable") -> dict:
    return {
        "Event": "ContactList",
        "EndpointName": number,
        "Status": status,
        "URI": uri,
        "UserAgent": user_agent,
        "RoundtripUsec": "1234",
    }


@pytest.mark.asyncio
async def test_get_extension_diagnostics_keeps_every_contact():
    fake_manager = AsyncMock()
    fake_manager.send_action.side_effect = [
        [_endpoint_list("11", contacts=2)],
        [
            _contact_list("11", "sip:11@192.168.7.217:5060", "MicroSIP"),
            _contact_list("11", "sip:11@192.168.7.241:45908", "Gigaset"),
        ],
    ]
    with patch("backend.ami._get_manager", new=AsyncMock(return_value=fake_manager)):
        result = await ami.get_extension_diagnostics()

    assert len(result) == 1
    ext = result[0]
    assert ext["contacts"] == 2
    assert len(ext["contacts_detail"]) == 2
    user_agents = {c["user_agent"] for c in ext["contacts_detail"]}
    assert user_agents == {"MicroSIP", "Gigaset"}
    # Backward-compat singular fields still point at the first contact seen.
    assert ext["user_agent"] == "MicroSIP"
    assert ext["contact_uri"] == "sip:11@192.168.7.217:5060"


@pytest.mark.asyncio
async def test_get_extension_diagnostics_handles_single_contact():
    fake_manager = AsyncMock()
    fake_manager.send_action.side_effect = [
        [_endpoint_list("12", contacts=1)],
        [_contact_list("12", "sip:12@192.168.7.99:5060", "Linphone")],
    ]
    with patch("backend.ami._get_manager", new=AsyncMock(return_value=fake_manager)):
        result = await ami.get_extension_diagnostics()

    assert result[0]["contacts_detail"] == [
        {"status": "Reachable", "uri": "sip:12@192.168.7.99:5060", "roundtrip_usec": 1234, "user_agent": "Linphone"}
    ]


@pytest.mark.asyncio
async def test_get_extension_diagnostics_handles_zero_contacts():
    fake_manager = AsyncMock()
    fake_manager.send_action.side_effect = [
        [_endpoint_list("13", contacts=0)],
        [],
    ]
    with patch("backend.ami._get_manager", new=AsyncMock(return_value=fake_manager)):
        result = await ami.get_extension_diagnostics()

    assert result[0]["contacts"] == 0
    assert result[0]["contacts_detail"] == []
    assert result[0]["status"] == "Online"  # DeviceState "Not in use" - still registered-capable


@pytest.mark.asyncio
async def test_get_extension_diagnostics_survives_non_numeric_contacts_field():
    """Reported bug: some Asterisk versions put the actual comma-separated
    contact list in PJSIPShowEndpoints's 'Contacts' field instead of a plain
    count (e.g. '11/sip:11@192.168.7.217:58004;ob,'). int() on that used to
    raise ValueError and silently killed the entire diagnostics response
    (every call returned []), which is also why IP addresses never showed
    up in the UI - this must degrade to a best-effort count instead."""
    endpoint = _endpoint_list("11", contacts=0)
    endpoint["Contacts"] = "11/sip:11@192.168.7.217:58004;ob,"
    fake_manager = AsyncMock()
    fake_manager.send_action.side_effect = [
        [endpoint],
        [_contact_list("11", "sip:11@192.168.7.217:58004;ob", "MicroSIP")],
    ]
    with patch("backend.ami._get_manager", new=AsyncMock(return_value=fake_manager)):
        result = await ami.get_extension_diagnostics()

    assert len(result) == 1
    assert result[0]["contacts"] == 1
