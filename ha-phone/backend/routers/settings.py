import os
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter
from pydantic import BaseModel

from backend.conf_generator import render_conf
from backend import ami

router = APIRouter()

_ip_cache: Optional[tuple[str, float]] = None
CACHE_TTL = 300  # 5 minutes


async def detect_public_ip() -> Optional[str]:
    global _ip_cache
    if _ip_cache and (time.time() - _ip_cache[1]) < CACHE_TTL:
        return _ip_cache[0]
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        for url in ["https://api4.ipify.org", "https://icanhazip.com"]:
            try:
                resp = await client.get(url)
                ip = resp.text.strip()
                if ip:
                    _ip_cache = (ip, time.time())
                    return ip
            except Exception:
                continue
    return None


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


class PublicIPRequest(BaseModel):
    ip: str


@router.get("/settings/public-ip")
async def get_public_ip():
    """Auto-detect public IP and return it."""
    ip = await detect_public_ip()
    return {"ip": ip}


@router.post("/settings/public-ip")
async def save_public_ip(body: PublicIPRequest):
    """Write pjsip_local.conf with the given IP, then trigger AMI reload."""
    output_path = _data_dir() / "asterisk" / "pjsip_local.conf"
    render_conf("pjsip_local.conf.j2", {"ip": body.ip}, output_path)
    await ami.ami_reload_pjsip()
    return {"ok": True, "ip": body.ip}


@router.get("/status/active-calls")
async def get_active_calls():
    """Returns the count of active calls via AMI CoreShowChannels. Covers UI-01 Anrufzähler."""
    count = await ami.get_active_call_count()
    return {"count": count}
