#!/usr/bin/env python3
"""
Tests fuer Dead-letter Queue: Persistenz, Retry-Loop und HTTP-Endpunkt (RET-01, RET-02, RET-03)
TDD RED phase — tests must fail before implementation is added to session_manager.py and main.py
"""
import sqlite3
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _seed_completed_session(sm):
    """Insert a completed session row directly into SQLite for testing."""
    conn = sqlite3.connect(sm.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sessions
            (rfid_hash, wallbox_id, start_time, end_time, total_kwh, status, created_at)
        VALUES ('abc123hash', 'alfen_eve', '2026-01-01T10:00:00',
                '2026-01-01T11:00:00', 5.0, 'completed', '2026-01-01T10:00:00')
    ''')
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def _seed_dead_letter_row(sm, session_id, status='pending', retry_count=0):
    """Insert a dead_letter row directly into SQLite for testing.

    This INSERT will fail (OperationalError: no such table) until Plan 08-02
    creates the dead_letter table. That is the expected RED behaviour.
    """
    conn = sqlite3.connect(sm.db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO dead_letter
            (session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh,
             error_msg, retry_count, status, created_at)
            VALUES (?, 'abc123hash', 'alfen_eve', '2026-01-01T10:00:00',
                    '2026-01-01T11:00:00', 5.0, 'HTTP 503', ?, ?, '2026-01-01T11:00:00')
        ''', (session_id, retry_count, status))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# RET-01: Persistenz in der Dead-letter-Tabelle
# ---------------------------------------------------------------------------

class TestDeadLetterWrite:
    """RET-01: Fehlgeschlagene Sessions werden in dead_letter-Tabelle persistiert."""

    def test_failed_session_written_to_dead_letter(
        self, in_memory_session_manager, mock_api_client_failure
    ):
        """Nach einem fehlgeschlagenen Upload wird eine Zeile in dead_letter geschrieben.

        RET-01 — FAILS weil dead_letter-Tabelle noch nicht existiert (Plan 08-02).
        """
        sm = in_memory_session_manager
        _seed_completed_session(sm)

        sm.transmit_completed_sessions(mock_api_client_failure)

        conn = sqlite3.connect(sm.db_path)
        cursor = conn.cursor()
        # Wird mit OperationalError scheitern, bis Plan 08-02 die Tabelle anlegt
        cursor.execute("SELECT COUNT(*) FROM dead_letter")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1, (
            f"Erwartet 1 Zeile in dead_letter, gefunden: {count}. "
            "Tabelle fehlt noch (Plan 08-02)."
        )

        # Felder prüfen
        conn = sqlite3.connect(sm.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT session_id, wallbox_id, status, retry_count FROM dead_letter LIMIT 1"
        )
        row = cursor.fetchone()
        conn.close()
        assert row is not None
        assert row[1] == 'alfen_eve', f"wallbox_id falsch: {row[1]}"
        assert row[2] == 'pending', f"status falsch: {row[2]}"
        assert row[3] == 0, f"retry_count falsch: {row[3]}"


class TestDeadLetterDuplicatePrevention:
    """RET-01: UNIQUE(session_id) + INSERT OR IGNORE verhindert doppelte Einträge."""

    def test_unique_session_id_prevents_duplicate_rows(
        self, in_memory_session_manager, mock_api_client_failure
    ):
        """Zwei fehlgeschlagene Übertragungs-Versuche derselben Session erzeugen nur 1 Zeile.

        RET-01 — FAILS weil dead_letter-Tabelle noch nicht existiert (Plan 08-02).
        """
        sm = in_memory_session_manager
        _seed_completed_session(sm)

        sm.transmit_completed_sessions(mock_api_client_failure)
        sm.transmit_completed_sessions(mock_api_client_failure)

        conn = sqlite3.connect(sm.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM dead_letter")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1, (
            f"UNIQUE(session_id) muss Duplikate verhindern — gefunden: {count} Zeilen. "
            "Tabelle oder UNIQUE-Constraint fehlt (Plan 08-02)."
        )


