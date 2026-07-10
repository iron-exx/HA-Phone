---
phase: 06-monitoring-status
reviewed: 2026-06-22T00:00:00Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php
  - Homeassistant/session_manager.py
  - Homeassistant/main.py
  - Dolibarr/htdocs/custom/wallboxbilling/admin.php
  - Homeassistant/tests/test_session_status.py
  - Homeassistant/tests/conftest.py
findings:
  critical: 4
  warning: 5
  info: 2
  total: 11
status: issues_found
---

# Phase 06: Code Review Report — Gap-Closure (Plan 06-04)

**Reviewed:** 2026-06-22
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

This review covers the gap-closure fixes for the five prior findings (CR-01 infinite recursion, CR-02 missing CSRF on `stop_session`, CR-03 `session_id` not used in stop handler, WR-06 logger-before-db-init, WR-07 broken `<td>` structure, WR-08 `sm._conn` in tests). Some prior issues are genuinely fixed; several remain broken or were replaced with new defects. The test suite will fail at runtime due to NOT NULL violations, `xfail` markers are inverted, and the `update_rfid` action still lacks CSRF protection. The CR-01 "infinite recursion" fix is structural but leaves a different correctness problem in its place.

### Prior Finding Status

| ID    | Fixed? | Notes |
|-------|--------|-------|
| CR-01 | PARTIAL | Recursion eliminated, but `parent::__construct()` is never called — Dolibarr base-class initialization is skipped entirely. See CR-01-NEW. |
| CR-02 | FIXED | `checkToken()` is present on `stop_session` action (line 49 of admin.php). |
| CR-03 | PARTIAL | `session_id` is now passed to `mark_session_incomplete()`, but the semantics are wrong: `incomplete` sessions with a non-NULL `end_time` are picked up by `transmit_completed_sessions` and sent with `kwh=0.0`. See WR-01. |
| WR-06 | FIXED | Module-level `_LOGGER` is now used before `self._logger` exists; correct pattern. |
| WR-07 | FIXED | The status table now emits 7 `<td>` cells per row matching the 7-column header. |
| WR-08 | FIXED | Tests use `sqlite3.connect(sm.db_path)` instead of the non-existent `sm._conn`. |

---

## Critical Issues

### CR-01-NEW: `modWallboxbilling` Never Calls `parent::__construct()`

**File:** `Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php:19`
**Issue:** The constructor sets properties directly on `$this` and calls `$this->init()` (line 115) but never calls `parent::__construct($db)`. `DolibarrModules::__construct()` registers the module in the Dolibarr framework, sets internal registry entries, and initializes `$this->tabs`, `$this->boxes`, `$this->dictionaries`, and other properties that the module manager reads during activation. Without the parent call the module will either fail to activate or produce an incomplete registration — missing menu entries, broken `$this->const_name` resolution, and no box/tab registration. The prior CR-01 finding was recursion caused by the parent calling `init()` which was overridden here; the fix removed the parent call entirely rather than restructuring `init()` so it does not conflict.

**Fix:** Call `parent::__construct($db)` after setting all `$this->*` properties. Move table-creation SQL out of `init()` (which the framework calls on every page load) into `install()` and `upgrade()` only — those methods already contain the correct SQL and are correct.
```php
public function __construct($db)
{
    global $langs, $conf;

    $this->db = $db;
    $this->numero = 104000;
    $this->rights_class = 'wallboxbilling';
    // ... all other property assignments ...

    parent::__construct($db);  // Called AFTER setting properties
    // Do NOT call $this->init() here
}

// Remove or make init() a no-op; table creation belongs in install()/upgrade()
public function init($options = '')
{
    return $this->_init(array(), $options);
}
```

---

### CR-02-NEW: `update` and `update_rfid` Actions Lack `checkToken()` — CSRF

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:24,31`
**Issue:** The prior CR-02 fix added `checkToken()` only to the `stop_session` action. The `update` action (line 24) and `update_rfid` action (line 31) still do not call `checkToken()` before processing POST data. Both actions mutate persistent state: `update` writes a global Dolibarr constant via `dolibarr_set_const()`; `update_rfid` (once the DB write is implemented) will modify RFID-to-user mappings. A CSRF attack against an authenticated admin can change the billing price per kWh or replace RFID associations without the admin's knowledge.

**Fix:**
```php
if ($action == 'update') {
    checkToken();
    $new_price = GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'alpha');
    dolibarr_set_const($db, 'WALLBOXBILLING_DEFAULT_PRICE', $new_price, 'chaine', 0, '', $conf->entity);
    setEventMessages($langs->trans('Saved'), null, 'mesgs');
}

