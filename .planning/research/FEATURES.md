# Feature Research

**Domain:** Wallbox RFID Billing System (EV Charging + ERP Integration)
**Researched:** 2026-05-04
**Confidence:** MEDIUM (based on multiple vendor docs, industry sources, and competitor analysis; some extrapolation from adjacent domains)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **RFID authentication (tap-to-charge)** | Industry standard across Wallbox, Alfen, Zaptec, Elinta — all major vendors ship RFID readers as primary auth method. Users expect to tap and charge. | LOW | Alfen Eve supports ISO 14443A/B MIFARE cards. Home Assistant reads `sensor.alfen_eve_tag_socket_1`. |
| **kWh-based billing with MID-compliant meter** | EU Eichrecht (de) and AFIR (EU-wide) require calibrated metering for energy resale. Alfen Eve has integrated MID meter. Billing by kWh is fairest model per BCG/Plugmatic/Tridens research. | LOW | Alfen Eve has MID meter built-in. `sensor.alfen_energy_total` provides kWh data. |
| **Session tracking (start/end time, kWh, RFID ID)** | Every EV charging billing system (Wallbox Pay per Charge, 1C CMS, GDON, Flipturn) records Charge Detail Records (CDRs) with timestamps, energy, and user identity. Required for any billing. | MEDIUM | SQLite persistence as per PROJECT.md. Must survive HA restarts. |
| **RFID whitelist management** | Alfen Eve supports 800-1200 tokens in local list. Wallbox/OCPP standard. Required to control who can charge. | LOW | YAML-based whitelist per PROJECT.md decision. |
| **Session persistence across HA restarts** | Reliability is #1 user expectation (BCG 2023, JD Power). Sessions lost on restart → billing disputes. | MEDIUM | SQLite in HA Addon as specified in PROJECT.md. |
| **User management (RFID → user mapping, per-user kWh price)** | All billing systems (Wallbox Pay per Month, Dolibarr subscriptions) link charging identity to user account with individual pricing. | MEDIUM | Dolibarr module extends users with RFID-ID and price fields. |
| **Monthly billing + PDF invoice generation** | Wallbox Pay per Month, Dolibarr recurring invoices, all CPO billing platforms generate monthly invoices. Core value of this project. | MEDIUM | Dolibarr Cronjob on last day of month per PROJECT.md. |
| **REST API transmission (HA → Dolibarr) with retry** | OCPP backends (Wallbox, PandaExo) sync session data to billing systems. Reliability requires retry logic. | MEDIUM | API-Token auth per PROJECT.md. |
| **Data privacy (RFID not in cleartext, no logging)** | GDPR/EU privacy requirements. RFID is personal identifier. | LOW | Hash storage as per PROJECT.md. |
| **RFID debouncing (multiple tap protection)** | Physical RFID readers can fire multiple events. Clean session data requires debouncing. | LOW | Explicit requirement in PROJECT.md. |
| **Multi-wallbox scalability** | Alfen Eve supports networks of 100+ chargers. Future-proofing is expected for business users. | HIGH | Explicit requirement in PROJECT.md. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **CSV / DATEV export** | German accounting integration (DATEV is standard). Dolibarr supports export module. Competes with manual bookkeeping. | LOW | Explicit in PROJECT.md as differentiator. |
| **Transparent session history per user** | Users can see their charging history. Competitive with Wallbox app features but delivered via Dolibarr web UI. | MEDIUM | Dolibarr has user portals and detailed CDR viewing. |
| **Configurable billing periods (not just monthly)** | Some users want bi-weekly or custom billing cycles. Dolibarr subscriptions support flexible frequencies. | LOW | Dolibarr recurring invoices support daily/weekly/monthly/quarterly/yearly. |
| **Idle fee / overtime detection** | ChargePoint, Flipturn, Driivz all support idle fees to discourage overstaying. Increases revenue and turnover. | MEDIUM | Requires session monitoring after charge complete. Not in v1 scope. |
| **Real-time session status feedback** | Wallbox/Alfen chargers show charging status on display. Home Assistant can expose status entities. Nice for monitoring. | LOW | Home Assistant has rich sensor/notification ecosystem. |
| **Automatic retry with exponential backoff (API)** | More robust than simple retry. Reduces manual intervention. | LOW | Enhancement over basic retry in PROJECT.md. |
| **RFID card lifecycle management UI** | Dolibarr module could allow admins to issue/revoke RFID cards. Competitive with Wallbox portal features. | MEDIUM | Extends Dolibarr module beyond basic user fields. |
| **Per-department / cost center allocation** | Business users (fleets) want costs allocated to departments. Dolibarr supports this natively. | LOW | Already in PROJECT.md (Kostenstelle field). |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Mobile App for end users** | "Modern EV chargers have apps" (Wallbox app, Electromaps) | Dolibarr already has web UI; native app is massive effort for limited gain. Web-responsive UI is sufficient. | Dolibarr web portal with mobile-responsive theme |
| **Real-time charging dashboard / live monitoring** | Users like seeing charge progress | Core value is **billing**, not monitoring. Home Assistant already has energy dashboard. Scope creep. | Home Assistant's built-in energy dashboard + notifications |
| **Load balancing / smart charging** | "Charger should optimize for solar/grid" | Completely separate domain (OCPP smart charging profiles). Alfen handles this natively. Not part of billing solution. | Alfen Eve's built-in load management + Home Assistant solar integrations (EVCM, etc.) |
| **Payment processing (SEPA, credit card at charger)** | "Charge users automatically" | Dolibarr has Stripe/PayPal integrations. Payment processing is not billing system's job. AFIR requires ad-hoc payment options for DC fast chargers only. | Use Dolibarr's native payment modules + Stripe/PayPal |
| **Plug & Charge (ISO 15118)** | "Tesla-like seamless experience" | Requires vehicle certificates, OCPP 2.0.1, complex PKI infrastructure. Alfen Eve supports it but adds huge complexity for v1. | RFID + future upgrade path |
| **Roaming (OPI/OCPI integration)** | "Allow any RFID card from any network" | Requires hub agreements (Hubject, Gireve), complex settlement. Irrelevant for single-site Dolibarr setup. | Future expansion via OCPP backend change |
| **Last management (dynamic load balancing across multiple chargers)** | "Share limited power across chargers" | OCPP 1.6 has `SmartCharging` profile but is complex. Alfen handles this natively for up to 100 chargers. | Alfen's native load management + optional OCPP `SetChargingProfile` |
| **QR code / app-based authentication** | "Don't want to carry RFID cards" | RFID is primary auth for reliability (works offline at user side). QR/app is backup at best. | RFID primary + optional future app auth |

