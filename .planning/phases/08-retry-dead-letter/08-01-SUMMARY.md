---
phase: 08-retry-dead-letter
plan: 01
subsystem: testing
tags: [pytest, sqlite, tdd, dead-letter, retry, session-manager]

# Dependency graph
requires:
  - phase: 07-alerts-logging
    provides: session_manager.transmit_completed_sessions() + conftest.py fixtures
  - phase: 06-monitoring-status
    provides: upload_status column on sessions table
provides:
  - "TDD RED scaffold: test_dead_letter.py with 8 test classes, 9 test functions"
  - "RED gate for Plan 08-02: all tests fail before implementation touches session_manager.py"
  - "T-08-03 mitigation test: get_pending_dead_letters() must exclude rfid_hash"
affects: [08-02, 08-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED scaffold: test file exists before any implementation method is written"
    - "_seed_completed_session() helper with created_at field (NOT NULL constraint required)"
    - "_seed_dead_letter_row() helper uses pytest.fail() for explicit RED messaging"
    - "TestRetryEndpoint uses pytest.skip() on ImportError to avoid crashing collector"

key-files:
  created:
    - Homeassistant/tests/test_dead_letter.py
  modified: []

key-decisions:
  - "Added TestGetPendingDeadLetters (8th class beyond plan's 7) to cover T-08-03 threat: rfid_hash must not appear in get_pending_dead_letters() return value"
  - "TestRetryEndpoint tests use pytest.skip() on ImportError (not pytest.fail()) so test runner does not crash before Plan 08-02 implements handle_session_retry()"
  - "_seed_completed_session() must include created_at column — sessions table has NOT NULL constraint on that field"

patterns-established:
  - "RED seed helpers: direct SQLite INSERT bypasses SessionManager for table-existence assertions"
  - "Explicit pytest.fail() with 'RED: ...' prefix makes missing-implementation failures informative rather than cryptic OperationalError tracebacks"

requirements-completed:
  - RET-01
  - RET-02
  - RET-03

# Metrics
duration: 3min
completed: 2026-06-23
---

# Phase 08 Plan 01: Dead-letter TDD RED Scaffold Summary

**pytest RED scaffold for dead-letter queue: 8 test classes asserting dead_letter table, retry_dead_letter_sessions(), get_pending_dead_letters(), and /session/retry HTTP endpoint — all failing before Plan 08-02 implementation**

## Performance

- **Duration:** 3 min
- **Started:** 2026-06-23T15:03:36Z
- **Completed:** 2026-06-23T15:06:24Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `Homeassistant/tests/test_dead_letter.py` with 8 test classes and 9 test functions
- RED state confirmed: 7 FAILED (missing table/methods), 2 SKIPPED (endpoint tests wait for Plan 08-02), 0 PASSED
- All 3 requirement IDs referenced (RET-01, RET-02, RET-03); T-08-03 threat mitigated via TestGetPendingDeadLetters
- pytest collects all 9 tests without import errors or crashes

## Task Commits

1. **Task 1: Write RED test scaffold for RET-01, RET-02, RET-03** - `e06eaa0` (test)

## Files Created/Modified

- `Homeassistant/tests/test_dead_letter.py` - 8 test classes covering RET-01/02/03 in RED state

## Decisions Made

- Added `TestGetPendingDeadLetters` as an 8th class (plan specified 7 minimum) to cover the T-08-03 threat model entry requiring rfid_hash exclusion from `get_pending_dead_letters()`
- Used `pytest.skip()` (not `pytest.fail()`) on ImportError in `TestRetryEndpoint` so that the test runner does not abort collection when `handle_session_retry` is absent
- `_seed_completed_session()` includes `created_at` column because the sessions table has a NOT NULL constraint that was not documented in the plan's helper snippet

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed _seed_completed_session() missing created_at column**
- **Found during:** Task 1 (after first test run)
- **Issue:** Plan-provided INSERT snippet omitted `created_at`, which has a NOT NULL constraint on the sessions table — all tests failed with `sqlite3.IntegrityError` before reaching the intended RED assertion
- **Fix:** Added `created_at` field with value `'2026-01-01T10:00:00'` to the INSERT statement
- **Files modified:** Homeassistant/tests/test_dead_letter.py
- **Verification:** All 9 tests re-run; failures are now the correct OperationalError/AssertionError RED failures
- **Committed in:** e06eaa0 (Task 1 commit)

**2. [Rule 2 - Missing Critical] Added TestGetPendingDeadLetters for T-08-03 rfid_hash exclusion**
- **Found during:** Task 1 (threat model scan before writing SUMMARY)
- **Issue:** Plan listed 7 test classes but T-08-03 in the threat model had `mitigate` disposition for rfid_hash info-disclosure; no test class covered `get_pending_dead_letters()` rfid_hash exclusion
- **Fix:** Added 8th class `TestGetPendingDeadLetters` with `test_get_pending_dead_letters_excludes_rfid_hash`
- **Files modified:** Homeassistant/tests/test_dead_letter.py
- **Verification:** grep "rfid_hash" in test file; class in RED state (method does not exist yet)
- **Committed in:** e06eaa0 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 missing critical security test)
**Impact on plan:** Both fixes necessary — without fix 1, RED state was broken (wrong error type); without fix 2, T-08-03 threat mitigation would have no test coverage in Wave 1.

## Issues Encountered

None beyond the deviations documented above.

## Known Stubs

None — this plan creates test infrastructure only, no production code with stubs.

## Threat Flags

No new threat surface introduced (test-only file, no network endpoints, no schema changes).

## Next Phase Readiness

- RED gate established: Plan 08-02 can now add `dead_letter` table, `write_dead_letter_on_failure()`, `retry_dead_letter_sessions()`, `retry_single_dead_letter()`, `get_pending_dead_letters()`, and `handle_session_retry()` — each method will flip its test from FAILED to PASSED
- `TestRetryEndpoint` will automatically activate (skip drops) when Plan 08-02 adds `handle_session_retry` to main.py
- No blockers

---
*Phase: 08-retry-dead-letter*
*Completed: 2026-06-23*
