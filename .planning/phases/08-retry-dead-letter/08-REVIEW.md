---
phase: 08-retry-dead-letter
reviewed: 2026-06-23T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - Homeassistant/main.py
  - Homeassistant/session_manager.py
  - Homeassistant/tests/test_dead_letter.py
  - Dolibarr/htdocs/custom/wallboxbilling/admin.php
  - Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang
findings:
  critical: 4
  warning: 7
  info: 0
  total: 11
status: fixed
fixed_at: 2026-06-23T00:00:00Z
fixed_critical: 4
fixed_warning: 7
fixed_info: 3
---

# Phase 08: Code Review Report

**Reviewed:** 2026-06-23T00:00:00Z
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

This phase adds the dead-letter queue (RET-01), admin-triggered manual retry endpoint (RET-02), and automatic periodic retry loop (RET-03) to the Wallbox-Dolibarr integration. The core retry mechanics in `session_manager.py` are structurally sound. However, four blocker-level defects exist: two CSRF-protection gaps in `admin.php`, a WebSocket protocol collision that causes `get_state` to silently return wrong data or deadlock, and a connection-leak in `transmit_completed_sessions` if an unhandled exception occurs before `conn.close()`. Several warnings cover a missing `transmission_task` cancellation on shutdown, hardcoded absolute paths in tests, duplicate constant definitions, and numerous untranslated UI strings.

---

## Critical Issues

### CR-01: CSRF token not checked for `update` and `update_rfid` actions

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:24-47`
**Issue:** The `stop_session` (line 51) and `retry_dead_letter` (line 85) actions both call `checkToken()`, but `update` (saves price/email config, line 24) and `update_rfid` (saves RFID data, line 33) do not. An attacker who can lure an authenticated admin to a malicious page can silently overwrite the Dolibarr API price or link arbitrary RFID hashes to user accounts via a cross-site POST.

**Fix:**
```php
// Action: Konfiguration speichern
if ($action == 'update') {
    checkToken();          // ADD THIS LINE
    $new_price = GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'alpha');
    ...
}

// Action: RFID speichern
if ($action == 'update_rfid') {
    checkToken();          // ADD THIS LINE
    $user_id = GETPOST('user_id', 'int');
    ...
}
```

---

### CR-02: `update_rfid` action computes RFID hash but never persists it

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:33-47`
**Issue:** The action handler computes `$rfid_hash` (line 42) and logs a success message, but never executes any `INSERT` or `UPDATE` on `llx_wallbox_rfid`. The hash is silently discarded. Every RFID save attempt shows "RFIDHashSaved" to the admin but stores nothing — the whitelist in Home Assistant is never updated. This is a complete data-loss bug for the RFID management feature.

**Fix:** Add a DB write after computing the hash:
```php
if ($user_id > 0 && !empty($rfid_hex)) {
    $rfid_hash = hash('sha256', $rfid_hex);
    // Persist or update the mapping
    $sql = "INSERT INTO ".MAIN_DB_PREFIX."wallbox_rfid (fk_user, rfid_hash, price_kwh, cost_center)";
    $sql .= " VALUES (".(int)$user_id.", '".$db->escape($rfid_hash)."',";
    $sql .= " '".$db->escape($price_kwh)."', '".$db->escape($cost_center)."')";
    $sql .= " ON DUPLICATE KEY UPDATE rfid_hash=VALUES(rfid_hash),";
    $sql .= "  price_kwh=VALUES(price_kwh), cost_center=VALUES(cost_center)";
    $db->query($sql);
    setEventMessages($langs->trans('RFIDHashSaved'), null, 'mesgs');
}
```

---

### CR-03: WebSocket message-ID collision causes `get_state` to return wrong data or deadlock

**File:** `Homeassistant/main.py:175-213`
**Issue:** `subscribe_entities()` sends message `id=1` and then enters an infinite `while True` loop calling `await self._ws.receive_json()`. Inside the callback that loop drives, `sensor_callback` calls `await ha_ws.get_state(SENSOR_ENERGY)` (lines 245, 278), which sends message `id=2` and then calls `await self._ws.receive_json()`. Because both coroutines share the same websocket object without any multiplexing, the result message for `id=2` will be consumed by the `subscribe_entities` loop instead of `get_state`, causing `get_state` to silently return `None` (or block forever waiting for a reply that will never arrive after the `subscribe_entities` loop discards it). This means `start_energy` and `end_energy` are always `0.0` — every session records zero kWh.

**Fix:** Keep a separate aiohttp `ClientSession` for REST `get_states` calls (use the HTTP REST API at `/api/states/<entity_id>` with the supervisor token instead of the websocket) or implement a proper message-ID queue/dispatcher that routes responses to the correct awaiting caller:
```python
async def get_state(self, entity_id: str) -> Optional[Dict[str, Any]]:
    """Use HA REST API to avoid websocket message-ID collision."""
    url = f"http://homeassistant:8123/api/states/{entity_id}"
    headers = {"Authorization": f"Bearer {self.access_token}"}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as resp:
            if resp.status == 200:
                return await resp.json()
    return None
```

