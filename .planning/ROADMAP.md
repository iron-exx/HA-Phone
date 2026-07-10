# Roadmap: Wallbox-Dolibarr Integration

**Project:** Wallbox-Dolibarr Integration
**Granularity:** Fine (from config.json)
**Created:** 2026-05-04
**Total v1 Requirements:** 40 (v1.0) + 11 (v1.1) = 51

## Milestones

- ✅ **v1.0 MVP** — Phases 1-5 (shipped 2026-05-11)
- [x] **v1.1 Robustheit & Monitoring** — Phases 6-8 — completed 2026-06-23

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-5) — SHIPPED 2026-05-11</summary>

- [x] Phase 1: Foundation (2/2 plans) — completed 2026-05-04
- [x] Phase 2: Session Tracking + User Management (2/2 plans) — completed 2026-05-05
- [x] Phase 3: API Integration (2/2 plans) — completed 2026-05-06
- [x] Phase 4: Billing + Invoicing + Export (2/2 plans) — completed 2026-05-08
- [x] Phase 5: Hardening + Multi-Wallbox (2/2 plans) — completed 2026-05-08

</details>

**v1.1 Robustheit & Monitoring (Phases 6-8):**

- [x] **Phase 6: Monitoring & Status** — Dolibarr Admin-Tab zeigt Systemstatus und Session-Historie — completed 2026-06-22
- [x] **Phase 7: Alerts & Logging** — System meldet Fehler aktiv und protokolliert strukturiert — completed 2026-06-23
- [x] **Phase 8: Retry & Dead-letter** — Fehlgeschlagene Uploads werden gespeichert und können manuell neu gestartet werden — completed 2026-06-23

## Phase Details

### Phase 6: Monitoring & Status
**Goal**: Admin kann Systemgesundheit und Übertragungshistorie direkt im Dolibarr-Admin-Tab einsehen
**Depends on**: Phase 5 (v1.0 Foundation)
**Requirements**: MON-01, MON-02, MON-03
**Success Criteria** (what must be TRUE):
  1. Admin öffnet den Wallbox-Billing-Admin-Tab und sieht sofort, ob die API erreichbar ist oder nicht
  2. Admin sieht eine Tabelle der letzten N übertragenen Sessions mit Datum, Wallbox-ID und Übertragungsstatus
  3. Admin sieht fehlgeschlagene Übertragungen mit der zugehörigen Fehlermeldung (kein generischer Fehlertext)
  4. Die Status-Seite lädt ohne PHP-Fehler und ohne manuellen Reload des Dolibarr-Moduls
**Plans**: 3 plans
Plans:
- [x] 06-01-PLAN.md — DB schema migration: upload_status/upload_error/uploaded_at columns in llx_wallbox_sessions
- [x] 06-02-PLAN.md — HA-Addon: /health + /session/stop endpoints + upload_status writing in session_manager
- [x] 06-03-PLAN.md — Dolibarr admin.php: three-tab rebuild with Status-Tab (cURL ping + session table + stop button)
- [x] 06-04-PLAN.md — Gap-closure: CR-01/CR-02/CR-03/WR-06/WR-07/WR-08 fixes
**UI hint**: yes
**Completed**: 2026-06-22 (5/5 plans, 9/9 must-haves verified, human UAT pending)

### Phase 7: Alerts & Logging
**Goal**: Das System erkennt Upload-Fehler selbstständig und informiert den Admin — in Home Assistant und per E-Mail
**Depends on**: Phase 6
**Requirements**: ALT-01, ALT-02, LOG-01, LOG-02, LOG-03
**Success Criteria** (what must be TRUE):
  1. Wenn ein Session-Upload fehlschlägt, erscheint in Home Assistant eine persistent_notification mit Fehlerdetail
  2. Wenn Upload-Fehler auftreten, erhält der konfigurierte Admin eine E-Mail von Dolibarr mit Fehlerbeschreibung
  3. Das HA-Addon-Log-Level ist per config.yaml auf debug / info / warning setzbar — ohne Code-Änderung
  4. Logs enthalten keine RFID-Klartexte, API-Tokens oder personenbezogenen Daten (überprüfbar per Log-Review)
  5. Dolibarr loggt Upload-Ereignisse (Erfolg und Fehler) strukturiert ins Dolibarr-Logfile
