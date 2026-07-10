# Phase 6: Monitoring & Status - Pattern Map

**Mapped:** 2026-06-21
**Files analyzed:** 5 new/modified files
**Analogs found:** 5 / 5

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `Dolibarr/htdocs/custom/wallboxbilling/admin.php` | controller (UI) | request-response | self (existing file, extended) | exact |
| `Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php` | migration | CRUD | self (existing upgrade() method) | exact |
| `Homeassistant/main.py` | service (async) | event-driven + request-response | self (existing asyncio main()) | exact |
| `Homeassistant/api_client.py` | service | request-response | self (existing transmit_session()) | exact |
| `Homeassistant/session_manager.py` | service | CRUD | self (existing transmit_completed_sessions()) | exact |

---

## Pattern Assignments

### `Dolibarr/htdocs/custom/wallboxbilling/admin.php` (controller, request-response)

**Change type:** EXTEND — Tab-System hinzufügen; bestehende Inhalte in Tabs aufteilen; Status-Tab neu erstellen.

**Analog:** self (lines 1-146 as read above)

**Auth/Guard pattern** (lines 11-14 of admin.php):
```php
// Berechtigungsprüfung (SEC-04) — MUST be preserved as-is at top of file
if (!$user->rights->wallboxbilling->admin) {
    accessforbidden();
}
```

**Tab-System pattern** — replace the flat layout with dol_get_fiche_head (RESEARCH.md Pattern 1):
```php
// Tab-Array aufbauen (before llxHeader call area, after $langs->load())
$head = array();
$h = 0;

$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=status';
$head[$h][1] = $langs->trans('WallboxStatus');
$head[$h][2] = 'status';
$h++;

$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=config';
$head[$h][1] = $langs->trans('WallboxConfiguration');
$head[$h][2] = 'config';
$h++;

$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=rfid';
$head[$h][1] = $langs->trans('WallboxUserRFIDManagement');
$head[$h][2] = 'rfid';
$h++;

// Default = 'status' (D-02)
$tab = GETPOST('tab', 'aZ09');
if (empty($tab)) $tab = 'status';

// Tab-Leiste rendern (after load_fiche_titre())
print dol_get_fiche_head($head, $tab, $langs->trans('WallboxBillingSetup'), -1, 'title_setup');

if ($tab == 'status') {
    // ... Status-Tab-Inhalt (see cURL + SQL patterns below) ...
} elseif ($tab == 'config') {
    // ... bestehender Konfigurationsformular-Block aus admin.php lines 29-45 ...
} elseif ($tab == 'rfid') {
    // ... bestehender RFID-Block aus admin.php lines 48-105 ...
}

print dol_fiche_end();  // MUST be present — closes the <div> opened by dol_get_fiche_head
```

**cURL Health-Ping pattern** (inside `$tab == 'status'` block; RESEARCH.md Pattern 2):
```php
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
```

**HTML table render pattern** — copy class names from existing admin.php (lines 33-36, 55-62):
```php
print '<table class="noborder centpercent">';
print '<tr class="liste_titre">';
print '<td>'.$langs->trans('ColumnHeader').'</td>';
print '</tr>';
// rows:
print '<tr class="oddeven">';
print '<td>'.htmlspecialchars($value).'</td>';
print '</tr>';
print '</table>';
```
Note: `htmlspecialchars()` is REQUIRED for `upload_error` output (XSS mitigation, RESEARCH.md Security section).

