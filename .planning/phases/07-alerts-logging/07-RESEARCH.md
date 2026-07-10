# Phase 7: Alerts & Logging - Research

**Researched:** 2026-06-22
**Domain:** HA Addon Python alerting + Dolibarr PHP email + structured logging + log scrubbing
**Confidence:** HIGH (codebase verified) / MEDIUM (HA Supervisor API pattern, Dolibarr CMailFile)

---

## Summary

Phase 7 hat zwei klar abgegrenzte Subsysteme: das HA-Addon (Python/asyncio) und das Dolibarr-Modul (PHP). Beide brauchen unabhängige Änderungen, die aber keine strukturellen Umbauten erfordern — es sind gezielte Erweiterungen an bereits existierenden Stellen.

**HA-Addon-Seite (LOG-01, LOG-02, ALT-01):** Das Log-Level aus `config.yaml`/`options.json` wird aktuell NICHT angewendet. `main.py` liest `LOG_LEVEL` aus einem Umgebungsvariablen-Fallback (`os.getenv('LOG_LEVEL', 'INFO')`), ignoriert aber den `log_level`-Wert aus `options.json`. Das ist der zentrale LOG-01-Bug. Die Lösung ist `load_config()` zu erweitern, sodass nach dem Laden von `options.json` der Log-Level dynamisch per `logging.getLogger().setLevel(...)` gesetzt wird — `logging.basicConfig()` kann nicht nach Modulinitialisierung erneut aufgerufen werden. Für ALT-01 (persistent_notification) braucht das Addon einen aiohttp-POST-Call an `http://supervisor/core/api/services/persistent_notification/create` mit dem `SUPERVISOR_TOKEN` aus der Umgebung. Der SUPERVISOR_TOKEN ist bereits in `HomeAssistantWebsocket.__init__` verfügbar.

**Dolibarr-Seite (LOG-03, ALT-02):** `dol_syslog()` ist bereits im Modul etabliert (billing.class.php, admin.php). Upload-Events in `api_wallboxbilling.class.php` loggen bisher nicht mit `dol_syslog()` — das ist der LOG-03-Gap. Für ALT-02 (Admin-E-Mail) ist `CMailFile` + `sendfile()` der Dolibarr-Standard. Die Admin-E-Mail-Adresse ist konfigurierbar per neuer Dolibarr-Konstante `WALLBOXBILLING_ADMIN_EMAIL` (via `admin.php` Konfig-Tab) oder als Fallback aus `getDolGlobalString('MAIN_INFO_SOCIETE_MAIL')`.

**Log-Scrubbing (LOG-02):** Das bestehende Logging ist überwiegend datenschutzkonform. RFID erscheint nur als Hash ([:16] Prefix). Einzig kritischer Punkt: `api_client.py` ConnectionError-Exception-Strings könnten theoretisch URL-Fragmente enthalten, die den Token exponieren, wenn der Token in die URL eingebettet wird — tut er in der aktuellen Implementierung nicht (Token geht als HTTP-Header `DOLAPIKEY`). LOG-02 ist damit fast kostenlos — nur eine Auditzeile für Dokumentation + Test.

