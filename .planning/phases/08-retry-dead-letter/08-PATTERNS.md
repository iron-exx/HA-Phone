# Phase 8: Retry & Dead-letter - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 4 new/modified files
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `Homeassistant/session_manager.py` | service | CRUD + batch | itself (existing) | self-extension |
| `Homeassistant/main.py` | controller | request-response | itself (existing) | self-extension |
| `Homeassistant/tests/test_dead_letter.py` | test | batch | `Homeassistant/tests/test_health.py` | role-match |
| `Dolibarr/htdocs/custom/wallboxbilling/admin.php` | controller | request-response | itself (existing) | self-extension |

---

## Pattern Assignments

---

### `Homeassistant/session_manager.py` (service, CRUD + batch) — modifications

**Analog:** itself — add `_init_database()` extension, new methods `write_dead_letter()`, `retry_dead_letter_sessions()`, `retry_single_dead_letter()`, `get_pending_dead_letters()`, and modify `transmit_completed_sessions()` failure branch.

---

#### Pattern A: `_init_database()` — dead_letter table creation

**Analog lines 64–123** (existing ALTER TABLE migration pattern):

```python
# From session_manager.py lines 92–110 — ALTER TABLE + try/except migration pattern
try:
    cursor.execute('''
        ALTER TABLE sessions ADD COLUMN transmitted_at TEXT
    ''')
    _LOGGER.info("Datenbank-Schema erweitert: transmitted_at hinzugefügt")
except sqlite3.OperationalError:
    # Spalte existiert bereits
    pass
```

**New `dead_letter` table block to add at end of `_init_database()` before `conn.commit()`:**

```python
# Pattern: CREATE TABLE IF NOT EXISTS — same as sessions table (line 75-89)
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
```

---

#### Pattern B: `transmit_completed_sessions()` — failure branch modification

**Analog lines 459–471** (current failure branch — modify in-place):

```python
# CURRENT (lines 459–471) — replace 'error' status with 'dead_letter' + INSERT dead_letter:
# Before:
cursor.execute('''
    UPDATE sessions SET upload_status = ?, upload_error = ? WHERE id = ?
''', ('error', error[:1000] if error else 'Unknown error', session_id))
break

# After (Phase 8):
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
break
```

**Also change the `transmit_completed_sessions()` SELECT query** (line 425–429) to exclude dead_letter sessions:

```python
# CURRENT (line 425-429):
cursor.execute('''
    SELECT id, rfid_hash, wallbox_id, start_time, end_time, total_kwh
    FROM sessions
    WHERE end_time IS NOT NULL AND transmitted_at IS NULL
''')

# AFTER (Phase 8) — exclude sessions already in dead_letter queue:
cursor.execute('''
    SELECT id, rfid_hash, wallbox_id, start_time, end_time, total_kwh
    FROM sessions
    WHERE end_time IS NOT NULL AND transmitted_at IS NULL
      AND (upload_status IS NULL OR upload_status NOT IN ('ok', 'dead_letter'))
''')
```

---

#### Pattern C: `retry_dead_letter_sessions()` — new method

**Analog:** `transmit_completed_sessions()` (lines 411–479) — same structure: open conn, SELECT, loop with success/failure UPDATE. Key divergence: use `continue` per D-01, NOT `break`.

```python
# Pattern: conn setup — same as transmit_completed_sessions() lines 421-422
conn = sqlite3.connect(self.db_path)
cursor = conn.cursor()

# Pattern: SELECT pending entries — mirrors transmit query
cursor.execute(
    "SELECT id, session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh "
    "FROM dead_letter WHERE status = 'pending'"
)
rows = cursor.fetchall()
result = {"retried": 0, "resolved": 0, "still_failed": 0, "errors": []}

# Pattern: loop — CRITICAL: use continue (D-01), NOT break
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
            # Pattern: success UPDATE — mirrors line 454-456
            cursor.execute(
                "UPDATE dead_letter SET status='resolved', last_retry_at=? WHERE id=?",
                (datetime.now().isoformat(), dl_id)
            )
            cursor.execute(
                "UPDATE sessions SET transmitted_at=?, upload_status='ok', upload_error=NULL WHERE id=?",
                (datetime.now().isoformat(), session_id)
            )
            result["resolved"] += 1
        else:
            # Pattern: failure UPDATE — use UPDATE not INSERT (preserves retry_count)
            cursor.execute(
                "UPDATE dead_letter SET retry_count=retry_count+1, error_msg=?, last_retry_at=? WHERE id=?",
                (error[:1000] if error else 'Unknown error', datetime.now().isoformat(), dl_id)
            )
            result["still_failed"] += 1
    except Exception as e:
        # D-01: continue to next entry, do not break
        self._logger.error("Dead-letter retry Fehler für id=%s: %s", dl_id, e)
        result["errors"].append(str(e))
        continue

# Pattern: conn.commit / conn.close — same as transmit lines 473-474
conn.commit()
conn.close()
return result
```

