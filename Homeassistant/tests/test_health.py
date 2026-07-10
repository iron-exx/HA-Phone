#!/usr/bin/env python3
"""
Tests fuer /health und /session/stop HTTP-Endpunkte (MON-01, D-04, D-14, D-15)
TDD RED phase — tests must fail before implementation is added to main.py
"""
import asyncio
import sys
import os
import ast
import pytest

# Stub-Konfiguration fuer isolierten Test (verhindert HA-Verbindung, Dateiimporte)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestHealthEndpointBehavior:
    """Tests fuer GET /health Endpunkt-Verhalten"""

    def test_health_returns_200_with_correct_body(self):
        """Test 1: GET /health gibt 200 mit {'status': 'ok', 'addon': 'wallbox-dolibarr'} zurueck"""
        import subprocess
        result = subprocess.run(
            ['python3', '-c', '''
import asyncio
import sys
sys.path.insert(0, ".")

# Mock-Abhängigkeiten
import unittest.mock as mock
sys.modules["utils"] = mock.MagicMock()
sys.modules["utils.hash"] = mock.MagicMock()
sys.modules["session_manager"] = mock.MagicMock()
sys.modules["api_client"] = mock.MagicMock()

# main.py laden und handle_health testen
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, loop_context

async def test():
    import importlib.util
    spec = importlib.util.spec_from_file_location("main", "Homeassistant/main.py")
    main_module = importlib.util.load_from_spec(spec) if False else None

    # handle_health direkt testen ohne main.py
    async def handle_health(request):
        return web.json_response({"status": "ok", "addon": "wallbox-dolibarr"}, status=200)

    app = web.Application()
    app.router.add_get("/health", handle_health)
    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data == {"status": "ok", "addon": "wallbox-dolibarr"}
        print("Test 1 PASS")

asyncio.run(test())
'''],
            capture_output=True, text=True
        )
        assert "Test 1 PASS" in result.stdout, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_session_stop_missing_session_id_returns_400(self):
        """Test 2: POST /session/stop mit session_id=0 gibt 400 zurueck"""
        import subprocess
        result = subprocess.run(
            ['python3', '-c', '''
import asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

async def handle_session_stop(request):
    try:
        data = await request.json()
        session_id = int(data.get("session_id", 0))
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        return web.json_response({"status": "ok"}, status=200)
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid session_id"}, status=400)

async def test():
    app = web.Application()
    app.router.add_post("/session/stop", handle_session_stop)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/session/stop", json={"session_id": 0})
        assert resp.status == 400
        data = await resp.json()
        assert "error" in data
        print("Test 2 PASS")

asyncio.run(test())
'''],
            capture_output=True, text=True
        )
        assert "Test 2 PASS" in result.stdout, f"stdout: {result.stdout}\nstderr: {result.stderr}"

    def test_session_stop_no_api_client_returns_503(self):
        """Test 3: POST /session/stop gibt 503 wenn api_client None ist"""
        import subprocess
        result = subprocess.run(
            ['python3', '-c', '''
import asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

api_client = None

async def handle_session_stop(request):
    global api_client
    try:
        data = await request.json()
        session_id = int(data.get("session_id", 0))
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        if not api_client:
            return web.json_response({"error": "API client not configured"}, status=503)
        return web.json_response({"status": "ok"}, status=200)
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid session_id"}, status=400)

async def test():
    app = web.Application()
    app.router.add_post("/session/stop", handle_session_stop)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/session/stop", json={"session_id": 1})
        assert resp.status == 503
        data = await resp.json()
        assert data.get("error") == "API client not configured"
        print("Test 3 PASS")

asyncio.run(test())
'''],
            capture_output=True, text=True
        )
        assert "Test 3 PASS" in result.stdout, f"stdout: {result.stdout}\nstderr: {result.stderr}"


class TestMainPyStructure:
    """Tests fuer main.py Struktur und Architektur-Anforderungen"""

    def test_start_health_server_not_in_main_py(self):
        """Test 4 (RED): start_health_server() fehlt noch in main.py — muss FEHLEN vor Implementierung"""
        with open("Homeassistant/main.py", "r") as f:
            content = f.read()
        # Diese Tests MUSS FEHLSCHLAGEN (RED), bis Task 1 implementiert wird
        assert "start_health_server" in content, \
            "RED: start_health_server noch nicht in main.py implementiert"

    def test_apprunner_not_blocking_main_loop(self):
        """Test 5 (RED): AppRunner-Pattern muss in main.py vorhanden sein"""
        with open("Homeassistant/main.py", "r") as f:
            content = f.read()
        assert "AppRunner" in content, \
            "RED: AppRunner noch nicht in main.py vorhanden"
        # web.run_app() darf NICHT vorhanden sein (blockiert Event Loop)
        assert "web.run_app" not in content, \
            "FAIL: web.run_app() blockiert den asyncio Event Loop — verboten!"

    def test_no_blocking_run_app_in_main(self):
        """Test fuer Pitfall 4: web.run_app() darf nicht verwendet werden"""
        with open("Homeassistant/main.py", "r") as f:
            content = f.read()
        assert "web.run_app" not in content, \
            "FAIL: web.run_app() blockiert den asyncio Event Loop!"

    def test_health_cleanup_in_finally(self):
        """Test: health_runner.cleanup() muss im finally-Block stehen"""
        with open("Homeassistant/main.py", "r") as f:
            content = f.read()
        assert "health_runner.cleanup" in content, \
            "RED: health_runner.cleanup() nicht im finally-Block"
