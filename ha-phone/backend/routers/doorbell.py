"""Admin page "Türklingel": ring history, pictures, snapshot-source test, and the
cameras shared with the app (preview_cameras.py)."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from sqlmodel import Session, select

from backend import doorbell, preview_cameras
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


# ── Cameras shared with the app ───────────────────────────────────────────────

class SharedCameraIn(BaseModel):
    entity_id: str = Field(pattern=preview_cameras.CAMERA_ENTITY_PATTERN)
    name: str = Field(default="", max_length=64)


class SharedCamerasIn(BaseModel):
    cameras: list[SharedCameraIn] = Field(max_length=preview_cameras.MAX_SHARED)

    @field_validator("cameras")
    @classmethod
    def _unique(cls, cameras: list[SharedCameraIn]) -> list[SharedCameraIn]:
        if len({c.entity_id for c in cameras}) != len(cameras):
            raise ValueError("Kamera doppelt in der Liste")
        return cameras


@router.get("/ha-cameras")
async def ha_cameras():
    """All camera.* entities in Home Assistant, to pick from."""
    cameras = await preview_cameras.list_ha_cameras()
    if cameras is None:
        raise HTTPException(status_code=503, detail="Home Assistant nicht erreichbar")
    return cameras


@router.get("/preview-cameras")
def get_preview_cameras(session: Session = Depends(get_session)):
    return preview_cameras.shared(session)


@router.put("/preview-cameras")
def set_preview_cameras(data: SharedCamerasIn, session: Session = Depends(get_session)):
    preview_cameras.replace_shared(session, [(c.entity_id, c.name.strip()) for c in data.cameras])
    return preview_cameras.shared(session)
