from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import OutboundRule
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()

# Sensible defaults so external dialling works out of the box; fully editable.
#   0.  strip 1 prepend +49  → national (0…) → E.164
#   00. strip 2 prepend +    → international (00…) → E.164
#   +.  strip 0 prepend ''   → already E.164, pass through
#
# NOTE: the aarenet/AareSwitch platform (used by Deutsche Glasfaser as white-label,
# see pjsip_trunk.conf.j2) rejects E.164 destination numbers with an in-band "invalid
# number" announcement (183 Session Progress, no SIP error) — it expects the dialled
# number in NATIONAL format (leading 0), matching the national format it already
# requires for the registration identity (reg_user = trunk.phone_number). If calls to
# this trunk get rejected with that announcement, change the "0." rule to strip=0,
# prepend='' (pass the national number through unchanged) instead of rewriting to +49.
DEFAULT_OUTBOUND_RULES = [
    {"pattern": "0.", "strip": 1, "prepend": "+49", "priority": 10},
    {"pattern": "00.", "strip": 2, "prepend": "+", "priority": 20},
    {"pattern": "+.", "strip": 0, "prepend": "", "priority": 30},
]


def seed_default_outbound_rules(session: Session) -> bool:
    """Insert the default outbound rules if none exist. Idempotent. Returns True
    if it seeded (so callers can decide whether to regenerate the dialplan)."""
    if session.exec(select(OutboundRule)).first():
        return False
    for r in DEFAULT_OUTBOUND_RULES:
        session.add(OutboundRule(**r))
    session.commit()
    return True


@router.get("/outbound-rules", response_model=List[OutboundRule])
def list_outbound_rules(session: Session = Depends(get_session)):
    return session.exec(select(OutboundRule).order_by(OutboundRule.priority)).all()


@router.post("/outbound-rules", response_model=OutboundRule)
async def create_outbound_rule(rule: OutboundRule, session: Session = Depends(get_session)):
    rule.id = None
    session.add(rule)
    session.commit()
    session.refresh(rule)
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return rule


@router.patch("/outbound-rules/{rule_id}", response_model=OutboundRule)
async def update_outbound_rule(
    rule_id: int, rule_data: OutboundRule, session: Session = Depends(get_session)
):
    existing = session.get(OutboundRule, rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Outbound rule not found")
    for field, value in rule_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return existing


@router.delete("/outbound-rules/{rule_id}")
async def delete_outbound_rule(rule_id: int, session: Session = Depends(get_session)):
    existing = session.get(OutboundRule, rule_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Outbound rule not found")
    session.delete(existing)
    session.commit()
    _regenerate_routing_conf(session)
    await ami.ami_reload_dialplan()
    return {"ok": True}
