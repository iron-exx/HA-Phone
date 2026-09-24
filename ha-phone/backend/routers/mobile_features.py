"""
Phone-facing app features beyond pairing: presence (own status + live line
state of all extensions) and visual voicemail for the device's own mailbox.
All endpoints authenticate the device via X-Device-Id / X-Device-Token.
"""
import asyncio
import csv
import logging
import os
import re
import time
import wave
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from backend import ami, ha_api
from backend.database import get_session
from backend.models import Extension, MobileDevice, PresenceForwardingRule, RingGroup
from backend.regeneration import run_regeneration_steps, step_succeeded
from backend.routers.extensions import door_actions_of
from backend.routers.mobile_provisioning import authenticate_device
from backend.routers.time_conditions import _regenerate_routing_conf
from backend.voicemail_paths import data_dir, mailbox_dir

public_router = APIRouter(prefix="/mobile", tags=["mobile-features"])

PresenceStatus = Literal["available", "away", "lunch", "do_not_disturb", "off_work"]
VOICEMAIL_FOLDERS = ("INBOX", "Old")
_MESSAGE_NAME = re.compile(r"^msg\d{4}$")


def _device(
    x_device_id: int = Header(0),
    x_device_token: str = Header(""),
    session: Session = Depends(get_session),
) -> MobileDevice:
    return authenticate_device(session, x_device_id, x_device_token)


def _own_extension(session: Session, device: MobileDevice) -> Extension:
    ext = session.get(Extension, device.extension_id)
    if not ext:
        raise HTTPException(status_code=404, detail="Extension not found")
    return ext


# ============================================================
# Presence + live line state
# ============================================================

def line_state(device_state: str | None) -> str:
    """Asterisk DeviceState -> idle | ringing | busy | offline (for the app's status dot)."""
    state = (device_state or "").strip().lower()
    if state == "not in use":
        return "idle"
    if state.startswith("ring") and state != "ringinuse":
        return "ringing"
    if state in ("in use", "busy", "on hold", "ringinuse"):
        return "busy"
    return "offline"


class PresenceIn(BaseModel):
    status: PresenceStatus


