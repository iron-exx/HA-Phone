# Changelog

## 0.7.57

**Fix - Provisioning-Links ohne Portnummer (wie SIP mit Standardport 5060)**
- Backend lauscht jetzt auf Port 80 statt 8099 (`ingress_port` + uvicorn-Bind angepasst). Port 80 ist der HTTP-Standardport, Browser/Apps haengen ihn nie sichtbar an eine URL an - genau wie SIP automatisch Port 5060 nutzt, ohne dass man ihn eintragen muss.
- Betrifft den Linphone-Provisioning-Link UND die Gigaset/DECT-Autoprovisionierungs-URLs (`backend/routers/provisioning.py`) - beide nutzten bisher denselben ungewoehnlichen Port.
- Vor der Umstellung geprueft, dass Port 80 auf dem Host frei ist (kein Konflikt mit einem anderen Add-on).
- Zusammen mit dem `linphone-config:`-URI-Fix aus 0.7.55 sollte der Linphone-QR-Code jetzt vollstaendig funktionieren: gueltige URI-Syntax UND eine direkt erreichbare Adresse ohne Portnummer.

## 0.7.56

**Fix - Updates dauerten mehrere Minuten (lokaler Asterisk-Kompilierbau statt Image-Pull)**
- `config.yaml` fehlte das Addon-Feld `image`. Der GitHub-Actions-Workflow baut bei jedem Push bereits ein fertiges Multi-Arch-Image nach `ghcr.io/iron-exx/ha-phone/{arch}`, aber ohne dieses Feld ignoriert der Supervisor das komplett und kompiliert bei jedem Install/Update Asterisk lokal aus dem Quellcode auf dem HA-Host (`./configure && make` im Dockerfile) - mehrere Minuten, je nach Hardware deutlich mehr.
- `image: "ghcr.io/iron-exx/ha-phone/{arch}"` ergaenzt. Vor dem Einchecken verifiziert, dass das GHCR-Package tatsaechlich oeffentlich und ohne Zugangsdaten pullbar ist (Token-Exchange-Flow, 200 auf Manifest-Fetch), damit der Supervisor es ohne Anmeldedaten ziehen kann.
- Ab dieser Version sollte ein Update ein reiner Registry-Pull des bereits gebauten Images sein statt eines vollstaendigen lokalen Kompilierlaufs. Dieses Update selbst (0.7.55 -> 0.7.56) laeuft noch einmal als lokaler Build, da die vorige Version noch ohne `image`-Feld installiert war.

## 0.7.55

**Fix - Linphone QR-Code/Provisioning-Link ungueltig**
- `buildLinphoneConfigUri` erzeugte `linphone-config://http://host:8099/...` - ein doppelter Scheme-Separator (`://` gefolgt von einem weiteren `http://`). Das offizielle Linphone-Format ist `linphone-config:` (ein Doppelpunkt) gefolgt von der vollen Config-URL. Dadurch war die im QR-Code kodierte URI schlicht ungueltig, unabhaengig von Host/Port.
- "In Linphone oeffnen" navigierte `window.location`, was innerhalb des Home-Assistant-Ingress-`<iframe>` nur das iframe selbst umleitet - der Browser bietet das Custom-Scheme dann nie dem Betriebssystem/der App an. Navigiert jetzt stattdessen das Top-Window (mit Fallback auf das lokale Fenster ausserhalb von Ingress).
- "Kopieren" nutzte die Clipboard-API nur, wenn `window.isSecureContext` true war, und warf sonst ohne Fallback einen Fehler. Jetzt: Clipboard-API zuerst versuchen, bei Fehlschlag auf `execCommand` zurueckfallen, und im schlimmsten Fall den Text selektiert lassen statt nur eine Fehlermeldung zu zeigen.
- Live verifiziert: der Provisioning-Link selbst (`http://<lan-ip>:8099/api/linphone/provision/<token>`) war immer erreichbar und lieferte gueltiges Provisioning-XML - das Problem lag ausschliesslich am URI-Format und an der iframe-Navigation, nicht am Host/Port.

## 0.7.54

**Doku - Deutsche Glasfaser/aarenet erwartet nationales Format, nicht E.164**
- Live per SIP-Trace verifiziert: die aarenet/AareSwitch-Plattform (Deutsche Glasfaser Whitelabel) weist ausgehende Anrufe mit E.164-Zielnummer (`491741814689`) per Inband-Ansage ("diese Rufnummer ist ungueltig") ab - kein SIP-Fehlercode, sondern 183 Session Progress mit Ansage, danach Cancel.
- Passt zur bereits bekannten Eigenheit dieser Plattform: Die Registrierungsidentitaet (AOR/From/Contact) nutzt ebenfalls die nationale Rufnummer mit fuehrender 0, nicht E.164 (siehe `pjsip_trunk.conf.j2`).
- Kein Code-Bug - die betroffene Ausgehende Regel ist nutzerkonfigurierbar. Workaround: Regel `0.` auf "0 Ziffern entfernen, nichts voranstellen" stellen, damit die Nummer national (mit fuehrender 0) unveraendert zum Trunk geht statt zu `+49...` umgeschrieben zu werden.
- Hinweis direkt bei `DEFAULT_OUTBOUND_RULES` ergaenzt, damit das bei einer frischen Datenbank (z.B. Neuinstallation) nicht erneut unbemerkt auftritt.

## 0.7.53

