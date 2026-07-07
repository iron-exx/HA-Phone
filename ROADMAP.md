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
| D8 | `models.py` (`Trunk.password`, `SmtpSettings.password`, `Extension.sip_password`) | Alle Zugangsdaten liegen im Klartext in SQLite. Fuer den aktuellen Single-Host-Betrieb tolerierbar, wird aber zum Problem, sobald Backup/Export (Phase B) existiert. | offen -> Entscheidung noetig vor Phase B, Punkt 4 |
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

**3. Routing-Modell konsistent validieren**
- Ziele fuer Route, Rufgruppe, IVR und Zeitbedingung muessen im Backend konsistent validiert werden (baut auf Punkt 1 auf).
- Fehlertexte muessen fuer Admins klar lesbar sein (keine rohen Pydantic/SQLAlchemy-Fehler in der UI).
- ~~Delete- und Aenderungsfaelle muessen sauber behandelt werden~~ - **Delete-Teil erledigt in 0.7.67:** Loeschen einer Rufgruppe/eines IVR-Menues wird mit `409` abgelehnt, solange eine Route oder (bei IVR) ein Untermenue-Verweis darauf zeigt; Frontend zeigt die konkrete Fehlermeldung statt generischem "Fehler beim Loeschen". Noch offen: Aenderungsfaelle (z.B. eine Rufgruppen-Nummer aendern, waehrend eine Route per ID darauf zeigt - referenziert weiterhin korrekt per ID, aber noch nicht explizit getestet) und die breitere Frage roher Backend-Fehler in Zeitbedingungen/anderen Formularen.
- *Fertig, wenn (Rest):* keine rohen Pydantic/SQLAlchemy-Fehlertexte mehr in einem der Routing-Formulare sichtbar sind.

**4. Dialplan-Generierung absichern**
- Zentrale Tests fuer `extensions_routing.conf`, mindestens ein Regressionstest pro Konfigurationspfad: Extension, Rufgruppe, IVR, Zeitbedingung, Outbound-Regeln, und die Kombination aus allen gleichzeitig (das genaue Szenario, das D1 aufgedeckt hat).
- *Fertig, wenn:* CI schlaegt fehl, wenn `POST /api/ivrs` (oder jeder andere schreibende Endpunkt) nach dem Anlegen eines IVR-Menues einen Fehler wirft.

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

**8. Datenmigrationen aufraeumen**
- Migrationen fuer neue Felder wie Rufgruppen-Nummer und IVR sauber halten.
- Altbestaende muessen ohne manuelle SQLite-Eingriffe migrieren.
- Aktuelles Muster (`if column not in cols: ALTER TABLE ...` in `database.py`) ist fuer die heutige Groesse okay, sollte aber nicht beliebig weiterwachsen. Ab der naechsten neuen Tabelle mit Fremdschluessel-Bezug pruefen, ob ein leichtgewichtiges Migrationswerkzeug (z.B. Alembic) den manuellen Ansatz ablösen sollte.
- *Fertig, wenn:* ein Upgrade von der aeltesten unterstuetzten Version (0.7.0) auf HEAD in einem Testlauf ohne manuelle SQL-Eingriffe durchlaeuft.

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

**3. Zeitsteuerung alltagstauglich machen**
- Einfache Business-Hours-Oberflaeche.
- Feiertage als echte Erweiterung der Zeitbedingungen.
- Klare Regelprioritaet.

**4. Backup und Restore - inklusive expliziter Secrets-Entscheidung (haengt an D8)**
- Export/Import der PBX-Konfiguration, mindestens JSON/ZIP auf Add-on-Ebene.
- Vor der Umsetzung muss entschieden werden: Secrets (Trunk-Passwort, SMTP-Passwort, SIP-Passwoerter) im Export ein- oder ausschliessen? Wenn eingeschlossen: verschluesselt mit einem vom Nutzer eingegebenen Passwort, nicht im Klartext in der ZIP.
- *Fertig, wenn:* ein Restore auf einer frischen Instanz eine funktionierende PBX ergibt, und die Entscheidung zu Secrets im Backup dokumentiert und umgesetzt ist (nicht implizit "liegt halt mit drin").

Definition of done fuer Phase B:

- kleine Anlage kann ohne Shell-Eingriffe eingerichtet, gesichert und geaendert werden

## 6. Danach sinnvolle Erweiterungen

Diese Features sind sinnvoll, aber erst nach Phase A und B.

### Prioritaet Hoch

- Telefonbuch mit CSV-Import/Export
- Feiertage und erweiterte Geschaeftszeiten
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

- Numbering-Space-Dienst (Phase A.1) - **zuerst**, weil Punkt 3 und spaeter Queues darauf aufbauen
- Fehler-Isolation der Config-Regenerierung (Phase A.2)
- Routing-Regressionstests ausbauen (Phase A.3, A.4)
- CI/Build/Release-Prozess absichern (Phase A.5)
- IVR-Audio-Upload robust machen (Phase A.6) - klein, unabhaengig, kann parallel
- UI-Konsistenz fuer Routing, IVR und Rufgruppen (Phase A.7)
- Migrationskanten schliessen (Phase A.8)

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

Reihenfolge nach Abhaengigkeit, nicht nach Wunsch. Erledigt seit der letzten Fassung: Config-Regenerierung (D6, 0.7.63), CI-Haertung (D10, 0.7.64), Numbering-Space-Dienst (D5, 0.7.65), IVR-Audio-Normalisierung (D7, 0.7.66), referenzielle Integritaet beim Loeschen (0.7.67) - alle fuenf waren hier Ticket 1-5, sind raus.

1. **Externe Anrufe zeigen "Anonymous" trotz uebermittelter Rufnummer klaeren (D15-Folgefehler, neu 2026-07-06)** - noch nicht per Trace verifiziert, aber aktiv beim Nutzer aufgetreten. Naechster Schritt vor allem anderen, weil live kaputt.
2. Routing-Regressionstests erweitern, insbesondere: IVR + gleichzeitiges Anlegen von Extension/Rufgruppe/Route (genau das Szenario aus D1) - Grundstock existiert bereits (`test_api.py`), Matrix noch nicht vollstaendig
3. Zeitbedingungen in Business Hours + Feiertage ueberfuehren
4. Secrets-Entscheidung fuer Backup treffen, dann Backup/Restore entwerfen
5. Telefonbuch-Datenmodell und CRUD bauen
6. Sprachansagen als wiederverwendbare Objekte einfuehren

## 12. Entscheidung

Die realistische Produktstrategie fuer HA-Phone ist:

- erst eine zuverlaessige kleine PBX bauen
- dann die wichtigsten Admin-Funktionen von 3CX und Yeastar uebernehmen
- erst spaeter in Richtung Cloud, SBC und groessere Enterprise-Funktionen wachsen

Das macht das Projekt nicht kleiner. Es macht es nur deutlich wahrscheinlicher, dass es wirklich gut wird.

Der entscheidende Unterschied zur vorherigen Fassung dieser Roadmap: Phase A ist jetzt keine Liste von Absichten mehr, sondern haengt an einem konkreten, wachsenden Defekte-Register (Abschnitt 3). Ein Punkt gilt erst als erledigt, wenn sein zugehoeriger Registereintrag auf "behoben" steht und ein Test das belegt.
