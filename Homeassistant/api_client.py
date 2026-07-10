#!/usr/bin/env python3
"""
API Client für Dolibarr WallboxBilling Integration

Sendet abgeschlossene Lade-Sessions via REST API an Dolibarr.
"""

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


def format_timestamp(dt: Any) -> str:
    """
    Formatiert ein datetime-Objekt zu ISO 8601 String mit Zeitzone

    Args:
        dt: datetime-Objekt oder String

    Returns:
        ISO 8601 formatierter String (z.B. "2026-05-05T14:30:00+02:00")

    Note:
        Wenn dt bereits ein String ist, wird er unverändert zurückgegeben
    """
    if isinstance(dt, str):
        return dt

    if isinstance(dt, datetime):
        # ISO 8601 mit Zeitzone formatieren
        return dt.strftime("%Y-%m-%dT%H:%M:%S%z")

    return str(dt)


class WallboxApiClient:
    """
    API-Client für Dolibarr WallboxBilling Endpoint

    Sendet abgeschlossene Lade-Sessions via REST API mit:
    - DOLAPIKEY Authentifizierung
    - Exponential backoff retry (D-02)
    - RFID nur als SHA-256 Hash (SEC-03, API-05)
    """

    def __init__(self, base_url: str, api_token: str, timeout: int = 30):
        """
        Initialisiert den API-Client

        Args:
            base_url: Dolibarr Basis-URL (z.B. https://dolibarr.example.com)
            api_token: DOLAPIKEY Token für Authentifizierung
            timeout: Timeout für API-Calls in Sekunden
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.timeout = timeout

        # HTTP Headers mit DOLAPIKEY (API-02, SEC-03)
        self.headers = {
            "DOLAPIKEY": api_token,
            "Content-Type": "application/json"
        }

        # Retry-Strategie (D-02: Konservativ)
        retry_strategy = Retry(
            total=5,                          # Max. 5 Retries
            backoff_factor=0.5,                 # Initial 0.5s (wird zu min 1s)
            status_forcelist=[429, 500, 502, 503, 504],  # Retryable Errors
            allowed_methods=["POST"],           # Nur POST retry (idempotent für unsere API)
            raise_on_status=False               # Nicht bei Status-Fehlern werfen
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session = requests.Session()
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        _LOGGER.info("API-Client initialisiert: %s", self.base_url)

    def transmit_session(self, session_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Überträgt eine abgeschlossene Session an Dolibarr

        Args:
            session_data: Dict mit Session-Daten (rfid_hash, wallbox_id, start_time, end_time, kwh)

        Returns:
            Tuple[bool, str]: (Erfolg, Fehlermeldung)
        """
        url = f"{self.base_url}/custom/wallboxbilling/api/session.php"

        # JSON-Payload gemäß D-04 (API-01)
        payload = {
            "rfid_hash": session_data["rfid_hash"],      # Immer Hash (API-05, SEC-03)
            "wallbox_id": session_data["wallbox_id"],
            "start_time": format_timestamp(session_data["start_time"]),  # ISO 8601
            "end_time": format_timestamp(session_data["end_time"]),      # ISO 8601
            "kwh": round(float(session_data["kwh"]), 3)                # 3 Nachkommastellen
        }

        try:
            _LOGGER.debug("Sende Session an %s: rfid_hash=%s...",
                         url, payload["rfid_hash"][:16])

            response = self.session.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=self.timeout
            )

            # HTTP 4xx/5xx prüfen
            response.raise_for_status()

            _LOGGER.info("Session erfolgreich übertragen: rfid_hash=%s..., kwh=%.3f",
                        payload["rfid_hash"][:16], payload["kwh"])
            return (True, "")

        except requests.exceptions.Timeout:
            error_msg = f"Timeout nach {self.timeout}s"
            _LOGGER.error("API-Timeout: %s", error_msg)
            return (False, error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Verbindungsfehler: {e}"
            _LOGGER.error("API-Verbindungsfehler: %s", error_msg)
            return (False, error_msg)

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            _LOGGER.error("API-Fehler: %s", error_msg)
            return (False, error_msg)

        except Exception as e:
            error_msg = f"Unerwarteter Fehler: {e}"
            _LOGGER.error("API-Fehler: %s", error_msg)
            return (False, error_msg)

    def check_connection(self) -> bool:
        """
        Prüft die Verbindung zu Dolibarr (D-03)

        Returns:
            True wenn Verbindung erfolgreich (HTTP 200)
        """
        url = f"{self.base_url}/api/index.php/login"

        try:
            response = self.session.get(
                url,
                headers=self.headers,
                timeout=5  # Kurzer Timeout für Connectivity-Check
            )

            if response.status_code == 200:
                _LOGGER.info("Dolibarr API Verbindung erfolgreich")
                return True
            else:
                _LOGGER.warning("Dolibarr API Verbindung fehlgeschlagen: HTTP %s",
                               response.status_code)
                return False

        except Exception as e:
            _LOGGER.warning("Dolibarr API Verbindung fehlgeschlagen: %s", e)
            return False

    def get_wallbox_status(self, wallbox_id: str = "alfen_eve") -> Dict[str, Any]:
        """
        Ruft den Status einer spezifischen Wallbox ab (EXT-01, PER-03)

        Wird für Session Recovery beim Neustart verwendet.

        Args:
            wallbox_id: ID der abzufragenden Wallbox

        Returns:
            Dict mit status, energy, etc.
        """
        url = f"{self.base_url}/custom/wallboxbilling/api/status.php"

        try:
            response = self.session.get(
                url,
                params={"wallbox_id": wallbox_id},
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                _LOGGER.info("Wallbox %s Status: %s", wallbox_id, data.get('status', 'Unknown'))
                return data
            else:
                _LOGGER.warning("Wallbox Status abfrage fehlgeschlagen: HTTP %s", response.status_code)
                return {'status': 'Unknown', 'energy': 0}

        except Exception as e:
            _LOGGER.warning("Fehler beim Abfragen des Wallbox-Status: %s", e)
            return {'status': 'Unknown', 'energy': 0}

    def get_wallbox_sessions(self, wallbox_id: str, limit: int = 100) -> list:
        """
        Holt Sessions für eine spezifische Wallbox (EXT-01)

        Args:
            wallbox_id: ID der Wallbox
            limit: Maximale Anzahl Sessions

        Returns:
            Liste von Session-Dicts
        """
        url = f"{self.base_url}/custom/wallboxbilling/api/sessions.php"

        try:
            response = self.session.get(
                url,
                params={"wallbox_id": wallbox_id, "limit": limit},
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                sessions = response.json()
                _LOGGER.info("Gefundene Sessions für Wallbox %s: %d", wallbox_id, len(sessions))
                return sessions
            else:
                _LOGGER.warning("Sessions abfrage fehlgeschlagen: HTTP %s", response.status_code)
                return []

        except Exception as e:
            _LOGGER.warning("Fehler beim Abfragen der Sessions: %s", e)
            return []
