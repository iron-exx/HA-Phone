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
from backend.pjsip_local import TAILNET_SIP_PORT
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

def get_settings(session: Session) -> TailnetConfig:
    """The single settings row (may exist without an OAuth client)."""
    return session.exec(select(TailnetConfig)).first() or TailnetConfig()


def phone_tailscale_block(session: Session, ext: Extension, device: MobileDevice) -> Optional[dict]:
    """The `tailscale` block of the provisioning response, or None (Tailscale not on
    the box, or switched off - pairing then stays LAN-only).

    login = "auth_key": HA-Phone has an OAuth client and created a one-time key, the
    phone joins without any interaction. login = "interactive": no OAuth client (or
    the API failed), the phone shows Tailscale's login page once.
    """
    settings = get_settings(session)
    if not settings.enabled:
        return None
    addr = tailnet.detect_tailnet_address()
    if addr.missing:
        return None
    block = {
        "login": "interactive",
        "auth_key": None,
        "control_url": None,
        "hostname": tailnet.device_hostname(ext.number, device.device_name),
        "pbx_tailnet_ip": addr.ipv4,
        "pbx_tailnet_ipv6": addr.ipv6,
        "pbx_magicdns": settings.pbx_magicdns or None,
        # Own transport with the tailnet address in Contact/SDP (pjsip_local.conf.j2).
        "sip_domain_tailnet": f"{addr.ipv4}:{TAILNET_SIP_PORT}" if addr.ipv4 else None,
        "sip_port_tailnet": TAILNET_SIP_PORT,
        "api_base_tailnet": f"http://{addr.ipv4}" if addr.ipv4 else None,
    }
    cfg = get_config(session)
    if cfg:
        try:
            with make_client(cfg.client_id, cfg.client_secret) as c:
                key = c.create_device_key(cfg.tag, f"HA-Phone {ext.number} {device.device_name}")
            block["login"] = "auth_key"
            block["auth_key"] = key["key"]
        except tailnet.TailscaleError as e:
            log.warning("Tailscale key for extension %s failed, phone logs in itself: %s", ext.number, e.message)
    return block


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
    settings = get_settings(session)
    return {
        "configured": cfg is not None,
        "enabled": settings.enabled,
        "client_id": cfg.client_id if cfg else "",
        "secret_set": cfg is not None,  # the secret itself never leaves the box
        "tag": cfg.tag if cfg else tailnet.DEFAULT_TAG,
        "tailnet": settings.tailnet,
        "pbx_magicdns": settings.pbx_magicdns,
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
    settings = get_settings(session)
    settings.enabled = data.enabled
    settings.updated_at = datetime.utcnow()
    session.add(settings)
    session.commit()
    return {"enabled": settings.enabled}


@router.delete("/config")
def disconnect(remove_devices: bool = False, session: Session = Depends(get_session)):
    """Removes the OAuth client. Phones keep working (they are already in the tailnet)
    unless remove_devices deletes them from the tailnet too."""
    cfg = get_config(session)
    if not cfg:
        return {"removed": 0}
    removed = 0
    if remove_devices:
        for dev in session.exec(select(MobileDevice).where(MobileDevice.tailscale_node_id != "")).all():
            before = dev.tailscale_node_id
            remove_phone_from_tailnet(session, dev)
            if before and not dev.tailscale_node_id:
                removed += 1
                session.add(dev)
    cfg.client_id = ""
    cfg.client_secret = ""
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    tailnet.TailscaleClient.clear_token_cache()
    return {"removed": removed}


@router.get("/devices")
def list_devices(session: Session = Depends(get_session)):
    """Paired phones that joined the tailnet. Without an OAuth client the list comes
    from what the apps reported; with one it is enriched (and completed) by the API."""
    cfg = get_config(session)
    ext_numbers = {e.id: e.number for e in session.exec(select(Extension)).all()}
    paired = session.exec(select(MobileDevice).where(MobileDevice.tailscale_node_id != "")).all()
    rows = {}
    for d in paired:
        rows[d.tailscale_node_id] = {
            "id": d.tailscale_node_id, "hostname": "", "name": "",
            "addresses": [d.tailscale_ip] if d.tailscale_ip else [],
            "last_seen": d.last_seen_at.isoformat() + "Z" if d.last_seen_at else None, "os": d.platform,
            "extension_number": ext_numbers.get(d.extension_id), "device_name": d.device_name,
            "app_device_id": d.id, "removable": cfg is not None,
        }
    if cfg:
        try:
            with make_client(cfg.client_id, cfg.client_secret) as c:
                api_devices = c.list_devices()
        except tailnet.TailscaleError as e:
            raise HTTPException(status_code=502, detail=e.message)
        for d in api_devices:
            node_id = d.get("nodeId") or d.get("id", "")
            if node_id not in rows and cfg.tag not in (d.get("tags") or []):
                continue
            row = rows.setdefault(node_id, {
                "id": node_id, "extension_number": None, "device_name": "", "app_device_id": None,
            })
            row.update({
                "hostname": d.get("hostname", ""), "name": (d.get("name") or "").rstrip("."),
                "addresses": d.get("addresses") or row.get("addresses", []),
                "last_seen": d.get("lastSeen") or row.get("last_seen"), "os": d.get("os", ""),
                "removable": True,
            })
    return list(rows.values())


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