---

### CR-04: SQLite connection leaked when exception occurs in `transmit_completed_sessions`

**File:** `Homeassistant/session_manager.py:443-507`
**Issue:** `conn` is opened at line 443, and `conn.close()` is called unconditionally at line 507 — but only if no exception is raised between those lines. If `api_client.transmit_session()` (line 474) raises an unhandled exception (e.g., an unexpected type from the API client, a network timeout that is not caught by the client), the function exits via exception and the connection is never closed. The same pattern exists in `retry_dead_letter_sessions` (lines 517-560): the outer `except Exception` on line 554 only covers per-row exceptions; a failure in the initial SELECT or commit would also leak the connection.

**Fix:** Wrap each database-using method body in `try/finally`:
```python
conn = sqlite3.connect(self.db_path)
cursor = conn.cursor()
try:
    # ... all existing logic ...
    conn.commit()
finally:
    conn.close()
```

---

## Warnings

### WR-01: `transmission_task` is never cancelled on shutdown

**File:** `Homeassistant/main.py:506-526`
**Issue:** `transmission_task = asyncio.create_task(periodic_transmission())` is created at line 507 but is not stored in a scope reachable by the `finally` block (lines 523-526). When the addon exits (normal or exception), the task is abandoned. Python will log "Task was destroyed but it is pending!" and any mid-flight DB write in the task may be interrupted without commit. The local variable `transmission_task` inside `main()` is also referenced only after the point of creation, not in the `finally` clause.

**Fix:**
```python
transmission_task = None
if api_client:
    transmission_task = asyncio.create_task(periodic_transmission())

try:
    health_runner = await start_health_server(port=8099)
    await ha_ws.subscribe_entities(sensor_callback)
finally:
    if transmission_task and not transmission_task.done():
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

### WR-02: `api_client` set to `None` inside `periodic_transmission` has no effect on the outer scope

**File:** `Homeassistant/main.py:488-491`
**Issue:** The comment at line 490 says "api_client auf None setzen deaktiviert weitere Versuche", but the code only reads the global `api_client` (line 488) — it never actually sets it to `None`. The `if not api_client.check_connection():` block just logs a warning and falls through. The TODO at line 491 reinforces this is known incomplete logic. As written, failed transmissions will retry every cycle without any backoff or disabling. This is a logic error, not just a missing feature.

**Fix:** Either add `global api_client` and set it to `None`, or implement a backoff counter. If disabling is the intent:
```python
global api_client
if not api_client.check_connection():
    _LOGGER.warning("API-Verbindung verloren - deaktiviere temporär")
    api_client = None
```

---

### WR-03: `transmit_completed_sessions` breaks on first failure — subsequent completed sessions accumulate silently

**File:** `Homeassistant/session_manager.py:503-504`
**Issue:** Line 504 `break`s out of the loop on the first failed transmission. The dead-letter retry loop (`retry_dead_letter_sessions`) correctly uses `continue`. The inconsistency means that if session A fails, sessions B, C, D (already in status `completed`) are never attempted in that cycle and stay in `completed` state. They will be picked up by the NEXT `transmit_completed_sessions` call, but since the comment says "Bei Fehler: Schleife abbrechen", this appears intentional — yet it contradicts the design of the dead-letter retry loop and means the HA notification "N Sessions failed" always reports at most 1. If the intent is "fail fast and let dead-letter handle retries," the SQL filter at line 452 already excludes sessions with `upload_status IN ('ok', 'dead_letter')`, so the break is redundant and harmful.

**Fix:** Replace `break` with `continue` to be consistent with `retry_dead_letter_sessions` and report accurate failure counts:
```python
                self._logger.warning("Session %s in Dead-letter Queue geschrieben (RET-01)", session_id)
                continue  # Process remaining sessions; don't break
```

---

### WR-04: Hardcoded absolute path `/home/roto` in test subprocess calls

**File:** `Homeassistant/tests/test_dead_letter.py:389,442`
**Issue:** Both subprocess-based tests pass `cwd='/home/roto'` as a hardcoded absolute path. These tests will fail on any CI machine, Docker container, or developer machine that is not `/home/roto`.

**Fix:**
```python
cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

---

### WR-05: `get_state` fetches ALL entity states on every call (full-state dump)

**File:** `Homeassistant/main.py:199-213`
**Issue:** `get_state()` sends `type: 'get_states'` (line 203), which returns the full state of every entity in Home Assistant. It then iterates through the entire list to find one entity (lines 209-212). This is wasteful and grows with the number of HA entities. More critically, combined with CR-03, the WS response for this message will be misrouted by the subscribe_entities loop. If CR-03 is fixed by switching to REST, this issue also resolves. If the WS approach is kept, `get_state` should use `type: 'call_service'` or a targeted `get_states` filter.

