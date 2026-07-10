---
status: partial
phase: 07-alerts-logging
source: [07-VERIFICATION.md]
started: "2026-06-23T00:00:00Z"
updated: "2026-06-23T00:00:00Z"
---

## Current Test

[awaiting human testing]

## Tests

### 1. HA Persistent Notification on Upload Failure (ALT-01)

expected: A persistent_notification titled 'Wallbox Upload-Fehler' appears in the HA notification panel with the failed session count and error detail
result: [pending]

**Steps:**
1. Ensure addon is running in real HA environment with SUPERVISOR_TOKEN set
2. Temporarily break the Dolibarr API (e.g. wrong DOLAPIKEY or stop the service)
3. Wait for next periodic_transmission cycle (or restart addon to trigger immediately)
4. Open HA notification panel → verify notification "Wallbox Upload-Fehler" appears with session count

### 2. Dolibarr Email Alert on DB Insert Failure (ALT-02)

expected: Admin receives email with subject 'Wallbox Upload-Fehler: Session konnte nicht gespeichert werden' containing db error string and wallbox_id
result: [pending]

**Steps:**
1. In Dolibarr admin config tab → set WALLBOXBILLING_ADMIN_EMAIL to a real inbox
2. Trigger a DB INSERT failure (e.g. temporarily rename llx_wallbox_sessions table or introduce a schema constraint)
3. Submit a session via the API endpoint
4. Verify email arrives with error details

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
