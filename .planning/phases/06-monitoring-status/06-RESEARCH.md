# Phase 6: Monitoring & Status - Research

**Researched:** 2026-06-21
**Domain:** Dolibarr PHP admin tab UI + MySQL schema migration + Python/aiohttp HTTP endpoint
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Tab-System in `admin.php` — drei Tabs: "Konfiguration" | "RFID" | "Status". Bestehende Formulare bleiben als eigene Tabs erhalten.
- **D-02:** "Status" ist der Standard-Tab beim Öffnen von admin.php (nicht Konfiguration).
- **D-03:** Aktiver cURL-Ping beim Laden des Status-Tabs an den HA-Addon-API-Endpunkt.
- **D-04:** Der `/health`-Endpunkt im HA-Addon existiert noch nicht — muss in dieser Phase neu erstellt werden (in `main.py` oder separatem HTTP-Handler).
- **D-05:** Anzeige: checkmark Erreichbar / cross Nicht erreichbar / warning Fehler: [HTTP-Code].
- **D-06:** Anzeige der letzten 25 übertragenen Sessions — keine Pagination, keine konfigurierbare Anzahl.
- **D-07:** Spalten: Datum | Wallbox-ID | kWh | Nutzer (Name) | Status.
- **D-08:** Nutzer-Anzeige: Klarname aus Dolibarr-User-Tabelle (kein RFID-Hash in der UI).
- **D-09:** Neue Spalten in `llx_wallbox_sessions`: `upload_status` (ENUM: pending/ok/error), `upload_error` (TEXT, NULL wenn ok), `uploaded_at` (DATETIME).
- **D-10:** Status-Werte: `pending` (noch nicht übertragen), `ok` (erfolgreich), `error` (fehlgeschlagen).
- **D-11:** Dolibarr schreibt `upload_status` und `upload_error` beim API-Upload-Versuch.

### Claude's Discretion
- Timeout-Wert für den cURL-Ping (empfohlen: 3-5s)
- Genaue Tab-Implementierung (Dolibarr `dol_get_fiche_head` Pattern)
- Spalten-Reihenfolge und CSS-Klassen in der Session-Tabelle

### Deferred Ideas (OUT OF SCOPE)
- Alerts/E-Mail (Phase 7)
- Retry-Logik (Phase 8)
- Session-Logik Fix bei Überschussladen (separate Phase/Hotfix)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| MON-01 | Nutzer sieht im Dolibarr-Admin-Tab den aktuellen Systemstatus (API erreichbar / nicht erreichbar) | D-03+D-04: cURL-Ping von admin.php Status-Tab zu /health im HA-Addon |
| MON-02 | Nutzer sieht im Admin-Tab die letzten N übertragenen Sessions (Datum, Wallbox-ID, Status) | D-06+D-07+D-09: SELECT letzte 25 aus llx_wallbox_sessions mit upload_status |
| MON-03 | Nutzer sieht im Admin-Tab fehlgeschlagene Übertragungen mit Fehlermeldung | D-09+D-10: upload_error TEXT-Spalte + spezifische Fehlermeldung in upload_error |
</phase_requirements>

---

## Summary

Phase 6 erweitert den bestehenden Dolibarr-Admin-Tab um ein Tab-System (drei Tabs: Konfiguration, RFID, Status) und baut den Status-Tab als erste Ansicht. Der Status-Tab zeigt drei Informationen: API-Erreichbarkeit via cURL-Ping, Tabelle der letzten 25 Sessions, und Upload-Fehler mit Klartext-Fehlermeldung.

Die Implementierung teilt sich in drei klar abgegrenzte Teilgebiete: (1) Dolibarr PHP: admin.php Tab-Umbau mit `dol_get_fiche_head`, cURL-Ping, Session-Tabelle mit JOIN auf `llx_user`; (2) MySQL: ALTER TABLE `llx_wallbox_sessions` mit drei neuen Spalten (`upload_status`, `upload_error`, `uploaded_at`) plus Upgrade-Routine in `modWallboxbilling.class.php`; (3) HA-Addon: neuer `/health`-GET-Endpunkt in `main.py` mit aiohttp `AppRunner`-Pattern parallel zur bestehenden asyncio-Hauptschleife.