**Primary recommendation:** LOG-01 via options.json→logging.getLogger().setLevel(); ALT-01 via SUPERVISOR_TOKEN + aiohttp POST; LOG-03 via dol_syslog() in postSession(); ALT-02 via CMailFile mit konfigurierbarer WALLBOXBILLING_ADMIN_EMAIL Konstante.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ALT-01 | HA sendet persistent_notification wenn Session-Upload fehlschlägt | HA Supervisor REST API: POST http://supervisor/core/api/services/persistent_notification/create mit SUPERVISOR_TOKEN Bearer — bereits in main.py nutzbar |
| ALT-02 | Dolibarr sendet E-Mail an Admin bei Upload-Fehler | CMailFile-Klasse in Dolibarr-Core, neue Konstante WALLBOXBILLING_ADMIN_EMAIL, Aufruf in api_wallboxbilling.class.php bei upload_status='error' |
| LOG-01 | Log-Level per config.yaml konfigurierbar (debug/info/warning) ohne Code-Änderung | options.json enthält log_level — main.py liest es NICHT (Bug); Fix: nach load_config() logging.getLogger().setLevel() aufrufen |
| LOG-02 | Logs enthalten keine RFID-Klartexte, API-Tokens, personenbezogenen Daten | Audit ergibt: RFID immer gehasht [:16]; Token nie geloggt; ConnectionError-Strings sicher (Token als HTTP-Header, nicht in URL) |
| LOG-03 | Dolibarr-Modul loggt Upload-Ereignisse strukturiert ins Dolibarr-Logfile | dol_syslog() bereits in billing.class.php + admin.php; api_wallboxbilling.class.php loggt noch nicht — Gap zu schließen |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| HA persistent_notification (ALT-01) | HA Addon (Python) | HA Core via Supervisor REST | Addon erkennt den Fehler und ruft HA Core API auf |
| Admin-E-Mail (ALT-02) | Dolibarr API-Endpoint | Dolibarr CMailFile-Core | Upload-Fehler entstehen im Dolibarr-Endpunkt beim INSERT |
| Log-Level-Konfiguration (LOG-01) | HA Addon main.py | config.yaml / options.json | Lese-Seite: options.json; Anwende-Seite: Python logging-Framework |
| Log-Scrubbing (LOG-02) | HA Addon (Python) | — | RFID- und Token-Handling liegt vollständig in Python-Code |
| Dolibarr strukturiertes Logging (LOG-03) | Dolibarr api_wallboxbilling.class.php | dol_syslog() Core | Upload-Ereignisse entstehen in postSession() |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| aiohttp | 3.14.1 [VERIFIED: python env] | HTTP-Client für Supervisor API (ALT-01) | Bereits im Addon für /health Server genutzt |
| Python logging | stdlib | Strukturiertes Logging (LOG-01, LOG-02) | Bereits im Addon, kein zusätzliches Paket |
| dol_syslog() | Dolibarr Core | Dolibarr-Logging (LOG-03) | Standard in Dolibarr-Modulen, bereits in billing.class.php verwendet |
| CMailFile | Dolibarr Core | E-Mail-Versand (ALT-02) | Offizieller Dolibarr-Weg für Modul-E-Mails |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| requests | 2.31.0 [VERIFIED] | Bereits für API-Client | Nicht für ALT-01 (aiohttp bevorzugt wg. async-Kontext) |
| pytest | 7.4.4 [VERIFIED] | Tests | Bestehende Test-Infrastruktur |
| pytest-asyncio | — | Async-Tests für ALT-01 | Wenn persistent_notification-Funktion async ist |

**Installation:** Keine neuen Pakete nötig — aiohttp, pytest, requests bereits vorhanden.

---

## Architecture Patterns

### System Architecture Diagram

```
HA Addon (periodic_transmission)
    |
    v
session_manager.transmit_completed_sessions()
    |-- success --> upload_status='ok' in SQLite
    |-- failure --> upload_status='error' in SQLite
                        |
                        +--> [ALT-01] send_persistent_notification(error_msg)
                                       |
                                       v
                              POST http://supervisor/core/api/
                              services/persistent_notification/create
                              {Authorization: Bearer $SUPERVISOR_TOKEN}
                                       |
                                       v
                              HA Core persistent_notification UI

Dolibarr api_wallboxbilling.class.php postSession()
    |-- INSERT success --> upload_status='ok'
    |                      dol_syslog("OK", LOG_INFO)  [LOG-03]
    |-- INSERT failure --> upload_status='error'
                           dol_syslog("ERROR", LOG_ERR)  [LOG-03]
                               |
                               +--> [ALT-02] send_admin_email(error_detail)
                                             |
                                             v
                                    CMailFile($subject, $admin_email, ...)
                                    ->sendfile()

main.py startup sequence:
    load_config()  ->  options.json['log_level']
         |
         v
    logging.getLogger().setLevel(log_level)  [LOG-01 fix]
```

### Recommended Project Structure

Keine neuen Verzeichnisse nötig. Änderungen an bestehenden Dateien:

