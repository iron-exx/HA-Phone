# HA-Phone Roadmap

Stand: Juli 2026
Aktuelle Add-on-Linie: `0.7.63`
Ziel: von einer funktionierenden Home-Assistant-PBX zu einer stabilen, alltagstauglichen kleinen Business-Telefonanlage

## 1. Produktbild

HA-Phone ist kein Ersatz fuer jede Enterprise-PBX, aber es kann sehr gut eine kompakte Anlage fuer Home Office, kleine Buros, Praxen, Werkstaetten und Handwerksbetriebe werden.

Der realistische Zielbereich fuer die naechsten Versionen ist:

- 5 bis 30 Endgeraete
- 1 bis 5 Trunks
- 1 Standort, optional Remote-Teilnehmer per VPN
- Bedienung komplett ueber Web-UI in Home Assistant

## 2. Aktueller Ist-Stand

Diese Funktionen sind heute bereits vorhanden und im Code sichtbar:

- Nebenstellen `10-99`
- Trunk-Verwaltung
- Eingehende Routen
- Ausgehende Wahlregeln
- Rufgruppen mit eigener interner Durchwahl
- Zeitbedingungen
- IVR-Menues mit eigener interner Durchwahl und WAV-Ansage
- Voicemail inklusive Greeting-Upload und Nachrichtenliste
- SMTP fuer Voicemail-per-E-Mail
- Auto-Provisioning fuer mehrere Geraetetypen
- Web-UI, Authentifizierung und Add-on-Update-Pruefung

## 3. Bekannte Defekte (Register)

Diese Liste ist der eigentliche Input fuer Phase A. Eine Roadmap, die nur "Stabilitaet verbessern" sagt, ohne die konkreten Fehler zu benennen, ist nicht ausfuehrbar. Jeder Eintrag hier ist durch Code-Review und/oder Live-Reproduktion belegt, nicht vermutet.

