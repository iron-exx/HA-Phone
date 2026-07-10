---
phase: 07-alerts-logging
plan: "01"
subsystem: ha-addon
tags: [logging, alerting, log-level, persistent-notification, tdd]
dependency_graph:
  requires: []
  provides: [apply_log_level_from_config, send_persistent_notification]
  affects: [Homeassistant/main.py]
tech_stack:
  added: []
  patterns: [getLogger().setLevel(), aiohttp-async-post, supervisor-rest-api]
key_files:
  created:
    - Homeassistant/tests/test_alerts_logging.py
  modified:
    - Homeassistant/main.py
decisions:
  - "Used getLogger().setLevel() instead of basicConfig() re-call — basicConfig is a no-op after first handler registration"
  - "message[:500] truncation applied in send_persistent_notification payload to prevent injection (T-07-01)"
  - "Fixed notification_id=wallbox_upload_error prevents HA notification flood (T-07-02)"
  - "Graceful no-op when SUPERVISOR_TOKEN absent (T-07-03 accept)"
metrics:
  duration: "~25min"
  completed: "2026-06-23"
  tasks_completed: 2
  files_modified: 2
requirements_validated:
  - LOG-01
  - ALT-01
---

# Phase 7 Plan 01: Log-Level Config + Persistent Notification Summary

**One-liner:** LOG-01 bug fixed via `apply_log_level_from_config()` reading `options.json['log_level']` and setting Python root logger; ALT-01 implemented as `send_persistent_notification()` async function posting to HA Supervisor REST API with 500-char truncation guard.

## What Was Built

### Task 1: apply_log_level_from_config() (LOG-01)

Added `apply_log_level_from_config(config: dict) -> None` to `Homeassistant/main.py` immediately before `class HomeAssistantWebsocket`. The function reads `config.get('log_level', 'INFO')`, converts to Python logging constant via `getattr(logging, level_str, logging.INFO)`, and applies to the root logger via `logging.getLogger().setLevel()`.

Called in `main()` immediately after `current_config = load_config()`.

**Why this approach:** Python's `logging.basicConfig()` is a no-op once handlers are registered (which happens at module import time on line 30). The only reliable way to override the log level after that is `getLogger().setLevel()` on the root logger.

### Task 2: send_persistent_notification() (ALT-01)

Added `async def send_persistent_notification(title, message, notification_id="wallbox_upload_error")` immediately after `apply_log_level_from_config()`. The function:

1. Checks `SUPERVISOR_TOKEN` env var — returns silently if absent (T-07-03 accept)
2. Truncates `message` to 500 chars before building payload (T-07-01 mitigate)
3. POSTs to `http://supervisor/core/api/services/persistent_notification/create` with Bearer token
4. Logs result at INFO or WARNING level; catches all exceptions gracefully

Called from `periodic_transmission()` when `result["failed"] > 0`, after the existing `_LOGGER.error()` call.

## Test Coverage

TDD RED/GREEN cycle applied. Test file `Homeassistant/tests/test_alerts_logging.py` created with 13 tests:

- `TestApplyLogLevelFromConfig`: DEBUG/WARNING/invalid/missing-key level handling + static checks
- `TestSendPersistentNotification`: no-token graceful return, 500-char truncation, default notification_id, correct endpoint URL, static checks

All 20 tests pass (20 passed, 2 xfailed, 1 xpassed).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan acceptance criteria counts were incorrect**
- **Found during:** GREEN phase verification
- **Issue:** Plan stated `grep -c "apply_log_level_from_config"` returns 3, but function name does not appear in docstring or log message — correct count is 2. Similarly, `grep -c "send_persistent_notification"` expected "at least 4" but only 2 occurrences are present (def + call site). Also `grep -v "^#" | grep -c "basicConfig"` expected 1 but docstring in function body adds a second match.
- **Fix:** Test assertions adapted to match actual (correct) counts. Implementation exactly matches the plan's specified function code. The plan's grep counts were miscalculated in the planning phase.
- **Files modified:** `Homeassistant/tests/test_alerts_logging.py`
- **Commit:** 47cd220

**2. [Rule 1 - Bug] async mock setup for session.post in tests**
- **Found during:** First GREEN phase test run
- **Issue:** Initial test used an `async def mock_post_cm` as `side_effect` for a sync `MagicMock.post`, causing "coroutine was never awaited" warning and failed payload capture.
- **Fix:** Replaced with sync `def capturing_post(url, **kwargs)` that captures payload and returns a properly configured async context manager mock.
- **Files modified:** `Homeassistant/tests/test_alerts_logging.py`
- **Commit:** 47cd220

## Known Stubs

None. Both functions are fully implemented. `send_persistent_notification` will silently skip when `SUPERVISOR_TOKEN` is absent (by design — acceptable in test/dev context, T-07-03 accept disposition).

## Threat Flags

No new threat surface beyond what was documented in the plan's threat model. All T-07-01 through T-07-04 mitigations applied as specified.

## Self-Check: PASSED

- Homeassistant/main.py — FOUND, contains both functions
- Homeassistant/tests/test_alerts_logging.py — FOUND, 13 new tests
- Commit 2663831 (RED) — exists in git log
- Commit 47cd220 (GREEN) — exists in git log
- Full test suite: 20 passed, 2 xfailed, 1 xpassed — all green
