"""Demo instance of the HA-Phone admin UI for documentation screenshots.

Runs the real backend and the built frontend WITHOUT Asterisk: AMI calls are replaced
by fixed answers (everything online, trunk registered), the admin login is skipped,
and the database is filled with invented example data (no real names, numbers or
addresses). Usage (from the repo root, after `npm run build` in ha-phone/frontend):

    python3 scripts/demo_server.py [port]      # default 8099, data in /tmp/haphone-demo
"""
import io
import json
import os
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parent.parent / "ha-phone"
DATA = Path(os.environ.get("HAPHONE_DEMO_DIR", "/tmp/haphone-demo"))
shutil.rmtree(DATA, ignore_errors=True)
(DATA / "db").mkdir(parents=True)
(DATA / "asterisk").mkdir()
(DATA / "asterisk" / "ami_secret").write_text("demo")
(DATA / "asterisk" / "session_secret").write_text("demo-session-secret")
os.environ.update(BPX_DATA_DIR=str(DATA), BPX_DIST_DIR=str(ROOT / "frontend" / "dist"),
                  BPX_STUN_PORT="0", BPX_DOORBELL_LISTENER="0")
sys.path.insert(0, str(ROOT))

EXTENSIONS = [
    dict(number=11, display_name="Büro", video_capable=True),
    dict(number=12, display_name="Küche"),
    dict(number=13, display_name="Handy Anna", video_capable=True),
    dict(number=14, display_name="Handy Max", video_capable=True),
    dict(number=16, display_name="Haustür", video_capable=True, internal_only=True, is_door=True,
         door_open_webhook="http://homeassistant.local:8123/api/webhook/haustuer-oeffnen",
         doorbell_camera="camera.haustuer",
         door_actions=[{"label": "Licht Eingang", "service": "light.turn_on", "entity_id": "light.eingang"}]),
    dict(number=17, display_name="Gartentor", internal_only=True, is_door=True, door_open_code="*1"),
]
ONLINE = [str(e["number"]) for e in EXTENSIONS if e["number"] != 14]


def _statuses():
    return [{"number": str(e["number"]), "status": "Online" if str(e["number"]) in ONLINE else "Offline",
             "device_state": "Not in use" if str(e["number"]) in ONLINE else "Unavailable"} for e in EXTENSIONS]


def _diagnostics():
    agents = {"11": "Fanvil V65", "12": "Gigaset N510 IP PRO", "13": "HA-Phone App", "16": "Akuvox R20K", "17": "Fanvil i10"}
    out = []
    for i, e in enumerate(EXTENSIONS):
        n = str(e["number"]); on = n in ONLINE
        out.append({"number": n, "status": "Online" if on else "Offline", "device_state": "Not in use" if on else "Unavailable",
                    "active_channels": 0, "aor": n, "contacts": 1 if on else 0, "contact_status": "Avail" if on else "",
                    "contact_uri": f"sip:{n}@192.0.2.{20 + i}:5060" if on else "", "roundtrip_usec": 12000 if on else None,
                    "user_agent": agents.get(n, "") if on else "", "contacts_detail": []})
    return out


def _picture(text: str) -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (960, 540))
    d = ImageDraw.Draw(img)
    for y in range(540):
        d.line([(0, y), (960, y)], fill=(40 + y // 8, 60 + y // 10, 80 + y // 12))
    d.rectangle([380, 150, 580, 470], fill=(90, 70, 55))          # door
    d.ellipse([545, 300, 560, 315], fill=(200, 180, 90))           # handle
    d.text((20, 20), text, fill=(255, 255, 255))
    buf = io.BytesIO(); img.save(buf, "JPEG", quality=80)
    return buf.getvalue()


def seed(client):
    for e in EXTENSIONS:
        r = client.post("/api/extensions", json={**e, "sip_password": "demo-passwort-123456"})
        assert r.status_code in (200, 201), r.text
    client.post("/api/ring-groups", json={"name": "Zentrale", "number": 10, "extension_numbers": "11,12", "ring_timeout": 30})
    client.post("/api/ring-groups", json={"name": "Klingel", "number": 20, "extension_numbers": "11,13,14", "ring_timeout": 30})
    for name, number in (("Pizzeria Beispiel", "0301234567"), ("Praxis Dr. Muster", "0309876543"), ("Handwerker Mustermann", "01701234567")):
        client.post("/api/phonebook", json={"name": name, "number": number})
    templates = {t["name"]: t["id"] for t in client.get("/api/provisioning/templates").json()}
    def tpl(prefix):
        return next(i for n, i in templates.items() if n.startswith(prefix))
    for dev in (dict(name="Büro", manufacturer="Fanvil", model="V65", mac="0c383e000001", extension_numbers="11", template_id=tpl("Fanvil V65")),
                dict(name="Küche", manufacturer="Gigaset", model="N510 IP PRO", mac="7c2f80000002", extension_numbers="12", template_id=tpl("Gigaset N510/"))):
        assert client.post("/api/provisioning/devices", json=dev).status_code == 200
    rgs = {g["number"]: g["id"] for g in client.get("/api/ring-groups").json()}
    client.post("/api/routes", json={"did": "+49301234560", "destination_type": "ring_group", "destination_id": rgs[10]})
    client.post("/api/routes", json={"did": "+49301234561", "destination_type": "extension", "destination_id": 11})
    from sqlmodel import Session
    from backend.database import get_engine
    from backend.doorbell import DoorbellStore
    now = datetime.utcnow()
    with Session(get_engine()) as s:
        store = DoorbellStore(s)
        for minutes, answered, opened in ((12, "13", True), (95, "", False), (60 * 5, "11", False), (60 * 26, "14", True), (60 * 30, "", False)):
            ev = store.record_ring(16)
            ev.started_at = now - timedelta(minutes=minutes)
            ev.ended_at = ev.started_at + timedelta(seconds=25)
            ev.answered_by = answered; ev.door_opened = opened
            s.add(ev); s.commit()
            store.save_image(ev.id, _picture("Beispielbild Haustür"), "image/jpeg")


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    patches = [
        patch("backend.ami.ami_reload_pjsip", new_callable=AsyncMock),
        patch("backend.ami.ami_reload_dialplan", new_callable=AsyncMock),
        patch("backend.ami.ami_reload_voicemail", new_callable=AsyncMock),
        patch("backend.ami.get_trunk_status", new_callable=AsyncMock, return_value="Registered"),
        patch("backend.ami.get_trunk_debug", new_callable=AsyncMock, return_value={"Status": "Registered", "ServerUri": "sip:sip.example-provider.de"}),
        patch("backend.ami.get_extension_statuses", new_callable=AsyncMock, side_effect=lambda: _statuses()),
        patch("backend.ami.get_extension_diagnostics", new_callable=AsyncMock, side_effect=lambda: _diagnostics()),
        patch("backend.ami.get_active_call_count", new_callable=AsyncMock, return_value=0),
        patch("backend.ami.get_active_channel_details", new_callable=AsyncMock, return_value=[]),
        patch("backend.ami.hangup_channels_for_extension", new_callable=AsyncMock, return_value=0),
    ]
    for p in patches:
        p.start()
    from fastapi.testclient import TestClient
    from backend.main import app
    from backend.auth import get_current_user
    from backend.models import AdminUser
    app.dependency_overrides[get_current_user] = lambda: AdminUser(id=1, username="admin", hashed_password=b"x", must_change_password=False)
    with TestClient(app) as client:
        seed(client)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