| # | Ort | Symptom | Status |
|---|-----|---------|--------|
| D1 | `time_conditions.py::_regenerate_routing_conf` | Setzte `ivr.parsed_options` auf ein SQLModel-Tabellenobjekt ohne dieses Feld -> `ValueError`. Live reproduziert: `POST /api/ivrs` schlug mit 500 fehl, sobald ein IVR-Menue existierte. Kaskadierte in **jeden** Aufrufer (Extensions, Rufgruppen, Routen, Trunk, Boot-Skript). | behoben in 0.7.42 |
| D2 | `extensions_routing.conf.j2`, IVR-Kontext | Ungueltig-Zaehler (`IVR_INVALID_COUNT`) wurde bei jedem Replay auf 0 zurueckgesetzt, weil der Replay-Pfad zu `s,1` sprang (demselben Label, das den Zaehler initialisiert). `max_invalid_tries` griff nie -> Endlosschleife statt Auflegen. | behoben in 0.7.42 |
| D3 | `Routing.tsx` | Vier Stellen mit doppelt kodiertem UTF-8 (Mojibake) trotz vorherigem "Encoding gefixt"-Commit uebersehen. | behoben in 0.7.42 |
| D4 | `Routing.tsx::getRouteDestinationOptions` | Rufgruppen ohne eigene interne Durchwahl (`number=0`, z.B. Altbestaende nach Migration von vor 0.7.40) waren im Ziel-Dropdown fuer eingehende Routen unsichtbar, obwohl die Route ueber die DB-ID laeuft, nicht die Nummer. | behoben in 0.7.42 |
| D5 | `ring_groups.py` + `ivr.py` | Zwei fast identische `_validate_*_number`-Funktionen, jede prueft unabhaengig gegen Extension + RingGroup + IVRMenu. `extensions.py` hatte gar keine Cross-Table-Pruefung, `ring_groups.py` prueft nie gegen IVRMenu - zwei zusaetzliche Luecken beim Konsolidieren gefunden. | **behoben in 0.7.65** (`backend/numbering.py`) |
| D6 | Boot-Skript `10-asterisk-init.sh` | Alle Config-Regenerierungen (Extensions, Voicemail, Routing, Mail, Trunk) liefen in einem einzigen Python-Block ohne Isolation. Ein Fehler in einer Regenerierung (siehe D1) verhinderte stillschweigend auch alle anderen, inklusive Trunk und Mail. | **behoben in 0.7.63** (`regeneration.py`, pro Schritt isoliert + Dashboard-Statusbanner) |
| D7 | `ivr.py::upload_greeting` | Pruefte nur die Dateiendung `.wav`, validierte/konvertierte aber nicht Samplerate/Kanaele/Codec. Eine aus Audacity oder vom Handy exportierte WAV (z.B. 44.1kHz Stereo) wurde von Asterisk `Background()` nicht sauber abgespielt. | **behoben in 0.7.66** (`_normalize_greeting_wav` via `sox`) |
| D8 | `models.py` (`Trunk.password`, `SmtpSettings.password`, `Extension.sip_password`) | Alle Zugangsdaten lagen im Klartext in SQLite. | **behoben in 0.7.69** - Fernet-Verschluesselung at rest (`backend/crypto.py`, `EncryptedString`-Spaltentyp), Schluessel lokal in `/data/.secret_key`. Schuetzt vor kopierter/geleakter DB-Datei, nicht vor Root-Zugriff auf denselben Host. Backup-Export-Verschluesselung mit Nutzerpasswort bleibt Aufgabe von Phase B, sobald Backup/Restore gebaut wird. |
| D9 | Keine Locking-Strategie um `_regenerate_routing_conf` / Boot-Regenerierung | Zwei gleichzeitige Schreibvorgaenge (zwei Admin-Tabs, oder ein Request waehrend des Boots) koennen die generierten Dateien in unvorhersehbarer Reihenfolge ueberschreiben. `render_conf` selbst schreibt atomar (Temp-Datei + `os.replace`), es gibt aber keine Sperre ueber die gesamte DB-Lese- plus Render-Sequenz. | offen -> Phase A, Beobachtung, kein Blocker |
| D10 | GitHub Actions `build.yaml` | Baut und pusht das Multi-Arch-Image, fuehrt aber weder Backend-Tests (`pytest`) noch Frontend-Typecheck (`tsc --noEmit`) vorher aus. Ist bereits einmal live eingetreten: der 0.7.42-Build brach im Docker-CI an unbenutzten TS-Imports, die lokal nicht auffielen (siehe 0.7.43-Changelog-Eintrag). | **behoben in 0.7.64** -> Phase A, Punkt 5 |
| D11 | `config.yaml` (vor 0.7.56) | Kein `image:`-Feld gesetzt. Der Supervisor ignorierte das von der CI bereits gebaute GHCR-Image komplett und kompilierte Asterisk bei jedem Install/Update lokal aus dem Quellcode (`./configure && make`) - mehrere Minuten statt Sekunden. | behoben in 0.7.56 |
| D12 | `extensions_routing.conf.j2::[outbound-pstn]` | Pattern `_X.` matcht in Asterisk nur Ziffern, nie ein fuehrendes `+`. Ausgehende Regeln, die `+49...` erzeugen, wurden lokal sofort abgewiesen ("sent to invalid extension but no invalid handler"), bevor der Trunk ueberhaupt erreicht wurde. | behoben in 0.7.52 |
| D13 | Ausgehende Regel-Default (`outbound_rules.py::DEFAULT_OUTBOUND_RULES`) | Die aarenet/AareSwitch-Plattform (Deutsche Glasfaser Whitelabel) akzeptiert fuer die Zielrufnummer nur nationales Format (fuehrende 0), nicht E.164 - live per SIP-Trace verifiziert (183 Session Progress + Inband-Ansage "ungueltige Rufnummer" statt SIP-Fehlercode). Kein Code-Bug (Regel ist nutzerkonfigurierbar), aber der generische `+49`-Default passt nicht zu diesem konkreten Trunk-Typ. | dokumentiert in 0.7.54, Workaround in DB angewendet |
| D14 | `Extensions.tsx::buildLinphoneConfigUri` + Provisioning-XML (`extensions.py`) | Kette von 4 zusammenhaengenden Linphone-Bugs: (1) doppelter Scheme-Separator `linphone-config://http://...` statt `linphone-config:http://...`, (2) In-App-QR-Scanner erwartet die nackte URL, nicht die `linphone-config:`-Form, (3) `reg_proxy`/`reg_route` ohne `sip:`-Praefix -> App laed XML erfolgreich, sendet aber nie ein REGISTER, (4) Push-Benachrichtigungen aktiv, obwohl kein Apple-Push-Gateway existiert -> Registrierung schlief nach Ablauf ein, App zeigte trotzdem "Online". Jeder Einzelfehler live per SIP-Trace/HTTP-Test verifiziert. | behoben in 0.7.57-0.7.60 |
| D15 | `pjsip_extensions.conf.j2` | Asterisk 22 anonymisiert den From-Header auf `Dial()`-erzeugten Anruf-Legs (`"Anonymous" <sip:anonymous@anonymous.invalid>`), wenn der Ziel-Endpoint `trust_id_outbound` nicht gesetzt hat. Jeder interne Anruf zeigte "Anonymous"; Linphone iOS zeigte fuer die ungueltige Anonymous-URI teils gar keine Anruf-UI. Live per SIP-Trace bewiesen (AMI-Originate vs. Dialplan-Pfad verglichen). | behoben in 0.7.61 (`trust_id_outbound = yes`) |