**Plans**: 3 plans
Plans:
- [x] 07-01-PLAN.md — HA-Addon main.py: apply_log_level_from_config() (LOG-01) + send_persistent_notification() (ALT-01)
- [x] 07-02-PLAN.md — Test scaffold: test_logging.py (LOG-01) + test_log_scrubbing.py (LOG-02) + test_alerts.py (ALT-01)
- [x] 07-03-PLAN.md — Dolibarr: dol_syslog in postSession() (LOG-03) + CMailFile email alert + admin.php WALLBOXBILLING_ADMIN_EMAIL field (ALT-02)

### Phase 8: Retry & Dead-letter
**Goal**: Fehlgeschlagene Session-Uploads gehen nicht verloren und können vom Admin manuell oder automatisch wiederholt werden
**Depends on**: Phase 7
**Requirements**: RET-01, RET-02, RET-03
**Success Criteria** (what must be TRUE):
  1. Fehlgeschlagene Session-Uploads werden in einer eigenen Datenbanktabelle (Dead-letter) persistiert — kein Datenverlust bei Fehler
  2. Admin kann im Dolibarr-Admin-Tab einen einzelnen Dead-letter-Eintrag manuell zum Retry markieren und absenden
  3. Beim nächsten regulären Übertragungszyklus werden pending Dead-letter-Einträge automatisch erneut versucht
  4. Nach erfolgreichem Retry wird der Dead-letter-Eintrag als erledigt markiert und erscheint nicht mehr in der Fehlerliste
**Plans**: 3 plans
Plans:
**Wave 1:**
- [x] 08-01-PLAN.md — TDD test scaffold: test_dead_letter.py — 7 test classes RED phase (RET-01, RET-02, RET-03)

**Wave 2 *(parallel)*:**
- [x] 08-02-PLAN.md — HA-Addon Python: dead_letter table + 4 SessionManager methods + /session/retry + /dead-letter/list endpoints + periodic retry
- [x] 08-03-PLAN.md — Dolibarr admin.php: 4th tab 'Fehlgeschlagen' + retry_dead_letter action handler + deadletter tab content

**Cross-cutting constraints:**
- `rfid_hash` must never appear in any output, log, or HTTP response (SEC-01/02, D-04)
- `checkToken()` + `newToken()` on every POST form (D-05)
- `upload_status='dead_letter'` set in same transaction as dead_letter INSERT to prevent double-retry race (RESEARCH Pitfall 1)
**UI hint**: yes

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 2/2 | Complete ✓ | 2026-05-04 |
| 2. Session Tracking + User Management | v1.0 | 2/2 | Complete ✓ | 2026-05-05 |
| 3. API Integration | v1.0 | 2/2 | Complete ✓ | 2026-05-06 |
| 4. Billing + Invoicing + Export | v1.0 | 2/2 | Complete ✓ | 2026-05-08 |
| 5. Hardening + Multi-Wallbox | v1.0 | 2/2 | Complete ✓ | 2026-05-08 |
| 6. Monitoring & Status | v1.1 | 5/5 | Complete ✓ | 2026-06-22 |
| 7. Alerts & Logging | v1.1 | 3/3 | Complete ✓ | 2026-06-23 |
| 8. Retry & Dead-letter | v1.1 | 3/3 | Complete ✓ | 2026-06-23 |

---

*Roadmap created: 2026-05-04*
*v1.0 requirements: 40/40 ✓*
*v1.1 requirements: 11/11 ✓*
*Total coverage: 51/51 ✓*
*Last updated: 2026-06-23 — Phase 8 complete, v1.1 milestone complete*
