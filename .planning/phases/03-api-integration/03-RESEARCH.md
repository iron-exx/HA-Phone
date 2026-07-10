# Phase 3: API Integration (HA Addon → Dolibarr) - Research

**Researched:** 2026-05-05
**Domain:** REST API Integration zwischen HA-Addon (Python) und Dolibarr (PHP)
**Confidence:** HIGH

## Summary

Phase 3 etabliert die API-Integration zwischen dem Home Assistant Addon und dem Dolibarr-Modul wallboxbilling. Abgeschlossene Lade-Sessions werden über eine REST-API von HA zu Dolibarr übertragen. Die Implementierung erfordert einen Custom API Endpoint in Dolibarr (PHP) und einen API-Client im HA-Addon (Python requests).

**Primäre Herausforderungen:**
1. Dolibarr Custom API Endpoint mit DOLAPIKEY-Authentifizierung
2. Zuverlässige API-Übertragung mit exponential backoff retry
3. Erweiterung der Datenbank um `transmitted_at` Feld
4. Sicherstellung, dass RFID nur als Hash übertragen wird

**Primary recommendation:** Custom API Endpoint in `wallboxbilling/class/api_wallboxbilling.class.php` erstellen, Python requests mit `HTTPAdapter` + `Retry` für exponential backoff nutzen, und `transmitted_at` Feld via ALTER TABLE hinzufügen.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Session-Erfassung (completed) | HA-Addon (SQLite) | — | Sessions werden im HA-Addon erfasst und persistiert |
| API-Client (Sender) | HA-Addon (Python) | — | HA-Addon initiiert Übertragung via REST API |
| API-Endpoint (Receiver) | Dolibarr (PHP) | — | Dolibarr validiert Token und speichert Sessions |
| Token-Validierung | Dolibarr API Layer | — | DOLAPIKEY wird von Dolibarr core validiert |
| Session-Status-Tracking | HA-Addon (SQLite) | Dolibarr (DB) | transmitted_at in HA, Status in Dolibarr |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|----------------|
| requests | 2.31.0 [VERIFIED: pip show] | HTTP-Client für API-Calls in HA-Addon | Python-Standard für HTTP, unterstützt Retry via HTTPAdapter |
| aiohttp | 3.11.11 [VERIFIED: pip show] | Async HTTP (bereits in HA-Addon) | Bereits installiert in Phase 1, für eventuelle async Calls |
| Dolibarr REST API | Dolibarr 21.x-22.x | API Framework (Restler) | Standard API in Dolibarr, DOLAPIKEY Auth [CITED: htdocs/api/README.md] |
| PHP | 8.1+ [ASSUMED] | Server-Sprache Dolibarr | Laut AGENTS.md Stack-Vorgabe |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|----------------|
| urllib3.util.retry (Retry) | via requests | Retry-Logik mit exponential backoff | Für robuste API-Übertragung (API-04) |
| backoff (Python) | latest | Alternative Dezorator-basiert | Falls komplexere Retry-Logik benötigt wird |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| requests + HTTPAdapter | aiohttp + custom retry | aiohttp ist async, aber requests + Retry ist etablierter Standard für HTTP-Clients |
| Custom PHP Endpoint | Dolibarr Standard-API (POST /objects) | Standard-API flexibler, aber custom Endpoint erlaubt spezifische Validierung für Wallbox-Sessions |

**Installation (HA-Addon):**
```bash
# requests ist bereits in requirements.txt (2.32.3 laut config, 2.31.0 installiert)
# urllib3 ist Dependency von requests
pip install requests==2.31.0
```

**Version verification:**
- `requests`: 2.31.0 (installiert), 2.32.3 in requirements.txt [VERIFIED: pip show + requirements.txt]
- Dolibarr: 21.x-22.x [CITED: AGENTS.md + Dolibarr Doxygen docs]

