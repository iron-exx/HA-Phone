# Phase 6: Monitoring & Status - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-21
**Phase:** 06-monitoring-status
**Areas discussed:** Admin Tab Integration, API-Health-Check, Session-Tabelle Umfang, Fehler-Speicherung

---

## Admin Tab Integration

| Option | Description | Selected |
|--------|-------------|----------|
| Tab-System in admin.php | Drei Tabs: Konfiguration / RFID / Status. Standard-Dolibarr-Pattern. | ✓ |
| Separate status.php | Eigene Seite, unabhängig von admin.php | |
| Alles inline in admin.php | Status-Block unter bestehenden Formularen, kein Tab-System | |

**User's choice:** Tab-System in admin.php

**Folgeentscheidung — Standard-Tab:**

| Option | Description | Selected |
|--------|-------------|----------|
| Konfiguration ist Standard | Bestehender Standard bleibt | |
| Status ist Standard | Admin sieht sofort Systemstatus beim Öffnen | ✓ |
| Du entscheidest | Technisch egal, per GET-Parameter steuerbar | |

**User's choice:** Status ist Standard-Tab

---

## API-Health-Check

| Option | Description | Selected |
|--------|-------------|----------|
| Aktiver cURL-Ping | Echter HTTP-Request an HA-Addon beim Tab-Laden | ✓ |
| Passiv: letzte Übertragungszeit | Kein Live-Ping, nur DB-Abfrage des letzten Timestamps | |
| Beides kombiniert | Ping + Zeitstempel | |

**User's choice:** Aktiver cURL-Ping

**Folgeentscheidung — /health-Endpunkt:**

| Option | Description | Selected |
|--------|-------------|----------|
| Muss neu erstellt werden | Im HA-Addon gibt es noch keinen /health-Endpunkt | ✓ |
| Existiert bereits | HA-Addon hat schon erreichbaren Endpunkt | |
| Dolibarr pingt sich selbst | TCP-Check ohne HA-Endpunkt | |

**User's choice:** Muss neu erstellt werden

---

## Session-Tabelle Umfang

| Option | Description | Selected |
|--------|-------------|----------|
| Feste Anzahl Top-25 | Letzte 25 Sessions, kein Pagination-Aufwand | ✓ |
| Konfigurierbare Anzahl | Admin wählt 10/25/50 im Konfig-Tab | |
| Pagination | Vollständige Tabelle mit Navigation | |

**User's choice:** Top-25

**Folgeentscheidung — Spalten:**

| Option | Description | Selected |
|--------|-------------|----------|
| Datum + Wallbox + Status | Minimal, exakt MON-02 | |
| Datum + Wallbox + kWh + Nutzer + Status | Erweiterte Ansicht mit Energie und Nutzer | ✓ |
| Datum + Wallbox + Status + Fehlermeldung | MON-02 und MON-03 kombiniert in einer Tabelle | |

**User's choice:** Datum + Wallbox-ID + kWh + Nutzer + Status

---

## Fehler-Speicherung

| Option | Description | Selected |
|--------|-------------|----------|
| Neue Spalten in bestehender Tabelle | upload_status + upload_error + uploaded_at in llx_wallbox_sessions | ✓ |
| Separate Upload-Log-Tabelle | llx_wallbox_upload_log, besser für spätere Retry-Logik | |

**User's choice:** Neue Spalten in bestehender Tabelle

**Folgeentscheidung — Status-Werte:**

| Option | Description | Selected |
|--------|-------------|----------|
| pending / ok / error | Drei Zustände, einfach und ausreichend | ✓ |
| pending / ok / error / retrying | Vier Zustände, inkl. Phase 8 Vorbereitung | |
| Du entscheidest | Technisches Detail | |

**User's choice:** pending / ok / error

---

## Claude's Discretion

- Timeout-Wert für cURL-Ping (empfohlen: 3-5s)
- Genaue Tab-Implementierung (dol_get_fiche_head Pattern)
- Spalten-Reihenfolge und CSS-Klassen in der Session-Tabelle

## Deferred Ideas

- **Überschussladen Session-Logik Fix:** Session bleibt aktiv bis neue RFID gestartet wird (kein Zustandswechsel-Trigger). Monatssplit bei Mitternacht letzter Monatstag. Betrifft session_manager.py + main.py. Als eigene Phase oder Hotfix nach v1.1 einplanen.
