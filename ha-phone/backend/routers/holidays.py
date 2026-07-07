from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Holiday
from backend.regeneration import run_single_regeneration_step, step_succeeded
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()


def _validate_month_day(month: int, day: int) -> None:
    # SQLModel table=True models do NOT enforce Field(ge=, le=) constraints on
    # plain construction (a known quirk - see numbering.py/D5 for the same
    # pattern with extension/ring-group/IVR numbers), so this has to be
    # checked explicitly rather than relying on the model's Field() bounds.
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="month must be between 1 and 12")
    if not (1 <= day <= 31):
        raise HTTPException(status_code=422, detail="day must be between 1 and 31")


@router.get("/holidays", response_model=List[Holiday])
def list_holidays(session: Session = Depends(get_session)):
    return sorted(session.exec(select(Holiday)).all(), key=lambda h: (h.month, h.day))


@router.post("/holidays", response_model=Holiday)
async def create_holiday(holiday: Holiday, session: Session = Depends(get_session)):
    _validate_month_day(holiday.month, holiday.day)
    holiday.id = None
    session.add(holiday)
    session.commit()
    session.refresh(holiday)
    summary = run_single_regeneration_step(
        f"holidays.create:{holiday.month}-{holiday.day}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return holiday


@router.patch("/holidays/{holiday_id}", response_model=Holiday)
async def update_holiday(holiday_id: int, data: Holiday, session: Session = Depends(get_session)):
    existing = session.get(Holiday, holiday_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Holiday not found")
    updates = data.model_dump(exclude_unset=True, exclude_none=True)
    _validate_month_day(updates.get("month", existing.month), updates.get("day", existing.day))
    for field, value in updates.items():
        if field != "id":
            setattr(existing, field, value)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    summary = run_single_regeneration_step(
        f"holidays.update:{existing.id}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return existing


@router.delete("/holidays/{holiday_id}")
async def delete_holiday(holiday_id: int, session: Session = Depends(get_session)):
    existing = session.get(Holiday, holiday_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Holiday not found")
    session.delete(existing)
    session.commit()
    summary = run_single_regeneration_step(
        f"holidays.delete:{holiday_id}",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return {"ok": True}
