# Phase 6: Monitoring & Status - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Admin-facing Status-Seite im Dolibarr-Modul: zeigt API-Erreichbarkeit (Live-Ping), Session-Historie der letzten 25 Übertragungen und Upload-Fehler mit Fehlermeldung — alles in einem neuen Tab in admin.php.

Scope: Dolibarr admin.php Tab-Umbau + cURL Health-Check + DB-Schema-Erweiterung + HA-Addon /health-Endpunkt.
Nicht in Scope: Alerts/E-Mail (Phase 7), Retry-Logik (Phase 8).

</domain>

<decisions>
## Implementation Decisions

### Admin Tab Integration
- **D-01:** Tab-System in `admin.php` — drei Tabs: "Konfiguration" | "RFID" | "Status". Bestehende Formulare bleiben als eigene Tabs erhalten.
- **D-02:** "Status" ist der Standard-Tab beim Öffnen von admin.php (nicht Konfiguration).

### API Health-Check
- **D-03:** Aktiver cURL-Ping beim Laden des Status-Tabs an den HA-Addon-API-Endpunkt.
- **D-04:** Der `/health`-Endpunkt im HA-Addon existiert noch nicht — muss in dieser Phase neu erstellt werden (in `main.py` oder separatem HTTP-Handler).
- **D-05:** Anzeige: ✅ Erreichbar / ❌ Nicht erreichbar / ⚠️ Fehler: [HTTP-Code].

### Session-Tabelle
- **D-06:** Anzeige der letzten 25 übertragenen Sessions — keine Pagination, keine konfigurierbare Anzahl.
- **D-07:** Spalten: Datum | Wallbox-ID | kWh | Nutzer (Name) | Status.
- **D-08:** Nutzer-Anzeige: Klarname aus Dolibarr-User-Tabelle (kein RFID-Hash in der UI).

### Fehler-Speicherung (DB-Schema)
- **D-09:** Neue Spalten in `llx_wallbox_sessions`: `upload_status` (ENUM: pending/ok/error), `upload_error` (TEXT, NULL wenn ok), `uploaded_at` (DATETIME).
- **D-10:** Status-Werte: `pending` (noch nicht übertragen), `ok` (erfolgreich), `error` (fehlgeschlagen).
- **D-11:** Dolibarr schreibt `upload_status` und `upload_error` beim API-Upload-Versuch.

### Manuelle Session-Steuerung (neu, 2026-06-21)
- **D-12:** Admin kann eine aktive Ladesitzung aus dem Status-Tab heraus manuell beenden — Button "Session beenden" in der Session-Tabelle für Einträge mit `upload_status = pending` oder aktive Sessions.
- **D-13:** Nach manuellem Beenden wird die Session sofort an Dolibarr übermittelt — kein Warten auf den nächsten automatischen Zyklus.
- **D-14:** Technisch: Dolibarr sendet POST-Request an HA-Addon-Endpunkt `/session/stop` mit `session_id`. HA-Addon beendet die Session in SQLite und triggert sofortigen Upload.
- **D-15:** Der `/session/stop`-Endpunkt wird in `main.py` neben `/health` als neuer aiohttp-Route implementiert.
- **D-16:** UI-Feedback: Nach erfolgreichem Stop/Upload aktualisiert sich die Status-Tabelle (Redirect oder AJAX). Fehlermeldung wenn HA-Addon nicht erreichbar.

### Claude's Discretion
- Timeout-Wert für den cURL-Ping (empfohlen: 3-5s)
- Genaue Tab-Implementierung (Dolibarr `dol_get_fiche_head` Pattern)
- Spalten-Reihenfolge und CSS-Klassen in der Session-Tabelle

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Dolibarr Modul
- `Dolibarr/htdocs/custom/wallboxbilling/admin.php` — Bestehende Admin-Seite, wird auf Tab-System umgebaut
- `Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php` — Modul-Definition, Tabellen-Schema
- `Dolibarr/htdocs/custom/wallboxbilling/class/wallboxbilling.class.php` — Hauptklasse, DB-Zugriff

### HA-Addon
- `Homeassistant/main.py` — Hauptloop, hier wird /health-Endpunkt ergänzt
- `Homeassistant/api_client.py` — API-Client, Upload-Logik und Upload-Status-Schreibung
- `Homeassistant/session_manager.py` — Session-Verwaltung, SQLite-Zugriff

### Anforderungen
- `.planning/REQUIREMENTS.md` — MON-01, MON-02, MON-03 (Active v1.1)
- `.planning/ROADMAP.md` — Phase 6 Success Criteria (4 Punkte)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `admin.php` bestehende Struktur: GETPOST, newToken(), llxHeader(), load_fiche_titre() — Pattern bereits vorhanden, Tab-Umbau ist additiv
- `llx_wallbox_sessions` Tabelle: bereits mit `wallbox_id`, `rfid_hash`, `energy_kwh` — upload_status/upload_error als ALTER TABLE ergänzbar
- Dolibarr `$db->query()` Pattern: einheitlich in billing.class.php und wallboxbilling.class.php, gleich für Session-Abfrage nutzen

### Established Patterns
- SEC-04: Berechtigungsprüfung via `$user->rights->wallboxbilling->admin` — muss im Status-Tab erhalten bleiben
- SEC-01/02: Kein RFID-Klartext in UI — Nutzer-Anzeige via JOIN auf User-Tabelle (Name, kein Hash)
- Dolibarr-Tab-Pattern: `dol_get_fiche_head()` mit Array von Tab-Definitionen — Standard in Dolibarr-Modulen

### Integration Points
- HA-Addon schreibt `upload_status` nach Upload-Versuch → Dolibarr liest für Anzeige
- cURL-Ping von Dolibarr → neuer `/health` GET-Endpunkt im HA-Addon
- Session-Tabellen-JOIN: `llx_wallbox_sessions` ↔ `llx_user` via RFID-Hash → User-Mapping

</code_context>

<specifics>
## Specific Ideas

- Status-Tab ist Default beim Öffnen von admin.php — Admin sieht sofort den Systemstatus (Success Criterion 1)
- Fehlermeldung muss spezifisch sein (kein generischer Fehlertext) — z.B. "HTTP 503: Service Unavailable" oder "Connection timeout after 5s"
- Die Session-Tabelle kombiniert MON-02 (Historie) und MON-03 (Fehler) in einer Ansicht über die upload_status-Spalte

</specifics>

<deferred>
## Deferred Ideas

### Überschussladen: Session-Logik Fix (wichtig — separate Aufgabe)
**Problem:** Bei aktivem Überschussladen stoppt die Wallbox temporär; das Addon interpretiert dies fälschlicherweise als Session-Ende. Energie der Fortsetzung wird nicht erfasst — Datenverlust bei der Abrechnung.

**Vorgeschlagene Lösung:**
- Session bleibt aktiv bis neue RFID-Karte gestartet wird (kein Zustandswechsel-Trigger mehr)
- Wallbox-Zustand (Charging/Idle) nur noch für Status-Anzeige, nicht für Session-Ende
- Monatssplit: Bei Mitternacht letzter Monatstag → Session schließen + sofort neue Session gleicher RFID/Wallbox starten
- Energie via `start_energy_total` und `end_energy_total` (Differenz = abgerechnete kWh)

**Betrifft:** `Homeassistant/session_manager.py`, `Homeassistant/main.py`
**Einzuplanen als:** Eigene Phase oder Hotfix nach Milestone v1.1

### Reviewed Todos (not folded)
Keine offenen Todos für Phase 6 gefunden.

</deferred>

---

*Phase: 6-Monitoring & Status*
*Context gathered: 2026-06-21*
