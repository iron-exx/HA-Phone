"""Admin page "Türklingel": ring history, pictures, snapshot-source test."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from backend import doorbell
from backend.database import get_session
from backend.models import DOORBELL_CAMERA_PATTERN, DoorbellEvent, _match

router = APIRouter(prefix="/doorbell", tags=["doorbell"])


@router.get("")
def list_events(limit: int = 100, session: Session = Depends(get_session)):
    store = doorbell.DoorbellStore(session)
    rows = session.exec(
        select(DoorbellEvent).order_by(DoorbellEvent.started_at.desc()).limit(max(1, min(limit, 500)))
    ).all()
    return [doorbell.event_json(e, store) for e in rows]


@router.get("/{event_id}/image")
def event_image(event_id: int, session: Session = Depends(get_session)):
    ev = session.get(DoorbellEvent, event_id)
    path = doorbell.DoorbellStore(session).image_path(ev) if ev else None
    if not path:
        raise HTTPException(status_code=404, detail="Kein Bild")
    return FileResponse(str(path), media_type="image/png" if path.suffix == ".png" else "image/jpeg")


@router.delete("/{event_id}")
def delete_event(event_id: int, session: Session = Depends(get_session)):
    ev = session.get(DoorbellEvent, event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Nicht gefunden")
    doorbell.DoorbellStore(session).delete(ev)
    return {"deleted": True}


class SnapshotTestIn(BaseModel):
    source: str


# Test hook (httpx.MockTransport in tests).
_transport = None


@router.post("/test-snapshot")
async def test_snapshot(data: SnapshotTestIn):
    """Fetches one picture from a source so the admin sees whether it works."""
    try:
        source = _match(DOORBELL_CAMERA_PATTERN, data.source.strip(), "doorbell_camera")
    except ValueError:
        raise HTTPException(status_code=422, detail="Quelle: camera.name oder http(s)://…")
    image = await doorbell.fetch_snapshot(source, transport=_transport)
    if not image:
        raise HTTPException(status_code=502, detail="Kein Bild erhalten (Adresse, Zugangsdaten oder Kamera prüfen)")
    return Response(content=image[0], media_type=image[1])
