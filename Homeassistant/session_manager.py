#!/usr/bin/env python3
"""
Session Manager für Wallbox-Ladevorgänge

Verwaltet SQLite-Datenbank für Lade-Sessions:
- Session-Start (RFID-Validierung, Whitelist-Check)
- Session-Ende (Energie-Berechnung, Zeitstempel)
- RFID-Debouncing (5-10 Sekunden Unterdrückung)
- Persistenz für Neustart-Überlebung
"""
import sqlite3
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime

# Hash-Utility importieren
import sys
sys.path.insert(0, '/usr/local/bin')
from utils.hash import hash_rfid, verify_rfid_hash

# Status-Konstanten (D-16)
CHARGING = "Charging"
IDLE = "Idle"
STOPPED = "Stopped"

# Debounce-Zeit in Sekunden (HA-07)
DEBOUNCE_SECONDS = 7

# Modul-Level Logger (wird auch in _init_database() vor self._logger benutzt)
_LOGGER = logging.getLogger(__name__)


def format_iso8601(dt: Any) -> str:
    """
    Konvertiert datetime zu ISO 8601 String mit Zeitzone

    Args:
        dt: datetime-Objekt oder String

    Returns:
        ISO 8601 formatierter String

    Note:
        Wenn dt bereits ein String ist, wird er unverändert zurückgegeben
    """
    if isinstance(dt, str):
        return dt

    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    return str(dt)

