---
phase: 07-alerts-logging
plan: "02"
subsystem: ha-addon
tags: [testing, log-level, log-scrubbing, alerts, tdd, pytest]
dependency_graph:
  requires: [07-01]
  provides: [test_logging, test_log_scrubbing, test_alerts]
  affects:
    - Homeassistant/tests/test_logging.py
    - Homeassistant/tests/test_log_scrubbing.py
    - Homeassistant/tests/test_alerts.py
tech_stack:
  added: []
  patterns: [pytest-caplog, pytest-asyncio, unittest.mock.patch.dict, static-analysis-in-tests]
key_files:
  created:
    - Homeassistant/tests/test_logging.py
    - Homeassistant/tests/test_log_scrubbing.py
    - Homeassistant/tests/test_alerts.py
  modified: []
decisions:
  - "Used mock.patch.dict('sys.modules') to isolate main.py imports from HA runtime in LOG-01 and ALT-01 tests"
  - "Static analysis tests (reading main.py/api_client.py source) used for LOG-02 and ALT-01 verification without runtime HA"
  - "Each LOG-01 test resets root logger to INFO after assertion to prevent test isolation issues (T-07-06)"
metrics:
  duration: "~15min"
  completed: "2026-06-23"
  tasks_completed: 2
  files_modified: 3
requirements_validated:
  - LOG-01
  - LOG-02
  - ALT-01
---

# Phase 7 Plan 02: Test Scaffold for LOG-01, LOG-02, ALT-01 Summary

**One-liner:** Three test files created covering LOG-01 (apply_log_level_from_config behavior), LOG-02 (no RFID/token cleartext in logs), and ALT-01 (send_persistent_notification graceful no-token + truncation); full suite expands from 20 to 34 passing tests.

## What Was Built

### Task 1: test_logging.py (LOG-01)

Created `Homeassistant/tests/test_logging.py` with class `TestLogLevelConfig` containing 5 tests:

- `test_apply_log_level_debug` — verifies DEBUG level is set on root logger
- `test_apply_log_level_warning` — verifies WARNING level is set on root logger
- `test_apply_log_level_invalid_falls_back_to_info` — invalid string falls back to INFO
- `test_apply_log_level_missing_key_falls_back_to_info` — missing key falls back to INFO
- `test_apply_log_level_function_exists_in_main` — static check: function defined + called in main()

Each test uses `mock.patch.dict('sys.modules', ...)` to avoid HA runtime import errors and resets the root logger to INFO as cleanup (T-07-06 isolation).

### Task 2: test_log_scrubbing.py (LOG-02) + test_alerts.py (ALT-01)

**test_log_scrubbing.py** — class `TestLogScrubbing` with 4 tests:

- `test_rfid_hex_not_in_debounce_logs` — uses caplog + `in_memory_session_manager` fixture; verifies RFID cleartext absent after `debounce_rfid()`
- `test_rfid_hex_not_in_session_start_logs` — same pattern for `start_session()`
- `test_api_token_not_logged_in_api_client` — static analysis: regex extracts all `_LOGGER.*()` calls from api_client.py, asserts none contain `api_token`
- `test_rfid_hash_prefix_pattern_used_in_main` — static analysis: verifies no `rfid_hex` variable appears in `_LOGGER` lines of main.py

**test_alerts.py** — class `TestPersistentNotification` with 5 tests:

- `test_function_exists_in_main` — static check: `async def send_persistent_notification` present
- `test_called_on_failed_transmission_in_main` — static check: `await send_persistent_notification` present
- `test_notification_id_default_is_wallbox_upload_error` — static check: `wallbox_upload_error` present
- `test_no_token_returns_gracefully` — async test: monkeypatches away `SUPERVISOR_TOKEN`, asserts no exception raised
- `test_message_truncated_to_500_chars` — static check for `message[:500]` guard + async no-raise when no token

## Test Results

```
34 passed, 2 xfailed, 1 xpassed (full suite)
- test_logging.py: 5 passed
- test_log_scrubbing.py: 4 passed
- test_alerts.py: 5 passed
- pre-existing tests: 20 passed, 2 xfailed, 1 xpassed (unchanged)
```

## Deviations from Plan

None — plan executed exactly as written. All test files match the plan's specified content. All acceptance criteria met.

## Known Stubs

None. All tests are fully implemented and passing.

## Threat Flags

No new threat surface introduced. Test files do not expose sensitive data. Assertion messages use variable names (not values) where possible (T-07-05 compliant).

## Self-Check: PASSED

- Homeassistant/tests/test_logging.py — FOUND
- Homeassistant/tests/test_log_scrubbing.py — FOUND
- Homeassistant/tests/test_alerts.py — FOUND
- Commit ccc4e05 (Task 1) — exists in git log
- Commit d27a142 (Task 2) — exists in git log
- Full test suite: 34 passed, 2 xfailed, 1 xpassed — all green
