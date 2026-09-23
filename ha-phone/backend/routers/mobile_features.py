"""
Phone-facing app features beyond pairing: presence (own status + live line
state of all extensions) and visual voicemail for the device's own mailbox.
All endpoints authenticate the device via X-Device-Id / X-Device-Token.
"""
import os
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from backend import ami
from backend.database import get_session
from backend.models import Extension, MobileDevice
from backend.regeneration import run_regeneration_steps, step_succeeded
from backend.routers.mobile_provisioning import authenticate_device
from backend.routers.time_conditions import _regenerate_routing_conf

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
    diagnostics = await ami.get_extension_diagnostics()
    lines = {str(d.get("number")): line_state(d.get("device_state")) for d in diagnostics}
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
    return _data_dir() / "asterisk" / "spool" / "voicemail" / "default" / str(ext_number)


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
