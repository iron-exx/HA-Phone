# Project Research Summary

**Project:** Wallbox-Dolibarr RFID Billing Integration
**Domain:** EV Charging Billing System (Home Assistant + Dolibarr ERP)
**Researched:** 2026-05-04
**Confidence:** HIGH (stack and architecture), MEDIUM (features extrapolated from vendor docs)

## Executive Summary

This project builds a bridge between an Alfen Eve Wallbox (EV charger) and Dolibarr ERP to automate kWh-based billing for RFID-authenticated charging sessions. The architecture follows a **hub-and-spoke pattern**: Home Assistant acts as the local hub that reads wallbox data via Modbus TCP, tracks charging sessions in SQLite, and pushes completed sessions to Dolibarr via REST API for monthly invoicing. This is a proven pattern in the EV charging industry—competitors like Wallbox Pay per Month and PandaExo use similar local-to-cloud flows, but this implementation leverages Dolibarr's native billing engine instead of a proprietary subscription platform.

The recommended technical approach is **pragmatic and minimal**: a Python-based HA Addon (Alpine 3.23, Python 3.13) handles session logic with SQLite persistence, while a PHP module extends Dolibarr (21.x-22.x, PHP 8.1+) with custom tables and cron-driven billing. No FastAPI or Flask is needed in the addon—simple Python with `requests` library suffices since the addon only makes outgoing API calls. The Dolibarr module follows standard module development patterns with `modWallbox.class.php`, DAO classes, and REST API endpoints via RESTler.

The primary risks are **RFID fraud via cloned cards** (MIFARE Classic UIDs are unencrypted and easily sniffed) and **session state loss on HA restarts**. Mitigation: always hash RFID with SHA-256 before storage, never log plaintext RFIDs, implement startup recovery logic for SQLite sessions, and add server-side anomaly detection for impossible travel patterns. Additionally, Alfen's wallbox API allows only one active session at a time—the addon must implement proper login/logout cycling and handle 429 rate-limit errors with exponential backoff.

## Key Findings

### Recommended Stack

The stack is split across two runtimes: Home Assistant Addon (local edge) and Dolibarr (backend ERP).

**HA Addon core technologies:**
- **Alpine Linux 3.23 (via HA base image `ghcr.io/home-assistant/base:3.23`)** — minimal container OS, official HA standard, automatic ARM/x86 detection via `BUILD_FROM`
- **Python 3.13** — HA's standard runtime; ideal for Modbus polling, SQLite access, and REST client work
- **SQLite3 (built-in)** — local session persistence that survives HA restarts; no network DB needed for edge tracking
- **requests 2.32+** — HTTP client for Dolibarr API calls; simpler than aiohttp for this use case (outgoing only)
- **bashio (built-in)** — access to HA Supervisor API for config, secrets, and logging

**Dolibarr Module core technologies:**
- **PHP 8.1+** — Dolibarr 21.x-22.x supports up to PHP 8.3; 8.1+ recommended for type hints and match expressions
- **MariaDB 10.3+** — Dolibarr's recommended database; MySQL 5.7+ also works
- **Dolibarr Core 21.x or 22.x** — LTS versions with active community support and REST API stability
- **TCPDF (built-in)** — PDF invoice generation via Dolibarr's native `pdf_wallbox.modules.php`

**Build system:** Docker BuildKit with `ARG BUILD_FROM` (legacy `home-assistant/builder` is deprecated as of April 2026).

### Expected Features

**Must have (table stakes — P1):**
- **RFID authentication via whitelist (YAML)** — core auth mechanism; Alfen Eve supports 800-1200 local tokens, we use a YAML whitelist per PROJECT.md
- **Session tracking** (start/end kWh, timestamps, RFID hash, wallbox-ID) — foundation for all billing; stored in SQLite
- **Session persistence (SQLite)** — survives HA restarts; recovery logic queries active sessions on startup
- **kWh billing with MID-compliant meter** — Alfen Eve has integrated MID meter; `sensor.alfen_energy_total` provides certified values
- **REST API transmission (HA → Dolibarr) with retry** — JSON payload via DOLAPIKEY auth; exponential backoff for resilience
- **User management in Dolibarr** — RFID-hash, per-user kWh price, cost center fields added to `llx_user`
- **Monthly billing + PDF invoices** — Dolibarr Cronjob on last day of month; aggregates sessions and generates invoices
- **RFID hash storage (SHA-256, no plaintext)** — GDPR compliance; never log or store raw RFID UIDs
- **RFID debouncing** — suppress multiple reads within 5-10 second window; prevents duplicate sessions
- **CSV/DATEV export** — German accounting integration; differentiator for v1