```
Homeassistant/
├── main.py              # LOG-01: load_config -> setLevel; ALT-01: notify_ha_persistent()
├── session_manager.py   # unverändert für Phase 7
├── api_client.py        # unverändert für Phase 7
└── tests/
    ├── conftest.py      # ggf. mock SUPERVISOR_TOKEN fixture
    └── test_alerts_logging.py  # neu: Tests für LOG-01, LOG-02, ALT-01

Dolibarr/htdocs/custom/wallboxbilling/
└── class/
    └── api_wallboxbilling.class.php  # LOG-03 + ALT-02: dol_syslog + CMailFile
```

### Pattern 1: HA persistent_notification via Supervisor REST API

**What:** Addon ruft HA Core Service über http://supervisor/core/api/... auf — kein direkter Websocket-Call nötig.
**When to use:** Immer wenn ein Session-Upload fehlschlägt (result["failed"] > 0 in periodic_transmission).

```python
# Source: developers.home-assistant.io/docs/api/supervisor/endpoints/ + community verfied pattern
async def send_persistent_notification(title: str, message: str, notification_id: str = "wallbox_upload_error") -> None:
    """Sendet persistent_notification via HA Supervisor REST API (ALT-01)."""
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
        "message": message,
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
```

**Integration in periodic_transmission (main.py):**
```python
if result["failed"] > 0:
    _LOGGER.error("Fehler bei API-Übertragung: %s Sessions fehlgeschlagen", result["failed"])
    error_summary = "; ".join(result.get("errors", []))
    await send_persistent_notification(
        title="Wallbox Upload-Fehler",
        message=f"{result['failed']} Session(s) konnten nicht übertragen werden: {error_summary}",
        notification_id="wallbox_upload_error",
    )
```

### Pattern 2: LOG-01 — Log-Level aus options.json anwenden

**What:** `load_config()` gibt Config-Dict zurück; `main()` extrahiert `log_level` und setzt Python-Logger neu.
**When to use:** Direkt nach `load_config()` in `main()` aufrufen, BEVOR irgendwelche weiteren Logs erscheinen.

```python
# Source: Python logging stdlib docs [ASSUMED für setLevel-Methode — stdlib, stabil]
def apply_log_level_from_config(config: dict) -> None:
    """Setzt Log-Level aus options.json (LOG-01)."""
    log_level_str = config.get('log_level', 'INFO').upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    _LOGGER.info("Log-Level gesetzt auf: %s", log_level_str)
```

**Wichtig:** `logging.basicConfig()` hat keine Wirkung wenn es nach dem ersten Logger-Call erneut aufgerufen wird (Python-stdlib-Verhalten). Daher muss `logging.getLogger().setLevel()` auf dem Root-Logger verwendet werden.

### Pattern 3: LOG-03 — dol_syslog in postSession()

**What:** Nach INSERT-Erfolg LOG_INFO, nach INSERT-Fehler LOG_ERR. Bereits etabliertes Pattern im Modul.
**When to use:** In `api_wallboxbilling.class.php::postSession()` nach jedem DB-Schreibvorgang.

```php
// Source: Dolibarr dol_syslog — verified in billing.class.php + wiki.dolibarr.org
// Nach erfolgreichem INSERT:
dol_syslog("WallboxBilling: Session upload OK - session_id=".$new_id." wallbox=".$wallbox_id." kwh=".$kwh, LOG_INFO);

// Bei INSERT-Fehler:
dol_syslog("WallboxBilling: Session upload FAILED - ".$this->db->lasterror(), LOG_ERR);
```

### Pattern 4: ALT-02 — Admin-E-Mail via CMailFile

**What:** Bei Upload-Fehler in `postSession()` eine E-Mail an konfigurierten Admin senden.
**When to use:** Nur bei INSERT-Fehler (nicht bei Validierungsfehlern). Admin-Adresse aus neuer Konstante `WALLBOXBILLING_ADMIN_EMAIL`.

```php
// Source: Dolibarr CMailFile constructor — [CITED: doxygen.dolibarr.org/dolibarr_dev/]
// Requires: require_once DOL_DOCUMENT_ROOT.'/core/class/CMailFile.class.php';

$admin_email = getDolGlobalString('WALLBOXBILLING_ADMIN_EMAIL');
if (!empty($admin_email)) {
    $from = getDolGlobalString('MAIN_MAIL_EMAIL_FROM', getDolGlobalString('MAIN_INFO_SOCIETE_MAIL'));
    $subject = "Wallbox Upload-Fehler: Session konnte nicht gespeichert werden";
    $message = "Session-Upload fehlgeschlagen.\n\nFehler: ".$this->db->lasterror()."\n\nZeitpunkt: ".dol_print_date(dol_now(), 'dayhour');
    $mail = new CMailFile($subject, $admin_email, $from, $message, array(), array(), array(), '', '', 0, 0);
    if (!$mail->sendfile()) {
        dol_syslog("WallboxBilling: Admin-E-Mail konnte nicht gesendet werden: ".$mail->error, LOG_WARNING);
    }
}
```

