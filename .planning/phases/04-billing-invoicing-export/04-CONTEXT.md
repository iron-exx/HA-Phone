# Phase 4: Billing + Invoicing + Export - Context

**Phase:** 04-billing-invoicing-export
**Created:** 2026-05-06
**Language:** German

## Design Decisions Summary

### Architecture

| Decision | Selected | Rationale |
|----------|----------|-----------|
| Cron Job | Dolibarr modCron | Integriert, keine externen crontab nötig |
| PDF Engine | TCPDF | Dolibarr Standard |
| CSV Export | PHP fputcsv | Einfach, robust |
| DATEV Format | EXTF 5.0 | Standard für deutsche Buchhaltung |

### Key Classes

| Class | File | Purpose |
|-------|------|--------|
| WallboxBilling | class/billing.class.php | Hauptlogik für BIL-01 bis BIL-06 |
| PdfWallboxBilling | core/modules/doc/pdf_wallboxbilling.class.php | TCPDF Template für BIL-06 |
| WallboxExport | class/export.class.php | CSV/DATEV Export für EXT-02/EXT-03 |

### Dependencies

| Dependency | From Phase | Used By |
|------------|------------|---------|
| llx_wallbox_sessions | Phase 2 | BIL-02, BIL-03 |
| modWallboxbilling.class.php | Phase 1 | Cron Registration |

### Workflow

1. **BIL-01 (Cron):** modCron Job läuft monatlich (am 1. Tag des Monats für Vormonat)
2. **BIL-02 (Group):** Sessions nach user_id gruppiert
3. **BIL-03 (Cost):** Kosten = kWh × price_per_kwh (user-spezifisch)
4. **BIL-04 (List):** Detaillierte Ladeliste pro User im PDF
5. **BIL-05 (Summary):** Zusammenfassung mit Summen im PDF
6. **BIL-06 (PDF):** TCPDF-generiertes PDF pro User
7. **BIL-07 (Optional):** Dolibarr Facture (erst v2)
8. **EXT-02 (CSV):** Export über Export Wizard
9. **EXT-03 (DATEV):** DATEV EXTF Format

### Out of Scope (v1)

- BIL-07: Dolibarr Facture Objekt (Optional, erst v2)
- EXT-02: Detail + Aggregiert (nur aggregiert)
- EXT-03: DATEV Buchungskreis-Auswahl (Standard Handelsrecht)

---

*Context dokumentiert für Phase 4 Planning*