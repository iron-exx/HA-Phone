"""Phones upload their diagnostic log; the admin reads it."""
from backend import app_logs
from backend.tests.test_mobile_device_auth import paired  # noqa: F401 (fixture)


def _auth(paired):
    return {"X-Device-Id": str(paired["device_id"]), "X-Device-Token": paired["device_token"]}


def test_upload_needs_device_token(client, paired):
    assert client.post("/api/mobile/diagnostics", json={"log": "x"}).status_code == 401


def test_phone_uploads_and_admin_reads_it(client, paired):
    resp = client.post("/api/mobile/diagnostics", headers=_auth(paired),
                       json={"log": "09-29 20:50:02 I/IncomingCall: incoming 3\n", "app_version": "1.7.3", "note": "Tür"})
    assert resp.status_code == 200, resp.text
    name = resp.json()["name"]
    assert name.startswith("ext87-dev")
    listing = client.get("/api/diagnostics/app-logs").json()
    assert name in [e["name"] for e in listing]
    text = client.get(f"/api/diagnostics/app-logs/{name}").text
    assert "app 1.7.3" in text and "Tür" in text and "incoming 3" in text


def test_admin_download_rejects_other_paths(client):
    for bad in ("ext1-dev1-x.log", "hello.txt", "%2e%2e"):
        assert client.get(f"/api/diagnostics/app-logs/{bad}").status_code == 404, bad
    # With slashes the URL no longer matches this route (web UI fallback): never a file from outside.
    for bad in ("../../etc/passwd", "..%2F..%2Fetc%2Fpasswd"):
        assert "root:" not in client.get(f"/api/diagnostics/app-logs/{bad}").text


def test_big_logs_keep_the_newest_part_and_old_ones_are_pruned(tmp_data_dir, monkeypatch):
    monkeypatch.setattr(app_logs, "MAX_BYTES", 10)
    name = app_logs.save(5, 7, "0123456789ABCDEF", "hdr", now=1000)
    assert app_logs.path_of(name).read_bytes() == b"hdr\n6789ABCDEF"
    for i in range(app_logs.MAX_PER_DEVICE + 2):
        app_logs.save(5, 7, "x", "h", now=2000 + i)
    assert len([e for e in app_logs.listing() if e["name"].startswith("ext5-dev7-")]) == app_logs.MAX_PER_DEVICE


def test_upload_rejects_empty_and_huge(client, paired):
    assert client.post("/api/mobile/diagnostics", headers=_auth(paired), json={"log": ""}).status_code == 422
    huge = "x" * (app_logs.MAX_BYTES * 3)
    assert client.post("/api/mobile/diagnostics", headers=_auth(paired), json={"log": huge}).status_code == 413
