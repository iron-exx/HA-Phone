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


def test_script_reasserts_secret_permissions_after_recursive_chmod():
    """Code review CR-2 regression guard: `chmod -R 755 /data/asterisk` runs
    on every boot and applies to files as well as directories, silently
    undoing the `chmod 600` the generation blocks above already applied to
    the AMI secret, session secret, and TLS private key -- and leaving
    pjsip_extensions.conf's plaintext SIP passwords world-readable too.
    Asserts the re-assertion lines exist AFTER the recursive chmod, not
    just that they exist anywhere in the file.
    """
    content = SCRIPT.read_text()
    recursive_chmod_index = content.index("chmod -R 755 /data/voicemail /data/logs /data/asterisk")

    for reasserted_path in (
        "/data/asterisk/ami_secret",
        "/data/asterisk/session_secret",
        "/data/asterisk/tls/asterisk.key",
        "/data/asterisk/pjsip_extensions.conf",
    ):
        reassert_index = content.index(f"chmod 600 {reasserted_path}", recursive_chmod_index)
        assert reassert_index > recursive_chmod_index, (
            f"chmod 600 {reasserted_path} must appear after the recursive chmod -R 755, "
            "or the broad chmod silently resets it back to world-readable on every boot"
        )
