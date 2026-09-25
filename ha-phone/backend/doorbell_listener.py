"""Feeds AMI events into the doorbell history (doorbell.py).

Own long-lived AMI connection with events on; the request/response connection in
ami.py stays untouched. panoramisk reconnects by itself after an Asterisk restart,
the loop here only covers the very first connect.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time

from sqlmodel import Session, select

from backend import doorbell
from backend.database import get_engine
from backend.models import Extension

log = logging.getLogger(__name__)

DOOR_CACHE_S = 30
PRUNE_EVERY_S = 3600
_EVENTS = ("Newchannel", "DialEnd", "Hangup")


def listener_enabled() -> bool:
    return os.environ.get("BPX_DOORBELL_LISTENER", "1") != "0"


class DoorbellListener:
    def __init__(self, fetch=doorbell.fetch_snapshot):
        self._fetch = fetch
        self._doors: set[str] = set()
        self._doors_at = 0.0
        self._event_of: dict[str, int] = {}  # door channel Uniqueid -> DoorbellEvent.id
        self._last_prune = 0.0
        self.tracker = doorbell.DoorbellTracker(self._is_door)
        self._tasks: set[asyncio.Task] = set()

    def _is_door(self, number: str) -> bool:
        now = time.monotonic()
        if now - self._doors_at > DOOR_CACHE_S:
            with Session(get_engine()) as s:
                self._doors = {str(e.number) for e in s.exec(select(Extension)).all() if doorbell.is_door(e)}
            self._doors_at = now
        return number in self._doors

    def handle(self, ev: dict) -> None:
        """One AMI event (dict-like). Never raises into panoramisk."""
        try:
            for action in self.tracker.on_event(ev):
                self._apply(action)
        except Exception:
            log.exception("doorbell: event %s failed", ev.get("Event"))

    def _apply(self, action) -> None:
        with Session(get_engine()) as s:
            store = doorbell.DoorbellStore(s)
            if isinstance(action, doorbell.Ring):
                event = store.record_ring(int(action.door))
                self._event_of[action.uniqueid] = event.id
                log.info("doorbell: %s rings (event %s)", action.door, event.id)
                door = s.exec(select(Extension).where(Extension.number == int(action.door))).first()
                source = door.doorbell_camera if door else ""
                if source:
                    self._spawn(self._snapshot(event.id, source))
            elif isinstance(action, doorbell.Answered):
                event_id = self._event_of.get(action.uniqueid)
                if event_id:
                    store.mark_answered(event_id, action.by)
            elif isinstance(action, doorbell.Ended):
                event_id = self._event_of.pop(action.uniqueid, None)
                if event_id:
                    store.mark_ended(event_id)
                if time.monotonic() - self._last_prune > PRUNE_EVERY_S:
                    self._last_prune = time.monotonic()
                    store.prune()

    def _spawn(self, coro) -> None:
        try:
            task = asyncio.get_running_loop().create_task(coro)
        except RuntimeError:  # no loop (unit tests call handle() synchronously)
            coro.close()
            return
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _snapshot(self, event_id: int, source: str) -> None:
        image = await self._fetch(source)
        if not image:
            return
        with Session(get_engine()) as s:
            doorbell.DoorbellStore(s).save_image(event_id, *image)

    async def run(self) -> None:
        from panoramisk import Manager
        from backend.ami import _read_ami_secret

        delay = 2
        while True:
            manager = Manager(host="127.0.0.1", port=5038, username="bpx-admin",
                              secret=_read_ami_secret(), events="on")
            for name in _EVENTS:
                manager.register_event(name, lambda _m, msg: self.handle(dict(msg)))
            try:
                await manager.connect()
                log.info("doorbell: AMI event listener connected")
                delay = 2
                # panoramisk keeps the connection (and reconnects) on its own.
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                manager.close()
                raise
            except Exception as exc:
                log.warning("doorbell: AMI listener not connected (%s), retry in %ss", exc, delay)
                manager.close()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 60)
