import os
import time
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.conf_generator import render_conf
from backend.database import get_session
from backend.models import SmtpSettings
from backend import ami

router = APIRouter()


def regenerate_mail_configs(session: Session) -> None:
    """Render voicemail [general] + msmtp config from the SMTP settings. Also runs
    on boot so /data/asterisk/voicemail_general.conf always exists (the #include
    in voicemail.conf would otherwise fail)."""
    s = session.exec(select(SmtpSettings)).first()
    ctx = {
        "host": s.host if s else "",
        "port": s.port if s else 587,
        "encryption": s.encryption if s else "starttls",
        "username": s.username if s else "",
        "password": s.password if s else "",
        "from_addr": s.from_addr if s else "",
        "from_name": (s.from_name if s else "HA-Phone") or "HA-Phone",
        "enabled": bool(s and s.enabled),
    }
    d = _data_dir() / "asterisk"
    render_conf("voicemail_general.conf.j2", dict(ctx), d / "voicemail_general.conf")
    mp = d / "msmtprc"
    if ctx["enabled"] and ctx["host"]:
        render_conf("msmtprc.j2", dict(ctx), mp)
        try:
            os.chmod(mp, 0o600)
        except Exception:
            pass

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


# ── SMTP (voicemail-to-email) ────────────────────────────────────────────────
class SmtpConfig(BaseModel):
    host: str = ""
    port: int = 587
    encryption: str = "starttls"   # starttls | ssl | none
    username: str = ""
    password: str = ""             # write-only; never returned
    from_addr: str = ""
    from_name: str = "HA-Phone"
    enabled: bool = False


class SmtpTestRequest(BaseModel):
    to: str
    # Live overrides — the UI sends the current form values so you can test exactly
    # what you typed, without saving first. Any blank field falls back to the saved
    # settings (e.g. a blank password reuses the stored one).
    host: str = ""
    port: int = 0
    encryption: str = ""
    username: str = ""
    password: str = ""
    from_addr: str = ""
    from_name: str = ""


@router.get("/settings/smtp", response_model=SmtpConfig)
def get_smtp(session: Session = Depends(get_session)):
    s = session.exec(select(SmtpSettings)).first()
    if not s:
        return SmtpConfig()
    return SmtpConfig(
        host=s.host, port=s.port, encryption=s.encryption, username=s.username,
        password="", from_addr=s.from_addr, from_name=s.from_name, enabled=s.enabled,
    )


@router.post("/settings/smtp")
async def save_smtp(body: SmtpConfig, session: Session = Depends(get_session)):
    s = session.exec(select(SmtpSettings)).first()
    if not s:
        s = SmtpSettings()
    s.host = body.host.strip()
    s.port = body.port
    s.encryption = body.encryption
    s.username = body.username.strip()
    if body.password:               # blank = keep existing
        s.password = body.password.strip()   # copy-paste often adds trailing whitespace
    s.from_addr = body.from_addr.strip()
    s.from_name = body.from_name.strip() or "HA-Phone"
    s.enabled = body.enabled
    session.add(s)
    session.commit()
    regenerate_mail_configs(session)
    await ami.ami_reload_voicemail()
    return {"ok": True}


@router.post("/settings/smtp/test")
def test_smtp(body: SmtpTestRequest, session: Session = Depends(get_session)):
    import smtplib
    import ssl
    from email.message import EmailMessage

    saved = session.exec(select(SmtpSettings)).first()
    # Prefer live form values; fall back to saved settings per field.
    host = (body.host or (saved.host if saved else "")).strip()
    port = body.port or (saved.port if saved else 587)
    encryption = (body.encryption or (saved.encryption if saved else "starttls")).strip()
    username = (body.username or (saved.username if saved else "")).strip()
    password = (body.password.strip() if body.password else (saved.password if saved else ""))
    from_addr = (body.from_addr or (saved.from_addr if saved else "")).strip()
    from_name = (body.from_name or (saved.from_name if saved else "HA-Phone")).strip() or "HA-Phone"
    if not host:
        raise HTTPException(status_code=400, detail="SMTP-Server fehlt.")

    msg = EmailMessage()
    msg["Subject"] = "HA-Phone — SMTP-Test"
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = body.to
    msg.set_content("Dies ist eine Test-E-Mail von HA-Phone. Wenn du sie erhältst, funktioniert der Postausgang.")
    try:
        if encryption == "ssl":
            server = smtplib.SMTP_SSL(host, port, timeout=12)
        else:
            server = smtplib.SMTP(host, port, timeout=12)
            if encryption == "starttls":
                server.starttls(context=ssl.create_default_context())
        if username:
            server.login(username, password)
        server.send_message(msg)
        server.quit()
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}")
