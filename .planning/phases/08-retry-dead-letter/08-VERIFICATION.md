---
phase: 08-retry-dead-letter
verified: 2026-06-23T16:00:00Z
status: human_needed
score: 4/4
overrides_applied: 0
human_verification:
  - test: "Open admin.php ?tab=deadletter in Dolibarr browser. Verify 4th tab 'Fehlgeschlagen' is visible and loads the dead-letter table."
    expected: "Tab renders without PHP error. Empty-state message 'Keine fehlgeschlagenen Übertragungen vorhanden.' shown when no entries exist, or table with Retry buttons shown when entries exist."
    why_human: "Dolibarr is only accessible via web UI (no SSH/VPS) — cannot test PHP rendering programmatically."
  - test: "With a pending dead-letter entry present, click 'Wiederholen' button on a row. Observe flash message and redirect."
    expected: "Page redirects to ?tab=deadletter with either 'Übertragung erfolgreich wiederholt.' (success) or 'Wiederholen fehlgeschlagen: ...' (failure). Entry disappears from table on success."
    why_human: "End-to-end admin retry flow requires live Dolibarr + HA-Addon environment with real cURL connectivity."
---

# Phase 8: Retry & Dead-letter Verification Report

**Phase Goal:** Fehlgeschlagene Session-Uploads gehen nicht verloren und können vom Admin manuell oder automatisch wiederholt werden
**Verified:** 2026-06-23T16:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Fehlgeschlagene Session-Uploads werden in einer eigenen Datenbanktabelle (Dead-letter) persistiert — kein Datenverlust bei Fehler | VERIFIED | `CREATE TABLE IF NOT EXISTS dead_letter` in `_init_database()` with `UNIQUE(session_id)`. `transmit_completed_sessions()` failure branch writes `upload_status='dead_letter'` and executes `INSERT OR IGNORE INTO dead_letter`. Test `TestDeadLetterWrite::test_failed_session_written_to_dead_letter` PASSES. |
| 2 | Admin kann im Dolibarr-Admin-Tab einen einzelnen Dead-letter-Eintrag manuell zum Retry markieren und absenden | VERIFIED (code) / UNCERTAIN (UI runtime) | `retry_dead_letter` action handler in admin.php: `checkToken()`, `GETPOST('dead_letter_id', 'int')`, cURL POST to `/session/retry`, PRG redirect to `?tab=deadletter`. HA endpoint `handle_session_retry()` registered at `POST /session/retry`. 4th tab `deadletter` in tab array. Requires human verification for live execution. |
| 3 | Beim nächsten regulären Übertragungszyklus werden pending Dead-letter-Einträge automatisch erneut versucht | VERIFIED | `periodic_transmission()` in main.py calls `session_manager.retry_dead_letter_sessions(api_client)` after `transmit_completed_sessions()` on every cycle (lines 474, 494). `retry_dead_letter_sessions()` SELECT: `WHERE status = 'pending'`, uses `continue` per D-01. Test `TestRetryCountIncrement` PASSES. |
| 4 | Nach erfolgreichem Retry wird der Dead-letter-Eintrag als erledigt markiert und erscheint nicht mehr in der Fehlerliste | VERIFIED | `retry_dead_letter_sessions()` sets `dead_letter.status='resolved'` and updates `sessions.transmitted_at=NOW, upload_status='ok'` on success. `get_pending_dead_letters()` SELECT: `WHERE status = 'pending'` — resolved entries excluded. Tests `TestRetryResolution` and `TestSessionTransmittedAtAfterRetry` PASS. |

