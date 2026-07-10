---
phase: 07-alerts-logging
reviewed: 2026-06-23T00:00:00Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - Homeassistant/main.py
  - Homeassistant/tests/test_alerts_logging.py
  - Homeassistant/tests/test_logging.py
  - Homeassistant/tests/test_log_scrubbing.py
  - Homeassistant/tests/test_alerts.py
  - Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php
  - Dolibarr/htdocs/custom/wallboxbilling/admin.php
findings:
  critical: 5
  warning: 6
  info: 3
  total: 14
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-06-23
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Phase 7 delivers log-level configuration (LOG-01), RFID log scrubbing (LOG-02), structured Dolibarr logging (LOG-03), HA persistent notifications on upload failure (ALT-01), and admin-email alerts on DB error (ALT-02). The new features themselves (apply_log_level_from_config, send_persistent_notification) are implemented correctly and the tests adequately verify the happy and error paths.

However the review surfaces five blockers: the admin RFID-save action is a silent no-op (data is never written to the database), the standalone PHP endpoint authenticates only by checking that the API key is non-empty (any non-empty string grants access), the WebSocket message ID is hard-coded to a fixed value making concurrent or sequential calls protocol-invalid, the asyncio background task is leaked on shutdown, and a TypeError/ValueError is possible in the RFID callback because energy state conversion is unguarded.

---

## Critical Issues

### CR-01: admin.php `update_rfid` never writes to the database — silent data loss

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:33-47`
**Issue:** The `update_rfid` action block computes `$rfid_hash` and logs it, then falls through without executing any INSERT or UPDATE statement. Every RFID save submitted by an admin silently discards the data. The table `llx_wallbox_rfid` is queried elsewhere (session lookup) but will always remain empty because this write path is missing.
**Fix:**
```php
if ($user_id > 0 && !empty($rfid_hex)) {
    $rfid_hash = hash('sha256', $rfid_hex);
    dol_syslog("Wallbox: Saving RFID hash for user_id=".$user_id." hash=".substr($rfid_hash, 0, 16)."...", LOG_INFO);

    // Check for existing entry
    $sql_check = "SELECT rowid FROM ".MAIN_DB_PREFIX."wallbox_rfid WHERE fk_user = ".(int)$user_id;
    $res = $db->query($sql_check);
    if ($res && $db->num_rows($res) > 0) {
        $obj = $db->fetch_object($res);
        $sql_write = "UPDATE ".MAIN_DB_PREFIX."wallbox_rfid SET rfid_hash = '".$db->escape($rfid_hash)."' WHERE rowid = ".(int)$obj->rowid;
    } else {
        $sql_write = "INSERT INTO ".MAIN_DB_PREFIX."wallbox_rfid (fk_user, rfid_hash) VALUES (".(int)$user_id.", '".$db->escape($rfid_hash)."')";
    }
    if (!$db->query($sql_write)) {
        setEventMessages($langs->trans('ErrorWritingRFID').': '.$db->lasterror(), null, 'errors');
    } else {
        setEventMessages($langs->trans('RFIDHashSaved'), null, 'mesgs');
    }
}
```

---

### CR-02: Standalone PHP endpoint authenticates any non-empty API key — authentication bypass

**File:** `Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php:265-270`
**Issue:** The standalone block (lines 265-270) reads the API key from the environment or request header and rejects it only if it is empty. It never validates the key against `llx_const` or any other Dolibarr credential store. An attacker who sends any non-empty string in the `DOLAPIKEY` header (e.g., `"x"`) will bypass authentication and can write arbitrary session records to the database.
**Fix:**
```php
// After extracting $api_key:
$sql_key = "SELECT value FROM ".MAIN_DB_PREFIX."const WHERE name = 'DOLAPIKEY' AND entity = ".(int)$conf->entity;
$res = $db->query($sql_key);
$row = $res ? $db->fetch_object($res) : null;
if (!$row || !hash_equals($row->value, $api_key)) {
    http_response_code(401);
    echo json_encode(array('error' => 'Invalid DOLAPIKEY'));
    exit;
}
```
Alternatively, remove the standalone block entirely and rely solely on the DolibarrApi framework which validates tokens correctly.

---

### CR-03: WebSocket message IDs are hard-coded constants — protocol violation under any sequential use

**File:** `Homeassistant/main.py:175,202`
**Issue:** `subscribe_entities` always sends `id: 1` and `get_state` always sends `id: 2`. The Home Assistant WebSocket protocol requires each request to have a unique, monotonically increasing integer ID within a connection. If `get_state` is called while a subscription is active (which it is — it is called from `sensor_callback` while `subscribe_entities` is running), HA will reject the duplicate ID or send the response to the wrong handler, causing silent data corruption or a hard crash from an unexpected message type.
**Fix:**
```python
class HomeAssistantWebsocket:
    def __init__(self, ...):
        ...
        self._msg_id = 0

    def _next_id(self) -> int:
        self._msg_id += 1
        return self._msg_id