Regel ab jetzt: Jeder in Code-Review oder Bugfix gefundene Defekt wird hier eingetragen, bevor er behoben wird, und erst nach Fix + Test als "behoben" markiert. Kein stillschweigendes Reparieren ohne Spur.

**Neu, noch nicht eingeordnet (2026-07-06):** Externe eingehende Anrufe zeigen auf Linphone UND dem alten Android "Anonymous", obwohl der Provider laut Nutzerangabe die Rufnummer uebertraegt. Verdacht: `trunk-endpoint`-CallerID-Konfiguration (statisch gesetzte `callerid` fuer ausgehende CLIP) ueberschreibt moeglicherweise auch eingehend, oder die Nummer steckt im `P-Asserted-Identity`-Header statt `From` und `trust_id_inbound` wertet ihn nicht wie erwartet aus. Noch nicht per Trace verifiziert (Anruf kam waehrend der Diagnose-Session nicht durch) -> naechster Schritt: Live-SIP-Trace bei echtem externen Anruf.

## 4. Aktuelle Realitaet

Die wichtigste Aufgabe ist gerade nicht "noch mehr Features", sondern Stabilitaet und saubere Basisschichten.

Die letzten Arbeiten zeigen das ziemlich deutlich:

- Routing, Rufgruppen und IVR haben sich mehrfach gegenseitig beeinflusst (siehe D1-D5)
- Config-Regenerierung ist ein kritischer Kernpfad, der aktuell keine Fehler-Isolation hat (D6)
- CI und Add-on-Build muessen bei jeder Version absolut sauber laufen
- Die UI ist funktional, aber in einigen Bereichen noch technisch statt administrativ gedacht
- Neue Features werden aktuell ohne Regressionstests gemerged: Das IVR-Feature (0.7.38-0.7.41) hatte beim Merge **null** Backend-Tests, was D1 und D2 direkt ermoeglicht hat

Deshalb ist die Roadmap bewusst in zwei Teile getrennt:

- zuerst Basis stabilisieren
- dann gezielt Business-Features ergaenzen

## 5. Was vor neuen Grossfeatures zuerst fertig sein muss

### Phase A - Basis stabilisieren

Ziel: die vorhandenen Kernfunktionen muessen robust, vorhersagbar und supportbar sein.

