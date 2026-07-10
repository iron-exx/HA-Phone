# Architecture Patterns

**Domain:** Wallbox RFID Billing System (Home Assistant + Dolibarr)
**Researched:** 2026-05-04
**Confidence:** HIGH (official docs, existing integrations, Dolibarr module structure verified)

## Recommended Architecture

The system follows a **hub-and-spoke** pattern with Home Assistant as the local hub and Dolibarr as the backend ERP/CRM. Communication flows one-way: HA → Dolibarr via REST API.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Physical Layer                         │
│  ┌──────────────┐    Modbus TCP     ┌────────────────┐    │
│  │  Alfen Eve   │◄────────────────►│   Home        │    │
│  │  Wallbox     │  (port 502)      │   Assistant   │    │
│  │ RFID: 13.56MHz│  (local IP)    │   (HA OS)     │    │
│  └──────────────┘                  └────────────────┘    │
│         │                                    │              │
│         │ RFID Card (EFCD083E)            │              │
│         ▼                                    │              │
│  ┌──────────────┐                         │              │
│  │  Electric    │                         │              │
│  │  Vehicle     │                         │              │
│  └──────────────┘                         │              │
└─────────────────────────────────────────────┼──────────────┘
                                              │
                                              │ REST API (JSON)
                                              │ DOLAPIKEY auth
                                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Dolibarr ERP/CRM                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Wallbox      │  │ User         │  │ Cron Job     │   │
│  │ Module       │  │ Management   │  │ (Monthly     │   │
│  │ - Tables     │  │ - RFID ID    │  │  Billing)    │   │
│  │ - API Endpoints│  │ - kWh Price  │  │ Last day     │   │
│  └──────────────┘  │ - Cost Center│  └──────────────┘   │
│                      └──────────────┘                       │
│  ┌──────────────┐                                         │
│  │ llx_wallbox_ │                                         │
│  │ sessions     │  (session data + billing)                 │
│  └──────────────┘                                         │
└───────────────────────────────────────────────────────────────┘
```

## Component Boundaries

| Component | Responsibility | Communicates With | Technology |
|-----------|-----------------|-------------------|------------|
| **Alfen Eve Wallbox** | EV charging, RFID authentication, energy metering | Home Assistant (Modbus TCP) | Hardware + Modbus Slave |
| **HA Alfen Integration** | Poll wallbox via Modbus, expose sensors (`sensor.alfen_eve_tag_socket_1`, `sensor.alfen_energy_total`, charging status) | Wallbox (Modbus), HA Core, SQLite, REST API | Python (custom component) |
| **HA Wallbox Addon** | Session tracking logic, RFID whitelist check, SQLite persistence, state recovery after restart, API client to Dolibarr | HA Integration (sensors), SQLite DB, Dolibarr API | Python (addon with UI) |
| **SQLite Database** | Persist active/incomplete charging sessions locally | HA Addon | SQLite3 (`/config/wallbox/sessions.db`) |
| **Dolibarr Wallbox Module** | Receive sessions via REST API, store in `llx_wallbox_sessions`, user extension (RFID, price, cost center), monthly billing cron | Dolibarr Core, Cron System, REST API | PHP (Dolibarr module) |
| **Dolibarr Cron Job** | Monthly billing execution (last day), generate PDF reports, create invoices | Dolibarr Wallbox Module, User Management | PHP (scheduled job) |

## Data Flow

### Primary Flow: Charging Session → Billing

```
1. RFID Card Presented
   [Wallbox] RFID reader detects card → tag ID (e.g., "EFCD083E")
       ↓ (Modbus register read)
   [HA Integration] sensor.alfen_eve_tag_socket_1 updates
       ↓ (state change trigger)
   [HA Addon] Check RFID against whitelist (YAML)
       ↓ (if authorized)
   [HA Addon] Create session record in SQLite
       ├── rfid_hash (SHA256 of RFID, not plaintext)
       ├── start_time
       ├── wallbox_id
       └── status: "active"

2. Charging in Progress
   [Wallbox] Energy meter updates (kWh)
       ↓ (Modbus poll every 20s)
   [HA Integration] sensor.alfen_energy_total updates
       ↓ (periodic sync)
   [HA Addon] Update session in SQLite
       ├── energy_kwh (running total)
       └── last_update

