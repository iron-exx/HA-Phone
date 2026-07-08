import csv
import io
from datetime import date as _date
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import Holiday
from backend.regeneration import run_single_regeneration_step, step_succeeded
from backend.routers.time_conditions import _regenerate_routing_conf
from backend import ami

router = APIRouter()

_CSV_FIELDS = ["name", "year", "month", "day"]


def _validate_date(year: int, month: int, day: int) -> None:
    # SQLModel table=True models do NOT enforce Field(ge=, le=) constraints on
    # plain construction (a known quirk - see numbering.py/D5 for the same
    # pattern with extension/ring-group/IVR numbers), so this has to be
    # checked explicitly rather than relying on the model's Field() bounds.
    if not (1970 <= year <= 2200):
        raise HTTPException(status_code=422, detail="year must be between 1970 and 2200")
    if not (1 <= month <= 12):
        raise HTTPException(status_code=422, detail="month must be between 1 and 12")
    if not (1 <= day <= 31):
        raise HTTPException(status_code=422, detail="day must be between 1 and 31")
    try:
        _date(year, month, day)
    except ValueError:
        raise HTTPException(status_code=422, detail="not a real calendar date")


@router.get("/holidays", response_model=List[Holiday])
def list_holidays(session: Session = Depends(get_session)):
    return sorted(session.exec(select(Holiday)).all(), key=lambda h: (h.year, h.month, h.day))


@router.post("/holidays", response_model=Holiday)
async def create_holiday(holiday: Holiday, session: Session = Depends(get_session)):
    _validate_date(holiday.year, holiday.month, holiday.day)
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
    _validate_date(
        updates.get("year", existing.year),
        updates.get("month", existing.month),
        updates.get("day", existing.day),
    )
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


@router.get("/holidays/export")
def export_csv(session: Session = Depends(get_session)):
    holidays = sorted(session.exec(select(Holiday)).all(), key=lambda h: (h.year, h.month, h.day))
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for h in holidays:
        writer.writerow({"name": h.name, "year": h.year, "month": h.month, "day": h.day})
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ha-phone-holidays.csv"'},
    )


@router.post("/holidays/import")
async def import_csv(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """Upsert by (year, month, day): re-importing a previous export (or an
    updated list with corrected names) doesn't pile up duplicate entries for
    the same date."""
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    try:
        reader = csv.DictReader(io.StringIO(raw))
    except csv.Error as exc:
        raise HTTPException(status_code=422, detail=f"Invalid CSV: {exc}")

    required = {"name", "year", "month", "day"}
    if reader.fieldnames is None or not required.issubset(reader.fieldnames):
        raise HTTPException(status_code=422, detail="CSV must have 'name', 'year', 'month' and 'day' columns")

    existing_by_date = {(h.year, h.month, h.day): h for h in session.exec(select(Holiday)).all()}
    created, updated, skipped = 0, 0, 0

    for row in reader:
        name = (row.get("name") or "").strip()
        try:
            year = int((row.get("year") or "").strip())
            month = int((row.get("month") or "").strip())
            day = int((row.get("day") or "").strip())
        except ValueError:
            skipped += 1
            continue
        if not name or not (1970 <= year <= 2200) or not (1 <= month <= 12) or not (1 <= day <= 31):
            skipped += 1
            continue
        try:
            _date(year, month, day)
        except ValueError:
            skipped += 1
            continue

        key = (year, month, day)
        if key in existing_by_date:
            holiday = existing_by_date[key]
            holiday.name = name
            session.add(holiday)
            updated += 1
        else:
            holiday = Holiday(name=name, year=year, month=month, day=day)
            session.add(holiday)
            existing_by_date[key] = holiday
            created += 1
    session.commit()

    summary = run_single_regeneration_step(
        "holidays.import",
        "routing",
        lambda: _regenerate_routing_conf(session),
    )
    if step_succeeded(summary, "routing"):
        await ami.ami_reload_dialplan()
    return {"ok": True, "created": created, "updated": updated, "skipped": skipped}