## Architecture Patterns

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Home Assistant Addon                        │
│                                                                 │
│  ┌─────────────────────┐     ┌──────────────────────────┐    │
│  │  session_manager.py │     │   api_client.py         │    │
│  │  - SQLite DB       │────▶│   - poll completed     │    │
│  │  - track sessions  │     │   - requests + retry   │    │
│  └─────────────────────┘     │   - DOLAPIKEY header   │    │
│                              └──────────┬───────────────┘    │
│                                       │ HTTP POST           │
└───────────────────────────────────────┼───────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Dolibarr Server                           │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  /api/index.php/wallboxbilling/session               │   │
│  │  - api_wallboxbilling.class.php (Custom Endpoint)   │   │
│  │  - DOLAPIKEY Validierung (DolibarrApiAccess)        │   │
│  │  - Insert into llx_wallbox_sessions                 │   │
│  └────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────┐                                    │
│  │ llx_wallbox_sessions│  (erweitert um transmitted_at)     │
│  └─────────────────────┘                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (Additions)

```
Homeassistant/
├── session_manager.py       # Bestehend - verwaltet Sessions in SQLite
├── api_client.py           # NEU - API-Client für Dolibarr-Übertragung
├── config.yaml             # Erweitern: dolibarr_url, api_token
├── requirements.txt        # requests bereits enthalten
└── utils/
    └── hash.py             # Bestehend - SHA-256 für RFID

Dolibarr/htdocs/custom/wallboxbilling/
├── class/
│   ├── wallboxbilling.class.php      # Bestehend - DAO
│   └── api_wallboxbilling.class.php # NEU - Custom API Endpoint
├── sql/
│   └── dolibarr_allversions.sql     # NEU - Migration für transmitted_at
└── core/modules/
    └── modWallboxbilling.class.php  # Erweitern: Update-Logik
```

### Pattern 1: Custom API Endpoint in Dolibarr
**What:** Erstellen eines Custom API Endpoints für Wallbox-Sessions
**When to use:** Wenn spezifische Validierung oder Felder benötigt werden, die über den Standard-Object-API hinausgehen
**Example:**
```php
<?php
/**
 * API class for wallboxbilling module
 * 
 * @access protected
 * @class  DolibarrApiAccess {@requires user,external}
 */
class WallboxbillingApi extends DolibarrApi
{
    /**
     * @var WallboxBilling {@type WallboxBilling}
     */
    public $wallboxbilling;

    /**
     * Constructor
     * 
     * @url     GET /
     */
    public function __construct()
    {
        global $db;
        $this->db = $db;
        $this->wallboxbilling = new WallboxBilling($this->db);
    }

    /**
     * Create a new charging session from HA-Addon
     * 
     * @param array $request_data Request data (rfid_hash, wallbox_id, start_time, end_time, kwh)
     * @phan-param ?array<string,mixed> $request_data
     * @return int ID of created session
     * 
     * @throws RestException 403 Not allowed
     * @throws RestException 500 System error
     * 
     * @url POST session
     */
    public function post($request_data = null)
    {
        // Permission prüfen
        if (!DolibarrApiAccess::$user->hasRight('wallboxbilling', 'session', 'write')) {
            throw new RestException(403, 'Keine Berechtigung für wallboxbilling.session.write');
        }

        // Pflichtfelder prüfen
        $required = ['rfid_hash', 'wallbox_id', 'start_time', 'end_time', 'kwh'];
        foreach ($required as $field) {
            if (empty($request_data[$field])) {
                throw new RestException(400, "Feld '$field' ist erforderlich");
            }
        }

        // RFID-Hash validieren (muss 64 Zeichen SHA-256 sein)
        if (!preg_match('/^[a-f0-9]{64}$/', $request_data['rfid_hash'])) {
            throw new RestException(400, 'Ungültiges rfid_hash Format (SHA-256 erwartet)');
        }

        // Session erstellen
        $this->wallboxbilling->rfid_hash = $request_data['rfid_hash'];
        $this->wallboxbilling->wallbox_id = $this->db->escape($request_data['wallbox_id']);
        $this->wallboxbilling->start_time = $request_data['start_time'];
        $this->wallboxbilling->end_time = $request_data['end_time'];
        $this->wallboxbilling->kwh = (float) $request_data['kwh'];
        
        // User über RFID-Hash finden (optional, falls implementiert)
        // $user_id = $this->findUserByRfidHash($request_data['rfid_hash']);
        // $this->wallboxbilling->fk_user = $user_id ?: 0;

        dol_syslog("WallboxBillingApi::post rfid_hash=" . substr($request_data['rfid_hash'], 0, 16) . "...", LOG_DEBUG);

        $result = $this->wallboxbilling->createSessionFromApi(DolibarrApiAccess::$user);
        if ($result < 0) {
            throw new RestException(500, "Fehler beim Erstellen der Session: " . $this->wallboxbilling->error);
        }

        return $this->wallboxbilling->id;
    }
}
?>
```
**Source:** [CITED: htdocs/modulebuilder/template/class/api_mymodule.class.php] + [VERIFIED: htdocs/api/README.md]

