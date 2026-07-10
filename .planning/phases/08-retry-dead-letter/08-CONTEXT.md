# Phase 8: Retry & Dead-letter - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 8 adds a dead-letter queue so failed session uploads are never silently lost. Delivers:
1. A `dead_letter` table in HA SQLite (`/data/sessions.db`) that captures every failed upload with payload + error + retry state
2. A 4th "Fehlgeschlagen" tab in Dolibarr `admin.php` that shows pending dead-letter entries and a per-row "Wiederholen" retry button
3. Automatic retry of pending dead-letter entries in the existing `periodic_transmission()` loop

Architecture is locked via RESEARCH.md. All three requirements (RET-01, RET-02, RET-03) map to a two-subsystem split: HA-Addon (Python) owns persistence and retry execution; Dolibarr (PHP) owns the admin trigger UI.

</domain>

<decisions>
## Implementation Decisions

### Auto-retry Isolation (RET-03)
- **D-01:** The automatic dead-letter retry loop (`retry_dead_letter_sessions()`) MUST continue to the next pending entry when one entry fails. It does NOT break/stop like the current `transmit_completed_sessions()`. Each dead-letter entry is independent — one stuck entry must not block others in the same cycle.

### Abandon Policy
- **D-02 (Claude's discretion):** No automatic abandoning in Phase 8. Entries stay `pending` until resolved. The `abandoned` status defined in the schema is available for future phases but is not used here. Automatic retry continues each cycle for all `WHERE status='pending'` entries. `retry_count` increments on each failure for visibility only.

### Admin Retry Feedback (RET-02)
- **D-03 (Claude's discretion):** After clicking "Wiederholen", the PHP handler POSTs to the HA-Addon `/session/retry`, then redirects back to `?tab=deadletter` with a Dolibarr flash message via `dol_htmloutput_mesg()` — success: "Retry erfolgreich" (green), failure: "Retry fehlgeschlagen: {error}" (red). Follows the POST→redirect→flash pattern of the `stop_session` action in admin.php.

### Security
- **D-04 (locked from Phase 6):** `rfid_hash` is NEVER printed, logged, or included in any output. Dead-letter UI shows only `created_at`, `wallbox_id`, `total_kwh`, `error_msg`, `retry_count` — consistent with SEC-01/02.

### CSRF
- **D-05 (locked from Phase 6):** Every retry form includes `newToken()` hidden field. No exceptions.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### HA-Addon — Python patterns to replicate
- `Homeassistant/session_manager.py` — `_init_database()` (dead_letter table creation follows same ALTER TABLE pattern), `transmit_completed_sessions()` (lines 411-479, failure flow that triggers dead_letter write), `SessionManager` class structure
- `Homeassistant/main.py` — `handle_session_stop()` / `app.router.add_post('/session/stop', ...)` — exact pattern for new `/session/retry` endpoint registration
- `Homeassistant/api_client.py` — `transmit_session()` return signature `Tuple[bool, str]` used in retry logic

### Dolibarr — PHP patterns to replicate
- `Dolibarr/htdocs/custom/wallboxbilling/admin.php` — tab definition array (lines 95-108), `dol_get_fiche_head()` call, `stop_session` POST handler (lines 226-233, verbatim retry button pattern), cURL `/health` ping pattern for `/session/retry` call

### Phase planning artifacts
- `.planning/phases/08-retry-dead-letter/08-RESEARCH.md` — full architecture, schema, code patterns, pitfalls
- `.planning/phases/08-retry-dead-letter/08-UI-SPEC.md` — dead-letter tab design contract (column spec, status badge colors, button class)

### Tests
- `Homeassistant/tests/conftest.py` — `in_memory_session_manager`, `mock_api_client_*` fixtures for reuse in `test_dead_letter.py`
- `Homeassistant/tests/test_health.py` — async endpoint test pattern (pytest-asyncio)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SessionManager._init_database()`: Add `dead_letter` CREATE TABLE statement here — same `IF NOT EXISTS` pattern, same connection
- `conftest.py` fixtures: `in_memory_session_manager` and `mock_api_client_success/failure` ready for dead-letter tests
- `handle_session_stop()` in `main.py`: Template for `handle_session_retry()` — same JSON body parsing, same error handling shape
- admin.php `stop_session` form (lines 226-233): Verbatim template for the per-row "Wiederholen" retry form

### Established Patterns
- **Loop isolation:** `retry_dead_letter_sessions()` uses try/except per entry with `continue` — NOT `break`. Key divergence from `transmit_completed_sessions()`.
- **UNIQUE(session_id):** Dead-letter table must include this constraint + `INSERT OR IGNORE` to prevent duplicate rows on repeated failures
- **Status update on retry failure:** `UPDATE dead_letter SET retry_count = retry_count + 1, last_error = ?, last_retry_at = ? WHERE id = ?` — do NOT use INSERT OR REPLACE (resets retry_count)
- **Dolibarr flash message:** `dol_htmloutput_mesg($langs->trans('WallboxRetrySuccess'), '', 'ok')` / `('error')` — standard pattern from Phase 6

### Integration Points
- `periodic_transmission()` in `main.py`: add `await session_manager.retry_dead_letter_sessions(api_client)` after existing `transmit_completed_sessions()` call
- `start_health_server()` in `main.py`: register `/session/retry` (POST) and `/dead-letter/list` (GET)
- admin.php `$h` tab index: new tab at index 3 (4th tab, 0-based)

</code_context>

<specifics>
## Specific Ideas

- Dead-letter tab label: "Fehlgeschlagen" (lang key `WallboxDeadLetter`)
- Only `WHERE status='pending'` entries shown — resolved entries disappear automatically
- Error message truncated to 80 chars in UI with `...` suffix
- `/dead-letter/list` GET endpoint returns JSON array — Dolibarr fetches via cURL same as `/health`
- No batch retry in Phase 8 — one "Wiederholen" button per row

</specifics>

<deferred>
## Deferred Ideas

- Automatic "abandoned" status after N retries — deferred; Phase 8 keeps all pending entries in retry rotation indefinitely
- Batch retry (select all → retry all) — out of scope for Phase 8
- Resolved dead-letter history view — entries disappear on resolution; history view is future

</deferred>

---

*Phase: 08-retry-dead-letter*
*Context gathered: 2026-06-23*
