# Phase 1: Foundation (HA Integration + Dolibarr Skeleton) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-04
**Phase:** 1-Foundation
**Areas discussed:** HA-Addon Struktur, Dolibarr-Modul Aufbau, Sensor-Integration HA, Gemeinsame Konfiguration, Logging & Datenschutz, Dolibarr Frontend, Testing Setup

---

## HA-Addon Struktur

| Option | Description | Selected |
|--------|-------------|----------|
| Dockerfile + build.json (Recommended) | Standard HA-Addon Ansatz: Dockerfile mit Alpine 3.23, build.json fuer Config-UI in Supervisor | ✓ |
| Nur Dockerfile | Manuelles Addon ohne build.json Config-UI | |
| Vorhandenes Image erweitern | Auf bestehendem Python-Image aufbauen | |

**User's choice:** Dockerfile + build.json (Recommended)
**Notes:** Standard HA Supervisor Integration, Config-UI ueber build.json

---

| Option | Description | Selected |
|--------|-------------|----------|
| HA Core Integration nutzen (Recommended) | Bestehende Alfen-Integration in HA nutzen, ueber Home Assistant API (websocket/rest) auf sensor.alfen_eve_tag_socket_1 etc. zugreifen | ✓ |
| Direkt ueber Modbus TCP | Addon kommuniziert direkt mit Wallbox via Modbus, unabhaengig von HA-Core | |
| Hybrid: Modbus + HA-Fallback | Primaer Modbus, Fallback auf HA-Sensoren bei Verbindungsabbruch | |

**User's choice:** HA Core Integration nutzen (Recommended)
**Notes:** Nutzung der bestehenden Alfen-Integration in HA, Zugriff ueber Websocket API

---

| Option | Description | Selected |
|--------|-------------|----------|
| Async loop mit aiohttp (Recommended) | Event-basiert ueber HA-Websocket-API, effizient fuer Sensor-Polling | ✓ |
| Sync loop mit requests + time.sleep | Einfacher, blockierender Poll-Loop alle X Sekunden | |
| Service-basiert (systemd inside container) | Python-Skript als systemd-Service im Container mit Auto-Restart | |

**User's choice:** Async loop mit aiohttp (Recommended)
**Notes:** Event-basiert, effizient fuer Sensor-Polling ueber HA Websocket API

---

| Option | Description | Selected |
|--------|-------------|----------|
| Standard (Recommended) | main.py, config.yaml, requirements.txt, Dockerfile, build.json, README.md | ✓ |
| Erweitert mit Utils | main.py, config.yaml, requirements.txt, Dockerfile, build.json, utils/db.py, utils/hash.py, README.md | |
| Minimal | main.py, config.yaml, requirements.txt, Dockerfile | |

**User's choice:** Standard (Recommended)
**Notes:** Standard-Dateien fuer HA-Addon

---

## Dolibarr-Modul Aufbau

| Option | Description | Selected |
|--------|-------------|----------|
| noumainventoryapp als Vorlage (Recommended) | Bestehende Struktur in Dolibarr-Verzeichnis nutzen, auf Module-Conventions angepasst | ✓ |
| Leeres Modul-Geruest | Neues Modul von Grund auf nach Dolibarr-Doku erstellen | |
| Minimales Skeleton | Nur core/modules/wallbox.class.php und admin Setup-Seite | |

**User's choice:** noumainventoryapp als Vorlage (Recommended)
**Notes:** Struktur orientiert sich an bestehendem Modul in Dolibarr-Verzeichnis

---

| Option | Description | Selected |
|--------|-------------|----------|
| wallbox (Recommended) | Modul-Name: wallbox, Tabelle: llx_wallbox_sessions (DB-01 erfuellt) | |
| wallboxbilling | Modul-Name: wallboxbilling, Tabelle: llx_wallboxbilling_sessions | ✓ |
| evcharging | Modul-Name: evcharging, Tabelle: llx_evcharging_sessions | |

**User's choice:** wallboxbilling
**Notes:** Modul-Name ist wallboxbilling, Tabelle llx_wallboxbilling_sessions

---

| Option | Description | Selected |
|--------|-------------|----------|
| SQL in module/wallboxbilling.sql (Recommended) | Standard Dolibarr-Pattern: sql/mysql/migrate/ oder sql/ Verzeichnis mit CREATE TABLE Statements | ✓ |
| Dynamisch per PHP (db->DDL) | Tabellenerstellung ueber PHP $db->query() in _init() Methode | |
| Migrations-Dateien | Separate Migrations-Dateien pro Version im sql/-Verzeichnis | |

