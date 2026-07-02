# Changelog

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