---

#### Pattern D: `retry_single_dead_letter()` — new method (used by `/session/retry` endpoint)

**Analog:** `transmit_completed_sessions()` loop body — same SELECT by id + transmit + UPDATE pattern, single entry.

```python
# Pattern: single-row SELECT by primary key — same SELECT structure as get_active_session() line 186-193
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
# ... same transmit + UPDATE logic as retry_dead_letter_sessions() single iteration
```

---

#### Pattern E: `get_pending_dead_letters()` — new method (used by `/dead-letter/list` endpoint)

**Analog:** `get_completed_sessions()` (lines 385–409) — same SELECT + row_factory + dict conversion pattern.

```python
# Pattern: conn.row_factory = sqlite3.Row — same as get_completed_sessions() line 396
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
# NOTE: rfid_hash is NOT selected — SEC-01/02 (D-04)
return [dict(row) for row in rows]
```

---

### `Homeassistant/main.py` (controller, request-response) — modifications

**Analog:** `handle_session_stop()` (lines 341–365) and `start_health_server()` (lines 368–378).

---

#### Pattern F: `handle_session_retry()` — new endpoint handler

**Analog:** `handle_session_stop()` (lines 341–365) — verbatim structure: global access, json parse, int coerce, None-check, call session_manager, return json_response.

```python
# From main.py lines 341-365 — handle_session_stop() shape to replicate exactly:
async def handle_session_stop(request):
    """POST /session/stop ..."""
    global session_manager, api_client
    try:
        data = await request.json()
        session_id = int(data.get('session_id', 0))
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        if not api_client:
            return web.json_response({"error": "API client not configured"}, status=503)
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
```

New handler `handle_session_retry()` follows this shape exactly, replacing:
- `session_id` → `dead_letter_id`
- `mark_session_incomplete` + `transmit_completed_sessions` → `session_manager.retry_single_dead_letter(api_client, dead_letter_id)`
- Error key string `"session/stop"` → `"session/retry"`

---

#### Pattern G: `handle_dead_letter_list()` — new GET handler

**Analog:** `handle_health()` (line 337) — simplest possible GET handler returning json_response.

```python
# From main.py line 337 — handle_health() shape:
async def handle_health(request):
    """GET /health - Liveness-Check ..."""
    return web.json_response({"status": "ok", "addon": "wallbox-dolibarr"}, status=200)
```

New `handle_dead_letter_list()` replaces the static dict with `session_manager.get_pending_dead_letters()`.

---

#### Pattern H: Route registration in `start_health_server()`

**Analog:** `start_health_server()` lines 368–378 — `app.router.add_*()` calls before `runner.setup()`.

```python
# From main.py lines 370-372 — existing route registration:
app = web.Application()
app.router.add_get('/health', handle_health)
app.router.add_post('/session/stop', handle_session_stop)

# Add after line 372:
app.router.add_post('/session/retry', handle_session_retry)
app.router.add_get('/dead-letter/list', handle_dead_letter_list)
```

---

#### Pattern I: `periodic_transmission()` — add retry call

**Analog:** `periodic_transmission()` lines 427–458 — add one `await` call after `transmit_completed_sessions()`.

```python
# From main.py line 437 — existing call:
result = session_manager.transmit_completed_sessions(api_client)

# Add after result handling block (after line 456, before last_transmit = current_time):
retry_result = session_manager.retry_dead_letter_sessions(api_client)
if retry_result["resolved"] > 0:
    _LOGGER.info("Dead-letter Retries erfolgreich: %s aufgelöst", retry_result["resolved"])
if retry_result["still_failed"] > 0:
    _LOGGER.warning("Dead-letter Retries fehlgeschlagen: %s ausstehend", retry_result["still_failed"])
```

