import os
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

_SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
_SUPERVISOR_URL = "http://supervisor"


async def _supervisor_get(path: str) -> dict:
    if not _SUPERVISOR_TOKEN:
        raise HTTPException(503, "SUPERVISOR_TOKEN not available — not running inside HA")
    async with httpx.AsyncClient() as client:
        r = await client.get(
            f"{_SUPERVISOR_URL}{path}",
            headers={"Authorization": f"Bearer {_SUPERVISOR_TOKEN}"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json()


async def _supervisor_post(path: str) -> dict:
    if not _SUPERVISOR_TOKEN:
        raise HTTPException(503, "SUPERVISOR_TOKEN not available — not running inside HA")
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{_SUPERVISOR_URL}{path}",
            headers={"Authorization": f"Bearer {_SUPERVISOR_TOKEN}"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()


@router.get("/update/info")
async def update_info():
    data = await _supervisor_get("/addons/self/info")
    addon = data.get("data", {})
    return {
        "version": addon.get("version"),
        "version_latest": addon.get("version_latest"),
        "update_available": addon.get("update_available", False),
    }


@router.post("/update/start")
async def update_start():
    await _supervisor_post("/addons/self/update")
    return {"ok": True}
