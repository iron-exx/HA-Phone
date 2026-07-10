# Phase 3: API Integration — Discussion Log

**Date:** 2026-05-05
**Phase:** 3 (API Integration - HA Addon → Dolibarr)
**Status:** Discussion completed

## Discussion Summary

User selected 3 areas to discuss from 5 presented options:
1. API Endpoint Design
2. Retry-Strategie
3. Session Status Tracking

### Area 1: API Endpoint Design

**Question:** Wie soll der API-Endpunkt in Dolibarr implementiert werden?

**Options presented:**
- Custom Endpoint (Empfohlen) — Eigener Endpunkt in modWallboxbilling mit voller Kontrolle
- Dolibarr Standard API erweitern — Nutzung bestehender REST API mit Custom Objects
- Hybrid (Standard + Custom) — Standard API für CRUD, Custom für Session-Upload

**User selection:** Custom Endpoint (Empfohlen)

**Decision:** D-01 — Custom Endpoint in modWallboxbilling (z.B. `/wallboxbilling/api/session.php`)

### Area 2: Retry-Strategie

**Question:** Welche Retry-Parameter sollen für fehlgeschlagene API-Übertragungen genutzt werden?

**Options presented:**
- Konservativ (Empfohlen) — 1s initial, max 60s, 5 retries, factor 2x
- Aggressiv — 0.5s initial, max 30s, 3 retries, factor 2x
- Langsame Leitung — 2s initial, max 300s, 8 retries, factor 1.5x

**User selection:** Konservativ (Empfohlen)

**Decision:** D-02 — Konservative Retry-Parameter (1s init, 60s max, 5 retries, 2x factor)

### Area 3: Session Status Tracking

**Question:** Wie tracken wir, welche Sessions bereits übertragen wurden?

**Options presented:**
- transmitted_at Feld (Empfohlen) — Neues Feld in llx_wallbox_sessions, DATETIME NULL
- Separate Tabelle — llx_wallbox_transmissions mit session_id und Status
- Status-Feld erweitern — active → completed → transmitted

**User selection:** transmitted_at Feld (Empfohlen)

**Decision:** D-03 — `transmitted_at` Feld in `llx_wallbox_sessions` Tabelle

## Additional Decisions (Claude's Discretion)

- D-04: JSON-Payload Format (rfid_hash, wallbox_id, start_time, end_time, kWh, ISO 8601 timestamps)
- DOLAPIKEY Token in HTTP Header `DOLAPIKEY: {token}`
- HA-Addon nutzt aiohttp für API-Calls
- Polling-Logik: Periodische Prüfung auf `transmitted_at IS NULL`

## Deferred Ideas

None — discussion stayed within phase scope

## Session Notes

- Phase 2 bereits abgeschlossen (laut STATE.md)
- gsd-sdk nicht verfügbar, manuelle Durchführung der Diskussion
- Alle Entscheidungen wurden dokumentiert für Phase 3 Planung

---
*Discussion completed: 2026-05-05*