**Session-Tabelle SQL pattern** (RESEARCH.md Pattern 5 — LEFT JOIN chain):
```php
$sql = "SELECT s.rowid, s.start_time, s.wallbox_id, s.kwh,";
$sql.= " s.upload_status, s.upload_error,";
$sql.= " COALESCE(CONCAT(u.firstname, ' ', u.lastname), '".$db->escape($langs->trans('Unknown'))."') as user_name";
$sql.= " FROM ".MAIN_DB_PREFIX."wallbox_sessions as s";
$sql.= " LEFT JOIN ".MAIN_DB_PREFIX."wallbox_rfid as r ON s.rfid_hash = r.rfid_hash";
$sql.= " LEFT JOIN ".MAIN_DB_PREFIX."user as u ON r.fk_user = u.rowid";
$sql.= " WHERE s.status = 'completed'";
$sql.= " ORDER BY s.rowid DESC";
$sql.= " LIMIT 25";

$resql = $db->query($sql);
if ($resql) {
    $num = $db->num_rows($resql);
    $i = 0;
    while ($i < $num) {
        $obj = $db->fetch_object($resql);
        // ... print table row ...
        $i++;
    }
    $db->free($resql);
}
```
Pattern source: admin.php lines 66-102 (existing user query uses identical $db->query / fetch_object / free pattern).

**Manual session stop button pattern** (D-12 to D-16) — POST form inside table row:
```php
// Inside the session table row, for sessions with upload_status = 'pending'
if ($obj->upload_status == 'pending') {
    print '<td>';
    print '<form method="POST" action="'.$_SERVER['PHP_SELF'].'?tab=status">';
    print '<input type="hidden" name="token" value="'.newToken().'">';
    print '<input type="hidden" name="action" value="stop_session">';
    print '<input type="hidden" name="session_id" value="'.((int)$obj->rowid).'">';
    print '<input type="submit" class="button smallpaddingimp" value="'.$langs->trans('StopSession').'">';
    print '</form>';
    print '</td>';
}
```
Action handler at top of file (before HTML output): read `GETPOST('action', 'alpha') == 'stop_session'`, then send POST to `$ha_url . '/session/stop'` via cURL with `{"session_id": (int)$session_id}`.

---

### `Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php` (migration, CRUD)

**Change type:** EXTEND — add three new columns to `upgrade()` method AND to `init()`/`install()` CREATE TABLE statements.

**Analog:** self — existing `upgrade()` method (lines 294-307) and `install()` column-check pattern (lines 257-262).

**Existing SHOW COLUMNS guard pattern** (lines 257-262 of modWallboxbilling.class.php):
```php
// Exact pattern already in install() — replicate for upgrade()
$check_col = "SHOW COLUMNS FROM llx_wallbox_sessions LIKE 'transmitted_at'";
$res = $db->query($check_col);
if (!$res || $db->num_rows($res) == 0) {
    $db->query("ALTER TABLE llx_wallbox_sessions ADD COLUMN transmitted_at DATETIME NULL AFTER date_creation");
}
```

**New columns to add** — copy the guard pattern three times in `upgrade()` (RESEARCH.md Pattern 4):
```php
// In upgrade() — after existing transmitted_at guard block:
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

**CREATE TABLE extension** — add columns to `init()` and `install()` CREATE TABLE IF NOT EXISTS statement (lines 127-141 and 199-212):
```sql
-- Add after `transmitted_at DATETIME NULL` in both CREATE TABLE blocks:
`upload_status` ENUM('pending','ok','error') NOT NULL DEFAULT 'pending',
`upload_error` TEXT NULL,
`uploaded_at` DATETIME NULL,
```

**Error logging pattern** — copy from install() line 252:
```php
dol_syslog("WallboxBilling SQL error: ".$db->lasterror, LOG_ERR);
```

---

### `Homeassistant/main.py` (service, event-driven + request-response)

**Change type:** EXTEND — add aiohttp AppRunner for `/health` and `/session/stop` endpoints; integrate into existing `main()` asyncio.gather.

**Analog:** self — existing `main()` function (lines 283-374) and `periodic_transmission()` async task pattern (lines 328-353).

**Existing asyncio.gather pattern** (lines 355-368 of main.py):
```python
# Current pattern — extend this to include health_runner cleanup
try:
    await ha_ws.connect()
    await check_startup_session()

    if api_client:
        transmission_task = asyncio.create_task(periodic_transmission())

    await ha_ws.subscribe_entities(sensor_callback)

except KeyboardInterrupt:
    _LOGGER.info("Addon wird beendet...")