class SessionManager:
    """Verwaltet Lade-Sessions in SQLite"""

    def __init__(self, db_path: str = "/data/sessions.db"):
        self.db_path = db_path
        self._logger = logging.getLogger(__name__)
        self._init_database()
        self._last_rfid_time: Dict[str, float] = {}  # Für Debouncing

    def _init_database(self):
        """Initialisiert die SQLite-Datenbank mit Sessions-Tabelle (PER-01, DB-01 Vorbereitung)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # WAL Mode aktivieren für bessere Concurrenty (PER-02)
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=5000")

        # Tabelle für Lade-Sessions (HA-03, Felder für Phase 2)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rfid_hash TEXT NOT NULL,
                wallbox_id TEXT NOT NULL DEFAULT 'alfen_eve',
                start_time TEXT NOT NULL,
                end_time TEXT,
                start_energy_kwh REAL NOT NULL DEFAULT 0.0,
                end_energy_kwh REAL,
                total_kwh REAL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                transmitted_at TEXT
            )
        ''')

        # Spalte transmitted_at hinzufügen falls Tabelle bereits existiert (Migration)
        try:
            cursor.execute('''
                ALTER TABLE sessions ADD COLUMN transmitted_at TEXT
            ''')
            _LOGGER.info("Datenbank-Schema erweitert: transmitted_at hinzugefügt")
        except sqlite3.OperationalError:
            # Spalte existiert bereits
            pass

        # upload_status und upload_error fuer Uebertragungsprotokoll (MON-01, D-09, D-10)
        try:
            cursor.execute('ALTER TABLE sessions ADD COLUMN upload_status TEXT DEFAULT "pending"')
        except sqlite3.OperationalError:
            pass  # Spalte existiert bereits

        try:
            cursor.execute('ALTER TABLE sessions ADD COLUMN upload_error TEXT')
        except sqlite3.OperationalError:
            pass  # Spalte existiert bereits

        # Index für rfid_hash (DB-02 Vorbereitung)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_rfid_hash ON sessions(rfid_hash)
        ''')

        # Index für status (für aktive Sessions)
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_status ON sessions(status)
        ''')

        # Dead-letter queue table (RET-01)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dead_letter (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                rfid_hash TEXT NOT NULL,
                wallbox_id TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                total_kwh REAL NOT NULL DEFAULT 0.0,
                error_msg TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                last_retry_at TEXT,
                UNIQUE(session_id)
            )
        ''')
        cursor.execute(
            'CREATE INDEX IF NOT EXISTS idx_dead_letter_status ON dead_letter(status)'
        )

        conn.commit()
        conn.close()
        self._logger.info("SQLite Datenbank initialisiert mit WAL Mode: %s", self.db_path)

    def debounce_rfid(self, rfid_hex: str) -> bool:
        """
        Prüft ob RFID-Lesung innerhalb des Debounce-Intervalls liegt (HA-07)

        Args:
            rfid_hex: RFID als Hex-String

        Returns:
            True wenn RFID akzeptiert wird (nicht debounced)
        """
        current_time = time.time()
        rfid_hash = hash_rfid(rfid_hex)

        if rfid_hash in self._last_rfid_time:
            time_diff = current_time - self._last_rfid_time[rfid_hash]
            if time_diff < DEBOUNCE_SECONDS:
                self._logger.debug("RFID debounced: %s (%.1fs < %ds)",
                                rfid_hash[:16], time_diff, DEBOUNCE_SECONDS)
                return False

        self._last_rfid_time[rfid_hash] = current_time
        return True

    def is_rfid_authorized(self, rfid_hex: str, whitelist: list) -> bool:
        """
        Prüft ob RFID in der Whitelist ist (HA-02, HA-04)

        Args:
            rfid_hex: RFID als Hex-String
            whitelist: Liste der erlaubten RFID-Karten (aus config.yaml)

        Returns:
            True wenn RFID autorisiert ist
        """
        if not whitelist:
            self._logger.warning("Keine RFID-Whitelist konfiguriert")
            return False

        rfid_hash = hash_rfid(rfid_hex)

        # Whitelist enthält Hex-Strings, wir vergleichen Hashes
        for whitelisted_rfid in whitelist:
            if verify_rfid_hash(whitelisted_rfid, rfid_hash):
                self._logger.info("RFID autorisiert: %s...", rfid_hash[:16])
                return True

        self._logger.warning("RFID NICHT autorisiert: %s...", rfid_hash[:16])
        return False

    def get_active_session(self) -> Optional[Dict[str, Any]]:
        """
        Holt die aktuell aktive Session (für Neustart-Recovery, PER-01)

        Returns:
            Session-Dict oder None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM sessions
            WHERE status = 'active'
            ORDER BY start_time DESC
            LIMIT 1
        ''')

        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def recover_active_sessions(self) -> list:
        """
        Findet aktive Sessions beim Neustart (PER-02)
        Prüft ob Session noch aktiv oder abgeschlossen

        Returns:
            Liste der wiederhergestellten Sessions
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM sessions
            WHERE status = 'active'
            ORDER BY start_time DESC
        ''')

        active_sessions = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if active_sessions:
            self._logger.info("Gefundene aktive Sessions beim Start: %d", len(active_sessions))

        return active_sessions

    def handle_recovered_session(self, session: Dict, wallbox_status: str = None) -> Dict:
        """
        Behandelt eine wiederhergestellte Session beim Neustart (PER-03)

        Args:
            session: Die wiederhergestelle Session
            wallbox_status: Aktueller Wallbox-Status (falls verfügbar)

        Returns:
            Dict mit action und session
        """
        if wallbox_status in [None, 'Unknown']:
            return {
                'action': 'incomplete',
                'session': session,
                'reason': 'status_unknown'
            }

        if wallbox_status in ['Idle', 'Stopped']:
            return {
                'action': 'terminate',
                'session': session,
                'reason': 'wallbox_stopped'
            }

        return {
            'action': 'continue',
            'session': session,
            'reason': 'still_charging'
        }

    def mark_session_incomplete(self, session_id: int, reason: str = 'crash_recovery'):
        """
        Markiert eine Session als unvollständig (PER-03)

        Args:
            session_id: ID der Session
            reason: Grund für die Markierung
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE sessions
            SET status = 'incomplete', end_time = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), session_id))
        conn.commit()
        conn.close()
        self._logger.warning("Session %d als unvollständig markiert: %s", session_id, reason)

    def get_sessions_by_wallbox(self, wallbox_id: str) -> list:
        """
        Holt alle Sessions für eine spezifische Wallbox (EXT-01)

        Args:
            wallbox_id: ID der Wallbox

        Returns:
            Liste von Session-Dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM sessions
            WHERE wallbox_id = ?
            ORDER BY start_time DESC
        ''', (wallbox_id,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def start_session(self, rfid_hex: str, start_energy_kwh: float, wallbox_id: str = "alfen_eve") -> Optional[int]:
        """
        Startet eine neue Lade-Session (HA-03, HA-04)

        Args:
            rfid_hex: RFID als Hex-String
            start_energy_kwh: Energie-Zählerstand bei Start
            wallbox_id: ID der Wallbox

        Returns:
            Session-ID oder None bei Fehler
        """
        # Prüfen ob bereits eine aktive Session läuft
        active = self.get_active_session()
        if active:
            self._logger.warning("Bestehende aktive Session: ID=%s", active['id'])
            return None

        rfid_hash = hash_rfid(rfid_hex)
        start_time = datetime.now().isoformat()
        created_at = datetime.now().isoformat()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO sessions (rfid_hash, wallbox_id, start_time, start_energy_kwh, status, created_at)
            VALUES (?, ?, ?, ?, 'active', ?)
        ''', (rfid_hash, wallbox_id, start_time, start_energy_kwh, created_at))

        session_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self._logger.info("Session gestartet: ID=%s, RFID=%s..., Energie=%.2f kWh",
                       session_id, rfid_hash[:16], start_energy_kwh)
        return session_id

    def end_session(self, end_energy_kwh: float) -> Optional[Dict[str, Any]]:
        """
        Beendet die aktive Lade-Session (HA-05, HA-06)

        Args:
            end_energy_kwh: Energie-Zählerstand bei Ende

        Returns:
            Session-Dict mit berechneten Werten oder None
        """
        active = self.get_active_session()
        if not active:
            self._logger.warning("Keine aktive Session zum Beenden")
            return None

        end_time = datetime.now().isoformat()
        total_kwh = end_energy_kwh - active['start_energy_kwh']
        total_kwh = max(0.0, total_kwh)  # Negativer Wert verhindern

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE sessions
            SET end_time = ?, end_energy_kwh = ?, total_kwh = ?, status = 'completed'
            WHERE id = ?
        ''', (end_time, end_energy_kwh, total_kwh, active['id']))

        conn.commit()
        conn.close()

        completed_session = {
            'id': active['id'],
            'rfid_hash': active['rfid_hash'],
            'wallbox_id': active['wallbox_id'],
            'start_time': active['start_time'],
            'end_time': end_time,
            'start_energy_kwh': active['start_energy_kwh'],
            'end_energy_kwh': end_energy_kwh,
            'total_kwh': total_kwh
        }

        self._logger.info("Session beendet: ID=%s, Verbrauch=%.2f kWh",
                       active['id'], total_kwh)
        return completed_session

    def get_completed_sessions(self, limit: int = 10) -> list:
        """
        Holt abgeschlossene Sessions (für API-Übertragung an Dolibarr, Phase 3)

        Args:
            limit: Maximale Anzahl an Sessions

        Returns:
            Liste von Session-Dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM sessions
            WHERE status = 'completed'
            ORDER BY end_time DESC
            LIMIT ?
        ''', (limit,))

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def transmit_completed_sessions(self, api_client: Any) -> Dict[str, Any]:
        """
        Überträgt abgeschlossene (noch nicht übertragene) Sessions an Dolibarr

        Args:
            api_client: WallboxApiClient Instanz für API-Calls

        Returns:
            Dict mit transmitted, failed, errors
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Sessions finden: end_time IS NOT NULL und transmitted_at IS NULL
            # Ausschluss: upload_status IN ('ok', 'dead_letter') — verhindert Doppel-Retry (T-08-05)
            cursor.execute('''
                SELECT id, rfid_hash, wallbox_id, start_time, end_time, total_kwh
                FROM sessions
                WHERE end_time IS NOT NULL AND transmitted_at IS NULL
                  AND (upload_status IS NULL OR upload_status NOT IN ('ok', 'dead_letter'))
            ''')

            rows = cursor.fetchall()

            result = {
                "transmitted": 0,
                "failed": 0,
                "errors": []
            }

            for row in rows:
                session_id = row[0]
                session_data = {
                    "rfid_hash": row[1],
                    "wallbox_id": row[2],
                    "start_time": format_iso8601(row[3]),
                    "end_time": format_iso8601(row[4]),
                    "kwh": row[5] if row[5] else 0.0
                }

                # Session an Dolibarr übertragen
                success, error = api_client.transmit_session(session_data)

                if success:
                    # transmitted_at, upload_status und upload_error setzen (MON-01, D-09)
                    cursor.execute('''
                        UPDATE sessions SET transmitted_at = ?, upload_status = ?, upload_error = ? WHERE id = ?
                    ''', (datetime.now().isoformat(), 'ok', None, session_id))
                    result["transmitted"] += 1
                    self._logger.info("Session %s erfolgreich übertragen", session_id)
                else:
                    error_msg = f"Session {session_id}: {error}"
                    result["errors"].append(error_msg)
                    result["failed"] += 1
                    self._logger.error("Fehler bei Session %s: %s", session_id, error)

                    # upload_status='dead_letter' und Fehlermeldung in SQLite schreiben (RET-01)
                    cursor.execute('''
                        UPDATE sessions SET upload_status = ?, upload_error = ? WHERE id = ?
                    ''', ('dead_letter', error[:1000] if error else 'Unknown error', session_id))
                    cursor.execute('''
                        INSERT OR IGNORE INTO dead_letter
                        (session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh,
                         error_msg, retry_count, status, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'pending', ?)
                    ''', (session_id, row[1], row[2], row[3], row[4],
                          row[5] or 0.0, error[:1000] if error else 'Unknown error',
                          datetime.now().isoformat()))
                    self._logger.warning("Session %s in Dead-letter Queue geschrieben (RET-01)", session_id)
                    continue  # WR-03: process remaining sessions (do not break)

            conn.commit()
        finally:
            conn.close()

        self._logger.info("API-Übertragung abgeschlossen: %s übertragen, %s fehlgeschlagen",
                         result["transmitted"], result["failed"])

        return result

    def retry_dead_letter_sessions(self, api_client: Any) -> Dict[str, Any]:
        """Retries all pending dead-letter entries. Called from periodic_transmission() (RET-03).
        D-01: continues to next entry on failure — does NOT break."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh "
                "FROM dead_letter WHERE status = 'pending'"
            )
            rows = cursor.fetchall()
            result = {"retried": 0, "resolved": 0, "still_failed": 0, "errors": []}

            for row in rows:
                dl_id, session_id = row[0], row[1]
                session_data = {
                    "rfid_hash": row[2], "wallbox_id": row[3],
                    "start_time": format_iso8601(row[4]), "end_time": format_iso8601(row[5]),
                    "kwh": row[6] or 0.0
                }
                try:
                    success, error = api_client.transmit_session(session_data)
                    result["retried"] += 1
                    if success:
                        cursor.execute(
                            "UPDATE dead_letter SET status='resolved', last_retry_at=? WHERE id=?",
                            (datetime.now().isoformat(), dl_id)
                        )
                        cursor.execute(
                            "UPDATE sessions SET transmitted_at=?, upload_status='ok', upload_error=NULL WHERE id=?",
                            (datetime.now().isoformat(), session_id)
                        )
                        result["resolved"] += 1
                        self._logger.info("Dead-letter Session %s erfolgreich wiederholt (RET-03)", session_id)
                    else:
                        cursor.execute(
                            "UPDATE dead_letter SET retry_count=retry_count+1, error_msg=?, last_retry_at=? WHERE id=?",
                            (error[:1000] if error else 'Unknown error', datetime.now().isoformat(), dl_id)
                        )
                        result["still_failed"] += 1
                        self._logger.warning("Dead-letter Session %s Retry fehlgeschlagen: %s", session_id, error)
                except Exception as e:
                    self._logger.error("Dead-letter Retry Fehler fuer id=%s: %s", dl_id, e)
                    result["errors"].append(str(e))
                    continue  # D-01: do NOT break

            conn.commit()
        finally:
            conn.close()
        return result

    def retry_single_dead_letter(self, api_client: Any, dead_letter_id: int) -> Dict[str, Any]:
        """Retries a single dead-letter entry by id. Used by /session/retry HTTP endpoint (RET-02)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh "
            "FROM dead_letter WHERE id = ? AND status = 'pending'",
            (dead_letter_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return {"success": False, "error": "dead_letter_id not found or not pending"}

        dl_id, session_id = row[0], row[1]
        session_data = {
            "rfid_hash": row[2], "wallbox_id": row[3],
            "start_time": format_iso8601(row[4]), "end_time": format_iso8601(row[5]),
            "kwh": row[6] or 0.0
        }
        try:
            success, error = api_client.transmit_session(session_data)
            if success:
                cursor.execute(
                    "UPDATE dead_letter SET status='resolved', last_retry_at=? WHERE id=?",
                    (datetime.now().isoformat(), dl_id)
                )
                cursor.execute(
                    "UPDATE sessions SET transmitted_at=?, upload_status='ok', upload_error=NULL WHERE id=?",
                    (datetime.now().isoformat(), session_id)
                )
                conn.commit()
                conn.close()
                self._logger.info("Dead-letter id=%s manuell aufgeloest (RET-02)", dead_letter_id)
                return {"success": True, "error": ""}
            else:
                cursor.execute(
                    "UPDATE dead_letter SET retry_count=retry_count+1, error_msg=?, last_retry_at=? WHERE id=?",
                    (error[:1000] if error else 'Unknown error', datetime.now().isoformat(), dl_id)
                )
                conn.commit()
                conn.close()
                self._logger.warning("Dead-letter id=%s manueller Retry fehlgeschlagen: %s", dead_letter_id, error)
                return {"success": False, "error": error or "Unknown error"}
        except Exception as e:
            conn.close()
            self._logger.error("retry_single_dead_letter Fehler: %s", e)
            return {"success": False, "error": str(e)}

    def get_pending_dead_letters(self) -> list:
        """Returns pending dead-letter entries as list of dicts.
        rfid_hash is NEVER included in the SELECT (SEC-01/02, D-04)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, session_id, wallbox_id, start_time, end_time, total_kwh, "
            "error_msg, retry_count, status, created_at, last_retry_at "
            "FROM dead_letter WHERE status = 'pending' ORDER BY created_at ASC"
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_recent_sessions(self, limit: int = 25) -> list:
        """Returns last N completed sessions for the dashboard.
        rfid_hash is NEVER included in the SELECT (SEC-01/02)."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, start_time, end_time, wallbox_id, total_kwh, "
                "upload_status, upload_error "
                "FROM sessions WHERE status = 'completed' "
                "ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "start_time": row[1] or "",
                    "end_time": row[2] or "",
                    "wallbox_id": row[3] or "",
                    "total_kwh": row[4] or 0.0,
                    "upload_status": row[5] or "pending",
                    "upload_error": row[6] or "",
                }
                for row in rows
            ]
        except Exception as e:
            self._logger.error("get_recent_sessions Fehler: %s", e)
            return []
        finally:
            conn.close()

    def get_stats(self) -> dict:
        """Returns session counts by upload_status for the dashboard."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT upload_status, COUNT(*) FROM sessions "
                "WHERE status = 'completed' GROUP BY upload_status"
            )
            counts: dict = {}
            for row in cursor.fetchall():
                counts[row[0] or "pending"] = row[1]

            cursor.execute(
                "SELECT COUNT(*) FROM dead_letter WHERE status = 'pending'"
            )
            dead_letter_pending = cursor.fetchone()[0]

            total = sum(counts.values())
            return {
                "total": total,
                "ok": counts.get("ok", 0),
                "error": counts.get("error", 0),
                "dead_letter": counts.get("dead_letter", 0),
                "pending": counts.get("pending", 0),
                "dead_letter_pending": dead_letter_pending,
            }
        except Exception as e:
            self._logger.error("get_stats Fehler: %s", e)
            return {
                "total": 0, "ok": 0, "error": 0,
                "dead_letter": 0, "pending": 0, "dead_letter_pending": 0,
            }
        finally:
            conn.close()
