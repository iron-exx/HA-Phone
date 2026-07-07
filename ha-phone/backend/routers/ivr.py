import json
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import IVRMenu, Extension, RingGroup
from backend.numbering import validate_number
from backend.regeneration import run_single_regeneration_step, step_succeeded
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _ivr_dir() -> Path:
    """Directory for IVR greeting audio files."""
    d = _data_dir() / "sounds" / "custom" / "ivr"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _validate_ivr_number(ivr: IVRMenu, session: Session, existing_id: int | None = None) -> None:
    validate_number(session, ivr.number, kind="ivr", exclude_id=existing_id)


def _validate_options(options_str: str) -> list[dict]:
    """Parse and validate IVR options JSON."""
    if not options_str or not options_str.strip():
        return []
    try:
        options = json.loads(options_str)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=422, detail=f"Invalid options JSON: {e}")
    if not isinstance(options, list):
        raise HTTPException(status_code=422, detail="options must be a JSON array")
    valid_actions = {"extension", "ring_group", "ivr", "voicemail", "hangup"}
    for opt in options:
        if "key" not in opt or "action" not in opt:
            raise HTTPException(status_code=422, detail="Each option needs 'key' and 'action'")
        if opt["action"] not in valid_actions:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid action '{opt['action']}'. Must be: {', '.join(valid_actions)}",
            )
        if opt["action"] != "hangup" and "target" not in opt:
            raise HTTPException(
                status_code=422,
                detail=f"Action '{opt['action']}' requires a 'target' value",
            )
    return options


def _validate_option_targets(
    ivr_number: int,
    options: list[dict],
    session: Session,
    existing_id: int | None = None,
) -> None:
    extension_numbers = {ext.number for ext in session.exec(select(Extension)).all()}
    ring_group_numbers = {group.number for group in session.exec(select(RingGroup)).all()}
    ivr_numbers = {
        menu.number
        for menu in session.exec(select(IVRMenu)).all()
        if menu.id != existing_id
    }

    for opt in options:
        action = opt.get("action")
        target = opt.get("target")
        if action == "extension" and target not in extension_numbers:
            raise HTTPException(status_code=422, detail=f"Unknown extension target '{target}'")
        if action == "ring_group" and target not in ring_group_numbers:
            raise HTTPException(status_code=422, detail=f"Unknown ring group target '{target}'")
        if action == "voicemail" and target not in extension_numbers:
            raise HTTPException(status_code=422, detail=f"Unknown voicemail target '{target}'")
        if action == "ivr":
            if target == ivr_number:
                raise HTTPException(status_code=422, detail="IVR submenu cannot point to itself")
            if target not in ivr_numbers:
                raise HTTPException(status_code=422, detail=f"Unknown IVR submenu target '{target}'")


@router.get("/ivrs", response_model=List[IVRMenu])
def list_ivrs(session: Session = Depends(get_session)):
    return session.exec(select(IVRMenu)).all()


@router.get("/ivrs/{ivr_id}", response_model=IVRMenu)
def get_ivr(ivr_id: int, session: Session = Depends(get_session)):
    ivr = session.get(IVRMenu, ivr_id)
    if not ivr:
        raise HTTPException(status_code=404, detail="IVR menu not found")
    return ivr


@router.post("/ivrs", response_model=IVRMenu)
async def create_ivr(ivr: IVRMenu, session: Session = Depends(get_session)):
    _validate_ivr_number(ivr, session)
    parsed_options = _validate_options(ivr.options)
    _validate_option_targets(ivr.number, parsed_options, session)
    ivr.id = None
    session.add(ivr)
    session.commit()
    session.refresh(ivr)
    summary = run_single_regeneration_step(
        f"ivrs.create:{ivr.number}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return ivr


@router.patch("/ivrs/{ivr_id}", response_model=IVRMenu)
async def update_ivr(ivr_id: int, ivr_data: IVRMenu, session: Session = Depends(get_session)):
    existing = session.get(IVRMenu, ivr_id)
    if not existing:
        raise HTTPException(status_code=404, detail="IVR menu not found")
    for field, value in ivr_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    _validate_ivr_number(existing, session, existing_id=ivr_id)
    parsed_options = _validate_options(existing.options)
    _validate_option_targets(existing.number, parsed_options, session, existing_id=ivr_id)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    summary = run_single_regeneration_step(
        f"ivrs.update:{existing.number}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return existing


@router.delete("/ivrs/{ivr_id}")
async def delete_ivr(ivr_id: int, session: Session = Depends(get_session)):
    existing = session.get(IVRMenu, ivr_id)
    if not existing:
        raise HTTPException(status_code=404, detail="IVR menu not found")
    # Remove greeting file if exists
    if existing.greeting_file:
        greeting_path = _ivr_dir() / existing.greeting_file
        if greeting_path.exists():
            greeting_path.unlink()
    session.delete(existing)
    session.commit()
    summary = run_single_regeneration_step(
        f"ivrs.delete:{existing.number}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return {"ok": True}


@router.post("/ivrs/{ivr_id}/greeting")
async def upload_greeting(
    ivr_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
):
    """Upload a WAV greeting file for an IVR menu."""
    ivr = session.get(IVRMenu, ivr_id)
    if not ivr:
        raise HTTPException(status_code=404, detail="IVR menu not found")

    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(status_code=422, detail="Only WAV files are accepted")

    # Save file
    filename = f"ivr_{ivr_id}_greeting.wav"
    filepath = _ivr_dir() / filename
    content = await file.read()
    filepath.write_bytes(content)

    # Update IVR record
    ivr.greeting_file = filename
    session.add(ivr)
    session.commit()
    session.refresh(ivr)

    return {"ok": True, "filename": filename}


@router.delete("/ivrs/{ivr_id}/greeting")
async def delete_greeting(ivr_id: int, session: Session = Depends(get_session)):
    """Remove the greeting file for an IVR menu."""
    ivr = session.get(IVRMenu, ivr_id)
    if not ivr:
        raise HTTPException(status_code=404, detail="IVR menu not found")

    if ivr.greeting_file:
        greeting_path = _ivr_dir() / ivr.greeting_file
        if greeting_path.exists():
            greeting_path.unlink()
        ivr.greeting_file = ""
        session.add(ivr)
        session.commit()

    return {"ok": True}


@router.get("/ivr-greeting/{ivr_id}")
def get_greeting(ivr_id: int, session: Session = Depends(get_session)):
    """Stream the IVR greeting audio file."""
    ivr = session.get(IVRMenu, ivr_id)
    if not ivr or not ivr.greeting_file:
        raise HTTPException(status_code=404, detail="No greeting file")

    from fastapi.responses import FileResponse
    filepath = _ivr_dir() / ivr.greeting_file
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Greeting file not found")

    return FileResponse(filepath, media_type="audio/wav")