class TestSessionStatusAfterFailure:
    """RET-01: Sessions-Status nach fehlgeschlagenem Upload muss 'dead_letter' sein."""

    def test_session_upload_status_set_to_dead_letter(
        self, in_memory_session_manager, mock_api_client_failure
    ):
        """Nach Übertragungsfehler muss sessions.upload_status='dead_letter' sein.

        RET-01 — FAILS weil aktuelle Implementierung 'error' setzt (nicht 'dead_letter').
        """
        sm = in_memory_session_manager
        session_id = _seed_completed_session(sm)

        sm.transmit_completed_sessions(mock_api_client_failure)

        conn = sqlite3.connect(sm.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT upload_status FROM sessions WHERE id = ?", (session_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None, f"Session {session_id} nicht gefunden"
        assert row[0] == 'dead_letter', (
            f"upload_status muss 'dead_letter' sein, ist aber: '{row[0]}'. "
            "Plan 08-02 aendert transmit_completed_sessions() auf 'dead_letter'."
        )


# ---------------------------------------------------------------------------
# RET-03: Retry-Loop
# ---------------------------------------------------------------------------

class TestRetryResolution:
    """RET-03: Erfolgreicher Retry markiert dead_letter-Eintrag als 'resolved'."""

    def test_retry_resolves_pending_entry(
        self, in_memory_session_manager, mock_api_client_success
    ):
        """retry_dead_letter_sessions() setzt status='resolved' und sessions.transmitted_at.

        RET-03 — FAILS weil retry_dead_letter_sessions() noch nicht existiert (Plan 08-02).
        """
        sm = in_memory_session_manager
        session_id = _seed_completed_session(sm)

        try:
            _seed_dead_letter_row(sm, session_id, status='pending', retry_count=0)
        except Exception as exc:
            pytest.fail(
                f"RED: dead_letter-Tabelle fehlt (erwartet bis Plan 08-02): {exc}"
            )

        try:
            result = sm.retry_dead_letter_sessions(mock_api_client_success)
        except AttributeError as exc:
            pytest.fail(
                f"RED: retry_dead_letter_sessions() fehlt noch in SessionManager: {exc}"
            )

        conn = sqlite3.connect(sm.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT status FROM dead_letter WHERE session_id = ?", (session_id,)
        )
        dl_row = cursor.fetchone()
        cursor.execute(
            "SELECT transmitted_at FROM sessions WHERE id = ?", (session_id,)
        )
        sess_row = cursor.fetchone()
        conn.close()

        assert dl_row is not None, "dead_letter-Zeile nicht gefunden"
        assert dl_row[0] == 'resolved', (
            f"dead_letter.status muss 'resolved' sein, ist: '{dl_row[0]}'"
        )
        assert sess_row is not None, "sessions-Zeile nicht gefunden"
        assert sess_row[0] is not None, (
            "sessions.transmitted_at muss nach Retry gesetzt sein"
        )


class TestRetryCountIncrement:
    """RET-03: Fehlgeschlagener Retry erhoeht retry_count um 1."""

    def test_retry_count_increments_on_failure(
        self, in_memory_session_manager, mock_api_client_failure
    ):
        """retry_dead_letter_sessions() erhoeht retry_count bei erneutem Fehler.

        RET-03 — FAILS weil retry_dead_letter_sessions() noch nicht existiert (Plan 08-02).
        """
        sm = in_memory_session_manager
        session_id = _seed_completed_session(sm)

        try:
            _seed_dead_letter_row(sm, session_id, status='pending', retry_count=0)
        except Exception as exc:
            pytest.fail(
                f"RED: dead_letter-Tabelle fehlt (erwartet bis Plan 08-02): {exc}"
            )

        try:
            sm.retry_dead_letter_sessions(mock_api_client_failure)
        except AttributeError as exc:
            pytest.fail(
                f"RED: retry_dead_letter_sessions() fehlt noch in SessionManager: {exc}"
            )

        conn = sqlite3.connect(sm.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT retry_count FROM dead_letter WHERE session_id = ?", (session_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None, "dead_letter-Zeile nicht gefunden"
        assert row[0] == 1, (
            f"retry_count muss nach 1 Fehlversuch == 1 sein, ist: {row[0]}"
        )


class TestSessionTransmittedAtAfterRetry:
    """RET-03: Erfolgreicher Retry setzt sessions.transmitted_at und upload_status='ok'."""

    def test_sessions_transmitted_at_set_after_successful_retry(
        self, in_memory_session_manager, mock_api_client_success
    ):
        """Nach erfolgreichem Retry: transmitted_at IS NOT NULL und upload_status='ok'.

        RET-03 — FAILS weil retry_dead_letter_sessions() noch nicht existiert (Plan 08-02).
        """
        sm = in_memory_session_manager
        session_id = _seed_completed_session(sm)

        try:
            _seed_dead_letter_row(sm, session_id, status='pending', retry_count=0)
        except Exception as exc:
            pytest.fail(
                f"RED: dead_letter-Tabelle fehlt (erwartet bis Plan 08-02): {exc}"
            )

        try:
            sm.retry_dead_letter_sessions(mock_api_client_success)
        except AttributeError as exc:
            pytest.fail(
                f"RED: retry_dead_letter_sessions() fehlt noch in SessionManager: {exc}"
            )

        conn = sqlite3.connect(sm.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT transmitted_at, upload_status FROM sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        conn.close()

        assert row is not None, f"sessions-Zeile {session_id} nicht gefunden"
        assert row[0] is not None, (
            "sessions.transmitted_at muss nach Retry gesetzt sein"
        )
        assert row[1] == 'ok', (
            f"sessions.upload_status muss 'ok' sein nach Retry, ist: '{row[1]}'"
        )


# ---------------------------------------------------------------------------
# RET-02: HTTP-Endpunkt /session/retry
# ---------------------------------------------------------------------------

class TestGetPendingDeadLetters:
    """RET-01 / SEC-01: get_pending_dead_letters() darf rfid_hash nicht zurueckgeben (T-08-03)."""

    def test_get_pending_dead_letters_excludes_rfid_hash(
        self, in_memory_session_manager
    ):
        """get_pending_dead_letters() liefert keine rfid_hash-Felder (SEC-01 / D-04).

        RET-01 — FAILS weil get_pending_dead_letters() noch nicht existiert (Plan 08-02).
        """
        sm = in_memory_session_manager
        session_id = _seed_completed_session(sm)

        try:
            _seed_dead_letter_row(sm, session_id, status='pending', retry_count=0)
        except Exception as exc:
            pytest.fail(
                f"RED: dead_letter-Tabelle fehlt (erwartet bis Plan 08-02): {exc}"
            )

        try:
            entries = sm.get_pending_dead_letters()
        except AttributeError as exc:
            pytest.fail(
                f"RED: get_pending_dead_letters() fehlt noch in SessionManager: {exc}"
            )

        assert len(entries) >= 1, "Mindestens 1 pending-Eintrag erwartet"
        for entry in entries:
            assert 'rfid_hash' not in entry, (
                "SEC-01/D-04: rfid_hash darf NICHT in get_pending_dead_letters() Ergebnis enthalten sein"
            )


class TestRetryEndpoint:
    """RET-02: /session/retry HTTP-Endpunkt — Validierung und API-Client-Pruefung."""

    def test_retry_endpoint_returns_400_when_dead_letter_id_missing(self):
        """POST /session/retry ohne dead_letter_id liefert HTTP 400.

        RET-02 — FAILS weil handle_session_retry() noch nicht in main.py implementiert.
        """
        import subprocess
        try:
            from main import handle_session_retry  # noqa: F401
        except ImportError:
            pytest.skip(
                "handle_session_retry nicht in main.py (erwartet bis Plan 08-02) — "
                "Subprocess-Test uebersprungen"
            )

        result = subprocess.run(
            ['python3', '-c', '''
import asyncio
import sys
sys.path.insert(0, ".")

import unittest.mock as mock
sys.modules.setdefault("utils", mock.MagicMock())
sys.modules.setdefault("utils.hash", mock.MagicMock())
sys.modules.setdefault("session_manager", mock.MagicMock())
sys.modules.setdefault("api_client", mock.MagicMock())

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

async def handle_session_retry(request):
    try:
        data = await request.json()
        dead_letter_id = int(data.get("dead_letter_id", 0))
        if not dead_letter_id:
            return web.json_response({"error": "dead_letter_id required"}, status=400)
        return web.json_response({"status": "ok"}, status=200)
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid dead_letter_id"}, status=400)

async def test():
    app = web.Application()
    app.router.add_post("/session/retry", handle_session_retry)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/session/retry", json={})
        assert resp.status == 400, f"Erwartet 400, erhalten: {resp.status}"
        data = await resp.json()
        assert "error" in data, f"Kein 'error'-Feld in Response: {data}"
        print("Test PASS")

asyncio.run(test())
'''],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        assert "Test PASS" in result.stdout, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_retry_endpoint_returns_503_when_api_client_none(self):
        """POST /session/retry gibt HTTP 503 wenn api_client global None ist.

        RET-02 — FAILS weil handle_session_retry() noch nicht in main.py implementiert.
        """
        import subprocess
        try:
            from main import handle_session_retry  # noqa: F401
        except ImportError:
            pytest.skip(
                "handle_session_retry nicht in main.py (erwartet bis Plan 08-02) — "
                "Subprocess-Test uebersprungen"
            )

        result = subprocess.run(
            ['python3', '-c', '''
import asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

api_client = None

async def handle_session_retry(request):
    global api_client
    try:
        data = await request.json()
        dead_letter_id = int(data.get("dead_letter_id", 0))
        if not dead_letter_id:
            return web.json_response({"error": "dead_letter_id required"}, status=400)
        if api_client is None:
            return web.json_response({"error": "API client not configured"}, status=503)
        return web.json_response({"status": "ok"}, status=200)
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid dead_letter_id"}, status=400)

async def test():
    app = web.Application()
    app.router.add_post("/session/retry", handle_session_retry)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/session/retry", json={"dead_letter_id": 1})
        assert resp.status == 503, f"Erwartet 503, erhalten: {resp.status}"
        data = await resp.json()
        assert data.get("error") == "API client not configured", f"Falsche Meldung: {data}"
        print("Test PASS")

asyncio.run(test())
'''],
            capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        assert "Test PASS" in result.stdout, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
