# Requirements: Wallbox-Dolibarr Integration v1.1

**Milestone:** v1.1 Robustheit & Monitoring
**Created:** 2026-06-16
**Status:** Active

---

## v1.1 Requirements

### Monitoring / Status

- [x] **MON-01**: Nutzer sieht im Dolibarr-Admin-Tab den aktuellen Systemstatus (API erreichbar / nicht erreichbar) — Validated in Phase 6 (2026-06-22)
- [x] **MON-02**: Nutzer sieht im Admin-Tab die letzten N übertragenen Sessions (Datum, Wallbox-ID, Status) — Validated in Phase 6 (2026-06-22)
- [x] **MON-03**: Nutzer sieht im Admin-Tab fehlgeschlagene Übertragungen mit Fehlermeldung — Validated in Phase 6 (2026-06-22)

### Alerts

- [ ] **ALT-01**: HA sendet persistent_notification wenn ein Session-Upload fehlschlägt
- [ ] **ALT-02**: Dolibarr sendet E-Mail an konfigurierten Admin wenn Upload-Fehler auftreten

### Logging

- [ ] **LOG-01**: Log-Level im HA-Addon per config.yaml konfigurierbar (debug / info / warning)
- [ ] **LOG-02**: Logs enthalten keine RFID-Klartexte, API-Tokens oder personenbezogene Daten
- [ ] **LOG-03**: Dolibarr-Modul loggt Upload-Ereignisse strukturiert ins Dolibarr-Logfile

### Retry / Dead-letter

- [ ] **RET-01**: Fehlgeschlagene Session-Uploads werden in einer Dead-letter-Tabelle gespeichert
- [ ] **RET-02**: Admin kann fehlgeschlagene Uploads manuell im Dolibarr-Admin neu anstoßen
- [ ] **RET-03**: Automatischer Retry-Versuch beim nächsten Übertragungszyklus für pending Dead-letter-Einträge

---

## Future Requirements (deferred)

- BIL-07: Echte Dolibarr-Invoice-Erstellung (native Dolibarr-Rechnung statt nur PDF) — verschoben auf v1.2+

---

## Out of Scope (v1.1)

- [Echtzeit-Ladeanzeige / Live-Dashboard] — Kernfokus bleibt Abrechnung, nicht Monitoring-Dashboard
- [Externe Monitoring-Integration (Prometheus, Grafana)] — Zu komplex für diese Milestonesize
- [Automatische Alert-Eskalation] — Manueller Admin-Eingriff genügt für v1.1

---

## Traceability

| REQ-ID | Phase | Plan | Status |
|--------|-------|------|--------|
| MON-01 | Phase 6 | 06-01/06-02/06-03/06-04 | Complete ✓ |
| MON-02 | Phase 6 | 06-01/06-03/06-04 | Complete ✓ |
| MON-03 | Phase 6 | 06-01/06-03/06-04 | Complete ✓ |
| ALT-01 | Phase 7 | TBD | Pending |
| ALT-02 | Phase 7 | TBD | Pending |
| LOG-01 | Phase 7 | TBD | Pending |
| LOG-02 | Phase 7 | TBD | Pending |
| LOG-03 | Phase 7 | TBD | Pending |
| RET-01 | Phase 8 | TBD | Pending |
| RET-02 | Phase 8 | TBD | Pending |
| RET-03 | Phase 8 | TBD | Pending |