Note: `retry_dead_letter_sessions()` is synchronous (uses `sqlite3.connect` directly, same as `transmit_completed_sessions()`). No `await` needed — call without await, same as the existing `result = session_manager.transmit_completed_sessions(api_client)`.

---

### `Homeassistant/tests/test_dead_letter.py` (test) — new file

**Analog:** `test_health.py` (lines 1–173) for endpoint test structure; `conftest.py` (lines 14–63) for fixture reuse.

---

#### Pattern J: Test file structure

**Analog:** `test_health.py` lines 1–15 — file header + imports:

```python
# From test_health.py lines 1-15:
#!/usr/bin/env python3
"""
Tests fuer /health und /session/stop HTTP-Endpunkte (MON-01, D-04, D-14, D-15)
TDD RED phase — tests must fail before implementation is added to main.py
"""
import asyncio
import sys
import os
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

New `test_dead_letter.py` uses the same header convention with module docstring citing RET-01, RET-02, RET-03.

---

#### Pattern K: Fixture reuse from conftest.py

**Analog:** `conftest.py` lines 14–44 — `in_memory_session_manager`, `mock_api_client_success`, `mock_api_client_failure`.

```python
# From conftest.py lines 14-44 — fixtures available without import (pytest auto-discovery):
@pytest.fixture
def in_memory_session_manager(tmp_path):
    """SessionManager backed by a temporary file SQLite database."""
    from session_manager import SessionManager
    db_file = str(tmp_path / "test_sessions.db")
    sm = SessionManager(db_path=db_file)
    yield sm

@pytest.fixture
def mock_api_client_success():
    class MockApiClient:
        def transmit_session(self, session):
            return (True, "")
    return MockApiClient()

@pytest.fixture
def mock_api_client_failure():
    class MockApiClient:
        def transmit_session(self, session):
            return (False, "HTTP 503: Service Unavailable")
    return MockApiClient()
```

All three fixtures are available by name in `test_dead_letter.py` with no import — pytest discovers `conftest.py` automatically.

---

#### Pattern L: Unit test class structure

**Analog:** `test_health.py` classes `TestHealthEndpointBehavior` and `TestMainPyStructure` — group by requirement ID.

```python
# From test_health.py lines 16-32 — class + docstring per test pattern:
class TestHealthEndpointBehavior:
    """Tests fuer GET /health Endpunkt-Verhalten"""

    def test_health_returns_200_with_correct_body(self):
        """Test 1: GET /health gibt 200 mit {'status': 'ok', 'addon': 'wallbox-dolibarr'} zurueck"""
        ...
```

New test classes for dead_letter:
- `TestDeadLetterWrite` — RET-01: write_dead_letter() correct fields
- `TestDeadLetterDuplicatePrevention` — RET-01: UNIQUE(session_id) + INSERT OR IGNORE
- `TestSessionStatusAfterFailure` — RET-01: sessions.upload_status = 'dead_letter'
- `TestRetryResolution` — RET-03: resolved on success
- `TestRetryCountIncrement` — RET-03: retry_count++ on failure
- `TestSessionTransmittedAtAfterRetry` — RET-03: sessions.transmitted_at set on success
- `TestRetryEndpoint` — RET-02: 400 on missing id, 503 on no api_client

Each class uses `in_memory_session_manager` fixture to seed a completed session, call the relevant SessionManager method, then assert SQLite state directly.

---

#### Pattern M: Endpoint test using subprocess/aiohttp TestClient

**Analog:** `test_health.py` lines 20–61 — inline subprocess or `aiohttp.test_utils.TestClient` pattern for async endpoint tests.

```python
# From test_health.py lines 63-96 — session/stop endpoint test structure:
def test_session_stop_missing_session_id_returns_400(self):
    import subprocess
    result = subprocess.run(
        ['python3', '-c', '''
import asyncio
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

async def handle_session_stop(request):
    data = await request.json()
    session_id = int(data.get("session_id", 0))
    if not session_id:
        return web.json_response({"error": "session_id required"}, status=400)
    ...

async def test():
    app = web.Application()
    app.router.add_post("/session/stop", handle_session_stop)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post("/session/stop", json={"session_id": 0})
        assert resp.status == 400
        ...
asyncio.run(test())
'''], capture_output=True, text=True)
    assert "Test 2 PASS" in result.stdout
