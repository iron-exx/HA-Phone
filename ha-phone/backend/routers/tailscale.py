"""Admin page "Tailscale": connect a Tailscale OAuth client, test it, list and
remove phones in the tailnet. Plus the helpers QR pairing uses to hand out a
per-phone auth key (see mobile_provisioning.py)."""
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend import tailnet
from backend.database import get_session
from backend.models import Extension, MobileDevice, TailnetConfig

log = logging.getLogger(__name__)

router = APIRouter(prefix="/tailscale", tags=["tailscale"])

# Test hook: tests swap in an httpx.MockTransport.
_transport = None


def make_client(client_id: str, client_secret: str) -> tailnet.TailscaleClient:
    return tailnet.TailscaleClient(client_id, client_secret, transport=_transport)


def get_config(session: Session) -> Optional[TailnetConfig]:
    cfg = session.exec(select(TailnetConfig)).first()
    return cfg if cfg and cfg.client_id and cfg.client_secret else None


# ── Helpers for QR pairing / unpairing ─────────────────────────────────────────

def phone_tailscale_block(session: Session, ext: Extension, device: MobileDevice) -> Optional[dict]:
    """The `tailscale` block of the provisioning response, or None (not set up,
    switched off, or the API failed - pairing then continues LAN-only)."""
    cfg = get_config(session)
    if not cfg or not cfg.enabled:
        return None
    addr = tailnet.detect_tailnet_address()
    hostname = tailnet.device_hostname(ext.number, device.device_name)
    try:
        with make_client(cfg.client_id, cfg.client_secret) as c:
            key = c.create_device_key(cfg.tag, f"HA-Phone {ext.number} {device.device_name}")
    except tailnet.TailscaleError as e:
        log.warning("Tailscale key for extension %s failed: %s", ext.number, e.message)
        return None
    return {
        "auth_key": key["key"],
        "control_url": None,
        "hostname": hostname,
        "pbx_tailnet_ip": addr.ipv4,
        "pbx_tailnet_ipv6": addr.ipv6,
        "pbx_magicdns": cfg.pbx_magicdns or None,
        "sip_domain_tailnet": f"{addr.ipv4}:5061" if addr.ipv4 else None,
        "api_base_tailnet": f"http://{addr.ipv4}" if addr.ipv4 else None,
    }


def remove_phone_from_tailnet(session: Session, device: MobileDevice) -> None:
    """Best effort: delete the phone's node. Unpairing never fails because of this."""
    if not device.tailscale_node_id:
        return
    cfg = get_config(session)
    if cfg:
        try:
            with make_client(cfg.client_id, cfg.client_secret) as c:
                c.delete_device(device.tailscale_node_id)
        except tailnet.TailscaleError as e:
            log.warning("could not delete tailnet node %s: %s", device.tailscale_node_id, e.message)
            return
    device.tailscale_node_id = ""
    device.tailscale_ip = ""


# ── Admin API ──────────────────────────────────────────────────────────────────

class TailscaleConfigIn(BaseModel):
    client_id: str
    client_secret: str = ""  # empty = keep the stored one
    tag: str = tailnet.DEFAULT_TAG
    enabled: bool = True


class TailscaleEnabledIn(BaseModel):
    enabled: bool


def _address_dict() -> dict:
    a = tailnet.detect_tailnet_address()
    return {"ipv4": a.ipv4, "ipv6": a.ipv6, "found": not a.missing}


@router.get("/config")
def read_config(session: Session = Depends(get_session)):
    cfg = get_config(session)
    return {
        "configured": cfg is not None,
        "enabled": bool(cfg and cfg.enabled),
        "client_id": cfg.client_id if cfg else "",
        "secret_set": cfg is not None,  # the secret itself never leaves the box
        "tag": cfg.tag if cfg else tailnet.DEFAULT_TAG,
        "tailnet": cfg.tailnet if cfg else "",
        "pbx_magicdns": cfg.pbx_magicdns if cfg else "",
        "pbx": _address_dict(),
        "console_url": tailnet.CONSOLE_TRUST_CREDENTIALS_URL,
        "acl_snippet": tailnet.ACL_SNIPPET,
    }


def _resolve_secret(session: Session, data: TailscaleConfigIn) -> str:
    if data.client_secret:
        return data.client_secret.strip()
    cfg = get_config(session)
    if cfg and cfg.client_id == data.client_id.strip():
        return cfg.client_secret
    raise HTTPException(status_code=422, detail="Client-Secret fehlt.")