Pflichtpunkte, jeweils mit Fertig-Kriterium:

**1. Zentralen Numbering-Space-Dienst einfuehren (loest D5) - ERLEDIGT in 0.7.65**
- `backend/numbering.py::validate_number` ist jetzt der einzige Ort, der "ist Nummer X im Bereich 10-99 frei/belegt/von wem" beantwortet.
- `extensions.py`, `ring_groups.py::_validate_ring_group_number` und `ivr.py::_validate_ivr_number` rufen alle denselben Dienst auf.
- Beim Konsolidieren zwei zusaetzliche, vorher unentdeckte Luecken gefunden und mitgeschlossen: `extensions.py` hatte gar keine Cross-Table-Pruefung, `ring_groups.py` prueft nie gegen IVRMenu (siehe D5).
- 5 Regressionstests decken alle Kollisionsrichtungen ab, inkl. Update-Pfad.
- *Abhaengigkeit erfuellt:* Queues und Konferenzraeume (v0.9) koennen jetzt auf diesem Dienst aufbauen.

**2. Config-Regenerierung fehler-isolieren (loest D6, verhindert D1-Klasse-Bugs strukturell) - ERLEDIGT in 0.7.63**
- Jede einzelne Regenerierungsfunktion laeuft jetzt ueber `regeneration.py::run_regeneration_steps` einzeln try/except-behandelt und geloggt, sowohl im Boot-Skript als auch in jedem Router (Extensions, Routing, Trunk, IVR, Rufgruppen, Zeitbedingungen, Ausgehende Regeln, Settings).
- Ein Fehler in einer Regenerierung verhindert die anderen nicht mehr - AMI-Reload passiert nur noch pro erfolgreichem Schritt.
- Status wird persistiert (`config_regeneration_status.json`) und im Dashboard als Banner angezeigt, inklusive Zeitstempel und Fehlermeldung pro Schritt.
- Regressionstests vorhanden (`test_api.py`).

**3. Routing-Modell konsistent validieren - ERLEDIGT in 0.7.67/0.7.70**
- Delete-Teil (0.7.67): Loeschen einer Rufgruppe/eines IVR-Menues wird mit `409` abgelehnt, solange eine Route oder (bei IVR) ein Untermenue-Verweis darauf zeigt.
- Fehlertexte (0.7.70): Neue gemeinsame Hilfsfunktion `apiErrorMessage`/`toErrorMessage` (`src/lib/apiError.ts`) extrahiert die echte Backend-`detail`-Meldung statt generischer Texte oder rohem JSON im Toast. Angewendet in ca. 20 Speicher-/Loeschvorgaengen ueber Routing, Voicemail, Nebenstellen, Trunk und IVR.
- Noch offen (kleinerer Rest, kein Blocker): Aenderungsfaelle wie eine Rufgruppen-Nummer aendern, waehrend eine Route per ID darauf zeigt - funktioniert bereits (Route referenziert per ID, nicht Nummer), aber noch nicht mit einem expliziten Test abgesichert.

**4. Dialplan-Generierung absichern - ERLEDIGT in 0.7.68**
- Regressionstests fuer `extensions_routing.conf` pro Konfigurationspfad (Extension, Rufgruppe, IVR, Zeitbedingung, Outbound-Regeln) existierten bereits verteilt in `test_api.py`.
- Neu: `test_all_routing_domains_combined_after_ivr_exists` stellt die Kombination aus allen gleichzeitig nach (das genaue D1-Szenario: IVR existiert, dann Extension/Rufgruppe/Route/Regel/Zeitbedingung anlegen, dann Extension nochmal aendern) und prueft sowohl den finalen Dialplan-Inhalt als auch den Regenerierungs-Status pro Schritt.
- CI (D10, seit 0.7.64) schlaegt entsprechend fehl, wenn ein schreibender Endpunkt nach IVR-Existenz wieder einen Fehler wirft.

