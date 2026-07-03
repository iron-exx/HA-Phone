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

## Remote access (audio + video on the go)

If you want to answer normal PBX calls or a **video door intercom call** while you are away from home, do **not** expose SIP directly to the internet unless you really know what you are doing.

The recommended setup is:

- **HA-Phone** inside Home Assistant
- **Tailscale** (or WireGuard) for secure remote access
- **Linphone** as the SIP softphone on your mobile device

HA-Phone treats VPN peers as local, so SIP audio and video can flow through the tunnel without opening PBX ports to the public internet.

### What you need

- A working HA-Phone installation
- At least one configured extension, for example `11`
- The SIP password of that extension
- A Home Assistant host or another always-on machine joined to your Tailscale network
- A smartphone with:
  - the **Tailscale** app
  - the **Linphone** app

### Recommended topology

```
Door intercom -> HA-Phone -> mobile extension
                       -> over Tailscale VPN -> Linphone on Android/iPhone
```

For video door calls, the most reliable setup is:

- the door station calls a normal HA-Phone extension or route
- your mobile extension is marked as **video-capable**
- Linphone registers over the Tailscale connection
- once you answer on the phone, the SIP video stream is sent through the VPN tunnel

## Tailscale setup in Home Assistant

1. Install and start the **Tailscale** add-on in Home Assistant.
2. Join it to your tailnet.
3. Note the **Tailscale IP address** of the Home Assistant / HA-Phone host.
4. Confirm that the HA-Phone web UI is reachable from another Tailscale device.

Practical tip:

- Use the **Tailscale IP** as the SIP server in Linphone.
- Do not use Cloudflare tunnels, reverse proxies, or the Home Assistant ingress URL for SIP registration.

## HA-Phone extension setup

Create or edit the extension you want to use remotely:

1. Open **Extensions**.
2. Create a dedicated mobile extension such as `11 Sandro Mobile`.
3. Keep the generated SIP password or set your own strong password.
4. Enable video support for the extension if the device should receive door video.

Recommended:

- Use a **separate extension for mobile use** instead of reusing a desk phone extension.
- That makes troubleshooting, routing and video handling much cleaner.

## Android setup

### 1. Install the apps

Install on your Android phone:

- **Tailscale** from Google Play
- **Linphone** from Google Play

### 2. Connect the phone to Tailscale

1. Open Tailscale.
2. Sign in to the same tailnet as your HA-Phone system.
3. Accept Android's VPN permission request.
4. Make sure the device shows as connected.

Before continuing, verify:

- your phone has a Tailscale IP
- the HA-Phone host is reachable over Tailscale

### 3. Add your SIP account in Linphone

In Linphone, create a SIP account with:

- **Username**: your extension number, for example `11`
- **Password**: the SIP password from HA-Phone
- **Domain / Server / SIP server**: the **Tailscale IP of the HA-Phone host**
- **Transport**: start with `UDP`, switch to `TCP` if your network behaves badly

If Linphone asks for extra fields:

- **Display name**: anything you like
- **Outbound proxy**: usually leave empty at first
- **Port**: `5060` unless you changed it

### 4. Android permissions

Allow these permissions if you want door video to work well:

- microphone
- camera
- notifications
- battery/background activity exceptions if your phone aggressively sleeps apps

Important:

- many Android vendors kill SIP apps in the background
- if Linphone stops registering after some time, disable battery optimization for Linphone and Tailscale

### 5. Test calls

Test in this order:

1. internal audio call from another extension to the mobile extension
2. inbound trunk call to the mobile extension
3. door intercom audio call
4. door intercom video call

If audio works but video does not:

- check that the extension is video-capable in HA-Phone
- check that the door intercom uses a codec your client supports, typically `H.264`
- check that Linphone has camera permission

## iPhone / iOS setup

### 1. Install the apps

Install on your iPhone:

- **Tailscale** from the App Store
- **Linphone** from the App Store

