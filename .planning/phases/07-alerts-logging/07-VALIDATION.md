---
phase: 7
slug: alerts-logging
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-22
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | Homeassistant/tests/ (existing) |
| **Quick run command** | `python3 -m pytest Homeassistant/tests/ -q --tb=short` |
| **Full suite command** | `python3 -m pytest Homeassistant/tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest Homeassistant/tests/ -q --tb=short`
- **After every plan wave:** Run `python3 -m pytest Homeassistant/tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 1 | LOG-01 | — | log_level from config, not hardcoded | unit | `python3 -m pytest Homeassistant/tests/test_logging.py -q` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 1 | LOG-02 | — | no RFID/token in log output | unit | `python3 -m pytest Homeassistant/tests/test_log_scrubbing.py -q` | ❌ W0 | ⬜ pending |
| 7-02-01 | 02 | 1 | ALT-01 | — | persistent_notification POST triggered on failure | unit/mock | `python3 -m pytest Homeassistant/tests/test_alerts.py -q` | ❌ W0 | ⬜ pending |
| 7-03-01 | 03 | 1 | LOG-03 | — | dol_syslog called in postSession() | manual | php -l check | existing | ⬜ pending |
| 7-03-02 | 03 | 1 | ALT-02 | — | CMailFile called on upload error | manual | code review | existing | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `Homeassistant/tests/test_logging.py` — stubs for LOG-01 (configurable log level)
- [ ] `Homeassistant/tests/test_log_scrubbing.py` — stubs for LOG-02 (no sensitive data in logs)
- [ ] `Homeassistant/tests/test_alerts.py` — stubs for ALT-01 (persistent_notification mock)

*Existing infrastructure (conftest.py, session_manager fixtures) covers shared state.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dolibarr dol_syslog appears in Dolibarr log file | LOG-03 | Requires live Dolibarr + writable logfile | Upload a session via Dolibarr admin, check `/var/log/dolibarr.log` for `wallboxbilling` entries |
| CMailFile sends email to admin on upload error | ALT-02 | Requires live SMTP + Dolibarr mail config | Trigger a failed upload via API, check admin email inbox |
| HA persistent_notification appears in UI | ALT-01 | Requires live Home Assistant | Trigger a failed upload, check HA UI for notification badge |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-22