**Primary recommendation:** Implement in sequence: (1) DB-Schema-Migration first (Basis fuer alle anderen), (2) /health-Endpunkt im HA-Addon, (3) admin.php Tab-Umbau mit Status-Tab.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| API-Erreichbarkeits-Check | Backend (PHP) | — | cURL-Ping laeuft server-seitig in admin.php beim Seiten-Load |
| /health-Endpunkt | HA-Addon (Python) | — | HA-Addon ist die Ziel-API; Endpunkt muss dort existieren |
| Session-Historie anzeigen | Backend (PHP) | DB | SQL-JOIN in admin.php, Ausgabe als HTML-Tabelle |
| Upload-Status schreiben | HA-Addon (Python) | DB | api_client.py schreibt Status nach Upload-Versuch zurueck |
| DB-Schema Migration | Database (MySQL) | PHP | ALTER TABLE in modWallboxbilling upgrade() Methode |
| Tab-Navigation | Frontend (Dolibarr UI) | PHP | dol_get_fiche_head rendert Tabs, GETPOST bestimmt aktiven Tab |

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Dolibarr `dol_get_fiche_head` | Built-in (Dolibarr >=3.x) | Tab-System in admin.php | Standard Dolibarr-Funktion fuer Tabs, keine Alternative noetig |
| PHP `curl_*` functions | Built-in | Health-Ping von admin.php | Bereits in Dolibarr-Umgebung verfuegbar; kein zusaetzliches Package |
| aiohttp `web.AppRunner` + `TCPSite` | aiohttp 3.x (bereits in Addon) | HTTP-Server fuer /health | Bereits als Dependency vorhanden (aiohttp fuer HA-Websocket-Verbindung) |
| MySQL `ALTER TABLE` | MySQL 5.7+ | Schema-Migration | Standard-SQL, keine ORM-Abhaengigkeit |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Dolibarr `dol_fiche_end()` / `</div>` | Built-in | Tab-Bereich schliessen | Nach Tab-Inhalt, vor Footer |
| `GETPOST()` | Built-in Dolibarr | Tab-Parameter aus GET/POST | Sicherer Input-Accessor, already used in admin.php |
| `getDolGlobalString()` | Built-in Dolibarr | HA-API-URL fuer cURL lesen | Config-Wert aus Dolibarr-Konstanten |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| PHP curl_* | file_get_contents + stream_context | curl erlaubt bessere Timeout-Kontrolle und Fehler-Differenzierung |
| aiohttp AppRunner | Flask/FastAPI | Unnoetige Dependency; aiohttp bereits vorhanden |
| ALTER TABLE | Neue Tabelle fuer upload_status | ALTER ist einfacher; Status gehoert zur Session |

---

## Architecture Patterns

### System Architecture Diagram

```
Admin oeffnet admin.php
         |
         v
[admin.php PHP] --> GETPOST('tab') --> "status" (Default, D-02)
         |
         |-- Tab-Leiste: dol_get_fiche_head($head, 'status', ...)
         |
         |-- Status-Tab-Inhalt:
         |     |
         |     +-- cURL-Ping --> [HA-Addon :8099/health] --> 200 OK / Fehler
         |     |      |
         |     |      v
         |     |   Erreichbar-Anzeige (D-05)
         |     |
         |     +-- SQL-Query: SELECT letzte 25 aus llx_wallbox_sessions
         |           JOIN llx_user ON rfid_hash = llx_wallbox_rfid.rfid_hash
         |           ORDER BY rowid DESC LIMIT 25
         |           v
         |        HTML-Tabelle: Datum | Wallbox-ID | kWh | Nutzer | Status
         |
         v
[HA-Addon main.py] -- asyncio.gather() -->
         |-- websocket_loop (bestehend, blockiert)
         +-- aiohttp AppRunner auf Port 8099 (neu)
                  |
                  GET /health --> {"status": "ok"} 200

[api_client.py transmit_session()] -- nach Upload:
         --> UPDATE llx_wallbox_sessions SET upload_status='ok'/'error',
             upload_error='...', uploaded_at=NOW()
```

### Recommended Project Structure
```
Dolibarr/htdocs/custom/wallboxbilling/
├── admin.php              # ERWEITERT: Tab-System + Status-Tab
├── core/modules/
│   └── modWallboxbilling.class.php  # ERWEITERT: upgrade() mit ALTER TABLE
└── class/
    └── wallboxbilling.class.php     # Optional: getLastSessions() Methode

Homeassistant/
├── main.py                # ERWEITERT: /health-Endpunkt via AppRunner
└── api_client.py          # ERWEITERT: schreibt upload_status nach transmit_session()
```

### Pattern 1: Dolibarr dol_get_fiche_head Tab-System

