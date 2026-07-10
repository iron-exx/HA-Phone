# Phase 3: API Integration (HA Addon → Dolibarr) - Context

**Gathered:** 2026-05-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Diese Phase liefert die Übertragung abgeschlossener Lade-Sessions von HA-Addon an Dolibarr via REST-API. Sessions werden in SQLite erfasst (Phase 2) und nun automatisiert an Dolibarr übertragen.

**In scope:**
- HA Addon sendet completed sessions via REST API (JSON mit rfid_hash, wallbox_id, start_time, end_time, kwh)
- API-Authentifizierung mit DOLAPIKEY Token
- Retry-Mechanismus mit exponential backoff bei Fehlern
- RFID nur als SHA-256 Hash übertragen
- Dolibarr Custom API Endpoint validiert Token und verarbeitet Sessions
- Session-Status-Tracking (welche Sessions wurden übertragen)

**Out of scope:**
- Eigentliche Abrechnung/Rechnungserstellung (Phase 4)
- Multi-Wallbox Unterstützung (Phase 5)
- UI für API-Konfiguration

</domain>

<decisions>
## Implementation Decisions

### API Endpoint Design
- **D-01:** Custom Endpoint in modWallboxbilling (z.B. `/wallboxbilling/api/session.php`)
  - Volle Kontrolle über Validierung und RFID-Hash Verarbeitung
  - Eigenes Routing unabhängig von Dolibarr Standard API
  - Erlaubt spezifische Fehlerbehandlung für Wallbox-Sessions

### Retry-Strategie
- **D-02:** Konservative Retry-Parameter
  - Initial Delay: 1 Sekunde
  - Max. Retries: 5
  - Max. Delay: 60 Sekunden
  - Factor: 2x (1s, 2s, 4s, 8s, 16s, 32s)
  - Retryable Errors: HTTP 5xx, Timeout, Connection Refused
  - Permanente Fehler (HTTP 4xx außer 429): Kein Retry

### Session Status Tracking
- **D-03:** `transmitted_at` Feld in `llx_wallbox_sessions`
  - Neues DATETIME NULL Feld in bestehender Tabelle
  - NULL = noch nicht übertragen, Timestamp = erfolgreich übertragen
  - Einfachste Lösung ohne neue Tabelle
  - Query für ausstehende Sessions: `WHERE transmitted_at IS NULL AND end_time IS NOT NULL`

### JSON-Payload Format
- **D-04:** Standardisiertes JSON-Format
  - Felder: `rfid_hash`, `wallbox_id`, `start_time`, `end_time`, `kwh`
  - Zeitstempel: ISO 8601 Format (`2026-05-05T14:30:00+02:00`)
  - RFID: Immer als SHA-256 Hash (kein Klartext)
  - kWh: Float mit 3 Nachkommastellen

### Claude's Discretion
- DOLAPIKEY Token-Handling: In HA-Addon Config via YAML, Übergabe als HTTP Header `DOLAPIKEY: {token}`
- HTTP Client: `aiohttp` in HA-Addon (bereits vorhanden aus Phase 1)
- Transmissions-Logik: HA-Addon pollert periodisch alle X Minuten nach `transmitted_at IS NULL`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### API Integration
- `.planning/ROADMAP.md` § Phase 3 — Phase Goal, Requirements (API-01 to API-05, SEC-03)
- `.planning/REQUIREMENTS.md` § API-Integration (API-01 to API-05) — Detaillierte Requirements
- `.planning/REQUIREMENTS.md` § Sicherheit & Datenschutz (SEC-03) — API-Token Validierung

### HA Addon Code
- `Homeassistant/session_manager.py` — Session-Tracking Logik aus Phase 2 (wie Sessions als "completed" markiert werden)
- `Homeassistant/config.yaml` — Config-Struktur für API-Token Parameter

### Dolibarr Module
- `Dolibarr/wallboxbilling/` — Bestehendes Modul aus Phase 1 & 2
- `Dolibarr/wallboxbilling/sql/llx_wallbox_sessions.sql` — DB-Tabelle für `transmitted_at` Erweiterung

### Prior Phase Context
- `.planning/phases/02-session-tracking/02-CONTEXT.md` — Session-Tracking Entscheidungen
- `.planning/phases/01-foundation/01-CONTEXT.md` — Foundation (Hash Utility, API-Token Konzept)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Homeassistant/utils/hash.py`: SHA-256 Hashing für RFID (auch für API-Payload nutzen)
- `Homeassistant/Dockerfile`: Python 3.13, Alpine 3.23 (aiohttp bereits installiert)
- `Dolibarr/wallboxbilling/core/modules/modWallboxbilling.class.php`: Modul-Struktur für API-Endpoint Registration

### Established Patterns
- Config per YAML in HA-Addon (`config.yaml` mit `api_token`, `dolibarr_url` Parametern)
- SQLite als Persistenz (Session-Status wird in DB getrackt)
- Dolibarr Modul-Struktur mit `lib/`, `sql/`, `core/modules/` Verzeichnissen

### Integration Points
- HA-Addon: Neuer Service in `main.py` oder `api_client.py` für API-Calls
- Dolibarr: Neuer Endpoint in `wallboxbilling/api/` Verzeichnis
- DB: `ALTER TABLE llx_wallbox_sessions ADD COLUMN transmitted_at DATETIME NULL;` in Modul-Update

</code_context>

<specifics>
## Specific Ideas

- API-Endpoint URL Struktur: `https://dolibarr.example.com/custom/wallboxbilling/api/session.php`
- HTTP Header für Token: `DOLAPIKEY: {token_value}`
- Content-Type: `application/json`
- HA-Addon sollte bei Dolibarr-Erreichbarkeitsprüfung vor erstem API-Call prüfen (GET auf `/api/index.php/login` oder ähnlich)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---
*Phase: 3-API Integration*
*Context gathered: 2026-05-05*
