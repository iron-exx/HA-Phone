---
status: partial
phase: 06-monitoring-status
source: [06-VERIFICATION.md]
started: 2026-06-22T13:00:00Z
updated: 2026-06-22T13:00:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. admin.php lädt ohne PHP-Fehler
expected: Seite öffnet sich ohne PHP-Fatal, keine Blank-Page
result: [pending]

### 2. cURL Health-Ping — visuelle Zustände
expected: Status-Tab zeigt ✅ Erreichbar / ❌ Nicht erreichbar / ⚠ Fehler korrekt je nach HA-Addon-Zustand
result: [pending]

### 3. Session-Tabelle befüllt sich mit echten Daten
expected: Sessions aus llx_wallbox_sessions werden in der Tabelle angezeigt (Datum, Wallbox-ID, kWh, Status)
result: [pending]

### 4. Stop-Button beendet die korrekte Session
expected: Klick auf "Session beenden" für eine Session mit upload_status='pending' ruft mark_session_incomplete(session_id) auf — Session verschwindet aus der pending-Liste
result: [pending]

### 5. WR-07 td-Darstellung im Browser
expected: Health-Status-Zeile rendert korrekt ohne leere Zellen oder doppelten Inhalt im 'unreachable'-Zweig
result: [pending]

## Summary

total: 5
passed: 0
issues: 0
pending: 5
skipped: 0
blocked: 0

## Gaps
