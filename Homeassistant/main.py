#!/usr/bin/env python3
"""
Wallbox-Dolibarr Addon Hauptskript

Verbindet sich via Websocket API mit Home Assistant Core,
liest Alfen Wallbox Sensoren aus und implementiert Session-Tracking.
"""
import asyncio
import aiohttp
from aiohttp import web
import json
import logging
import os
import sys
from typing import Dict, Any, Optional

# Hash-Utility importieren
sys.path.insert(0, '/usr/local/bin')
from utils.hash import hash_rfid

# Session Manager importieren
from session_manager import SessionManager, CHARGING, IDLE, STOPPED

# API Client importieren (Phase 3)
from api_client import WallboxApiClient

# Web Dashboard importieren
from dashboard import DASHBOARD_HTML

# Logging Setup (D-17, D-20)
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)

# Alfen Sensoren (D-09)
SENSOR_RFID = "sensor.alfen_eve_tag_socket_1"
SENSOR_ENERGY = "sensor.alfen_energy_total"
SENSOR_STATE = None  # Wird dynamisch aus Alfen Integration ermittelt

# Globale Variablen für Session-Tracking
session_manager = None
current_config = {}
ha_ws = None
api_client = None  # WallboxApiClient Instanz (wird in main() initialisiert)
health_runner = None  # aiohttp AppRunner für /health und /session/stop Endpunkte


def load_config():
    """Lädt Addon-Konfiguration aus /data/options.json (D-04)"""
    config_path = '/data/options.json'
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            _LOGGER.info("Konfiguration geladen von %s", config_path)

            # API-Konfiguration validieren (Task 3)
            api_config = config.get('api', {})
            if api_config:
                dolibarr_url = api_config.get('dolibarr_url', '')
                if dolibarr_url and not (dolibarr_url.startswith('http://') or dolibarr_url.startswith('https://')):
                    _LOGGER.warning("API-Konfiguration: dolibarr_url muss mit http:// oder https:// beginnen")

                api_token = api_config.get('api_token', '')
                if not api_token or api_token == 'your_dolapikey_here':
                    _LOGGER.warning("API-Token nicht konfiguriert oder noch Default-Wert")

            return config
    except Exception as e:
        _LOGGER.error("Fehler beim Laden der Konfiguration: %s", e)
        return {}


def apply_log_level_from_config(config: dict) -> None:
    """Setzt Log-Level aus options.json (LOG-01).
    logging.basicConfig() kann nach der ersten Handler-Registrierung nicht erneut aufgerufen
    werden — daher getLogger().setLevel() auf dem Root-Logger verwenden.
    """
    log_level_str = config.get('log_level', 'INFO').upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    _LOGGER.info("Log-Level aus options.json gesetzt: %s", log_level_str)


