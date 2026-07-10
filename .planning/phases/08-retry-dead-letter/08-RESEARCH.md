# Phase 8: Retry & Dead-letter — Research

**Researched:** 2026-06-23
**Domain:** SQLite dead-letter queue, HA-Addon retry loop, Dolibarr admin tab extension, PHP AJAX/form retry trigger
**Confidence:** HIGH (all claims verified against actual codebase)

---

## Summary

Phase 8 adds a dead-letter queue so that failed session uploads are never silently lost. The fundamental architecture question — WHERE does the dead-letter table live? — resolves clearly to the HA-Addon's SQLite database (`/data/sessions.db`). The session data that needs to be retried already exists there (the `sessions` table has all payload fields). A separate `dead_letter` table in the same SQLite file is the minimal, zero-new-dependency approach. Dolibarr can then trigger retries by POSTing to a new HA-Addon HTTP endpoint, following the exact same pattern as the existing `/session/stop` endpoint in `main.py`.

**The current failure flow in `transmit_completed_sessions()` is:** on failure, the session gets `upload_status='error'` written back to SQLite and the loop breaks. The session is NOT retransmitted on the next periodic cycle because `transmit_completed_sessions()` only queries `WHERE end_time IS NOT NULL AND transmitted_at IS NULL` — sessions with `upload_status='error'` but no `transmitted_at` WILL be retried (the condition is correct!). The problem is that `upload_status='error'` and `transmitted_at=NULL` can coexist, which means the basic re-transmit is already partially functional. Phase 8 formalises this with an explicit dead-letter table and admin UI.

**Two-subsystem split (mirrors Phase 7 split):**
1. **HA-Addon (Python):** Add `dead_letter` table to `session_manager.py`, write to it on failure in `transmit_completed_sessions()`, add `/session/retry` HTTP endpoint in `main.py`, include dead-letter retry in `periodic_transmission()` loop.
2. **Dolibarr (PHP):** Add a 4th "Dead-letter" tab to `admin.php` that reads dead-letter entries via a new API endpoint or directly from the HA health endpoint, and presents a "Retry" button that POSTs to the HA-Addon `/session/retry` endpoint.

**Primary recommendation:** Dead-letter table in HA SQLite (`/data/sessions.db`). Admin UI as 4th tab in `admin.php`. Retry trigger via POST to HA-Addon `/session/retry`. Automatic retry integrated into the existing `periodic_transmission()` loop.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RET-01 | Fehlgeschlagene Session-Uploads werden in einer Dead-letter-Tabelle gespeichert | New `dead_letter` table in HA SQLite; written from `transmit_completed_sessions()` on failure; stores full payload + error + retry_count + status |
| RET-02 | Admin kann fehlgeschlagene Uploads manuell im Dolibarr-Admin neu anstoßen | New 4th tab "Dead-letter" in admin.php; cURL POST to HA-Addon `/session/retry` endpoint with `dead_letter_id`; follows existing `stop_session` pattern exactly |
| RET-03 | Automatischer Retry beim nächsten Übertragungszyklus für pending Dead-letter-Einträge | `periodic_transmission()` loop already calls `transmit_completed_sessions()` — extend it to also call a new `retry_dead_letter_sessions()` method; pending DL entries processed each cycle |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Dead-letter persistence (RET-01) | HA-Addon SQLite | — | Session payload already lives in HA SQLite; no data duplication; zero Dolibarr schema change |
| Manual retry trigger (RET-02) | Dolibarr admin.php | HA-Addon /session/retry | Dolibarr is the admin UI; HA Addon owns the retry execution |
| Automatic retry (RET-03) | HA-Addon periodic_transmission() | SessionManager | Retry must run on same interval cycle as original transmit; Dolibarr knows nothing about HA timing |
| Dead-letter read for UI | HA-Addon new /dead-letter/list endpoint | OR Dolibarr reads HA JSON | HA is authoritative source; Dolibarr polls it via cURL (same pattern as /health) |
| Retry success cleanup (RET-01 success branch) | HA-Addon SessionManager | — | Status update stays in HA SQLite |

---

## Key Architecture Question: WHERE Does the Dead-Letter Table Live?

