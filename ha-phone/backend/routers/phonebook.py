import csv
import io
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from fastapi.responses import Response
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import PhonebookEntry

router = APIRouter()

_CSV_FIELDS = ["name", "number", "notes"]


@router.get("/phonebook/ldap-info")
def ldap_info(request: Request):
    """Connection details for the embedded LDAP phonebook server (see
    backend/ldap_server.py) - so the UI can show them instead of making
    users dig through the changelog to configure a phone/DECT base by hand.
    Host is taken the same way as the public provisioning endpoints (never
    an HA-ingress host/port - a phone can't reach those)."""
    from backend.ldap_server import ldap_port_from_env

    forwarded_host = request.headers.get("x-forwarded-host", "")
    host = forwarded_host.split(",")[0].strip() if forwarded_host else (request.url.hostname or "pbx.local")
    if host.startswith("[") and "]" in host:
        host = host[1 : host.index("]")]
    elif host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return {
        "host": host,
        "port": ldap_port_from_env(),
        "base_dn": "dc=phonebook",
        "auth": "anonymous",
        "name_filter": "(|(cn=%s)(sn=%s)(givenName=%s))",
        "number_filter": "(telephoneNumber=%s)",
    }


@router.get("/phonebook", response_model=List[PhonebookEntry])
def list_entries(session: Session = Depends(get_session)):
    return sorted(session.exec(select(PhonebookEntry)).all(), key=lambda e: e.name.lower())


@router.post("/phonebook", response_model=PhonebookEntry)
def create_entry(entry: PhonebookEntry, session: Session = Depends(get_session)):
    if not entry.name.strip() or not entry.number.strip():
        raise HTTPException(status_code=422, detail="name and number are required")
    entry.id = None
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


@router.patch("/phonebook/{entry_id}", response_model=PhonebookEntry)
def update_entry(entry_id: int, data: PhonebookEntry, session: Session = Depends(get_session)):
    existing = session.get(PhonebookEntry, entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Phonebook entry not found")
    for field, value in data.model_dump(exclude_unset=True, exclude_none=True).items():
        if field != "id":
            setattr(existing, field, value)
    if not existing.name.strip() or not existing.number.strip():
        raise HTTPException(status_code=422, detail="name and number are required")
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


@router.delete("/phonebook/{entry_id}")
def delete_entry(entry_id: int, session: Session = Depends(get_session)):
    existing = session.get(PhonebookEntry, entry_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Phonebook entry not found")
    session.delete(existing)
    session.commit()
    return {"ok": True}


@router.get("/phonebook/export")
def export_csv(session: Session = Depends(get_session)):
    entries = sorted(session.exec(select(PhonebookEntry)).all(), key=lambda e: e.name.lower())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for e in entries:
        writer.writerow({"name": e.name, "number": e.number, "notes": e.notes})
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="ha-phone-phonebook.csv"'},
    )


@router.post("/phonebook/import")
async def import_csv(file: UploadFile = File(...), session: Session = Depends(get_session)):
    """Upsert by number: a row whose number already exists updates that
    entry's name/notes instead of creating a duplicate - re-importing an
    updated export (or a partial list) doesn't pile up duplicates."""
    raw = (await file.read()).decode("utf-8-sig", errors="replace")
    try:
        reader = csv.DictReader(io.StringIO(raw))
    except csv.Error as exc:
        raise HTTPException(status_code=422, detail=f"Invalid CSV: {exc}")

    if reader.fieldnames is None or "name" not in reader.fieldnames or "number" not in reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV must have 'name' and 'number' columns")

    existing_by_number = {e.number: e for e in session.exec(select(PhonebookEntry)).all()}
    created, updated, skipped = 0, 0, 0

    for row in reader:
        name = (row.get("name") or "").strip()
        number = (row.get("number") or "").strip()
        notes = (row.get("notes") or "").strip()
        if not name or not number:
            skipped += 1
            continue
        if number in existing_by_number:
            entry = existing_by_number[number]
            entry.name = name
            entry.notes = notes
            session.add(entry)
            updated += 1
        else:
            entry = PhonebookEntry(name=name, number=number, notes=notes)
            session.add(entry)
            existing_by_number[number] = entry
            created += 1
    session.commit()
    return {"ok": True, "created": created, "updated": updated, "skipped": skipped}