**What:** Tab-Navigation in admin.php mittels head-Array und dol_get_fiche_head
**When to use:** Jede Dolibarr-Admin-Seite mit mehreren Unterbereichen

```php
// Source: wiki.dolibarr.org/index.php/Module_development (CITED)
// Tab-Array aufbauen
$head = array();
$h = 0;

$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=config';
$head[$h][1] = $langs->trans('WallboxConfiguration');
$head[$h][2] = 'config';
$h++;

$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=rfid';
$head[$h][1] = $langs->trans('WallboxUserRFIDManagement');
$head[$h][2] = 'rfid';
$h++;

$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=status';
$head[$h][1] = $langs->trans('WallboxStatus');
$head[$h][2] = 'status';
$h++;

// Aktiven Tab aus GET-Parameter lesen (D-02: Default = 'status')
$tab = GETPOST('tab', 'aZ09');
if (empty($tab)) $tab = 'status';  // D-02: Default ist Status-Tab

// Tab-Leiste rendern
print dol_get_fiche_head($head, $tab, $langs->trans('WallboxBillingSetup'), -1, 'title_setup');

// Tab-Inhalt ausgeben (Switch)
if ($tab == 'status') {
    // ... Status-Inhalt ...
} elseif ($tab == 'config') {
    // ... Konfigurationsformular (bestehend) ...
} elseif ($tab == 'rfid') {
    // ... RFID-Tabelle (bestehend) ...
}

// Tab schliessen
print dol_fiche_end();
```

**Key:** Parameter `$head[$h][2]` muss mit dem aktiven Tab-String identisch sein. `dol_fiche_end()` schliesst den Tab-Bereich.

### Pattern 2: cURL Health-Ping in PHP

**What:** Aktiver HTTP-Request von admin.php zum HA-Addon /health Endpunkt
**When to use:** Status-Tab Ladezeit; wird synchron beim Tab-Render ausgefuehrt

```php
// Source: [ASSUMED] - Standard PHP cURL Pattern
function wallbox_ping_health($url, $timeout = 4) {
    $ch = curl_init($url . '/health');
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_TIMEOUT, $timeout);
    curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, $timeout);
    curl_setopt($ch, CURLOPT_NOBODY, false);  // HEAD wuerde fuer /health genuegen
    
    $response = curl_exec($ch);
    $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $curl_error = curl_error($ch);
    curl_close($ch);
    
    if ($curl_error) {
        return array('status' => 'unreachable', 'message' => $curl_error, 'code' => 0);
    }
    if ($http_code == 200) {
        return array('status' => 'ok', 'message' => '', 'code' => 200);
    }
    return array('status' => 'error', 'message' => 'HTTP ' . $http_code, 'code' => $http_code);
}
```

**Timeout-Empfehlung:** 4 Sekunden (Discretion per D-03; Balance zwischen UX und LAN-Realitaet).

### Pattern 3: aiohttp AppRunner neben asyncio-Hauptloop

**What:** HTTP-Server parallel zur bestehenden asyncio-Hauptschleife in main.py
**When to use:** HA-Addon benoetigt HTTP-Endpunkt, hat aber bereits blockierende subscribe_entities-Schleife

```python
# Source: docs.aiohttp.org/en/stable/web_advanced.html (CITED)
from aiohttp import web

async def handle_health(request):
    return web.json_response({"status": "ok", "addon": "wallbox-dolibarr"})

async def start_health_server(port=8099):
    app = web.Application()
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    return runner  # Referenz fuer cleanup() behalten

# In main():
async def main():
    # ... bestehender Code ...
    health_runner = await start_health_server(port=8099)
    
    try:
        await asyncio.gather(
            ha_ws.subscribe_entities(sensor_callback),  # blockiert
            periodic_transmission(),                    # bestehend
        )
    finally:
        await health_runner.cleanup()
        await ha_ws.disconnect()
```

**Key:** AppRunner laeuft im selben Event-Loop; kein separater Thread benoetigt. Port 8099 ist bereits in `config.yaml` mit `ports: 8099/tcp: null` definiert.

### Pattern 4: DB-Schema Migration in modWallboxbilling.class.php

**What:** ALTER TABLE fuer drei neue Spalten; idempotent via SHOW COLUMNS Check
**When to use:** upgrade() Methode fuer bestehende Installationen; init() fuer Neu-Installationen

