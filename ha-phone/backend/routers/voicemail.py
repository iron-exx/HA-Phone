import os
import re
import datetime
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import VoicemailSettings, Extension

router = APIRouter()


# ---- Helpers ----

def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _spool_inbox(ext_num: int) -> Path:
    return _data_dir() / "asterisk" / "spool" / "voicemail" / "default" / str(ext_num) / "INBOX"


def _spool_greeting(ext_num: int) -> Path:
    return _data_dir() / "asterisk" / "spool" / "voicemail" / "default" / str(ext_num) / "unavail.wav"


def _validate_ext_exists(ext_num: int, session: Session) -> None:
    """Raise 404 if extension number does not exist in DB (prevents spool enumeration)."""
    exts = session.exec(select(Extension)).all()
    numbers = {e.number for e in exts}
    if ext_num not in numbers:
        raise HTTPException(status_code=404, detail="Extension not found")


# ---- Existing settings endpoints ----

@router.get("/voicemail-settings", response_model=List[VoicemailSettings])
def list_voicemail_settings(session: Session = Depends(get_session)):
    return session.exec(select(VoicemailSettings)).all()


@router.post("/voicemail-settings", response_model=VoicemailSettings)
def create_voicemail_settings(
    settings: VoicemailSettings, session: Session = Depends(get_session)
):
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


@router.patch("/voicemail-settings/{settings_id}", response_model=VoicemailSettings)
def update_voicemail_settings(
    settings_id: int,
    settings_data: VoicemailSettings,
    session: Session = Depends(get_session),
):
    existing = session.get(VoicemailSettings, settings_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Voicemail settings not found")
    for field, value in settings_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


# ---- New voicemail message + greeting endpoints ----

@router.get("/voicemail/messages/{ext_num}")
def list_voicemail_messages(
    ext_num: int,
    session: Session = Depends(get_session),
):
    """List WAV messages in INBOX for an extension. Returns [] if no messages yet."""
    _validate_ext_exists(ext_num, session)
    inbox = _spool_inbox(ext_num)
    if not inbox.exists():
        return []
    messages = []
    for f in sorted(inbox.glob("*.wav"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = f.stat()
        messages.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "modified_at": datetime.datetime.fromtimestamp(
                stat.st_mtime, tz=datetime.timezone.utc
            ).isoformat(),
        })
    return messages


@router.get("/voicemail/messages/{ext_num}/{filename}")
def stream_voicemail_message(
    ext_num: int,
    filename: str,
    session: Session = Depends(get_session),
):
    """Stream a WAV voicemail message. Validates path to prevent traversal."""
    _validate_ext_exists(ext_num, session)
    # Whitelist: only msg####.wav filenames (Asterisk convention)
    if not re.match(r'^msg\d{4}\.wav$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    inbox = _spool_inbox(ext_num)
    file_path = inbox / filename
    # Additional path traversal guard
    if not file_path.resolve().is_relative_to(inbox.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Message not found")
    return FileResponse(str(file_path), media_type="audio/wav")


@router.delete("/voicemail/messages/{ext_num}/{filename}")
def delete_voicemail_message(
    ext_num: int,
    filename: str,
    session: Session = Depends(get_session),
):
    """Delete a WAV voicemail message and its envelope .txt file."""
    _validate_ext_exists(ext_num, session)
    if not re.match(r'^msg\d{4}\.wav$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    inbox = _spool_inbox(ext_num)
    file_path = inbox / filename
    if not file_path.resolve().is_relative_to(inbox.resolve()):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Message not found")
    file_path.unlink()
    # Also delete envelope .txt if present (Asterisk MWI tracking file)
    txt_path = inbox / filename.replace(".wav", ".txt")
    if txt_path.exists():
        txt_path.unlink()
    return {"ok": True}


@router.post("/voicemail-settings/{settings_id}/greeting")
async def upload_greeting(
    settings_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Upload a custom greeting WAV to the voicemail spool unavail.wav path."""
    settings = session.get(VoicemailSettings, settings_id)
    if not settings:
        raise HTTPException(status_code=404, detail="Voicemail settings not found")
    # Derive ext_num from mailbox field "10@default" → 10
    ext_num_str = settings.mailbox.split("@")[0]
    greeting_dir = _data_dir() / "asterisk" / "spool" / "voicemail" / "default" / ext_num_str
    greeting_dir.mkdir(parents=True, exist_ok=True)
    greeting_path = greeting_dir / "unavail.wav"
    content = await file.read()
    greeting_path.write_bytes(content)
    return {"ok": True}


@router.get("/voicemail/greeting/{ext_num}")
def stream_greeting(
    ext_num: int,
    session: Session = Depends(get_session),
):
    """Return custom greeting WAV if it exists; 404 otherwise (browser checks this for badge status)."""
    _validate_ext_exists(ext_num, session)
    greeting_path = _spool_greeting(ext_num)
    if not greeting_path.exists():
        raise HTTPException(status_code=404, detail="No custom greeting")
    return FileResponse(str(greeting_path), media_type="audio/wav")
