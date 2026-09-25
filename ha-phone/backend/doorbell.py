"""Doorbell history: every ring at a door station with time, who answered, whether the
door was opened, and a picture.

The PBX sees rings through AMI events (doorbell_listener.py feeds them in):
  Newchannel of the door's own endpoint, placing a call  -> a ring starts
  DialEnd with DialStatus=ANSWER for that call           -> answered by DestCallerIDNum
  Hangup of the door's channel                           -> ring over
A ring group produces one Newchannel for the door and one DialEnd per called device,
so there is exactly one event per ring.

The picture comes from the door's `doorbell_camera`: a Home Assistant camera entity
(camera.xyz, via the Supervisor API) or the door station's own snapshot URL.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlsplit, urlunsplit

import httpx
from sqlmodel import Session, select

from backend.models import DoorbellEvent, Extension

log = logging.getLogger(__name__)

RETENTION_DAYS = 30
MAX_EVENTS = 500
MAX_IMAGE_BYTES = 2 * 1024 * 1024
SNAPSHOT_TIMEOUT_S = 4.0
OPENED_WINDOW = timedelta(minutes=5)
_CORE_API = "http://supervisor/core/api"
_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png"}


def image_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return (Path(d) if d else Path("/data")) / "doorbell"


def is_door(ext: Extension) -> bool:
    """Same meaning as in the app: something that makes this extension a door station."""
    try:
        actions = json.loads(ext.door_actions or "[]")
    except ValueError:
        actions = []
    return bool(ext.door_open_code or ext.door_open_webhook or actions or ext.doorbell_camera)


# ── AMI event state machine (no I/O) ───────────────────────────────────────────

@dataclass(frozen=True)
class Ring:
    uniqueid: str
    door: str


@dataclass(frozen=True)
class Answered:
    uniqueid: str
    by: str


@dataclass(frozen=True)
class Ended:
    uniqueid: str


_ENDPOINT_RE = re.compile(r"^PJSIP/([^-]+)-")


class DoorbellTracker:
    def __init__(self, is_door_number: Callable[[str], bool]):
        self._is_door = is_door_number
        self._active: dict[str, bool] = {}  # door channel Uniqueid -> answered yet

    def on_event(self, ev: dict) -> list:
        name = ev.get("Event", "")
        if name == "Newchannel":
            m = _ENDPOINT_RE.match(ev.get("Channel", ""))
            door = m.group(1) if m else ""
            uid = ev.get("Uniqueid", "")
            # The door's own endpoint placing a call. A call TO the door (app calls the
            # door) has the caller's channel as the originator and is not a ring.
            if (door and uid and uid not in self._active and self._is_door(door)
                    and ev.get("CallerIDNum", "") == door and ev.get("Exten", "") != door):
                self._active[uid] = False
                return [Ring(uid, door)]
            return []
        if name == "DialEnd":
            uid = ev.get("Uniqueid", "")
            if uid in self._active and not self._active[uid] and ev.get("DialStatus") == "ANSWER":
                self._active[uid] = True
                return [Answered(uid, ev.get("DestCallerIDNum", "") or ev.get("DestExten", ""))]
            return []
        if name == "Hangup":
            uid = ev.get("Uniqueid", "")
            if uid in self._active:
                del self._active[uid]
                return [Ended(uid)]
        return []


# ── Snapshot ───────────────────────────────────────────────────────────────────

def _split_userinfo(url: str) -> tuple[str, Optional[tuple[str, str]]]:
    parts = urlsplit(url)
    if parts.username is None:
        return url, None
    host = parts.hostname or ""
    if parts.port:
        host = f"{host}:{parts.port}"
    clean = urlunsplit((parts.scheme, host, parts.path, parts.query, parts.fragment))
    return clean, (parts.username, parts.password or "")


def _image_or_none(resp: httpx.Response) -> Optional[tuple[bytes, str]]:
    if resp.status_code != 200:
        log.warning("doorbell snapshot: HTTP %s", resp.status_code)
        return None
    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if ctype not in _IMAGE_TYPES:
        log.warning("doorbell snapshot: not an image (%s)", ctype or "no content-type")
        return None
    if len(resp.content) > MAX_IMAGE_BYTES:
        log.warning("doorbell snapshot: %d bytes, too large", len(resp.content))
        return None
    return resp.content, ctype


async def fetch_snapshot(source: str, *, transport: httpx.AsyncBaseTransport | None = None
                         ) -> Optional[tuple[bytes, str]]:
    """(image bytes, content type) or None. Never raises."""
    source = (source or "").strip()
    if not source:
        return None
    try:
        async with httpx.AsyncClient(timeout=SNAPSHOT_TIMEOUT_S, transport=transport,
                                     follow_redirects=False) as client:
            if source.startswith("camera."):
                token = os.environ.get("SUPERVISOR_TOKEN", "")
                if not token:
                    log.warning("doorbell snapshot: no SUPERVISOR_TOKEN for %s", source)
                    return None
                resp = await client.get(f"{_CORE_API}/camera_proxy/{source}",
                                        headers={"Authorization": f"Bearer {token}"})
                return _image_or_none(resp)
            url, creds = _split_userinfo(source)
            resp = await client.get(url, auth=httpx.BasicAuth(*creds) if creds else None)
            if resp.status_code == 401 and creds and "digest" in resp.headers.get("www-authenticate", "").lower():
                resp = await client.get(url, auth=httpx.DigestAuth(*creds))
            return _image_or_none(resp)
    except httpx.HTTPError as exc:
        log.warning("doorbell snapshot from %s failed: %s", source.split("@")[-1], exc.__class__.__name__)
        return None


# ── Storage ────────────────────────────────────────────────────────────────────

class DoorbellStore:
    def __init__(self, session: Session):
        self.s = session

    def record_ring(self, door_number: int) -> DoorbellEvent:
        door = self.s.exec(select(Extension).where(Extension.number == door_number)).first()
        ev = DoorbellEvent(door_number=door_number, door_name=door.display_name if door else "")
        self.s.add(ev)
        self.s.commit()
        self.s.refresh(ev)
        return ev

    def _get(self, event_id: int) -> Optional[DoorbellEvent]:
        return self.s.get(DoorbellEvent, event_id)

    def mark_answered(self, event_id: int, by: str) -> None:
        ev = self._get(event_id)
        if ev and not ev.answered_by:
            ev.answered_by = by[:64]
            self.s.add(ev)
            self.s.commit()

    def mark_ended(self, event_id: int) -> None:
        ev = self._get(event_id)
        if ev and ev.ended_at is None:
            ev.ended_at = datetime.utcnow()
            self.s.add(ev)
            self.s.commit()

    def mark_opened(self, door_number: int, now: Optional[datetime] = None) -> bool:
        now = now or datetime.utcnow()
        ev = self.s.exec(
            select(DoorbellEvent).where(DoorbellEvent.door_number == door_number)
            .order_by(DoorbellEvent.started_at.desc())
        ).first()
        if not ev or now - ev.started_at > OPENED_WINDOW:
            return False
        ev.door_opened = True
        self.s.add(ev)
        self.s.commit()
        return True

    def save_image(self, event_id: int, data: bytes, content_type: str) -> None:
        ev = self._get(event_id)
        if not ev:
            return
        directory = image_dir()
        directory.mkdir(parents=True, exist_ok=True)
        name = f"{ev.id}{_IMAGE_TYPES.get(content_type, '.jpg')}"
        (directory / name).write_bytes(data)
        ev.image_file = name
        self.s.add(ev)
        self.s.commit()

    def image_path(self, ev: DoorbellEvent) -> Optional[Path]:
        if not ev.image_file:
            return None
        path = image_dir() / Path(ev.image_file).name
        return path if path.is_file() else None

    def delete(self, ev: DoorbellEvent) -> None:
        path = self.image_path(ev)
        if path:
            path.unlink(missing_ok=True)
        self.s.delete(ev)
        self.s.commit()

    def prune(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.utcnow()
        cutoff = now - timedelta(days=RETENTION_DAYS)
        events = self.s.exec(select(DoorbellEvent).order_by(DoorbellEvent.started_at.desc())).all()
        doomed = [e for i, e in enumerate(events) if i >= MAX_EVENTS or e.started_at < cutoff]
        for ev in doomed:
            path = self.image_path(ev)
            if path:
                path.unlink(missing_ok=True)
            self.s.delete(ev)
        if doomed:
            self.s.commit()
        return len(doomed)


def event_json(ev: DoorbellEvent, store: DoorbellStore) -> dict:
    return {
        "id": ev.id,
        "door_number": ev.door_number,
        "door_name": ev.door_name,
        "started_at": ev.started_at.isoformat() + "Z",
        "ended_at": ev.ended_at.isoformat() + "Z" if ev.ended_at else None,
        "answered_by": ev.answered_by,
        "door_opened": ev.door_opened,
        "has_image": store.image_path(ev) is not None,
    }