3. Charging Complete (car unplugged or stopped)
   [Wallbox] Status changes to "Idle" / "Stopped"
       ↓ (Modbus status register)
   [HA Integration] Status sensor updates
       ↓ (state change trigger)
   [HA Addon] Finalize session in SQLite
       ├── end_time
       ├── total_kwh (final)
       ├── duration (calculated)
       └── status: "completed"
       ↓ (immediate or batch)
   [HA Addon] POST to Dolibarr REST API
       ├── endpoint: /api/index.php/wallbox_sessions
       ├── headers: DOLAPIKEY: xxx
       └── payload: {rfid_hash, start_time, end_time, kwh, wallbox_id}
       ↓ (HTTP 200)
   [HA Addon] Mark session as "synced" in SQLite

4. Monthly Billing (Dolibarr Cron - Last Day of Month)
   [Dolibarr Cron] Trigger wallbox_billing job
       ↓
   [Dolibarr Module] Query llx_wallbox_sessions for current month
       ├── JOIN with user table on RFID hash
       ├── Calculate cost: SUM(kwh) × user.kwh_price
       └── Group by user/cost_center
       ↓
   [Dolibarr Module] Generate outputs:
       ├── Detailed charging list (per session)
       ├── Summary per user
       ├── Total costs
       └── PDF invoice
       ↓
   [Dolibarr] Attach to user account, email notification
```

### RFID Whitelist Check Flow

```
[HA Addon Startup]
    ↓
Load whitelist from /config/wallbox/whitelist.yaml
    ↓
Watch sensor.alfen_eve_tag_socket_1 for changes
    ↓
On new RFID detected:
    ├── Hash RFID (SHA256, not stored plaintext)
    ├── Check against whitelist[hash]
    ├── IF match → Allow charging (session starts)
    └── IF no match → Deny (optionally log attempt)
```

### Session Persistence (HA Restart Survival)

```
[HA Addon Startup]
    ↓
SQLite: SELECT * FROM sessions WHERE status = 'active'
    ↓
IF active session found:
    ├── Get current wallbox status via Modbus
    ├── IF still charging → Resume session (continue tracking)
    └── IF idle/stopped → Finalize session (treat as interrupted)
        └── Set end_time = NOW(), status = 'completed'
