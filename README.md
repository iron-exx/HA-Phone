<div align="center">

<img width="180" alt="HA-Phone logo" src="https://github.com/user-attachments/assets/eccec6b3-ec21-4e7a-8307-a48dbea1b438" />

# HA-Phone

**Full-featured SIP PBX for Home Assistant** — powered by Asterisk 22.x LTS, managed entirely through a modern web UI. No command line, no config files, no SSH.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Asterisk](https://img.shields.io/badge/Asterisk-22.x%20LTS-red.svg)
![Arch](https://img.shields.io/badge/arch-amd64%20%7C%20aarch64-lightgrey.svg)

</div>

---

HA-Phone turns your Home Assistant into a complete telephone system: connect a SIP trunk from your provider, register desk phones, softphones and DECT bases, and route calls — all from a clean dark-mode dashboard.

<img width="900" alt="HA-Phone dashboard" src="https://github.com/user-attachments/assets/3801f7fc-cb4c-49d4-bd36-1c823fedb6c3" />

## Features

- **📞 Any SIP trunk** — works with all standard providers (Telekom, Vodafone, 1&1, Sipgate, Deutsche Glasfaser / outbox, and many more). Registration, CLIP (outbound caller ID), and a selectable codec list.
- **☎️ Extensions** — internal SIP accounts with auto-generated passwords. Optional **internal-only** mode (e.g. door intercoms that must not dial out).
- **🔀 Call routing** — editable **outbound dial rules** (pattern / strip / prepend, like the big vendors), **inbound routes** (DID → extension or ring group, format-tolerant matching), **ring groups** (ring several phones at once) and time conditions.
- **📟 Auto-provisioning** — configure IP phones, DECT bases and door stations by MAC address, like 3CX/Yeastar. Ships with **editable templates** for Yealink, Grandstream, Fanvil and Gigaset — customize freely.
- **📬 Voicemail** — per-extension mailboxes with **voicemail-to-email** via your own SMTP server (with a built-in test button).
- **📊 Live dashboard** — active calls chart, registration gauges, trunk status — updated in real time.
- **🩺 Diagnostics** — one-click network trace (PCAP) you can download and open in Wireshark.
- **🌐 Remote use** — reach your extensions on the go with a softphone (e.g. Linphone) over a VPN such as Tailscale/WireGuard.
- **⬆️ In-app updates** — update directly from the UI via the Home Assistant Supervisor.

## Installation

1. In Home Assistant: **Settings → Add-ons → Add-on Store → ⋮ → Repositories**, add:
   ```
   https://github.com/iron-exx/HA-Phone
   ```
2. Install **HA-Phone** and start it.
3. Open the UI from the sidebar. Default password: `changeme` (you'll be asked to change it on first login).

## First steps

1. **Trunk** — enter your provider's SIP credentials (login name, password, phone number). See the notes below for Deutsche Glasfaser / outbox.
2. **Extensions** — add an extension; the SIP password is auto-generated.
3. **Softphone / desk phone** — register your device against the PBX (server = the HA host IP, user = extension number, password = the extension's SIP password), or use **Auto-Provisioning**.
4. **Routing** — outbound rules come pre-filled with sensible defaults; add an inbound route (your number → an extension or ring group).

## Remote access (softphone on the go)

SIP does **not** pass through an HTTP tunnel (e.g. Cloudflare) and, on CGNAT connections like Deutsche Glasfaser, port-forwarding isn't possible. The reliable way:

1. Install the **Tailscale** (or WireGuard) add-on in Home Assistant.
2. Install the Tailscale app + **Linphone** on your phone.
3. In Linphone, set the SIP server to the **Tailscale IP of the PBX** (user = extension, password = SIP password).

HA-Phone treats VPN peers as local, so audio flows cleanly over the tunnel — inbound and outbound, encrypted, with nothing exposed to the internet.

## Provider notes — Deutsche Glasfaser / outbox

DG resells the outbox / aarenet platform. Two things differ from a "typical" trunk and are handled automatically by HA-Phone:

- **Login name ≠ phone number.** Authentication uses the **SIP account** from the provider letter; the registration/AOR identity is the **phone number** (with leading 0, e.g. `063483260104`). Enter the SIP account under *Login name* and the number under *Phone number*.
- **SRV / DNS.** The registrar `dg.voip.dg-w.de` uses SRV records — HA-Phone resolves them correctly (no manual proxy needed).

## Documentation

See [DOCS.md](DOCS.md) for network setup, SIP trunk configuration and softphone guides.

## Support

Issues and questions: [github.com/iron-exx/HA-Phone/issues](https://github.com/iron-exx/HA-Phone/issues)

## License

HA-Phone's own code (backend, frontend, add-on config, templates) is released under the [MIT License](LICENSE).

The container image bundles **Asterisk** (GPLv2, © Sangoma Technologies), built from the official source at downloads.asterisk.org. Asterisk runs as a separate process — HA-Phone talks to it only via AMI and generated config files (mere aggregation). Other bundled components (FastAPI, React, …) keep their own licenses. See [LICENSE](LICENSE) for details.
