"""TLS pinning data for the HA-Phone app.

The PJSIP TLS transport and the HTTPS mobile API (port 8443) share one self-signed
cert (/data/asterisk/tls/asterisk.crt, made by cont-init). Its SHA-256 fingerprint
goes into the pairing QR code, so the app can pin it: a self-signed cert has no CA
and the box is reached under changing names (LAN IP, tailnet IP).
"""
import hashlib
import os
from pathlib import Path
from typing import Optional

from cryptography import x509
from cryptography.hazmat.primitives import serialization

HTTPS_PORT = 8443


def _data_dir() -> Path:
    d = os.environ.get("BPX_DATA_DIR", "")
    return Path(d) if d else Path("/data")


def cert_path() -> Path:
    return _data_dir() / "asterisk" / "tls" / "asterisk.crt"


def key_path() -> Path:
    return _data_dir() / "asterisk" / "tls" / "asterisk.key"


def cert_fingerprint(path: Optional[Path] = None) -> str:
    """Lower-case hex SHA-256 of the cert's DER encoding, "" if there is no usable cert."""
    p = path or cert_path()
    try:
        cert = x509.load_pem_x509_certificate(p.read_bytes())
    except (OSError, ValueError):
        return ""
    return hashlib.sha256(cert.public_bytes(serialization.Encoding.DER)).hexdigest()


def pin_fields() -> dict:
    """Fields for /provision/complete and /config; empty without a cert (old installs)."""
    fp = cert_fingerprint()
    return {"tls_fingerprint": fp, "api_https_port": HTTPS_PORT} if fp else {}
