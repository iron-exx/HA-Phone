# ha-phone Documentation

Asterisk 22.x PBX as Home Assistant add-on.

## Requirements

- Home Assistant Supervised installation
- Deutsche Glasfaser SIP trunk credentials (optional in Phase 1)
- IP phone or softphone (Linphone, Grandstream Wave)

## Installation

1. Add this repository to your HA add-on store:
   `https://github.com/iron-exx/HA-Phone`
2. Install the **ha-phone** add-on.
3. Start the add-on.
4. Open the web UI via the sidebar link.

## Phase 1 Status

Phase 1 delivers the container infrastructure only. The web admin UI is available from Phase 3.

The ingress link in the HA sidebar returns a placeholder page confirming Asterisk is running.

## Configuration

No user configuration is required for Phase 1. All defaults are suitable for initial startup.

## Network

This add-on uses `host_network: true` because Home Assistant's add-on system does not support
UDP port ranges required for RTP audio. All LAN ports used:

| Port | Protocol | Purpose |
|------|----------|---------|
| 5060 | UDP | SIP signalling |
| 8099 | TCP | Web admin UI (via HA ingress) |
| 10000-10200 | UDP | RTP audio streams |

AMI (5038) and ARI (8088) are bound to 127.0.0.1 and are NOT accessible from the LAN.

## Support

Issues: https://github.com/iron-exx/HA-Phone/issues

## iOS Softphone Support

iOS softphones (Linphone, Acrobits, Zoiper) can register and make calls when the
app is in the **foreground**. Incoming calls are NOT reliably received when the app
is backgrounded.

**Why:** iOS suspends background apps after a short grace period (~5–10 seconds for
network tasks). SIP registration requires periodic re-registration (every 60–3600
seconds) which cannot happen while the app is suspended.

**Workaround (v1):** Keep the softphone app open and in the foreground to receive
incoming calls. Use the HA companion app for other household alerts.

**Long-term solution (planned v2):** Apple PushKit (VoIP Push Notifications) allows
incoming call notifications to wake the app. This requires an Apple Developer account
and server-side APNs integration — deferred to a future version of this add-on.

**Outgoing calls** work normally (user taps dial → app activates → call connects).

## Cellular Softphone Support

Cellular softphones (4G/5G, Wi-Fi off) connect via IPv6. IPv4 STUN/TURN is not
available because Deutsche Glasfaser uses CGNAT (100.64.x.x) for IPv4 — port
forwarding is impossible under CGNAT (D-01).

**Requirement:** The HA host must have a stable global IPv6 address. The add-on
auto-detects the IPv6 address at startup and writes it to `pjsip_local.conf`. If
detection fails, the add-on operates in LAN-only mode (restart the add-on after
the IPv6 address becomes available).

**Tested configuration:** Linphone on Android (4G/5G, Wi-Fi disabled) registered
to extension credentials over IPv6. Two-way audio confirmed on PSTN call.