**Score:** 4/4 truths verified (Truth 2 code-verified; runtime requires human confirmation)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Homeassistant/tests/test_dead_letter.py` | TDD test scaffold 8 classes, 9 functions | VERIFIED | 8 classes, 9 test functions. All 9 PASS GREEN. RET-01, RET-02, RET-03 referenced. |
| `Homeassistant/session_manager.py` | dead_letter table, write/retry/list methods | VERIFIED | `CREATE TABLE IF NOT EXISTS dead_letter` with `UNIQUE(session_id)`, index `idx_dead_letter_status`. Methods: `retry_dead_letter_sessions()`, `retry_single_dead_letter()`, `get_pending_dead_letters()`. Failure branch updated. |
| `Homeassistant/main.py` | /session/retry and /dead-letter/list endpoints + periodic retry | VERIFIED | `handle_session_retry()` and `handle_dead_letter_list()` defined. Both routes registered in `start_health_server()`. `retry_dead_letter_sessions()` called in `periodic_transmission()`. |
| `Dolibarr/htdocs/custom/wallboxbilling/admin.php` | 4th tab deadletter + action handler for retry_dead_letter | VERIFIED | `tab=deadletter` in head array (line 150-153). `retry_dead_letter` action handler (lines 84-121). deadletter tab content block (lines 389-465). |
| `Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang` | German lang keys for dead-letter UI | VERIFIED | 9 keys confirmed: WallboxDeadLetter, WallboxDeadLetterQueue, WallboxDeadLetterCreated, WallboxRetryCount, WallboxRetryAction, WallboxNoDeadLetterEntries, WallboxHAUnreachable, WallboxHANotConfigured, RetryDeadLetterSuccess, RetryDeadLetterFailed. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py periodic_transmission()` | `session_manager.retry_dead_letter_sessions()` | direct call after `transmit_completed_sessions()` | WIRED | Line 494: `retry_result = session_manager.retry_dead_letter_sessions(api_client)` |
| `main.py handle_session_retry()` | `session_manager.retry_single_dead_letter()` | POST /session/retry JSON body | WIRED | Line 380: `result = session_manager.retry_single_dead_letter(api_client, dead_letter_id)` |
| `main.py handle_dead_letter_list()` | `session_manager.get_pending_dead_letters()` | GET /dead-letter/list | WIRED | Line 396: `entries = session_manager.get_pending_dead_letters()` |
| `admin.php retry_dead_letter action` | HA-Addon /session/retry | cURL POST JSON {dead_letter_id: N} | WIRED | Lines 90-96: `curl_init($ha_url . '/session/retry')`, json_encode dead_letter_id |
| `admin.php deadletter tab content` | HA-Addon /dead-letter/list | cURL GET → json_decode | WIRED | Lines 399-406: `curl_init($ha_url . '/dead-letter/list')` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `admin.php deadletter tab` | `$dl_entries` | cURL GET /dead-letter/list → `get_pending_dead_letters()` → SQLite `dead_letter WHERE status='pending'` | Yes — real SQLite query | FLOWING |
| `handle_dead_letter_list()` | `entries` | `get_pending_dead_letters()` → SQLite SELECT | Yes — real SQLite query, rfid_hash excluded | FLOWING |
| `retry_dead_letter_sessions()` | `rows` | SQLite SELECT `dead_letter WHERE status='pending'` | Yes | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All 9 dead-letter tests pass GREEN | `python3 -m pytest Homeassistant/tests/test_dead_letter.py -v` | 9 passed in 1.64s | PASS |
| Full test suite passes (no regression) | `python3 -m pytest Homeassistant/tests/ -q` | 43 passed, 2 xfailed, 1 xpassed in 5.00s | PASS |
| dead_letter table created in schema | `grep -c "CREATE TABLE IF NOT EXISTS dead_letter" session_manager.py` | 1 | PASS |
| UNIQUE constraint present | `grep -c "UNIQUE(session_id)" session_manager.py` | 1 | PASS |
| transmit query excludes dead_letter sessions | `grep "upload_status NOT IN" session_manager.py \| grep -c "dead_letter"` | 1 | PASS |
| INSERT OR IGNORE prevents duplicates | `grep -c "INSERT OR IGNORE INTO dead_letter" session_manager.py` | 1 | PASS |
| /session/retry registered | `grep -c "add_post('/session/retry'" main.py` | 1 | PASS |
| /dead-letter/list registered | `grep -c "add_get('/dead-letter/list'" main.py` | 1 | PASS |
| admin.php 4th tab entry present | `grep -c "tab=deadletter" admin.php` | 3 | PASS |
| admin.php checkToken() called in retry handler | `grep -c "checkToken()" admin.php` | 2 | PASS |
| rfid_hash never printed in admin.php | `grep -v '^#' admin.php \| grep -c "print.*rfid_hash"` | 0 | PASS |
| XSS protection on error_msg | `grep -c "mb_substr.*error_msg\|err_raw\|err_display" admin.php` | 5 | PASS |
| rfid_hash excluded from get_pending_dead_letters SELECT | `sed -n '/def get_pending_dead_letters/,/return/p' session_manager.py \| grep "rfid_hash"` | 0 rows in SELECT | PASS |
| D-01 continue in retry loop | `grep "continue" session_manager.py \| grep -c "D-01\|do NOT break"` | 2 | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| RET-01 | 08-01, 08-02 | Fehlgeschlagene Session-Uploads werden in einer Dead-letter-Tabelle gespeichert | SATISFIED | dead_letter table in session_manager.py `_init_database()`, `INSERT OR IGNORE` in failure branch, `UNIQUE(session_id)` constraint. Tests TestDeadLetterWrite, TestDeadLetterDuplicatePrevention, TestSessionStatusAfterFailure all PASS. |
| RET-02 | 08-02, 08-03 | Admin kann fehlgeschlagene Uploads manuell im Dolibarr-Admin neu anstoßen | SATISFIED (code) | `handle_session_retry()` endpoint, `retry_single_dead_letter()` method, admin.php deadletter tab with per-row Wiederholen form, `retry_dead_letter` action handler with CSRF. TestRetryEndpoint PASSES. Human verification needed for live runtime. |
| RET-03 | 08-01, 08-02 | Automatischer Retry-Versuch beim nächsten Übertragungszyklus für pending Dead-letter-Einträge | SATISFIED | `periodic_transmission()` calls `retry_dead_letter_sessions()` after every transmit cycle. `continue` per D-01 (no break on per-entry failure). Tests TestRetryResolution, TestRetryCountIncrement, TestSessionTransmittedAtAfterRetry all PASS. |