### Option A: HA SQLite `/data/sessions.db` (RECOMMENDED)
**[VERIFIED: codebase — session_manager.py lines 64-123]**

- Session payload (rfid_hash, wallbox_id, start_time, end_time, total_kwh) is already in SQLite
- `SessionManager._init_database()` already runs `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations — dead_letter table creation follows exact same pattern
- No Dolibarr DB schema change needed
- Full data available at failure time: row from `sessions` table + error string from `api_client.transmit_session()` return tuple
- Admin UI reads via new HA HTTP endpoint (cURL, same as health ping) — no direct DB access from Dolibarr

### Option B: Dolibarr MySQL `llx_wallbox_dead_letter`
**NOT recommended:**
- Dolibarr only learns of failures AFTER the HA-Addon has already written `upload_status='error'` to its own SQLite
- Would require HA-Addon to POST a "failure record" to Dolibarr — adds a second API call that can also fail
- Circular dependency: dead-letter record creation itself needs a working Dolibarr API connection
- Dolibarr MySQL schema change in production requires proper `.sql` migration file + module version bump

**Decision:** Option A — HA SQLite.

---

## Current Error Flow Analysis

**[VERIFIED: session_manager.py lines 411-479]**

`transmit_completed_sessions()` behavior on failure:
1. Queries `WHERE end_time IS NOT NULL AND transmitted_at IS NULL`
2. For each row, calls `api_client.transmit_session(session_data)`
3. On failure: writes `upload_status='error'`, `upload_error=error[:1000]` — **`transmitted_at` stays NULL**
4. Breaks the loop (no further sessions attempted)

**Critical observation:** Because `transmitted_at` stays NULL on failure, the NEXT call to `transmit_completed_sessions()` will pick up the same failed session again (it still matches `transmitted_at IS NULL`). This means **automatic retry is already happening** for the initial transmission path — but without limit and without dead-letter tracking. Phase 8 formalises this with explicit retry tracking.

**Data available at failure time:**
```python
session_id  = row[0]   # int
rfid_hash   = row[1]   # str (64-char hex SHA-256)
wallbox_id  = row[2]   # str
start_time  = row[3]   # str (ISO 8601)
end_time    = row[4]   # str (ISO 8601)
total_kwh   = row[5]   # float
error       = error    # str from api_client.transmit_session() Tuple[bool, str]
```

No additional data capture needed — all payload fields are already in the `sessions` row.

---

## Standard Stack

### Core (no new dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | stdlib | Dead-letter table in HA SQLite | Already used in SessionManager; no new install |
| Python logging | stdlib | Log retry attempts + outcomes | Already used throughout |
| aiohttp web | 3.14.1 [VERIFIED: env] | New /session/retry HTTP endpoint | Already used for /health and /session/stop |
| PHP cURL | system | Dolibarr admin retry trigger | Already used for /health ping and stop_session |
| pytest | 7.4.4 [VERIFIED: env] | Tests | Existing test infrastructure |

**No new pip packages required.** [VERIFIED: requirements.txt exists, all libs already present]

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-asyncio | installed [VERIFIED: test_health.py uses async fixtures] | Async endpoint tests | /session/retry handler test |
| conftest.py fixtures | project | in_memory_session_manager, mock_api_client_* | Reuse for dead-letter tests |

**Installation:** None needed.

---

## Architecture Patterns

### System Architecture Diagram

```
periodic_transmission() [every 300s]
    |
    +-- transmit_completed_sessions(api_client)
    |       |-- success --> transmitted_at=NOW(), upload_status='ok'
    |       |-- failure --> upload_status='error', upload_error=msg
    |                       --> INSERT INTO dead_letter (session_id, payload_json, error_msg, retry_count=0, status='pending')
    |
    +-- retry_dead_letter_sessions(api_client)         [NEW]
            |-- SELECT * FROM dead_letter WHERE status='pending'
            |-- for each: api_client.transmit_session(payload)
            |       |-- success --> dead_letter.status='resolved', sessions.transmitted_at=NOW()
            |       |-- failure --> dead_letter.retry_count++, dead_letter.last_error=msg
            |

