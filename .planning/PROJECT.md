# Wallbox-Dolibarr Integration

## What This Is

Eine vollständig integrierte Lösung aus einem Home-Assistant-Addon und einem Dolibarr-ERP-Modul zur automatischen Erfassung, Auswertung und monatlichen Abrechnung von Ladevorgängen einer Alfen Eve Wallbox. Die Identifikation erfolgt über RFID-Karten, die Lösung ist produktionsreif, ausfallsicher, datenschutzkonform und skalierbar.

## Core Value

Automatisierte, RFID-basierte Abrechnung von Wallbox-Ladevorgängen ohne manuellen Aufwand – Ladevorgänge werden erfasst, Nutzer identifiziert und monatlich korrekt abgerechnet.

## Current Milestone: v1.1 Robustheit & Monitoring

**Goal:** Das System beobachtbar und ausfallsicher machen — Fehler werden erkannt, gemeldet und können behoben werden.

**Progress:** Phase 8 complete 2026-06-23 (3/3 phases) — milestone COMPLETE ✓

**Target features:**
- ✓ Health-Check / Status-Seite im Dolibarr-Modul (Admin-Tab) mit Übertragungsstatus und Fehlerhistorie — Phase 6 done
- ✓ Alert bei Fehler: HA persistent_notification + Dolibarr E-Mail wenn Upload fehlschlägt — Phase 7 done
- ✓ Strukturiertes Logging mit konfigurierbarem Log-Level (kein Klartext von RFID) — Phase 7 done
- ✓ Retry / Dead-letter Queue für fehlgeschlagene Session-Uploads (manueller Retry im Admin) — Phase 8 done

## Previous State (v1.0 — shipped 2026-05-11)

Das System ist vollständig einsatzbereit:

- **HA Addon** (Alpine 3.23, Python 3.13, SQLite) — erfasst RFID-Karten, authentifiziert gegen Whitelist, trackt Sessions mit Start/Ende/kWh/Wallbox-ID, 7s Debouncing, Neustart-Recovery, WAL-Modus
- **Dolibarr Modul** (PHP 8.1+) — Benutzerverwaltung mit RFID-Hash(es), individuellem kWh-Preis, Kostenstelle; API-Endpunkt für Session-Upload; monatlicher Cronjob für Abrechnung; PDF-Invoices via TCPDF; CSV/DATEV-Export
- **Integration** — REST-API mit DOLAPIKEY-Auth, exponentieller Backoff-Retry, SHA-256 Hash für RFID

Stacks: Alpine 3.23 + Python 3.13 + requests 2.32+ (HA-Addon) | PHP 8.1+ + Dolibarr 21.x-22.x + TCPDF (Dolibarr)
Code: ~4.100 LOC (Python + PHP + Shell + Config)

## Requirements

### Validated (v1.0)

- ✓ **HA-01**: RFID-Erfassung via sensor.alfen_eve_tag_socket_1
- ✓ **HA-02**: Whitelist-Prüfung per YAML
- ✓ **HA-03–07**: Session-Tracking, Start/Ende, Energieberechnung, Debouncing
- ✓ **PER-01–05**: SQLite-Persistenz, Neustart-Recovery, WAL-Modus, atomare Energie
- ✓ **API-01–05**: REST-Übertragung, JSON-Payload, DOLAPIKEY, Retry/Backoff, RFID-Hash
- ✓ **USR-01–05**: Benutzeraktivierung, RFID-Verknüpfung, kWh-Preis, Kostenstelle, SHA-256
- ✓ **DB-01–03**: llx_wallbox_sessions Tabelle, Indizes, Auto-Erstellung
- ✓ **BIL-01–06**: Monatlicher Cronjob, Gruppierung, Preislogik, PDF via TCPDF
- ✓ **BIL-07**: Optional — PDF-Invoices implementiert, Dolibarr-Invoice deferred
- ✓ **SEC-01–05**: Keine Klartext-Logs, SHA-256, API-Token, Rollen/Rechte, SQL-Injection-Prävention
- ✓ **EXT-01–03**: Multi-Wallbox, CSV-Export, DATEV-Export

### Validated (v1.1 — Phase 6 complete 2026-06-22)