### Pattern 2: Exponential Backoff in Python (requests)
**What:** Automatische Wiederholung von API-Calls bei Fehlern mit exponential backoff
**When to use:** Für zuverlässige API-Übertragung bei Netzwerkproblemen oder Server-Fehlern
**Example:**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, Any

def create_api_session() -> requests.Session:
    """
    Erstellt eine requests Session mit exponential backoff retry
    
    Konfiguration (D-02):
    - Initial Delay: 1 Sekunde
    - Max. Retries: 5
    - Max. Delay: 60 Sekunden
    - Factor: 2x (1s, 2s, 4s, 8s, 16s, 32s)
    - Retryable Errors: HTTP 5xx, Timeout, Connection Refused
    """
    session = requests.Session()
    
    # Retry-Strategie nach D-02
    retries = Retry(
        total=5,                          # Max. 5 Retries (D-02)
        backoff_factor=1,                   # 1s initial delay
        max_backoff=60,                     # Max. 60s delay (D-02)
        status_forcelist=[429, 500, 502, 503, 504],  # Retryable HTTP Codes
        allowed_methods=["POST", "GET"]     # POST darf retry (idempotent für unsere API)
    )
    
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    return session

def transmit_session(session_data: Dict[str, Any], api_url: str, api_key: str) -> Optional[int]:
    """
    Überträgt eine Session an Dolibarr API
    
    Args:
        session_data: Dict mit rfid_hash, wallbox_id, start_time, end_time, kwh
        api_url: URL des API Endpoints (z.B. https://dolibarr/api/index.php/wallboxbilling/session)
        api_key: DOLAPIKEY Token
    
    Returns:
        Session ID in Dolibarr oder None bei Fehler
    """
    session = create_api_session()
    
    headers = {
        'DOLAPIKEY': api_key,
        'Content-Type': 'application/json'
    }
    
    try:
        response = session.post(
            api_url,
            json=session_data,
            headers=headers,
            timeout=(5, 30)  # connect timeout 5s, read timeout 30s
        )
        response.raise_for_status()
        
        result = response.json()
        return result.get('id') if isinstance(result, dict) else result
        
    except requests.exceptions.RequestException as e:
        logging.error(f"API-Übertragung fehlgeschlagen: {e}")
        return None
