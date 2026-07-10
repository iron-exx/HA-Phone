---
phase: 8
slug: retry-dead-letter
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | Homeassistant/tests/ (existing) |
| **Quick run command** | `python3 -m pytest Homeassistant/tests/ -q --tb=short` |
| **Full suite command** | `python3 -m pytest Homeassistant/tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest Homeassistant/tests/ -q --tb=short`
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | RET-01 | T-08-01 | dead_letter INSERT uses UNIQUE(session_id) to prevent duplicates | unit | `pytest tests/test_dead_letter.py -k test_write_dead_letter` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | RET-03 | T-08-02 | retry_dead_letter_sessions() only processes status='pending' rows | unit | `pytest tests/test_dead_letter.py -k test_retry_loop` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | RET-02 | T-08-03 | /session/retry endpoint rejects unknown dead_letter_id | integration | `pytest tests/test_dead_letter.py -k test_retry_endpoint` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 2 | RET-02 | — | PHP syntax valid, admin tab renders without error | syntax | `php -l admin.php` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Homeassistant/tests/test_dead_letter.py` — stubs for RET-01, RET-02, RET-03
- [ ] Use existing `conftest.py` fixtures (`in_memory_session_manager`, `mock_api_client_failure`)

*Existing pytest infrastructure covers all phase requirements — no new framework install needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Admin tab shows dead-letter table in live Dolibarr | RET-02 | Requires live Dolibarr + HA Addon running | Open admin.php Dead-letter tab, trigger a failed upload, verify row appears |
| Manual retry button sends cURL POST to HA Addon | RET-02 | Requires live integration | Click retry → verify HA Addon /session/retry receives POST, session is re-transmitted |
| Resolved dead-letter entries disappear from pending list | RET-03 | Requires live integration | After successful retry, verify row status changes to 'resolved' |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
