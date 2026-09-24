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


def write_pjsip_local(ip: str | None) -> Path:
    ip = normalize_ip(ip)
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
        },
        output,
    )
    return output