# In subscribe_entities:
    msg_id = self._next_id()
    await self._ws.send_json({'id': msg_id, 'type': 'subscribe_events', ...})
    msg = await self._ws.receive_json()
    if msg.get('id') != msg_id or not msg.get('success'):
        raise RuntimeError(...)

# In get_state:
    msg_id = self._next_id()
    await self._ws.send_json({'id': msg_id, 'type': 'get_states'})
    msg = await self._ws.receive_json()
    if msg.get('id') != msg_id or msg.get('type') != 'result':
        ...
```
Note: `get_state` also needs a response-routing mechanism because `subscribe_entities` already owns the `receive_json` loop — the current architecture cannot multiplex responses correctly. A proper fix requires a dispatcher pattern (dict of pending futures keyed by msg_id).

---

### CR-04: `periodic_transmission` asyncio task is never cancelled — resource leak and silent suppression on shutdown

**File:** `Homeassistant/main.py:461-463`
**Issue:** `transmission_task = asyncio.create_task(periodic_transmission())` is a local variable in `main()`. When a `KeyboardInterrupt` or any other exception raises and the `finally` block runs, the task is never cancelled or awaited. The task continues executing in the background (until the event loop closes), and any exceptions it raises after `main()` returns are silently swallowed by asyncio's default "Task exception was never retrieved" mechanism — which only prints to stderr and does not propagate. Additionally, if the event loop closes before the task exits naturally, `asyncio.run()` forcibly cancels it without any cleanup.
**Fix:**
```python
transmission_task = asyncio.create_task(periodic_transmission())
try:
    health_runner = await start_health_server(port=8099)
    await ha_ws.subscribe_entities(sensor_callback)
finally:
    transmission_task.cancel()
    try:
        await transmission_task
    except asyncio.CancelledError:
        pass
    if health_runner:
        await health_runner.cleanup()
    await ha_ws.disconnect()
```

---

### CR-05: Unguarded `float()` conversion on energy sensor value in RFID callback — unhandled ValueError crashes session start

**File:** `Homeassistant/main.py:246`
**Issue:** In the RFID branch of `sensor_callback`, `start_energy = float(energy_state.get('state', 0))` is called without a try/except. If the HA energy sensor reports `'unavailable'`, `'unknown'`, or any non-numeric state string, this raises `ValueError`. In contrast, the energy sensor branch (line 258) correctly wraps the same conversion in `try/except (ValueError, TypeError)`. An unavailable energy sensor at RFID swipe time would crash the callback and leave the session in an inconsistent state.
**Fix:**
```python
try:
    start_energy = float(energy_state.get('state', 0)) if energy_state else 0.0
except (ValueError, TypeError):
    _LOGGER.warning("Ungültiger Energie-Startwert beim Session-Start: %s", energy_state)
    start_energy = 0.0
```

---

## Warnings

### WR-01: `CHARGING`, `IDLE`, `STOPPED` constants doubly defined — import shadowed by local re-definition

**File:** `Homeassistant/main.py:23,37-39`
**Issue:** Line 23 imports `CHARGING`, `IDLE`, `STOPPED` from `session_manager`. Lines 37-39 immediately redefine them with identical string values. The local definitions silently win and the imported names are discarded. If `session_manager` ever changes its constant values, `main.py` will silently use stale values. This is also dead import code.
**Fix:** Remove lines 37-39 and rely on the imported constants, or remove the import from line 23 if these are intentionally re-declared. The import on line 23 should use the `as` alias or the local redefinitions should be removed entirely.

---

### WR-02: `get_state` reads all HA states to find one entity — and discards the subscription event stream

**File:** `Homeassistant/main.py:199-213`
**Issue:** `get_state` sends `type: get_states` which returns the entire state of every entity in HA, then iterates to find one. Beyond the inefficiency (out of scope), the critical issue is that `get_state` calls `await self._ws.receive_json()` directly on the shared WebSocket connection while `subscribe_entities` is also iterating the same connection in its `while True` loop. These two concurrent `receive_json` calls on the same socket will race — whichever coroutine wins will consume the message intended for the other, causing the subscription loop or the get_state call to hang or process the wrong message.
**Fix:** The proper fix is the dispatcher pattern noted in CR-03. Until that is implemented, `get_state` must use a separate HTTP REST call (`GET /api/states/<entity_id>`) rather than the shared WebSocket connection.

---

### WR-03: `handle_session_stop` marks session incomplete unconditionally, ignoring actual session state

**File:** `Homeassistant/main.py:354`
**Issue:** `session_manager.mark_session_incomplete(session_id, reason='admin_stop')` is called unconditionally before `transmit_completed_sessions`. If the session is already completed and uploaded (`upload_status='ok'`), this will retroactively corrupt it. If the session ID does not exist, the behavior depends on `SessionManager` internals (silent no-op or error). The intent from comments (D-14, D-15) is to stop an active/pending session — the code should first verify the session exists and is in a stoppable state.
**Fix:**
```python
active = session_manager.get_session_by_id(session_id)
if not active:
    return web.json_response({"error": "session not found"}, status=404)
