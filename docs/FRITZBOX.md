# Fritz!Box SIP ALG — Setup Guide

## Problem: Fritz!Box SIP ALG

Fritz!Box routers intercept SIP traffic on UDP port 5060 and rewrite SDP headers
(the `c=` connection line and `o=` origin line) with their own external IP address.
This conflicts with Asterisk's own NAT handling and typically causes:

- Registration succeeds but inbound calls have no audio
- Outbound calls connect but one or both sides cannot hear audio
- sngrep traces show Contact/Via headers different from what Asterisk sent

**Fritz!Box does not allow disabling SIP ALG on most models.**
The recommended solution for hassio-bpx is to use **Exposed Host** (Exposed Host / DMZ)
mode, which causes Fritz!Box to forward all inbound connections to the Asterisk host
without SIP ALG intervention.

---

## Solution: Fritz!Box Exposed Host (DMZ) Mode

### Step 1 — Identify your Asterisk host IP

Find the LAN IP address of the Home Assistant host running hassio-bpx.
Example: `192.168.178.50`

### Step 2 — Open Fritz!Box admin panel

Open your browser and go to: `http://192.168.178.1` (default Fritz!Box address)

### Step 3 — Navigate to Exposed Host

1. Go to **Internet → Permit Access** (or **Internet → Freigaben** in German)
2. Click the tab **Exposed Host** (or **Exposed Host / DMZ**)
3. Enable the option: "Forward all inbound connections to this host"
4. Enter the IP address of your Asterisk host (e.g. `192.168.178.50`)
5. Click **Apply** (OK / Übernehmen)

### Step 4 — Restart hassio-bpx add-on

After enabling Exposed Host, restart the hassio-bpx add-on from the Home Assistant UI.
The Asterisk container will re-detect its external IP on startup.

### Step 5 — Verify with pjsip show registrations

Inside the container, run:
```
asterisk -rx "pjsip show registrations"
```
Expected output:
```
dg-registration   sip:sip.dg-w.de   Registered   59
```

---

## Diagnostic: sngrep SIP Packet Capture

`sngrep` is included in the hassio-bpx container image for SIP packet debugging.

To run sngrep from inside the container:

```bash
docker exec -it hassio-bpx-test sngrep
```

Or from the HA add-on terminal (if available):
```bash
sngrep
```

**What to look for:**
- If Fritz!Box SIP ALG is active: the `Contact:` header in the REGISTER request on
  the wire will contain Fritz!Box's external IP, not Asterisk's `external_signaling_address`
- If externip is working correctly: the `Contact:` header matches the IP in
  `/data/asterisk/pjsip_local.conf`

**sngrep key bindings:**
- `F2` — SIP dialog detail
- `F3` — View raw SIP message
- `q` — Quit

---

## DG Registrar Hostname Note

The project documentation uses `sip.dg-w.de` as the Deutsche Glasfaser SIP registrar.
Multiple community sources (FreePBX forum, Glasfaserforum, Auerswald FAQ) report
`dg.voip.dg-w.de` as the working hostname.

**If registration fails with `Status: Rejected` or `Status: Failed`:**

Edit `/data/asterisk/pjsip_trunk.conf` and replace `sip.dg-w.de` with `dg.voip.dg-w.de`
in these fields:
- `server_uri = sip:dg.voip.dg-w.de`
- `client_uri = sip:<PHONE_NUMBER>@dg.voip.dg-w.de`
- `contact = sip:dg.voip.dg-w.de` (in [dg-aor])
- `from_domain = dg.voip.dg-w.de` (in [dg-trunk])
- `match = dg.voip.dg-w.de` (in [dg-identify])

Then reload:
```bash
asterisk -rx "module reload res_pjsip"
```

---

## Bridge Mode (Advanced — not required for most users)

If your Fritz!Box is your primary internet router and Exposed Host mode is not acceptable,
an alternative is to put Fritz!Box in **bridge mode** (IP-Passthrough / Expose) and handle
NAT on a separate router/firewall with SIP ALG disabled.

This is a significant network reconfiguration and is outside the scope of this document.
Consult your Fritz!Box manual and internet provider documentation before attempting this.