```

`TestRetryEndpoint` replicates this pattern substituting `/session/retry` and `dead_letter_id`.

---

### `Dolibarr/htdocs/custom/wallboxbilling/admin.php` (controller, request-response) — modifications

**Analog:** itself — add 4th tab, `retry_dead_letter` action handler, `deadletter` tab content block.

---

#### Pattern N: 4th tab array entry

**Analog:** admin.php lines 95–108 — existing tab array pattern.

```php
// From admin.php lines 95-108 — verbatim pattern for new 4th tab (add after $h=2 block):
$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=rfid';
$head[$h][1] = $langs->trans('WallboxUserRFIDManagement');
$head[$h][2] = 'rfid';
$h++;

// Add new 4th tab immediately after:
$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=deadletter';
$head[$h][1] = $langs->trans('WallboxDeadLetter');
$head[$h][2] = 'deadletter';
$h++;
```

---

#### Pattern O: `retry_dead_letter` action handler

**Analog:** admin.php lines 50–81 — `stop_session` action handler (verbatim template).

```php
// From admin.php lines 50-81 — stop_session action handler to replicate:
if ($action == 'stop_session') {
    checkToken();
    $session_id = GETPOST('session_id', 'int');
    $ha_url = getDolGlobalString('WALLBOXBILLING_HA_URL', '');

    if ($session_id > 0 && !empty($ha_url)) {
        $ch = curl_init($ha_url . '/session/stop');
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(array('session_id' => (int)$session_id)));
        curl_setopt($ch, CURLOPT_HTTPHEADER, array('Content-Type: application/json'));
        curl_setopt($ch, CURLOPT_TIMEOUT, 4);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 4);
        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        $curl_error = curl_error($ch);
        curl_close($ch);

        if ($curl_error || $http_code != 200) {
            $err_detail = $curl_error ? $curl_error : 'HTTP '.$http_code;
            setEventMessages($langs->trans('StopSessionFailed').': '.$err_detail, null, 'errors');
            dol_syslog("Wallbox stop_session failed for session_id=".$session_id.": ".$err_detail, LOG_ERR);
        } else {
            setEventMessages($langs->trans('StopSessionSuccess'), null, 'mesgs');
        }
    } else {
        setEventMessages($langs->trans('StopSessionInvalidOrNoURL'), null, 'errors');
    }
    header('Location: '.$_SERVER['PHP_SELF'].'?tab=status');
    exit;
}
```

New `retry_dead_letter` handler substitutes:
- `session_id` → `dead_letter_id`
- `/session/stop` → `/session/retry`
- `StopSessionFailed/Success/InvalidOrNoURL` → `RetryDeadLetterFailed/RetryDeadLetterSuccess` + `WallboxHAUnreachable`
- `?tab=status` redirect → `?tab=deadletter`

---

#### Pattern P: `deadletter` tab content — cURL GET + table render

**Analog:** admin.php lines 117–243 — `status` tab: cURL health check + table with rows. Replace DB query with cURL GET to `/dead-letter/list`.

```php
// Analog A: cURL GET pattern — from admin.php lines 123-139 (health check):
$ch = curl_init($ha_url . '/health');
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
curl_setopt($ch, CURLOPT_TIMEOUT, 4);
curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 4);
$response = curl_exec($ch);
$http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curl_error = curl_error($ch);
curl_close($ch);
// Dead-letter list: same cURL pattern to /dead-letter/list, then json_decode($response, true)

// Analog B: table render — from admin.php lines 170-243 (status tab table):
print '<div class="div-table-responsive">';
print '<table class="noborder centpercent">';
print '<tr class="liste_titre">';
print '<td>'.$langs->trans('Date').'</td>';
// ... column headers ...
print '</tr>';
// ... row loop ...
print '</table>';
print '</div>';

// Analog C: status badge color — from admin.php lines 206-213:
if ($obj->upload_status == 'ok') {
    $status_html = '<span style="color:green">'.$status_label.'</span>';
} elseif ($obj->upload_status == 'error') {
    $status_html = '<span style="color:red">'.$status_label.'</span>';
} else {
    $status_html = '<span style="color:orange">'.$status_label.'</span>';
}
// Dead-letter: pending=orange, resolved=green (won't show — filtered by WHERE status='pending')