def _check(client_id: str, secret: str, tag: str) -> tailnet.CheckResult:
    if not tailnet.valid_tag(tag):
        raise HTTPException(status_code=422, detail="Tag muss wie tag:haphone-phone aussehen.")
    with make_client(client_id, secret) as c:
        return c.check(tag, tailnet.detect_tailnet_address())


@router.post("/test")
def test_config(data: TailscaleConfigIn, session: Session = Depends(get_session)):
    res = _check(data.client_id.strip(), _resolve_secret(session, data), data.tag)
    return {"ok": res.ok, "steps": [s.as_dict() for s in res.steps],
            "tailnet": res.tailnet, "pbx_magicdns": res.pbx_magicdns}


@router.put("/config")
def save_config(data: TailscaleConfigIn, session: Session = Depends(get_session)):
    """Tests first and only saves when every check passed."""
    client_id = data.client_id.strip()
    secret = _resolve_secret(session, data)
    res = _check(client_id, secret, data.tag)
    out = {"ok": res.ok, "steps": [s.as_dict() for s in res.steps],
           "tailnet": res.tailnet, "pbx_magicdns": res.pbx_magicdns}
    if not res.ok:
        return out
    cfg = session.exec(select(TailnetConfig)).first() or TailnetConfig()
    cfg.client_id = client_id
    cfg.client_secret = secret
    cfg.tag = data.tag
    cfg.enabled = data.enabled
    cfg.tailnet = res.tailnet
    cfg.pbx_magicdns = res.pbx_magicdns
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    return out


@router.patch("/config")
def set_enabled(data: TailscaleEnabledIn, session: Session = Depends(get_session)):
    cfg = get_config(session)
    if not cfg:
        raise HTTPException(status_code=404, detail="Tailscale ist nicht eingerichtet.")
    cfg.enabled = data.enabled
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    return {"enabled": cfg.enabled}


@router.delete("/config")
def disconnect(remove_devices: bool = False, session: Session = Depends(get_session)):
    cfg = session.exec(select(TailnetConfig)).first()
    if not cfg:
        return {"removed": 0}
    removed = 0
    if remove_devices and get_config(session):
        for dev in session.exec(select(MobileDevice).where(MobileDevice.tailscale_node_id != "")).all():
            before = dev.tailscale_node_id
            remove_phone_from_tailnet(session, dev)
            if not dev.tailscale_node_id and before:
                removed += 1
                session.add(dev)
    session.delete(cfg)
    session.commit()
    tailnet.TailscaleClient.clear_token_cache()
    return {"removed": removed}


@router.get("/devices")
def list_devices(session: Session = Depends(get_session)):
    """Phones in the tailnet (tagged with our tag), matched to paired app devices."""
    cfg = get_config(session)
    if not cfg:
        raise HTTPException(status_code=404, detail="Tailscale ist nicht eingerichtet.")
    try:
        with make_client(cfg.client_id, cfg.client_secret) as c:
            devices = c.list_devices()
    except tailnet.TailscaleError as e:
        raise HTTPException(status_code=502, detail=e.message)
    paired = {d.tailscale_node_id: d for d in session.exec(
        select(MobileDevice).where(MobileDevice.tailscale_node_id != "")).all()}
    ext_numbers = {e.id: e.number for e in session.exec(select(Extension)).all()}
    out = []
    for d in devices:
        if cfg.tag not in (d.get("tags") or []):
            continue
        node_id = d.get("nodeId") or d.get("id", "")
        mine = paired.get(node_id)
        out.append({
            "id": node_id,
            "hostname": d.get("hostname", ""),
            "name": (d.get("name") or "").rstrip("."),
            "addresses": d.get("addresses") or [],
            "last_seen": d.get("lastSeen"),
            "os": d.get("os", ""),
            "extension_number": ext_numbers.get(mine.extension_id) if mine else None,
            "device_name": mine.device_name if mine else "",
            "app_device_id": mine.id if mine else None,
        })
    return out


@router.delete("/devices/{node_id}")
def remove_device(node_id: str, session: Session = Depends(get_session)):
    cfg = get_config(session)
    if not cfg:
        raise HTTPException(status_code=404, detail="Tailscale ist nicht eingerichtet.")
    try:
        with make_client(cfg.client_id, cfg.client_secret) as c:
            c.delete_device(node_id)
    except tailnet.TailscaleError as e:
        raise HTTPException(status_code=502, detail=e.message)
    for dev in session.exec(select(MobileDevice).where(MobileDevice.tailscale_node_id == node_id)).all():
        dev.tailscale_node_id = ""
        dev.tailscale_ip = ""
        session.add(dev)
    session.commit()
    return {"removed": True}