**User's choice:** SQL in module/wallboxbilling.sql (Recommended)
**Notes:** Standard Dolibarr-Pattern fuer DDL

---

| Option | Description | Selected |
|--------|-------------|----------|
| wallboxbilling.read + write (Recommended) | Zwei Basis-Rechte: Lesen und Schreiben fuer Wallbox-Sessions | |
| wallboxbilling.admin (nur Admin) | Nur Admins koennen das Modul nutzen, keine granularen Rechte | |
| wallboxbilling.user + admin + billing | Drei Rollen: user (lesen), billing (abrechnen), admin (voll) | ✓ |

**User's choice:** wallboxbilling.user + admin + billing
**Notes:** Drei Berechtigungen fuer Phase1 (SEC-04)

---

## Sensor-Integration HA

| Option | Description | Selected |
|--------|-------------|----------|
| Nur RFID + Energie + Status (Recommended) | sensor.alfen_eve_tag_socket_1, sensor.alfen_energy_total, charging state (3 Sensoren reichen fuer Foundation) | ✓ |
| Alle Alfen-Sensoren | Alle verfuegbaren Alfen-Sensoren in HA auslesen und loggen | |
| RFID + Energie + Status + Wallbox-ID | Zusaetzlich wallbox_id als Config-Parameter, nicht als Sensor | |

**User's choice:** Nur RFID + Energie + Status (Recommended)
**Notes:** 3 Sensoren fuer Phase1 Foundation

---

| Option | Description | Selected |
|--------|-------------|----------|
| 5 Sekunden (Recommended) | Schnell genug fuer RFID-Erkennung, schonend fuer HA-System | |
| 10 Sekunden | Minimaler Overhead, ausreichend fuer RFID-Debouncing (HA-07) | |
| Event-basiert (Websocket push) | Websocket-API nutzen, nur bei Aenderungen triggern (effizienter) | ✓ |

**User's choice:** Event-basiert (Websocket push)
**Notes:** Kein Polling, effizienter ueber HA Websocket API

---

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-Reconnect mit Backoff (Recommended) | Bei Verbindungsabbruch: Exponential Backoff Reconnect (spaeter PER-02 vorbereiten) | |
| Einfacher Retry-Loop | Alle X Sekunden versuchen, wieder zu verbinden (linear) | |
| Crash + Supervisor restart | Addon crasht bei Verbindungsverlust, HA Supervisor restartet es | ✓ |

**User's choice:** Crash + Supervisor restart
**Notes:** Einfach, HA Supervisor uebernimmt Recovery

---

| Option | Description | Selected |
|--------|-------------|----------|
| Ja, SQLite Setup in Phase1 (Recommended) | Datenbank-Initialisierung und erste Schreibversuche in Foundation-Phase | ✓ |
| Nein, nur Sensor-Abruf | SQLite kommt erst in Phase2 (Session Tracking) | |
| In-Memory Dummy-Speicher | Temporaerer Speicher in Phase1, echte DB in Phase2 | |

**User's choice:** Ja, SQLite Setup in Phase1 (Recommended)
**Notes:** Datenbank-Initialisierung in Foundation-Phase (Vorbereitung PER-01)

---

## Gemeinsame Konfiguration

| Option | Description | Selected |
|--------|-------------|----------|
| config.yaml in HA-Addon (Recommended) | wallbox_id als Parameter in build.json/config.yaml des Addons, Default: 'wallbox_01' | |
| Dynamisch aus Alfen-Sensor | Wallbox-ID wird aus sensor-Daten extrahiert (falls verfuegbar) | ✓ |
| Hardcoded v1, DB-Feld in Phase5 | In Phase1 nur eine Wallbox, ID erst spaeter konfigurierbar machen | |

**User's choice:** Dynamisch aus Alfen-Sensor
**Notes:** wallbox_id aus Sensor-Daten extrahiert (Multi-Wallbox Vorbereitung EXT-01)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Hash-Funktion in utils/hash.py (Recommended) | Zentrale Hash-Funktion im Addon, spaeter SEC-02 erfuellen | ✓ |
| Direkt in main.py hashen | Einfach inline hashlib.sha256 in main.py nutzen | |
| Nur Hash-Storage vorbereiten | Nur DB-Schema fuer Hash vorbereiten, Hashing-Logik in Phase2 | |