if ($action == 'update_rfid') {
    checkToken();
    // ... rest of handler
}
```

---

### CR-03-NEW: Test INSERTs Omit NOT NULL Column `start_time` — Tests Fail Before Reaching Assertions

**File:** `Homeassistant/tests/test_session_status.py:34,58`
**Issue:** Both test INSERT statements specify `(wallbox_id, rfid_hash, end_time, total_kwh)` but omit `start_time`, which is defined `TEXT NOT NULL` in the `sessions` schema (session_manager.py line 80). SQLite enforces NOT NULL; these INSERTs will raise `sqlite3.IntegrityError: NOT NULL constraint failed: sessions.start_time` before any assertion executes. The tests will error out rather than fail, and the WR-08 fix they are meant to verify is not actually exercised by a passing test run.

**Fix:**
```python
# test_transmit_success_writes_upload_status_ok
conn.execute(
    "INSERT INTO sessions (wallbox_id, rfid_hash, start_time, end_time, total_kwh) "
    "VALUES (?, ?, ?, ?, ?)",
    ("wb-01", "abc123", "2026-06-22T09:00:00", "2026-06-22T10:00:00", 12.5)
)

# test_transmit_failure_writes_upload_status_error
conn.execute(
    "INSERT INTO sessions (wallbox_id, rfid_hash, start_time, end_time, total_kwh) "
    "VALUES (?, ?, ?, ?, ?)",
    ("wb-02", "def456", "2026-06-22T09:00:00", "2026-06-22T10:00:00", 7.3)
)
```

---

### CR-04-NEW: `xfail` Markers Are Semantically Inverted — Fixed Tests Will Appear as `XPASS` Failures

**File:** `Homeassistant/tests/test_session_status.py:14,26,50`
**Issue:** All three tests carry `@pytest.mark.xfail(reason="WR-08 fixed: ...")`. The reason strings describe the tests as *verification of already-completed fixes*, meaning the tests are expected to pass. A test decorated with `@pytest.mark.xfail` that actually passes is reported by pytest as `XPASS` ("unexpected pass"). By default pytest treats XPASS as a failure (or at minimum as a non-green result), so CI will reject these tests even when the code is correct. The `xfail` decorator is appropriate when a test is written for a known-broken feature. These tests document a completed fix and must not carry `xfail`.

**Fix:** Remove all three `@pytest.mark.xfail` decorators:
```python
# Remove this line entirely from all three tests:
# @pytest.mark.xfail(reason="WR-08 fixed: ...")
def test_init_database_creates_upload_status_column(in_memory_session_manager):
    ...
```

---

## Warnings

### WR-01: `handle_session_stop` Marks Session `incomplete` Then Transmits It With `kwh=0`

**File:** `Homeassistant/main.py:303-306`
**Issue:** The stop handler calls `mark_session_incomplete(session_id, reason='admin_stop')` which sets `status='incomplete'` and `end_time=now()` with no energy data. The immediately following `transmit_completed_sessions()` queries `WHERE end_time IS NOT NULL AND transmitted_at IS NULL` — this will match the just-marked incomplete session and transmit it to Dolibarr with `total_kwh=NULL` (or `0.0`). The admin intended to stop and finalize the session, but the transmitted record has no meaningful energy data. Additionally, `mark_session_incomplete` does not set `upload_status` to anything, so the status column remains `pending` forever after transmission if it is excluded from the transmit query.

**Fix:** The stop handler should call `end_session()` (passing a current energy reading if available, or the last known reading) rather than `mark_session_incomplete()`. If no energy reading is available, at minimum set `total_kwh=0` explicitly and use `status='completed'` so the record transmits as a zero-kWh session rather than a corrupted one.

---

### WR-02: `update_rfid` Action Computes RFID Hash But Never Writes It to the Database

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:38-44`
**Issue:** The `update_rfid` handler computes `$rfid_hash = hash('sha256', $rfid_hex)` (line 40), logs it with `dol_syslog()` (line 41), and shows the user a success message "RFID Hash Saved" (line 42). No SQL INSERT or UPDATE is executed. The hash is silently discarded. The admin UI presents the operation as successful while the RFID-to-user mapping is never persisted. This makes the entire RFID management tab non-functional.

**Fix:**
```php
if ($user_id > 0 && !empty($rfid_hex)) {
    $rfid_hash = hash('sha256', $rfid_hex);
    $sql = "INSERT INTO ".MAIN_DB_PREFIX."wallbox_rfid"
         . " (fk_user, rfid_hash, label, active, date_creation)"
         . " VALUES (".(int)$user_id.", '".$db->escape($rfid_hash)."', '', 1, NOW())"
         . " ON DUPLICATE KEY UPDATE fk_user = ".(int)$user_id;
    if ($db->query($sql)) {
        setEventMessages($langs->trans('RFIDHashSaved'), null, 'mesgs');
    } else {
        setEventMessages($langs->trans('Error').': '.$db->lasterror(), null, 'errors');
    }
}
```

