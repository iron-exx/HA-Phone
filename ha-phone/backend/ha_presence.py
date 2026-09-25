"""Doorbell only rings phones of people who are away when nobody is at home.

An extension can belong to a Home Assistant person (`Extension.ha_person`). When a
door station rings a ring group, extensions whose person is away are left out, as
long as at least one configured person is at home. Nobody at home: every phone rings
(the one away can still answer the door). Unknown/unavailable states count as "at
home" for that extension (never silence a phone because HA did not answer).

HA-Phone polls `person.*` via the Supervisor API every minute and re-renders the
dialplan when the set of left-out extensions changes.
"""
from __future__ import annotations

import asyncio
import logging
import os

import httpx
from sqlmodel import Session, select

from backend.database import get_engine
from backend.models import Extension

log = logging.getLogger(__name__)

_CORE_API = "http://supervisor/core/api"
POLL_INTERVAL_S = 60
_HOME = "home"

# Extensions left out of door ring groups right now (read by the dialplan generator).
door_excluded: frozenset[str] = frozenset()


def excluded_extensions(ext_person: dict[str, str], states: dict[str, str | None],
                        home_names: frozenset[str] = frozenset({_HOME})) -> frozenset[str]:
    """ext_person: extension -> person entity. states: person -> HA state (None = unknown).
    home_names: states meaning "at home" ("home" plus the home zone's name, e.g. "Zuhause":
    HA reports a person in zone.home with that zone's friendly name on some installs)."""
    homes = {h.casefold() for h in home_names}
    known = {p: s for p, s in states.items() if s not in (None, "unknown", "unavailable")}
    at_home = {p for p, s in known.items() if s.casefold() in homes}
    if not any(p in at_home for p in ext_person.values()):
        return frozenset()
    return frozenset(ext for ext, person in ext_person.items() if person in known and person not in at_home)


async def fetch_states(persons: set[str], transport: httpx.AsyncBaseTransport | None = None) -> dict[str, str | None]:
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token or not persons:
        return {p: None for p in persons}
    out: dict[str, str | None] = {}
    async with httpx.AsyncClient(timeout=5, transport=transport) as client:
        for person in sorted(persons):
            try:
                resp = await client.get(f"{_CORE_API}/states/{person}", headers={"Authorization": f"Bearer {token}"})
                out[person] = resp.json().get("state") if resp.status_code == 200 else None
            except (httpx.HTTPError, ValueError):
                out[person] = None
    return out


async def fetch_home_name(transport: httpx.AsyncBaseTransport | None = None) -> str | None:
    """Friendly name of zone.home (what a person at home may report as state)."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=5, transport=transport) as client:
            resp = await client.get(f"{_CORE_API}/states/zone.home", headers={"Authorization": f"Bearer {token}"})
        return (resp.json().get("attributes") or {}).get("friendly_name") if resp.status_code == 200 else None
    except (httpx.HTTPError, ValueError):
        return None


def _ext_persons() -> dict[str, str]:
    with Session(get_engine()) as s:
        return {str(e.number): e.ha_person for e in s.exec(select(Extension)).all() if e.ha_person and e.enabled}


async def refresh_once() -> bool:
    """True when the left-out set changed (dialplan re-rendered + reloaded)."""
    global door_excluded
    mapping = _ext_persons()
    states = await fetch_states(set(mapping.values()))
    home_names = frozenset({_HOME} | ({await fetch_home_name()} - {None}))
    now = excluded_extensions(mapping, states, home_names)
    if now == door_excluded:
        return False
    door_excluded = now
    log.info("doorbell presence: left out of door ring groups: %s", sorted(now) or "none")
    from backend import ami
    from backend.routers.time_conditions import _regenerate_routing_conf
    with Session(get_engine()) as s:
        _regenerate_routing_conf(s)
    await ami.ami_reload_dialplan()
    return True


async def watch() -> None:
    while True:
        try:
            await refresh_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("doorbell presence check failed: %s", exc)
        await asyncio.sleep(POLL_INTERVAL_S)