**Fix - Interne Anrufe, Voicemail und Plus-Rufnummern**
- Videofaehige Nebenstellen nutzen wieder den normalen internen Wahlkontext statt faelschlich `doorbell-out`.
- Bereits normalisierte Rufnummern wie `+49...` koennen jetzt auch im Trunk-Kontext sauber rausgewaehlt werden.
- Asterisk laedt die fehlenden Voicemail-Abhaengigkeiten `res_adsi` und `res_smdi`, damit der Rueckfall auf Mailbox nicht mehr mit einem Modulfehler scheitert.

## 0.7.51

**Fix - Linphone Link ohne Ingress-Pfad**
- Provisioning-Link und QR-Code werden nicht mehr aus der Home-Assistant-Ingress-URL gebaut.
- Statt `:8123/api/hassio_ingress/...` nutzt HA-Phone jetzt fuer Linphone die direkte Add-on-Adresse auf Port `8099`.
- Dadurch zeigen QR und Kopier-Link wieder auf die eigentliche PBX-Provisioning-URL.

## 0.7.50

**Fix - Linphone QR Scanner**
- Der angezeigte QR-Code nutzt jetzt wieder direkt das Linphone-spezifische Schema `linphone-config://...`.
- Der normale Provisioning-Link bleibt separat fuer die manuelle Eingabe in Linphone sichtbar.
- Damit wird der QR-Scanner in Linphone gezielter mit dem von der App erwarteten URI-Format gefuettert.

## 0.7.49

**Fix - Linphone Provisioning XML**
- Die fuer Linphone ausgelieferte Provisioning-XML wurde an das offizielle Linphone-Beispiel angenaehert.
- `reg_proxy` und `reg_route` werden jetzt im erwarteten Format ohne vorangestelltes `sip:` geschrieben.
- Zusaetzliche Auth-/Proxy-Felder (`userid`, `realm`, `publish`, `dial_escape_plus`) und das Linphone-XML-Schema wurden ergaenzt.
- Ziel ist, den weiter gemeldeten Fehler **"ungueltige URI"** beim Linphone-Provisioning zu beseitigen.

## 0.7.48

**Feature/Fix - IVR Untermenues und Dialog-Layout**
- IVR-Menuepunkte koennen jetzt auch auf ein anderes IVR-Menue als Untermenue zeigen.
- Die Auswahl erfolgt ueber die interne IVR-Durchwahl, also passend zur PBX-Logik.
- Selbstverweise werden serverseitig blockiert, damit ein Menue nicht direkt auf sich selbst zeigt.
- Der IVR-Dialog wurde responsiver gemacht: Optionszeilen umbrechen jetzt sauber und das Fenster bleibt innerhalb des sichtbaren Bereichs statt rechts abgeschnitten zu werden.

## 0.7.47

**Fix - Linphone QR robuster**
- Der QR-Code fuer Linphone enthaelt wieder die reine Provisioning-URL statt eines `linphone-config`-Schemas. Das ist robuster fuer den In-App-QR-Scanner.
- Zusaetzlich gibt es jetzt einen separaten Button **"In Linphone oeffnen"**, der das Linphone-spezifische Schema verwendet.
- Der Kopier-Button nutzt jetzt auch in Umgebungen ohne modernes Clipboard-API einen Fallback, damit der Provisioning-Link im Home-Assistant-UI besser kopierbar bleibt.

## 0.7.46

**Fix - Linphone QR / Provisioning**
- QR-Code fuer Linphone nutzt jetzt das Linphone-spezifische URI-Format `linphone-config:` statt nur den nackten Provisioning-Link.
- Die ausgelieferte Provisioning-XML setzt den SIP-Proxy jetzt in der kompakteren Linphone-Form `sip:host;transport=udp` statt `sip:host:5060;transport=udp`.
- Dadurch wird der QR-/Provisioning-Flow von Linphone besser erkannt und die gemeldete "ungueltige URI" vermieden.

## 0.7.45

**Fix - QR-Dialog absturzfrei**
- Absturz auf der Extensions-Seite behoben: der neue Linphone-QR-Dialog nutzte ein `FormLabel` ausserhalb eines `FormField`, wodurch React Hook Form beim Rendern mit `getFieldState ... is null` abstuerzte.
- Der Provisioning-Link im QR-Dialog wird jetzt ohne Formular-Kontext gerendert, damit die Seite in Home Assistant Ingress stabil laeuft.

## 0.7.44

**Feature - Linphone QR fuer Nebenstellen**
- In der Nebenstellenliste gibt es jetzt pro Extension eine neue Aktion **"Linphone QR"**. Damit wird ein QR-Code samt Provisioning-Link erzeugt, den Linphone direkt scannen kann.
- HA-Phone stellt dafuer eine tokenisierte Provisioning-URL bereit. Die normale Nebenstellenliste liefert diesen Token nicht aus, damit die Verbindungsdaten nicht versehentlich offengelegt werden.
- Die Linphone-Konfiguration wird als Provisioning-XML ausgeliefert und setzt Rufnummer, SIP-Server, Passwort und Video-Option passend fuer die gewaehlte Nebenstelle.
- Frontend/Build: QR-Code-Erzeugung im Web-UI integriert.

## 0.7.43