**User's choice:** Hash-Funktion in utils/hash.py (Recommended)
**Notes:** Zentrale SHA-256 Logik im Addon

---

| Option | Description | Selected |
|--------|-------------|----------|
| Token in config.yaml (Recommended) | DOLAPIKEY als Option in Addon-Config, spaeter API-03 erfuellen | |
| Umgebungsvariable im Container | Token ueber Docker ENV var uebergeben (sicherer) | ✓ |
| Noch nicht bereitstellen | API-Token kommt erst in Phase3 (API-Integration) | |

**User's choice:** Umgebungsvariable im Container
**Notes:** DOLAPIKEY als ENV Variable (sicherer als config.yaml)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Ja (Recommended) | Status-Codes: CHARGING, IDLE, STOPPED als Konstanten in Python + PHP definieren | ✓ |
| Nein, nur in Phase2 | Status-Codes erst wenn Sessions implementiert werden | |
| Nur in Python (HA-Addon) | Nur im Addon definieren, Dolibarr nutzt eigene Logik spaeter | |

**User's choice:** Ja (Recommended)
**Notes:** Gemeinsame Status-Konstanten in Python + PHP

---

## Logging & Datenschutz

| Option | Description | Selected |
|--------|-------------|----------|
| Strukturiertes Logging mit Hash (Recommended) | Python logging Modul, RFID wird IMMER gehasht geloggt (Vorbereitung SEC-01/SEC-02) | ✓ |
| Minimal (nur Errors) | Nur Fehler loggen, RFID-Daten werden komplett vermieden | |
| Debug + Filter | Vollstaendiges Debug-Logging, aber Filter fuer Klartext-RFID | |

**User's choice:** Strukturiertes Logging mit Hash (Recommended)
**Notes:** RFID wird IMMER gehasht geloggt

---

| Option | Description | Selected |
|--------|-------------|----------|
| dol_syslog mit Hash (Recommended) | Dolibarr eigene dol_syslog() nutzen, RFID nur als Hash weitergeben | ✓ |
| Custom Log-Datei | Eigene Log-Datei im Modul-Verzeichnis, RFID wird gefiltert | |
| Nur Standard-Logging | Keine zusaetzlichen Logs in Dolibarr, nur Standard | |

**User's choice:** dol_syslog mit Hash (Recommended)
**Notes:** Dolibarr Logging mit Hash fuer RFID (SEC-01/SEC-02)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Identischer Hash-Algorithmus (Recommended) | Hash-Funktion in beiden Systemen identisch (SHA-256), damit Abgleich moeglich | ✓ |
| Unabhaengige Hash-Logik | HA und Dolibarr nutzen jeweils eigene Hash-Logik | |
| Mit Salt vorbereiten | Salt in Phase1 schon vorbereiten (spaeter SEC-02 erfuellen) | |

**User's choice:** Identischer Hash-Algorithmus (Recommended)
**Notes:** SHA-256 in beiden Systemen identisch

---

| Option | Description | Selected |
|--------|-------------|----------|
| Konfigurierbarer Log-Level (Recommended) | Log-Level ueber config.yaml steuerbar (DEBUG/INFO/WARNING/ERROR) | ✓ |
| Fix auf INFO | Fix auf INFO-Level in Phase1, spaeter erweiterbar | |
| Startup-Debug dann INFO | DEBUG nur bei Startup, dann INFO | |

**User's choice:** Konfigurierbarer Log-Level (Recommended)
**Notes:** Log-Level ueber config.yaml steuerbar

---

## Dolibarr Frontend

| Option | Description | Selected |
|--------|-------------|----------|
| 3 Seiten (Recommended) | admin.php (Konfiguration + Rechte), index.php (Sessions-Liste), card.php (User-Link) | |
| Minimal (nur admin) | Nur admin.php fuer Modul-Konfiguration, Rest via Dolibarr-Standard | |
| 4 Seiten inkl. Bill | admin.php + index.php + card.php + bill.php (Abrechnung-Vorschau) | ✓ |

**User's choice:** 4 Seiten inkl. Bill
**Notes:** Inklusive bill.php fuer Abrechnung-Vorschau in Phase1

---

| Option | Description | Selected |
|--------|-------------|----------|
| Dolibarr Standard-Theme (Recommended) | Dolibarr eigenes Theme nutzen, keine eigenen Assets (ausser wallbox icon) | ✓ |
| Custom CSS | Eigenes CSS im Modul-Verzeichnis (css/wallboxbilling.css) | |
| Nur HTML | Kein CSS, nur Standard-Dolibarr HTML | |

