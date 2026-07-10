---
phase: "06-monitoring-status"
plan: "00"
subsystem: "homeassistant-tests"
tags: ["testing", "pytest", "tdd", "wave-0", "scaffold"]
dependency_graph:
  requires: []
  provides:
    - "Homeassistant/tests/conftest.py"
    - "Homeassistant/tests/test_health.py"
    - "Homeassistant/tests/test_session_status.py"
  affects:
    - "06-01"
    - "06-02"
tech_stack:
  added:
    - "pytest (test runner)"
    - "aiohttp.test_utils (HTTP test client stubs)"
  patterns:
    - "pytest.mark.xfail for RED-phase stubs"
    - "pytest.skip on ImportError for safe collection pre-implementation"
    - "in-memory SQLite via :memory: for isolated fixture state"
key_files:
  created:
    - "Homeassistant/tests/__init__.py"
    - "Homeassistant/tests/conftest.py"
    - "Homeassistant/tests/test_health.py"
    - "Homeassistant/tests/test_session_status.py"
  modified: []
decisions:
  - "Use pytest.mark.xfail (not pytest.skip) so test contracts are visible in run output"
  - "No module-level imports from main.py or session_manager.py — prevents collection-time ImportError before Wave 1"
  - "pytest.skip on ImportError in fixtures — allows collection even without aiohttp installed"
metrics:
  duration: "303s"
  completed_date: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
  files_created: 4
  files_modified: 0
requirements:
  - MON-01
  - MON-02
---

# Phase 6 Plan 00: Test Scaffold (Wave 0) Summary

**One-liner:** pytest test scaffold with 8 xfail stubs documenting /health, /session/stop, and upload_status SQLite write contracts for Wave 1 implementation.

## What Was Built

Created the Homeassistant/tests/ directory with three files:

- **conftest.py** — Shared fixtures: `in_memory_session_manager` (SQLite :memory:), `mock_api_client_success`, `mock_api_client_failure`, `health_app` (async fixture, skips pre-Wave 1)
- **test_health.py** — 5 xfail stubs for MON-01: GET /health → 200, POST /session/stop → 400 (missing id), POST /session/stop → 503 (no api_client), start_health_server returns AppRunner, AppRunner non-blocking
- **test_session_status.py** — 3 xfail stubs for MON-02/MON-03: upload_status/upload_error columns created by _init_database(), upload_status='ok' on success, upload_status='error' on failure

## Verification Results

```
python3 -m pytest Homeassistant/tests/ --collect-only -q
8 tests collected in 0.01s   (0 errors)

python3 -c "import ast; [...]; print('all syntax ok')"
all syntax ok
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | c058a39 | feat(06-00): add pytest test scaffold conftest.py with shared fixtures |
| 2 | 687ca27 | test(06-00): add failing test stubs for /health, /session/stop, upload_status (RED phase) |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

This entire plan IS the stub/scaffold layer. All 8 test functions are intentionally marked `@pytest.mark.xfail` — they will be wired to real implementations by Wave 1 plans (06-01, 06-02). No production data flows are affected.

## TDD Gate Compliance

Wave 0 role: establish RED gate artifacts. The `test(06-00)` commit at 687ca27 is the RED gate. GREEN gate commits will appear in 06-01 and 06-02.

## Self-Check: PASSED

- FOUND: Homeassistant/tests/__init__.py
- FOUND: Homeassistant/tests/conftest.py
- FOUND: Homeassistant/tests/test_health.py
- FOUND: Homeassistant/tests/test_session_status.py
- FOUND: commit c058a39 (feat: conftest.py)
- FOUND: commit 687ca27 (test: stubs)