### 2. Connect the iPhone to Tailscale

1. Open Tailscale.
2. Sign in to the same tailnet.
3. Accept the iOS request to install the VPN profile.
4. Confirm that Tailscale is connected.

### 3. Add your SIP account in Linphone

Use the same values as on Android:

- **Username**: extension number, for example `11`
- **Password**: SIP password from HA-Phone
- **SIP server / Domain**: the **Tailscale IP of the HA-Phone host**
- **Port**: `5060`

### 4. iPhone permissions

Allow:

- microphone
- camera
- notifications

On iPhone, background SIP behavior is more restrictive than on desktop systems. If the app does not stay reliably reachable:

- keep Tailscale connected
- allow notifications
- avoid low power mode while testing

### 5. Test calls

Use the same order as on Android:

1. internal audio
2. inbound trunk
3. door intercom audio
4. door intercom video

## Door intercom video notes

For a SIP door station with video, these points matter most:

- the extension that receives the call must be **video-capable**
- the mobile client must support the intercom's video codec, usually `H.264`
- the phone must be registered over the VPN at the moment the call arrives

Recommended first setup:

- use **one dedicated mobile extension** for video door calls
- make that extension the primary destination for the intercom route
- after that works, expand to ring groups or more advanced routing

Why this recommendation:

- normal audio ring groups are simple
- SIP video to multiple simultaneous endpoints is often less predictable
- one reliable mobile video target is much easier to support than video fanout

## Troubleshooting

### Linphone does not register

Check:

- Tailscale is connected on the phone
- the SIP server in Linphone is the **Tailscale IP**, not the Home Assistant URL
- extension number and password are correct
- the extension is enabled in HA-Phone

### Audio works but video does not

Check:

- the extension is configured as video-capable
- the intercom actually sends video
- the codec is compatible, typically `H.264`
- camera permissions are granted

### Calls only work on Wi-Fi but not on mobile data

Check:

- Tailscale is still connected on mobile data
- the phone is not blocking Linphone or Tailscale in background mode
- no battery saver is stopping the apps

### Incoming calls stop after some time

This is usually a mobile background issue, not a PBX issue.

Check:

- Tailscale still shows connected
- Linphone is allowed to run in background
- battery optimization is disabled for Linphone and Tailscale on Android

## Recommended apps and references

- Tailscale iOS install guide: [tailscale.com/docs/install/ios](https://tailscale.com/docs/install/ios)
- Tailscale Android install guide: [tailscale.com/docs/install/android](https://tailscale.com/docs/install/android)
- Linphone softphone: [linphone.org/en/linphone-softphone](https://www.linphone.org/en/linphone-softphone/)

## Provider notes — Deutsche Glasfaser / outbox

DG resells the outbox / aarenet platform. Two things differ from a "typical" trunk and are handled automatically by HA-Phone:

- **Login name ≠ phone number.** Authentication uses the **SIP account** from the provider letter; the registration/AOR identity is the **phone number** (with leading 0, e.g. `063483260104`). Enter the SIP account under *Login name* and the number under *Phone number*.
- **SRV / DNS.** The registrar `dg.voip.dg-w.de` uses SRV records — HA-Phone resolves them correctly (no manual proxy needed).

## Documentation

The README contains the main installation and remote-use guide. Additional project-specific documentation can be added under `docs/` over time.

## Support

Issues and questions: [github.com/iron-exx/HA-Phone/issues](https://github.com/iron-exx/HA-Phone/issues)

## License

HA-Phone's own code (backend, frontend, add-on config, templates) is released under the [MIT License](LICENSE).

The container image bundles **Asterisk** (GPLv2, © Sangoma Technologies), built from the official source at downloads.asterisk.org. Asterisk runs as a separate process — HA-Phone talks to it only via AMI and generated config files (mere aggregation). Other bundled components (FastAPI, React, …) keep their own licenses. See [LICENSE](LICENSE) for details.