```php
// Source: Bestehender Code in modWallboxbilling.class.php (VERIFIED: codebase)
// Muster bereits fuer transmitted_at vorhanden - gleich anwenden

// In upgrade():
$cols_to_add = array(
    'upload_status' => "ALTER TABLE llx_wallbox_sessions ADD COLUMN upload_status ENUM('pending','ok','error') NOT NULL DEFAULT 'pending' AFTER transmitted_at",
    'upload_error'  => "ALTER TABLE llx_wallbox_sessions ADD COLUMN upload_error TEXT NULL AFTER upload_status",
    'uploaded_at'   => "ALTER TABLE llx_wallbox_sessions ADD COLUMN uploaded_at DATETIME NULL AFTER upload_error",
);

foreach ($cols_to_add as $col => $alter_sql) {
    $check = "SHOW COLUMNS FROM llx_wallbox_sessions LIKE '" . $col . "'";
    $res = $db->query($check);
    if (!$res || $db->num_rows($res) == 0) {
        $db->query($alter_sql);
    }
}
```

**Key:** ENUM('pending','ok','error') ist direktes Match zu D-09/D-10. Default 'pending' stellt sicher, dass alle bestehenden Sessions korrekt initialisiert sind.

### Pattern 5: Session-Tabelle mit JOIN auf llx_user

**What:** SQL-Query fuer die letzten 25 Sessions mit Nutzernamen (D-07, D-08)
**When to use:** Status-Tab Session-Tabelle in admin.php

```php
// Source: [ASSUMED] - Standard Dolibarr JOIN Pattern (basiert auf bestehendem Code in admin.php)
$sql = "SELECT s.rowid, s.start_time, s.end_time, s.wallbox_id, s.kwh,";
$sql.= " s.upload_status, s.upload_error,";
$sql.= " CONCAT(u.firstname, ' ', u.lastname) as user_name";
$sql.= " FROM ".MAIN_DB_PREFIX."wallbox_sessions as s";
$sql.= " LEFT JOIN ".MAIN_DB_PREFIX."wallbox_rfid as r ON s.rfid_hash = r.rfid_hash";
$sql.= " LEFT JOIN ".MAIN_DB_PREFIX."user as u ON r.fk_user = u.rowid";
$sql.= " WHERE s.status = 'completed'";
$sql.= " ORDER BY s.rowid DESC";
$sql.= " LIMIT 25";
```

**Key:** JOIN-Kette: sessions -> rfid (rfid_hash-Mapping) -> user (Name). Kein RFID-Hash in der UI (SEC-01/02). LEFT JOIN sichert, dass Sessions ohne User-Mapping trotzdem angezeigt werden.

### Pattern 6: upload_status in api_client.py schreiben

**What:** Nach transmit_session()-Aufruf schreibt der SessionManager upload_status via Dolibarr-API oder direkt in DB
**When to use:** Nach jedem API-Upload-Versuch in session_manager.py

**Analyse des bestehenden Codes:**

`session_manager.py::transmit_completed_sessions()` schreibt bereits `transmitted_at` via `UPDATE sessions SET transmitted_at = ?`. Die neuen Spalten `upload_status` und `upload_error` muessen in **derselben Methode** ergaenzt werden.

**Wichtig:** Die SQLite-DB im HA-Addon und die MySQL-DB in Dolibarr sind getrennte Datenbanken. `upload_status` existiert in BEIDEN:
- SQLite (HA-Addon): fuer lokale Fehler-Nachverfolgung (optional, aber konsistent)
- MySQL Dolibarr (`llx_wallbox_sessions`): fuer die UI-Anzeige in admin.php

Das HA-Addon schreibt upload_status in **die Dolibarr-Datenbank** als Teil des API-Upload-Calls (POST-Antwort wird ausgewertet). Dies geschieht via separatem PATCH/PUT oder als Teil der POST-Antwortverarbeitung.

**Realistischer Ansatz fuer Phase 6:** Der einfachste Weg ist, dass `transmit_session()` den Erfolg/Fehler zurueckgibt (bereits implementiert via `Tuple[bool, str]`), und Dolibarr selbst nach Empfang der Session den Status auf 'ok' setzt. Alternativ: HA-Addon sendet Status-Update via PATCH an Dolibarr-API.

**Empfehlung:** Dolibarr API-Handler (`session.php`) setzt `upload_status = 'ok'` beim erfolgreichen Empfang. HA-Addon sendet bei HTTP-Fehler nichts mehr an Dolibarr - der Status bleibt 'pending'. Dolibarr sieht 'pending'-Sessions als "noch nicht uebertragen". Fuer 'error'-Status: separater PATCH-Endpunkt oder HTTP-Body mit Fehlerinfo. Diese Entscheidung muss im Plan geklaert werden.