**Fix - GitHub-Build fuer Add-on-Update**
- Fehlgeschlagenen CI-Build fuer `0.7.42` repariert: in `IVR.tsx` verbliebene unbenutzte Imports (`Check`, `X`, `Separator`) entfernte TypeScript im lokalen Lauf nicht, im Docker-CI aber schon.
- Dadurch kann das Add-on-Image wieder gebaut und das Update in Home Assistant installiert werden.

## 0.7.42

**Fix (kritisch, per Live-Reproduktion verifiziert) — IVR brach jede Config-Regenerierung**
- `_regenerate_routing_conf` setzte `ivr.parsed_options` direkt auf ein `IVRMenu`-SQLModel-Tabellenobjekt, das dieses Feld nicht deklariert → `ValueError: "IVRMenu" object has no field "parsed_options"`. Reproduziert: `POST /api/ivrs` schlug mit 500 fehl, sobald ein IVR-Menü existierte. Da dieselbe Funktion von Extensions-, Rufgruppen-, Routen- und Trunk-Endpunkten **und dem Boot-Skript** aufgerufen wird, brach ab dem ersten angelegten IVR-Menü **jede** dieser Operationen — inklusive der Config-Regenerierung beim Neustart (Trunk/Voicemail/Mail-Settings wurden dann still nicht mehr aktualisiert). Fix: IVR-Daten werden für das Template jetzt als reines dict übergeben (Jinja2-Punktzugriff funktioniert unverändert), keine Mutation des ORM-Objekts mehr.
- **IVR-Endlosschleife:** Der Ungültig-Zähler (`IVR_INVALID_COUNT`) wurde bei jeder Wiederholung auf 0 zurückgesetzt, weil der Replay-Pfad zurück zu `s,1` sprang — derselbe Einstiegspunkt, der den Zähler initialisiert. `max_invalid_tries` griff dadurch nie; der Anrufer konnte beliebig oft falsch eingeben, ohne dass aufgelegt wurde. Fix: eigener `menu`-Einstiegspunkt für Wiederholungen, der den Zähler nicht zurücksetzt.
- Verbliebene Mojibake-Reste in Routing.tsx behoben (`wÃ¤hlbar`, `hinzugefÃ¼gt`, `LÃ¤uft`, `lÃ¶schen` → korrekte Umlaute) — trotz vorherigem "Encoding gefixt"-Commit übersehen.
- Rufgruppen ohne eigene interne Durchwahl (z.B. migrierte Altbestände mit `number=0`) waren im Ziel-Dropdown für eingehende Routen unsichtbar, obwohl die Route über die DB-ID (nicht die Nummer) läuft — Filter entfernt, betroffene Gruppen sind jetzt wählbar.
- Ursache für die Lücke: Das neue IVR-Feature hatte keinerlei Backend-Tests. Alle Fixes wurden per FastAPI-TestClient-Reproduktion end-to-end verifiziert (IVR anlegen → Extension/Rufgruppe/Route anlegen → kein Crash, korrekter generierter Dialplan).

## 0.7.41

**Feature — IVR-Menü (Digitaler Empfang)**
- Neues IVR-Menü-System (Interactive Voice Response) ähnlich wie bei 3CX/Yeastar.
- Anrufer hören eine Begrüßung und werden per Tastendruck weitergeleitet.
- Optionen: Nebenstelle, Rufgruppe, Voicemail oder Auflegen.
- IVR-Menüs haben eine eigene interne Durchwahl (10-99) und können als Routing-Ziel verwendet werden.
- Begrüßungs-Upload als WAV-Datei.
- Timeout und max. Falscheingaben konfigurierbar.
- Neue Sidebar-Navigation "IVR-Menüs".

## 0.7.40

**Feature/Fix - Rufgruppen als echte interne Ziele**
- Rufgruppen haben jetzt eine eigene interne Durchwahl (`10-99`) und dürfen nicht mit Nebenstellen oder anderen Rufgruppen kollidieren.
- Rufgruppen können nach dem Anlegen bearbeitet werden: Durchwahl, Name, Mitglieder und Timeout.
- Eingehende Routen wählen Ziele jetzt per Dropdown aus: Nebenstelle oder Rufgruppe mit verständlichem Namen statt technischer ID.
- Der Asterisk-Dialplan erzeugt interne Rufgruppen-Durchwahlen, damit z.B. `10 = Zentrale` direkt gewählt werden kann.

## 0.7.39

**Fix — Lesbarkeit und Rufgruppen-Bedienung**
- Dialogfenster sind jetzt deckend dunkel statt transparent, damit Routing-Formulare lesbar bleiben.
- Radix-Selects und native Browser-Dropdowns nutzen dunkle Hintergründe und helle Schrift.
- Rufgruppen-Mitglieder werden beim Anlegen per Nebenstellen-Auswahl gesetzt statt per fehleranfälligem Zahlenfeld.
- Die Rufgruppen-Maske zeigt klar an, wenn erst Nebenstellen angelegt werden müssen.

## 0.7.38

**Fix — Routing- und Rufgruppen-Basis**
- Interne Nebenstellen `10-99` werden im Dialplan jetzt vollständig unterstützt; vorher waren intern nur `10-19` erreichbar.
- Rufgruppen werden gegen vorhandene Nebenstellen validiert und doppelte Mitgliedschaften werden verhindert.
- Nebenstellen können im Extension-Dialog direkt Rufgruppen zugewiesen werden; die Tabelle zeigt die aktuellen Gruppen.
- Deaktivierte Nebenstellen werden nicht mehr als PJSIP-Endpunkte gerendert und der Routing-Dialplan wird bei Änderungen an Nebenstellen aktualisiert.
- Doorbell-/Rufgruppen-Dialplan erzeugt nur noch einen stabilen `[doorbell-out]`-Kontext.
- AMI-Secret wird nicht mehr teilweise ins Log geschrieben.

