import os

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

_SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
_SUPERVISOR_URL = "http://supervisor"


def _supervisor_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        message = body.get("message") or body.get("error") or body.get("result")
        if message:
            return str(message)
    except (AttributeError, ValueError):
        pass
    text = response.text.strip()
    return text or f"Supervisor request failed with HTTP {response.status_code}"


async def _supervisor_request(method: str, path: str, timeout: int) -> dict:
    if not _SUPERVISOR_TOKEN:
        raise HTTPException(503, "SUPERVISOR_TOKEN not available - not running inside HA")
    async with httpx.AsyncClient() as client:
        try:
            response = await client.request(
                method,
                f"{_SUPERVISOR_URL}{path}",
                headers={"Authorization": f"Bearer {_SUPERVISOR_TOKEN}"},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                exc.response.status_code,
                f"{path}: {_supervisor_error_message(exc.response)}",
            )
        except httpx.HTTPError as exc:
            raise HTTPException(502, f"{path}: Supervisor request failed: {exc}")


async def _supervisor_get(path: str) -> dict:
    return await _supervisor_request("GET", path, timeout=10)


async def _supervisor_post(path: str) -> dict:
    return await _supervisor_request("POST", path, timeout=30)


async def _supervisor_first(method: str, paths: list[str]) -> dict:
    last_error: HTTPException | None = None
    for path in paths:
        try:
            if method == "GET":
                return await _supervisor_get(path)
            return await _supervisor_post(path)
        except HTTPException as exc:
            last_error = exc
            if exc.status_code not in (404, 405):
                raise
    assert last_error is not None
    raise last_error


@router.get("/update/info")
async def update_info():
    data = await _supervisor_first("GET", ["/apps/self/info", "/addons/self/info"])
    app = data.get("data", {})
    return {
        "version": app.get("version"),
        "version_latest": app.get("version_latest"),
        "update_available": app.get("update_available", False),
    }


@router.post("/update/start")
async def update_start():
    await _supervisor_first("POST", ["/apps/self/update", "/addons/self/update"])
    return {"ok": True}