**Should have (differentiators — P2):**
- **Multi-wallbox scalability** — `wallbox_id` field in sessions; supports up to 100 Alfen chargers
- **RFID card lifecycle management UI** — admin interface in Dolibarr to issue/revoke cards (reduces YAML editing)
- **Configurable billing periods** — not just monthly; Dolibarr subscriptions support flexible frequencies

**Defer (v2+):**
- **Plug & Charge (ISO 15118)** — requires PKI infrastructure and OCPP 2.0.1; RFID sufficient for v1
- **Mobile app for end users** — Dolibarr web UI is responsive; native app is massive effort for limited gain
- **Load balancing / smart charging** — separate domain; Alfen handles natively via OCPP `SmartCharging` profile
- **Roaming (OCPI) integration** — irrelevant for single-site Dolibarr setup

### Architecture Approach

The system uses a **hub-and-spoke architecture** with one-way data flow: Alfen Wallbox → Home Assistant (Modbus TCP) → HA Addon (SQLite session tracking) → Dolibarr REST API → Dolibarr Module (billing engine). The HA Addon is the intelligence layer—it polls the wallbox every 20 seconds, detects RFID taps and charging state transitions, persists sessions locally, and transmits completed sessions to Dolibarr. The Dolibarr module receives sessions via REST API, links them to users by RFID hash, and runs a monthly cron job that calculates costs (kWh × user price), generates PDF invoices, and optionally exports to DATEV format. Component boundaries are clean: HA custom integration only exposes sensors (no business logic), the Addon handles session state machines, and Dolibarr module follows standard PHP module patterns with `llx_wallbox_sessions` table and RESTler API endpoints.

**Major components:**
1. **HA Alfen Modbus Integration** — polls wallbox registers (RFID, energy, status) via TCP port 502; exposes `sensor.alfen_eve_tag_socket_1`, `sensor.alfen_energy_total`, charging status
2. **HA Wallbox Addon** — session state machine, RFID whitelist check (YAML), SQLite persistence, startup recovery, REST client to Dolibarr
3. **Dolibarr Wallbox Module** — custom tables (`llx_wallbox_sessions`), user extension fields (RFID hash, kWh price, cost center), REST API endpoint, monthly billing cron

### Critical Pitfalls

1. **RFID Cloning and Fraud (Critical)** — MIFARE Classic UIDs are unencrypted and easily cloned with $20 tools; 80-90% of charging transactions are vulnerable. **Prevention:** Hash RFIDs with SHA-256 before storage, never log plaintext, implement server-side duplicate detection for simultaneous sessions, add anomaly detection for impossible travel patterns. **Phase:** HA Addon RFID handling (Phase 1).

2. **Session State Loss on HA Restart (Critical)** — active sessions lost if not persisted properly; causes billing discrepancies. **Prevention:** SQLite recovery on startup (query `status='active'`), implement Option A from research (close orphaned session with current meter reading, start new if still charging), write to SQLite atomically before acknowledging session start. **Phase:** HA Addon persistence (Phase 1).

3. **RFID Debouncing Failures (Critical)** — readers fire multiple events for single tap; causes duplicate sessions. **Prevention:** state machine with `previous_tag` + `last_read_time`, suppress repeats within 5-10s window, only trigger on tag CHANGE not tag PRESENCE. **Phase:** HA Addon RFID handling (Phase 1).

4. **Wallbox API Single-Session Limit (Critical)** — Alfen allows only ONE active API session; HA Addon and MyEve app conflict. **Prevention:** implement login/logout cycle per API call, queue requests (no concurrency), retry with exponential backoff on auth failures, document "don't use MyEve app while Addon active." **Phase:** HA Addon API client (Phase 1/3).

5. **Incorrect Billing from Energy Meter Timing (Critical)** — capturing meter readings at wrong state transitions causes under/over-billing. **Prevention:** only capture `meter_start_kwh` when state transitions to `Charging` (not on RFID tap), only capture `meter_end_kwh` when state transitions to `Idle`/`Stopped`, cross-validate charged_kwh ±5% against car consumption. **Phase:** HA Addon state machine (Phase 1).

## Implications for Roadmap

Based on combined research, the recommended phase structure is:

### Phase 1: Foundation (HA Integration + Dolibarr Skeleton)
**Rationale:** No dependencies — these two workstreams can run in parallel. HA integration is needed before any session logic can work; Dolibarr skeleton is needed before module features can be added.
**Delivers:** HA Alfen Modbus integration (custom component exposing sensors), Dolibarr module skeleton (`modWallbox.class.php`, directory structure, table creation on activate)
**Addresses:** Foundation for all downstream work — sensors enable session tracking; module skeleton enables user extension and billing features
**Avoids:** Building on wrong foundation — verify sensor readings and module activation before proceeding
**Uses:** Python 3.13 (HA), PHP 8.1+ (Dolibarr), Modbus TCP (port 502), Dolibarr module development patterns
**Stack elements:** HA base image, Python, PHP, Dolibarr core

