"""Calls into Home Assistant Core from the add-on (needs `homeassistant_api: true`)."""
import os

import httpx
from fastapi import HTTPException

_CORE_API = "http://supervisor/core/api"


async def call_webhook(url: str, payload: dict) -> None:
    """POSTs JSON to an admin-configured webhook (e.g. HA /api/webhook/<id>). 502 on failure."""
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            response = await client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Webhook nicht erreichbar: {exc}")
    if response.status_code >= 400:
        raise HTTPException(502, f"Webhook fehlgeschlagen (HTTP {response.status_code})")


async def call_service(service: str, entity_id: str) -> None:
    """Runs e.g. `light.turn_on` for one entity. 503 outside HA, 502 when HA refuses."""
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        raise HTTPException(503, "Home Assistant nicht erreichbar (kein SUPERVISOR_TOKEN)")
    domain, name = service.split(".", 1)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{_CORE_API}/services/{domain}/{name}",
                headers={"Authorization": f"Bearer {token}"},
                json={"entity_id": entity_id},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Home Assistant nicht erreichbar: {exc}")
    if response.status_code >= 400:
        raise HTTPException(502, f"Home Assistant: {service} fehlgeschlagen (HTTP {response.status_code})")
