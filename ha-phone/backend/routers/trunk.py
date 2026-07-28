import os
import re
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Trunk, TrunkDid
from backend.conf_generator import render_conf
from backend.regeneration import run_regeneration_steps, step_succeeded
from backend import ami

router = APIRouter()


class TrunkDidCreate(BaseModel):
    did: str
    label: str = ""


def _to_e164(number: str) -> str:
    """Normalize a German phone number to E.164 (+49…) for outbound CallerID/PAI.
    Registrars like aarenet/Deutsche Glasfaser only present a caller ID (CLIP) when
    it is signalled in E.164; a national '0…' number is not displayed to the callee."""
    raw = (number or "").strip()
    if raw.startswith("+"):
        return "+" + re.sub(r"[^0-9]", "", raw)
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return ""
    if digits.startswith("00"):
        return "+" + digits[2:]
    if digits.startswith("0"):
        return "+49" + digits[1:]
    if digits.startswith("49"):
        return "+" + digits
    return "+" + digits


class TrunkPublic(BaseModel):
    """Trunk response that omits the password field (T-03-03)."""
    id: Optional[int] = None
    registrar_host: str
    port: int
    transport: str
    domain: str
    auth_username: str
    phone_number: str
    reg_refresh: int
    codecs: str = "ulaw,alaw"


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _regenerate_trunk_conf(trunk: Trunk) -> None:
    output_path = _data_dir() / "asterisk" / "pjsip_trunk.conf"
    render_conf(
        "pjsip_trunk.conf.j2",
        {"trunk": trunk, "caller_e164": _to_e164(trunk.phone_number)},
        output_path,
    )


@router.get("/trunk", response_model=Optional[TrunkPublic])
def get_trunk(session: Session = Depends(get_session)):
    trunk = session.exec(select(Trunk)).first()
    if trunk is None:
        return None
    return TrunkPublic(
        id=trunk.id,
        registrar_host=trunk.registrar_host,
        port=trunk.port,
        transport=trunk.transport,
        domain=trunk.domain,
        auth_username=trunk.auth_username,
        phone_number=trunk.phone_number,
        reg_refresh=trunk.reg_refresh,
        codecs=trunk.codecs or "ulaw,alaw",
    )


@router.post("/trunk", response_model=TrunkPublic)
async def save_trunk(trunk_data: Trunk, session: Session = Depends(get_session)):
    # Upsert: delete existing row, insert new
    existing_trunks = session.exec(select(Trunk)).all()
    for t in existing_trunks:
        session.delete(t)
    session.commit()

    trunk_data.id = None
    session.add(trunk_data)
    session.commit()
    session.refresh(trunk_data)
    # Also refresh the dialplan so the outbound caller ID (CLIP) picks up the new
    # number. Deferred import avoids a circular import with time_conditions.
    from backend.routers.time_conditions import _regenerate_routing_conf

    summary = run_regeneration_steps(
        f"trunk.save:{trunk_data.phone_number}",
        [
            ("trunk", lambda: _regenerate_trunk_conf(trunk_data)),
            ("routing", lambda: _regenerate_routing_conf(session)),
        ],
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    if step_succeeded(summary, "trunk"):
        await ami.ami_reload_pjsip()
    return TrunkPublic(
        id=trunk_data.id,
        registrar_host=trunk_data.registrar_host,
        port=trunk_data.port,
        transport=trunk_data.transport,
        domain=trunk_data.domain,
        auth_username=trunk_data.auth_username,
        phone_number=trunk_data.phone_number,
        reg_refresh=trunk_data.reg_refresh,
        codecs=trunk_data.codecs or "ulaw,alaw",
    )


@router.post("/trunk/test")
async def test_trunk():
    status = await ami.get_trunk_status()
    return {"status": status}


@router.get("/trunk/status")
async def trunk_status():
    status = await ami.get_trunk_status()
    return {"status": status}


@router.get("/trunk/debug")
async def trunk_debug():
    return await ami.get_trunk_debug()


@router.get("/trunk/dids", response_model=list[TrunkDid])
def list_trunk_dids(session: Session = Depends(get_session)):
    return session.exec(select(TrunkDid)).all()


@router.post("/trunk/dids", response_model=TrunkDid)
def create_trunk_did(did_data: TrunkDidCreate, session: Session = Depends(get_session)):
    did = TrunkDid(did=did_data.did, label=did_data.label)
    session.add(did)
    session.commit()
    session.refresh(did)
    return did


@router.delete("/trunk/dids/{did_id}")
def delete_trunk_did(did_id: int, session: Session = Depends(get_session)):
    existing = session.get(TrunkDid, did_id)
    if not existing:
        raise HTTPException(status_code=404, detail="DID not found")
    session.delete(existing)
    session.commit()
    return {"ok": True}