@public_router.get("/presence")
async def get_presence(device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    # PJSIPShowEndpoints alone (fast); the contacts query behind diagnostics can hang.
    statuses = await ami.get_extension_statuses()
    lines = {str(d.get("number")): line_state(d.get("device_state")) for d in statuses}
    extensions = session.exec(
        select(Extension).where(Extension.enabled == True).order_by(Extension.number)  # noqa: E712
    ).all()
    return {
        "self": {"number": str(own.number), "presence": own.presence_status, "line": lines.get(str(own.number), "offline")},
        "extensions": [
            {"number": str(e.number), "presence": e.presence_status, "line": lines.get(str(e.number), "offline")}
            for e in extensions
            if e.id != own.id
        ],
    }


@public_router.put("/presence")
async def set_presence(
    data: PresenceIn,
    device: MobileDevice = Depends(_device),
    session: Session = Depends(get_session),
):
    own = _own_extension(session, device)
    own.presence_status = data.status
    session.add(own)
    session.commit()
    # Presence forwarding rules are baked into the dialplan, so a change needs a regeneration.
    summary = run_regeneration_steps(
        f"mobile.presence:{own.number}",
        [("routing", lambda: _regenerate_routing_conf(session))],
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return {"number": str(own.number), "presence": own.presence_status}


# ============================================================
# Visual voicemail
# ============================================================

def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _mailbox(ext_number: int) -> Path:
    return mailbox_dir(ext_number)


def _parse_envelope(txt: Path) -> dict:
    """Asterisk's msgNNNN.txt: key=value lines under [message]."""
    fields: dict[str, str] = {}
    if txt.exists():
        for line in txt.read_text(errors="replace").splitlines():
            if "=" in line and not line.startswith(";"):
                key, value = line.split("=", 1)
                fields[key.strip()] = value.strip()
    callerid = fields.get("callerid", "")
    match = re.match(r'^\s*"?([^"<]*)"?\s*<([^>]*)>\s*$', callerid)
    name, number = (match.group(1).strip(), match.group(2).strip()) if match else ("", callerid.strip())

    def as_int(key: str) -> int:
        try:
            return int(fields.get(key, "0"))
        except ValueError:
            return 0

    return {"caller_number": number, "caller_name": name, "duration_sec": as_int("duration"), "received_at": as_int("origtime")}


def _message_path(ext_number: int, folder: str, name: str) -> Path:
    if folder not in VOICEMAIL_FOLDERS:
        raise HTTPException(status_code=404, detail="Folder not found")
    if not _MESSAGE_NAME.match(name):
        raise HTTPException(status_code=400, detail="Invalid message id")
    base = _mailbox(ext_number) / folder
    path = base / f"{name}.wav"
    if not path.resolve().is_relative_to(base.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Message not found")
    return path


@public_router.get("/voicemail")
def list_voicemail(device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    messages = []
    for folder in VOICEMAIL_FOLDERS:
        base = _mailbox(own.number) / folder
        if not base.exists():
            continue
        for wav in sorted(base.glob("msg*.wav")):
            if not _MESSAGE_NAME.match(wav.stem):
                continue
            messages.append({
                "id": f"{folder}/{wav.stem}",
                "new": folder == "INBOX",
                **_parse_envelope(wav.with_suffix(".txt")),
            })
    return {"messages": messages, "new_count": sum(1 for m in messages if m["new"])}


@public_router.get("/voicemail/{folder}/{name}/audio")
def voicemail_audio(folder: str, name: str, device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    return FileResponse(str(_message_path(own.number, folder, name)), media_type="audio/wav")


@public_router.delete("/voicemail/{folder}/{name}")
def delete_voicemail(folder: str, name: str, device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    path = _message_path(own.number, folder, name)
    path.unlink()
    envelope = path.with_suffix(".txt")
    if envelope.exists():
        envelope.unlink()
    return {"success": True}


# ============================================================
# Forwarding rules per presence status (own extension only)
# ============================================================

# Destinations the app offers; IVR menus stay an admin-only choice.
_MOBILE_DEST_TYPES = {"extension", "ring_group", "voicemail", "hangup"}


class ForwardingRuleIn(BaseModel):
    status: PresenceStatus
    direction: Literal["internal", "external"]
    mode: Literal["ring_then_dest", "always_dest"] = "ring_then_dest"
    dest_type: str = "voicemail"
    dest_target: int = 0
    ring_timeout: int = Field(default=20, ge=5, le=120)


class ForwardingIn(BaseModel):
    rules: list[ForwardingRuleIn]


def _rule_out(rule: PresenceForwardingRule) -> dict:
    return {
        "status": rule.status, "direction": rule.direction, "mode": rule.mode,
        "dest_type": rule.dest_type, "dest_target": rule.dest_target, "ring_timeout": rule.ring_timeout,
    }


@public_router.get("/forwarding")
def get_forwarding(device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    rules = session.exec(select(PresenceForwardingRule).where(PresenceForwardingRule.extension_id == own.id)).all()
    return {"rules": [_rule_out(r) for r in sorted(rules, key=lambda r: (r.status, r.direction))]}


def _check_destination(session: Session, rule: ForwardingRuleIn) -> None:
    if rule.dest_type not in _MOBILE_DEST_TYPES:
        raise HTTPException(status_code=422, detail=f"dest_type must be one of {sorted(_MOBILE_DEST_TYPES)}")
    if rule.dest_type in ("extension", "voicemail"):
        if not session.exec(select(Extension).where(Extension.number == rule.dest_target)).first():
            raise HTTPException(status_code=422, detail=f"Unknown extension {rule.dest_target}")
    if rule.dest_type == "ring_group" and not session.get(RingGroup, rule.dest_target):
        raise HTTPException(status_code=422, detail=f"Unknown ring group {rule.dest_target}")


@public_router.put("/forwarding")
async def set_forwarding(
    data: ForwardingIn,
    device: MobileDevice = Depends(_device),
    session: Session = Depends(get_session),
):
    own = _own_extension(session, device)
    keys = [(r.status, r.direction) for r in data.rules]
    if len(keys) != len(set(keys)):
        raise HTTPException(status_code=422, detail="At most one rule per status and direction")
    for rule in data.rules:
        _check_destination(session, rule)
    for old in session.exec(select(PresenceForwardingRule).where(PresenceForwardingRule.extension_id == own.id)).all():
        session.delete(old)
    for rule in data.rules:
        session.add(PresenceForwardingRule(extension_id=own.id, **rule.model_dump()))
    session.commit()
    summary = run_regeneration_steps(
        f"mobile.forwarding:{own.number}",
        [("routing", lambda: _regenerate_routing_conf(session))],
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return get_forwarding(device, session)


# ============================================================
# Call history from Asterisk's CDR (all devices of the extension)
# ============================================================

_CDR_TAIL_BYTES = 2_000_000
_CDR_FIELDS = (
    "accountcode", "src", "dst", "dcontext", "clid", "channel", "dstchannel", "lastapp",
    "lastdata", "start", "answer", "end", "duration", "billsec", "disposition", "amaflags",
    "uniqueid",
)


def _cdr_file() -> Path:
    return _data_dir() / "logs" / "asterisk" / "cdr-csv" / "Master.csv"


def _cdr_rows() -> list[dict]:
    path = _cdr_file()
    if not path.exists():
        return []
    with path.open("rb") as f:
        f.seek(max(0, path.stat().st_size - _CDR_TAIL_BYTES))
        text = f.read().decode("utf-8", errors="replace")
    lines = text.splitlines()
    if path.stat().st_size > _CDR_TAIL_BYTES and lines:
        lines = lines[1:]  # first line is probably cut in half
    rows = []
    for values in csv.reader(lines):
        if len(values) >= len(_CDR_FIELDS):
            rows.append(dict(zip(_CDR_FIELDS, values)))
    return rows


def _epoch(local_time: str) -> int:
    try:
        return int(time.mktime(time.strptime(local_time, "%Y-%m-%d %H:%M:%S")))
    except ValueError:
        return 0


def _clid_name(clid: str) -> str:
    match = re.match(r'^\s*"([^"]*)"', clid)
    return match.group(1).strip() if match else ""


@public_router.get("/calls")
def get_calls(
    limit: int = 100,
    device: MobileDevice = Depends(_device),
    session: Session = Depends(get_session),
):
    own = _own_extension(session, device)
    leg = f"PJSIP/{own.number}-"
    calls: dict[str, dict] = {}
    for row in _cdr_rows():
        if row["dstchannel"].startswith(leg):
            direction, number, name = "incoming", row["src"], _clid_name(row["clid"])
        elif row["channel"].startswith(leg):
            direction, number, name = "outgoing", row["dst"], ""
        else:
            continue
        answered = row["disposition"] == "ANSWERED"
        call_id = row["uniqueid"] or f"{row['start']}-{number}"
        existing = calls.get(call_id)
        if existing and existing["answered"]:
            continue
        calls[call_id] = {
            "id": call_id, "number": number, "name": name, "direction": direction,
            "answered": answered, "started_at": _epoch(row["start"]),
            "duration_sec": int(row["billsec"] or 0) if answered else 0,
        }
    newest = sorted(calls.values(), key=lambda c: c["started_at"], reverse=True)
    return {"calls": newest[: max(1, min(limit, 500))]}


# ============================================================
# Home Assistant quick actions for door stations
# ============================================================

class DoorOpenIn(BaseModel):
    extension: str


@public_router.post("/door-open")
async def open_door(
    data: DoorOpenIn,
    device: MobileDevice = Depends(_device),
    session: Session = Depends(get_session),
):
    """The app's "Zum Öffnen schieben" slider: calls the door station's webhook, also while
    it only rings (no DTMF needed). 404 when the door has no webhook configured."""
    door = session.exec(select(Extension).where(Extension.number == int(data.extension))).first() if data.extension.isdigit() else None
    if not door or not door.door_open_webhook:
        raise HTTPException(status_code=404, detail="Kein Tür-Webhook eingerichtet")
    own = _own_extension(session, device)
    await ha_api.call_webhook(door.door_open_webhook, {
        "event": "door_open",
        "door_extension": str(door.number),
        "door_name": door.display_name,
        "by_extension": str(own.number),
        "by_name": own.display_name,
        "device_id": device.id,
    })
    return {"success": True}


class DoorActionIn(BaseModel):
    extension: str
    index: int


@public_router.post("/door-action")
async def run_door_action(
    data: DoorActionIn,
    device: MobileDevice = Depends(_device),
    session: Session = Depends(get_session),
):
    """Runs the admin-configured HA service of a door station (e.g. light on). The app only
    sends extension + button index; service and entity stay on the PBX."""
    door = session.exec(select(Extension).where(Extension.number == int(data.extension))).first() if data.extension.isdigit() else None
    actions = door_actions_of(door) if door else []
    if not 0 <= data.index < len(actions):
        raise HTTPException(status_code=404, detail="Aktion nicht gefunden")
    action = actions[data.index]
    await ha_api.call_service(action["service"], action["entity_id"])
    return {"success": True, "label": action["label"]}


# ============================================================
# Call recording (only for extensions the admin allowed)
# ============================================================

_RECORDING_NAME = re.compile(r"^(\d{8}-\d{6})_([0-9+*#]{0,32})$")


class RecordingIn(BaseModel):
    action: Literal["start", "stop"]
    # Number of the other party: tells the two lines apart when one is on hold.
    peer: str = Field(default="", max_length=32)


def recordings_dir(ext_number: int) -> Path:
    return data_dir() / "recordings" / str(ext_number)


def _recording_name(peer: str) -> str:
    safe_peer = re.sub(r"[^0-9+*#]", "", peer)[:32]
    return f"{time.strftime('%Y%m%d-%H%M%S')}_{safe_peer}"


def _recording_path(ext_number: int, name: str) -> Path:
    if not _RECORDING_NAME.match(name):
        raise HTTPException(status_code=400, detail="Invalid recording id")
    path = recordings_dir(ext_number) / f"{name}.wav"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")
    return path


def _wav_duration(path: Path) -> int:
    try:
        with wave.open(str(path)) as wav:
            return round(wav.getnframes() / (wav.getframerate() or 1))
    except (wave.Error, EOFError, OSError):
        return 0


@public_router.post("/recording")
async def control_recording(
    data: RecordingIn,
    device: MobileDevice = Depends(_device),
    session: Session = Depends(get_session),
):
    own = _own_extension(session, device)
    if not own.recording_allowed:
        raise HTTPException(status_code=403, detail="Aufzeichnung für diese Nebenstelle nicht freigegeben")
    peer = data.peer.strip()
    try:
        if data.action == "stop":
            if not await ami.stop_recording(str(own.number), peer):
                raise HTTPException(status_code=409, detail="Keine laufende Aufzeichnung gefunden")
            return {"recording": False}
        target = recordings_dir(own.number)
        target.mkdir(parents=True, exist_ok=True)
        name = _recording_name(peer)
        if not await ami.start_recording(str(own.number), peer, str(target / f"{name}.wav")):
            raise HTTPException(status_code=409, detail="Kein eindeutiges Gespräch gefunden")
    except (TimeoutError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"Anlage: {exc}")
    return {"recording": True, "id": name}


@public_router.get("/recordings")
def list_recordings(device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    base = recordings_dir(own.number)
    items = []
    for wav in sorted(base.glob("*.wav"), reverse=True) if base.exists() else []:
        match = _RECORDING_NAME.match(wav.stem)
        if not match:
            continue
        started = int(time.mktime(time.strptime(match.group(1), "%Y%m%d-%H%M%S")))
        items.append({
            "id": wav.stem,
            "peer": match.group(2),
            "started_at": started,
            "duration_sec": _wav_duration(wav),
            "size_bytes": wav.stat().st_size,
        })
    return {"allowed": own.recording_allowed, "recordings": items}


@public_router.get("/recordings/{name}/audio")
def recording_audio(name: str, device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    return FileResponse(str(_recording_path(own.number, name)), media_type="audio/wav")


@public_router.delete("/recordings/{name}")
def delete_recording(name: str, device: MobileDevice = Depends(_device), session: Session = Depends(get_session)):
    own = _own_extension(session, device)
    _recording_path(own.number, name).unlink()
    return {"success": True}


# ============================================================
# Test call ("Test-Anruf an mich" in the app's Erreichbarkeit screen)
# ============================================================

TEST_CALL_COOLDOWN_SEC = 60
_last_test_call: dict[int, float] = {}
_test_call_tasks: set[asyncio.Task] = set()
_log = logging.getLogger(__name__)


class TestCallIn(BaseModel):
    # Time to lock the phone before it rings.
    delay_sec: int = Field(default=10, ge=0, le=60)


async def _ring_later(number: str, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await ami.originate_test_call(number)
    except Exception as exc:  # the app already got 202; log for the admin
        _log.warning("test call to %s failed: %s", number, exc)


@public_router.post("/test-call", status_code=202)
async def request_test_call(
    data: TestCallIn,
    device: MobileDevice = Depends(_device),
    session: Session = Depends(get_session),
):
    """Rings this device's extension after `delay_sec`, once per minute per device."""
    own = _own_extension(session, device)
    now = time.monotonic()
    last = _last_test_call.get(device.id)
    if last is not None and now - last < TEST_CALL_COOLDOWN_SEC:
        raise HTTPException(status_code=429, detail=f"Bitte {int(TEST_CALL_COOLDOWN_SEC - (now - last)) + 1} s warten")
    _last_test_call[device.id] = now
    task = asyncio.create_task(_ring_later(str(own.number), data.delay_sec))
    _test_call_tasks.add(task)
    task.add_done_callback(_test_call_tasks.discard)
    return {"scheduled": True, "delay_sec": data.delay_sec, "number": str(own.number)}
