from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Extension, PresenceForwardingRule
from backend.regeneration import run_single_regeneration_step, step_succeeded
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()

_VALID_DIRECTIONS = {"internal", "external"}
_VALID_MODES = {"ring_then_dest", "always_dest"}
_VALID_DEST_TYPES = {"extension", "ring_group", "ivr", "voicemail", "hangup"}


def _validate_rule(rule: PresenceForwardingRule, session: Session) -> None:
    if not session.get(Extension, rule.extension_id):
        raise HTTPException(status_code=422, detail="Unknown extension_id")
    if not rule.status.strip():
        raise HTTPException(status_code=422, detail="status must not be empty")
    if rule.direction not in _VALID_DIRECTIONS:
        raise HTTPException(status_code=422, detail=f"direction must be one of {sorted(_VALID_DIRECTIONS)}")
    if rule.mode not in _VALID_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {sorted(_VALID_MODES)}")
    if rule.dest_type not in _VALID_DEST_TYPES:
        raise HTTPException(status_code=422, detail=f"dest_type must be one of {sorted(_VALID_DEST_TYPES)}")


@router.get("/presence-rules", response_model=List[PresenceForwardingRule])
def list_presence_rules(
    extension_id: Optional[int] = Query(default=None),
    session: Session = Depends(get_session),
):
    query = select(PresenceForwardingRule)
    if extension_id is not None:
        query = query.where(PresenceForwardingRule.extension_id == extension_id)
    return session.exec(query).all()


@router.post("/presence-rules", response_model=PresenceForwardingRule)
async def create_presence_rule(rule: PresenceForwardingRule, session: Session = Depends(get_session)):
    _validate_rule(rule, session)
    # At most one rule per (extension, status, direction) - replace any existing
    # one instead of accumulating ambiguous duplicates the dialplan would have
    # to arbitrarily pick between.
    existing = session.exec(
        select(PresenceForwardingRule).where(
            PresenceForwardingRule.extension_id == rule.extension_id,
            PresenceForwardingRule.status == rule.status,
            PresenceForwardingRule.direction == rule.direction,
        )
    ).first()
    if existing:
        session.delete(existing)
        session.commit()
    rule.id = None
    session.add(rule)
    session.commit()
    session.refresh(rule)
    summary = run_single_regeneration_step(
        f"presence_rules.create:{rule.extension_id}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return rule


@router.patch("/presence-rules/{rule_id}", response_model=PresenceForwardingRule)
async def update_presence_rule(
    rule_id: int, rule_data: PresenceForwardingRule, session: Session = Depends(get_session)
):
    existing = session.get(PresenceForwardingRule, rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Presence rule not found")
    for field, value in rule_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    _validate_rule(existing, session)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    summary = run_single_regeneration_step(
        f"presence_rules.update:{existing.id}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return existing


@router.delete("/presence-rules/{rule_id}")
async def delete_presence_rule(rule_id: int, session: Session = Depends(get_session)):
    existing = session.get(PresenceForwardingRule, rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Presence rule not found")
    session.delete(existing)
    session.commit()
    summary = run_single_regeneration_step(
        f"presence_rules.delete:{rule_id}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return {"ok": True}
