"""TLS pinning data for the HA-Phone app: SHA-256 fingerprint of the self-signed
PJSIP cert (also served by the HTTPS API on 8443), handed out in the QR link,
/provision/complete and /config."""
import datetime
import hashlib
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from backend import tls_pin


def _write_cert(path: Path) -> bytes:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ha-phone")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=1)).sign(key, hashes.SHA256())
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert.public_bytes(serialization.Encoding.DER)


@pytest.fixture
def cert():
    path = Path(os.environ["BPX_DATA_DIR"]) / "asterisk" / "tls" / "asterisk.crt"
    backup = path.read_bytes() if path.exists() else None
    der = _write_cert(path)
    yield hashlib.sha256(der).hexdigest()
    if backup is None:
        path.unlink()
    else:
        path.write_bytes(backup)


def test_fingerprint_is_sha256_of_der(cert):
    assert tls_pin.cert_fingerprint() == cert


def test_fingerprint_empty_without_cert(tmp_path):
    assert tls_pin.cert_fingerprint(tmp_path / "missing.crt") == ""


def _pair(client, number):
    resp = client.post("/api/extensions", json={"number": number, "display_name": "Pin", "sip_password": "securepass1234567"})
    assert resp.status_code in (200, 201), resp.text
    start = client.post("/api/mobile/provision/start", json={"extension_number": number, "platform": "android"})
    assert start.status_code == 200, start.text
    return resp.json()["id"], start.json()


def test_qr_link_and_responses_carry_fingerprint_and_https_port(client, cert):
    ext_id, start = _pair(client, 86)
    try:
        q = parse_qs(urlparse(start["qr_code_url"]).query)
        assert q["fp"] == [cert]
        assert q["https"] == ["8443"]
        done = client.post("/api/mobile/provision/complete", json={
            "provisioning_token": start["provisioning_token"], "push_token": "", "os_device_id": "pin-test"})
        assert done.status_code == 200, done.text
        body = done.json()
        assert body["tls_fingerprint"] == cert
        assert body["api_https_port"] == 8443
        cfg = client.get("/api/mobile/config", headers={
            "X-Device-Id": str(body["device_id"]), "X-Device-Token": body["device_token"]}).json()
        assert cfg["tls_fingerprint"] == cert
        assert cfg["api_https_port"] == 8443
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_no_pin_parameters_without_cert(client):
    path = Path(os.environ["BPX_DATA_DIR"]) / "asterisk" / "tls" / "asterisk.crt"
    if path.exists():
        pytest.skip("test data dir has a cert")
    ext_id, start = _pair(client, 85)
    try:
        q = parse_qs(urlparse(start["qr_code_url"]).query)
        assert "fp" not in q and "https" not in q
    finally:
        client.delete(f"/api/extensions/{ext_id}")


def test_serve_adds_https_without_lifespan_only_with_cert(cert):
    from backend import serve
    key = Path(os.environ["BPX_DATA_DIR"]) / "asterisk" / "tls" / "asterisk.key"
    key.write_text("dummy")
    try:
        http, https = serve._servers()
        assert http.config.port == 80 and http.config.lifespan == "auto"
        assert https.config.port == 8443 and https.config.lifespan == "off"
        assert https.config.ssl_certfile.endswith("asterisk.crt")
    finally:
        key.unlink()
    assert len(serve._servers()) == 1
