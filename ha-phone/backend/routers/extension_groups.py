from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import ExtensionGroup, RingGroup
from backend.regeneration import run_single_regeneration_step, step_succeeded
from backend.routers.ring_groups import _validate_extension_numbers
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()


@router.get("/extension-groups", response_model=List[ExtensionGroup])
def list_extension_groups(session: Session = Depends(get_session)):
    return session.exec(select(ExtensionGroup)).all()


@router.post("/extension-groups", response_model=ExtensionGroup)
async def create_extension_group(group: ExtensionGroup, session: Session = Depends(get_session)):
    numbers = _validate_extension_numbers(group.extension_numbers, session, allow_empty=True)
    group.extension_numbers = ",".join(str(number) for number in numbers)
    group.id = None
    session.add(group)
    session.commit()
    session.refresh(group)
    return group


@router.patch("/extension-groups/{group_id}", response_model=ExtensionGroup)
async def update_extension_group(
    group_id: int, group_data: ExtensionGroup, session: Session = Depends(get_session)
):
    existing = session.get(ExtensionGroup, group_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Extension group not found")
    for field, value in group_data.model_dump(exclude_unset=True).items():
        if field != "id":
            setattr(existing, field, value)
    numbers = _validate_extension_numbers(existing.extension_numbers, session, allow_empty=True)
    existing.extension_numbers = ",".join(str(number) for number in numbers)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    # A ring group referencing this extension group dials its members, so
    # membership changes must regenerate the dialplan too.
    summary = run_single_regeneration_step(
        f"extension_groups.update:{existing.id}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return existing


@router.delete("/extension-groups/{group_id}")
async def delete_extension_group(group_id: int, session: Session = Depends(get_session)):
    existing = session.get(ExtensionGroup, group_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Extension group not found")
    # Referential integrity, same convention as ring_groups.py's delete guard:
    # block deleting a group still referenced by a RingGroup's members instead
    # of silently leaving a dangling id that resolves to nothing.
    blocking_ring_groups = [
        rg
        for rg in session.exec(select(RingGroup)).all()
        if str(group_id) in [g.strip() for g in rg.extension_group_ids.split(",") if g.strip()]
    ]
    if blocking_ring_groups:
        names = ", ".join(rg.name for rg in blocking_ring_groups)
        raise HTTPException(
            status_code=409,
            detail=f"Extension group is still used by ring group(s): {names}",
        )
    session.delete(existing)
    session.commit()
    return {"ok": True}