except Exception as e:
    _LOGGER.error("Fehler: %s", e, exc_info=True)
    raise
finally:
    await ha_ws.disconnect()
```

**New /health endpoint pattern** (RESEARCH.md Pattern 3 + Code Examples):
```python
from aiohttp import web

async def handle_health(request):
    """GET /health - Liveness-Check fuer Dolibarr cURL-Ping"""
    return web.json_response({"status": "ok", "addon": "wallbox-dolibarr"}, status=200)

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

**New /session/stop endpoint pattern** (D-14, D-15):
```python
async def handle_session_stop(request):
    """POST /session/stop - Manuelle Session-Beendigung durch Dolibarr-Admin (D-14)"""
    global session_manager, api_client
    try:
        data = await request.json()
        session_id = int(data.get('session_id', 0))
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)

        # Session beenden (end_energy from last known value or current HA state)
        # Sofort-Upload (D-13)
        if api_client:
            result = session_manager.transmit_completed_sessions(api_client)
            return web.json_response({"status": "ok", "result": result}, status=200)
        else:
            return web.json_response({"error": "API client not configured"}, status=503)
    except Exception as e:
        _LOGGER.error("session/stop Fehler: %s", e)
        return web.json_response({"error": str(e)}, status=500)
```

**Integration into main()** — extend start_health_server and finally block:
```python
# In main(), before subscribe_entities call:
health_runner = await start_health_server(port=8099)

# In finally block — add alongside ha_ws.disconnect():
finally:
    await health_runner.cleanup()
    await ha_ws.disconnect()
```

**Import additions** (at top of main.py — aiohttp.web not yet imported):
```python
from aiohttp import web  # Add to existing `import aiohttp` line or as separate import
```
Note: `aiohttp` is already imported on line 9 as `import aiohttp` — change to `from aiohttp import web` or add `web = aiohttp.web` alias.

---

### `Homeassistant/api_client.py` (service, request-response)

**Change type:** EXTEND — `transmit_session()` returns `Tuple[bool, str]` already (lines 86-143). No structural change needed. The upload_status writing for MySQL (Dolibarr side) is handled by Dolibarr's `session.php` API handler upon receiving the POST (per RESEARCH.md Open Question 1 recommendation).

**Existing return pattern** (lines 122-143 of api_client.py):
```python
# Already returns (True, "") on success
return (True, "")

# Returns (False, error_msg) variants:
except requests.exceptions.Timeout:
    error_msg = f"Timeout nach {self.timeout}s"
    return (False, error_msg)

except requests.exceptions.HTTPError as e:
    error_msg = f"HTTP {response.status_code}: {response.text}"
    return (False, error_msg)
```
This return value is already consumed by `session_manager.py::transmit_completed_sessions()` (lines 436-449). No change to api_client.py is needed for Phase 6 unless a dedicated PATCH error-status call is required (deferred to planner decision).

---

### `Homeassistant/session_manager.py` (service, CRUD)

**Change type:** EXTEND — `transmit_completed_sessions()` (lines 397-460) already writes `transmitted_at`. Phase 6 adds writing of `upload_status` and `upload_error` to the **SQLite** local DB (optional, see RESEARCH.md Open Question 3 — recommended to defer to Phase 8). No SQLite schema change for Phase 6.

**Existing UPDATE pattern** (lines 438-443 of session_manager.py):
```python
# Pattern to extend if SQLite upload_status tracking is desired:
cursor.execute('''
    UPDATE sessions SET transmitted_at = ? WHERE id = ?
''', (datetime.now().isoformat(), session_id))
```

**If SQLite upload_status is added** — extend ALTER TABLE in `_init_database()` using existing migration guard (lines 88-96):
```python
try:
    cursor.execute('ALTER TABLE sessions ADD COLUMN upload_status TEXT DEFAULT "pending"')
    cursor.execute('ALTER TABLE sessions ADD COLUMN upload_error TEXT')
except sqlite3.OperationalError:
    pass  # Column already exists
```

---

## Shared Patterns