async def send_persistent_notification(
    title: str,
    message: str,
    notification_id: str = "wallbox_upload_error"
) -> None:
    """Sendet persistent_notification via HA Supervisor REST API (ALT-01).
    Schlägt graceful fehl wenn SUPERVISOR_TOKEN nicht gesetzt ist.
    """
    supervisor_token = os.getenv('SUPERVISOR_TOKEN', '')
    if not supervisor_token:
        _LOGGER.warning("SUPERVISOR_TOKEN nicht verfügbar — persistent_notification nicht gesendet")
        return

    headers = {
        "Authorization": f"Bearer {supervisor_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "message": message[:500],          # Max 500 Zeichen (Anti-Injection)
        "notification_id": notification_id,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://supervisor/core/api/services/persistent_notification/create",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    _LOGGER.info("persistent_notification gesendet: %s", title)
                else:
                    _LOGGER.warning("persistent_notification fehlgeschlagen: HTTP %s", resp.status)
    except Exception as e:
        _LOGGER.warning("persistent_notification Fehler: %s", e)


class HomeAssistantWebsocket:
    """Verbindung zur Home Assistant Websocket API (D-02, D-10)"""

    def __init__(self, host: str = "homeassistant", port: int = 8123):
        self.host = host
        self.port = port
        self.ws_url = f"ws://{host}:{port}/api/websocket"
        self.access_token = os.getenv('SUPERVISOR_TOKEN', '')
        self.session_id: Optional[str] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self):
        """Verbindet sich mit HA Websocket API"""
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(self.ws_url)
            _LOGGER.info("Verbunden mit HA Websocket API: %s", self.ws_url)

            # Auth-Response empfangen
            msg = await self._ws.receive_json()
            if msg.get('type') != 'auth_required':
                raise ConnectionError("Unerwartete Antwort von HA")

            # Auth senden
            await self._ws.send_json({
                'type': 'auth',
                'access_token': self.access_token
            })

            # Auth-Bestätigung
            msg = await self._ws.receive_json()
            if msg.get('type') != 'auth_ok':
                raise PermissionError("Authentifizierung fehlgeschlagen")

            _LOGGER.info("Erfolgreich authentifiziert bei Home Assistant")
            return True

        except Exception as e:
            _LOGGER.error("Verbindungsfehler: %s", e)
            await self.disconnect()
            raise

    async def subscribe_entities(self, callback):
        """Abonniert Entitäts-Updates via Websocket (D-10, event-basiert)"""
        # Subscribe to state changes
        msg_id = 1
        await self._ws.send_json({
            'id': msg_id,
            'type': 'subscribe_events',
            'event_type': 'state_changed'
        })

        msg = await self._ws.receive_json()
        if msg.get('type') != 'result' or not msg.get('success'):
            raise RuntimeError(f"Subscribe fehlgeschlagen: {msg}")

        _LOGGER.info("Erfolgreich Entitäts-Updates abonniert")

        # Nachrichten verarbeiten
        while True:
            msg = await self._ws.receive_json()
            if msg.get('type') == 'event':
                event = msg.get('event', {})
                entity_id = event.get('data', {}).get('entity_id')
                new_state = event.get('data', {}).get('new_state', {})

                if entity_id and new_state:
                    await callback(entity_id, new_state)

    async def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """Holt den aktuellen State einer Entität via REST API (CR-03).

        Uses the HA REST API instead of the websocket to avoid message-ID
        collisions with the subscribe_entities receive loop.
        """
        url = f"http://{self.host}:{self.port}/api/states/{entity_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            _LOGGER.warning("get_state REST Fehler für %s: %s", entity_id, e)
        return None

    async def disconnect(self):
        """Trennt die Verbindung"""
        if self._ws:
            await self._ws.close()
        if self._session:
            await self._session.close()
        _LOGGER.info("Verbindung getrennt")


async def sensor_callback(entity_id: str, state: Dict[str, Any]):
    """Callback für Sensor-Updates mit Session-Tracking (D-09, D-10, HA-03-HA-07)"""
    global session_manager, current_config, ha_ws

    state_value = state.get('state')

    # RFID Sensor (HA-03, HA-04, HA-07)
    if entity_id == SENSOR_RFID:
        if state_value and state_value != 'unknown':
            # Debouncing prüfen (HA-07)
            if not session_manager.debounce_rfid(state_value):
                return  # RFID debounced, ignorieren

            # RFID Whitelist prüfen (HA-02, HA-04)
            whitelist = current_config.get('rfid_whitelist', [])
            if not session_manager.is_rfid_authorized(state_value, whitelist):
                rfid_hash = hash_rfid(state_value)
                _LOGGER.warning("Nicht autorisierte RFID: %s...", rfid_hash[:16])
                return

            # Energie-Stand für Session-Start abfragen (PER-05: atomar)
            energy_state = await ha_ws.get_state(SENSOR_ENERGY)
            start_energy = float(energy_state.get('state', 0)) if energy_state else 0.0

            # Session starten (HA-03, HA-04)
            session_id = session_manager.start_session(state_value, start_energy)
            if session_id:
                _LOGGER.info("Ladevorgang gestartet: Session ID=%s", session_id)
        else:
            _LOGGER.debug("RFID Sensor unbekannt oder leer")

    # Energie Sensor (HA-06)
    elif entity_id == SENSOR_ENERGY:
        try:
            kwh = float(state_value) if state_value else 0.0

            # Wenn aktive Session, prüfen ob Wallbox noch lädt
            active_session = session_manager.get_active_session()
            if active_session:
                # Status der Wallbox abfragen (HA-05)
                # Annahme: Charging State wird über separaten Sensor ermittelt
                # oder über Energie-Änderung (vereinfacht)
                _LOGGER.debug("Aktive Session: ID=%s, Aktuelle Energie=%.2f kWh",
                             active_session['id'], kwh)
        except (ValueError, TypeError):
            _LOGGER.warning("Ungültiger Energie-Wert: %s", state_value)

    # Ladezustand (aus Alfen Integration) - HA-05
    elif 'charging' in entity_id.lower() or 'state' in entity_id.lower():
        active_session = session_manager.get_active_session()

        if state_value == IDLE or state_value == STOPPED:
            if active_session:
                # Session beenden (HA-05, HA-06)
                energy_state = await ha_ws.get_state(SENSOR_ENERGY)
                end_energy = float(energy_state.get('state', 0)) if energy_state else 0.0

                completed = session_manager.end_session(end_energy)
                if completed:
                    _LOGGER.info("Ladevorgang beendet: Session ID=%s, %.2f kWh",
                                completed['id'], completed['total_kwh'])

        elif state_value == CHARGING:
            _LOGGER.debug("Wallbox lädt (Charging)")