**Admin-E-Mail konfigurierbar machen:** Im Config-Tab von `admin.php` ein neues Feld `WALLBOXBILLING_ADMIN_EMAIL` hinzufügen (analog zu `WALLBOXBILLING_DEFAULT_PRICE`):

```php
// In admin.php action=update:
$admin_email = GETPOST('WALLBOXBILLING_ADMIN_EMAIL', 'email');
dolibarr_set_const($db, 'WALLBOXBILLING_ADMIN_EMAIL', $admin_email, 'chaine', 0, '', $conf->entity);

// Im Config-Tab HTML:
<tr><td>Admin-E-Mail für Alerts</td>
    <td><input type="email" name="WALLBOXBILLING_ADMIN_EMAIL"
               value="'.getDolGlobalString('WALLBOXBILLING_ADMIN_EMAIL').'" /></td></tr>
```

### Anti-Patterns to Avoid

- **logging.basicConfig() nach Init erneut aufrufen:** Hat keine Wirkung wenn bereits Handler registriert — stattdessen `logging.getLogger().setLevel()` verwenden.
- **notification_id weglassen:** Ohne `notification_id` entstehen bei jedem Fehler neue Notifications — mit fixer ID wird immer dieselbe überschrieben (sinnvoller für Alerts).
- **E-Mail bei jedem API-Call senden:** Nur bei tatsächlichem Datenbankfehler, nicht bei HTTP-Validierungsfehlern (400). Sonst Spam-Risiko.
- **Fehlertext ungefiltert in persistent_notification:** `result["errors"]` aus `transmit_completed_sessions` kann technische Fehlermeldungen enthalten — auf sinnvolle Länge kürzen (max 500 Zeichen).
- **aiohttp.ClientSession pro Notification öffnen:** Akzeptabel für seltene Alert-Calls, aber kein Pool-Sharing mit der Websocket-Session.
- **rfid_hex (Klartext) in Log-Nachrichten:** Bereits korrekt vermieden — nicht regressieren.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP-Client für Supervisor API | eigener urllib3-Code | aiohttp (bereits vorhanden) | Asyncio-kompatibel, kein Blocking |
| E-Mail-Versand in Dolibarr | PHP mail() direkt | CMailFile | CMailFile respektiert Dolibarr SMTP-Konfig, Fallback-Handler, TLS |
| Log-Level-Parsing | eigenes string-to-int mapping | `getattr(logging, level_str, logging.INFO)` | stdlib-Standard, sicher gegen ungültige Werte |
| Dolibarr-Log-Channel | custom file_put_contents() | dol_syslog() | Respektiert Syslog-Modul-Konfig, zentrales Dolibarr-Log |

**Key insight:** In beiden Subsystemen gibt es etablierte Logging/Alerting-Infrastruktur — die Phase ergänzt nur die fehlenden Aufrufe an den richtigen Stellen.

---

## Common Pitfalls

### Pitfall 1: LOG-01 — logging.basicConfig() nach Init hat keine Wirkung

**What goes wrong:** `logging.basicConfig()` wird erneut mit neuem Log-Level aufgerufen (z.B. nach `load_config()`), aber die Konfiguration wird ignoriert weil bereits Handler registriert sind.
**Why it happens:** Python-stdlib: `basicConfig()` ist ein No-op wenn Root-Logger bereits Handler hat.
**How to avoid:** `logging.getLogger().setLevel(level)` direkt auf dem Root-Logger aufrufen — das funktioniert immer.
**Warning signs:** Log-Ausgaben erscheinen trotz `log_level: DEBUG` nur auf INFO-Level.

### Pitfall 2: LOG-01 — options.json vs ENV-Variable Reihenfolge