### Auth/Permission Check
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php` lines 11-14
**Apply to:** All new PHP code blocks in admin.php (auth check is at file top — applies to all tabs automatically)
```php
if (!$user->rights->wallboxbilling->admin) {
    accessforbidden();
}
```

### GETPOST Input Sanitization
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php` lines 80-82, 111
**Apply to:** All `$_GET`/`$_POST` reads in admin.php Status-Tab
```php
$tab = GETPOST('tab', 'aZ09');       // alphanumeric only
$session_id = GETPOST('session_id', 'int');  // integer only
```

### Dolibarr DB Query Pattern
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php` lines 70-102
**Apply to:** Session-Tabelle SQL in Status-Tab
```php
$resql = $db->query($sql);
if ($resql) {
    $num = $db->num_rows($resql);
    $i = 0;
    while ($i < $num) {
        $obj = $db->fetch_object($resql);
        // use $obj->fieldname
        $i++;
    }
    $db->free($resql);
}
```

### SHOW COLUMNS Migration Guard
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php` lines 257-262
**Apply to:** All ALTER TABLE operations in upgrade() and install()
```php
$check_col = "SHOW COLUMNS FROM llx_wallbox_sessions LIKE 'column_name'";
$res = $db->query($check_col);
if (!$res || $db->num_rows($res) == 0) {
    $db->query("ALTER TABLE llx_wallbox_sessions ADD COLUMN ...");
}
```

### Python Logging Pattern
**Source:** `Homeassistant/main.py` lines 28-33; `Homeassistant/api_client.py` line 15
**Apply to:** All new Python functions in main.py and session_manager.py
```python
_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Message with %s placeholder", value)
_LOGGER.error("Error: %s", e)
```

### aiohttp Error Response Pattern
**Source:** RESEARCH.md Pattern 3 + api_client.py exception handling
**Apply to:** `/health` and `/session/stop` handlers in main.py
```python
# Success:
return web.json_response({"status": "ok"}, status=200)
# Error:
return web.json_response({"error": "message"}, status=400)
```

### Token CSRF Protection
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php` lines 30-31, 49-50
**Apply to:** All new POST forms in admin.php (session stop button)
```php
print '<input type="hidden" name="token" value="'.newToken().'">';
```

### XSS Prevention for DB Content
**Source:** RESEARCH.md Security section (upload_error XSS threat)
**Apply to:** All places in admin.php where `upload_error` or any DB text is output to HTML
```php
print htmlspecialchars($obj->upload_error ?? '', ENT_QUOTES, 'UTF-8');
```

---

## No Analog Found

All files have direct analogs (all are extensions of existing files). No greenfield files in this phase.

---

## Key Anti-Patterns (from RESEARCH.md)

| Anti-Pattern | Where It Would Occur | Correct Pattern |
|---|---|---|
| `web.run_app()` blocking call | main.py | Use `AppRunner + TCPSite` (Pattern 3) |
| `requests.get()` inside asyncio | main.py health handler | aiohttp handles it natively; cURL runs on PHP side |
| Missing `dol_fiche_end()` | admin.php | Always call after tab content, before `llxFooter()` |
| Missing `CURLOPT_TIMEOUT` | admin.php cURL ping | Set both `CURLOPT_TIMEOUT` and `CURLOPT_CONNECTTIMEOUT` to 4 |
| `rfid_hash` printed directly | admin.php session table | Always JOIN to `llx_user` and display name only |
| Hardcoded HA URL | admin.php | Always read via `getDolGlobalString('WALLBOXBILLING_HA_URL')` |
| INNER JOIN for sessions | admin.php session SQL | LEFT JOIN — sessions without RFID mapping must still appear |

---

## Metadata

**Analog search scope:** `/home/roto/Dolibarr/htdocs/custom/wallboxbilling/`, `/home/roto/Homeassistant/`
**Files scanned:** 5 (admin.php, modWallboxbilling.class.php, main.py, api_client.py, session_manager.py)
**Pattern extraction date:** 2026-06-21
