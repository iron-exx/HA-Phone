import asyncio
import logging
import os
from pathlib import Path
from panoramisk import Manager

_log = logging.getLogger(__name__)

_manager: Manager | None = None
_manager_lock = asyncio.Lock()


def _read_ami_secret() -> str:
    data_dir = os.environ.get("BPX_DATA_DIR", "")
    secret_path = (
        Path(data_dir) / "asterisk" / "ami_secret"
        if data_dir
        else Path("/data/asterisk/ami_secret")
    )
    if secret_path.exists():
        return secret_path.read_text().strip()
    return "changeme"


async def _get_manager() -> Manager:
    global _manager
    async with _manager_lock:
        if _manager is not None and _manager.authenticated:
            try:
                await asyncio.wait_for(
                    _manager.send_action({"Action": "Ping"}), timeout=3.0
                )
                return _manager
            except Exception:
                _log.info("AMI: stale connection, reconnecting")
                try:
                    _manager.close()
                except Exception:
                    pass
                _manager = None

        secret = _read_ami_secret()
        _log.info("AMI: connecting to 127.0.0.1:5038 user=bpx-admin")

        manager = Manager(
            host="127.0.0.1",
            port=5038,
            username="bpx-admin",
            secret=secret,
        )
        await manager.connect()

        try:
            if manager.authenticated_future is not None:
                await asyncio.wait_for(manager.authenticated_future, timeout=5.0)
        except asyncio.TimeoutError:
            _log.error("AMI: Login timed out")
            manager.close()
            raise

        if not manager.authenticated:
            manager.close()
            raise RuntimeError("AMI Login failed — check manager.conf secret matches /data/asterisk/ami_secret")

        _log.info("AMI: connected and authenticated")
        _manager = manager
        return manager


_AMI_TIMEOUT = 8


async def _ami_cli(command: str) -> None:
    """Run an Asterisk CLI command via the AMI 'Command' action.

    panoramisk's Manager has NO send_command() method — only send_action().
    The previous code called send_command(), which raised AttributeError on
    every reload, got swallowed, and meant Asterisk NEVER reloaded live: new
    extensions/trunk edits only took effect on a full add-on restart.
    """
    manager = await _get_manager()
    # NOTE: no as_list=True here. A CLI 'Command' action replies with a single
    # "Response: Follows ... --END COMMAND--" block, not a multi-event list; waiting
    # for a list terminator makes panoramisk block until the timeout fires (which
    # surfaced as an empty-message "AMI reload skipped:" — an asyncio.TimeoutError).
    await manager.send_action({"Action": "Command", "Command": command})


async def ami_reload_pjsip() -> None:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            await _ami_cli("module reload res_pjsip.so")
    except Exception as exc:
        _log.warning("AMI pjsip reload skipped: %s", exc)


async def ami_reload_dialplan() -> None:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            await _ami_cli("dialplan reload")
    except Exception as exc:
        _log.warning("AMI dialplan reload skipped: %s", exc)


async def ami_reload_voicemail() -> None:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            await _ami_cli("module reload app_voicemail.so")
    except Exception as exc:
        _log.warning("AMI voicemail reload skipped: %s", exc)


async def get_trunk_status() -> str:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            manager = await _get_manager()
            responses = await manager.send_action(
                {"Action": "PJSIPShowRegistrationsOutbound"}, as_list=True
            )
        for r in responses:
            if r.get("Event") == "OutboundRegistrationDetail":
                return r.get("Status", "UNKNOWN")
        return "UNKNOWN"
    except Exception as exc:
        _log.warning("AMI trunk status unavailable: %s", exc)
        return "UNKNOWN"


async def get_trunk_debug() -> dict:
    """Return full OutboundRegistrationDetail fields for diagnosis."""
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            manager = await _get_manager()
            responses = await manager.send_action(
                {"Action": "PJSIPShowRegistrationsOutbound"}, as_list=True
            )
        for r in responses:
            if r.get("Event") == "OutboundRegistrationDetail":
                return dict(r)
        return {"error": "no OutboundRegistrationDetail received", "raw": [dict(r) for r in responses]}
    except Exception as exc:
        _log.warning("AMI trunk debug unavailable: %s", exc)
        return {"error": str(exc)}


async def get_extension_statuses() -> list[dict]:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            manager = await _get_manager()
            responses = await manager.send_action(
                {"Action": "PJSIPShowEndpoints"}, as_list=True
            )
        result = []
        for r in responses:
            if r.get("Event") == "EndpointList":
                name = r.get("ObjectName", "")
                # Exclude the SIP trunk endpoint ("trunk-endpoint") — it is a PJSIP
                # endpoint too, so once the trunk registers it would otherwise be
                # counted as an "online extension" (Dashboard showed 2 for 1 ext).
                # Real extensions are always numeric.
                if not name.isdigit():
                    continue
                result.append(
                    {
                        "number": name,
                        "status": (
                            "Online"
                            if r.get("DeviceState", "") == "Not in use"
                            else "Offline"
                        ),
                    }
                )
        return result
    except Exception as exc:
        _log.warning("AMI extension statuses unavailable: %s", exc)
        return []


def _parse_contacts_count(raw) -> int:
    """PJSIPShowEndpoints's 'Contacts' field is a plain integer count on most
    Asterisk versions, but some versions instead put the actual comma-
    separated contact list here (e.g. '11/sip:11@192.168.7.217:58004;ob,') -
    int() on that raised ValueError, which took down the whole diagnostics
    endpoint (every call silently returned []), including all IP/contact
    info shown in the UI. Fall back to counting list entries."""
    text = str(raw or "").strip()
    if not text:
        return 0
    try:
        return int(text)
    except ValueError:
        return len([part for part in text.split(",") if part.strip()])


