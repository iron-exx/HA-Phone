# HA-Phone Documentation

## Requirements

- Home Assistant Supervised or Home Assistant OS
- A SIP trunk from any provider (Telekom, Vodafone, 1&1, Sipgate, Deutsche Glasfaser, etc.)
- At least one SIP device: IP phone, softphone, or SIP doorbell

---

## Installation

1. **Add repository** — HA → Settings → Add-ons → Add-on Store → ⋮ → Repositories:
   ```
   https://github.com/iron-exx/HA-Phone
   ```
2. **Install** HA-Phone and click **Start**.
3. **Open the UI** via the HA sidebar — first login uses the password set in the add-on configuration (default: `changeme`). You will be prompted to change it immediately.

---

## Network

This add-on uses `host_network: true` because the HA add-on network does not support
the UDP port ranges required for RTP audio.

| Port | Protocol | Purpose |
|------|----------|---------|
| 5060 | UDP/TCP | SIP signalling |
| 80 | TCP | Web UI / provisioning (HA ingress + direct LAN access) |
| 10000–10200 | UDP | RTP audio |

AMI (5038) and ARI (8088) are bound to `127.0.0.1` and are not reachable from the LAN.

---

## SIP Trunk Setup

1. Open the HA-Phone UI → **Trunk**.
2. Enter the details from your SIP provider:

| Field | Description |
|-------|-------------|
| Registrar Host | SIP server of your provider (e.g. `sip.sipgate.de`) |
| Port | Usually `5060`, or `0` to let the provider decide |
| Transport | `UDP` for most providers, `TLS` for encrypted connections |
| SIP Account | Your SIP username / account number |
| Password | SIP password from your provider portal |
| Phone Number | Your full phone number in international format (e.g. `+4930123456`) |
| Registration Refresh | How often to re-register in seconds (60–3600, default 60) |

3. Click **Save** — Asterisk applies the config without a restart.
4. Click **Test Connection** to verify registration status.

> **Note:** If your provider rejects registration, check that NAT / SIP ALG is disabled on your router. Many consumer routers interfere with SIP traffic.

---

## Extensions

Each SIP device (phone, softphone, doorbell) needs an **extension**:

1. UI → **Extensions** → **Add Extension**.
2. Choose a number (10–99) and a display name.
3. A secure SIP password is auto-generated — copy it to your device.
4. Configure your SIP device:
   - **Server / Registrar:** IP address of your Home Assistant host
   - **Port:** 5060
   - **Username / Auth:** the extension number (e.g. `10`)
   - **Password:** the generated SIP password

---

## Softphone Support

**Android** — Linphone, Zoiper, Grandstream Wave — full support, including background operation.

**iOS** — Linphone, Acrobits, Zoiper — outgoing calls and foreground incoming calls work.
Background incoming calls require Apple PushKit (planned for a future version).

---

## Cellular / Remote Access

Mobile softphones on 4G/5G connect via **IPv6** if your ISP uses CGNAT for IPv4
(common with cable and fibre providers). The add-on auto-detects the host's global
IPv6 address at startup. No extra configuration is needed if your HA host has a
stable IPv6 address.

If your ISP provides a public IPv4 address, configure it under **Settings → Public IP**
in the UI to enable STUN-based NAT traversal for remote SIP devices.

---

## Support

[github.com/iron-exx/HA-Phone/issues](https://github.com/iron-exx/HA-Phone/issues)