### Phase 2: Session Tracking + User Management
**Rationale:** Depends on Phase 1 — need HA sensors working before tracking sessions; need Dolibarr module active before extending users.
**Delivers:** HA Addon with SQLite session tracking (start/end kWh, RFID hash, wallbox-ID), RFID whitelist check (YAML), debouncing logic, user management in Dolibarr (RFID hash field, kWh price, cost center)
**Addresses features:** RFID authentication, session tracking, SQLite persistence, RFID debouncing, user management, RFID hash storage (GDPR)
**Avoids:** Pitfall 2 (debouncing), Pitfall 3 (session loss — implement recovery in this phase), Pitfall 5 (meter timing — state machine here)
**Implements:** HA Addon component, SQLite `sessions` table, Dolibarr user extension (`llx_user` ALTER)

### Phase 3: Integration (HA Addon → Dolibarr API)
**Rationale:** Depends on Phase 2 — need sessions in SQLite before transmitting; need Dolibarr API endpoint before receiving data.
**Delivers:** HA Addon REST client (DOLAPIKEY auth, retry with exponential backoff), Dolibarr REST API endpoint (`/api/index.php/wallbox_sessions`), JSON payload transmission on session complete
**Addresses features:** REST API transmission with retry logic
**Avoids:** Pitfall 4 (wallbox API conflicts — rate limiter here), Pitfall 1 (RFID cloning — ensure hashes transmitted, not plaintext), Minor Pitfall 3 (API token in secrets.yaml, not logs)
**Implements:** REST API client pattern (Python requests), Dolibarr RESTler service (`api_wallbox_sessions.class.php`)

### Phase 4: Billing + Invoicing
**Rationale:** Depends on Phase 3 — need sessions in Dolibarr before billing can run; this is the core value delivery.
**Delivers:** Dolibarr monthly billing cronjob (last day of month, or 1st for previous month), PDF invoice generation (`pdf_wallbox.modules.php`), CSV/DATEV export for German accounting
**Addresses features:** Monthly billing, PDF invoices, CSV/DATEV export (differentiator)
**Avoids:** Moderate Pitfall 3 (cronjob timing — run on 1st for previous month, add overlap protection), Moderate Pitfall 1 (SQL injection — use GETPOST(), transactions)
**Implements:** Dolibarr cron system, PDF generation via `pdf.lib.php`, CSV export

### Phase 5: Hardening + Multi-Wallbox
**Rationale:** Depends on Phase 4 — core value delivered; now harden against edge cases and scale.
**Delivers:** HA Addon restart recovery (robust startup logic), multi-wallbox support (wallbox-ID in all sessions), RFID lifecycle UI in Dolibarr, timezone/DST handling (UTC storage), SQLite WAL mode for concurrency
**Addresses features:** Multi-wallbox scalability, RFID lifecycle UI, timezone handling
**Avoids:** Minor Pitfall 1 (SQLite locking — WAL mode), Minor Pitfall 4 (DST — UTC storage), Pitfall 3 (session loss — harden recovery logic)
**Implements:** Enhanced error handling, multi-entity support (`$conf->entity`), admin UI for RFID cards

### Phase Ordering Rationale