**5. Add-on-Release-Prozess haerten (loest D10) - ERLEDIGT in 0.7.64**
- Jede Version braucht Changelog, Versionsbump und erfolgreichen Multi-Arch-Build.
- GitHub Actions fuehrt jetzt Backend-Tests (`pytest`) und Frontend-Typecheck+Build (`tsc -b && vite build`) sowie Frontend-Tests (`vitest run`) als eigenen `test`-Job aus, den der `build`-Job per `needs:` voraussetzt - ein fehlschlagender Test/Typecheck verhindert den Image-Build komplett.
- Zusaetzlich `image:`-Feld in `config.yaml` seit 0.7.56 (loest D11) - Updates sind seitdem ein Registry-Pull (~30s) statt eines lokalen Asterisk-Kompilierlaufs (mehrere Minuten).

**6. IVR-Audio-Upload robust machen (loest D7) - ERLEDIGT in 0.7.66**
- Hochgeladene WAV-Dateien werden serverseitig mit `sox` auf 8kHz/Mono/16-Bit normalisiert, statt nur die Dateiendung zu pruefen.
- Nicht-Audio-Uploads (kaputte Datei, `.wav`-umbenannte Textdatei) werden mit klarer Fehlermeldung abgelehnt.
- 3 Regressionstests, davon einer mit echter Sox-Konvertierung (keine Mocks).

**7. UI-Grundqualitaet verbessern**
- Alle Dialoge, Dropdowns und Tabellen konsistent dunkel und lesbar.
- Technische IDs nicht direkt dem Benutzer zeigen, wenn eine sprechende Auswahl moeglich ist.
- Editing-Flows fuer Rufgruppen, IVR und Routen angleichen.
- *Fertig, wenn:* eine Stichprobe aller Dropdown-Menues in einem dunklen Browser-Theme manuell durchgeklickt wurde und lesbar ist (kein automatischer Test moeglich, daher manuelle Checkliste im PR).

**8. Datenmigrationen aufraeumen - ERLEDIGT in 0.7.70**
- Neue Testdatei `test_migrations.py` baut die historisch aelteste Spaltenstruktur von Hand nach, laesst `create_all()` + `run_migrations()` echt darueberlaufen und prueft alle Spalten/Defaults/Datenerhalt/ORM-Lesbarkeit. Zusaetzlicher Idempotenz-Test (zweifacher Lauf).
- Dabei sofort einen echten, bis dahin unentdeckten Bug gefunden: `extension.enabled` hatte ueberhaupt keine Migration - jede aeltere Installation waere beim ersten Zugriff auf die Extension-Tabelle abgestuerzt. Migration ergaenzt.
- Aktuelles Muster (`if column not in cols: ALTER TABLE ...` in `database.py`) bleibt fuer die heutige Groesse die richtige Wahl; Alembic-Umstieg weiterhin nur als Beobachtung fuer den Tag, an dem eine neue Tabelle mit Fremdschluessel-Bezug dazukommt.

Definition of done fuer Phase A:

- keine bekannten Build-Brecher in CI
- Defekte-Register (Abschnitt 3) enthaelt keine offenen Eintraege mit Status "Phase A"
- alle Kernpfade mit Tests abgesichert
- neues Add-on-Release laesst sich in HA ohne Sonderfaelle installieren

### Phase B - Betriebsreife fuer kleine Anlagen

Ziel: die vorhandene PBX soll im Alltag sinnvoll administrierbar werden.

Pflichtpunkte:

**1. Trunk-Diagnose verbessern**
- Registrierung, Fehlerursache und letzte SIP-Antwort verstaendlich anzeigen.
- Testanruf bzw. Testkonfiguration klarer fuehren.

**2. Bessere Nebenstellenverwaltung**
- Such- und Filterfunktion.
- Anzeige von Zuordnung zu Rufgruppen und IVR-Zielen.
- Sauberer Umgang mit deaktivierten Nebenstellen.