**Fix:** Use the REST API approach (see CR-03 fix) or use `type: 'get_states'` with an entity filter if available.

---

### WR-06: `handle_dead_letter_list` accesses `session_manager` global without null-check

**File:** `Homeassistant/main.py:393-400`
**Issue:** `handle_dead_letter_list` at line 396 calls `session_manager.get_pending_dead_letters()` but does not check whether `session_manager` is `None`. The global `session_manager` is initialized in `main()` (line 425), but if `start_health_server()` is ever called before `session_manager` is set (or if the HTTP server receives a request before initialization completes), this will raise `AttributeError: 'NoneType' object has no attribute 'get_pending_dead_letters'` and return HTTP 500 with the raw exception in the response body.

**Fix:**
```python
async def handle_dead_letter_list(request):
    if not session_manager:
        return web.json_response({"error": "not initialized"}, status=503)
    try:
        entries = session_manager.get_pending_dead_letters()
        return web.json_response(entries, status=200)
    except Exception as e:
        _LOGGER.error("dead-letter/list Fehler: %s", e)
        return web.json_response({"error": str(e)}, status=500)
```

---

### WR-07: Config tab renders stored values without HTML escaping

**File:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php:309,312`
**Issue:** Lines 309 and 312 output `getDolGlobalString('WALLBOXBILLING_DEFAULT_PRICE')` and `getDolGlobalString('WALLBOXBILLING_ADMIN_EMAIL')` directly into HTML `<input value="...">` attributes without `htmlspecialchars()`. If the stored value contains `"` or `>` (e.g., a price saved as `0.30"<script>`) it can break out of the attribute context. Dolibarr's `getDolGlobalString` does not escape for HTML output.

**Fix:**
```php
print '<td><input type="text" name="WALLBOXBILLING_DEFAULT_PRICE" value="'
    .htmlspecialchars(getDolGlobalString('WALLBOXBILLING_DEFAULT_PRICE'), ENT_QUOTES, 'UTF-8')
    .'"></td></tr>';
print '<td><input type="email" name="WALLBOXBILLING_ADMIN_EMAIL" value="'
    .htmlspecialchars(getDolGlobalString('WALLBOXBILLING_ADMIN_EMAIL'), ENT_QUOTES, 'UTF-8')
    .'" placeholder="admin@example.com"></td></tr>';
```

---

## Info

### IN-01: `CHARGING`, `IDLE`, `STOPPED` constants imported then immediately redefined

**File:** `Homeassistant/main.py:23,37-39`
**Issue:** Line 23 imports `CHARGING, IDLE, STOPPED` from `session_manager`, then lines 37-39 immediately redefine them with identical values. The imported names are shadowed and the import is a no-op. This is dead code and will cause confusion if the values ever diverge.

**Fix:** Remove lines 37-39 and keep only the imported constants. Alternatively, remove the import clause from line 23 if `main.py` defines them as the authoritative source.

---

### IN-02: `import yaml` is unused

**File:** `Homeassistant/main.py:15`
**Issue:** `yaml` is imported at line 15 but never referenced anywhere in the file. Config is loaded via `json.load` (line 59).

**Fix:** Remove line 15: `import yaml`

---

### IN-03: 25 lang keys used in `admin.php` are missing from `wallboxbilling.lang`

**File:** `Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang`
**Issue:** The following keys are called via `$langs->trans()` in `admin.php` but are absent from the German lang file. Dolibarr will fall back to the raw key string as the display value (e.g., `StopSessionFailed` shown as-is to the German-speaking admin):

`Action`, `APIStatus`, `CostCenter`, `DatabaseError`, `Date`, `Error`, `kWh`, `NoSessionsFound`, `NotConfigured`, `PricePerKWh`, `Reachable`, `RFIDHash`, `RFIDHashSaved`, `RFIDHex`, `Saved`, `StopSession`, `StopSessionFailed`, `StopSessionInvalidOrNoURL`, `StopSessionSuccess`, `Unknown`, `Unreachable`, `UploadStatus`, `User`, `WallboxID`, `WallboxStatus`, `WallboxUserRFIDManagement`

Note: Some of these (e.g., `Date`, `Error`, `Save`, `User`, `Unknown`) may be defined in Dolibarr core lang files and resolved at runtime. The module-specific ones (`StopSession*`, `RFIDHash*`, `WallboxID`, `WallboxStatus`, `WallboxUserRFIDManagement`, `UploadStatus`, `APIStatus`, `NoSessionsFound`) will definitely not resolve and will display as raw keys.

**Fix:** Add the missing module-specific keys to `wallboxbilling.lang`.

---

_Reviewed: 2026-06-23_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
