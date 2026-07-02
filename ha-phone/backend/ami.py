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
        _log.info("AMI: connecting to 127.0.0.1:5038 user=bpx-admin secret=%s...", secret[:8])

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
                result.append(
                    {
                        "number": r.get("ObjectName", ""),
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
