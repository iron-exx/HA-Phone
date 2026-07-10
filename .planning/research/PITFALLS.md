# Domain Pitfalls

**Domain:** Wallbox RFID Billing System (Home Assistant + Dolibarr)
**Researched:** 2026-05-04
**Confidence:** HIGH (based on research papers, GitHub issues, security analyses, and industry white papers)

## Critical Pitfalls

Mistakes that cause rewrites or major issues.

### Pitfall 1: RFID Cloning and Fraud Due to Unencrypted Card UIDs

**What goes wrong:** RFID cards used in EV charging (especially MIFARE Classic) transmit unencrypted static UIDs that can be easily intercepted and cloned using inexpensive tools (smartphones with NFC apps, RFID sniffers, software-defined radios). Attackers can copy a card's UID and create duplicate cards, leading to unauthorized charging billed to the victim's account. Research shows 80-90% of charging transactions still use vulnerable RFID cards, and fleet operators have reported 100% fraud rates before implementing countermeasures.

**Why it happens:** 
- MIFARE Classic protocol (used by many EV charging systems) has no encryption
- RFID tags broadcast static UIDs that never change
- Many systems rely solely on UID matching without additional authentication factors
- Cards often display the "hidden" serial number in plaintext (starting with '04')

**Consequences:**
- Financial losses from fraudulent charging sessions
- Victim users billed for sessions they didn't initiate
- Reputational damage to the charging service
- Fraudulent charges can accumulate to thousands of euros monthly