```

## Key Data Structures

### SQLite Table: `sessions` (Home Assistant)

```sql
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rfid_hash TEXT NOT NULL,          -- SHA256 hash, NEVER plaintext
    wallbox_id TEXT NOT NULL DEFAULT '001',
    start_time TEXT NOT NULL,            -- ISO 8601
    end_time TEXT,                       -- NULL if active
    energy_start_kwh REAL DEFAULT 0,
    energy_end_kwh REAL,
    total_kwh REAL,
    status TEXT NOT NULL DEFAULT 'active',  -- 'active', 'completed', 'synced'
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    synced_at TEXT                         -- NULL until sent to Dolibarr
);
```

### Dolibarr Table: `llx_wallbox_sessions`

```sql
CREATE TABLE llx_wallbox_sessions (
    rowid INTEGER PRIMARY KEY AUTO_INCREMENT,
    entity INTEGER NOT NULL DEFAULT 1,
    fk_user INTEGER,                       -- Links to llx_user.rowid
    rfid_hash TEXT NOT NULL,
    wallbox_id VARCHAR(64),
    start_time DATETIME NOT NULL,
    end_time DATETIME,
    total_kwh REAL NOT NULL,
    total_cost REAL,                        -- Calculated: kwh × user price
    status VARCHAR(32) DEFAULT 'pending',  -- 'pending', 'billed', 'disputed'
    billing_month VARCHAR(7),              -- '2026-05'
    invoice_id INTEGER,                     -- Links to llx_facture.rowid
    date_creation DATETIME,
    tms TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Dolibarr User Extension (added by module)

```sql
-- Add to llx_user or separate llx_wallbox_user_prefs
ALTER TABLE llx_user ADD wallbox_rfid_hash TEXT;
ALTER TABLE llx_user ADD wallbox_kwh_price REAL DEFAULT 0.30;  -- €/kWh
ALTER TABLE llx_user ADD wallbox_cost_center INTEGER;  -- fk to llx_societe
```

## Build Order (Dependencies)

### Phase 1: Foundation (No dependencies)
1. **HA Alfen Modbus Integration** (custom component)
   - Modbus TCP connection to wallbox (port 502, server address 1 or 2 for socket)
   - Read registers: RFID tag, energy meter, charging status
   - Expose sensors: `sensor.alfen_eve_tag_socket_1`, `sensor.alfen_energy_total`, `sensor.alfen_charging_status`
   - **Verification:** Sensors update in real-time, RFID shows correct hex value

2. **Dolibarr Wallbox Module Skeleton**
   - Module descriptor: `modWallbox.class.php` (numero = 104500, family = "financial")
   - Directory structure: `class/`, `sql/`, `core/triggers/`, `admin/`
   - Activation flow: creates `llx_wallbox_sessions` table
   - **Verification:** Module appears in Dolibarr module list, activates without errors

### Phase 2: Data Persistence (Depends on Phase 1)
3. **HA Wallbox Addon - Session Tracking**
   - SQLite database setup (`sessions.db`)
   - Automation: watch RFID sensor → whitelist check → start session
   - Automation: watch charging status → end session
   - Debounce RFID multiple triggers (ignore < 2s repeats)
   - **Verification:** Session appears in SQLite on RFID scan + plug

4. **Dolibarr User Extension**
   - Add RFID hash field to user card (tab in user view)
   - Add kWh price field (user-specific rate)
   - Add cost center selection (dropdown from third parties)
   - **Verification:** Admin can edit user → Wallbox tab shows, saves correctly

### Phase 3: Integration (Depends on Phase 2)
5. **HA Addon → Dolibarr API Client**
   - REST API client with DOLAPIKEY authentication
   - Retry logic (exponential backoff, store failed in SQLite)
   - Endpoint: `POST /api/index.php/wallbox_sessions`
   - JSON payload with session data
   - **Verification:** Completed session in HA → appears in Dolibarr `llx_wallbox_sessions`

6. **Dolibarr API Endpoint**
   - `api_wallbox_sessions.class.php` (RESTler service)
   - Accept POST: create session record
   - Validate RFID hash exists in user base
   - **Verification:** `curl` POST creates session in Dolibarr

### Phase 4: Billing (Depends on Phase 3)
7. **Dolibarr Monthly Billing Cron**
   - Scheduled job: last day of month, 23:59
   - Query: all unsynced sessions for billing month
   - Group by user, calculate totals
   - Generate detailed list (CSV/HTML)
   - **Verification:** Cron runs manually → produces correct billing data

8. **PDF Generation & Invoicing**
   - Use Dolibarr's built-in PDF generation (`pdf_wallbox.modules.php`)
   - Create draft invoice per user (using `facture.class.php`)
   - Link sessions to invoice (`invoice_id` in sessions table)
   - **Verification:** Billing cron → invoices appear in Dolibarr

### Phase 5: Hardening (Depends on Phase 4)
9. **HA Addon - Restart Recovery**
   - On startup, check SQLite for active sessions
   - Compare with wallbox status → resume or finalize
   - **Verification:** Start charging → restart HA → addon recovers session correctly

10. **Security & Audit**
    - Ensure RFID never logged in plaintext (only hashes)
    - Addon logs: no sensitive data
    - Dolibarr: audit trail for billing changes
    - **Verification:** Check logs for RFID hashes only, never hex IDs

## Patterns to Follow

### Pattern 1: HA Custom Integration (Modbus)
**What:** Python component that polls Modbus TCP registers, exposes sensors
**When:** Communicating with local hardware that supports Modbus
**Why:** Native HA integration, auto-discovery, entity registry, state persistence

```python
# From ThaStealth/alfen_modbus (HIGH confidence - verified on GitHub)
from homeassistant.components.modbus import ModbusHub

async def async_setup_entry(hass, config_entry):
    hub = ModbusHub(hass, config_entry.data["host"], 502)
    await hub.async_connect()
    
    # Register sensors for socket 1
    hass.data[DOMAIN][config_entry.entry_id] = hub
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
```

### Pattern 2: Dolibarr Module with Custom Table
**What:** PHP descriptor class, SQL install script, DAO class for CRUD
**When:** Adding new business objects to Dolibarr
**Why:** Standard Dolibarr pattern, works with permissions, hooks, triggers

```php
// From Dolibarr module development docs (HIGH confidence)
class modWallbox extends DolibarrModules {
    function __construct($db) {
        $this->numero = 104500;
        $this->rights_class = 'wallbox';
        $this->module_parts = ['db' => 1];
        $this->sql = ['/wallbox/sql/llx_wallbox_sessions.sql'];
    }
}
```

### Pattern 3: REST API Client with Retry
**What:** HTTP client that sends data to external API with exponential backoff
**When:** Integrating HA with external systems that may be temporarily unavailable
**Why:** Ensures data eventually reaches destination, survives network outages

```python
# Recommended pattern for HA addon
async def send_to_dolibarr(session_data, max_retries=5):
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{DOLIBARR_URL}/api/index.php/wallbox_sessions",
                    headers={"DOLAPIKEY": API_KEY},
                    json=session_data
                ) as resp:
                    if resp.status == 200:
                        return True
        except Exception as e:
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return False  # Mark for later retry
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Storing RFID in Plaintext
**What:** Saving RFID hex like "EFCD083E" directly in DB or logs
**Why bad:** GDPR violation, privacy risk if DB is compromised
**Instead:** Always hash (SHA256) before storage, log only hash prefixes for debugging

### Anti-Pattern 2: Using HA Integration for Business Logic
**What:** Putting session tracking, billing logic inside the HA custom component
**Why bad:** Integrations should only expose sensors/controls, not business logic
**Instead:** Use HA Addon (separate container) for session logic, integration only reads hardware

### Anti-Pattern 3: Polling Wallbox Too Frequently
**What:** Querying Modbus every second or faster
**Why bad:** Wallbox firmware may rate-limit, cause reconnection bugs (see known issues in alfen_modbus repo)
**Instead:** 20-30 second poll interval, adjust via integration options

### Anti-Pattern 4: Direct DB Access from HA to Dolibarr
**What:** HA addon connecting directly to Dolibarr's MySQL/PostgreSQL database
**Why bad:** Tight coupling, security risk, breaks on Dolibarr updates
**Instead:** Always use REST API (DOLAPIKEY auth), respects Dolibarr business logic

## Scalability Considerations

| Concern | At 1 Wallbox | At 10 Wallboxes | At 100 Wallboxes |
|---------|----------------|-------------------|--------------------|
| **HA Modbus Integration** | Single IP, 20s poll | 10 IPs, stagger polls | Use Modbus gateway, batch reads |
| **SQLite Sessions DB** | Single table, < 1000 rows/month | Still fine | Consider periodic archive to Dolibarr |
| **Dolibarr API** | Low traffic, sync after each session | Batch sync (hourly cron in HA) | Queue system (RabbitMQ/Redis) |
| **Billing Cron** | Seconds to run | < 1 minute | Parallel processing, chunk by wallbox |
| **User Management** | Manual RFID entry | Import CSV | LDAP/Active Directory sync |

## Integration Points Summary

| Interface | Technology | Auth | Data Format | Trigger |
|-----------|------------|------|------------|--------|
| Wallbox ↔ HA | Modbus TCP (port 502) | None (local network) | Registers (16-bit ints, floats) | Continuous poll (20s) |
| HA Addon ↔ SQLite | Python sqlite3 | File permissions | SQL | State changes |
| HA Addon ↔ Dolibarr | REST API (HTTPS) | DOLAPIKEY header | JSON | Session complete / batch |
| Dolibarr Module ↔ DB | PHP PDO (Dolibarr DB layer) | User permissions | SQL | Cron / API calls |
| Dolibarr Cron ↔ Billing | PHP (internal) | Cron security key | Internal function calls | Scheduled (monthly) |

## Sources

- **Alfen Modbus Documentation**: [alfen.com/media/1047/download](https://alfen.com/media/1047/download) (HIGH confidence - official PDF)
- **Alfen Modbus HA Integration**: [github.com/ThaStealth/alfen_modbus](https://github.com/ThaStealth/alfen_modbus) (HIGH confidence - existing code)
- **Alfen Wallbox RFID**: [alfen.com/media/1384/download](https://alfen.com/media/1384/download) (HIGH confidence - official manual)
- **Home Assistant Integration Type**: [Home Assistant Community](https://community.home-assistant.io/t/difference-between-integration-add-on/227415) (HIGH confidence - official forum)
- **Dolibarr Module Structure**: [wiki.dolibarr.org](https://wiki.dolibarr.org/index.php/Module_development) (HIGH confidence - official wiki)
- **Dolibarr REST API**: [github.com/Dolibarr/dolibarr/blob/develop/htdocs/api/README.md](https://github.com/Dolibarr/dolibarr/blob/develop/htdocs/api/README.md) (HIGH confidence - official docs)
- **Dolibarr Cron Jobs**: [wiki.dolibarr.org](https://wiki.dolibarr.org/index.php/Module_Scheduled_jobs) (HIGH confidence - official wiki)
- **EV Charging Session Architecture**: [simplico.net](https://simplico.net/2025/06/27/building-a-scalable-ev-charging-backend-for-operators-developers-and-innovators/) (MEDIUM confidence - industry article)
