---
phase: 6
slug: monitoring-status
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-06-21
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (Python / HA-Addon), PHP manual (Dolibarr) |
| **Config file** | `Homeassistant/tests/conftest.py` — Wave 0 creates |
| **Quick run command** | `python3 -m pytest Homeassistant/tests/test_health.py -x -q` |
| **Full suite command** | `python3 -m pytest Homeassistant/tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest Homeassistant/tests/ -x -q`
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 6-W0-01 | W0 | 0 | MON-01 | — | /health returns JSON, no auth bypass | unit | `python3 -m pytest Homeassistant/tests/test_health.py -x -q` | ❌ W0 | ⬜ pending |
| 6-01-01 | 01 | 1 | MON-02/03 | — | upload_status ENUM columns exist | manual | `php artisan tinker` / DB inspect | ✅ | ⬜ pending |
| 6-02-01 | 02 | 1 | MON-01 | — | /health responds 200 JSON | unit | `python3 -m pytest Homeassistant/tests/test_health.py -x -q` | ❌ W0 | ⬜ pending |
| 6-02-02 | 02 | 1 | MON-02/03 | — | upload_status written to SQLite after transmit | unit | `python3 -m pytest Homeassistant/tests/test_session_status.py -x -q` | ❌ W0 | ⬜ pending |
| 6-02-03 | 02 | 1 | MON-03 | — | Dolibarr session.php sets upload_status='ok' in MySQL | manual | Admin-Tab öffnen, Session prüfen | ✅ | ⬜ pending |
| 6-03-01 | 03 | 2 | MON-01/02/03 | — | Status-Tab lädt ohne PHP-Fehler, zeigt Tabelle | manual | Browser: admin.php?tab=status | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `Homeassistant/tests/test_health.py` — 5 Behavior-Tests für /health Endpunkt (HTTP 200, JSON-Format, kein Auth erforderlich, Timeout-Handling, korrekte Response-Keys) — **Plan 06-00**
- [x] `Homeassistant/tests/test_session_status.py` — Tests für upload_status-Schreibung in SQLite nach transmit_session() — **Plan 06-00**
- [x] `Homeassistant/tests/conftest.py` — shared fixtures (mock aiohttp-App, test-SQLite-DB) — **Plan 06-00**

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Status-Tab als Default-Tab | MON-01 | Browser-Navigation nötig | admin.php öffnen ohne ?tab= → muss Status-Tab aktiv sein |
| Fehlermeldung spezifisch (kein generischer Text) | MON-03 | Inhaltsprüfung | Error-Session einfügen, prüfen ob upload_error-Text (z.B. "HTTP 503") angezeigt wird |
| cURL-Ping Timeout 4s | MON-01 | HA-Addon muss offline sein | HA-Addon stoppen, admin.php?tab=status laden → Ladezeit < 6s |
| Manuelle Session-Beendigung | D-12/D-14 | UI-Interaktion + API-Aufruf | aktive Session im Tab anzeigen, "Beenden"-Button klicken, Weiterleitung und Status "ok" prüfen |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (plan 06-00)
- [x] No watch-mode flags
- [x] Feedback latency < 10s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-21