if active.get('status') not in ('active', 'pending'):
    return web.json_response({"error": "session not in stoppable state"}, status=409)
session_manager.mark_session_incomplete(session_id, reason='admin_stop')
```

---

### WR-04: `WALLBOXBILLING_DEFAULT_PRICE` saved with `'alpha'` GETPOST filter — corrupts numeric values

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:25`
**Issue:** `GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'alpha')` uses the `alpha` sanitization filter, which strips all non-alphabetic characters. A price value like `"0.30"` becomes `""` (empty string) after filtering because digits and dots are not alphabetic characters. The saved constant will always be an empty string, breaking price calculation everywhere this constant is read.
**Fix:**
```php
$new_price = GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'num');
// 'num' allows digits and decimal separator
// Alternatively validate manually:
// $new_price = price2num(GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'alpha'));
```

---

### WR-05: Runtime schema detection via `SELECT transmitted_at LIMIT 1` silently swallows DB errors

**File:** `Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php:128-131`
**Issue:** The code runs a probe query to detect whether the `transmitted_at` column exists by checking if the query fails. Any DB error unrelated to the missing column (permissions, connection loss, table lock) is incorrectly interpreted as "column doesn't exist" and the fallback INSERT is used. This masks real database errors and could insert records into the wrong schema path silently.
**Fix:** Determine schema capabilities at module installation time, not at runtime per-request. Use a module constant or a stored configuration flag set during the SQL upgrade script execution. If runtime detection is truly needed, use `SHOW COLUMNS FROM ... LIKE 'transmitted_at'` with an explicit result check rather than relying on query failure.

---

### WR-06: `subscribe_entities` WebSocket loop has no error handling — any network error causes unhandled exception

**File:** `Homeassistant/main.py:189-197`
**Issue:** The `while True` loop calls `await self._ws.receive_json()` without catching `aiohttp.WSMessage` closed events, `asyncio.TimeoutError`, or `aiohttp.ClientConnectionError`. When the WebSocket connection drops (HA restart, network blip), `receive_json` raises an exception that propagates unhandled up to `main()` where it triggers the supervisor restart path. There is no reconnection logic, so every transient network error causes a full addon restart.
**Fix:** Add error handling in the loop and a reconnection strategy:
```python
while True:
    try:
        msg = await self._ws.receive_json()
    except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as e:
        _LOGGER.warning("WebSocket Verbindungsfehler: %s — reconnect...", e)
        break  # Exit loop; outer retry loop in main() handles reconnect
    if msg.get('type') == 'event':
        ...
```

---

## Info

### IN-01: Standalone PHP block in a class file executes on every include

**File:** `Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php:251-353`
**Issue:** The standalone endpoint block is guarded by `if (basename($_SERVER['SCRIPT_NAME']) === 'session.php')`, which is a fragile inclusion guard. This block runs (and evaluates the condition) every time the class file is included by other Dolibarr modules. If `$_SERVER['SCRIPT_NAME']` is absent (CLI, certain webserver configs) the condition is `basename('') === 'session.php'` which is false — safe but only by accident. The correct pattern is to put standalone endpoints in their own dedicated file, not mixed into a class definition file.
**Fix:** Move the standalone block to a separate file `api/session.php` (without a class definition) and remove it from this class file.

---

### IN-02: `test_notification_id_default_is_wallbox_upload_error` has a logically incorrect assertion

**File:** `Homeassistant/tests/test_alerts.py:67`
**Issue:** The assertion reads:
```python
assert 'notification_id.*wallbox_upload_error' or 'wallbox_upload_error' in content
```
Due to Python operator precedence, this evaluates as `assert ('notification_id.*wallbox_upload_error') or ('wallbox_upload_error' in content)`. The first operand is always truthy (non-empty string), so the assertion always passes regardless of whether `wallbox_upload_error` is present in `content`. The regex fragment `'notification_id.*wallbox_upload_error'` is never applied as a regex.
**Fix:**
```python
import re
assert re.search(r'notification_id.*wallbox_upload_error', content), \
    "wallbox_upload_error not found as default notification_id in main.py"
```

---

### IN-03: Magic number `0.30` hardcoded as price in SQL INSERT — inconsistent with configurable price

**File:** `Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php:151,169`
**Issue:** Both INSERT variants write `0.30` as `price_per_kwh`. This ignores the `WALLBOXBILLING_DEFAULT_PRICE` global constant, so sessions uploaded via the API always get the hardcoded price regardless of the admin-configured value. When the admin changes the price in configuration, historical sessions and new API-submitted sessions will still show 0.30.
**Fix:**
```php
$price_per_kwh = (float) getDolGlobalString('WALLBOXBILLING_DEFAULT_PRICE', '0.30');
// Then use $price_per_kwh in the INSERT instead of the literal 0.30
```

---

_Reviewed: 2026-06-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
