import re
import os
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import RingGroup, TimeCondition
from backend.conf_generator import render_conf
from backend import ami

router = APIRouter()


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _build_dial_string(ring_group: RingGroup) -> str:
    numbers = [n.strip() for n in ring_group.extension_numbers.split(",") if n.strip()]
    return "&".join(f"PJSIP/{n}" for n in numbers)


def _validate_extension_numbers(extension_numbers: str) -> None:
    if not extension_numbers or not extension_numbers.strip():
        raise HTTPException(status_code=422, detail="extension_numbers must not be empty")
    if not re.match(r'^\d+(,\d+)*$', extension_numbers.strip()):
        raise HTTPException(status_code=422, detail="extension_numbers must be comma-separated integers")


def _regenerate_routing_conf(session: Session) -> None:
    time_conditions = session.exec(select(TimeCondition)).all()
    ring_groups_list = session.exec(select(RingGroup)).all()
    ring_group_dials = {rg.id: _build_dial_string(rg) for rg in ring_groups_list}
    output_path = _data_dir() / "asterisk" / "extensions_routing.conf"
    render_conf(
        "extensions_routing.conf.j2",
        {
            "time_conditions": time_conditions,
            "ring_groups": ring_groups_list,
            "ring_group_dials": ring_group_dials,
        },
        output_path,
    )


@router.get("/ring-groups", response_model=List[RingGroup])
def list_ring_groups(session: Session = Depends(get_session)):
    return session.exec(select(RingGroup)).all()


@router.post("/ring-groups", response_model=RingGroup)
async def create_ring_group(rg: RingGroup, session: Session = Depends(get_session)):
    _validate_extension_numbers(rg.extension_numbers)
    rg.id = None
    session.add(rg)
    session.commit()
    session.refresh(rg)
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return rg


@router.patch("/ring-groups/{rg_id}", response_model=RingGroup)
async def update_ring_group(rg_id: int, rg_data: RingGroup, session: Session = Depends(get_session)):
    existing = session.get(RingGroup, rg_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ring group not found")
    for field, value in rg_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    _validate_extension_numbers(existing.extension_numbers)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return existing


@router.delete("/ring-groups/{rg_id}")
async def delete_ring_group(rg_id: int, session: Session = Depends(get_session)):
    existing = session.get(RingGroup, rg_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ring group not found")
    session.delete(existing)
    session.commit()
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return {"ok": True}
