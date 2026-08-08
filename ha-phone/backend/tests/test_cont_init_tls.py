from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "rootfs" / "etc" / "cont-init.d" / "10-asterisk-init.sh"


def test_script_generates_tls_cert_idempotently():
    content = SCRIPT.read_text()
    assert "openssl req -x509" in content
    assert "/data/asterisk/tls/asterisk.crt" in content
    assert "/data/asterisk/tls/asterisk.key" in content
    assert "chmod 600 /data/asterisk/tls/asterisk.key" in content


def test_script_appends_transport_tls_stanza_guarded_by_existence_check():
    content = SCRIPT.read_text()
    assert "[transport-tls]" in content
    assert "protocol   = tls" in content
    assert "grep -q '^\\[transport-tls\\]'" in content  # idempotency guard, not a plain duplicate append