## Feature Dependencies

```
RFID Whitelist Management
    └──requires──> User Management (RFID → User mapping)
                        └──requires──> Session Tracking (need user ID in session)
                                            └──requires──> kWh Billing (sessions → billable amount)
                                                            └──requires──> Monthly Invoicing (aggregate bills)
                                                                                └──requires──> PDF Generation

Session Persistence (SQLite)
    └──enhances──> Session Tracking (survives HA restarts)

REST API (HA → Dolibarr)
    └──requires──> Session Tracking (data to transmit)
    └──requires──> API Authentication (token management)
    └──enhances──> Reliable Billing (no data loss)

RFID Debouncing
    └──enhances──> Session Tracking (clean session starts/stops)

Per-User kWh Pricing
    └──requires──> User Management (price stored per user)
    └──enhances──> Billing Accuracy

Multi-Wallbox Support
    └──enhances──> Scalability (future-proof)
    └──requires──> Wallbox-ID in session data

CSV/DATEV Export
    └──requires──> Monthly Invoicing (data source)
    └──enhances──> Accounting Integration (differentiator)

Privacy (RFID Hashing)
    └──enhances──> GDPR Compliance
    └──requires──> User Management (store hash, not plaintext)
```

### Dependency Notes

- **Session Tracking requires RFID Whitelist:** Must know which RFID card started the session before billing can occur.
- **kWh Billing requires Session Tracking:** Cannot bill without session data (start/end kWh, timestamps).
- **Monthly Invoicing requires kWh Billing:** Invoices aggregate individual session costs.
- **REST API requires Session Tracking:** No session data = nothing to transmit to Dolibarr.
- **Per-User Pricing enhances Billing:** User-specific rates require user management to be in place first.
- **Multi-Wallbox requires Wallbox-ID:** Each session must record which physical charger was used.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] RFID authentication via whitelist (YAML) — core auth mechanism
- [ ] Session tracking with start/end time, kWh, RFID ID, Wallbox-ID — billing data foundation
- [ ] Session persistence in SQLite — reliability across HA restarts
- [ ] RFID debouncing — clean session data
- [ ] User management in Dolibarr (RFID-ID, per-user kWh price, Kostenstelle)
- [ ] REST API with token auth + retry logic (HA → Dolibarr)
- [ ] Monthly billing as Dolibarr Cronjob (last day of month)
- [ ] PDF invoice generation — core value delivered
- [ ] RFID hash storage (no plaintext logging) — GDPR compliance
- [ ] CSV/DATEV export — German accounting integration (differentiator)

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] Real-time session status notifications (HA → user) — trigger: users want status visibility
- [ ] Automatic retry with exponential backoff — trigger: network issues cause failed transmissions
- [ ] RFID card lifecycle management UI in Dolibarr — trigger: admin overhead of YAML editing becomes burdensome
- [ ] Idle fee detection — trigger: chargers occupied after charge complete
- [ ] Transparent session history per user in Dolibarr — trigger: users request their own data

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] QR code / app-based authentication — why defer: RFID works; app adds complexity without clear v1 need
- [ ] Plug & Charge (ISO 15118) — why defer: huge PKI complexity; RFID sufficient for v1
- [ ] Roaming (OCPI) integration — why defer: single-site Dolibarr setup doesn't need roaming
- [ ] Native mobile app — why defer: Dolibarr web UI sufficient; app is massive effort
- [ ] Load balancing / smart charging — why defer: separate domain; Alfen handles natively

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| RFID authentication (whitelist) | HIGH | LOW | P1 |
| Session tracking (kWh, timestamps, RFID) | HIGH | MEDIUM | P1 |
| Session persistence (SQLite) | HIGH | LOW | P1 |
| Monthly billing + PDF invoice | HIGH | MEDIUM | P1 |
| REST API with retry (HA → Dolibarr) | HIGH | MEDIUM | P1 |
| User management (RFID → user, per-user price) | HIGH | MEDIUM | P1 |
| RFID debouncing | MEDIUM | LOW | P1 |
| RFID hash storage (GDPR) | HIGH | LOW | P1 |
| CSV/DATEV export | MEDIUM | LOW | P2 |
| Multi-wallbox support | MEDIUM | HIGH | P2 |
| Real-time session notifications | LOW | LOW | P3 |
| Exponential backoff for API retry | LOW | LOW | P3 |
| RFID lifecycle management UI | MEDIUM | MEDIUM | P2 |
| Idle fee detection | LOW | MEDIUM | P3 |
| Plug & Charge (ISO 15118) | LOW | HIGH | P3 |
| Mobile app for end users | LOW | HIGH | P3 |
| Load balancing / smart charging | LOW | HIGH | P3 |
| Roaming (OCPI) integration | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (table stakes)
- P2: Should have, add when possible (differentiators)
- P3: Nice to have, future consideration (anti-features or deferred)