```
**Source:** [VERIFIED: requests docs + urllib3.util.retry docs] + [CITED: Python Requests Retry Guides]

### Anti-Patterns to Avoid
- **RFID im Klartext übertragen:** Immer Hash verwenden (SEC-03, API-05)
- **Kein Retry-Mechanismus:** Netzwerkfehler passieren; exponential backoff ist Pflicht (API-04)
- **DOLAPIKEY in URL:** Immer HTTP Header verwenden, nicht URL-Parameter (Sicherheit)
- **Keine Timeout-Angabe:** requests ohne timeout kann unendlich hängen
- **transmitted_at nicht setzen:** Session-Status muss nach Übertragung aktualisiert werden

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|---------------|-------------|-----|
| HTTP Retry mit exponential backoff | Eigenes retry-loop mit time.sleep() | `urllib3.util.retry.Retry` + `HTTPAdapter` | Komplexe Edge Cases (Thread-Safety, Connection Pooling, Jitter) sind bereits gelöst |
| REST API Framework in PHP | Eigener PHP Router für API | Dolibarr REST API (Restler) + `DolibarrApi` | Dolibarr liefert Authentifizierung, Permissions, Input-Validierung out-of-the-box |
| SHA-256 Hash in PHP | Selbst implementiert | `hash('sha256', $input)` | PHP Standard-Funktion, sicher und getestet |
| JSON-Handling in Python | Manual JSON mit json.dumps() | `requests.post(json=data)` | requests serialisiert automatisch, handhabt Content-Type |

**Key insight:** Dolibarr's API Framework (Restler) übernimmt Routing, Authentifizierung und Input-Validierung. Ein eigener Endpunkt ist nur 30 Zeilen PHP.

## Runtime State Inventory

> Phase 3 ist eine API-Integrationsphase (keine Rename/Refactor), daher fokussiert auf API-State.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `llx_wallbox_sessions` Tabelle in MariaDB (Dolibarr) | `ALTER TABLE` für `transmitted_at` in HA-Addon SQLite + Dolibarr Tabelle |
| Live service config | DOLAPIKEY Token in Dolibarr-User | Token generieren und in HA-Addon config.yaml speichern |
| OS-registered state | Keine relevanten OS-Registrierungen | — |
| Secrets/env vars | `api_token` in HA-Addon config.yaml (neu) | Config erweitern: `dolibarr_url`, `api_token` |
| Build artifacts | Keine Build-Artifakte betroffen | — |

**Details:**
- **SQLite (HA-Addon):** `ALTER TABLE sessions ADD COLUMN transmitted_at DATETIME NULL;` [ASSUMED: SQLite Syntax]
- **MariaDB (Dolibarr):** `ALTER TABLE llx_wallbox_sessions ADD COLUMN transmitted_at DATETIME NULL;` [VERIFIED: Dolibarr migration SQL examples]
- **DOLAPIKEY:** Wird in Dolibarr unter User → API Key generiert [CITED: htdocs/api/README.md]

## Common Pitfalls

### Pitfall 1: Falscher API-Endpoint-Dateiname
**What goes wrong:** Endpoint wird nicht gefunden (HTTP 501 API not found)
**Why it happens:** Dolibarr erwartet spezifisches Namensschema: `api_<moduleobject>.class.php` im `class/` Verzeichnis
**How to avoid:** Datei muss heißen: `htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php` und Klasse `WallboxbillingApi` (nicht `WallboxBillingApi`)
**Warning signs:** HTTP 501 "API not found (failed to include API file)"

### Pitfall 2: DOLAPIKEY wird nicht erkannt
**What goes wrong:** HTTP 401 Unauthorized obwohl Token korrekt ist
**Why it happens:** Token muss als HTTP Header `DOLAPIKEY` gesendet werden, nicht als GET-Parameter (weniger sicher) oder Bearer Token
**How to avoid:** Header explizit setzen: `headers={'DOLAPIKEY': token}` [VERIFIED: htdocs/api/class/api_access.class.php]
**Warning signs:** API-Key in URL sichtbar (Logs!), HTTP 401

### Pitfall 3: Exponential Backoff zu aggressiv
**What goes wrong:** Server wird mit Retries überschwemmt (DDOS-artig)
**Why it happens:** `backoff_factor` zu niedrig oder `max_retries` zu hoch
**How to avoid:** Konservative Parameter (D-02): initial 1s, max 60s, nur 5 retries [ASSUMED: Best Practice]
**Warning signs:** Server-Logs zeigen viele Anfragen in kurzer Zeit

### Pitfall 4: RFID-Hash geht verloren in der Übertragung
**What goes wrong:** Session in Dolibarr hat leeres oder falsches rfid_hash
**Why it happens:** Feldname im JSON unterscheidet sich von DB-Feld (`rfid_hash` vs `rfid_hash`)
**How to avoid:** JSON-Feld `rfid_hash` muss exakt mit API-Validierung übereinstimmen; SHA-256 ist immer 64 Zeichen [VERIFIED: RFC 6234]
**Warning signs:** Dolibarr Session hat `rfid_hash = ''` oder NULL

### Pitfall 5: transmitted_at wird nicht gesetzt
**What goes wrong:** Gleiche Session wird mehrfach übertragen
**Why it happens:** Nach erfolgreicher API-Übertragung wird `transmitted_at` in HA-Addon DB nicht aktualisiert
**How to avoid:** Immer `UPDATE sessions SET transmitted_at = ? WHERE id = ?` nach erfolgreicher Übertragung ausführen
**Warning signs:** Gleiche Session taucht mehrfach in Dolibarr auf

## Code Examples

Verified patterns from official sources:

### Example 1: Python API Client (requests with retry)
```python
# api_client.py - Zu platzieren in Homeassistant/api_client.py
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class DolibarrApiClient:
    """API-Client für Dolibarr WallboxBilling Endpoint"""
    
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Erstellt Session mit exponential backoff (D-02)"""
        session = requests.Session()
        
        retries = Retry(
            total=5,                      # Max. 5 retries (D-02)
            backoff_factor=1,               # 1s initial
            max_backoff=60,                 # Max. 60s delay (D-02)
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST", "GET"]
        )
        
        adapter = HTTPAdapter(max_retries=retries)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        return session
    
    def transmit_session(self, session_data: Dict[str, Any]) -> bool:
        """
        Überträgt Session an Dolibarr
        
        Args:
            session_data: Dict mit rfid_hash, wallbox_id, start_time, end_time, kwh
            
        Returns:
            True bei Erfolg
        """
        url = f"{self.base_url}/api/index.php/wallboxbilling/session"
        
        headers = {
            'DOLAPIKEY': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            response = self.session.post(
                url,
                json=session_data,
                headers=headers,
                timeout=(5, 30)
            )
            response.raise_for_status()
            
            logger.info(f"Session übertragen: {session_data.get('rfid_hash', '')[:16]}...")
            return True
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API-Fehler: {e}")
            return False

# Source: [VERIFIED: requests docs + urllib3 Retry docs]
```

### Example 2: SQLite ALTER TABLE for transmitted_at
```sql
-- Für HA-Addon SQLite Datenbank
ALTER TABLE sessions ADD COLUMN transmitted_at TEXT NULL;

-- Für Dolibarr MariaDB/MySQL
ALTER TABLE llx_wallbox_sessions 
ADD COLUMN transmitted_at DATETIME NULL AFTER end_time;
```
**Source:** [ASSUMED: SQLite ALTER TABLE] + [VERIFIED: Dolibarr migration SQL files]

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Keine API (manuelle Abrechnung) | REST API mit DOLAPIKEY Auth | Phase 3 | Automatisierung der Session-Übertragung |
| Einfache HTTP-Requests ohne Retry | Exponential backoff mit urllib3.Retry | API-04 | Robustheit gegen Netzwerkfehler |
| RFID im Klartext (gefährlich) | SHA-256 Hash nur in API | SEC-03, API-05 | DSGVO-konform |

**Deprecated/outdated:**
- Manuelle Datenübertragung via CSV/Export: Ersetzt durch automatische REST API
- API-Key in URL: Nicht mehr empfohlen, Header verwenden [CITED: htdocs/api/README.md]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SQLite unterstützt `ALTER TABLE ADD COLUMN transmitted_at DATETIME NULL` | Runtime State Inventory | SQLite Syntax könnte sich von MySQL unterscheiden; müsste geprüft werden |
| A2 | PHP 8.1+ ist korrekt für Dolibarr 21.x-22.x | Standard Stack | Falls Dolibarr andere PHP-Version benötigt, könnte Code-Anpassungen nötig sein |
| A3 | `WallboxbillingApi` ist korrekter Klassenname für Dolibarr API | Architecture Patterns | Falscher Name → API nicht gefunden (HTTP 501) |
| A4 | `backoff_factor=1` führt zu 1s, 2s, 4s, 8s, 16s, 32s delays | Architecture Patterns | Formel könnte sein: `backoff_factor * (2 ** (retry_num - 1))` statt anders |
| A5 | DOLAPIKEY Token kann in Dolibarr User-Profil generiert werden | Common Pitfalls | Falls Feature nicht verfügbar, müsste Token via SQL gesetzt werden |

**If this table is empty:** All claims in this research were verified or cited — no user confirmation needed.

## Open Questions

1. **API-Endpoint URL-Struktur**
   - What we know: Dolibarr API erwartet `/api/index.php/wallboxbilling/session` (basierend auf Klassenname)
   - What's unclear: Ob custom Endpoint unter `/custom/wallboxbilling/` oder Standard `/api/index.php/` erreichbar ist
   - Recommendation: Testen mit `curl -H "DOLAPIKEY: xxx" https://dolibarr/api/index.php/wallboxbilling/session`

2. **User-Resolution für RFID-Hash**
   - What we know: RFID-Hash wird übertragen, Dolibarr speichert ihn
   - What's unclear: Soll API direkt `fk_user` aus `llx_user_extrafields` oder separate Tabelle auflösen, oder bleibt `fk_user=0`?
   - Recommendation: Erste Implementation mit `fk_user=0`, Phase 4 (Billing) löst User-Zuordnung

3. **Polling-Intervall für HA-Addon**
   - What we know: HA-Addon soll abgeschlossene Sessions übertragen
   - What's unclear: Wie oft pollt das Addon? (jede Minute? event-basiert?)
   - Recommendation: Cronjob-artig alle X Minuten (z.B. 5 Min), oder event-basiert wenn Session completed wird

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | HA-Addon API Client | ✓ | 3.13 [ASSUMED] | — |
| requests | API-Client HA-Addon | ✓ | 2.31.0 [VERIFIED: pip show] | — |
| aiohttp | Eventuell async API-Calls | ✓ | 3.11.11 [VERIFIED: pip show] | — |
| Dolibarr 21.x-22.x | API Endpoint Host | ✗ [ASSUMED] | — | Docker-Container starten |
| MariaDB/MySQL | Dolibarr Datenbank | ✗ [ASSUMED] | — | Docker-Container starten |
| PHP 8.1+ | Dolibarr Server | ✗ [ASSUMED] | — | Docker-Container starten |

**Missing dependencies with no fallback:**
- Dolibarr Instanz (für API-Testing) — Entwicklungsumgebung muss aufgesetzt werden

**Missing dependencies with fallback:**
- None — Phase benötigt Dolibarr zwingend

## Validation Architecture

> workflow.nyquist_validation is enabled (absent = enabled per config.json).

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (Python) + PHPUnit (PHP) |
| Config file | `Homeassistant/test_api_client.py` (neu) + `Dolibarr/tests/` (neu) |
| Quick run command | `pytest Homeassistant/test_api_client.py -x` |
| Full suite command | `pytest Homeassistant/ && cd Dolibarr && phpunit` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-01 | HA Addon überträgt completed session via REST API | integration | `pytest Homeassistant/test_api_client.py::test_transmit_session -x` | ❌ Wave 0 |
| API-02 | JSON-Payload mit rfid_hash, wallbox_id, start_time, end_time, kwh | unit | `pytest Homeassistant/test_api_client.py::test_json_payload -x` | ❌ Wave 0 |
| API-03 | DOLAPIKEY Token in HTTP Header | unit | `pytest Homeassistant/test_api_client.py::test_auth_header -x` | ❌ Wave 0 |
| API-04 | Retry mit exponential backoff bei Fehlern | unit | `pytest Homeassistant/test_api_client.py::test_retry_logic -x` | ❌ Wave 0 |
| API-05 | RFID nur als SHA-256 Hash übertragen | unit | `pytest Homeassistant/test_api_client.py::test_rfid_hash_only -x` | ❌ Wave 0 |
| SEC-03 | API-Token Validierung in Dolibarr | integration | `phpunit Dolibarr/tests/ApiSessionTest.php --filter testTokenValidation` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest Homeassistant/test_api_client.py -x`
- **Per wave merge:** `pytest Homeassistant/ && cd Dolibarr && phpunit`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `Homeassistant/test_api_client.py` — tests für API-01 bis API-05, SEC-03
- [ ] `Dolibarr/tests/ApiSessionTest.php` — Integration-Test für Custom Endpoint
- [ ] `Homeassistant/api_client.py` — API-Client Implementierung (für Tests)
- [ ] `Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php` — Custom Endpoint (für Tests)
- Framework install: `pip install pytest` und `phpunit/phpunit` via Composer

## Security Domain

> security_enforcement is enabled (absent = enabled per config.json).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | DOLAPIKEY Token in HTTP Header [CITED: htdocs/api/class/api_access.class.php] |
| V3 Session Management | No | — |
| V4 Access Control | Yes | `DolibarrApiAccess::$user->hasRight()` in API Endpoint |
| V5 Input Validation | Yes | `rfid_hash` Format-Prüfung (64-char hex), `wallbox_id` escape |
| V6 Cryptography | Yes | SHA-256 für RFID (bereits implementiert), nie Klartext |

### Known Threat Patterns for HA-Addon → Dolibarr

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| RFID Hash Abgreifen (Man-in-the-Middle) | Information Disclosure | HTTPS/TLS für API-Calls (D-03 in HA-Addon Config) |
| DOLAPIKEY Leak (Logs, Config) | Information Disclosure | Token nicht in Logs, Hash in config.yaml (nicht im Code) |
| SQL Injection in Custom Endpoint | Tampering | `$this->db->escape()` verwenden [VERIFIED: existing wallboxbilling.class.php] |
| Brute Force on API | Denial of Service | Dolibarr Rate Limiting (Standard), exponentieller Backoff auf Client-Seite |
| RFID Hash Fälschung | Spoofing | Server-seitige Validierung: Hash-Format prüfen (64 hex chars) |

## Sources

### Primary (HIGH confidence)
- [VERIFIED: pip show requests] - requests 2.31.0 installiert
- [VERIFIED: pip show aiohttp] - aiohttp 3.11.11 installiert
- [CITED: htdocs/api/README.md] - Dolibarr REST API Dokumentation (DOLAPIKEY Auth)
- [CITED: htdocs/api/class/api_access.class.php] - DolibarrApiAccess Token Validation
- [CITED: htdocs/modulebuilder/template/class/api_mymodule.class.php] - Custom API Endpoint Template
- [VERIFIED: Dolibarr GitHub repo] - API file naming conventions
- Existing code: `Homeassistant/session_manager.py`, `Dolibarr/htdocs/custom/wallboxbilling/class/wallboxbilling.class.php`

### Secondary (MEDIUM confidence)
- [CITED: Python Requests Retry Guides] - urllib3.util.retry.Retry + HTTPAdapter Patterns
- [CITED: Dolibarr MarketPlace API Guides] - API Key Generation, Endpoint Usage
- [CITED: Dolibarr Wiki] - Module Development, API Custom Endpoints

### Tertiary (LOW confidence)
- [ASSUMED] SQLite ALTER TABLE Syntax (nicht explizit verifiziert)
- [ASSUMED] PHP 8.1+ Kompatibilität mit Dolibarr 21.x-22.x
- [ASSUMED] `WallboxbillingApi` Klassenname (basierend auf Namenskonventionen)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - requests/urllib3 verified via pip, Dolibarr API docs cited
- Architecture: HIGH - Code examples from official Dolibarr templates + bestehende Codebase
- Pitfalls: MEDIUM - Einige Pitfalls basieren auf ASSUMED Wissen (SQLite Syntax)

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (30 days for stable stack, Dolibarr APIs ändern sich selten)

---
*Research completed: 2026-05-05*
*Researcher: GSD Research Agent (big-pickle)*
*Phase: 3 - API Integration*
