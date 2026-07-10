# Stack Research

**Domain:** Home Assistant Addon + Dolibarr Module für Wallbox-Ladeabrechnung  
**Researched:** 2026-05-04  
**Confidence:** HIGH (Home Assistant base images, PHP versions from official docs), MEDIUM (library choices verified via examples)

---

## Recommended Stack

### Home Assistant Addon ("App")

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **Alpine Linux (via HA base)** | 3.23 | Basis-OS im Container | Home Assistant standard base image (`ghcr.io/home-assistant/base:3.23`) – minimale Größe, offiziell unterstützt, automatische Architektur-Erkennung via `BUILD_FROM` |
| **Python** | 3.13 | Skriptsprache für Addon-Logik | HA-Addons nutzen offiziell Python 3.13 (siehe `home-assistant/docker-base` v2026.02.0). Python 3.12-3.14 verfügbar. Python 3.13 ist der aktuelle Standard für HA-Images. |
| **S6 Overlay** | Latest | Prozess-Supervisor | Im HA-Base-Image enthalten. Ermöglicht sauberes Lifecycle-Management mehrerer Prozesse. Bei einfachen Addons mit `init: false` in `config.yaml` nicht zwingend nötig. |
| **bashio** | Latest | HA-Supervisor-API-Helfer | Im Base-Image vorinstalliert unter `/usr/bin/with-contenv bashio`. Ermöglicht Zugriff auf Addon-Config, Logs, Secrets. Shebang `#!/usr/bin/with-contenv bashio` nutzen. |
| **SQLite3 (Python modul)** | Built-in | Lokale Persistenz für Lade-Sessions | Laut PROJECT.md gefordert. Leichtgewichtig, keine externe DB nötig. Python `sqlite3`-Standardbibliothek nutzen. |
| **requests** | 2.32+ | HTTP-Client für REST-API | Standard-Bibliothek für REST-Calls an Dolibarr. Offiziell in HA-Doku für API-Zugriff empfohlen. Alternative: `homeassistant_api` (5.0.3) für Websocket/REST-Abstraktion. |
| **FastAPI** (optional) | 0.115+ | REST-API-Server im Addon | Nur nötig, falls Addon eigene Endpoints für HA-Integration braucht. Viele aktuelle Addons (siehe `hass-tflite`, `Flatlib-Natal-Chart-API`) nutzen FastAPI für Performance + Docs. Für diese Use-Case (nur ausgehende Calls an Dolibarr) NICHT nötig. |

#### HA Addon Config-Dateien

| Datei | Zweck | Pflicht? |
|--------|--------|----------|
| `Dockerfile` | Container-Build, basierend auf `ARG BUILD_FROM` / `FROM $BUILD_FROM` | Ja |
| `config.yaml` | Addon-Metadaten, Ports, Options-Schema, Permissions | Ja |
| `build.yaml` | Build-Parameter (Base-Images pro Architektur) – wird derzeit zu Dockerfile-Labels migriert | Nein (kurzfristig noch unterstützt) |
| `run.sh` | Hauptskript (Shebang mit bashio) | Ja (oder CMD in Dockerfile) |
| `translations/en.yaml` (und `de.yaml`) | Beschreibungen der Config-Optionen | Nein (empfohlen für multilingual) |

#### HA Addon Build & Labels (neu ab 2026)

```dockerfile
ARG BUILD_FROM=ghcr.io/home-assistant/base:3.23
FROM ${BUILD_FROM}

# Labels für HA Supervisor (ersetzen build.yaml)
LABEL \
  io.hass.name="Wallbox-Dolibarr Addon" \
  io.hass.description="Erfassung und Übertragung von Wallbox-Ladevorgängen" \
  io.hass.type="addon" \
  io.hass.version="1.0.0" \
  org.opencontainers.image.source="https://github.com/yourrepo/Wallbox-Dolibarr"

# Python + SQLite + Abhängigkeiten installieren
RUN apk add --no-cache python3 py3-pip py3-requests sqlite

# Eigene Skripte kopieren
COPY run.sh /usr/local/bin/
RUN chmod a+x /usr/local/bin/run.sh

CMD ["/usr/local/bin/run.sh"]
```

**WICHTIG (2026-Update):** Das alte `home-assistant/builder` System wurde auf Docker BuildKit umgestellt. `build.yaml` wird ausgephase, Labels kommen direkt ins Dockerfile.

---