async def check_startup_session():
    """Prüft beim Start ob eine aktive Session existiert und führt Recovery durch (PER-02, PER-03)"""
    global session_manager, api_client

    # Startup Recovery: Alle aktiven Sessions finden (PER-02)
    recovered_sessions = session_manager.recover_active_sessions()

    if recovered_sessions:
        _LOGGER.info("=== Startup Recovery: %d aktive Sessions gefunden ===", len(recovered_sessions))

        for session in recovered_sessions:
            wallbox_status = None

            # Versuche Wallbox-Status zu ermitteln (wenn API verfügbar)
            if api_client:
                try:
                    status_result = api_client.get_wallbox_status(session['wallbox_id'])
                    if status_result and 'status' in status_result:
                        wallbox_status = status_result['status']
                except Exception as e:
                    _LOGGER.warning("Konnte Wallbox-Status nicht abfragen: %s", e)

            # Recovery-Entscheidung treffen (PER-03)
            result = session_manager.handle_recovered_session(session, wallbox_status)

            _LOGGER.info("Session %d: %s (%s)", session['id'], result['action'], result['reason'])

            if result['action'] == 'terminate':
                # Session war schon beendet - als unvollständig markieren
                session_manager.mark_session_incomplete(session['id'], result['reason'])
                _LOGGER.warning("Session %d als unvollständig markiert (Wallbox gestoppt)", session['id'])

            elif result['action'] == 'incomplete':
                # Status unbekannt - als unvollständig markieren
                session_manager.mark_session_incomplete(session['id'], result['reason'])
                _LOGGER.warning("Session %d als unvollständig markiert (Status unbekannt)", session['id'])

            elif result['action'] == 'continue':
                # Session wird fortgesetzt - läuft weiter
                _LOGGER.info("Session %d wird fortgesetzt (Wallbox noch aktiv)", session['id'])

        _LOGGER.info("=== Startup Recovery abgeschlossen ===")
    else:
        _LOGGER.info("Keine aktiven Sessions beim Start - alles bereit")


async def handle_dashboard(request):
    """GET / - Web-Dashboard HTML (single-page, selbst-enthaltend)"""
    return web.Response(text=DASHBOARD_HTML, content_type='text/html', charset='utf-8')


async def handle_api_status(request):
    """GET /api/status - Addon-Status + Session-Statistiken als JSON"""
    global session_manager, api_client
    stats = session_manager.get_stats() if session_manager else {
        "total": 0, "ok": 0, "error": 0,
        "dead_letter": 0, "pending": 0, "dead_letter_pending": 0,
    }
    stats["api_connected"] = api_client is not None
    return web.json_response(stats, status=200)