### Anti-Patterns to Avoid

- **Tab-Redirect statt Tab-Parameter:** Nicht auf separate .php-Dateien pro Tab redirecten; alle Tabs in einer admin.php via GETPOST('tab') — Dolibarr-Standard.
- **Direkte DB-Verbindung aus HA-Addon:** HA-Addon darf NICHT direkt auf MySQL Dolibarr zugreifen — nur via REST API.
- **Blocking HTTP-Call in asyncio ohne await:** `requests.get()` in asyncio blockiert den Event-Loop; fuer den /health-Endpunkt selbst ist aiohttp korrekt. Der cURL-Ping laeuft auf PHP-Seite, nicht in Python.
- **RFID-Hash in der UI:** Niemals `rfid_hash` direkt in admin.php anzeigen (SEC-01, SEC-02) — immer via JOIN auf llx_user den Klarnamen holen.
- **hardcoded HA-URL in PHP:** Die HA-Addon-URL (fuer cURL-Ping) muss aus Dolibarr-Konfiguration gelesen werden (`getDolGlobalString('WALLBOXBILLING_HA_URL')`), nicht hardcoded.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tab-Navigation | Eigenes Tab-CSS/JS | `dol_get_fiche_head` + `dol_fiche_end` | Dolibarr-Standard, Theme-konform, keine Mehrarbeit |
| HTTP-Server in Python | `socket.bind()` manuell | aiohttp AppRunner | Bereits als Dependency da; thread-safe mit asyncio |
| Input-Sanitization in PHP | eigene Escape-Funktion | `GETPOST()`, `$db->escape()` | Dolibarr-Standard; SEC-05 Compliance |
| DB-Migration Guard | Eigene Lock-Tabelle | `SHOW COLUMNS ... LIKE` | Standard in bestehendem modWallboxbilling.class.php |

---

## Common Pitfalls

### Pitfall 1: Tab-Default wird nicht erkannt

**What goes wrong:** Admin oeffnet admin.php ohne ?tab= Parameter; default ist erstes Tab (Konfiguration) statt Status.
**Why it happens:** `dol_get_fiche_head` nutzt den zweiten Parameter fuer den aktiven Tab; ohne expliziten Default zeigt es Tab 0.
**How to avoid:** `if (empty($tab)) $tab = 'status';` direkt nach `GETPOST('tab', ...)`.
**Warning signs:** Status-Tab ist beim Oeffnen nicht aktiv.

### Pitfall 2: dol_fiche_end() wird vergessen

**What goes wrong:** Tab-Inhalte nach dem Status-Tab "leaken" aus dem Tab-Container; Layout kaputt.
**Why it happens:** `dol_get_fiche_head` oeffnet ein `<div>`; ohne `dol_fiche_end()` bleibt es offen.
**How to avoid:** Immer `print dol_fiche_end();` nach dem Tab-Inhalt, vor `llxFooter()`.
**Warning signs:** Dolibarr-Footer-Elemente erscheinen innerhalb des Tab-Bereichs.

### Pitfall 3: cURL-Ping blockiert Seiten-Load bei Timeout

**What goes wrong:** HA-Addon ist nicht erreichbar; cURL wartet Standard-Timeout (30s); Admin-Seite haengt.
**Why it happens:** Kein explizites CURLOPT_TIMEOUT gesetzt.
**How to avoid:** Immer `CURLOPT_TIMEOUT` und `CURLOPT_CONNECTTIMEOUT` auf 4s setzen.
**Warning signs:** admin.php laedt langsam wenn HA-Addon offline.

### Pitfall 4: aiohttp AppRunner blockiert asyncio-Loop

**What goes wrong:** `web.run_app()` (blocking) statt `AppRunner` Pattern verwendet; subscribe_entities laeuft nie.
**Why it happens:** `web.run_app()` blockiert den Event-Loop selbst.
**How to avoid:** Immer `AppRunner + TCPSite` Pattern verwenden (Pattern 3 oben).
**Warning signs:** HA-Addon startet HTTP-Server aber verarbeitet keine HA-Events mehr.

### Pitfall 5: ENUM-Default 'pending' vs. bestehende Rows