### Dolibarr Module

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **PHP** | 8.1 oder 8.2 | Serverseitige Sprache für Dolibarr-Modul | Dolibarr v21.x-v22.x offiziell kompatibel mit PHP 7.1–8.3 (siehe [Dolibarr Wiki](https://wiki.dolibarr.org/index.php?title=List_of_releases,_change_log_and_compatibilities)). Für neue Entwicklung PHP 8.1+ empfohlen (Performance, Security). Dolibarr v23.x (Feb 2025) erhöht Minimum auf PHP 7.2, unterstützt bis PHP 8.4. |
| **MariaDB** | 10.3+ | Datenbank für Dolibarr + Modul-Tabellen | Offiziell empfohlen (siehe [Prerequisites](https://wiki.dolibarr.org/index.php/Prerequisites)). MySQL 5.7+ ebenfalls unterstützt. PostgreSQL 9.1+ möglich. |
| **Apache** oder **Nginx** | Aktuell | Webserver | Dolibarr läuft mit jedem PHP-fähigen Webserver. Apache ist Standard in den meisten Dolibarr-Setups. |
| **Dolibarr Core** | 21.x oder 22.x | Basis-ERP-Plattform | LTS-Versionen mit aktiver Community. v21.x ist stabil, v22.x bringt PHP 8.4 Support. |
| **TCPDF** (über Dolibarr intern) | Integriert | PDF-Generierung für Abrechnungen | Dolibarr hat eingebaute PDF-Generierung über TCPDF. Keine externe Library nötig – Modul nutzt `dol_print_rect()`, `pdf_pagehead()` etc. aus `core/lib/pdf.lib.php`. |
| **Dolibarr Module Builder** | In Core ab v12.0 | Code-Generator für Modul-Grundgerüst | Erzeugt automatisch `modMyModule.class.php`, SQL-Dateien, PHP-DAO-Klassen, Menü-Einträge. Grundlage: `htdocs/modulebuilder/template` (offizieller Template-Code). |

#### Dolibarr Module Verzeichnisstruktur (Standard)

```
htdocs/custom/mymodule/          # oder htdocs/mymodule/ für Core-Module
├── mymodule.class.php           # Haupt-Modul-Datei (Descriptor)
├── core/
│   ├── modules/                 # Modul-Descriptor (modMyModule.class.php)
│   ├── triggers/               # Event-Handler (optional)
│   └── boxes/                  # Dashboard-Widgets (optional)
├── class/                       # DAO-Klassen (CRUD für llx_wallbox_sessions etc.)
├── sql/                         # llx_wallbox_sessions.sql, llx_wallbox_sessions.key.sql
├── admin/                       # Konfigurationsseite (Setup-Page)
├── langs/en_US/                 # Sprachdateien (en_US, de_DE)
├── css/                         # Stylesheets (optional)
├── js/                          # JavaScript (optional)
├── img/                         # Bilder/Icons
└── README.md
```

#### Dolibarr API-Token Authentication

Dolibarr REST-API nutzt API-Token via HTTP-Header:
```
Authorization: Basic base64(user:password)
```
oder (neuere Versionen) via API-Token in URL-Parametern oder Custom Headers. Das HA-Addon sendet Sessions per JSON-Payload an Dolibarr.

---

## Installation

### Home Assistant Addon

```bash
# Entwicklung: Addon lokal bauen (amd64 Beispiel)
docker build \
  --build-arg BUILD_FROM="ghcr.io/home-assistant/amd64-base:3.23" \
  -t local/wallbox-dolibarr-addon \
  /path/to/Homeassistant

# Addon-Container lokal testen
docker run \
  --rm \
  -v /tmp/wallbox_test:/data \
  -p 8099:8099 \
  local/wallbox-dolibarr-addon
```

### Dolibarr Module

```bash
# Modul-Verzeichnis in Dolibarr custom/ kopieren
cp -r Dolibarr /pfad/zu/dolibarr/htdocs/custom/wallbox

# In Dolibarr: Setup → Modules → Wallbox-Modul aktivieren
# → SQL-Tabellen (llx_wallbox_sessions) werden automatisch angelegt
```

---

## Alternatives Considered

| Recommended | Alternative | Why Not / When to Use Alternative |
|-------------|-------------|-------------------------------|
| **Python 3.13 (HA Addon)** | Node.js (mit `homeassistant-api` npm) | Node.js wäre möglich, aber Python ist Standard für HA-Addons. `homeassistant_api` (Python) ist ausgereifter als npm-Alternativen. Bei reinen HTTP-Calls genügt auch einfaches Bash + `curl`, aber Python bietet bessere Fehlerbehandlung (Retry-Logic für API-Calls). |
| **PHP 8.1+ (Dolibarr)** | PHP 7.4 (Legacy) | PHP 7.4 ist EOL seit 2022. Für neue Module PHP 8.1+ nutzen (Performance, Type Hints, Match-Expressions). Nur bei zwingendem Hosting-Zwang auf alten Servern PHP 7.4 in Betracht ziehen. |
| **SQLite (HA Sessions)** | PostgreSQL / MySQL direkt aus Addon | Zu schwergewichtig für einfache Session-Persistenz im Addon. SQLite ist lokal, braucht keinen Netzwerk-Zugriff, überlebt HA-Neustarts. Wenn später zentrale DB für mehrere Wallboxen nötig: MariaDB in Dolibarr nutzen, aber Sessions bleiben lokal in SQLite. |
| **FastAPI (HA Addon, optional)** | Flask | FastAPI hat native async/await, automatische OpenAPI-Docs, bessere Performance. Flask ist einfacher für Minimaleinsatz. Für dieses Projekt (nur ausgehende API-Calls) ist weder FastAPI noch Flask nötig – einfaches Python-Skript mit `requests` genügt. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **PHP 7.2 oder älter** | EOL, keine Security-Updates, veraltete Syntax | PHP 8.1+ (unterstützt Dolibarr v21.x+) |
| **MySQL 5.5.40/5.5.41** | Bekannte Datenverlust-Bugs laut Dolibarr-Doku | MariaDB 10.3+ oder MySQL 5.7+ |
| **Alpine Linux < 3.20 (HA Addon)** | Veraltet, keine Sicherheits-Updates | `ghcr.io/home-assistant/base:3.23` (Alpine 3.23) |
| **`home-assistant/builder` (Legacy Build)** | Im April 2026 offiziell eingestellt, migriere zu Docker BuildKit | Native `docker build` mit `BUILD_FROM` ARG |
| **Frameworks wie Laravel/Symfony für Dolibarr-Modul** | Dolibarr hat eigene Architektur, Modul muss Dolibarr-Conventions folgen | Native Dolibarr-Modul-Struktur (`modMyModule.class.php`, DAO-Klassen) |
| **RFID im Klartext loggen** | Datenschutzverstoß (laut PROJECT.md) | RFID-Hash speichern (z.B. `hash('sha256', $rfid_id . $salt)`) |

---

## Stack Patterns by Variant

**If (wie in PROJECT.md v1 geplant) nur eine Wallbox + RFID-Whitelist in YAML:**
- HA Addon: Einfaches Python-Skript mit `init: false` in `config.yaml` (kein S6 Overlay nötig)
- RFID-Whitelist: YAML-Datei in `/data/rfid_whitelist.yaml` (vom Addon gelesen)
- Persistence: SQLite3 lokal im `/data` Verzeichnis (überlebt Container-Neustarts via HA `map: data`)

**If später mehrere Wallboxen (Skalierung):**
- Architektur bleibt gleich: Jede Wallbox = eigener Sensor in HA (`sensor.alfen_eve_tag_socket_X`)
- Dolibarr-Modul: `llx_wallbox_sessions` bekommt Spalte `wallbox_id` (String, z.B. "socket_1", "socket_2")
- API-Übertragung: JSON-Payload enthält `wallbox_id` Feld

**If Klartext-Logs verhindern (Datenschutz):**
- Python (HA): `hashlib.sha256(rfid_id.encode() + salt.encode()).hexdigest()`
- PHP (Dolibarr): `hash('sha256', $rfid_id . $conf->global->WALLBOX_RFID_SALT)`

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| **Dolibarr v21.x-v22.x** | PHP 7.1–8.3 | V22.0.0+ offiziell PHP 8.4 Support |
| **Dolibarr v23.x** | PHP 7.2–8.4 | Minimum erhöht auf PHP 7.2 (seit März 2026) |
| **HA Base Image 3.23** | Alpine 3.23, Python 3.12-3.14 | Python 3.13 ist Standard in 2026 |
| **SQLite3 (Python)** | Python 3.10+ | Standardbibliothek, keine Installation nötig |
| **requests (Python)** | Python 3.8+ | Kompatibel mit HA Base Python 3.13 |

---

## Sources

- **[Home Assistant Docker Base](https://github.com/home-assistant/docker-base)** (HIGH confidence) — Verifiziert: Alpine 3.23, Python 3.12-3.14, Base-Image Tags
- **[Home Assistant Apps Docs](https://developers.home-assistant.io/docs/apps/)** (HIGH confidence) — Verifiziert: Apps (ehemals Addons), Dockerfile-Labels, BuildKit-Migration April 2026
- **[Dolibarr Module Development Wiki](https://wiki.dolibarr.org/index.php/Module_development)** (HIGH confidence) — Verifiziert: Modul-Struktur, Template, PHP-Versionen
- **[Dolibarr Release Compatibility](https://wiki.dolibarr.org/index.php?title=List_of_releases,_change_log_and_compatibilities)** (HIGH confidence) — Verifiziert: PHP 7.1-8.4 Support-Matrix für v20.x-23.x
- **[Dolibarr Prerequisites](https://wiki.dolibarr.org/index.php/Prerequisites)** (MEDIUM confidence) — Verifiziert: MariaDB 10.3+, MySQL 5.7+, PHP-Extensions
- **[GitHub: hass-api/homeassistant_api](https://github.com/GrandMoff100/HomeAssistantAPI)** (MEDIUM confidence) — Beispiel für Python HA API Client (5.0.3, März 2026)
- **[GitHub: home-assistant/apps-example](https://github.com/home-assistant/apps-example)** (HIGH confidence) — Offizieller Template-Code für HA Addons (Dockerfile, Config)
- **[Blog: HA Addon Dev Notes](https://blog.michal.pawlik.dev/posts/smarthome/home-assistant-addons)** (MEDIUM confidence) — Praxis-Erfahrungen: bashio, S6, Build-Prozess

---

*Stack research for: Home Assistant Addon + Dolibarr Module (Wallbox-Dolibarr Integration)*  
*Researched: 2026-05-04*