async def handle_api_sessions(request):
    """GET /api/sessions - Letzte 25 abgeschlossene Sessions als JSON (kein rfid_hash, SEC-01)"""
    if not session_manager:
        return web.json_response([], status=200)
    try:
        sessions = session_manager.get_recent_sessions(limit=25)
        return web.json_response(sessions, status=200)
    except Exception as e:
        _LOGGER.error("api/sessions Fehler: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def handle_health(request):
    """GET /health - Liveness-Check fuer Dolibarr cURL-Ping (MON-01, D-04)"""
    return web.json_response({"status": "ok", "addon": "wallbox-dolibarr"}, status=200)


async def handle_session_stop(request):
    """POST /session/stop - Manuelle Session-Beendigung durch Dolibarr-Admin (D-14, D-15)"""
    global session_manager, api_client
    try:
        data = await request.json()
        session_id = int(data.get('session_id', 0))
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)

        if not api_client:
            return web.json_response({"error": "API client not configured"}, status=503)

        # CR-03: Spezifische Session beenden bevor bulk-transmit (VERIFICATION.md Gap 2)
        session_manager.mark_session_incomplete(session_id, reason='admin_stop')

        result = session_manager.transmit_completed_sessions(api_client)
        return web.json_response(
            {"status": "ok", "transmitted": result.get("transmitted", 0), "failed": result.get("failed", 0)},
            status=200
        )
    except (ValueError, TypeError) as e:
        return web.json_response({"error": "invalid session_id"}, status=400)
    except Exception as e:
        _LOGGER.error("session/stop Fehler: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def handle_session_retry(request):
    """POST /session/retry - Admin-Triggered Retry eines Dead-letter-Eintrags (RET-02)"""
    global session_manager, api_client
    try:
        data = await request.json()
        dead_letter_id = int(data.get('dead_letter_id', 0))
        if not dead_letter_id:
            return web.json_response({"error": "dead_letter_id required"}, status=400)

        if not api_client:
            return web.json_response({"error": "API client not configured"}, status=503)

        result = session_manager.retry_single_dead_letter(api_client, dead_letter_id)
        return web.json_response(
            {"status": "ok", "success": result.get("success", False),
             "error": result.get("error", "")},
            status=200
        )
    except (ValueError, TypeError):
        return web.json_response({"error": "invalid dead_letter_id"}, status=400)
    except Exception as e:
        _LOGGER.error("session/retry Fehler: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def handle_dead_letter_list(request):
    """GET /dead-letter/list - Pending Dead-letter-Eintraege als JSON (RET-02 display)"""
    if not session_manager:  # WR-06: guard against uninitialized session_manager
        return web.json_response({"error": "not initialized"}, status=503)
    try:
        entries = session_manager.get_pending_dead_letters()
        return web.json_response(entries, status=200)
    except Exception as e:
        _LOGGER.error("dead-letter/list Fehler: %s", e)
        return web.json_response({"error": str(e)}, status=500)


async def start_health_server(port: int = 8099) -> web.AppRunner:
    """Startet aiohttp HTTP-Server fuer Dashboard + API-Endpunkte"""
    app = web.Application()
    app.router.add_get('/', handle_dashboard)
    app.router.add_get('/api/status', handle_api_status)
    app.router.add_get('/api/sessions', handle_api_sessions)
    app.router.add_get('/health', handle_health)
    app.router.add_post('/session/stop', handle_session_stop)
    app.router.add_post('/session/retry', handle_session_retry)
    app.router.add_get('/dead-letter/list', handle_dead_letter_list)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    _LOGGER.info("Health-Endpunkt gestartet auf Port %d", port)
    return runner


async def main():
    """Hauptschleife (D-03, D-10, D-11) - erweitert für Session-Tracking und API-Transmission"""
    global session_manager, current_config, ha_ws, api_client, health_runner

    _LOGGER.info("Wallbox-Dolibarr Addon startet...")

    # Session Manager initialisieren (PER-01)
    session_manager = SessionManager(db_path="/data/sessions.db")

    # Konfiguration laden (für Whitelist und API)
    current_config = load_config()
    apply_log_level_from_config(current_config)   # LOG-01: apply log_level from options.json

    # API Client initialisieren (nur wenn konfiguriert, Task 4)
    # api_client ist globale Variable (handle_session_stop braucht Zugriff)
    api_config = current_config.get("api", {})
    if api_config.get("dolibarr_url"):
        try:
            api_client = WallboxApiClient(
                base_url=api_config["dolibarr_url"],
                api_token=api_config.get("api_token", ""),
                timeout=api_config.get("timeout", 30)
            )

            # Verbindung testen
            if api_client.check_connection():
                _LOGGER.info("Dolibarr API Verbindung erfolgreich")
            else:
                _LOGGER.warning("Dolibarr API Verbindung fehlgeschlagen - wird später erneut versucht")
                api_client = None
        except Exception as e:
            _LOGGER.error("Fehler beim Initialisieren des API-Clients: %s", e)
            api_client = None
    else:
        _LOGGER.info("Keine API-Konfiguration - Addon läuft ohne API-Transmission")

    ha_ws = HomeAssistantWebsocket()
    transmission_task = None  # WR-01: declared here so finally block can cancel it

    try:
        # Verbinden
        await ha_ws.connect()

        # Prüfen ob aktive Session nach Neustart existiert (PER-01)
        await check_startup_session()

        # Periodic API Transmission als Hintergrund-Task (Task 4 - Fix: subscribe_entities blockiert)
        async def periodic_transmission():
            """Periodische API-Übertragung als Hintergrund-Task"""
            global api_client  # WR-02: need global to set api_client = None on connection loss
            import time
            last_transmit = 0
            transmit_interval = api_config.get("transmit_interval", 300)

            while True:
                if api_client:
                    current_time = time.time()
                    if (current_time - last_transmit) >= transmit_interval:
                        result = session_manager.transmit_completed_sessions(api_client)

                        if result["transmitted"] > 0:
                            _LOGGER.info("Sessions an Dolibarr übertragen: %s", result["transmitted"])

                        if result["failed"] > 0:
                            _LOGGER.error("Fehler bei API-Übertragung: %s Sessions fehlgeschlagen", result["failed"])
                            error_summary = "; ".join(result.get("errors", []))
                            await send_persistent_notification(
                                title="Wallbox Upload-Fehler",
                                message=f"{result['failed']} Session(s) konnten nicht übertragen werden: {error_summary}",
                                notification_id="wallbox_upload_error",
                            )
                            # Bei Fehlern: Verbindung neu testen, bei Verlust deaktivieren (WR-02)
                            if not api_client.check_connection():
                                _LOGGER.warning("API-Verbindung verloren - deaktiviere temporär")
                                api_client = None  # WR-02: disables further transmission attempts

                        # Dead-letter auto-retry (RET-03)
                        retry_result = session_manager.retry_dead_letter_sessions(api_client)
                        if retry_result["resolved"] > 0:
                            _LOGGER.info("Dead-letter Retries erfolgreich: %s aufgeloest", retry_result["resolved"])
                        if retry_result["still_failed"] > 0:
                            _LOGGER.warning("Dead-letter Retries ausstehend: %s Eintraege fehlgeschlagen",
                                            retry_result["still_failed"])

                        last_transmit = current_time

                await asyncio.sleep(1)

        # Hintergrund-Task starten
        if api_client:
            transmission_task = asyncio.create_task(periodic_transmission())
            _LOGGER.info("API-Transmission Hintergrund-Task gestartet")
        # transmission_task is accessible to the finally block via the outer scope

        # HTTP-Server starten via start_health_server() (MON-01, D-04)
        health_runner = await start_health_server(port=8099)
        _LOGGER.info("Wallbox-Dolibarr HTTP-Server bereit auf Port 8099")

        # Sensor-Updates abonnieren (event-basiert, D-10) - blockiert bis zur Unterbrechung
        await ha_ws.subscribe_entities(sensor_callback)

    except KeyboardInterrupt:
        _LOGGER.info("Addon wird beendet...")
    except Exception as e:
        _LOGGER.error("Fehler: %s", e, exc_info=True)
        # Crash + Supervisor restart (D-11)
        raise
    finally:
        # WR-01: cancel transmission_task on shutdown to prevent pending task warnings
        if transmission_task and not transmission_task.done():
            transmission_task.cancel()
            try:
                await transmission_task
            except asyncio.CancelledError:
                pass
        if health_runner:
            await health_runner.cleanup()
        await ha_ws.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