Dolibarr admin.php [Dead-letter tab]
    |
    +-- cURL GET WALLBOXBILLING_HA_URL/dead-letter/list
    |       --> renders table of pending dead_letter rows
    |
    +-- POST action=retry_dead_letter (form submit)
            --> cURL POST WALLBOXBILLING_HA_URL/session/retry {"dead_letter_id": N}
            --> HA-Addon: immediate single-entry retry, returns {success, transmitted, failed}
```

### Recommended Project Structure Changes

```
Homeassistant/
├── session_manager.py        # Add: dead_letter table init, write_dead_letter(), retry_dead_letter_sessions()
├── main.py                   # Add: handle_session_retry(), start_health_server() route, periodic retry call
└── tests/
    └── test_dead_letter.py   # New: TDD tests for RET-01, RET-02, RET-03

Dolibarr/htdocs/custom/wallboxbilling/
├── admin.php                 # Add: 4th tab 'deadletter', action=retry_dead_letter handler
└── sql/upgrade/
    └── (no new SQL needed — dead-letter lives in HA SQLite)
```

### Pattern 1: Dead-letter Table Schema (HA SQLite)

**What:** New table `dead_letter` in `/data/sessions.db`, created alongside `sessions` table in `_init_database()`.

**Schema:**
```sql
CREATE TABLE IF NOT EXISTS dead_letter (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,          -- FK to sessions.id
    rfid_hash TEXT NOT NULL,              -- Copied from sessions (payload for retry)
    wallbox_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    total_kwh REAL NOT NULL,
    error_msg TEXT,                       -- Last error from api_client
    retry_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'resolved' | 'abandoned'
    created_at TEXT NOT NULL,
    last_retry_at TEXT
);
```

**Why copy payload fields:** Allows retry without re-querying `sessions` table; self-contained record for the dead-letter log.

**Status lifecycle:** `pending` → `resolved` (success) or stays `pending` with `retry_count++` on failure.

### Pattern 2: write_dead_letter() in SessionManager

**What:** Called from `transmit_completed_sessions()` immediately after writing `upload_status='error'`.

```python
# Source: codebase pattern from transmit_completed_sessions()
def write_dead_letter(self, conn, session_row: tuple, error_msg: str) -> int:
    """Write failed session to dead_letter table. Uses existing conn to stay in same transaction."""
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR IGNORE INTO dead_letter
        (session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh,
         error_msg, retry_count, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'pending', ?)
    ''', (
        session_row[0],  # session_id
        session_row[1],  # rfid_hash
        session_row[2],  # wallbox_id
        session_row[3],  # start_time
        session_row[4],  # end_time
        session_row[5] or 0.0,  # total_kwh
        error_msg[:1000] if error_msg else 'Unknown error',
        datetime.now().isoformat()
    ))
    return cursor.lastrowid
```

**OR IGNORE:** Prevents duplicate dead_letter rows if `transmit_completed_sessions()` is called repeatedly for the same failed session. Alternatively, add `UNIQUE(session_id)` constraint.

### Pattern 3: /session/retry Endpoint in main.py

**What:** New POST endpoint on the existing aiohttp server (port 8099), following the `handle_session_stop` pattern exactly.

```python
# Source: codebase pattern from handle_session_stop() in main.py
async def handle_session_retry(request):
    """POST /session/retry — Admin-triggered retry of a dead-letter entry (RET-02)"""
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
```

Registered in `start_health_server()`:
```python
app.router.add_post('/session/retry', handle_session_retry)
```

### Pattern 4: /dead-letter/list Endpoint

**What:** New GET endpoint returning JSON list of pending dead-letter entries. Used by Dolibarr admin tab to render the table.

```python
async def handle_dead_letter_list(request):
    """GET /dead-letter/list — Returns pending dead-letter entries as JSON (RET-02 display)"""
    entries = session_manager.get_pending_dead_letters()
    return web.json_response(entries, status=200)
```

Registered:
```python
app.router.add_get('/dead-letter/list', handle_dead_letter_list)
```

**Alternative:** Dolibarr queries its own `llx_wallbox_sessions` for `upload_status='error'` (it already has this data from Phase 6). This avoids a new endpoint. However, that data reflects the last transmission attempt — not the dead-letter queue status after retries. The dedicated endpoint is cleaner.

### Pattern 5: 4th Tab in admin.php

**What:** Add `deadletter` tab following exact same pattern as existing three tabs.

```php
// Add to $head array (after existing $h++ for rfid tab):
$head[$h][0] = $_SERVER['PHP_SELF'].'?tab=deadletter';
$head[$h][1] = $langs->trans('WallboxDeadLetter');  // new lang key
$head[$h][2] = 'deadletter';
$h++;
```

**Action handler** (before HTML, following stop_session pattern):
```php
if ($action == 'retry_dead_letter') {
    checkToken();
    $dead_letter_id = GETPOST('dead_letter_id', 'int');
    $ha_url = getDolGlobalString('WALLBOXBILLING_HA_URL', '');

    if ($dead_letter_id > 0 && !empty($ha_url)) {
        $ch = curl_init($ha_url . '/session/retry');
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode(array('dead_letter_id' => (int)$dead_letter_id)));
        curl_setopt($ch, CURLOPT_HTTPHEADER, array('Content-Type: application/json'));
        curl_setopt($ch, CURLOPT_TIMEOUT, 4);
        curl_setopt($ch, CURLOPT_CONNECTTIMEOUT, 4);
        $response = curl_exec($ch);
        $http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        // ... setEventMessages based on http_code
    }
    header('Location: '.$_SERVER['PHP_SELF'].'?tab=deadletter');
    exit;
}
```

**Tab content:** cURL GET to `/dead-letter/list`, JSON decode, render table with columns: created_at, wallbox_id, kwh, error_msg, retry_count, [Retry button].

### Anti-Patterns to Avoid

- **Do NOT set `transmitted_at` when writing to dead_letter.** The session stays `transmitted_at IS NULL` so it is excluded from normal transmit loop only after successful retry sets it. Wait — this causes the session to be retried by BOTH the regular transmit loop AND the dead-letter retry loop. **Resolution:** After writing to dead_letter, set `upload_status='dead_letter'` on the session to exclude it from `transmit_completed_sessions()`. Or: change the query to also exclude `upload_status='dead_letter'`.

- **Do NOT build a custom retry queue from scratch** — the existing SQLite + aiohttp HTTP server + cURL patterns cover all retry queue needs.

- **Do NOT add the dead-letter to Dolibarr's MySQL** — the HA Addon cannot reliably write to Dolibarr when the API is failing.

- **Do NOT skip `checkToken()` in the retry action handler** in admin.php — every POST action in admin.php uses `checkToken()` + `newToken()` (CSRF pattern established in Phase 6).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry queue storage | Custom file-based queue, Redis | SQLite dead_letter table | SQLite already in place, WAL mode, no new deps |
| HTTP retry endpoint | New aiohttp server on different port | Add route to existing server on port 8099 | Same pattern as /session/stop |
| Dead-letter display in Dolibarr | Build a native Dolibarr module page | 4th tab in existing admin.php | Tab system already in place, three tabs working |
| Retry scheduling | cron job, separate process | Extend existing periodic_transmission() loop | Already runs every 300s, no new orchestration |

---

## Common Pitfalls

### Pitfall 1: Double-Retry Race Condition
**What goes wrong:** `transmit_completed_sessions()` picks up sessions with `transmitted_at IS NULL` AND `upload_status='error'` — those sessions are ALREADY in the dead-letter table, causing both the regular loop and the dead-letter retry loop to attempt them simultaneously.

**Why it happens:** The existing query `WHERE end_time IS NOT NULL AND transmitted_at IS NULL` does not filter by `upload_status`.

**How to avoid:** After writing a session to `dead_letter`, update `sessions.upload_status = 'dead_letter'` in the SAME transaction. Change `transmit_completed_sessions()` query to `WHERE end_time IS NOT NULL AND transmitted_at IS NULL AND (upload_status IS NULL OR upload_status NOT IN ('ok', 'dead_letter'))`.

**Warning signs:** `result["transmitted"]` count double-counts sessions; dead-letter entry shows `retry_count > 0` even without admin action.

### Pitfall 2: Dead-letter Entry Created Repeatedly on Each Cycle
**What goes wrong:** Each `periodic_transmission()` cycle writes a new dead-letter row for the same failed session.

**Why it happens:** If the INSERT uses no UNIQUE constraint, every failed attempt creates a new row.

**How to avoid:** Add `UNIQUE(session_id)` to the `dead_letter` table schema. Use `INSERT OR IGNORE INTO dead_letter` when writing. Use `INSERT OR REPLACE` only if you want to update the error message.

**Warning signs:** `dead_letter` table grows unboundedly; retry_count resets to 0 unexpectedly.

### Pitfall 3: retry_count Never Increments
**What goes wrong:** Dead-letter entries stay `retry_count=0` forever even after automatic retries.

**Why it happens:** `retry_dead_letter_sessions()` uses INSERT OR REPLACE instead of UPDATE.

**How to avoid:** On retry failure: `UPDATE dead_letter SET retry_count = retry_count + 1, last_error = ?, last_retry_at = ? WHERE id = ?`.

### Pitfall 4: Admin Tab Shows Stale Data After Retry
**What goes wrong:** After clicking "Retry" and succeeding, the dead-letter tab still shows the entry.

**Why it happens:** The tab is a cURL GET — it shows data at page load time. The POST/redirect cycle handles this, but only if the redirect goes back to `?tab=deadletter`.

**How to avoid:** Same `header('Location: ...'.$_SERVER['PHP_SELF'].'?tab=deadletter'); exit;` pattern used in `stop_session`. This forces a fresh page load.

### Pitfall 5: /dead-letter/list Endpoint Not Secured
**What goes wrong:** Any caller who knows the HA URL can read session metadata (wallbox_id, timing, retry errors).

**Why it happens:** HA Addon HTTP endpoints currently have no authentication (same as /health, /session/stop).

**How to avoid:** Consistent with existing endpoints — no auth on HA-side (all calls come from Dolibarr admin which is already auth-gated by `wallboxbilling.admin` right). The admin permission check in admin.php already acts as the auth gate. Document this in threat model.

---

## Code Examples

### Example: _init_database() extension for dead_letter table

```python
# Source: session_manager.py _init_database() pattern (lines 64-123)
# Add after existing upload_status ALTER TABLE block:
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

### Example: Integration into transmit_completed_sessions() failure branch

```python
# Source: session_manager.py lines 459-471 (failure branch)
# BEFORE (current):
cursor.execute(
    'UPDATE sessions SET upload_status = ?, upload_error = ? WHERE id = ?',
    ('error', error[:1000] if error else 'Unknown error', session_id)
)

# AFTER (Phase 8):
cursor.execute(
    'UPDATE sessions SET upload_status = ?, upload_error = ? WHERE id = ?',
    ('dead_letter', error[:1000] if error else 'Unknown error', session_id)
)
# Write to dead_letter (UNIQUE(session_id) prevents duplicates)
cursor.execute('''
    INSERT OR IGNORE INTO dead_letter
    (session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh,
     error_msg, retry_count, status, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'pending', ?)
