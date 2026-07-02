import re
import socket
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import get_session
from backend.models import ProvisioningTemplate, ProvisionedDevice, Extension

# Auth-protected CRUD router
router = APIRouter()
# PUBLIC router — devices fetch their config unauthenticated (secured by MAC).
public_router = APIRouter()


def _norm_mac(value: str) -> str:
    """Lowercase hex only (strip :, -, ., spaces)."""
    return re.sub(r"[^0-9a-fA-F]", "", value or "").lower()


def _lan_ip() -> str:
    """Best-effort primary LAN IPv4 of the host (the address phones register to)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


# ── Built-in starter templates (fully editable in the UI) ────────────────────
BUILTIN_TEMPLATES = [
    {
        "name": "Yealink T5x/T4x",
        "vendor": "Yealink",
        "file_pattern": "{mac}.cfg",
        "content": (
            "#!version:1.0.0.1\n"
            "## HA-Phone auto-provisioning — Yealink. Editierbar.\n"
            "account.1.enable = 1\n"
            "account.1.label = {{label}}\n"
            "account.1.display_name = {{display_name}}\n"
            "account.1.auth_name = {{sip_username}}\n"
            "account.1.user_name = {{sip_username}}\n"
            "account.1.password = {{sip_password}}\n"
            "account.1.sip_server.1.address = {{sip_server}}\n"
            "account.1.sip_server.1.port = {{sip_port}}\n"
            "account.1.sip_server.1.transport_type = 0\n"
        ),
    },
    {
        "name": "Grandstream",
        "vendor": "Grandstream",
        "file_pattern": "cfg{mac}.xml",
        "content": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- HA-Phone auto-provisioning — Grandstream P-values. Editierbar. -->\n"
            '<gs_provision version="1">\n'
            "  <config version=\"1\">\n"
            "    <P271>1</P271>\n"
            "    <P47>{{sip_server}}</P47>\n"
            "    <P35>{{sip_username}}</P35>\n"
            "    <P36>{{sip_username}}</P36>\n"
            "    <P34>{{sip_password}}</P34>\n"
            "    <P3>{{display_name}}</P3>\n"
            "  </config>\n"
            "</gs_provision>\n"
        ),
    },
    {
        "name": "Fanvil",
        "vendor": "Fanvil",
        "file_pattern": "{mac}.cfg",
        "content": (
            "<<VOIP CONFIG FILE>>Version:2.0000\n"
            "## HA-Phone auto-provisioning — Fanvil. Editierbar.\n"
            "<SIP CONFIG MODULE>\n"
            "SIP1 Phone Number :{{sip_username}}\n"
            "SIP1 Display Name :{{display_name}}\n"
            "SIP1 Register User :{{sip_username}}\n"
            "SIP1 Register Pswd :{{sip_password}}\n"
            "SIP1 Register Addr :{{sip_server}}\n"
            "SIP1 Register Port :{{sip_port}}\n"
            "SIP1 Register Enable :1\n"
        ),
    },
    {
        "name": "Gigaset N670/N870 IP PRO (DECT)",
        "vendor": "Gigaset",
        "file_pattern": "{mac}.xml",
        "content": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            "<!-- HA-Phone auto-provisioning — Gigaset DECT provider profile.\n"
            "     STARTVORLAGE: exakte Parameternamen je nach Firmware anpassen!\n"
            "     Gigaset-Datenserver-URL am Gerät: http://<PBX-IP>:8099/api/autoprovision/[MAC].xml -->\n"
            '<provisioning version="1.1" productID="e2">\n'
            "  <nvm>\n"
            '    <param name="SipProvider.0.Name" value="HA-Phone"/>\n'
            '    <param name="SipProvider.0.Domain" value="{{sip_server}}"/>\n'
            '    <param name="SipProvider.0.RegServer" value="{{sip_server}}"/>\n'
            '    <param name="SipProvider.0.RegServerPort" value="{{sip_port}}"/>\n'
            '    <param name="SipProvider.0.ProxyServer" value="{{sip_server}}"/>\n'
            '    <param name="SipProvider.0.ProxyServerPort" value="{{sip_port}}"/>\n'
            '    <param name="Handset.0.SIP.UserName" value="{{sip_username}}"/>\n'
            '    <param name="Handset.0.SIP.AuthName" value="{{sip_username}}"/>\n'
            '    <param name="Handset.0.SIP.AuthPassword" value="{{sip_password}}"/>\n'
            '    <param name="Handset.0.SIP.DisplayName" value="{{display_name}}"/>\n'
            "  </nvm>\n"
            "</provisioning>\n"
        ),
    },
]


def seed_builtin_templates(session: Session) -> bool:
    """Insert starter templates once (by name). Returns True if it seeded."""
    seeded = False
    existing = {t.name for t in session.exec(select(ProvisioningTemplate)).all()}
    for t in BUILTIN_TEMPLATES:
        if t["name"] not in existing:
            session.add(ProvisioningTemplate(builtin=True, **t))
            seeded = True
    if seeded:
        session.commit()
    return seeded


def _render(content: str, subs: dict) -> str:
    out = content
    for k, v in subs.items():
        out = out.replace("{{ " + k + " }}", str(v)).replace("{{" + k + "}}", str(v))
    return out


# ── Templates CRUD ───────────────────────────────────────────────────────────
@router.get("/provisioning/templates", response_model=List[ProvisioningTemplate])
def list_templates(session: Session = Depends(get_session)):
    return session.exec(select(ProvisioningTemplate)).all()


@router.post("/provisioning/templates", response_model=ProvisioningTemplate)
def create_template(tpl: ProvisioningTemplate, session: Session = Depends(get_session)):
    tpl.id = None
    tpl.builtin = False
    session.add(tpl)
    session.commit()
    session.refresh(tpl)
    return tpl


@router.patch("/provisioning/templates/{tpl_id}", response_model=ProvisioningTemplate)
def update_template(tpl_id: int, data: ProvisioningTemplate, session: Session = Depends(get_session)):
    existing = session.get(ProvisioningTemplate, tpl_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    for field in ("name", "vendor", "file_pattern", "content"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(existing, field, val)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


@router.delete("/provisioning/templates/{tpl_id}")
def delete_template(tpl_id: int, session: Session = Depends(get_session)):
    existing = session.get(ProvisioningTemplate, tpl_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Template not found")
    session.delete(existing)
    session.commit()
    return {"ok": True}


# ── Devices CRUD ─────────────────────────────────────────────────────────────
class DeviceOut(BaseModel):
    id: Optional[int]
    name: str
    manufacturer: str
    model: str
    mac: str
    extension_id: int
    template_id: int
    provisioning_url: str


def _device_out(d: ProvisionedDevice, session: Session, lan_ip: str) -> DeviceOut:
    tpl = session.get(ProvisioningTemplate, d.template_id)
    fname = (tpl.file_pattern if tpl else "{mac}").replace("{mac}", d.mac)
    base = f"http://{lan_ip}:8099" if lan_ip else "http://<PBX-IP>:8099"
    return DeviceOut(
        id=d.id, name=d.name, manufacturer=d.manufacturer, model=d.model, mac=d.mac,
        extension_id=d.extension_id, template_id=d.template_id,
        provisioning_url=f"{base}/api/autoprovision/{fname}",
    )


@router.get("/provisioning/devices", response_model=List[DeviceOut])
def list_devices(session: Session = Depends(get_session)):
    lan = _lan_ip()
    return [_device_out(d, session, lan) for d in session.exec(select(ProvisionedDevice)).all()]


@router.post("/provisioning/devices", response_model=DeviceOut)
def create_device(device: ProvisionedDevice, session: Session = Depends(get_session)):
    device.id = None
    device.mac = _norm_mac(device.mac)
    if len(device.mac) != 12:
        raise HTTPException(status_code=400, detail="MAC muss 12 Hex-Zeichen haben.")
    session.add(device)
    session.commit()
    session.refresh(device)
    return _device_out(device, session, _lan_ip())


@router.patch("/provisioning/devices/{device_id}", response_model=DeviceOut)
def update_device(device_id: int, data: ProvisionedDevice, session: Session = Depends(get_session)):
    existing = session.get(ProvisionedDevice, device_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    for field in ("name", "manufacturer", "model", "extension_id", "template_id"):
        val = getattr(data, field, None)
        if val is not None:
            setattr(existing, field, val)
    if data.mac:
        existing.mac = _norm_mac(data.mac)
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return _device_out(existing, session, _lan_ip())


@router.delete("/provisioning/devices/{device_id}")
def delete_device(device_id: int, session: Session = Depends(get_session)):
    existing = session.get(ProvisionedDevice, device_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Device not found")
    session.delete(existing)
    session.commit()
    return {"ok": True}


# ── PUBLIC provisioning endpoint (no auth — devices fetch by MAC) ─────────────
@public_router.get("/autoprovision/{path:path}")
def serve_provisioning(path: str, session: Session = Depends(get_session)):
    mac_match = re.search(r"([0-9a-fA-F]{12})", path)
    if not mac_match:
        raise HTTPException(status_code=404, detail="No MAC in request")
    mac = mac_match.group(1).lower()
    device = session.exec(select(ProvisionedDevice).where(ProvisionedDevice.mac == mac)).first()
    if not device:
        raise HTTPException(status_code=404, detail="Unknown device")
    tpl = session.get(ProvisioningTemplate, device.template_id)
    ext = session.exec(
        select(Extension).where(Extension.number == device.extension_id)
    ).first()
    if not tpl or not ext:
        raise HTTPException(status_code=404, detail="Device not fully configured")
    subs = {
        "mac": device.mac,
        "extension": str(ext.number),
        "display_name": ext.display_name,
        "label": ext.display_name,
        "sip_username": str(ext.number),
        "sip_auth": str(ext.number),
        "sip_password": ext.sip_password,
        "sip_server": _lan_ip(),
        "sip_port": "5060",
    }
    body = _render(tpl.content, subs)
    media = "application/xml" if path.lower().endswith(".xml") else "text/plain"
    return Response(content=body, media_type=media)