- ✓ **MON-01**: Health-Check Status-Seite im Dolibarr-Modul Admin-Tab — cURL-Ping + Status-Icon im Status-Tab
- ✓ **MON-02**: Session-Tabelle im Admin-Tab (Datum, Wallbox-ID, kWh, upload_status) — inklusive Stop-Button
- ✓ **MON-03**: Fehlgeschlagene Übertragungen mit Fehlermeldung im Admin-Tab sichtbar (upload_error Spalte)

### Validated (v1.1 — Phase 7 complete 2026-06-23)

- ✓ **ALT-01**: HA persistent_notification bei Upload-Fehler — send_persistent_notification() in main.py
- ✓ **ALT-02**: Dolibarr E-Mail an Admin bei DB-Fehler — CMailFile in api_wallboxbilling.class.php + WALLBOXBILLING_ADMIN_EMAIL admin config
- ✓ **LOG-01**: Konfigurierbares Log-Level per options.json — apply_log_level_from_config() in main.py
- ✓ **LOG-02**: Keine sensiblen Daten in Logs — statische Analyse + caplog Tests bestätigt
- ✓ **LOG-03**: Dolibarr strukturiertes Logging (dol_syslog LOG_INFO/LOG_ERR) in postSession()

### Active (v1.1 — Phase 8 next)
- [ ] **RET-01**: Dead-letter Queue für fehlgeschlagene Session-Uploads
- [ ] **RET-02**: Manueller Retry-Trigger im Dolibarr-Admin

### Out of Scope

- [Mobile App für Nutzer] — Web-Interface von Dolibarr ausreichend für v1
- [Echtzeit-Ladeanzeige im Dashboard] — Kernfokus liegt auf Abrechnung, nicht Monitoring
- [Lastmanagement / Load Balancing] — Nicht Teil der Abrechnungslösung
- [Zahlungsabwicklung (SEPA/Überweisung)] — Dolibarr-Standardfunktionen nutzen
- [Plug & Charge (ISO 15118)] — Erfordert PKI-Infrastruktur, RFID reicht für v1
- [Roaming (OCPI)] — Irrelevant für Single-Site Dolibarr-Setup
- [OCPP-Backend] — Lokale Modbus/API-Lösung bevorzugt für v1

## Context

- Wallbox: Alfen Eve mit Home-Assistant-Integration
- Sensoren: sensor.alfen_eve_tag_socket_1 (RFID), sensor.alfen_energy_total (Energie), Ladezustand (Charging/Idle/Stopped)
- RFID-Format: z.B. "EFCD083E"
- Addon-Verzeichnis: ~/projects/Wallbox-Dolibarr/Homeassistant
- Dolibarr-Verzeichnis: ~/projects/Wallbox-Dolibarr/Dolibarr
- Übertragung: REST-API von HA-Addon an Dolibarr mit JSON-Payload

## Constraints

- **Datenschutz**: RFID nur gehasht speichern, keine Klartext-Logs
- **Ausfallsicherheit**: Sessions in SQLite persistieren, HA-Neustarts überleben
- **Skalierbarkeit**: Mehrere Wallboxen müssen später unterstützbar sein
- **Sprache**: Deutsch (Code-Kommentare, Dokumentation, UI)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SQLite für Session-Persistenz | Leichtgewichtig, lokal, keine externe DB nötig | ✓ Good |
| REST-API mit DOLAPIKEY | Standard, in Dolibarr nativ unterstützt | ✓ Good |
| RFID-Whitelist per YAML | Einfach pflegbar, kein komplexes UI nötig für v1 | ✓ Good |
| Dolibarr Cronjob für Abrechnung | Native Dolibarr-Funktion, kein externer Scheduler | ✓ Good |
| SHA-256 für RFID-Hash | Sicher, deterministisch, kein Klartext | ✓ Good |
| WAL-Modus für SQLite | Bessere Concurrency bei gleichzeitigen Zugriffen | ✓ Good |
| TCPDF für PDF-Rechnungen | Dolibarr-eigene PDF-Bibliothek, kein zusätzliches Tool | ✓ Good |
| Mehrere Wallboxen per Konfiguration | Flexibel ohne Code-Änderungen | ✓ Good |

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-06-16 — Milestone v1.1 started*
