# Wallbox-Dolibarr Addon

Home Assistant Addon zur RFID-basierten Abrechnung von Wallbox-Ladevorgängen.

## Funktionen

- Erfasst RFID-Karten via Alfen Wallbox Integration
- Trackt Ladevorgänge (Start/Ende, kWh)
- Überträgt abgeschlossene Sessions an Dolibarr via REST API
- Speichert RFID nur als SHA-256 Hash (Datenschutz)

## Installation

1. Addon Repository zu Home Assistant hinzufügen
2. Addon "Wallbox-Dolibarr" installieren
3. Konfiguration anpassen (RFID Whitelist, Log-Level)
4. Addon starten

## Konfiguration

- `log_level`: Logging-Level (DEBUG, INFO, WARNING, ERROR)
- `wallbox_id`: ID der Wallbox (z.B. "alfen_eve")
- `rfid_whitelist`: Liste der erlaubten RFID-Karten (Hex-Strings)

## Sensoren

Das Addon nutzt folgende Home Assistant Sensoren:
- `sensor.alfen_eve_tag_socket_1` (RFID)
- `sensor.alfen_energy_total` (Energie in kWh)

## Voraussetzungen

- Home Assistant mit Alfen Wallbox Integration
- Dolibarr mit wallboxbilling Modul
