from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Extension, RingGroup
# Use the canonical routing regen (includes inbound routes, outbound rules, CLIP).
# The previous local copy here only wrote ring groups + time conditions and thus
# WIPED routes/outbound rules from the dialplan whenever a ring group changed.
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()


def _parse_extension_numbers(extension_numbers: str, allow_empty: bool = False) -> list[int]:
    if not extension_numbers or not extension_numbers.strip():
        if allow_empty:
            return []
        raise HTTPException(status_code=422, detail="extension_numbers must not be empty")
    try:
        numbers = [int(n.strip()) for n in extension_numbers.split(",") if n.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="extension_numbers must be comma-separated integers",
        ) from exc
    if not numbers and not allow_empty:
        raise HTTPException(status_code=422, detail="extension_numbers must not be empty")
    if len(numbers) != len(set(numbers)):
        raise HTTPException(status_code=422, detail="extension_numbers must not contain duplicates")
    return sorted(numbers)


def _validate_extension_numbers(
    extension_numbers: str,
    session: Session,
    allow_empty: bool = False,
) -> list[int]:
    numbers = _parse_extension_numbers(extension_numbers, allow_empty=allow_empty)
    existing = set(session.exec(select(Extension.number)).all())
    missing = [number for number in numbers if number not in existing]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown extension_numbers: {','.join(str(number) for number in missing)}",
        )
    return numbers


@router.get("/ring-groups", response_model=List[RingGroup])
def list_ring_groups(session: Session = Depends(get_session)):
    return session.exec(select(RingGroup)).all()


@router.post("/ring-groups", response_model=RingGroup)
async def create_ring_group(rg: RingGroup, session: Session = Depends(get_session)):
    numbers = _validate_extension_numbers(rg.extension_numbers, session)
    rg.extension_numbers = ",".join(str(number) for number in numbers)
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
    numbers = _validate_extension_numbers(existing.extension_numbers, session, allow_empty=True)
    existing.extension_numbers = ",".join(str(number) for number in numbers)
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
