# HA-Phone Documentation

## Requirements

- Home Assistant OS or Home Assistant Supervised
- A SIP trunk from any provider (Telekom, Vodafone, 1&1, Sipgate, Deutsche Glasfaser, etc.)
- At least one SIP device: the HA-Phone App, an IP phone, a DECT base, a softphone or a SIP door station

---

## Installation

1. **Add repository** — HA → Settings → Add-ons → Add-on Store → ⋮ → Repositories:
   ```
   https://github.com/iron-exx/HA-Phone
   ```
2. **Install** HA-Phone and click **Start**.
3. **Open the UI** via the HA sidebar — the first login uses the password from the add-on configuration (default: `changeme`). You are asked to change it immediately.

The web UI is in German.

---

## Network

This add-on uses `host_network: true` because the HA add-on network does not support
the UDP port ranges required for RTP.

| Port | Protocol | Purpose |
|------|----------|---------|
| 5060 | UDP/TCP | SIP |
| 5061 | TLS | SIP over TLS (HA-Phone App, TLS phones) |
| 5063 | TLS | SIP over TLS on the Tailscale interface (only when Tailscale runs on the host) |
| 80 | TCP | Web UI (HA ingress + direct LAN access) and provisioning |
| 8443 | HTTPS | API for the HA-Phone App |
| 3478 | UDP | STUN for the HA-Phone App |
| 389 | TCP | LDAP phonebook for desk phones |
| 10000–10200 | UDP | RTP audio and video |

AMI and ARI are bound to `127.0.0.1` and are not reachable from the LAN.

---

## SIP Trunk Setup (*Telefonanbieter*)

1. Open the HA-Phone UI → **Anschluss → Telefonanbieter**.
2. Enter the details from your SIP provider:

| Field | Description |
|-------|-------------|
| Server des Anbieters (Registrar) | SIP server of your provider (e.g. `sip.sipgate.de`) |
| Port | Usually `5060`, or `0` to let the provider decide |
| Übertragung (Transport) | `UDP` for most providers, `TLS` for encrypted connections |
| Anmeldename | Your SIP username / account number |
| Passwort | SIP password from your provider portal |
| Rufnummer (CallerID) | Your phone number (e.g. `+4930123456`) |
| Anmeldung erneuern alle (Sekunden) | How often to re-register in seconds (60–3600, default 60) |

3. Click **Speichern** — Asterisk applies the config without a restart.
4. Click **Verbindung testen** to verify the registration.

> **Note:** If your provider rejects the registration, check that SIP ALG is disabled on your router. Many consumer routers interfere with SIP traffic.

---

## Extensions (*Nebenstellen*)

Each device needs an **extension**. One extension can serve several devices (e.g. a desk phone and the app).

1. UI → **Nebenstellen** → **Nebenstelle hinzufügen**.
2. Choose a number (10–99) and a display name. A secure SIP password is generated.
3. Connect the device:
   - **HA-Phone App:** **⋯ → HA-Phone App QR** at the extension and scan the code with the app.
   - **Desk phone / DECT:** **Telefone & Personen → Tischtelefone** → add the device by MAC address, or enter the values by hand.
   - **By hand:** server = IP of the Home Assistant host, port 5060, user = extension number, password = the SIP password.

Useful options in the extension editor (**⋯ → Bearbeiten**):

| Option | Effect |
|--------|--------|
| *Video-fähig* | Video calls (H.264), needed for door video |
| *Nur intern* | No outgoing calls to the trunk (e.g. door stations) |
| *Gehört zu (Home-Assistant-Person)* | Door calls skip this phone while its person is away and someone else is at home |
| *Rückfall auf Handynummer* | If no device of the extension is reachable, HA-Phone calls this number over the trunk |
| *Gesprächsaufzeichnung erlauben* | The app may record calls of this extension (off by default; recording needs the consent of everyone on the call) |

---

## Door stations (*Türstationen & Verlauf*)

Open **Türklingel → Türstationen & Verlauf**. Pick the door station's extension under *Weitere Nebenstelle als Türstation einrichten* and click **Einrichten**; later, **Einstellungen** at the door station reopens the same dialog. Switch on **Türstation** there, then the door fields appear below the switch:

- **Tür-Öffnen-Webhook** — called (POST with JSON) when someone slides "Zum Öffnen schieben" in the app, even while it is still ringing. Usually a Home Assistant automation with a webhook trigger. The app never sees the URL.
- **Tür-Öffnen-Code (DTMF)** — for door stations that open with a key code during a call.
- **Klingelbild-Quelle** — a Home Assistant camera (`camera.…`) or the door station's snapshot URL (credentials as `http://user:password@…`). HA-Phone stores a picture of every ring for 30 days; see **Türklingel → Türstationen & Verlauf** in the sidebar. *Testbild holen* checks the source.
- **Home-Assistant-Aktionen** — buttons in the app while the door rings or during the call, e.g. switching on a light.

**Türklingel → Kameras für die App**: choose which Home Assistant cameras (`camera.…`) the paired phones may show as extra previews and give them a name. Nothing is shared by default. Each phone chooses from this list under *Ich → Weitere Kameras*. While a door rings, HA-Phone fetches the shared cameras continuously, so the ringing phones get the newest picture without waiting. Cameras that build every picture from an RTSP stream can take 10–25 s per picture in Home Assistant; cameras with a still-image URL are much faster.

For the camera preview before answering, switch on *Video-fähig* for the door station and for the phones. Put the phones into a ring group and let the door station call it.

---

## HA-Phone App and remote access

The HA-Phone App for Android pairs by QR code, keeps a TLS registration, rings over the lock screen and shows the door video before you answer. See [iron-exx/ha-phone-app](https://github.com/iron-exx/ha-phone-app).

For use on mobile data, install the **Tailscale** add-on on the Home Assistant host and join it to your tailnet (keep *userspace networking* off). The page **Anschluss → Fernzugriff** in HA-Phone checks the setup. After that, pairing also gives the phone tailnet access: either the user signs in once on the phone, or HA-Phone creates a one-time key via an OAuth client (*Vollautomatisch*). No ports need to be opened to the internet.

Other SIP softphones (Linphone, Zoiper, …) work too: connect the phone to your tailnet or another VPN and use the Tailscale IP of the Home Assistant host as the SIP server.

---

## Support

[github.com/iron-exx/HA-Phone/issues](https://github.com/iron-exx/HA-Phone/issues)
