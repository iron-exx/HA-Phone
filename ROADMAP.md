# HA-Phone Roadmap

Stand: Juli 2026
Aktuelle Add-on-Linie: `0.7.42`
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
| D5 | `ring_groups.py` + `ivr.py` | Zwei fast identische `_validate_*_number`-Funktionen, jede prueft unabhaengig gegen Extension + RingGroup + IVRMenu. Reiner Copy-Paste-Stand; die dritte Kopie kommt spaetestens mit Queues (v0.9). | offen -> Phase A, Punkt 1 |
| D6 | Boot-Skript `10-asterisk-init.sh` | Alle Config-Regenerierungen (Extensions, Voicemail, Routing, Mail, Trunk) laufen in einem einzigen Python-Block ohne Isolation. Ein Fehler in einer Regenerierung (siehe D1) verhindert stillschweigend auch alle anderen, inklusive Trunk und Mail. | offen -> Phase A, Punkt 2 (neu) |
| D7 | `ivr.py::upload_greeting` | Prueft nur die Dateiendung `.wav`, validiert/konvertiert aber nicht Samplerate/Kanaele/Codec. Eine aus Audacity oder vom Handy exportierte WAV (z.B. 44.1kHz Stereo) wird von Asterisk `Background()` nicht sauber abgespielt. `sox` ist bereits im Image installiert -> Konvertierung ist ein kleiner, klar umrissener Fix. | offen -> Phase A, Punkt 6 (neu) |
| D8 | `models.py` (`Trunk.password`, `SmtpSettings.password`, `Extension.sip_password`) | Alle Zugangsdaten liegen im Klartext in SQLite. Fuer den aktuellen Single-Host-Betrieb tolerierbar, wird aber zum Problem, sobald Backup/Export (Phase B) existiert. | offen -> Entscheidung noetig vor Phase B, Punkt 4 |
| D9 | Keine Locking-Strategie um `_regenerate_routing_conf` / Boot-Regenerierung | Zwei gleichzeitige Schreibvorgaenge (zwei Admin-Tabs, oder ein Request waehrend des Boots) koennen die generierten Dateien in unvorhersehbarer Reihenfolge ueberschreiben. `render_conf` selbst schreibt atomar (Temp-Datei + `os.replace`), es gibt aber keine Sperre ueber die gesamte DB-Lese- plus Render-Sequenz. | offen -> Phase A, Beobachtung, kein Blocker |

Regel ab jetzt: Jeder in Code-Review oder Bugfix gefundene Defekt wird hier eingetragen, bevor er behoben wird, und erst nach Fix + Test als "behoben" markiert. Kein stillschweigendes Reparieren ohne Spur.

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

**1. Zentralen Numbering-Space-Dienst einfuehren (loest D5)**
- Ein einziger Ort (Service-Funktion oder View ueber Extension+RingGroup+IVRMenu) beantwortet "ist Nummer X im Bereich 10-99 frei/belegt/von wem".
- `ring_groups.py::_validate_ring_group_number` und `ivr.py::_validate_ivr_number` rufen diesen Dienst auf, statt eigene Kopien zu pflegen.
- *Fertig, wenn:* keine der drei Routing-Domaenen (Extension, RingGroup, IVRMenu) mehr eine eigene Cross-Table-Kollisionspruefung hat, und ein Test beweist, dass eine Nummernkollision zwischen allen drei Typen konsistent abgelehnt wird.
- *Abhaengigkeit:* Queues und Konferenzraeume (v0.9) brauchen denselben Dienst - vor v0.9 zwingend erledigt.

**2. Config-Regenerierung fehler-isolieren (loest D6, verhindert D1-Klasse-Bugs strukturell)**
- Jede einzelne Regenerierungsfunktion (`_regenerate_extensions_conf`, `_regenerate_voicemail_conf`, `_regenerate_routing_conf`, `_regenerate_trunk_conf`, `regenerate_mail_configs`) wird im Boot-Skript und in jedem Router einzeln try/except-behandelt und geloggt, nicht mehr als ein monolithischer Block.
- Ein Fehler in einer Regenerierung darf die anderen nicht verhindern.
- Sichtbares Fehlersignal im Dashboard, wenn eine Regenerierung fehlgeschlagen ist ("Trunk-Konfiguration konnte nicht aktualisiert werden: <Ursache>"), nicht nur ein Log-Eintrag.
- *Fertig, wenn:* ein absichtlich kaputtes IVR-Menu (oder aehnliches) in einem Test weiterhin eine funktionierende Trunk- und Mail-Konfiguration nach einem Neustart erlaubt.

