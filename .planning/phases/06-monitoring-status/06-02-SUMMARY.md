---
phase: "06-monitoring-status"
plan: "02"
subsystem: "homeassistant-addon"
tags: ["health-endpoint", "aiohttp", "apprunner", "sqlite", "upload-status", "monitoring"]
dependency_graph:
  requires: ["06-00"]
  provides: ["MON-01-health-endpoint", "upload_status-sqlite", "upload_error-sqlite"]
  affects: ["06-03-admin-status-tab"]
tech_stack:
  added: ["aiohttp AppRunner pattern", "aiohttp.web routes"]
  patterns: ["AppRunner + TCPSite (non-blocking)", "SQLite migration guard (ALTER TABLE + OperationalError catch)", "TDD RED/GREEN"]
key_files:
  created:
    - Homeassistant/tests/__init__.py
    - Homeassistant/tests/test_health.py
  modified:
    - Homeassistant/main.py
    - Homeassistant/session_manager.py
decisions:
  - "AppRunner + TCPSite used (not web.run_app()) — web.run_app() blocks asyncio event loop; AppRunner is non-blocking"
  - "api_client promoted to module-level global so handle_session_stop() can access it without threading hacks"
  - "upload_status values: 'pending'/'ok'/'error' — match D-09/D-10 spec for Plan 03 admin.php reads"
  - "error[:1000] truncation prevents unbounded SQLite TEXT on long error messages"
metrics:
  duration_minutes: 15
  completed_date: "2026-06-21"
  tasks_completed: 2
  files_modified: 4
  commits: 3
requirements_satisfied:
  - MON-01
---

# Phase 6 Plan 02: Health Endpoints + Upload Status Summary

aiohttp AppRunner-based /health and /session/stop endpoints with upload_status/upload_error SQLite writes after each transmission attempt.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| TDD RED | Failing tests for /health and /session/stop | 82da950 | tests/test_health.py, tests/__init__.py |
| 1 GREEN | /health GET + /session/stop POST via AppRunner | 34da703 | Homeassistant/main.py |
| 2 | upload_status + upload_error SQLite writes | d9539bb | Homeassistant/session_manager.py |

## What Was Built

### Task 1: main.py — HTTP Endpoints via aiohttp AppRunner

Added three new functions to `Homeassistant/main.py`:

- `handle_health(request)` — GET /health returns `{"status": "ok", "addon": "wallbox-dolibarr"}` with HTTP 200
- `handle_session_stop(request)` — POST /session/stop: validates session_id (400 if missing), checks api_client (503 if None), calls transmit_completed_sessions()
- `start_health_server(port=8099)` — creates aiohttp app, registers routes, starts AppRunner + TCPSite on 0.0.0.0:8099, returns runner

Integration into `main()`:
- `api_client` promoted from local variable to module-level global (accessible from handler)
- `health_runner = await start_health_server(port=8099)` called after check_startup_session, before subscribe_entities
- `health_runner.cleanup()` added to `finally:` block for clean shutdown

### Task 2: session_manager.py — upload_status/upload_error Writes

Added to `_init_database()`:
- Migration guard: `ALTER TABLE sessions ADD COLUMN upload_status TEXT DEFAULT "pending"`
- Migration guard: `ALTER TABLE sessions ADD COLUMN upload_error TEXT`

Updated `transmit_completed_sessions()`:
- On success: `UPDATE sessions SET transmitted_at=?, upload_status='ok', upload_error=NULL WHERE id=?`
- On failure: `UPDATE sessions SET upload_status='error', upload_error=error[:1000] WHERE id=?`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing NameError in session_manager._init_database()**
- **Found during:** Task 2
- **Issue:** Line 88 used `_LOGGER.info(...)` but `_LOGGER` was never defined at module level in session_manager.py — only `self._logger` exists (set in `__init__` AFTER `_init_database()` is called)
- **Fix:** Added `_LOGGER = logging.getLogger(__name__)` at module level, consistent with main.py pattern
- **Files modified:** Homeassistant/session_manager.py
- **Commit:** d9539bb

## TDD Gate Compliance

- RED gate: commit 82da950 (`test(06-02): add failing tests...`) — 3 structure tests failed correctly
- GREEN gate: commit 34da703 (`feat(06-02): add /health and /session/stop...`) — all 7 tests pass

## Known Stubs

None. All endpoints are fully implemented. upload_status is written to SQLite and ready for Plan 03 to read from MySQL (llx_wallbox_sessions).

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: input-validation | Homeassistant/main.py | handle_session_stop validates session_id via int() coercion; ValueError caught and returns 400 (T-06-04 mitigated) |

## Self-Check: PASSED

- Homeassistant/main.py: FOUND
- Homeassistant/session_manager.py: FOUND
- Homeassistant/tests/test_health.py: FOUND
- Commit 82da950: FOUND
- Commit 34da703: FOUND
- Commit d9539bb: FOUND
- All 7 tests pass: CONFIRMED
