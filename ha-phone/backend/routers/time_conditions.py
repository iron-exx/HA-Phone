import os
import re
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import TimeCondition, RingGroup, Route, OutboundRule, Extension, Trunk
from backend.conf_generator import render_conf
from backend.routers.trunk import _to_e164
from backend import ami

router = APIRouter()


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def _build_dial_string(ring_group: RingGroup) -> str:
    numbers = [n.strip() for n in ring_group.extension_numbers.split(",") if n.strip()]
    return "&".join(f"PJSIP/{n}" for n in numbers)


def _did_variants(did: str) -> list[str]:
    """Expand a stored DID into the formats a carrier might send in an inbound
    INVITE, so an inbound route matches regardless of whether the trunk delivers
    +49…, 0049…, 49…, national 0… or the national number without leading 0.
    German (+49) numbers are expanded to their national forms too."""
    raw = (did or "").strip()
    digits = re.sub(r"[^0-9]", "", raw)
    variants: set[str] = set()
    if raw:
        variants.add(raw)
    if digits:
        variants.add(digits)
        variants.add("+" + digits)
        variants.add("00" + digits)
        if digits.startswith("49") and len(digits) > 2:
            nat = digits[2:]
            variants.add("0" + nat)
            variants.add(nat)
    return sorted(variants)


def _regenerate_routing_conf(session: Session) -> None:
    """Render extensions_routing.conf.j2 from time conditions, ring groups,
    inbound routes and outbound dial rules (all editable via the web UI)."""
    time_conditions = session.exec(select(TimeCondition)).all()
    ring_groups_list = session.exec(select(RingGroup)).all()
    ring_group_dials = {rg.id: _build_dial_string(rg) for rg in ring_groups_list}
    routes = session.exec(select(Route)).all()
    outbound_rules = session.exec(
        select(OutboundRule).order_by(OutboundRule.priority)
    ).all()
    extensions = session.exec(select(Extension)).all()
    route_dids = {r.id: _did_variants(r.did) for r in routes}
    # dial-all-extensions string for the no-route inbound fallback
    all_ext_dial = "&".join(f"PJSIP/{e.number}" for e in extensions)
    # Outbound caller ID (E.164) — set on outbound calls so the callee sees the
    # trunk's number (CLIP), independent of the calling extension's caller ID.
    trunk = session.exec(select(Trunk)).first()
    trunk_callerid = _to_e164(trunk.phone_number) if trunk else ""
    output_path = _data_dir() / "asterisk" / "extensions_routing.conf"
    render_conf(
        "extensions_routing.conf.j2",
        {
            "time_conditions": time_conditions,
            "ring_groups": ring_groups_list,
            "ring_group_dials": ring_group_dials,
            "routes": routes,
            "route_dids": route_dids,
            "outbound_rules": outbound_rules,
            "extensions": extensions,
            "all_ext_dial": all_ext_dial,
            "trunk_callerid": trunk_callerid,
        },
        output_path,
    )


@router.get("/time-conditions", response_model=List[TimeCondition])
def list_time_conditions(session: Session = Depends(get_session)):
    return session.exec(select(TimeCondition)).all()


@router.post("/time-conditions", response_model=TimeCondition)
async def create_time_condition(
    condition: TimeCondition, session: Session = Depends(get_session)
):
    session.add(condition)
    session.commit()
    session.refresh(condition)
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return condition


@router.patch("/time-conditions/{condition_id}", response_model=TimeCondition)
async def update_time_condition(
    condition_id: int,
    condition_data: TimeCondition,
    session: Session = Depends(get_session),
):
    existing = session.get(TimeCondition, condition_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Time condition not found")
    for field, value in condition_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return existing


@router.delete("/time-conditions/{condition_id}")
async def delete_time_condition(
    condition_id: int, session: Session = Depends(get_session)
):
    existing = session.get(TimeCondition, condition_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Time condition not found")
    session.delete(existing)
    session.commit()
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return {"ok": True}
