# Changelog

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
