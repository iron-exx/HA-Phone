import html
import os
import secrets
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from fastapi.responses import Response

from backend.database import get_session
from backend.models import (
    Extension,
    ExtensionCreateOut,
    ExtensionOut,
    ExtensionUpdate,
    RingGroup,
    VoicemailSettings,
)
from backend.conf_generator import render_conf
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()
public_router = APIRouter()


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


def _ensure_provisioning_token(extension: Extension, session: Session) -> Extension:
    if extension.provisioning_token:
        return extension
    extension.provisioning_token = secrets.token_urlsafe(24)
    session.add(extension)
    session.commit()
    session.refresh(extension)
    return extension


def _request_host(request: Request) -> str:
    forwarded_host = request.headers.get("x-forwarded-host", "")
    if forwarded_host:
        return forwarded_host.split(",")[0].strip()
    if request.url.hostname:
        return request.url.hostname
    return "pbx.local"


def _render_linphone_provisioning_xml(extension: Extension, request: Request) -> str:
    host = html.escape(_request_host(request), quote=True)
    username = html.escape(str(extension.number), quote=True)
    password = html.escape(extension.sip_password, quote=True)
    identity = f"sip:{username}@{host}"
    # linphonerc URI format: reg_proxy/reg_route MUST carry the sip: scheme
    # (canonically wrapped in <>). A bare "host;transport=udp" downloads fine
    # but account creation fails silently - the app fetches the XML repeatedly
    # and never sends a single REGISTER.
    proxy = f"&lt;sip:{host};transport=udp&gt;"
    route = f"&lt;sip:{host};transport=udp;lr&gt;"
    media_encryption = "none"
    video_enabled = "1" if extension.video_capable else "0"

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<config xmlns="http://www.linphone.org/xsds/lpconfig.xsd" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        'xsi:schemaLocation="http://www.linphone.org/xsds/lpconfig.xsd lpconfig.xsd">\n'
        '  <section name="sip">\n'
        '    <entry name="sip_port" overwrite="true">-1</entry>\n'
        '    <entry name="sip_tcp_port" overwrite="true">-1</entry>\n'
        '    <entry name="sip_tls_port" overwrite="true">-1</entry>\n'
        '    <entry name="default_proxy" overwrite="true">0</entry>\n'
        '    <entry name="guess_hostname" overwrite="true">1</entry>\n'
        f'    <entry name="media_encryption" overwrite="true">{media_encryption}</entry>\n'
        "  </section>\n"
        '  <section name="auth_info_0">\n'
        f'    <entry name="username" overwrite="true">{username}</entry>\n'
        f'    <entry name="userid" overwrite="true">{username}</entry>\n'
        f'    <entry name="passwd" overwrite="true">{password}</entry>\n'
        f'    <entry name="realm" overwrite="true">{host}</entry>\n'
        f'    <entry name="domain" overwrite="true">{host}</entry>\n'
        "  </section>\n"
        '  <section name="proxy_0">\n'
        f'    <entry name="reg_proxy" overwrite="true">{proxy}</entry>\n'
        f'    <entry name="reg_route" overwrite="true">{route}</entry>\n'
        f'    <entry name="reg_identity" overwrite="true">{identity}</entry>\n'
        '    <entry name="reg_expires" overwrite="true">600</entry>\n'
        '    <entry name="reg_sendregister" overwrite="true">1</entry>\n'
        '    <entry name="publish" overwrite="true">0</entry>\n'
        '    <entry name="dial_escape_plus" overwrite="true">0</entry>\n'
        # No push gateway exists for this self-hosted PBX. With push enabled,
        # Linphone (iOS in particular) registers once with ;pn- contact params,
        # then suspends and waits for pushes that never come: the registration
        # expires, the UI still claims "online", and tapping call does nothing.
        '    <entry name="push_notification_allowed" overwrite="true">0</entry>\n'
        '    <entry name="remote_push_notification_allowed" overwrite="true">0</entry>\n'
        "  </section>\n"
        '  <section name="video">\n'
        f'    <entry name="enabled" overwrite="true">{video_enabled}</entry>\n'
        f'    <entry name="capture" overwrite="true">{video_enabled}</entry>\n'
        f'    <entry name="display" overwrite="true">{video_enabled}</entry>\n'
        '    <entry name="self_view" overwrite="true">0</entry>\n'
        '    <entry name="automatically_initiate" overwrite="true">0</entry>\n'
        '    <entry name="automatically_accept" overwrite="true">0</entry>\n'
        "  </section>\n"
        "</config>\n"
    )


def _extension_out(extension: Extension) -> ExtensionOut:
    return ExtensionOut(
        id=extension.id or 0,
        number=extension.number,
        display_name=extension.display_name,
        enabled=extension.enabled,
        video_capable=extension.video_capable,
        internal_only=extension.internal_only,
        numeric_callerid=extension.numeric_callerid,
    )


def _extension_create_out(extension: Extension) -> ExtensionCreateOut:
    return ExtensionCreateOut(
        **_extension_out(extension).model_dump(),
        sip_password=extension.sip_password,
    )


@router.get("/extensions/generate-password")
def generate_password() -> dict:
    """SEC-03: Generate a cryptographically secure SIP-safe password (16 chars)."""
    return {"password": secrets.token_urlsafe(12)}


@router.get("/extensions", response_model=List[ExtensionOut])
def list_extensions(session: Session = Depends(get_session)):
    return [_extension_out(extension) for extension in session.exec(select(Extension)).all()]


@router.get("/extensions/{extension_id}/linphone-qr")
def get_linphone_qr(extension_id: int, session: Session = Depends(get_session)):
    extension = session.get(Extension, extension_id)
    if not extension:
        raise HTTPException(status_code=404, detail="Extension not found")
    extension = _ensure_provisioning_token(extension, session)
    return {
        "extension_id": extension.id,
        "extension_number": extension.number,
        "display_name": extension.display_name,
        "provisioning_path": f"/api/linphone/provision/{extension.provisioning_token}",
    }


@router.post("/extensions", response_model=ExtensionCreateOut)
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
    return _extension_create_out(extension)


@router.patch("/extensions/{extension_id}", response_model=ExtensionOut)
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
    return _extension_out(existing)


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


@public_router.get("/linphone/provision/{token}")
def get_linphone_provisioning(token: str, request: Request, session: Session = Depends(get_session)):
    extension = session.exec(
        select(Extension).where(Extension.provisioning_token == token)
    ).first()
    if not extension:
        raise HTTPException(status_code=404, detail="Unknown provisioning token")
    xml = _render_linphone_provisioning_xml(extension, request)
    return Response(content=xml, media_type="application/xml")