**3. Zeitsteuerung alltagstauglich machen - ERLEDIGT in 0.7.72/0.7.73**
- Neues `Holiday`-Modell (Monat/Tag, jaehrlich wiederkehrend) gilt automatisch fuer alle Zeitbedingungen als "geschlossen" (0.7.72).
- Klare Regelprioritaet: Feiertags-Check steht im generierten Dialplan immer vor der normalen Oeffnungszeiten-Pruefung.
- Bewusste Einschraenkung: keine beweglichen Feiertage (Ostern etc.) - dafuer bleibt die manuelle Zeitbedingung.
- Wochentag-Toggle-Buttons (Mo-So) ersetzen das rohe Asterisk-Format-Freitextfeld bei "Open Days" (0.7.73) - `src/lib/weekdays.ts` konvertiert transparent, keine Backend-Aenderung noetig.

**4. Backup und Restore - ERLEDIGT in 0.7.71**
- Neue Seite "Backup": Export/Import der kompletten PBX-Konfiguration als ZIP (`backend/routers/backup.py`).
- Secrets-Entscheidung umgesetzt: Portabilitaet gewaehlt (nicht "nur gleicher Host") - der komplette Export wird mit einem beim Export eingegebenen Backup-Passwort neu verschluesselt (PBKDF2-HMAC-SHA256 -> Fernet), unabhaengig vom lokalen `.secret_key` des Zielhosts.
- Admin-Login bewusst ausgeschlossen - ein Restore darf den Zugang zum Zielhost nie aendern.
- Provisioning-Vorlagen werden per Name statt ID zugeordnet (Kollisionsvermeidung mit bereits geseedeten Builtin-Vorlagen auf der Zielinstanz).
- *Fertig-Kriterium erfuellt und per Test bewiesen:* `test_backup_restore_round_trip_on_fresh_instance` loescht den lokalen Schluessel (simuliert eine frische Instanz), stellt wieder her, und prueft, dass ein Trunk-Passwort korrekt in der generierten Config landet.

Definition of done fuer Phase B:

- kleine Anlage kann ohne Shell-Eingriffe eingerichtet, gesichert und geaendert werden

## 6. Danach sinnvolle Erweiterungen

Diese Features sind sinnvoll, aber erst nach Phase A und B.

### Prioritaet Hoch

- ~~Telefonbuch mit CSV-Import/Export~~ - erledigt 0.7.74 (CallerID-Namensabgleich fuer eingehende Anrufe als natuerliche Folge-Erweiterung noch offen)
- ~~Feiertage und erweiterte Geschaeftszeiten~~ - erledigt 0.7.72/0.7.73
- Sprachansagen-Manager fuer IVR und Zeitziele
- Blacklist / Whitelist fuer eingehende Anrufe
- **Warteschlangen / Queues** und **Konferenzraeume** - siehe gesonderte Anmerkung unten. Beide brauchen den Numbering-Service aus Phase A Punkt 1.

**Anmerkung zu Queues/Konferenz:** Diese zwei Punkte sind technisch keine weitere CRUD-Ergaenzung wie Telefonbuch oder Kurzwahlen. Alles bisher Gebaute folgt dem Muster DB-Eintrag -> Jinja2-Template -> statische Asterisk-Config -> Reload. Queues brauchen zusaetzlich **Live-Zustand** (Warteschlangenposition, Agenten-Status, typischerweise ueber AMI-Events) und einen Weg, diesen Zustand ins Frontend zu pushen (Websocket oder Server-Sent-Events fuer ein Live-Dashboard), nicht nur eine generierte Konfigurationsdatei. Bei der Aufwandsschaetzung entsprechend groesser einplanen als die Nachbarpunkte in der Liste.

### Prioritaet Mittel

- Follow Me / Weiterleitung auf externe Nummern
- Pickup, Parken, Intercom, Paging
- Music on Hold Verwaltung
- Kurzwahlen
- Besseres Operator-/Statuspanel
- CDR / Anrufhistorie mit einfacher Auswertung