**What goes wrong:** `load_config()` wird NACH `logging.basicConfig(level=os.getenv('LOG_LEVEL'))` aufgerufen, aber der Root-Logger ignoriert das Config-Level.
**Why it happens:** In `main.py` ist `logging.basicConfig()` ein Modul-Level-Statement (Zeile 30) — wird beim Import ausgeführt, nicht bei `main()`.
**How to avoid:** `apply_log_level_from_config()` in `main()` nach `load_config()` aufrufen; der Root-Logger-Level wird dann überschrieben.
**Warning signs:** Test mit `log_level: DEBUG` in options.json zeigt keine DEBUG-Ausgaben.

### Pitfall 3: ALT-01 — SUPERVISOR_TOKEN nicht verfügbar in Tests

**What goes wrong:** Test schlägt fehl weil `SUPERVISOR_TOKEN` nicht gesetzt ist.
**Why it happens:** SUPERVISOR_TOKEN ist nur im laufenden HA-Addon-Container verfügbar.
**How to avoid:** `send_persistent_notification` mockbar machen; in Tests `SUPERVISOR_TOKEN` über `monkeypatch.setenv` setzen; Funktion prüft bereits auf leeren Token und skipped gracefully.
**Warning signs:** `pytest` schlägt mit `ConnectionRefusedError` fehl beim Test von ALT-01.

### Pitfall 4: ALT-02 — CMailFile ohne require_once

**What goes wrong:** `new CMailFile(...)` wirft `Fatal error: Class 'CMailFile' not found`.
**Why it happens:** Dolibarr lädt Core-Klassen nicht automatisch in Custom-Modul-Kontext.
**How to avoid:** `require_once DOL_DOCUMENT_ROOT.'/core/class/CMailFile.class.php';` am Anfang der Methode oder Datei.
**Warning signs:** Fatal error in Dolibarr-Log bei erstem Upload-Fehler.

### Pitfall 5: ALT-02 — E-Mail-Versand blockiert API-Response

**What goes wrong:** `CMailFile::sendfile()` hängt wegen SMTP-Timeout und blockiert die API-Response für das HA-Addon.
**Why it happens:** PHP ist synchron; SMTP-Timeout kann 30+ Sekunden dauern.
**How to avoid:** E-Mail nur bei konfigurierter Adresse senden; kurzen SMTP-Timeout sicherstellen (Dolibarr `MAIN_MAIL_SMTP_PORT`-Konfig). Alternativ: E-Mail-Versand nach dem API-Response via Buffer — aber das ist PHP-seitig aufwendig. Pragmatische Lösung: Guard mit `!empty($admin_email)` und Fehler nur in `dol_syslog` protokollieren wenn CMailFile fehlschlägt.
**Warning signs:** HA-Addon-Timeout bei API-Calls wenn Dolibarr-SMTP fehlkonfiguriert.

### Pitfall 6: LOG-03 — postSession() loggt bei Validierungsfehlern mit falscher Severity

**What goes wrong:** `dol_syslog()` mit `LOG_ERR` bei 400-Validierungsfehlern (ungültiger rfid_hash-Format) — das wäre fehlleitend.
**Why it happens:** Alle Fehler pauschal als LOG_ERR geloggt.
**How to avoid:** 400-Fehler (Client-seitig, falsche Inputs) als `LOG_WARNING`; 500-Fehler (DB-Fehler) als `LOG_ERR`.

---

## Code Examples

### LOG-01: apply_log_level_from_config in main.py

```python
# In main() nach current_config = load_config():
log_level_str = current_config.get('log_level', 'INFO').upper()
numeric_level = getattr(logging, log_level_str, logging.INFO)
logging.getLogger().setLevel(numeric_level)
_LOGGER.info("Log-Level aus options.json: %s", log_level_str)
```

### LOG-02: Audit-Checkliste bestehender Log-Aufrufe (alle Dateien)

Aus Codebase-Analyse [VERIFIED: grep auf *.py]:

| Datei | Log-Aufruf | Sensibel? | Status |
|-------|-----------|-----------|--------|
| main.py:191 | `rfid_hash[:16]` | OK — nur Prefix | Compliant |
| main.py:201 | `session_id` | OK — Integer | Compliant |
| main.py:70-71 | API-Token-Warnung (kein Token in Msg) | OK | Compliant |
| session_manager.py:143 | `rfid_hash[:16]` | OK — Prefix | Compliant |
| session_manager.py:169-172 | `rfid_hash[:16]` | OK | Compliant |
| session_manager.py:335-336 | `rfid_hash[:16]` | OK | Compliant |
| api_client.py:108-109 | `rfid_hash[:16]` | OK | Compliant |
| api_client.py:84 | `self.base_url` (kein Token) | OK | Compliant |
| api_client.py:131 | `ConnectionError as e` | PRÜFEN — `e` könnte URL enthalten | Verify in Test |

**Ergebnis:** Keine RFID-Klartexte, keine API-Token-Leaks gefunden. api_client.py ConnectionError-`e` enthält in requests-Library üblicherweise keine Auth-Header, nur die URL ohne Query-Parameter — der Token geht als HTTP-Header `DOLAPIKEY`, nicht in der URL.

### ALT-01: Test-Stub für persistent_notification

```python
# In tests/test_alerts_logging.py
import pytest
import os

@pytest.mark.asyncio
async def test_send_persistent_notification_no_token(monkeypatch):
    """Wenn SUPERVISOR_TOKEN fehlt, soll Funktion ohne Exception returnieren."""
    monkeypatch.delenv('SUPERVISOR_TOKEN', raising=False)
    from main import send_persistent_notification
    # Kein raise erwartet
    await send_persistent_notification("Test", "Test-Msg")

@pytest.mark.asyncio
async def test_send_persistent_notification_with_mock(monkeypatch, aiohttp_client):
    """Erfolgreicher POST an Supervisor-Mock."""
    monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-token')
    # aiohttp TestServer mock oder unittest.mock.patch auf aiohttp.ClientSession
    ...
```

---

## LOG-01 Gap: Aktuelle Code-Situation

**Problem:** `main.py` Zeile 29 liest `os.getenv('LOG_LEVEL', 'INFO')` — das ist ein Fallback auf eine Umgebungsvariable die HA Supervisor NOT automatically injects von `options.json`. [VERIFIED: HA Addon Developer Docs — options.json wird nicht automatisch als Env-Var injiziert; muss manuell gelesen werden.]

**Aktueller Zustand:**
- `config.yaml` hat `log_level: "INFO"` als default und `schema: log_level: "list(DEBUG|INFO|WARNING|ERROR)"` [VERIFIED: config.yaml]
- `load_config()` liest `options.json` aber extrahiert `log_level` nicht [VERIFIED: main.py]
- Root-Logger wird auf `os.getenv('LOG_LEVEL', 'INFO')` gesetzt — bleibt immer INFO außer wenn manuell Env-Var gesetzt

**Fix (minimal):**
```python
# In main() nach current_config = load_config()
_log_level = current_config.get('log_level', 'INFO').upper()
logging.getLogger().setLevel(getattr(logging, _log_level, logging.INFO))
```

**Hinweis:** `logging.basicConfig()` kann nicht erneut aufgerufen werden (kein Effekt wenn Handler existieren). Die Lösung über `getLogger().setLevel()` wirkt auf alle Logger im Addon.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| HA Addon Supervisor API via urllib | aiohttp async POST zu http://supervisor/ | Supervisor-Ära (HAOS) | Non-blocking, kein requests-Import nötig |
| PHP mail() direkt | CMailFile (SMTP-aware) | Dolibarr 3.x+ | Respektiert Dolibarr SMTP-Konfig |
| Dolibarr error_log() | dol_syslog() | Dolibarr Custom Module Docu | Zentrales Log, konfigurierbar per Syslog-Modul |

