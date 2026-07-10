# AGENTS.md - Wallbox-Dolibarr Integration

## Project Context

**Project:** Wallbox-Dolibarr Integration
**Core Value:** Automatisierte, RFID-basierte Abrechnung von Wallbox-Ladevorgängen ohne manuellen Aufwand

## Current Phase

**Phase 1: Foundation (HA Integration + Dolibarr Skeleton)**
Goal: Establish technical foundation for both HA Addon and Dolibarr Module
Requirements: HA-01, DB-03, SEC-04

## Important Instructions

1. **Sprache:** Deutsch (Code-Kommentare, Dokumentation, UI)
2. **Datenbank:** SQLite3 für HA-Addon (Session-Persistenz), MariaDB für Dolibarr
3. **Sicherheit:** RFID nur als SHA-256 Hash speichern, keine Klartext-Logs
4. **Stack HA-Addon:** Alpine 3.23, Python 3.13, requests 2.32+
5. **Stack Dolibarr:** PHP 8.1+, Dolibarr 21.x-22.x, TCPDF für PDF

## Workflow

- **Mode:** YOLO (auto-approve)
- **Granularity:** Fine (8-12 Phasen)
- **Execution:** Parallel
- **Research:** Yes (before each phase)
- **Plan Check:** Yes
- **Verifier:** Yes

## Next Steps

1. `/gsd-discuss-phase 1` — Kontext sammeln und Ansatz klären
2. `/gsd-plan-phase 1` — Phase 1 detailliert planen
3. `/gsd-execute-phase 1` — Phase 1 ausführen

## References

- `.planning/PROJECT.md` — Projektbeschreibung
- `.planning/REQUIREMENTS.md` — 40 v1 Requirements
- `.planning/ROADMAP.md` — 5 Phasen, alle Requirements gemapped
- `.planning/research/` — Stack, Features, Architecture, Pitfalls, Summary
- `.planning/config.json` — Workflow-Einstellungen