### Prioritaet Spaeter

- WebRTC
- SBC / Cloud-PBX-Szenarien
- LDAP / Verzeichnisanbindung
- CRM-Integrationen
- Recording mit Richtlinien und Download
- Mandanten- oder Multi-Site-Konzepte
- Mehrere Admin-Benutzer / Rollen (aktuell fest ein einziger `admin`-Account - relevant, sobald CDR/Recording personenbezogene Zugriffskontrolle brauchen)

## 7. Vergleich mit 3CX und Yeastar

Was HA-Phone kurzfristig von 3CX und Yeastar uebernehmen sollte:

- klare Zielobjekte statt roher IDs
- robuste Admin-Workflows fuer Routing, IVR und Rufgruppen
- Telefonbuch als zentrale Schicht fuer spaetere Features
- Feiertage + Oeffnungszeiten als echter Standardbaustein
- Queue und Konferenz vor exotischen Enterprise-Funktionen
- bessere Diagnose bei Trunk- und Routing-Problemen

Was man bewusst noch nicht ueberfrachten sollte:

- vollwertige Cloud-Topologien
- komplexe SBC-Deployments
- TAPI, CRM, Fax, Multi-Tenant
- zu viele Integrationen gleichzeitig

## 8. Technischer Zielzustand

Die Architektur sollte in den naechsten Schritten so aussehen:

- Asterisk bleibt die Runtime fuer SIP, Dialplan und Voicemail
- FastAPI bleibt die einzige Schreibschicht fuer Konfiguration
- React bleibt die Admin-Oberflaeche
- SQLite bleibt fuer die aktuelle Groessenordnung ausreichend
- alle Asterisk-Konfigurationsdateien werden ausschliesslich aus validierten Daten generiert
- jede einzelne Konfigurationsdatei-Regenerierung ist fehler-isoliert (Phase A, Punkt 2) - ein kaputtes Feature darf niemals unbeteiligte Konfiguration mitreissen
- Secrets-at-rest ist eine bewusste, dokumentierte Entscheidung, nicht ein Nebeneffekt (D8)

Wichtigster Leitsatz:

Keine neue Funktion ohne klaren UI-Flow, valide Migration und mindestens einen Regressionstest fuer den betroffenen Konfigurationspfad.

## 9. Konkrete Reihenfolge fuer die naechsten Versionen

Reihenfolge ist durch Abhaengigkeiten bestimmt, nicht nur durch Prioritaetsgefuehl.

### v0.7.43 bis v0.7.46 - Stabilisierung

Abhaengigkeit: keine, kann sofort starten.

- ~~Numbering-Space-Dienst (Phase A.1)~~ - erledigt 0.7.65
- ~~Fehler-Isolation der Config-Regenerierung (Phase A.2)~~ - erledigt 0.7.63
- ~~Routing-Regressionstests ausbauen (Phase A.3, A.4)~~ - erledigt 0.7.67/0.7.68/0.7.70
- ~~CI/Build/Release-Prozess absichern (Phase A.5)~~ - erledigt 0.7.64
- ~~IVR-Audio-Upload robust machen (Phase A.6)~~ - erledigt 0.7.66
- **UI-Konsistenz fuer Routing, IVR und Rufgruppen (Phase A.7) - einziger noch offener Phase-A-Punkt.** Manuelle Checkliste, kein automatischer Test moeglich (dunkles Theme, Dropdowns, Editing-Flows angleichen).
- ~~Migrationskanten schliessen (Phase A.8)~~ - erledigt 0.7.70

### v0.8.x - Betriebsreife

Abhaengigkeit: Phase A muss abgeschlossen sein, insbesondere die Fehler-Isolation (A.2), bevor neue Features (Business Hours, Feiertage) das Risiko erneuter Kaskaden-Ausfaelle bekommen.

- Business Hours + Feiertage
- Secrets-Entscheidung treffen, dann Backup/Restore
- Trunk-Diagnose und bessere Admin-Hinweise
- Bessere Tabellen und Filter in der Verwaltung