**Deprecated/outdated:**
- `php mail()` direkt: In Dolibarr-Modulen nie verwenden — CMailFile respektiert SMTP-Konfiguration, TLS, Fallback.
- `logging.basicConfig()` nach Init: kein Effekt — immer `getLogger().setLevel()` für nachträgliche Änderungen.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | HA Supervisor injiziert options.json-Felder NICHT automatisch als Env-Vars | LOG-01 Gap | Wenn doch automatisch: LOG-01 wäre bereits teilweise gelöst — aber aktueller Code liest trotzdem nicht das richtige Feld |
| A2 | `http://supervisor/core/api/services/persistent_notification/create` ist der korrekte Endpoint | ALT-01 Pattern | Endpoint-Pfad könnte sich geändert haben — Fallback: Websocket-Call |
| A3 | CMailFile-Konstruktor-Signatur stabil in Dolibarr 21.x–22.x | ALT-02 Pattern | Signatur könnte sich geändert haben — low risk, sehr stabile Klasse |
| A4 | `MAIN_INFO_SOCIETE_MAIL` ist der richtige Fallback für die Absender-Adresse | ALT-02 Pattern | Könnte leer sein — dann E-Mail-Versand schlägt fehl, `sendfile()` gibt false zurück |
| A5 | `requests.exceptions.ConnectionError` str() enthält keine Auth-Header | LOG-02 Audit | Wenn doch: Token könnte in Error-Logs erscheinen — aber Token geht als Header, nicht URL |

---

## Open Questions (RESOLVED)

1. **ALT-01: notification_id — pro Session oder global?**
   - What we know: `notification_id="wallbox_upload_error"` überschreibt immer dieselbe Notification
   - What's unclear: Soll jeder Fehler eine neue Notification erzeugen oder die vorherige überschreiben?
   - Recommendation: Feste ID (`wallbox_upload_error`) — sauberer für Admin-View, vermeidet Notification-Flut

2. **ALT-02: E-Mail bei JEDEM Fehler oder nur beim ersten in einer Session?**
   - What we know: `postSession()` wird pro Übertragungsversuch aufgerufen
   - What's unclear: Kann dasselbe Fehlerprotokoll mehrfach getriggert werden (Retry)?
   - Recommendation: E-Mail immer senden wenn `$admin_email` gesetzt — Dolibarr-Admin entscheidet über Frequency