**Prevention:**
- Hash RFID UIDs before storing (SHA-256 minimum) — already planned per PROJECT.md
- Never log RFID in cleartext — already planned, but MUST enforce strictly
- Implement server-side duplicate detection: flag multiple simultaneous sessions with same RFID
- Consider adding 2FA for high-consumption sessions (like Tap Electric's Tap Tag approach)
- Monitor for impossible travel (same RFID used at different locations within impossible timeframes)
- Implement Tap Radar-style anomaly detection: flag unusual charging patterns

**Detection:**
- Monitor for multiple active sessions with same RFID
- Alert on sessions with consumption > vehicle battery capacity
- Track RFID usage locations and timing patterns
- Set up alerts for sessions outside normal hours for specific users

**Phase to address:** Phase 1 (Home Assistant Addon) — RFID handling and hashing must be implemented correctly from the start

---

### Pitfall 2: RFID De-bouncing Failures Causing Multiple Sessions

**What goes wrong:** RFID readers can trigger multiple reads of the same tag within seconds when a card is held near the reader, causing the system to start multiple charging sessions or incorrectly terminate/restart sessions. This is a well-documented issue in RFID systems (RDM6300, RC522 modules) where the reader continuously transmits the tag data while the card is present.

**Why it happens:**
- RFID tags continuously transmit while in reader range
- Reader has no built-in de-bouncing logic
- Software doesn't track "previous tag" state to suppress duplicates
- No time-based suppression of repeated reads

**Consequences:**
- Multiple session records for single charging event
- Billing discrepancies and user complaints
- Database pollution with duplicate/invalid sessions
- Session state machine corruption

**Prevention:**
- Implement software de-bouncing in the HA Addon:
  - Store `previous_tag` + `last_read_time` 
  - Suppress repeats within 5-10 second window
  - Only trigger on tag CHANGE (new tag detected), not tag PRESENCE
- Use state machine: `NO_CARD → CARD_DETECTED → SESSION_ACTIVE` (ignore re-reads while session active)
- For Alfen Eve `sensor.alfen_eve_tag_socket_1`: poll and compare, only act on transitions

**Detection:**
- Monitor for sessions with duration < 10 seconds (likely de-bounce artifacts)
- Check for multiple sessions starting within 30 seconds with same RFID
- Log RFID read events with timestamps to identify duplicate patterns

**Phase to address:** Phase 1 (Home Assistant Addon) — de-bouncing logic must be in initial RFID handling code

---

### Pitfall 3: Session State Loss on Home Assistant Restart

**What goes wrong:** When Home Assistant restarts (intentionally or due to crashes), active charging sessions are lost if not properly persisted. The in-memory session state disappears, leading to "orphaned" charging sessions that never get properly closed, or new sessions that don't account for energy already delivered.

**Why it happens:**
- Session state stored only in HA's memory/entities
- SQLite persistence exists but isn't queried on startup to recover state
- No logic to detect incomplete sessions and resume/close them
- `meter_start_kwh` lost on restart, making `charged_kwh` calculation impossible

**Consequences:**
- Incomplete charging records (missing `meter_end_kwh`, `charged_kwh`)
- Incorrect billing (only start reading captured, end reading lost)
- Users not billed for energy actually consumed
- Manual database repair required (as seen in evcc issues #8788)

**Prevention:**
- On HA Addon startup: query SQLite for sessions with `end_time = NULL` or `meter_end_kwh = NULL`
- Recovery logic (choose one approach):
  - **Option A (recommended):** Close orphaned session with current meter reading, create new session if car still charging
  - **Option B:** Resume session (restore state) if wallbox reports car still connected and charging
- Store session state as persistent entities (`input_text` or similar) that survive restart
- Write to SQLite BEFORE acknowledging session start (atomic operation)

**Detection:**
- Check SQLite for sessions with `finished = '0001-01-01 00:00:00'` or NULL end times
- Alert on HA restart if open sessions exist
- Validate: `meter_end_kwh >= meter_start_kwh` for all completed sessions

**Phase to address:** Phase 1 (Home Assistant Addon) — SQLite schema must include recovery logic from day one

---

### Pitfall 4: Wallbox API Session Conflicts (Single Session Limit)

**What goes wrong:** Alfen Wallbox (and many wallboxes) allow only ONE active API session at a time. If the Home Assistant Addon logs in, the MyEve/Eve Connect app gets disconnected. If the app is in use, the HA Addon can't authenticate. This causes intermittent failures in session management.

**Why it happens:**
- Wallbox API uses session-based auth with single-session enforcement
- API tokens expire or get invalidated by other clients
- No proper session management/reconnection logic in the Addon
- Conflicts between manual app usage and automated Addon

**Consequences:**
- Failed API calls to start/stop charging
- Unable to read RFID or energy data during API lockout
- Session state gets out of sync between Addon and wallbox
- 401/403 errors when trying to transmit to Dolibarr

**Prevention:**
- Implement proper login/logout cycle for each API call (as seen in alfen_wallbox integration)
- Use request queueing: don't make concurrent API calls
- Add retry logic with exponential backoff on auth failures
- Consider OCPP mode if available (bypasses cloud API limitations)
- Document for users: "Don't use MyEve app while Addon is active"

**Detection:**
- Monitor for HTTP 401/403 errors in Addon logs
- Track API call success/failure rates
- Alert if consecutive API failures exceed threshold (3+)

**Phase to address:** Phase 1 (Home Assistant Addon) — API client must handle single-session constraint

---

### Pitfall 5: Incorrect Billing Due to Energy Meter Reading Timing

**What goes wrong:** The energy meter reading at session start/stop doesn't match actual charging energy because:
- Reading taken before EV begins drawing power (session started, but car delays start)
- Reading taken after EV stops (session ended, but meter keeps incrementing briefly)
- Using `sensor.alfen_energy_total` at wrong state transitions

**Why it happens:**
- Confusion between "session authorized" vs "energy flowing"
- Not waiting for `Charging` state before capturing `meter_start_kwh`
- Capturing end reading before car stops drawing current
- Alfen states not properly understood (state 2501_2 values)

**Consequences:**
- Under-billing or over-billing users
- Disputes and manual invoice corrections
- Energy differences that don't match car's reported consumption
- VAT/tax calculation errors due to wrong energy amounts

**Prevention:**
- Only capture `meter_start_kwh` when state transitions to `Charging` (not on RFID tap)
- Only capture `meter_end_kwh` when state transitions to `Idle`/`Stopped` (not on RFID tap)
- Cross-validate: `charged_kwh = meter_end - meter_start` should match car's consumption ±5%
- Log state transitions with timestamps and meter readings for debugging
- Understand Alfen states: State 2501_2 = 1 (Idle), 2 (Charging), 3 (Stopped), etc.

**Detection:**
- Flag sessions where `charged_kwh <= 0` or `charged_kwh > 100 kWh` (impossible for passenger EV)
- Compare `charged_kwh` with `(meter_end_kwh - meter_start_kwh)` — must match
- Alert on sessions where `charged_kwh` is NULL or zero but duration > 10 minutes

**Phase to address:** Phase 1 (Home Assistant Addon) — state machine and meter reading timing

---

## Moderate Pitfalls

### Pitfall 1: Dolibarr Module SQL Injection and Data Validation Failures

**What goes wrong:** Custom Dolibarr modules often use raw `$_POST`/`$_GET` or inadequate input filtering, leading to SQL injection vulnerabilities or data corruption in the `llx_wallbox_sessions` table.

**Why it happens:**
- Not using Dolibarr's `GETPOST()` with type filters
- Not using the `$db` abstraction layer properly
- Missing input validation on RFID hashes, kWh values, timestamps
- Not using prepared statements or proper escaping

**Consequences:**
- Security vulnerability exploitable by attackers
- Database corruption or unexpected data
- Billing errors from malformed session data
- Module rejection from DoliStore (if published)

**Prevention:**
- ALWAYS use `GETPOST('param', 'alpha')`, `GETPOST('param', 'int')`, etc.
- Use `$db->escape()` for any raw SQL (though prepared statements preferred)
- Validate RFID hash format (expected length/characters) before DB insert
- Validate kWh values are numeric and positive
- Use Dolibarr's `$db->begin()` / `$db->commit()` / `$db->rollback()` transaction pattern

**Detection:**
- Code review: search for raw `$_POST` or string concatenation in SQL
- Test with malicious inputs (SQL injection attempts)
- Enable Dolibarr debug mode and check error logs

**Phase to address:** Phase 2 (Dolibarr Module) — use Dolibarr best practices from the start

---

### Pitfall 2: Wallbox API Rate Limiting (429 Errors)

**What goes wrong:** Wallbox API has strict rate limits (3 GET requests/minute for status, 5 POST/PUT requests/minute). Home Assistant's default Wallbox integration polls every 90 seconds per charger. Exceeding these limits causes HTTP 429 errors, making the Addon unable to read energy data or transmit sessions.

**Why it happens:**
- Polling too frequently for status updates
- Making multiple API calls in quick succession (e.g., login + get status + logout)
- Multiple chargers multiplying request rate
- No rate limiting logic in the Addon

**Consequences:**
- Addon can't read meter data (all chargers appear offline)
- Sessions can't be started/stopped via API
- Energy data gaps in SQLite
- Failed transmissions to Dolibarr

**Prevention:**
- Implement rate limiter: max 1 request per 20 seconds for GET, 1 per 12 seconds for POST
- Batch API calls where possible (use `/api/prop?ids=2060_0,2221_A,2221_B,...` for multiple properties)
- Cache readings: don't re-fetch data that hasn't changed
- Handle HTTP 429 gracefully: wait and retry with exponential backoff
- Consider local Modbus/TCP if license available (bypasses cloud API limits)

**Detection:**
- Monitor for HTTP 429 in Addon logs
- Track API call frequency
- Alert if consecutive rate limit errors

**Phase to address:** Phase 1 (Home Assistant Addon) — API client needs rate limiter

---

### Pitfall 3: Dolibarr Cronjob Timing and Month-End Billing Issues

**What goes wrong:** Monthly billing cronjob runs on the "last day of month" but encounters issues:
- February (28/29 days) vs other months
- Job runs at wrong time (before month-end energy data is complete)
- Job fails silently (no error reporting)
- Overlapping runs (job triggered twice, creating duplicate invoices)

**Why it happens:**
- Not using Dolibarr's built-in cron properly
- Date calculation errors for "last day of month"
- No locking mechanism to prevent concurrent execution
- No validation that all sessions for the month are closed

**Consequences:**
- Missing or incomplete monthly invoices
- Duplicate billing (same sessions billed twice)
- User complaints and manual corrections
- Revenue leakage

**Prevention:**
- Use Dolibarr's cron system (not system cron) for proper integration
- Calculate month-end date programmatically: `last day of this month`
- Add overlap protection: check if invoice already generated for the month
- Validate all sessions have `meter_end_kwh` before billing
- Run billing on 1st of month for PREVIOUS month (safer: all data is complete)
- Add email notification on billing success/failure

**Detection:**
- Log cronjob execution with timestamps
- Check for invoices generated on time (1st-2nd of each month)
- Validate no duplicate invoices for same month/user
- Alert if billing job hasn't run in 32+ days

**Phase to address:** Phase 2 (Dolibarr Module) — cronjob implementation

---

### Pitfall 4: RFID Whitelist YAML Injection or Parse Errors

**What goes wrong:** RFID whitelist stored in YAML (per PROJECT.md decision) can cause the Addon to crash or accept unauthorized cards if:
- YAML syntax error (wrong indentation, special characters in comments)
- File gets corrupted
- Unauthorized modification of whitelist file
- Concurrent read/write to YAML file

**Why it happens:**
- YAML parsing is picky about indentation and special characters
- No validation of RFID hash format in whitelist
- File edited manually with errors introduced
- No file locking during read/write

**Consequences:**
- Addon crashes on YAML parse error
- All RFID cards rejected (denial of service)
- Security bypass if malformed YAML is exploited
- Debugging difficulty

**Prevention:**
- Validate YAML syntax after any programmatic modification
- Use Python's `yaml.safe_load()` (not `yaml.load()` for security)
- Validate each RFID hash in whitelist on load (correct length, hex characters only)
- Make whitelist file read-only for Addon (write via separate admin script)
- Add fallback: if YAML fails to load, log error and DENY ALL (fail-closed, not open)
- Consider SQLite for whitelist if it grows beyond 50+ cards

**Detection:**
- Log YAML load errors with file content snippet
- Validate whitelist on each Addon start
- Alert if whitelist file modified unexpectedly (file watcher)
- Test: known-good RFID rejected after whitelist change

**Phase to address:** Phase 1 (Home Assistant Addon) — YAML handling

---

## Minor Pitfalls

### Pitfall 1: SQLite Database Locking During Concurrent Access

**What goes wrong:** SQLite doesn't support high concurrency. If the Addon tries to write session data while also reading for transmission to Dolibarr, database gets locked, causing `database is locked` errors.

**Prevention:**
- Use SQLite WAL (Write-Ahead Logging) mode: `PRAGMA journal_mode=WAL;`
- Single-threaded access pattern: queue writes, don't hold transactions open
- Keep transactions short (begin → write → commit quickly)
- If using Python, use `timeout=30.0` in `sqlite3.connect()`

**Phase to address:** Phase 1 (Home Assistant Addon) — SQLite setup

---

### Pitfall 2: Dolibarr Multi-Company Support Not Considered

**What goes wrong:** Dolibarr has multi-company mode. If enabled, the wallbox module might write to wrong company's database or show sessions from all companies mixed together.

**Prevention:**
- Check `global $db, $conf;` and use `$conf->entity` to filter by company
- Add `entity = $conf->entity` field to `llx_wallbox_sessions` table
- Test module with multi-company mode enabled

**Phase to address:** Phase 2 (Dolibarr Module) — if multi-company needed

---

### Pitfall 3: REST API Token Exposure in Home Assistant Logs

**What goes wrong:** Dolibarr API token stored in HA configuration or logs might be exposed to users with access to HA logs or configuration.

**Prevention:**
- Store API token in HA `secrets.yaml` (not in Addon code)
- Don't log the token value (mask it in all debug output)
- Use HTTPS for API calls to Dolibarr (prevent network sniffing)
- Rotate API tokens periodically

**Phase to address:** Phase 1 (Home Assistant Addon) — configuration handling

---

### Pitfall 4: Timezone and DST Handling in Billing

**What goes wrong:** Sessions span DST (Daylight Saving Time) changes, causing session duration calculation errors or billing for wrong month.

**Prevention:**
- Store all timestamps in UTC in SQLite (convert to local only for display)
- Use `datetime.utcnow()` (Python) or equivalent UTC functions
- Convert to CET/CEST only when displaying to users in Dolibarr
- Test billing across DST change dates (last Sunday in March and October)

**Phase to address:** Phase 1 & 2 — timestamp handling

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| HA Addon RFID handling | De-bouncing (Pitfall 2) | Implement state machine with 5s suppression |
| HA Addon Session persistence | State loss on restart (Pitfall 3) | SQLite recovery on startup |
| HA Addon Wallbox API | Rate limiting (Pitfall 2 in Moderate) | Implement rate limiter, batch requests |
| HA Addon Energy reading | Wrong timing (Pitfall 5) | Only read meter on state transition to/from Charging |
| Dolibarr Module DB layer | SQL injection (Moderate Pitfall 1) | Use GETPOST(), $db->escape(), transactions |
| Dolibarr Module Cronjob | Month-end billing errors (Moderate Pitfall 3) | Run on 1st for previous month, add overlap protection |
| Dolibarr Module Permissions | Unauthorized access | Follow Dolibarr permission system, check `$user->rights` |
| Transmission to Dolibarr | API token exposure (Minor Pitfall 3) | Use secrets.yaml, HTTPS, no token in logs |
| RFID Whitelist | YAML parse errors (Moderate Pitfall 4) | Validate on load, fail-closed, safe_load |

---

## Sources

| Source | Confidence | Key Contribution |
|--------|------------|-----------------|
| [Security Aspects of ISO 15118 Plug and Charge Payment](https://arxiv.org/abs/2512.15966) | HIGH | RFID cloning vulnerabilities, static UID issues |
| [Physical-Layer Signal Injection Attacks](https://arxiv.org/html/2506.16400v1) | HIGH | Authentication bypass via electrical exploits |
| [Intentional and Unintentional Fraud in EV Charging](https://www.deftpower.com/resources/white-papers/intentional-and-unintentional-fraud-in-ev-charging) | HIGH | 80-90% transactions use vulnerable RFID, cloning risks |
| [Check & Tap Electric Case Study](https://www.tapelectric.app/blog/case-study-rfid-ev-charge-card-fraud-reduction/) | HIGH | 100% fraud elimination with 2FA and anomaly detection |
| [Common RFID Implementation Mistakes](https://lowrysolutions.com/blog/common-rfid-implementation-mistakes-and-how-to-avoid-them/) | HIGH | RFID de-bouncing, tag selection, RF optimization |
| [Building Your Own Dolibarr Modules Guide](https://dolimarketplace.com/en-us/blogs/dolibarr/building-your-own-dolibarr-modules-a-developer-s-guide) | HIGH | SQL injection prevention, naming conventions, permission systems |
| [evcc Issue #8788 - Session Recovery](https://github.com/evcc-io/evcc/issues/8788) | MEDIUM | SQLite session persistence and recovery patterns |
| [Alfen Wallbox HA Integration](https://github.com/leeyuentuen/alfen_wallbox) | HIGH | API session limits, single-session constraint, state handling |
| [Home Assistant Wallbox Issues](https://github.com/home-assistant/core/issues/147022) | HIGH | API rate limiting (429 errors), firmware breaking changes |
| [Dolibarr Module Development Best Practices](https://nextgestion.com/en/module/smartblog/details?slug=developing-dolibarr-modules-where-to-begin-in) | HIGH | Do's and don'ts for module development |
| [RFID Debouncing - Raspberry Pi Forums](https://forums.raspberrypi.com/viewtopic.php?t=59025) | MEDIUM | Multiple read problem and software solutions |
| [Seamless Retry for EV Charging](https://inl.gov/content/uploads/2024/03/ChargeX-report_Seamless-Retry_Dec2024.pdf) | HIGH | Session failure handling, state machine best practices |

---

## Research Gaps

- **Alfen Eve specific API property codes:** Need to verify exact property IDs for session state (beyond 2501_2). The [Alfen API params wiki](https://github.com/leeyuentuen/alfen_wallbox/wiki/API-paramID) should be checked during implementation.
- **Dolibarr version-specific behaviors:** Test with Dolibarr 18.x, 19.x, 20.x to ensure compatibility. The module descriptor must declare supported versions.
- **OCPP vs local API tradeoffs:** The project uses local API, but OCPP might be more stable long-term. This should be evaluated if local API proves problematic.
- **MID meter compliance:** For selling energy in Germany, MID-certified meters are required. Verify Alfen Eve has MID certification and how to read verified values.
