from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Extension, ExtensionGroup, RingGroup, Route
from backend.numbering import validate_number
from backend.regeneration import run_single_regeneration_step, step_succeeded
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


def _validate_ring_group_number(rg: RingGroup, session: Session, existing_id: int | None = None) -> None:
    validate_number(session, rg.number, kind="ring_group", exclude_id=existing_id)


def _validate_extension_group_ids(extension_group_ids: str, session: Session) -> list[int]:
    """Same shape as _validate_extension_numbers, for the nested extension-group
    member list. Always allows empty - a ring group need not use any groups."""
    raw = (extension_group_ids or "").strip()
    if not raw:
        return []
    try:
        ids = [int(g.strip()) for g in raw.split(",") if g.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="extension_group_ids must be comma-separated integers",
        ) from exc
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=422, detail="extension_group_ids must not contain duplicates")
    existing = set(session.exec(select(ExtensionGroup.id)).all())
    missing = [gid for gid in ids if gid not in existing]
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown extension_group_ids: {','.join(str(gid) for gid in missing)}",
        )
    return sorted(ids)


@router.get("/ring-groups", response_model=List[RingGroup])
def list_ring_groups(session: Session = Depends(get_session)):
    return session.exec(select(RingGroup)).all()


@router.post("/ring-groups", response_model=RingGroup)
async def create_ring_group(rg: RingGroup, session: Session = Depends(get_session)):
    _validate_ring_group_number(rg, session)
    # A member can come from either list now (a ring group of pure extension
    # groups is valid) - allow_empty on both, then require at least one member
    # overall so an empty ring group (dials nobody) isn't silently created.
    numbers = _validate_extension_numbers(rg.extension_numbers, session, allow_empty=True)
    group_ids = _validate_extension_group_ids(rg.extension_group_ids, session)
    if not numbers and not group_ids:
        raise HTTPException(status_code=422, detail="extension_numbers must not be empty")
    rg.extension_numbers = ",".join(str(number) for number in numbers)
    rg.extension_group_ids = ",".join(str(gid) for gid in group_ids)
    rg.id = None
    session.add(rg)
    session.commit()
    session.refresh(rg)
    summary = run_single_regeneration_step(
        f"ring_groups.create:{rg.number}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
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
    _validate_ring_group_number(existing, session, existing_id=rg_id)
    numbers = _validate_extension_numbers(existing.extension_numbers, session, allow_empty=True)
    group_ids = _validate_extension_group_ids(existing.extension_group_ids, session)
    existing.extension_numbers = ",".join(str(number) for number in numbers)
    existing.extension_group_ids = ",".join(str(gid) for gid in group_ids)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    summary = run_single_regeneration_step(
        f"ring_groups.update:{existing.number}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return existing


@router.delete("/ring-groups/{rg_id}")
async def delete_ring_group(rg_id: int, session: Session = Depends(get_session)):
    existing = session.get(RingGroup, rg_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Ring group not found")
    # Referential integrity (Roadmap Phase A.3): a Route pointing at this ring
    # group's now-deleted id previously fell back to Congestion() in the
    # dialplan (extensions_routing.conf.j2) with no indication anywhere in the
    # UI that the DID was silently dead. Block the delete instead.
    blocking_routes = session.exec(
        select(Route).where(
            Route.destination_type == "ring_group",
            Route.destination_id == rg_id,
        )
    ).all()
    if blocking_routes:
        dids = ", ".join(route.did for route in blocking_routes)
        raise HTTPException(
            status_code=409,
            detail=f"Ring group is still used by inbound route(s): {dids}",
        )
    session.delete(existing)
    session.commit()
    summary = run_single_regeneration_step(
        f"ring_groups.delete:{existing.number}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return {"ok": True}
