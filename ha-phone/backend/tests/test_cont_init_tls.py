from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "rootfs" / "etc" / "cont-init.d" / "10-asterisk-init.sh"


def test_script_generates_tls_cert_idempotently():
    content = SCRIPT.read_text()
    assert "x509.CertificateBuilder()" in content
    assert "/data/asterisk/tls/asterisk.crt" in content
    assert "/data/asterisk/tls/asterisk.key" in content
    assert "chmod 600 /data/asterisk/tls/asterisk.key" in content


def test_tls_cert_generation_runs_on_every_boot_not_only_first_boot():
    """Existing installs (/data/.initialized already present) must still get a cert."""
    content = SCRIPT.read_text()
    first_boot_end = content.index("touch /data/.initialized")
    assert content.index("x509.CertificateBuilder()") > first_boot_end


def test_script_does_not_depend_on_openssl_cli():
    """The runtime image ships libssl3 only, no openssl binary."""
    assert "openssl req" not in SCRIPT.read_text()


def test_script_renders_pjsip_local_from_shared_template():
    """Boot script and web UI render the same template (no hand-appended TLS stanza)."""
    content = SCRIPT.read_text()
    assert "from backend.pjsip_local import write_pjsip_local" in content
    assert "cat >> \"$PJSIP_LOCAL\"" not in content
    template = (SCRIPT.parents[3] / "backend" / "conf_templates" / "pjsip_local.conf.j2").read_text()
    assert "[transport-tls]" in template
    assert "protocol   = tls" in template


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