## 0.7.37

**Fix — SMTP-Test**
- Der SMTP-Test nutzt jetzt die **aktuell eingegebenen Formulardaten** (nicht den gespeicherten Wert) → du testest genau das, was du siehst, ohne vorher speichern zu müssen. Leere Felder fallen auf die gespeicherten Werte zurück (leeres Passwort = gespeichertes wird genutzt).
- Passwort wird beim Speichern/Testen von umgebenden Leerzeichen befreit (häufige Copy-Paste-Ursache für „535 wrong user/password").

## 0.7.36

**Feature — Remote-Softphone via VPN (Tailscale/WireGuard)**
- `local_net` um die VPN-Bereiche erweitert (`100.64.0.0/10` Tailscale-IPv4, `fd7a:115c:a1e0::/48` Tailscale-IPv6, `172.16.0.0/12`). Damit behandelt Asterisk Softphones, die über ein VPN verbunden sind, als „lokal" → RTP/Audio läuft sauber über den Tunnel statt über die externe IP. Grundlage für Linphone von unterwegs über Tailscale (SIP-Server = Tailscale-IP der PBX). Der DG-Trunk (Medien zu 185.x, öffentlich) bleibt unberührt.

## 0.7.35

**Fix + Feature — Rufgruppen**
- **Bug:** Beim Anlegen/Ändern einer Rufgruppe wurde eine veraltete Routing-Generierung genutzt, die eingehende Routen und Ausgangsregeln aus dem Dialplan **löschte**. Jetzt nutzt sie die gemeinsame, vollständige Generierung.
- **Neu:** Rufgruppen-Verwaltung in der UI (Routing → Rufgruppen): Name, Nebenstellen (z.B. 10,11,12), Timeout. Mehrere Telefone klingeln gleichzeitig; als Ziel einer eingehenden Route wählbar.

## 0.7.34

**Build / Aufräumen (Code-Review)**
- CI-Workflow repariert: zeigte noch auf den alten Ordner `hassio-bpx` → baute nie ein Image. Jetzt `ha-phone`, beide Architekturen, versioniert getaggt, mit Build-Cache. Grundlage für vorgebaute Images (GHCR) → künftige Updates werden **geladen statt kompiliert** (Sekunden statt Minuten).
- Dockerfile: toten Node.js-Install aus dem Asterisk-Build-Stage entfernt (Frontend wird in separater Stage gebaut) — schlankerer Build.

## 0.7.33

**Feature — Postausgang (SMTP) für Voicemail-per-E-Mail**
- Neuer Bereich **Settings → Postausgang (SMTP)**: Server, Port, Verschlüsselung (STARTTLS/SSL/keine), Benutzer, Passwort, Absender — mit **Test-Button** (sendet eine Test-E-Mail und meldet den genauen Fehler bei Problemen).
- Voicemail-Mails gehen jetzt über **msmtp** (im Image ergänzt) an deinen SMTP-Server. Vorher stand `mailcmd = /bin/true` → Mails wurden still verworfen.
- `voicemail.conf`-[general] wird aus den SMTP-Settings generiert (`serveremail`, `mailcmd`); ohne SMTP bleibt es bei `/bin/true` (keine Fehler).
- Backend: `SmtpSettings`-Modell + `/api/settings/smtp` (GET/POST) + `/api/settings/smtp/test`.

## 0.7.32

**Fix (kritisch — der eigentliche Grund für den Gesprächsabbruch, per Log belegt)**
- **Bridging-Module fehlten** (`bridge_simple`, `bridge_softmix`, `bridge_native_rtp`, `bridge_holding`). Ohne Bridge-Technologie kann Asterisk zwei Gesprächsbeine nicht zusammenschalten → jeder Anruf brach **beim Annehmen** ab, rein wie raus (`Could not create class basic. No technology to support it.`). Jetzt gebaut + geladen → Gespräche bleiben stehen.
- **`func_callerid` fehlte** → `Set(CALLERID(...))` scheiterte (`Function CALLERID not registered`) → keine ausgehende Rufnummer (CLIP). Ergänzt (+ `func_channel/strings/logic`, `res_musiconhold`). Ausgehende Rufnummer wird jetzt übermittelt.
- Ursache war die `autoload = no`-Ladeliste ohne Bridging-/Function-Module.

## 0.7.31

**Fixes & Feature**
- **Voicemail-Modul**: `app_voicemail` wird jetzt gebaut und geladen. Vorher fehlte es → „No application 'Voicemail'" beim eingehenden Anruf (Rückfall auf Voicemail scheiterte).
- **CLIP (ausgehende Rufnummer)**: Der Dialplan setzt die Caller-ID beim ausgehenden Anruf jetzt explizit auf die Trunk-Rufnummer in E.164 (`Set(CALLERID(all)=+49…)`), unabhängig von der Caller-ID der anrufenden Nebenstelle. Vorher wurde die Nummer nicht/als „Anonymous" gesendet.
- **Codec-Auswahl im Trunk** (wie bei den großen Herstellern, abgespeckt): u-law / a-law / G.722 / GSM / G.726 wählbar, Reihenfolge = Priorität. Default `ulaw,alaw` (DG/outbox-Standard, ohne G.722). Editierbar auf der Trunk-Seite.
- Provisioning: Dropdown-Text war auf dunklem Grund unlesbar (`color-scheme:dark` + dunkler Hintergrund gesetzt).

## 0.7.30

**Feature — Dashboard-Ausbau**
- Dashboard neu gestaltet (Dark-OLED, wie sysvoice): Live-Flächendiagramm für aktive Anrufe (rollende Historie, 5-Sek-Takt), Donut-Gauges für „Nebenstellen online" und „Aktive Gespräche", Trunk-Status-Panel, Geräte-Zähler (Provisioning) und kompakte Metrik-Chips. Alle Grafiken als schlanke Inline-SVG (keine externe Chart-Lib).

## 0.7.29

**Feature — Auto-Provisioning (neu)**
- Neue Seite **Provisioning**: Endgeräte per MAC verwalten (Tischtelefone, DECT-Basen, Türstationen) und automatisch mit den SIP-Daten einer Nebenstelle konfigurieren — wie bei 3CX/Yeastar.
- **Editierbare Templates** (wie Yeastar Custom-Templates): Start-Vorlagen für Yealink, Grandstream, Fanvil und Gigaset N670/N870 DECT mitgeliefert, frei anpass-/erweiterbar. Platzhalter: `{{mac}} {{extension}} {{display_name}} {{sip_username}} {{sip_password}} {{sip_server}} {{sip_port}} {{label}}`.
- Öffentlicher Provisioning-Endpunkt `GET /api/autoprovision/<mac>.<ext>` liefert dem Gerät seine Config (per MAC, ohne Login). Pro Gerät wird die fertige Provisioning-URL angezeigt (im Gerät oder per DHCP-Option 66 eintragen; Gigaset: `…/[MAC].xml`).
- Backend: Modelle `ProvisioningTemplate` + `ProvisionedDevice`, CRUD, Start-Templates werden geseedet. Sidebar-Eintrag „Provisioning".

## 0.7.28

**Feature**
- Extension-Option **„Nur intern"**: Beschränkt eine Nebenstelle (z.B. Türsprechstelle) auf interne Anrufe — kein Telefonieren nach außen. Solche Endpoints landen im Dialplan-Context `from-internal-restricted` (nur interne Ziele, Ausgang blockiert). Toggle im Add- und Edit-Formular.

## 0.7.27

**Fix — ausgehende Rufnummer-Anzeige (CLIP)**
- Bei ausgehenden Anrufen wurde die eigene Rufnummer nicht angezeigt. Ursache: die CallerID ging als nationale `0…`-Nummer raus; aarenet/DG präsentiert nur E.164. Die CallerID (→ P-Asserted-Identity) wird jetzt automatisch nach E.164 normalisiert (`063483260104` → `+4963483260104`). Der From-URI-User bleibt die registrierte (nationale) Identität, damit die Anrufannahme nicht beeinträchtigt wird.

## 0.7.26

**Fix (kritisch — Gespräch bricht beim Annehmen ab)**
- `direct_media = no` auf Trunk- und Extension-Endpoints gesetzt (+ `rtp_symmetric`/`force_rport`/`rewrite_contact` auf Extensions). PJSIP versucht per Default, RTP direkt zwischen den Endpunkten auszuhandeln — zwischen LAN-Softphone und CGNAT-Trunk (Deutsche Glasfaser) unmöglich → das Gespräch brach beim Abheben sofort ab. Asterisk bleibt jetzt im Medienpfad, RTP läuft über die PBX.

## 0.7.25

**Feature — Routing**
- **Ausgehende Regeln** (neu, editierbar): UI unter Routing wie bei Yeastar — Muster / Entfernen / Voranstellen. Vorbefüllt mit funktionierenden Defaults (`0.`→+49, `00.`→+, `+.`→durch), frei erweiter-/löschbar. Generiert den `[from-internal]`-Dialplan und lädt live neu.
- **Eingehende Routen** greifen jetzt wirklich: `routes` werden in den `[from-trunk]`-Dialplan geschrieben (vorher komplett ignoriert), und `create/update/delete` lösen Regenerierung + Reload aus. DID-Matching ist **format-tolerant** — matcht `+49…`, `0049…`, `49…`, `0…` und national ohne 0, egal wie der Provider die Nummer sendet.
- Bugfix: Inbound dialte `PJSIP/ext11` statt `PJSIP/11` (Endpoint-Name) → eingehende Anrufe erreichten die Nebenstelle nie.
- Backend: neues `OutboundRule`-Modell + `/api/outbound-rules`-CRUD; Defaults werden bei Erststart und beim Boot geseedet.

## 0.7.24

**Fix**
- Dialplan-Context: Extensions liefen im Context `internal`, die Wählregeln (E.164-Normalisierung + Trunk-Routing) lagen aber in `from-internal` → ausgehende Anrufe wurden nie normalisiert/geroutet. Extensions nutzen jetzt `from-internal`.

## 0.7.23

**Fix**
- Dashboard/Extensions: „Extensions Online" zählte den Trunk mit (zeigte 2 bei 1 Nebenstelle). Der Trunk ist ebenfalls ein PJSIP-Endpoint (`trunk-endpoint`) und tauchte nach der Registrierung in der Statusliste auf. Die Statusabfrage filtert jetzt auf numerische Extension-Namen — der Trunk wird nicht mehr mitgezählt.

## 0.7.22

**Fix (kritisch — der eigentliche 404-Grund, per Trace + Provider-Doku belegt)**
- Trunk-REGISTER bekam nach erfolgreicher Auth ein `404 Not Found` (Server: AareSwitch/aarenet, die Plattform hinter Deutsche Glasfaser/outbox). Ursache: Auf dieser Plattform sind **Auth-Username und Registrierungs-Identität (AOR) verschieden**. Wir haben die AOR = Auth-Account registriert; der Registrar erwartet aber die **Rufnummer** als AOR. Template getrennt: `[trunk-auth]` nutzt weiter den Anmeldenamen (SIP-Account), aber `client_uri`/`from_user`/`contact_user` nutzen jetzt die **Rufnummer** (Feld „Rufnummer/CallerID"). Für DG die Rufnummer mit führender 0 eintragen (z.B. `063483260104`, wie im Portal).

## 0.7.21

**Fix (kritisch — der finale SRV-Fix, per Trace belegt)**
- Ein Trace zeigte: das REGISTER ging an den A-Record `185.22.44.186` (401 → REGISTER → 404), NICHT an die SRV-Ziele `sip10/sip20`. unbound war zwar geladen, aber der HA-Supervisor-DNS (`172.30.32.3`) liefert keine SRV-Records (auch `getent` kam leer/Timeout) → unbound bekam nur den A-Record → Registrierung auf dem falschen DG-Server → 404. `res_resolver_unbound.conf` ergänzt: unbound nutzt jetzt öffentliche Resolver (1.1.1.1/8.8.8.8/9.9.9.9), die SRV korrekt liefern → REGISTER geht an sip10/sip20.

## 0.7.20

**Verbesserung**
- Diagnose: Aufnahmezeitpunkt wird jetzt neben "DATEI BEREIT" angezeigt und der PCAP-Download bekommt einen Zeitstempel im Dateinamen (`haphone-capture-JJJJMMTT-HHMMSS.pcap`) — mehrere Traces sind nicht mehr verwechselbar.

## 0.7.19

**Fix**
- Diagnose-Timer: sprang beim Tab-Wechsel zurück auf 0, obwohl die Aufzeichnung weiterlief. Die Zeit wird jetzt aus einem Start-Zeitstempel vom Backend (`started_at` im Status) abgeleitet statt lokal hochgezählt — korrekt über Tab-Wechsel und Seiten-Reload hinweg.

## 0.7.18

**Fix (kritisch — schließt den SRV-Fix ab)**
- `res_resolver_unbound` im `menuselect`-Build aktiviert. 0.7.17 trug das Modul in die Ladeliste ein, aber es war nie kompiliert (`--disable-all` + fehlender `--enable`) → `cannot open shared object file` beim Start, kein SRV, weiter 404. `--with-unbound` liefert nur die Bibliothek; das Modul muss zusätzlich in menuselect aktiviert werden. Jetzt gebaut → SRV-Auflösung aktiv.

## 0.7.17

**Fix (kritisch — der eigentliche SRV-Fix)**
- `res_resolver_unbound.so` zur `modules.conf`-Ladeliste ergänzt. 0.7.16 entfernte zwar den Port aus dem `server_uri`, aber PJSIP macht SRV-Auflösung NUR mit geladenem unbound-Resolver — sonst nutzt es den OS-Resolver (nur A-Records) und landet weiter auf `185.22.44.186` → weiterhin 404. Das Modul war via `--with-unbound` gebaut, aber wegen `autoload = no` nie geladen. Jetzt explizit geladen (vor `res_pjsip.so`) → SRV zu `sip10/sip20.voip.dg-w.de` funktioniert, Registrierung geht durch.

**Fix**
- Diagnose: PCAP-Download gab 404. `window.location.href` umging den fetch-Wrapper, der das HA-Ingress-Präfix setzt → root-absoluter Pfad traf die HA-Wurzel. Präfix wird jetzt manuell vorangestellt.

## 0.7.16

**Fix (kritisch — Trunk-Registrierung, DG/SRV)**
- Trunk-REGISTER schlug mit `404 Fatal` fehl. Ursache per DNS belegt: Deutsche Glasfaser (und viele andere Provider) veröffentlichen SRV-Records — `_sip._udp.dg.voip.dg-w.de` → `sip10/sip20.voip.dg-w.de`. Der eigentliche Registrar-A-Record (`185.22.44.186`) bedient die Registrierung NICHT. Unser Template hängte `:5060` an den `server_uri`, was die SRV-Auflösung abschaltet → Asterisk landete auf dem falschen Server → 404. Ein einfaches SIP-Gerät (DECT) lässt den Port weg → SRV → funktioniert.
  - `server_uri`/`contact` lassen den Port jetzt weg (SRV-Auflösung), außer bei einem echten Custom-Port (≠ 0/5060). Fehlen SRV-Records, fällt PJSIP automatisch auf A-Record + 5060 zurück — universell sicher.
  - `outbound_proxy` und `contact_user` entfernt: erzwangen ebenfalls den A-Record + Route-Header, die ein Standard-Gerät nicht sendet.

## 0.7.15

**Fixes (kritisch — machen den AOR-Fix aus 0.7.14 wirksam)**
- Boot: Alle Asterisk-Configs werden jetzt bei **jedem Start** aus der Datenbank neu generiert (in `cont-init`, bevor Asterisk startet). Vorher wurde eine Config-Datei nur beim Anlegen/Bearbeiten via Web-UI geschrieben — ein Add-on-Update mit korrigiertem Template erreichte bestehende Installationen also NIE (die alte `pjsip_extensions.conf` mit `11-aors` blieb liegen). Deshalb blieb der AOR-Fehler trotz 0.7.14. Jetzt selbstheilend.
- AMI-Reload: `Command`-Action ohne `as_list=True` — mit Liste blockierte panoramisk bis zum Timeout (`AMI reload skipped:` mit leerer Meldung = `asyncio.TimeoutError`). Live-Reload nach UI-Änderungen funktioniert jetzt ohne Neustart.

## 0.7.14

**Fix (kritisch — der echte AOR-Fix)**
- PJSIP-Registrierung: Der Fix aus 0.7.13 (`disable_multi_domain`) war wirkungslos — `res_pjsip_registrar.c` referenziert diese Option gar nicht. Die tatsächliche Ursache: der Registrar sucht die AOR über den **Benutzernamen aus dem REGISTER** (`find_aor_name(username, host, endpoint->aors)`). Unsere AOR hieß `<nummer>-aors` und konnte nie zum User `<nummer>` passen. Template korrigiert: AOR heißt jetzt exakt `<nummer>` und `aors = <nummer>` (kanonisches Asterisk-Muster: Endpoint/Auth/AOR teilen den Namen). `disable_multi_domain` wieder entfernt. Softphones registrieren sich jetzt wirklich.

## 0.7.13

**Fixes (kritisch)**
- PJSIP: Extensions konnten sich nicht registrieren — `AOR '' not found for endpoint 'X'`. Ursache: Asterisk läuft im Multi-Domain-Default und sucht die AOR nach dem REGISTER-Benutzernamen (z.B. `11`), nicht nach der `aors=`-Referenz des Endpoints (`11-aors`). `[global] disable_multi_domain = yes` ergänzt → Registrar nutzt jetzt die `aors=`-Liste direkt. Softphones registrieren sich jetzt.
- Logo: wurde in Sidebar/Login/ChangePassword/Ladeansicht nicht angezeigt. `<img src="/haphone-logo.svg">` ist root-absolut und zeigt unter dem HA-Ingress-Präfix auf die HA-Wurzel statt aufs Add-on (404). Logo als Inline-SVG-Komponente (`Logo.tsx`) — keine Pfadauflösung mehr nötig.

## 0.7.12

**Fixes (kritisch)**
- AMI-Reload: `manager.send_command()` existiert in panoramisk nicht — jeder Reload (PJSIP, Dialplan, Voicemail) warf `AttributeError`, wurde geschluckt und Asterisk lud neue Extensions/Trunk-Änderungen NIE live. Umgestellt auf die korrekte `send_action({"Action":"Command", ...})`-API. Neue Extensions registrieren sich jetzt sofort ohne Add-on-Neustart.
- Dockerfile: `tcpdump` ergänzt — die Diagnose-Seite (Netzwerk-Trace) schlug mit "tcpdump verfügbar?" fehl, weil das Paket im Image fehlte.

## 0.7.11

**Feature**
- Diagnose-Seite: Netzwerk-Trace (PCAP) direkt aus der UI aufzeichnen — Start/Stop, Dauer-Timer, Dateigröße, Download als `.pcap` für Wireshark. Erfasst SIP (Port 5060/5061) + RTP (UDP 10000–20000).
- Backend: `POST /api/trace/start`, `POST /api/trace/stop`, `GET /api/trace/status`, `GET /api/trace/download`, `DELETE /api/trace/file` via tcpdump.

## 0.7.10

**Fix**
- Trunk: Label "SIP Account" → "Anmeldename (SIP-Benutzername laut Anbieter-Portal)" — allgemein für alle Provider.

## 0.7.9

**Fixes**
- Login + ChangePassword: Logo direkt angezeigt (kein Farbquadrat mehr), 80px mit blauem Glow.
- ChangePassword: komplettes Glassmorphism-Redesign, Passwort-Stärke-Anzeige, deutsche Texte.

## 0.7.8

**Fixes & Verbesserungen**
- Login-Seite: Dark OLED + Glassmorphism — passend zum Rest der App, Gradient-Logo, lila Glow-Button.
- Sidebar: Logo wird direkt angezeigt (war hinter Farbquadrat versteckt), blauer Glow passend zur Logo-Farbe.
- PJSIP Trunk: generische Sektionsnamen (`trunk-*` statt `dg-*`), `send_pai = yes` + `send_rpid = yes` für CLIP No Screening (P-Asserted-Identity), `outbound_proxy` automatisch aus Registrar-Host, NAT-Optionen (`rtp_symmetric`, `force_rport`, `rewrite_contact`).
- Dialplan: Ausgehende Anrufe über `trunk-endpoint` statt `dg-trunk`.
- Beschreibung und README: allgemein für alle SIP-Provider (Telekom, Vodafone, Sipgate, outbox/DG, etc.).

## 0.7.7

**Feature**
- UI Redesign: Dark OLED + Glassmorphism — schwarzer Hintergrund mit Ambient-Orbs, Glasskarten, lila Akzent-Gradient, grüne/gelbe Status-Punkte mit Pulsanimation, Inter + JetBrains Mono als Schrift.
- Sidebar: neue Logo-Area mit Gradient-Badge, aktive Nav-Items mit lila Glow-Border und Hintergrund-Highlight.
- Dashboard: glassmorphism StatCards mit Farb-Icons, pulsierender Statusanzeige für Trunk, Update-Banner neu gestaltet.
- Trunk: glass Card-Layout, kompaktere Actions-Zeile mit Icons, monospace Felder für SIP-Daten.
- Extensions: glass Table-Design, Online-Dots mit Pulsanimation, lila Extension-Nummern, verbesserter Empty-State.
- CSS: Scrollbar-Styling, Glassmorphism-Utility `.glass`, Glow-Utilities `.glow-green/.glow-yellow/.glow-red`, `.dot-pulse`-Animation, Input-Focus-Glow mit lila Ring.

## 0.7.6

**Fix (kritisch)**
- modules.conf: `res_pjsip_outbound_authenticator_digest.so` zur Load-Liste ergänzt. Das Modul war im Dockerfile kompiliert, aber `autoload = no` verhinderte das Laden — daher "No SIP outbound authenticator registered" bei jeder 401-Challenge von DG.

## 0.7.5

**Fix**
- Trunk-Seite: Port-Feld wurde nach jedem Reload auf 5060 zurückgesetzt, auch wenn 0 gespeichert war — `||`-Fallback durch `??` ersetzt (0 ist in JS falsy, `0 || 5060` ergibt 5060).

## 0.7.4

**Feature**
- Dashboard: Update-Banner wenn neue Version verfügbar — zeigt aktuelle und neue Version, "Jetzt aktualisieren"-Button ruft die HA Supervisor API auf (`POST /addons/self/update`) und startet das Update direkt aus der UI.
- Backend: `GET /api/update/info` und `POST /api/update/start` via HA Supervisor API (`SUPERVISOR_TOKEN`).

## 0.7.3

**Fix**
- Dockerfile: `res_pjsip_outbound_authenticator_digest` zum Asterisk-Build ergänzt — ohne dieses Modul kann Asterisk auf 401-Challenges von DG nicht mit Credentials antworten, weshalb die SIP-Registrierung immer fehlschlug.

## 0.7.2

**Fixes**
- pjsip_trunk.conf.j2: Sektion `[dg-transport]` → `[dg-registration]` (war falscher Name für type=registration).
- pjsip_trunk.conf.j2: `contact_user` ergänzt (setzt User-Teil im Contact-Header bei REGISTER).
- pjsip_trunk.conf.j2: `auth_rejection_permanent = no` ergänzt (Asterisk wiederholt nach 401/403 statt dauerhaft zu stoppen).
- pjsip_trunk.conf.j2: `from_user` nutzt jetzt `auth_username` statt `phone_number` (DG erwartet SIP-Account-Nummer).
- pjsip_trunk.conf.j2: `from_domain` ergänzt (korrekter From-Header Richtung DG).
- pjsip_trunk.conf.j2: AOR contact-URI enthält jetzt vollständige SIP-URI (`sip:user@host`).
- GET /api/trunk/debug: Neuer Endpunkt gibt alle OutboundRegistrationDetail-Felder zurück (Diagnose bei REJECTED).

## 0.4.1

**Fixes**
- AMI connection management: singleton Manager statt per-Request connect/close — behebt Ping-Flood in den Logs und stellt sicher dass `module reload res_pjsip.so` nach Trunk-Speicherung zuverlässig durchläuft.
- Trunk-Formular: Port-Default war 0 (Zod `min(1)` blockierte das Speichern) → jetzt 5060.
- Trunk-Seite: Hinweis unter "Test Connection" erklärt dass erst gespeichert werden muss.

## 0.2.0

First deployable build — Phases 1–6 plus the live-deploy hardening pass.

**Features**
- SEC-03: SIP passwords auto-generated (16-char) on extension create; readable in the form + a "Generate" button.
- SEC-04: web-admin authentication — login, mandatory first-login password change, logout, session cookies; all API routes protected.
- IPv6 PJSIP transport for cellular softphones (Deutsche Glasfaser CGNAT); iOS/cellular documentation.

**Fixes (first live HA deploy)**
- Build context: backend/ and frontend/ moved into the add-on directory so the Docker build resolves them.
- AdminUser seeding runs with `PYTHONPATH=/app` in cont-init.d.
- SPA shell serves the built `dist/index.html` (correct hashed asset names); assets resolve under the HA ingress prefix (fixes blank UI via the ingress sidebar).
- All `/api` calls carry the ingress prefix.
- AMI manager.conf ACL order fixed (localhost was being denied); panoramisk `send_action` uses `as_list=True`.
- AuthGuard shows a visible loading/error state instead of a silent blank screen; top-level error boundary surfaces render errors.
- Extensions page wrapped in `TooltipProvider` (was crashing once a row rendered).
- First-boot placeholder conf files so Asterisk parses `pjsip.conf`/`extensions.conf` cleanly before any extension/trunk/route exists.

**Known limitations**
- Cellular (4G/5G) registration and PSTN audio: hardware verification pending.
- iOS background incoming calls require the app in the foreground (PushKit deferred to a future version).

## 0.1.0

Initial foundation — Asterisk 22.x container, HA add-on scaffold, `/data` persistence, AMI/ARI bound to localhost.