async def get_extension_diagnostics() -> list[dict]:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            manager = await _get_manager()
            endpoint_responses = await manager.send_action(
                {"Action": "PJSIPShowEndpoints"}, as_list=True
            )
            contact_responses = await manager.send_action(
                {"Action": "PJSIPShowContacts"}, as_list=True
            )

        endpoints: dict[str, dict] = {}
        for r in endpoint_responses:
            if r.get("Event") != "EndpointList":
                continue
            name = r.get("ObjectName", "")
            if not name.isdigit():
                continue
            endpoints[name] = {
                "number": name,
                "status": (
                    "Online"
                    if r.get("DeviceState", "") == "Not in use"
                    else "Offline"
                ),
                "device_state": r.get("DeviceState", "UNKNOWN"),
                "active_channels": int(r.get("ActiveChannels", 0) or 0),
                "aor": r.get("Aor", ""),
                "contacts": _parse_contacts_count(r.get("Contacts", 0)),
                # Kept for backward compat (Diagnostics.tsx): first contact seen.
                "contact_status": "",
                "contact_uri": "",
                "roundtrip_usec": None,
                "user_agent": "",
                # Every registered contact, not just the last one processed - an
                # extension with two devices (e.g. a DECT base AND a softphone)
                # previously had each new contact silently overwrite the last,
                # so only one of the two ever showed up anywhere.
                "contacts_detail": [],
            }

        for r in contact_responses:
            if r.get("Event") != "ContactList":
                continue
            endpoint_name = (
                r.get("EndpointName")
                or r.get("ObjectName")
                or r.get("AOR")
                or r.get("Aor")
                or ""
            )
            endpoint_name = str(endpoint_name).split("/")[0]
            if not endpoint_name.isdigit():
                continue
            existing = endpoints.get(endpoint_name)
            if existing is None:
                continue
            status = r.get("Status") or r.get("ContactStatus") or ""
            uri = r.get("URI") or r.get("Uri") or r.get("Contact") or ""
            roundtrip_raw = r.get("RoundtripUsec") or r.get("Roundtrip")
            try:
                roundtrip = int(roundtrip_raw) if roundtrip_raw not in (None, "") else None
            except (TypeError, ValueError):
                roundtrip = None
            user_agent = r.get("UserAgent") or r.get("Useragent") or ""

            existing["contacts_detail"].append(
                {
                    "status": status,
                    "uri": uri,
                    "roundtrip_usec": roundtrip,
                    "user_agent": user_agent,
                }
            )
            if not existing["contact_status"]:
                existing["contact_status"] = status
                existing["contact_uri"] = uri
                existing["roundtrip_usec"] = roundtrip
                existing["user_agent"] = user_agent

        return [endpoints[number] for number in sorted(endpoints, key=int)]
    except Exception as exc:
        _log.warning("AMI extension diagnostics unavailable: %s", exc)
        return []


async def get_active_call_count() -> int:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            manager = await _get_manager()
            responses = await manager.send_action(
                {"Action": "CoreShowChannels"}, as_list=True
            )
        return sum(1 for r in responses if r.get("Event") == "CoreShowChannel")
    except Exception as exc:
        _log.warning("AMI active call count unavailable: %s", exc)
        return 0


async def get_active_channel_details() -> list[dict]:
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            manager = await _get_manager()
            responses = await manager.send_action(
                {"Action": "CoreShowChannels"}, as_list=True
            )
        result = []
        for r in responses:
            if r.get("Event") != "CoreShowChannel":
                continue
            result.append(
                {
                    "channel": r.get("Channel", ""),
                    "state": r.get("ChannelStateDesc", ""),
                    "caller_id_num": r.get("CallerIDNum", ""),
                    "caller_id_name": r.get("CallerIDName", ""),
                    "connected_line_num": r.get("ConnectedLineNum", ""),
                    "connected_line_name": r.get("ConnectedLineName", ""),
                    "application": r.get("Application", ""),
                    "context": r.get("Context", ""),
                    "extension": r.get("Extension", ""),
                    "duration": r.get("Duration", ""),
                }
            )
        return result
    except Exception as exc:
        _log.warning("AMI active channel details unavailable: %s", exc)
        return []


async def hangup_channels_for_extension(number: str) -> int:
    """Hang up any active call on `number`'s PJSIP channel(s). This is the
    only reliable, immediate "disconnect this device" action Asterisk's AMI
    actually exposes - there is no supported action to force-expire an
    otherwise-idle, already-registered SIP contact (the registration itself
    persists until it naturally expires or the device reconnects). Used when
    deleting a provisioned device so at least an in-progress call ends now."""
    try:
        async with asyncio.timeout(_AMI_TIMEOUT):
            manager = await _get_manager()
            responses = await manager.send_action(
                {"Action": "CoreShowChannels"}, as_list=True
            )
            prefix = f"PJSIP/{number}-"
            channels = [
                r.get("Channel", "")
                for r in responses
                if r.get("Event") == "CoreShowChannel" and r.get("Channel", "").startswith(prefix)
            ]
            for channel in channels:
                await manager.send_action({"Action": "Hangup", "Channel": channel})
        return len(channels)
    except Exception as exc:
        _log.warning("AMI hangup for extension %s failed: %s", number, exc)
        return 0