**What goes wrong:** Bestehende Sessions in llx_wallbox_sessions haben nach ALTER TABLE NULL statt 'pending' in upload_status.
**Why it happens:** MySQL setzt bei NOT NULL DEFAULT 'pending' den Default fuer neue Rows; bestehende Rows koennen NULL haben wenn die Spalte mit NULL als Default hinzugefuegt wird.
**How to avoid:** `ALTER TABLE ... ADD COLUMN upload_status ENUM('pending','ok','error') NOT NULL DEFAULT 'pending'` — MySQL fuellt bestehende Rows mit dem DEFAULT-Wert, nicht NULL. Direkt korrekt.
**Warning signs:** Tabelle zeigt NULL in upload_status fuer aeltere Sessions.

### Pitfall 6: JOIN schlaegt fehl wenn kein RFID-Mapping existiert

**What goes wrong:** Sessions ohne llx_wallbox_rfid-Eintrag erscheinen nicht in der Tabelle.
**Why it happens:** INNER JOIN statt LEFT JOIN.
**How to avoid:** LEFT JOIN auf llx_wallbox_rfid und llx_user; NULL-Handling fuer user_name (`COALESCE(CONCAT(...), 'Unbekannt')`).

### Pitfall 7: Port 8099 belegt / config.yaml ingress vs. ports

**What goes wrong:** /health-Endpunkt ist nicht von aussen erreichbar weil Port nicht in config.yaml deklariert.
**Why it happens:** config.yaml hat `ports: 8099/tcp: null` — das mappt Port 8099 auf Host. Fuer HA-intern-Calls (Dolibarr auf VPS zu HA-Addon) muss Port konfiguriert sein.
**How to avoid:** Port 8099 ist bereits in config.yaml deklariert. Sicherstellen dass der Dolibarr-VPS Netzwerkzugang zum HA-Host auf Port 8099 hat.
**Warning signs:** cURL-Ping gibt "Connection refused" zurueck.

---

## Code Examples

### Vollstaendiger Status-Tab Render (admin.php)

```php
// Source: Ableitung aus bestehendem admin.php + dol_get_fiche_head Dokumentation [CITED/VERIFIED]
if ($tab == 'status') {

    // --- API Health Check ---
    $ha_url = getDolGlobalString('WALLBOXBILLING_HA_URL', '');
    $health_result = array('status' => 'unconfigured');
    
    if (!empty($ha_url)) {
        $ch = curl_init($ha_url . '/health');
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 4);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 4);
        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = curl_error($ch);
        curl_close($ch);
        
        if ($curl_error) {
            $health_result = array('status' => 'unreachable', 'detail' => $curl_error);
        } elseif ($http_code == 200) {
            $health_result = array('status' => 'ok');
        } else {
            $health_result = array('status' => 'error', 'detail' => 'HTTP '.$http_code);
        }
    }
    
    // Anzeige gemaess D-05
    print '<div class="div-table-responsive">';
    print '<table class="noborder centpercent"><tr class="liste_titre">';
    print '<td>'.$langs->trans('APIStatus').'</td><td>'.$langs->trans('Detail').'</td></tr>';
    print '<tr><td>';
    if ($health_result['status'] == 'ok') {
        print '<span style="color:green">&#x2705; '.$langs->trans('Reachable').'</span>';
    } elseif ($health_result['status'] == 'unreachable') {
        print '<span style="color:red">&#x274C; '.$langs->trans('Unreachable').'</span>';
    } elseif ($health_result['status'] == 'error') {
        print '<span style="color:orange">&#x26A0; '.$langs->trans('Error').': '.$health_result['detail'].'</span>';
    } else {
        print $langs->trans('NotConfigured');
    }
    print '</td><td>'.($health_result['detail'] ?? '').'</td></tr></table></div>';
    
    // --- Session History Table ---
    $sql = "SELECT s.rowid, s.start_time, s.wallbox_id, s.kwh,";
    $sql.= " s.upload_status, s.upload_error,";
    $sql.= " COALESCE(CONCAT(u.firstname, ' ', u.lastname), '".$langs->trans('Unknown')."') as user_name";
    $sql.= " FROM ".MAIN_DB_PREFIX."wallbox_sessions as s";
    $sql.= " LEFT JOIN ".MAIN_DB_PREFIX."wallbox_rfid as r ON s.rfid_hash = r.rfid_hash";
    $sql.= " LEFT JOIN ".MAIN_DB_PREFIX."user as u ON r.fk_user = u.rowid";
    $sql.= " WHERE s.status = 'completed'";
    $sql.= " ORDER BY s.rowid DESC";
    $sql.= " LIMIT 25";
    
    $resql = $db->query($sql);
    // ... HTML table rendering ...
}
```

### aiohttp /health Endpunkt (main.py)