3. **ALT-02: Dolibarr SMTP-Konfiguration muss vorhanden sein**
   - What we know: CMailFile nutzt Dolibarr-SMTP-Einstellungen
   - What's unclear: Wenn SMTP nicht konfiguriert ist, schlägt sendfile() still fehl
   - Recommendation: dol_syslog(LOG_WARNING) wenn sendfile() false zurückgibt

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.x | HA Addon | ✓ | 3.12.3 | — |
| aiohttp | ALT-01 | ✓ | 3.14.1 | — |
| pytest | Tests | ✓ | 7.4.4 | — |
| requests | api_client | ✓ | 2.31.0 | — |
| PHP / Dolibarr | ALT-02, LOG-03 | Deployment-seitig (Dolibarr-Server) | 21.x–22.x [ASSUMED] | — |
| SUPERVISOR_TOKEN | ALT-01 Runtime | Nur im laufenden Addon-Container | automatisch gesetzt | graceful skip (bereits implementiert) |

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 + pytest-asyncio |
| Config file | none — Homeassistant/ Verzeichnis |
| Quick run command | `cd /home/roto/Homeassistant && python3 -m pytest tests/ -x -q` |
| Full suite command | `cd /home/roto/Homeassistant && python3 -m pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LOG-01 | options.json log_level wird angewendet (Root-Logger-Level ändert sich) | unit | `pytest tests/test_alerts_logging.py::test_log_level_from_config -x` | ❌ Wave 0 |
| LOG-02 | Kein rfid_hex in Logs; kein api_token in Logs | unit (caplog) | `pytest tests/test_alerts_logging.py::test_no_sensitive_data_in_logs -x` | ❌ Wave 0 |
| ALT-01 | send_persistent_notification wird bei Upload-Fehler aufgerufen | unit (mock) | `pytest tests/test_alerts_logging.py::test_persistent_notification_on_failure -x` | ❌ Wave 0 |
| ALT-01 | Kein Crash wenn SUPERVISOR_TOKEN fehlt | unit | `pytest tests/test_alerts_logging.py::test_persistent_notification_no_token -x` | ❌ Wave 0 |
| LOG-03 | (PHP) dol_syslog bei postSession Erfolg/Fehler | manual review | grep-based acceptance criterion | ❌ Wave 0 |
| ALT-02 | (PHP) CMailFile-Aufruf bei DB-Fehler in postSession | manual review | grep-based acceptance criterion | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd /home/roto/Homeassistant && python3 -m pytest tests/ -x -q`
- **Per wave merge:** `cd /home/roto/Homeassistant && python3 -m pytest tests/ -v`
- **Phase gate:** Full suite green vor `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `Homeassistant/tests/test_alerts_logging.py` — covers LOG-01, LOG-02, ALT-01
- [ ] pytest-asyncio install prüfen: `python3 -c "import pytest_asyncio" 2>/dev/null || pip install pytest-asyncio`
- [ ] PHP-Tests (LOG-03, ALT-02): grep-basierte Acceptance Criteria (kein PHP-Test-Framework im Projekt)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | nein | — |
| V3 Session Management | nein | — |
| V4 Access Control | nein | — |
| V5 Input Validation | ja | error_msg auf max Länge kürzen vor Notification; htmlspecialchars in PHP bereits vorhanden |
| V6 Cryptography | nein | — |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Notification-Flut (DoS durch viele Upload-Fehler) | Denial of Service | feste notification_id überschreibt alte; E-Mail nur bei konfiguriertem Admin |
| Error-Message-Injection (langer Fehlertext in Notification) | Tampering | error_summary auf max 500 Zeichen kürzen |
| RFID-Klartext in Logs (LOG-02) | Information Disclosure | rfid_hash[:16] Prefix-Pattern beibehalten; nie rfid_hex direkt loggen |
| API-Token in Logs (LOG-02) | Information Disclosure | Token geht als HTTP-Header, nie in URL — kein aktives Risiko gefunden |
| SMTP-Timeout blockiert API (ALT-02) | Availability | dol_syslog bei sendfile()-Fehler; kein Re-throw |

---

## Sources

### Primary (HIGH confidence)
- Codebase: `/home/roto/Homeassistant/main.py` — logging setup, load_config, periodic_transmission [VERIFIED]
- Codebase: `/home/roto/Homeassistant/session_manager.py` — transmit_completed_sessions, logging [VERIFIED]
- Codebase: `/home/roto/Homeassistant/api_client.py` — DOLAPIKEY header, logging patterns [VERIFIED]
- Codebase: `/home/roto/Homeassistant/config.yaml` — log_level schema definition [VERIFIED]
- Codebase: `/home/roto/Dolibarr/htdocs/custom/wallboxbilling/class/billing.class.php` — dol_syslog usage [VERIFIED]
- Codebase: `/home/roto/Dolibarr/htdocs/custom/wallboxbilling/admin.php` — dolibarr_set_const, GETPOST patterns [VERIFIED]

### Secondary (MEDIUM confidence)
- [HA Supervisor Endpoints](https://developers.home-assistant.io/docs/api/supervisor/endpoints/) — /core/api proxy endpoint [CITED]
- [HA persistent_notification docs](https://www.home-assistant.io/integrations/persistent_notification/) — Service fields: message, title, notification_id [CITED]
- [Dolibarr CMailFile Class Reference](https://doxygen.dolibarr.org/dolibarr_dev/build/html/dd/df7/class_c_mail_file.html) — Constructor signature, sendfile() [CITED]
- [Dolibarr Syslog Module Developer Docs](https://wiki.dolibarr.org/index.php/Module_Syslog_(developer)) — dol_syslog(), LOG_INFO/LOG_ERR, log file path [CITED]

### Tertiary (LOW confidence)
- Community pattern for `http://supervisor/core/api/services/...` endpoint from HA Community Forum — verified against official endpoint docs

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — alle Libraries bereits im Projekt vorhanden und versionsverifiziert
- Architecture: HIGH — beide Subsysteme aus Codebase vollständig verstanden
- HA persistent_notification Endpoint: MEDIUM — offiziell dokumentiert, genaue URL [ASSUMED] aus Community-Pattern
- Dolibarr CMailFile: MEDIUM — Klasse stabil, Signatur aus Doxygen verifiziert, Dolibarr-Version in Produktion unbekannt
- Log-Scrubbing (LOG-02): HIGH — vollständiger Codebase-Grep, kein Leck gefunden
- Pitfalls: HIGH — direkt aus Code-Analyse und Python-stdlib Verhalten

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (stabile Technologien; HA Supervisor API könnte sich ändern)