## Competitor Feature Analysis

| Feature | Wallbox (Pulsar Pro / Pay per Month) | Alfen Eve (Pro-line) | Dolibarr (ERP) | Our Approach |
|---------|-------------------------------|-------------------|----------------|--------------|
| RFID authentication | ✅ RFID cards + app | ✅ ISO 14443, 800-1200 local tokens | ❌ (needs custom module) | ✅ YAML whitelist + Dolibarr module |
| kWh billing (MID meter) | ✅ MID meter standard | ✅ MID-certified meter | ❌ (needs custom module) | ✅ Alfen MID + HA sensor |
| Session tracking | ✅ CDR with kWh, timestamps | ✅ 1500 transaction local DB | ❌ (needs custom table) | ✅ SQLite in HA + `llx_wallbox_sessions` |
| Monthly invoicing | ✅ Pay per Month (5% fee) | ❌ (needs backend) | ✅ Native recurring invoices | ✅ Dolibarr Cronjob |
| PDF generation | ✅ Automatic PDF invoices | ❌ | ✅ Native PDF per invoice | ✅ Dolibarr native |
| Per-user pricing | ✅ User-specific rates | ❌ | ✅ Custom fields possible | ✅ Dolibarr user fields |
| API/integration | ✅ OCPP 1.6, API | ✅ OCPP 1.6, API | ✅ REST API, hooks | ✅ REST API (HA → Dolibarr) |
| Offline resilience | ⚠️ Cloud-dependent | ✅ Local whitelist (offline auth) | N/A | ✅ SQLite + local whitelist |
| Multi-charger support | ✅ Up to 100 (Alfen) / OCPP | ✅ Up to 100 singles/50 dual | ✅ Scales with DB | ✅ Wallbox-ID in sessions |
| DATEV/CSV export | ❌ | ❌ | ✅ Export module | ✅ Custom CSV export |
| Plug & Charge | ✅ (some models) | ✅ (Eve Pro-line DE) | ❌ | ❌ (deferred to v2) |
| Mobile app | ✅ myWallbox app | ❌ (web only) | ✅ (web-responsive) | ❌ (Dolibarr web UI) |
| Load management | ✅ Dynamic Power Sharing | ✅ Up to 100 chargers | N/A | ❌ (Alfen native) |

