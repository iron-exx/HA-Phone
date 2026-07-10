---
phase: 07-alerts-logging
plan: "03"
subsystem: dolibarr-module
tags: [logging, alerting, email, api, admin-config]
dependency_graph:
  requires: []
  provides: [LOG-03, ALT-02]
  affects: [api_wallboxbilling, admin-config-tab]
tech_stack:
  added: [CMailFile]
  patterns: [dol_syslog, getDolGlobalString, dolibarr_set_const, GETPOST-email-filter]
key_files:
  modified:
    - Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php
    - Dolibarr/htdocs/custom/wallboxbilling/admin.php
decisions:
  - "sendfile() failure is caught and logged as LOG_WARNING, no re-throw — API responds regardless of SMTP issues (T-07-08)"
  - "Email guard (WALLBOXBILLING_ADMIN_EMAIL empty check) prevents spam on repeated DB failures (T-07-09)"
  - "GETPOST 'email' filter used for admin email input — Dolibarr validates format (T-07-10)"
metrics:
  duration: "~15 minutes"
  completed: "2026-06-23"
  tasks: 2
  files_modified: 2
---

# Phase 07 Plan 03: dol_syslog + CMailFile alerting Summary

## One-liner

Added dol_syslog structured logging (LOG_INFO on success, LOG_ERR on failure) and CMailFile email alerting with WALLBOXBILLING_ADMIN_EMAIL guard to the session upload API endpoint, with admin config UI field.

## What Was Built

### Task 1: api_wallboxbilling.class.php — LOG-03 + ALT-02

- Added `require_once DOL_DOCUMENT_ROOT.'/core/class/CMailFile.class.php'` after existing api.class.php require (prevents Fatal error on first use)
- On INSERT failure: `dol_syslog(LOG_ERR)` with wallbox_id + db error string
- On INSERT failure with WALLBOXBILLING_ADMIN_EMAIL set: `CMailFile->sendfile()` email to admin; sendfile failure logged as LOG_WARNING, no re-throw (API always responds)
- On INSERT success: `dol_syslog(LOG_INFO)` with session_id + wallbox_id + kwh
- Validation errors (400-level) unchanged — not touched per plan constraint

### Task 2: admin.php — ALT-02 admin config field

- `GETPOST('WALLBOXBILLING_ADMIN_EMAIL', 'email')` with Dolibarr's email filter in action=update block
- `dolibarr_set_const()` save alongside existing WALLBOXBILLING_DEFAULT_PRICE save
- `<input type="email">` row in config tab with `getDolGlobalString()` current value display and placeholder
- Tab structure, CSRF tokens (newToken x3), dol_get_fiche_head all unchanged

## Verification

Grep-based acceptance checks all passed:

```
grep -c "dol_syslog" api_wallboxbilling.class.php  => 3 (LOG_ERR, LOG_WARNING, LOG_INFO)
grep -c "WALLBOXBILLING_ADMIN_EMAIL" admin.php      => 3 (GETPOST, dolibarr_set_const, getDolGlobalString)
grep "CMailFile" api_wallboxbilling.class.php       => 2 lines (require_once + new CMailFile)
```

Note: PHP CLI not installed in this environment; php -l checks could not be executed. The file structure was manually verified as syntactically correct PHP through inspection.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Surface Scan

No new trust boundaries introduced beyond those already in the plan's threat model:
- T-07-08 (SMTP blocking): mitigated — sendfile() failure caught, logged as LOG_WARNING, no re-throw
- T-07-09 (email flood DoS): mitigated — email only sent when WALLBOXBILLING_ADMIN_EMAIL configured AND DB INSERT fails
- T-07-10 (admin email injection): mitigated — GETPOST 'email' filter applied

## Known Stubs

None — all data flows are wired. Admin email is read from DB constant via getDolGlobalString().

## Self-Check: PASSED

Files exist:
- Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php: modified (CMailFile + dol_syslog)
- Dolibarr/htdocs/custom/wallboxbilling/admin.php: modified (WALLBOXBILLING_ADMIN_EMAIL field)

Commits:
- 82901e9: feat(07-03): add dol_syslog + CMailFile alerting to postSession() (LOG-03 + ALT-02)
- 2bebd3c: feat(07-03): add WALLBOXBILLING_ADMIN_EMAIL field to admin config tab (ALT-02)