**User's choice:** Dolibarr Standard-Theme (Recommended)
**Notes:** Keine eigenen CSS-Dateien, nutzt Dolibarr Theme

---

| Option | Description | Selected |
|--------|-------------|----------|
| Deutsch (Recommended) | Nur Deutsch (de_DE) in langs/, spaeter weitere Sprachen moeglich | ✓ |
| EN + DE | Englisch als Default, Deutsche Uebersetzung (en_US + de_DE) | |
| i18n vorbereitet | Mehrsprachig vorbereitet (i18n), aber nur DE in Phase1 | |

**User's choice:** Deutsch (Recommended)
**Notes:** Code-Kommentare, Dokumentation, UI auf Deutsch (laut AGENTS.md)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Dolibarr GETPOST-Standard (Recommended) | GETPOST() nutzen, Formulare mit Dolibarr-Standard (dol_forms) | ✓ |
| Custom Validation | Eigene Form-Validierung, spaeter SEC-05 erfuellen | |
| Nur Anzeige (read-only) | Keine Formulare in Phase1, nur Listen/Anzeige | |

**User's choice:** Dolibarr GETPOST-Standard (Recommended)
**Notes:** Vorbereitung SEC-05, Dolibarr-Standard nutzen

---

## Testing Setup

| Option | Description | Selected |
|--------|-------------|----------|
| pytest (Recommended) | pytest fuer HA-Addon (Python), einfache Unit-Tests fuer Hash/Config | ✓ |
| unittest | unittest (Python Standard), keine externen Abhaengigkeiten | |
| Keine Tests in Phase1 | Erst in Phase2 | |

**User's choice:** pytest (Recommended)
**Notes:** Testing-Framework fuer HA-Addon (Python)

---

| Option | Description | Selected |
|--------|-------------|----------|
| PHPUnit (Recommended) | PHPUnit fuer Dolibarr-Modul, einfache Unit-Tests fuer DB/Rechte | ✓ |
| Keine PHP-Tests | Nur manuelle Tests in Phase1 | |
| Dolibarr TestLib | Dolibarr eigene Test-Klasse nutzen (TestLib) | |

**User's choice:** PHPUnit (Recommended)
**Notes:** Testing-Framework fuer Dolibarr-Modul (PHP)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Mock HA-API (Recommended) | HA-Addon: Mock fuer HA-Websocket/API, keine echte Wallbox noetig | ✓ |
| Echter Simulator | Echte Alfen-Wallbox oder Simulator im Test aufsetzen | |
| Nur Unit-Tests | Keine Mocks, nur Code-Logik testen (Hash, Config) | |

**User's choice:** Mock HA-API (Recommended)
**Notes:** Tests ohne echte Wallbox moeglich

---

| Option | Description | Selected |
|--------|-------------|----------|
| Unabhaengige Configs (Recommended) | requirements.txt + composer.json im jeweiligen Verzeichnis, CI-ready | ✓ |
| Zentrales Test-Setup | Gemeinsames Root-Level config (Makefile?), Test-Runner zentral | |
| Nur lokal | Keine CI-Config in Phase1, nur lokale Tests | |

**User's choice:** Unabhaengige Configs (Recommended)
**Notes:** Getrennte Test-Abhaengigkeiten fuer HA und Dolibarr

---

## Claude's Discretion

- Stack-Aligned: Alpine 3.23, Python 3.13, requests 2.32+ für HA-Addon; PHP 8.1+, Dolibarr 21.x-22.x für Dolibarr-Modul
- RFID-Format: z.B. "EFCD083E" (aus PROJECT.md), 8 Zeichen Hex-String
- Addon-Verzeichnis: `~/projects/Wallbox-Dolibarr/Homeassistant` (aus PROJECT.md Context)
- Dolibarr-Verzeichnis: `~/projects/Wallbox-Dolibarr/Dolibarr` (Beispielpaket noumainventoryapp existiert)
- Sensor-Namen: sensor.alfen_eve_tag_socket_1 (RFID), sensor.alfen_energy_total (Energie), Charging State

## Deferred Ideas

None — discussion stayed within phase scope.

---

*Discussion completed: 2026-05-04*
*Total areas discussed: 7*
*Total questions: 28*