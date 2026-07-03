import os
import secrets
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Extension, ExtensionUpdate, RingGroup, VoicemailSettings
from backend.conf_generator import render_conf
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _regenerate_extensions_conf(session: Session) -> None:
    """Regenerate pjsip_extensions.conf from all extensions in DB."""
    extensions = session.exec(select(Extension)).all()
    output_path = _data_dir() / "asterisk" / "pjsip_extensions.conf"
    render_conf("pjsip_extensions.conf.j2", {"extensions": extensions}, output_path)


def _regenerate_voicemail_conf(session: Session) -> None:
    """Render voicemail_mailboxes.conf.j2 from all extensions + their VM settings."""
    extensions = session.exec(select(Extension)).all()
    vm_settings_list = session.exec(select(VoicemailSettings)).all()
    # Build email map keyed by extension number
    ext_id_to_num = {ext.id: ext.number for ext in extensions}
    email_map: dict[int, str] = {}
    for vs in vm_settings_list:
        if vs.email and vs.extension_id in ext_id_to_num:
            email_map[ext_id_to_num[vs.extension_id]] = vs.email
    output_path = _data_dir() / "asterisk" / "voicemail_mailboxes.conf"
    render_conf(
        "voicemail_mailboxes.conf.j2",
        {"extensions": extensions, "email_map": email_map},
        output_path,
    )


def _remove_extension_from_ring_groups(session: Session, extension_number: int) -> None:
    ring_groups = session.exec(select(RingGroup)).all()
    for ring_group in ring_groups:
        numbers = [n.strip() for n in ring_group.extension_numbers.split(",") if n.strip()]
        filtered = [number for number in numbers if number != str(extension_number)]
        if filtered == numbers:
            continue
        ring_group.extension_numbers = ",".join(filtered)
        session.add(ring_group)


def _replace_extension_in_ring_groups(
    session: Session, old_number: int, new_number: int
) -> None:
    ring_groups = session.exec(select(RingGroup)).all()
    for ring_group in ring_groups:
        numbers = [n.strip() for n in ring_group.extension_numbers.split(",") if n.strip()]
        replaced = [str(new_number) if n == str(old_number) else n for n in numbers]
        deduped = sorted({int(n) for n in replaced})
        next_numbers = ",".join(str(number) for number in deduped)
        if next_numbers != ring_group.extension_numbers:
            ring_group.extension_numbers = next_numbers
            session.add(ring_group)


@router.get("/extensions/generate-password")
def generate_password() -> dict:
    """SEC-03: Generate a cryptographically secure SIP-safe password (16 chars)."""
    return {"password": secrets.token_urlsafe(12)}


@router.get("/extensions", response_model=List[Extension])
def list_extensions(session: Session = Depends(get_session)):
    return session.exec(select(Extension)).all()


@router.post("/extensions", response_model=Extension)
async def create_extension(extension: Extension, session: Session = Depends(get_session)):
    duplicate = session.exec(
        select(Extension).where(Extension.number == extension.number)
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Extension number already exists")
    # SEC-03: Auto-generate SIP password if not provided or empty (D-07)
    if not extension.sip_password:
        extension.sip_password = secrets.token_urlsafe(12)  # → exactly 16 SIP-safe chars
    session.add(extension)
    session.commit()
    session.refresh(extension)
    # Auto-create VoicemailSettings for this extension (Phase 4 requirement VM-03)
    existing_vm = session.exec(
        select(VoicemailSettings).where(VoicemailSettings.extension_id == extension.id)
    ).first()
    if not existing_vm:
        vm = VoicemailSettings(
            extension_id=extension.id,
            mailbox=f"{extension.number}@default",
        )
        session.add(vm)
        session.commit()
    _regenerate_extensions_conf(session)
    _regenerate_voicemail_conf(session)
    _regenerate_routing_conf(session)
    await ami.ami_reload_pjsip()
    await ami.ami_reload_voicemail()
    await ami.ami_reload_dialplan()
    return extension


@router.patch("/extensions/{extension_id}", response_model=Extension)
async def update_extension(
    extension_id: int,
    extension_data: ExtensionUpdate,
    session: Session = Depends(get_session),
):
    existing = session.get(Extension, extension_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Extension not found")
    if extension_data.number is not None and extension_data.number != existing.number:
        duplicate = session.exec(
            select(Extension).where(Extension.number == extension_data.number)
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Extension number already exists")
    old_number = existing.number
    for field, value in extension_data.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(existing, field, value)
    if existing.number != old_number:
        _replace_extension_in_ring_groups(session, old_number, existing.number)
        vm = session.exec(
            select(VoicemailSettings).where(VoicemailSettings.extension_id == extension_id)
        ).first()
        if vm:
            vm.mailbox = f"{existing.number}@default"
            session.add(vm)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    _regenerate_extensions_conf(session)
    _regenerate_voicemail_conf(session)
    _regenerate_routing_conf(session)
    await ami.ami_reload_pjsip()
    await ami.ami_reload_voicemail()
    await ami.ami_reload_dialplan()
    return existing


@router.delete("/extensions/{extension_id}")
async def delete_extension(
    extension_id: int, session: Session = Depends(get_session)
):
    existing = session.get(Extension, extension_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Extension not found")
    # Delete associated VM settings
    vm = session.exec(
        select(VoicemailSettings).where(VoicemailSettings.extension_id == extension_id)
    ).first()
    if vm:
        session.delete(vm)
    _remove_extension_from_ring_groups(session, existing.number)
    session.delete(existing)
    session.commit()
    _regenerate_extensions_conf(session)
    _regenerate_voicemail_conf(session)
    _regenerate_routing_conf(session)
    await ami.ami_reload_pjsip()
    await ami.ami_reload_voicemail()
    await ami.ami_reload_dialplan()
    return {"ok": True}


@router.get("/extensions/status")
async def get_extension_statuses():
    """Returns list of {number, status} from AMI PJSIPShowEndpoints."""
    statuses = await ami.get_extension_statuses()
    return statuses
