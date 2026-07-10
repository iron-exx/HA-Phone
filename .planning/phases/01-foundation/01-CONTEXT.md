# Phase 1: Foundation (HA Integration + Dolibarr Skeleton) - Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish technical foundation for both HA Addon and Dolibarr Module. This phase delivers:
- HA Addon scaffold with Alpine 3.23 + Python 3.13, connected to HA Core via Websocket API
- Dolibarr Module skeleton (wallboxbilling) based on noumainventoryapp structure
- SQLite database initialization for session persistence (preparation for Phase 2)
- SHA-256 hash utility for RFID privacy (preparation for SEC-02)
- Foundation for multi-wallbox support (wallbox_id dynamic from Alfen sensor)

New capabilities belong in other phases — this phase is scaffolding only.

</domain>

<decisions>
## Implementation Decisions

### HA-Addon Struktur
- **D-01:** Dockerfile + build.json für HA Supervisor Integration (Standard HA-Addon Ansatz mit Config-UI)
- **D-02:** HA Core Integration nutzen — bestehende Alfen-Integration in HA, Zugriff auf Sensoren via Websocket API
- **D-03:** Async loop mit aiohttp für effizientes Sensor-Polling (Event-basiert, Websocket push)
- **D-04:** Standard-Dateien: main.py, config.yaml, requirements.txt, Dockerfile, build.json, README.md

### Dolibarr-Modul Aufbau
- **D-05:** Modul-Name: `wallboxbilling`, Tabelle: `llx_wallboxbilling_sessions` (DB-01 Vorbereitung)
- **D-06:** Noumainventoryapp als Vorlage für Modul-Struktur nutzen
- **D-07:** SQL in `module/wallboxbilling.sql` für Tabellenerstellung (DB-03)
- **D-08:** Drei Berechtigungen: `wallboxbilling.user`, `wallboxbilling.admin`, `wallboxbilling.billing` (SEC-04)

### Sensor-Integration HA
- **D-09:** Nur 3 Sensoren in Phase 1: `sensor.alfen_eve_tag_socket_1` (RFID), `sensor.alfen_energy_total`, Charging State
- **D-10:** Event-basiert via HA Websocket API (kein Polling, effizienter)
- **D-11:** Crash + Supervisor restart bei Verbindungsabbruch (einfach, HA Supervisor übernimmt Recovery)
- **D-12:** SQLite Setup in Phase 1 (Datenbank-Initialisierung und erste Schreibversuche, Vorbereitung PER-01)

### Gemeinsame Konfiguration
- **D-13:** wallbox_id dynamisch aus Alfen-Sensor extrahiert (nicht hardcoded, Multi-Wallbox-Erweiterbarkeit EXT-01 vorbereitet)
- **D-14:** Hash-Funktion in `utils/hash.py` (zentrale SHA-256 Logik, Vorbereitung SEC-02)
- **D-15:** API-Token (DOLAPIKEY) als Umgebungsvariable im Container (sicherer als config.yaml)
- **D-16:** Gemeinsame Status-Konstanten definieren: `CHARGING`, `IDLE`, `STOPPED` in Python + PHP

### Logging & Datenschutz
- **D-17:** Strukturiertes Logging mit Hash (Python logging Modul, RFID wird IMMER gehasht geloggt — Vorbereitung SEC-01/SEC-02)
- **D-18:** Dolibarr: `dol_syslog()` mit Hash für RFID (keine Klartext-Logs)
- **D-19:** Identischer Hash-Algorithmus (SHA-256) in HA und Dolibarr für kompatible RFID-Hashes
- **D-20:** Konfigurierbarer Log-Level über config.yaml (DEBUG/INFO/WARNING/ERROR)

### Dolibarr Frontend
- **D-21:** 4 Seiten: `admin.php` (Konfiguration + Rechte), `index.php` (Sessions-Liste), `card.php` (User-Link), `bill.php` (Abrechnung-Vorschau)
- **D-22:** Dolibarr Standard-Theme nutzen (nur wallbox icon als eigenes Asset in `img/`)
- **D-23:** Deutsch (de_DE) in `langs/` (Code-Kommentare und UI auf Deutsch laut AGENTS.md)
- **D-24:** Dolibarr `GETPOST()` Standard für Formular-Validierung (Vorbereitung SEC-05)