```python
# Source: docs.aiohttp.org/en/stable/web_advanced.html (CITED)
from aiohttp import web

async def handle_health(request):
    """GET /health - Liveness-Check fuer Dolibarr cURL-Ping"""
    return web.json_response(
        {"status": "ok", "addon": "wallbox-dolibarr"},
        status=200
    )

async def start_health_server(port: int = 8099) -> web.AppRunner:
    app = web.Application()
    app.router.add_get('/health', handle_health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    _LOGGER.info("Health-Endpunkt gestartet auf Port %d", port)
    return runner
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Separate PHP-Dateien pro Admin-Bereich | Ein admin.php mit dol_get_fiche_head Tabs | Dolibarr-Standard seit v3 | Einfachere Navigation, Theme-konsistent |
| `web.run_app()` blockierend | AppRunner + asyncio.gather | aiohttp 3.x | Erlaubt parallelen HTTP-Server neben Websocket-Loop |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Dolibarr nutzt MySQL (nicht MariaDB) — ENUM-Syntax identisch | DB-Schema Pattern 4 | ENUM ist in MariaDB und MySQL kompatibel; kein Risiko |
| A2 | cURL ist in der Dolibarr-PHP-Umgebung auf dem VPS aktiviert | cURL Health-Ping | Falls curl nicht aktiviert: file_get_contents als Fallback noetig |
| A3 | JOIN-Kette sessions->rfid->user ist korrekt; rfid_hash in llx_wallbox_rfid ist eindeutig | Pattern 5 SQL | Wenn llx_wallbox_rfid leer ist (keine RFID zugeordnet): LEFT JOIN zeigt 'Unbekannt' — kein Datenverlust |
| A4 | upload_status 'ok'/'error' wird von Dolibarr-API-Handler gesetzt, nicht vom HA-Addon via Rueck-Update | Pattern 6 | Wenn API-Handler Status nicht setzt: alle Sessions bleiben 'pending' — Monitoring broken |
| A5 | Port 8099 auf dem HA-Host ist vom Dolibarr-VPS erreichbar (kein Firewall-Block) | Environment | Falls Firewall-Block: cURL-Ping schlaegt fehl; Konfigurationsproblem ausserhalb des Codes |
| A6 | `dol_fiche_end()` ist die korrekte Schliessfunktion fuer dol_get_fiche_head | Pattern 1 | Alternativ reicht `</div>`; im schlimmsten Fall Layout-Fehler, kein Funktionsfehler |

---

## Open Questions (RESOLVED)

1. **Wo schreibt das HA-Addon upload_status='error'?** *(RESOLVED)*
   - **Resolution:** Dual-Write-Ansatz: `session_manager.py` schreibt `upload_status` in SQLite nach dem Aufruf von `api_client.transmit_session()` (Plan 06-02 Task 2). Dolibarr's `api_wallboxbilling.class.php` setzt `upload_status='ok'`, `upload_error=NULL`, `uploaded_at=NOW()` beim erfolgreichen Empfang des POST-Requests (Plan 06-03 Task 2). Kein separater PATCH-Endpunkt nötig.

2. **Befindet sich WALLBOXBILLING_HA_URL bereits als Dolibarr-Konstante in der DB?** *(RESOLVED)*
   - **Resolution:** Plan 06-03 Task 1 liest die URL via `getDolGlobalString('WALLBOXBILLING_HA_URL')`. Falls nicht gesetzt, zeigt der Status-Tab einen Hinweistext. Die bestehende Konfigurationsstruktur (admin.php "Konfiguration"-Tab) wird in dieser Phase nicht erweitert — das HA-URL-Feld wurde bereits in Phase 1 angelegt.

3. **SQLite im HA-Addon: upload_status auch dort nachfuehren?** *(RESOLVED)*
   - **Resolution:** Ja — Plan 06-02 Task 2 ergänzt `upload_status` und `upload_error` auch in der SQLite `sessions`-Tabelle. Dies bereitet Phase 8 (Retry/Dead-letter) vor, ohne zusätzlichen Aufwand in Phase 6.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | HA-Addon main.py | Yes (local) | 3.12.3 | — |
| aiohttp | HA-Addon /health Endpunkt | [ASSUMED] in Addon | >=3.x | — |
| PHP curl extension | cURL-Ping in admin.php | [ASSUMED] — VPS | — | file_get_contents |
| MySQL | Dolibarr DB-Migration | [ASSUMED] — VPS | — | — |

**Note:** Dolibarr laeuft auf VPS (kein lokaler SSH-Zugang gemaess MEMORY.md). Environment-Checks fuer PHP/MySQL koennen nicht lokal verifiziert werden. Annahmen basieren auf Standard-Dolibarr-Installation.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | PHPUnit (Dolibarr), pytest (Python) |
| Config file | keine in wallboxbilling/ (tests/ vorhanden) |
| Quick run command | `python3 -m pytest Homeassistant/ -x -q` |
| Full suite command | `python3 -m pytest Homeassistant/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MON-01 | /health gibt 200 zurueck | unit (Python) | `pytest Homeassistant/tests/test_health.py -x` | No (Wave 0) |
| MON-01 | cURL-Ping-Funktion gibt 'ok'/'unreachable'/'error' zurueck | manual (PHP VPS) | manual in Dolibarr-UI | N/A |
| MON-02 | SQL-Query gibt max. 25 Sessions zurueck | manual (PHP VPS) | manual in Dolibarr-UI | N/A |
| MON-03 | upload_error wird korrekt in DB geschrieben | unit (Python) | `pytest Homeassistant/tests/test_api_client.py -x` | Partial (exists) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest Homeassistant/ -x -q`
- **Per wave merge:** `python3 -m pytest Homeassistant/ -v`
- **Phase gate:** Voller Test-Suite + manuelle Pruefung in Dolibarr-UI (kein Dolibarr-PHPUnit-Setup vorhanden)

### Wave 0 Gaps
- [ ] `Homeassistant/tests/test_health.py` — testet handle_health() Antwort (MON-01)
- [ ] Dolibarr-seitige Tests sind manuell (kein automatisierbarer PHPUnit-Setup ohne VPS-Zugang)

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Status-Tab ist hinter bestehender Dolibarr-Auth |
| V3 Session Management | no | Dolibarr-Session bereits vorhanden |
| V4 Access Control | yes | `$user->rights->wallboxbilling->admin` Check — bereits in admin.php (SEC-04) |
| V5 Input Validation | yes | GETPOST() fuer tab-Parameter; keine User-Inputs im Status-Tab |
| V6 Cryptography | no | Kein neues Kryptographie-Erfordernis |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| RFID-Hash in UI sichtbar | Information Disclosure | LEFT JOIN auf llx_user; niemals rfid_hash direkt ausgeben (SEC-01/02) |
| SSRF via cURL-Ping | Spoofing/Elevation | HA-URL nur aus Dolibarr-Admin-Konfiguration lesen; kein User-Input fuer URL |
| Tab-Parameter-Injection | Tampering | GETPOST('tab', 'aZ09') — alphanumerisch-Filterung |
| upload_error XSS | Tampering | `htmlspecialchars()` beim Ausgeben von upload_error in der Tabelle |

---

## Sources

### Primary (HIGH confidence)
- [CITED: docs.aiohttp.org/en/stable/web_advanced.html] — AppRunner + TCPSite Pattern verifiziert
- [VERIFIED: Homeassistant/main.py, api_client.py, session_manager.py] — bestehende Code-Struktur direkt gelesen
- [VERIFIED: Dolibarr/htdocs/custom/wallboxbilling/admin.php] — bestehende admin.php Struktur direkt gelesen
- [VERIFIED: Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php] — DB-Schema und upgrade()-Pattern direkt gelesen
- [VERIFIED: .planning/phases/06-monitoring-status/06-CONTEXT.md] — alle Entscheidungen D-01 bis D-11

### Secondary (MEDIUM confidence)
- [CITED: wiki.dolibarr.org/index.php/Module_development] — dol_get_fiche_head Tab-Array-Struktur
- [CITED: doxygen.dolibarr.org — product/admin/product.php] — dol_get_fiche_head Aufruf-Pattern in Produktiv-Code

### Tertiary (LOW confidence)
- WebSearch Ergebnisse zu Dolibarr Tab-System (mehrere Quellen bestaetigen head-Array-Struktur)

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — aiohttp und PHP cURL sind bestehende Technologien im Projekt
- Architecture: HIGH — alle Entscheidungen durch CONTEXT.md verriegelt; bestehender Code direkt geprueft
- Pitfalls: MEDIUM — cURL-Timeout und dol_fiche_end aus Erfahrung, nicht lokal verifizierbar
- DB-Migration: HIGH — identisches Pattern bereits in modWallboxbilling.class.php vorhanden

**Research date:** 2026-06-21
**Valid until:** 2026-08-01 (stabile Technologien; Dolibarr-API aendert sich selten)
