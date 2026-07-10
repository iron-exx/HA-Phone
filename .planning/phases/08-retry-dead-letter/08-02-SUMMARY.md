---
phase: 08-retry-dead-letter
plan: 02
subsystem: ha-addon
tags: [python, sqlite, dead-letter, retry, session-manager, aiohttp, rет-01, rет-02, rет-03]

# Dependency graph
requires:
  - phase: 08-01
    provides: TDD RED scaffold test_dead_letter.py (8 test classes, 9 tests in RED state)
  - phase: 07-alerts-logging
    provides: session_manager.transmit_completed_sessions() + conftest.py fixtures
provides:
  - "dead_letter SQLite table with UNIQUE(session_id) constraint"
  - "retry_dead_letter_sessions(): batch retry with D-01 continue behavior (RET-03)"
  - "retry_single_dead_letter(): per-entry manual retry for /session/retry endpoint (RET-02)"
  - "get_pending_dead_letters(): pending entries without rfid_hash (SEC-01/D-04)"
  - "/session/retry POST endpoint with int coerce + 400/503/200 responses (RET-02/T-08-01)"
  - "/dead-letter/list GET endpoint returning pending entries JSON (RET-02)"
  - "periodic_transmission() calls retry_dead_letter_sessions() after each transmit cycle (RET-03)"
affects: [08-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "INSERT OR IGNORE INTO dead_letter — prevents duplicate rows on repeated failure (UNIQUE constraint)"
    - "upload_status='dead_letter' replaces 'error' — enables exclusion from re-transmit query"
    - "AND (upload_status IS NULL OR upload_status NOT IN ('ok', 'dead_letter')) — race-condition guard T-08-05"
    - "continue per D-01 in retry loop — never break on per-entry failure"
    - "int(data.get('dead_letter_id', 0)) coerce in handler — T-08-01 tamper protection"

key-files:
  created: []
  modified:
    - Homeassistant/session_manager.py
    - Homeassistant/main.py

key-decisions:
  - "Tests run from worktree cwd (not cd /home/roto) because pytest imports session_manager from the worktree path — both yield identical behavior as long as the worktree branch is merged correctly"
  - "retry_dead_letter_sessions() does NOT await — synchronous sqlite3.connect call like transmit_completed_sessions()"
  - "get_pending_dead_letters() docstring mentions rfid_hash for documentation clarity; the SELECT itself does not include it — SEC-01 satisfied"

patterns-established:
  - "Dead-letter failure branch: UPDATE sessions + INSERT OR IGNORE dead_letter + break (transmit stops on first failure, records to dead_letter)"
  - "Retry loop: SELECT pending, loop with continue on exception (D-01), commit all at end"

requirements-completed:
  - RET-01
  - RET-02
  - RET-03

# Metrics
duration: 4min
completed: 2026-06-23
---

# Phase 08 Plan 02: Dead-letter Implementation Summary

**Dead-letter queue fully implemented: SQLite table with UNIQUE constraint, 3 new SessionManager methods, 2 new HTTP endpoints, and periodic retry integration — all 9 TDD RED tests flipped to GREEN**

## Performance

- **Duration:** 4 min
- **Started:** 2026-06-23T15:09:55Z
- **Completed:** 2026-06-23T15:14:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `session_manager.py`: dead_letter table added to _init_database() with UNIQUE(session_id) and idx_dead_letter_status index (RET-01)
- `session_manager.py`: transmit_completed_sessions() SELECT now excludes `upload_status IN ('ok', 'dead_letter')` — prevents double-retry race condition (T-08-05)
- `session_manager.py`: failure branch changed from upload_status='error' to 'dead_letter' + INSERT OR IGNORE into dead_letter table (RET-01)
- `session_manager.py`: retry_dead_letter_sessions() — batch retry with D-01 continue (RET-03)
- `session_manager.py`: retry_single_dead_letter() — single-entry manual retry (RET-02)
- `session_manager.py`: get_pending_dead_letters() — SELECT excludes rfid_hash (SEC-01/D-04/T-08-03)
- `main.py`: handle_session_retry() with int coerce T-08-01, 400/503/200 responses (RET-02)
- `main.py`: handle_dead_letter_list() returning pending entries JSON (RET-02)
- `main.py`: /session/retry and /dead-letter/list registered in start_health_server()
- `main.py`: periodic_transmission() calls retry_dead_letter_sessions() after transmit_completed_sessions() (RET-03)
- All 9 test_dead_letter.py tests GREEN; full suite 43 passed 0 failures

## Task Commits

1. **Task 1: session_manager.py — dead_letter table, new methods, transmit failure branch** - `02df4cf` (feat)
2. **Task 2: main.py — /session/retry endpoint, /dead-letter/list endpoint, periodic retry call** - `01a9f36` (feat)

## Files Created/Modified

- `Homeassistant/session_manager.py` — dead_letter table, 3 new methods, updated transmit query and failure branch (+148 lines)
- `Homeassistant/main.py` — 2 new handlers, 2 new routes, periodic retry call (+45 lines)

## Decisions Made

- Tests must run from worktree cwd because pytest imports `session_manager` from `sys.path`, which resolves to the worktree checkout path. Running `cd /home/roto` would import the original unmodified file. The plan's `<automated>` tags showed `cd /home/roto` but this reflects the original project path convention — within a parallel worktree execution, tests are run without the `cd /home/roto` prefix.
- `retry_dead_letter_sessions()` is called synchronously (no `await`) matching the existing pattern for `transmit_completed_sessions()`.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written. All patterns from 08-PATTERNS.md implemented verbatim.

## Issues Encountered

None beyond the test execution path difference noted in Decisions Made above.

## Known Stubs

None — all dead_letter methods are fully implemented with real SQLite operations.

## Threat Flags

No new threat surface beyond what is documented in the plan's threat model. All T-08-* mitigations implemented:
- T-08-01 (dead_letter_id tamper): `int(data.get('dead_letter_id', 0))` coerce in handle_session_retry()
- T-08-03 (rfid_hash disclosure): get_pending_dead_letters() SELECT omits rfid_hash column
- T-08-05 (double-retry race): SELECT excludes upload_status IN ('ok', 'dead_letter')

## Self-Check

Commits verified:
- `02df4cf`: feat(08-02) session_manager.py
- `01a9f36`: feat(08-02) main.py

Files verified present:
- Homeassistant/session_manager.py — contains dead_letter table, 3 new methods
- Homeassistant/main.py — contains handle_session_retry, handle_dead_letter_list

## Self-Check: PASSED

---
*Phase: 08-retry-dead-letter*
*Completed: 2026-06-23*