### v0.9.x - erste echte Business-Funktionen

Abhaengigkeit: Numbering-Space-Dienst (A.1) zwingend fertig, da Queue und Konferenz eigene Nummern im 10-99-Bereich brauchen.

- Telefonbuch
- Sprachansagen-Manager
- Queue-Grundfunktion (siehe Aufwandshinweis Abschnitt 6 - Live-Zustand noetig)
- Konferenz-Grundfunktion

### v1.0 - "kleine Business-PBX ist alltagstauglich"

- stabile Releases
- gute Routing- und Zeitsteuerung
- Telefonbuch
- Queue oder Konferenz, mindestens in sauberer Basisversion
- Backup/Restore mit geklaerter Secrets-Behandlung
- klare Doku fuer Einrichtung und Betrieb

## 10. Nicht in die naechste Phase ziehen

Diese Themen sind interessant, sollten aber bewusst zurueckgestellt werden:

- SBC-Image fuer Raspberry Pi
- OpenAI-TTS als fruehes Pflichtfeature
- LDAP
- WebRTC
- umfangreiche Enterprise-Security-Matrix
- Video-Telefonie

Grund:
Sie erzeugen viel technische Last, bevor die Kernanlage wirklich stabil und angenehm administrierbar ist.

## 11. Konkrete naechste Tickets

Reihenfolge nach Abhaengigkeit, nicht nach Wunsch. Erledigt seit der letzten Fassung: Config-Regenerierung (D6, 0.7.63), CI-Haertung (D10, 0.7.64), Numbering-Space-Dienst (D5, 0.7.65), IVR-Audio-Normalisierung (D7, 0.7.66), referenzielle Integritaet beim Loeschen (0.7.67), kombinierter Dialplan-Regressionstest (0.7.68), Secrets-Verschluesselung + Mehrfach-Nebenstellen pro Geraet (D8, 0.7.69), Migrations-Testabdeckung + Fehlertexte in der UI (0.7.70), Backup/Restore (0.7.71), Feiertage + Business-Hours-UI (0.7.72/0.7.73), Telefonbuch (0.7.74) - Phase A ist bis auf Punkt 7 (UI-Konsistenz, manuelle Checkliste) fertig, Phase B ist praktisch durch, und das erste "Prioritaet Hoch"-Feature (Telefonbuch) ist live.

1. **Externe Anrufe zeigen "Anonymous" trotz uebermittelter Rufnummer klaeren (D15-Folgefehler, neu 2026-07-06)** - noch nicht per Trace verifiziert, aber aktiv beim Nutzer aufgetreten. Naechster Schritt vor allem anderen, weil live kaputt.
2. UI-Konsistenz-Durchgang (Phase A.7, letzter offener Phase-A-Punkt) - manuelle Checkliste durch alle Dialoge/Dropdowns/Tabellen
3. Telefonbuch-CallerID-Abgleich fuer eingehende Anrufe (natuerliche Folge-Erweiterung aus 0.7.74)
4. Sprachansagen als wiederverwendbare Objekte einfuehren

## 12. Entscheidung

Die realistische Produktstrategie fuer HA-Phone ist:

- erst eine zuverlaessige kleine PBX bauen
- dann die wichtigsten Admin-Funktionen von 3CX und Yeastar uebernehmen
- erst spaeter in Richtung Cloud, SBC und groessere Enterprise-Funktionen wachsen

Das macht das Projekt nicht kleiner. Es macht es nur deutlich wahrscheinlicher, dass es wirklich gut wird.

Der entscheidende Unterschied zur vorherigen Fassung dieser Roadmap: Phase A ist jetzt keine Liste von Absichten mehr, sondern haengt an einem konkreten, wachsenden Defekte-Register (Abschnitt 3). Ein Punkt gilt erst als erledigt, wenn sein zugehoeriger Registereintrag auf "behoben" steht und ein Test das belegt.