Note: REQUIREMENTS.md traceability table still shows RET-01/02/03 as `Pending` — this is a documentation artifact only and does not affect implementation status.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `admin.php` | 252-255 | `upload_status == 'dead_letter'` not explicitly handled in status tab badge logic (falls through to orange `else` branch) | Info | Sessions with dead_letter status display as orange badge in status tab — correct indication that they need attention. Not a functional blocker. |

No stubs found. No TODO/FIXME/placeholder patterns found in implementation files. All methods are fully implemented with real SQLite operations.

### Human Verification Required

#### 1. Deadletter Tab Rendering in Dolibarr Browser

**Test:** Navigate to `admin.php?tab=deadletter` in the Dolibarr web UI. Confirm the 4th tab labeled "Fehlgeschlagen" is visible in the tab bar.
**Expected:** Tab renders without PHP error. When no dead-letter entries exist: shows empty-state row "Keine fehlgeschlagenen Übertragungen vorhanden." When entries exist: shows table with columns Erstellt, Wallbox-ID, kWh, Fehler, Versuche, Aktion and a "Wiederholen" button per row. When HA unreachable: shows error row in red.
**Why human:** Dolibarr is only accessible via web UI (project constraint: no SSH/VPS access). PHP rendering, Dolibarr tab system integration, and cURL /dead-letter/list connectivity cannot be tested programmatically.

#### 2. Manual Retry End-to-End Flow

**Test:** With a pending dead-letter entry in the HA-Addon SQLite database, click the "Wiederholen" button on that row in the Dolibarr deadletter tab.
**Expected:** POST is submitted with valid CSRF token. Page redirects to `?tab=deadletter`. Flash message shown: "Übertragung erfolgreich wiederholt." on success, or "Wiederholen fehlgeschlagen: ..." on API error. On success, the entry no longer appears in the table (status changed to 'resolved').
**Why human:** Requires live HA-Addon reachable from Dolibarr server with active /session/retry endpoint and SQLite write access — full integration test environment needed.

### Gaps Summary

No blocker gaps found. All 4 observable truths are verified by codebase evidence:

- RET-01 (persistence): dead_letter table, UNIQUE constraint, INSERT OR IGNORE, and upload_status='dead_letter' all present and test-proven.
- RET-02 (manual retry): complete implementation path from Dolibarr admin form → cURL POST → HA endpoint → SessionManager → SQLite. 2 human verification items remain for live runtime confirmation.
- RET-03 (auto retry): `periodic_transmission()` wires `retry_dead_letter_sessions()` correctly. D-01 continue behavior confirmed. Full test GREEN.
- Post-retry cleanup: `status='resolved'` set on success, excluded from future `get_pending_dead_letters()` queries. Tests PASS.

The only items requiring human action are live integration tests that cannot be executed in this environment per project constraints (Dolibarr web-UI-only access).

---

_Verified: 2026-06-23T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