### Testing Setup
- **D-25:** pytest für HA-Addon (Python), einfache Unit-Tests für Hash/Config
- **D-26:** PHPUnit für Dolibarr-Modul (PHP), Unit-Tests für DB/Rechte
- **D-27:** Mock HA-API für Tests ohne echte Wallbox (aiohttp test utils oder pytest-asyncio)
- **D-28:** Unabhängige Configs: `requirements.txt` (HA) + `composer.json` (Dolibarr) in jeweiligen Verzeichnissen

### Claude's Discretion
- Stack-Aligned: Alpine 3.23, Python 3.13, requests 2.32+ für HA-Addon; PHP 8.1+, Dolibarr 21.x-22.x für Dolibarr-Modul
- RFID-Format: z.B. "EFCD083E" (aus PROJECT.md), 8 Zeichen Hex-String
- Addon-Verzeichnis: `~/projects/Wallbox-Dolibarr/Homeassistant` (aus PROJECT.md Context)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Context
- `.planning/PROJECT.md` — Wallbox-Dolibarr Integration Projektbeschreibung, Key Decisions, Constraints
- `.planning/ROADMAP.md § Phase1` — Goal, Requirements (HA-01, DB-03, SEC-04), Success Criteria
- `.planning/REQUIREMENTS.md` — HA-01, DB-03, SEC-04 (Phase 1 Requirements), DB-01 (Tabelle), SEC-01/SEC-02 (Logging/Hash)

### Dolibarr Reference Module
- `~/projects/Wallbox-Dolibarr/Dolibarr/noumainventoryapp/` — Vorlage für Modul-Struktur (admin/, core/, lang/ Verzeichnisse)

### Technical References
- Home Assistant Addon Documentation: https://developers.home-assistant.io/docs/add-ons/
- Dolibarr Module Development: https://wiki.dolibarr.org/index.php?title=Module_development
- SHA-256 Hashing: Python `hashlib.sha256()`, PHP `hash('sha256', $data)`

### HA Sensor References
- Alfen Eve Integration in Home Assistant (sensor.alfen_eve_tag_socket_1, sensor.alfen_energy_total)
- HA Websocket API: https://developers.home-assistant.io/docs/api/websocket/

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `noumainventoryapp/` (Dolibarr): Modul-Struktur, admin.php Pattern, SQL-Dateien, lang/ Struktur
- Alpine 3.23 + Python 3.13: Leichtgewichtig, aktuell, requests 2.32+ unterstützt

### Established Patterns
- Dolibarr Modul-Standard: `module/wallboxbilling.class.php`, `admin/` für Konfiguration, `sql/` für DDL
- HA Addon Standard: `build.json` für Supervisor Config-UI, `Dockerfile` mit Alpine Base
- RFID als 8-char Hex (z.B. "EFCD083E"), SHA-256 Hash für Privacy

### Integration Points
- HA Addon → HA Core: Websocket API (sensor states, event streaming)
- Dolibarr Module → Dolibarr Core: `dol_syslog()`, `GETPOST()`, `$db` Abstraktion
- Gemeinsam: `wallbox_id` (dynamisch), Status-Konstanten, SHA-256 Hash-Logik

</code_context>

<specifics>
## Specific Ideas

- wallboxbilling als Modul-Name (nicht "wallbox" oder "evcharging") — Admin-Bereich braucht Abrechnung (billing) Fokus
- 4 Frontend-Seiten inkl. bill.php (Abrechnung-Vorschau) bereits in Phase 1 vorbereiten
- SQLite in Phase 1 initialisieren (nicht warten bis Phase 2), Datei: `sessions.db` im Addon
- Umgebungsvariable für DOLAPIKEY (nicht in config.yaml), bessere Sicherheit
- Crash + Supervisor restart (einfacher als Auto-Reconnect mit Backoff) — Phase 1 Fokus auf Foundation, nicht Resilience (kommt in Phase 5)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Foundation*
*Context gathered: 2026-05-04*