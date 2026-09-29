"""Extra preview cameras for the app: the admin picks which Home Assistant cameras
paired phones may show (e.g. garden, driveway); the app then chooses from that list.
Pictures always go through the add-on (Supervisor API), phones never talk to HA."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

import httpx
from sqlmodel import Session, select

from backend import doorbell
from backend.models import PreviewCamera

log = logging.getLogger(__name__)

CAMERA_ENTITY_PATTERN = r"^camera\.[a-z0-9_]{1,120}$"
MAX_SHARED = 12
# HA builds a picture per request (ffmpeg on RTSP cameras: 7-25 s measured on a
# door station), so allow far more than the doorbell's 4 s (the app waits 30 s) and
# share one fetch between phones and thumbnails.
SNAPSHOT_TIMEOUT_S = 25.0
CACHE_S = 2.0
_CORE_API = "http://supervisor/core/api"
# Test hook (httpx.MockTransport in tests).
_transport: Optional[httpx.AsyncBaseTransport] = None


async def list_ha_cameras() -> Optional[list[dict]]:
    """All camera.* entities in HA, sorted by name. None when HA is not reachable."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=10, transport=_transport) as client:
            resp = await client.get(f"{_CORE_API}/states", headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        log.warning("preview cameras: HA states failed: %s", exc.__class__.__name__)
        return None
    if resp.status_code != 200:
        return None
    cameras = [
        {"entity_id": s["entity_id"], "name": (s.get("attributes") or {}).get("friendly_name") or s["entity_id"]}
        for s in resp.json() if str(s.get("entity_id", "")).startswith("camera.")
    ]
    return sorted(cameras, key=lambda c: c["name"].lower())


def _json(cam: PreviewCamera) -> dict:
    return {"entity_id": cam.entity_id, "name": cam.name or cam.entity_id}


def shared(session: Session) -> list[dict]:
    rows = session.exec(select(PreviewCamera).order_by(PreviewCamera.position)).all()
    return [_json(c) for c in rows]


def replace_shared(session: Session, cameras: list[tuple[str, str]]) -> None:
    """cameras: validated (entity_id, name) pairs in display order."""
    for old in session.exec(select(PreviewCamera)).all():
        session.delete(old)
    session.flush()
    for position, (entity_id, name) in enumerate(cameras):
        session.add(PreviewCamera(entity_id=entity_id, name=name, position=position))
    session.commit()


def is_shared(session: Session, entity_id: str) -> bool:
    return session.exec(select(PreviewCamera).where(PreviewCamera.entity_id == entity_id)).first() is not None


_cache: dict[str, tuple[float, tuple[bytes, str]]] = {}
_locks: dict[str, asyncio.Lock] = {}

# While a door rings, the shared cameras are fetched back to back in the background
# (doorbell_listener starts/ends it), so the ringing phones get the newest finished
# picture at once instead of each waiting 7-25 s for HA.
WARM_MAX_S = 90.0        # safety stop if the Ended event is lost
WARM_PAUSE_S = 0.5       # between two rounds
WARM_MAX_AGE_S = 30.0    # older pictures are fetched on demand as usual
_rings: dict[str, float] = {}   # ringing door channel -> deadline
_warm_ids: list[str] = []
_warm_task: Optional[asyncio.Task] = None


async def _fetch_into_cache(entity_id: str) -> Optional[tuple[bytes, str]]:
    lock = _locks.setdefault(entity_id, asyncio.Lock())
    async with lock:
        hit = _cache.get(entity_id)
        if hit and time.monotonic() - hit[0] < CACHE_S:
            return hit[1]
        image = await doorbell.fetch_snapshot(entity_id, transport=_transport, timeout=SNAPSHOT_TIMEOUT_S)
        if image:
            _cache[entity_id] = (time.monotonic(), image)
        else:
            _cache.pop(entity_id, None)
        return image


def _warming() -> bool:
    now = time.monotonic()
    for uid in [u for u, deadline in _rings.items() if deadline < now]:
        _rings.pop(uid, None)
    return bool(_rings)


async def _warm_loop() -> None:
    global _warm_task
    try:
        while _warming():
            await asyncio.gather(*(_fetch_into_cache(e) for e in list(_warm_ids)))
            await asyncio.sleep(WARM_PAUSE_S)
    except Exception:
        log.exception("preview cameras: warm-up failed")
    finally:
        _warm_task = None


def ring_started(uniqueid: str, entity_ids: list[str]) -> None:
    """A door rings: keep [entity_ids] fresh until ring_ended (or WARM_MAX_S)."""
    global _warm_ids, _warm_task
    if not entity_ids:
        return
    _warm_ids = list(entity_ids)
    _rings[uniqueid] = time.monotonic() + WARM_MAX_S
    if _warm_task is not None:
        return
    try:
        _warm_task = asyncio.get_running_loop().create_task(_warm_loop())
    except RuntimeError:  # no event loop (unit tests call the listener synchronously)
        _rings.pop(uniqueid, None)


def ring_ended(uniqueid: str) -> None:
    _rings.pop(uniqueid, None)


async def snapshot(entity_id: str) -> Optional[tuple[bytes, str]]:
    """Current picture; requests within CACHE_S (or waiting on a running fetch) share it.
    While a door rings, the newest warmed picture is returned without waiting."""
    if _warming():
        hit = _cache.get(entity_id)
        if hit and time.monotonic() - hit[0] < WARM_MAX_AGE_S:
            return hit[1]
    return await _fetch_into_cache(entity_id)