// Analog D: XSS prevention — from admin.php lines 216-222:
print '<td>'.htmlspecialchars($obj->start_time ?? '', ENT_QUOTES, 'UTF-8').'</td>';
print '<td>'.htmlspecialchars($obj->wallbox_id ?? '', ENT_QUOTES, 'UTF-8').'</td>';
print '<td>'.htmlspecialchars(number_format((float)($obj->kwh ?? 0), 2), ENT_QUOTES, 'UTF-8').'</td>';
// error_msg: truncate to 80 chars before htmlspecialchars
// htmlspecialchars(mb_substr($obj->error_msg ?? '', 0, 80), ENT_QUOTES, 'UTF-8').(mb_strlen(...) > 80 ? '...' : '')

// Analog E: per-row retry form — from admin.php lines 226-233 (stop_session form):
print '<form method="POST" action="'.$_SERVER['PHP_SELF'].'?tab=status" style="display:inline">';
print '<input type="hidden" name="token" value="'.newToken().'">';
print '<input type="hidden" name="action" value="stop_session">';
print '<input type="hidden" name="session_id" value="'.((int)$obj->rowid).'">';
print '<input type="submit" class="button smallpaddingimp" value="'.htmlspecialchars($langs->trans('StopSession'), ENT_QUOTES, 'UTF-8').'">';
print '</form>';
// Dead-letter: substitute action=retry_dead_letter, dead_letter_id=(int)$entry['id'], ?tab=deadletter
```

---

## Shared Patterns

### CSRF Pattern
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php` lines 51 + 229
**Apply to:** `retry_dead_letter` action handler + Retry form in deadletter tab

```php
// Action handler (before HTML):
checkToken();

// Form (in tab HTML):
print '<input type="hidden" name="token" value="'.newToken().'">';
```

---

### aiohttp JSON Handler Error Shape
**Source:** `Homeassistant/main.py` lines 361–365
**Apply to:** `handle_session_retry()`, `handle_dead_letter_list()`

```python
except (ValueError, TypeError) as e:
    return web.json_response({"error": "invalid session_id"}, status=400)
except Exception as e:
    _LOGGER.error("session/stop Fehler: %s", e)
    return web.json_response({"error": str(e)}, status=500)
```

---

### SQLite Connection Pattern (synchronous)
**Source:** `Homeassistant/session_manager.py` lines 421–422 + 473–474
**Apply to:** all new `SessionManager` methods

```python
conn = sqlite3.connect(self.db_path)
cursor = conn.cursor()
# ... operations ...
conn.commit()
conn.close()
```

---

### POST→Redirect→Flash (PRG) Pattern
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php` lines 68–80
**Apply to:** `retry_dead_letter` action handler

```php
if ($curl_error || $http_code != 200) {
    $err_detail = $curl_error ? $curl_error : 'HTTP '.$http_code;
    setEventMessages($langs->trans('StopSessionFailed').': '.$err_detail, null, 'errors');
    dol_syslog("Wallbox stop_session failed ...", LOG_ERR);
} else {
    setEventMessages($langs->trans('StopSessionSuccess'), null, 'mesgs');
}
header('Location: '.$_SERVER['PHP_SELF'].'?tab=status');
exit;
```

---

### Logging Pattern (Python)
**Source:** `Homeassistant/session_manager.py` lines 458 + 463 + 476–477
**Apply to:** all new SessionManager methods + main.py handlers

```python
self._logger.info("Session %s erfolgreich übertragen", session_id)
self._logger.error("Fehler bei Session %s: %s", session_id, error)
self._logger.info("API-Übertragung abgeschlossen: %s übertragen, %s fehlgeschlagen",
                 result["transmitted"], result["failed"])
```

---

### Security: rfid_hash exclusion (D-04 / SEC-01/02)
**Source:** admin.php lines 185–192 (SQL does not select rfid_hash) + UI spec §2
**Apply to:** `get_pending_dead_letters()` SELECT statement, `deadletter` tab table columns

Rule: Never SELECT or print `rfid_hash`. The `/dead-letter/list` JSON response and all `print` statements in the `deadletter` tab block must not reference `rfid_hash`.

---

## No Analog Found

All four files have strong analogs within the existing codebase. No external patterns required.

---

## Metadata

**Analog search scope:** `Homeassistant/`, `Dolibarr/htdocs/custom/wallboxbilling/`, `Homeassistant/tests/`
**Files scanned:** 7 (session_manager.py, main.py, api_client.py, admin.php, conftest.py, test_health.py, 08-UI-SPEC.md)
**Pattern extraction date:** 2026-06-23