**3. Routing-Modell konsistent validieren**
- Ziele fuer Route, Rufgruppe, IVR und Zeitbedingung muessen im Backend konsistent validiert werden (baut auf Punkt 1 auf).
- Fehlertexte muessen fuer Admins klar lesbar sein (keine rohen Pydantic/SQLAlchemy-Fehler in der UI).
- Delete- und Aenderungsfaelle muessen sauber behandelt werden (was passiert mit Routen, die auf eine geloeschte Rufgruppe zeigen? Aktuell: nichts, die Route bleibt und referenziert eine tote ID - muss entweder blockiert oder mit Warnung erlaubt werden).
- *Fertig, wenn:* Loeschen einer referenzierten Rufgruppe/IVR entweder verhindert wird oder abhaengige Routen sichtbar als "Ziel fehlt" markiert werden, statt still ins Leere zu zeigen.

**4. Dialplan-Generierung absichern**
- Zentrale Tests fuer `extensions_routing.conf`, mindestens ein Regressionstest pro Konfigurationspfad: Extension, Rufgruppe, IVR, Zeitbedingung, Outbound-Regeln, und die Kombination aus allen gleichzeitig (das genaue Szenario, das D1 aufgedeckt hat).
- *Fertig, wenn:* CI schlaegt fehl, wenn `POST /api/ivrs` (oder jeder andere schreibende Endpunkt) nach dem Anlegen eines IVR-Menues einen Fehler wirft.

**5. Add-on-Release-Prozess haerten**
- Jede Version braucht Changelog, Versionsbump und erfolgreichen Multi-Arch-Build.
- Build-Fehler muessen vor Push lokal auffallen.
- GitHub Actions sollen nicht nur Image bauen, sondern Frontend-Build (`tsc --noEmit`) und Backend-Tests (`pytest`) als Pflichtschritte vor dem Image-Build ausfuehren, nicht danach oder gar nicht.
- *Fertig, wenn:* ein PR mit fehlschlagendem Test oder TypeScript-Fehler den Image-Build gar nicht erst startet.

**6. IVR-Audio-Upload robust machen (loest D7)**
- Hochgeladene WAV-Dateien serverseitig mit dem bereits vorhandenen `sox` auf das von Asterisk erwartete Format normalisieren (Samplerate, Mono, passender Codec), statt nur die Dateiendung zu pruefen.
- *Fertig, wenn:* eine 44.1kHz-Stereo-WAV nach Upload hoerbar im IVR abgespielt wird.

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

Reihenfolge nach Abhaengigkeit, nicht nach Wunsch:

1. Numbering-Space-Dienst extrahieren (loest D5, Voraussetzung fuer Ticket 4 und spaeter Queues)
2. Config-Regenerierung fehler-isolieren (loest D6, verhindert zukuenftige D1-artige Ausfaelle strukturell)
3. Routing-Regressionstests erweitern, insbesondere: IVR + gleichzeitiges Anlegen von Extension/Rufgruppe/Route (genau das Szenario aus D1)
4. IVR-Audio-Upload mit `sox` normalisieren (D7, klein und unabhaengig, kann jederzeit zwischengeschoben werden)
5. Referenzielle Integritaet bei Loeschungen klaeren (Route zeigt auf geloeschte Rufgruppe/IVR)
6. Zeitbedingungen in Business Hours + Feiertage ueberfuehren
7. Secrets-Entscheidung fuer Backup treffen, dann Backup/Restore entwerfen
8. Telefonbuch-Datenmodell und CRUD bauen
9. Sprachansagen als wiederverwendbare Objekte einfuehren

## 12. Entscheidung

Die realistische Produktstrategie fuer HA-Phone ist:

- erst eine zuverlaessige kleine PBX bauen
- dann die wichtigsten Admin-Funktionen von 3CX und Yeastar uebernehmen
- erst spaeter in Richtung Cloud, SBC und groessere Enterprise-Funktionen wachsen

Das macht das Projekt nicht kleiner. Es macht es nur deutlich wahrscheinlicher, dass es wirklich gut wird.

Der entscheidende Unterschied zur vorherigen Fassung dieser Roadmap: Phase A ist jetzt keine Liste von Absichten mehr, sondern haengt an einem konkreten, wachsenden Defekte-Register (Abschnitt 3). Ein Punkt gilt erst als erledigt, wenn sein zugehoeriger Registereintrag auf "behoben" steht und ein Test das belegt.