''', (session_id, row[1], row[2], row[3], row[4],
      row[5] or 0.0, error[:1000] if error else 'Unknown error',
      datetime.now().isoformat()))
```

### Example: retry_dead_letter_sessions() in SessionManager

```python
# Source: pattern from transmit_completed_sessions() lines 411-479
def retry_dead_letter_sessions(self, api_client: Any) -> Dict[str, Any]:
    """Retry all pending dead-letter entries. Called from periodic_transmission()."""
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, session_id, rfid_hash, wallbox_id, start_time, end_time, total_kwh "
        "FROM dead_letter WHERE status = 'pending'"
    )
    rows = cursor.fetchall()
    result = {"retried": 0, "resolved": 0, "still_failed": 0, "errors": []}

    for row in rows:
        dl_id, session_id = row[0], row[1]
        session_data = {
            "rfid_hash": row[2], "wallbox_id": row[3],
            "start_time": row[4], "end_time": row[5],
            "kwh": row[6] or 0.0
        }
        success, error = api_client.transmit_session(session_data)
        result["retried"] += 1
        if success:
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
            cursor.execute(
                "UPDATE dead_letter SET retry_count=retry_count+1, error_msg=?, last_retry_at=? WHERE id=?",
                (error[:1000] if error else 'Unknown error', datetime.now().isoformat(), dl_id)
            )
            result["still_failed"] += 1

    conn.commit()
    conn.close()
    return result
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sessions with `upload_status='error'` implicitly retried | Explicit dead_letter table with status lifecycle | Phase 8 | Admin visibility; retry_count tracking; no duplicate retries |
| 3-tab admin.php | 4-tab admin.php + deadletter | Phase 8 | Admin can see and action failed uploads |
| periodic_transmission only transmits new sessions | periodic_transmission + retry_dead_letter | Phase 8 | RET-03 automatic retry |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `WALLBOXBILLING_HA_URL` is already stored as a Dolibarr constant and accessible in admin.php via `getDolGlobalString()` | Architecture Patterns / Tab 4 | [VERIFIED: admin.php line 53 — used in stop_session action] — Not an assumption |
| A2 | The existing aiohttp server on port 8099 can accept new routes without restart (routes added at startup) | Pattern 3 | [VERIFIED: main.py start_health_server() lines 368-377 — routes added in app.router before runner.setup()] — New routes require code change + addon restart; this is expected behavior |
| A3 | `UNIQUE(session_id)` constraint is sufficient to prevent duplicate dead-letter rows | Dead-letter schema | [ASSUMED] — One session can fail multiple times in theory (across addon restarts). The UNIQUE constraint ensures one dead-letter record per session_id. If session_id is reused (it's AUTOINCREMENT, so it won't be), this assumption holds. LOW risk. |

**If this table is empty of real assumptions:** Claims A1 and A2 were verified during research. Only A3 is a design choice, not a factual assumption.

---

## Open Questions

1. **Should resolved dead-letter entries be deleted or archived?**
   - What we know: No explicit requirement. RET-01 says "als erledigt markiert und erscheint nicht mehr in der Fehlerliste".
   - What's unclear: Whether `status='resolved'` with display filter is sufficient, or if entries should be physically deleted.
   - Recommendation: Keep with `status='resolved'` — soft delete. Simpler, auditable. Filter `WHERE status='pending'` in all queries.

2. **Maximum retry_count before abandoning?**
   - What we know: RET-03 says "automatisch erneut versucht" — no explicit limit.
   - What's unclear: Should retries be capped (e.g., after 10 attempts, mark as `abandoned`)?
   - Recommendation: No cap for v1.1 — keep retrying. Admin can see retry_count in the UI and manually decide. Adding cap in Phase 9 if needed.

3. **What happens if the HA Addon is unreachable when admin clicks Retry?**
   - What we know: The cURL call will fail (timeout). The existing `stop_session` pattern handles this with `setEventMessages(..., 'errors')`.
   - What's unclear: Nothing unclear — same error handling as `stop_session`.
   - Recommendation: Copy the stop_session error handling verbatim for the retry action.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | HA Addon | ✓ | 3.12.3 | — |
| sqlite3 | dead_letter table | ✓ | stdlib | — |
| aiohttp | /session/retry endpoint | ✓ | 3.14.1 | — |
| pytest | Test suite | ✓ | 7.4.4 | — |
| PHP cURL | admin.php retry trigger | [ASSUMED: present in Dolibarr env] | — | — |
| PHP CLI | Syntax check | ✗ | — | Manual syntax review (same as Phase 7) |

**Missing dependencies with no fallback:** None blocking.

**Missing dependencies with fallback:** PHP CLI not available on this machine — PHP syntax validation must be done via careful manual review (established precedent from Phase 7).

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.4.4 |
| Config file | none — runs via `python3 -m pytest Homeassistant/tests/` |
| Quick run command | `python3 -m pytest Homeassistant/tests/test_dead_letter.py -x -q` |
| Full suite command | `python3 -m pytest Homeassistant/tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RET-01 | Failed session written to dead_letter with correct fields | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestDeadLetterWrite -x` | ❌ Wave 0 |
| RET-01 | UNIQUE(session_id) prevents duplicate dead_letter rows | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestDeadLetterDuplicatePrevention -x` | ❌ Wave 0 |
| RET-01 | sessions.upload_status set to 'dead_letter' after failure | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestSessionStatusAfterFailure -x` | ❌ Wave 0 |
| RET-03 | retry_dead_letter_sessions() resolves pending entries on success | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestRetryResolution -x` | ❌ Wave 0 |
| RET-03 | retry_count increments on repeated failure | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestRetryCountIncrement -x` | ❌ Wave 0 |
| RET-03 | sessions.transmitted_at set after successful retry | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestSessionTransmittedAtAfterRetry -x` | ❌ Wave 0 |
| RET-02 | /session/retry returns 400 when dead_letter_id missing | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestRetryEndpoint -x` | ❌ Wave 0 |
| RET-02 | /session/retry returns 503 when api_client None | unit | `python3 -m pytest Homeassistant/tests/test_dead_letter.py::TestRetryEndpoint -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest Homeassistant/tests/test_dead_letter.py -x -q`
- **Per wave merge:** `python3 -m pytest Homeassistant/tests/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `Homeassistant/tests/test_dead_letter.py` — covers RET-01, RET-02, RET-03
- Existing `conftest.py` fixtures (`in_memory_session_manager`, `mock_api_client_success`, `mock_api_client_failure`) are directly reusable — no new conftest needed.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | — (HA endpoints rely on network isolation + admin.php auth gate) |
| V3 Session Management | no | — |
| V4 Access Control | yes | `wallboxbilling.admin` right check at top of admin.php (existing pattern) |
| V5 Input Validation | yes | `GETPOST('dead_letter_id', 'int')` in admin.php; `int(data.get(..., 0))` in HA endpoint |
| V6 Cryptography | no | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| dead_letter_id tampering (admin POST) | Tampering | `GETPOST('dead_letter_id', 'int')` integer coercion; 0 rejected (existing pattern from stop_session) |
| CSRF on retry form | Tampering | `checkToken()` + `newToken()` in all POST forms (existing CSRF pattern from Phase 6) |
| Dead-letter list disclosure | Info Disclosure | `/dead-letter/list` only called from admin.php which requires `wallboxbilling.admin` right |
| XSS in error_msg display | Tampering | `htmlspecialchars($obj->error_msg, ENT_QUOTES, 'UTF-8')` — same pattern as upload_error in Phase 6 |
| SSRF via cURL retry | Elevation | URL from admin config `WALLBOXBILLING_HA_URL` (not user input) — same as stop_session; existing T-06-11 mitigation applies |
| rfid_hash in dead_letter response | Info Disclosure | `/dead-letter/list` JSON must NOT include rfid_hash field — display wallbox_id, kwh, times, error_msg only |

---

## Sources

### Primary (HIGH confidence)
- `Homeassistant/session_manager.py` — verified: transmit_completed_sessions() failure flow, _init_database() migration pattern, all session table fields
- `Homeassistant/main.py` — verified: handle_session_stop() pattern, start_health_server() route registration, periodic_transmission() loop structure
- `Dolibarr/htdocs/custom/wallboxbilling/admin.php` — verified: 3-tab structure, stop_session action handler, cURL pattern, checkToken() usage
- `Homeassistant/tests/conftest.py` — verified: reusable fixtures in_memory_session_manager, mock_api_client_*
- `.planning/phases/07-alerts-logging/07-RESEARCH.md` — verified stack: aiohttp 3.14.1, pytest 7.4.4

### Secondary (MEDIUM confidence)
- Phase 6 06-03-SUMMARY.md — verified tab system patterns, CSRF tokens, htmlspecialchars usage
- Phase 7 07-03-SUMMARY.md — verified CMailFile pattern, dol_syslog integration

### Tertiary (LOW confidence)
- None — all claims sourced from codebase.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries; all tools verified in existing code
- Architecture: HIGH — dead-letter-in-SQLite pattern verified against existing _init_database() structure; endpoint pattern verified against handle_session_stop()
- Pitfalls: HIGH — double-retry pitfall derived from direct code inspection of transmit_completed_sessions() query logic

**Research date:** 2026-06-23
**Valid until:** 2026-07-23 (stable stack; no external API dependencies beyond existing ones)