- **HA Integration before Addon logic:** Can't track sessions without sensor data from Modbus
- **Dolibarr skeleton before user/billing features:** Module must be activated before adding tables/fields
- **Session tracking before API integration:** Need sessions in SQLite before transmitting to Dolibarr
- **API integration before billing:** Need sessions in Dolibarr before generating invoices
- **Billing before hardening:** Core value (invoices) ships first; hardening is risk mitigation
- **Parallel workstreams in Phase 1:** HA integration and Dolibarr skeleton have no dependencies on each other — dispatch as parallel agents

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (HA Alfen Modbus Integration):** Need to verify exact Modbus register addresses for RFID tag, energy meter, and charging status. The [Alfen Modbus PDF](https://alfen.com/media/1047/download) has them, but register mapping should be researched in detail during `/gsd-research-phase`.
- **Phase 3 (REST API Integration):** Dolibarr REST API authentication options (DOLAPIKEY vs OAuth) and RESTler endpoint patterns need validation during planning. Consider `/gsd-research-phase` for API contract.
- **Phase 4 (PDF Invoice Generation):** Dolibarr's `pdf_wallbox.modules.php` pattern needs concrete example research. The `core/lib/pdf.lib.php` functions are documented but practical implementation may need a research spike.

Phases with standard patterns (skip research-phase):
- **Phase 2 (Session Tracking):** SQLite patterns, RFID whitelist YAML loading, and debouncing are well-documented. Standard implementation with `/gsd-plan-phase` directly.
- **Phase 5 (Hardening):** Restart recovery, WAL mode, and timezone handling are established patterns. No research spike needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Official HA base images verified (Alpine 3.23, Python 3.13). Dolibarr PHP 8.1+ compatibility verified against release notes. BuildKit migration documented. |
| Features | MEDIUM | Based on competitor analysis (Wallbox, Alfen, PandaExo) and industry research (BCG, Nature). Some extrapolation for Dolibarr-specific UI features. |
| Architecture | HIGH | Hub-and-spoke pattern verified against existing integrations (ThaStealth/alfen_modbus, evcc). Dolibarr module structure from official wiki. Anti-patterns clearly identified. |
| Pitfalls | HIGH | RFID cloning research from arxiv.org papers. Session recovery from evcc GitHub issues. Debouncing from Raspberry Pi forums. All critical pitfalls have verified sources. |

**Overall confidence:** HIGH for technical foundation, MEDIUM for feature completeness (may discover Dolibarr-specific constraints during implementation).

### Gaps to Address

- **Alfen Eve specific API property codes:** Need exact Modbus register numbers for socket_1 RFID, energy total, and charging status. The [Alfen API params wiki](https://github.com/leeyuentuen/alfen_wallbox/wiki/API-paramID) should be checked during Phase 1 planning.
- **Dolibarr version-specific behaviors:** Test module with Dolibarr 21.x vs 22.x — descriptor must declare supported versions. May need conditional code for version differences.
- **OCPP vs local API tradeoffs:** Project uses local Modbus/API, but if single-session limit becomes problematic, evaluate OCPP backend change (would be v2+).
- **MID meter compliance verification:** Confirm Alfen Eve's MID certificate number and how to read verified values (not just `sensor.alfen_energy_total` which may be uncalibrated).
- **RFID hashing salt management:** Where to store the salt for SHA-256 hashing — HA Addon config vs Dolibarr global config? Must be consistent between systems.

## Sources

### Primary (HIGH confidence)
- **[Home Assistant Docker Base](https://github.com/home-assistant/docker-base)** — Alpine 3.23, Python 3.13, BuildKit migration (April 2026)
- **[Alfen Modbus Documentation](https://alfen.com/media/1047/download)** — Official Modbus register map for Eve Single Pro-line
- **[Dolibarr Module Development Wiki](https://wiki.dolibarr.org/index.php/Module_development)** — Standard module structure, descriptor, SQL install scripts
- **[Dolibarr REST API Docs](https://github.com/Dolibarr/dolibarr/blob/develop/htdocs/api/README.md)** — DOLAPIKEY auth, endpoint patterns, RESTler framework
- **[Security Aspects of ISO 15118](https://arxiv.org/abs/2512.15966)** — RFID cloning vulnerabilities, static UID risks
- **[Intentional and Unintentional Fraud](https://www.deftpower.com/resources/white-papers/intentional-and-unintentional-fraud-in-ev-charging)** — 80-90% transactions use vulnerable RFID

### Secondary (MEDIUM confidence)
- **[Alfen Modbus HA Integration](https://github.com/ThaStealth/alfen_modbus)** — Existing code example (Python, ModbusHub pattern)
- **[Wallbox Pay per Month](https://support.wallbox.com/en/knowledge-base/how-to-set-the-pay-per-month-billing-solution-for-your-chargers/)** — Competitor billing model (kWh rate, RFID auth, 5% fee)
- **[Building Your Own Dolibarr Modules](https://dolimarketplace.com/en/blogs/dolibarr/building-your-own-dolibarr-modules-a-developer-s-guide)** — SQL injection prevention, GETPOST() usage
- **[evcc Issue #8788](https://github.com/evcc-io/evcc/issues/8788)** — SQLite session recovery patterns, restart survival strategies

### Tertiary (LOW confidence — needs validation)
- **OCPP 1.6 SmartCharging profile** — Load balancing capabilities; may be needed if Alfen native management insufficient
- **Plug & Charge (ISO 15118) PKI** — Future upgrade path; complexity not fully scoped
- **Dolibarr multi-company mode** — `entity` field behavior not tested; may affect billing queries

---
*Research completed: 2026-05-04*
*Ready for roadmap: yes*
