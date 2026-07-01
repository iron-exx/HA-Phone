import os
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Trunk
from backend.conf_generator import render_conf
from backend import ami

router = APIRouter()


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


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _regenerate_trunk_conf(trunk: Trunk) -> None:
    output_path = _data_dir() / "asterisk" / "pjsip_trunk.conf"
    render_conf("pjsip_trunk.conf.j2", {"trunk": trunk}, output_path)


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
    _regenerate_trunk_conf(trunk_data)
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