---

### WR-03: `session_manager` Not Guarded Against `None` in `handle_session_stop`

**File:** `Homeassistant/main.py:304`
**Issue:** `handle_session_stop` calls `session_manager.mark_session_incomplete(...)` at line 304 without checking whether `session_manager is None`. The global is initialized to `None` at line 47 and only assigned in `main()` at line 338. In the health_app fixture (conftest.py line 48-63) `handle_session_stop` is wired into a test app without `main()` having run, so `session_manager` remains `None`. Any test that POST-tests `/session/stop` via the fixture will get an unhandled `AttributeError` converted to a 500 response rather than the expected behavior. The guard for `api_client` (line 300-301) exists but the guard for `session_manager` is absent.

**Fix:**
```python
async def handle_session_stop(request):
    global session_manager, api_client
    try:
        data = await request.json()
        session_id = int(data.get('session_id', 0))
        if not session_id:
            return web.json_response({"error": "session_id required"}, status=400)
        if not session_manager:
            return web.json_response({"error": "session manager not initialized"}, status=503)
        if not api_client:
            return web.json_response({"error": "API client not configured"}, status=503)
        ...
```

---

### WR-04: Config Form — `getDolGlobalString` Output Unescaped in HTML Attribute

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:262`
**Issue:** The config form renders the stored price directly into an HTML attribute:
```php
value="'.getDolGlobalString('WALLBOXBILLING_DEFAULT_PRICE').'"
```
`getDolGlobalString` returns the raw database value without HTML escaping. If the stored value contains `"` or `>` (e.g., from a previous malformed save or injected value), the HTML attribute is broken and creates a stored XSS vector in the admin panel. All dynamic values placed into HTML attributes must be escaped.

**Fix:**
```php
value="'.htmlspecialchars(getDolGlobalString('WALLBOXBILLING_DEFAULT_PRICE'), ENT_QUOTES, 'UTF-8').'"
```

---

### WR-05: Async Fixture `health_app` Missing `asyncio` Mode Declaration — Will Not Execute

**File:** `Homeassistant/tests/conftest.py:47-63`
**Issue:** `health_app` is declared `async def` with `@pytest.fixture` but carries no `@pytest.mark.asyncio` marker and there is no `asyncio_mode = "auto"` in the project's pytest config. Without asyncio mode configured, `pytest-asyncio` will not drive the coroutine; the fixture will be collected as a plain function and any test consuming `health_app` will receive an unawaited coroutine object rather than the `web.Application` instance. The `pytest.skip()` inside the fixture body will never be reached if imports fail, so import errors will propagate as collection errors rather than skips.

**Fix:** Add `asyncio_mode = "auto"` to `pytest.ini` or `pyproject.toml`, or annotate the fixture:
```python
import pytest_asyncio

@pytest_asyncio.fixture
async def health_app():
    ...
```

---

## Info

### IN-01: `init()` and `install()` Duplicate Identical Schema SQL — MySQL Does Not Support `CREATE INDEX IF NOT EXISTS`

**File:** `Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php:176-179,250-253`
**Issue:** The full table DDL and index creation SQL appears verbatim in both `init()` and `install()` (approximately 60 lines duplicated). Standard MySQL and MariaDB prior to 10.1.4 do not support `IF NOT EXISTS` in `CREATE INDEX` statements — this syntax is a MySQL 8.0+ feature that is absent from many Dolibarr-compatible environments and will produce a fatal SQL error on older installs. The index creation loop silently swallows these errors, so the indexes are never created and no administrator is notified.

**Fix:** Use `SHOW INDEX FROM llx_wallbox_sessions WHERE Key_name = 'idx_...'` guards around each `CREATE INDEX`, matching the pattern already used for `ALTER TABLE` column additions in `install()`. Consolidate the duplicated DDL into a private helper.

---

### IN-02: `periodic_transmission` Task Reference Is Unreachable in `finally` Block — Not Cancelled on Shutdown

**File:** `Homeassistant/main.py:405`
**Issue:** `transmission_task = asyncio.create_task(periodic_transmission())` stores the task in a local variable inside the `try` block. The `finally` block does not reference `transmission_task`, so on shutdown (KeyboardInterrupt or exception) the task is abandoned without cancellation. Python's asyncio will log `Task was destroyed but it is pending` for each abandoned task. In production this is a noisy warning; in tests it can cause false test failures.

**Fix:**
```python
transmission_task = None
if api_client:
    transmission_task = asyncio.create_task(periodic_transmission())

# In finally block:
finally:
    if transmission_task and not transmission_task.done():
        transmission_task.cancel()
    if health_runner:
        await health_runner.cleanup()
    await ha_ws.disconnect()
```

---

_Reviewed: 2026-06-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
