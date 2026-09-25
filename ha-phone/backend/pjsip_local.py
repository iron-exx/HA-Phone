"""Render /data/asterisk/pjsip_local.conf (transport NAT settings + [transport-tls]).

Single source for both the boot script (cont-init.d) and the web UI's public-IP
setting: previously the boot script appended [transport-tls] by hand while the
web UI rendered a template without it, so saving the public IP silently removed
the TLS transport the HA-Phone app registers over.
"""
import ipaddress
import os
from pathlib import Path

from backend.conf_generator import render_conf


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def normalize_ip(ip: str | None) -> str:
    """'' for empty; raises ValueError for anything that is not a plain IP address."""
    raw = (ip or "").strip()
    if not raw:
        return ""
    return str(ipaddress.ip_address(raw))


TAILNET_SIP_PORT = 5063


def _ip_memo() -> Path:
    return _data_dir() / "asterisk" / "pjsip_local.ip"


def rendered_tailnet_ip() -> str | None:
    """Tailnet address the current pjsip_local.conf was written with (None = none)."""
    try:
        return (_data_dir() / "asterisk" / "pjsip_local.tailnet").read_text().strip() or None
    except OSError:
        return None


def write_pjsip_local(ip: str | None, tailnet_ip: str | None = "auto") -> Path:
    """Renders the transports. tailnet_ip "auto" = detect tailscale0 now."""
    ip = normalize_ip(ip)
    if tailnet_ip == "auto":
        from backend.tailnet import detect_tailnet_address
        tailnet_ip = detect_tailnet_address().ipv4
    asterisk_dir = _data_dir() / "asterisk"
    cert = asterisk_dir / "tls" / "asterisk.crt"
    key = asterisk_dir / "tls" / "asterisk.key"
    output = asterisk_dir / "pjsip_local.conf"
    render_conf(
        "pjsip_local.conf.j2",
        {
            "ip": ip,
            "ip_is_v6": bool(ip) and ipaddress.ip_address(ip).version == 6,
            "tls": cert.is_file() and key.is_file(),
            "tls_cert": str(cert),
            "tls_key": str(key),
            "tailnet_ip": tailnet_ip or "",
        },
        output,
    )
    # Remembered so the tailnet watcher can re-render with the same public IP.
    _ip_memo().write_text(ip)
    (asterisk_dir / "pjsip_local.tailnet").write_text(tailnet_ip or "")
    return output


def refresh_for_tailnet() -> bool:
    """Re-renders when the box's tailnet address appeared/changed/vanished since the
    last render (the Tailscale add-on may come up after HA-Phone). True = changed,
    caller reloads res_pjsip."""
    from backend.tailnet import detect_tailnet_address
    now = detect_tailnet_address().ipv4
    if now == rendered_tailnet_ip():
        return False
    try:
        ip = _ip_memo().read_text().strip()
    except OSError:
        ip = ""
    write_pjsip_local(ip, tailnet_ip=now)
    return True