## Sources

- **Alfen Eve Single Pro-line Documentation** — https://alfen.com/en/ev-charging/home/eve-single-pro-line (specs: MID meter, RFID ISO 14443, OCPP 1.6, 800-1200 token local list, 1500 transaction DB)
- **Wallbox Pay per Month & Pay per Charge** — https://support.wallbox.com/en/knowledge-base/how-to-set-the-pay-per-month-billing-solution-for-your-chargers/ (billing rates: per kWh, per minute, fixed fee; RFID auth; 5% fee model)
- **BCG: What EV Owners Really Want** — https://www.bcg.com/publications/2023/what-ev-drivers-expect-from-charging-stations-for-electric-cars (reliability, speed, ease of use are table stakes)
- **EV Charging Payment UX (Autoraiders, 2026)** — https://autoraiders.com/2026/01/16/ev-charging-payment-ux-why-plug-and-charge-is-becoming-the-new-standard/ (RFID still preferred by fleets; Plug & Charge is future)
- **Dolibarr Billing Module** — https://www.dolibarr.org/presentation-billing-invoicing.php (recurring invoices, PDF generation, payment gateways, export capabilities)
- **Dolibarr Subscriptions Module** — https://www.dolibarr.org/presentation-contracts-subscriptions.php (automated recurring billing, cron-based generation)
- **PandaExo: RFID & App Billing (2026)** — https://www.pandaexo.com/how-rfid-app-billing-work-in-semi-public-ac-charging-stations/ (RFID flow: tap → UID → OCPP → backend → authorize; session data recording)
- **RFID Card in EV Charging (RFIDCard.com, 2025-2026)** — https://www.rfidcard.com/the-business-value-of-rfid-cards-in-ev-charging-stations/ (fleet management, centralized billing, RFID as baseline access method)
- **OCPI CDR Billing (EV Cloud, 2026)** — https://www.ev-cloud.ai/blog/ocpi-cdr-billing-integration (CDR structure: session ID, kWh, timestamps, tariff ID, total cost, taxes)
- **Nature: EV Charging User Reviews (2025)** — https://www.nature.com/articles/s41467-025-60091-y (user pain points: network-specific cards, payment friction)
- **Flipturn, Tridens, GDON, Plugmatic** — Competitor billing platforms (kWh billing, RFID management, session tracking, PDF invoices as table stakes)
- **Project Context: /home/roto/.planning/PROJECT.md** — Validated requirements, out-of-scope items, constraints

---

*Feature research for: Wallbox-Dolibarr RFID Billing Integration*
*Researched: 2026-05-04*
*Confidence: MEDIUM — based on vendor docs (Alfen, Wallbox), industry research (BCG, Nature), and competitor platforms. Some extrapolation for Dolibarr integration specifics.*
