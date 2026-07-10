---
phase: 08-retry-dead-letter
plan: 03
subsystem: ui
tags: [php, dolibarr, curl, csrf, xss-prevention, dead-letter, retry]

# Dependency graph
requires:
  - phase: 08-01
    provides: dead_letter SQLite table + HA-Addon endpoints /session/retry and /dead-letter/list
  - phase: 06-monitoring-status
    provides: admin.php 3-tab structure (status, config, rfid) that this plan extends

provides:
  - "Dolibarr admin.php 4th tab 'Fehlgeschlagen' (deadletter) with cURL-backed dead-letter table"
  - "retry_dead_letter action handler: checkToken(), GETPOST int coercion, cURL POST to /session/retry, PRG redirect"
  - "deadletter tab: cURL GET /dead-letter/list, 6-column table, per-row Retry form with CSRF, empty + unreachable states"
  - "German lang keys for dead-letter UI (12 keys added to langs/de_DE/wallboxbilling.lang)"

affects:
  - 08-checker
  - future-admin-tabs

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PRG (Post-Redirect-Get) pattern extended to deadletter tab"
    - "cURL GET for list fetch + cURL POST for retry action (mirroring stop_session pattern)"
    - "error_msg truncation: htmlspecialchars(mb_substr($raw, 0, 80), ENT_QUOTES, 'UTF-8') + '...' if strlen > 80"

key-files:
  created: []
  modified:
    - "Dolibarr/htdocs/custom/wallboxbilling/admin.php"
    - "Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang"

key-decisions:
  - "error_msg column uses red inline style (color:red) matching Phase 6 error badge pattern — no status badge needed since all listed entries are pending"
  - "deadletter tab cURL uses $dl_ variable prefix to avoid naming collision with existing $ch in status tab (no collision in practice since tabs are mutually exclusive, but prefix improves readability)"
  - "WallboxHANotConfigured lang key added for empty HA_URL state — consistent with status tab unconfigured handling"

patterns-established:
  - "Dead-letter tab pattern: cURL GET to list endpoint → json_decode → table render with per-row action form"
  - "Retry action: same cURL POST shape as stop_session but with success/error branching on resp_data['success'] from HA JSON"

requirements-completed:
  - RET-02

# Metrics
duration: 22min
completed: 2026-06-23
---

# Phase 08 Plan 03: Dolibarr Dead-letter Tab Summary

**4th admin tab 'Fehlgeschlagen' added to admin.php with cURL-backed dead-letter table, per-row Wiederholen retry form, CSRF protection, XSS-safe error_msg rendering, and PRG action handler for /session/retry**

## Performance

- **Duration:** 22 min
- **Started:** 2026-06-23T14:50:00Z
- **Completed:** 2026-06-23T15:12:40Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Added 4th tab 'Fehlgeschlagen' (key: deadletter) to tab array — admin.php now has 4-tab structure
- Implemented retry_dead_letter action handler: checkToken() CSRF validation, GETPOST int coercion for dead_letter_id, cURL POST to /session/retry with 4s timeout, success/failure setEventMessages branching, PRG redirect to ?tab=deadletter
- Implemented deadletter tab content: cURL GET to /dead-letter/list, 6-column table (Erstellt, Wallbox-ID, kWh, Fehler, Versuche, Aktion), per-row form with newToken(), empty state, HA unreachable state — rfid_hash never printed
- Added 12 German lang keys to langs/de_DE/wallboxbilling.lang

## Task Commits

1. **Task 1: admin.php — 4th tab, retry_dead_letter action handler, deadletter tab content** - `1f6f227` (feat)

## Files Created/Modified

- `Dolibarr/htdocs/custom/wallboxbilling/admin.php` - 4th tab entry, retry_dead_letter action handler, deadletter tab content block (141 lines added)
- `Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang` - 12 new German lang keys for dead-letter UI

## Decisions Made

- Used `$dl_` prefix for deadletter cURL variables to visually separate from existing `$ch` health check in status tab
- Added `WallboxHANotConfigured` lang key (not in plan spec) for empty HA_URL state — consistent with existing status tab pattern. Tracked as Rule 2 (missing critical functionality for unconfigured state).
- Kept error_msg column with `style="color:red"` inline for all pending entries — no status badge column needed since only pending entries are ever shown in the dead-letter table

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added WallboxHANotConfigured lang key**
- **Found during:** Task 1 (deadletter tab content)
- **Issue:** The unconfigured state path (`if (empty($ha_url))`) uses `$langs->trans('WallboxHANotConfigured')` which was not in the plan's lang key list but is needed for correct fallback display
- **Fix:** Added `WallboxHANotConfigured=HA-Addon nicht konfiguriert (WALLBOXBILLING_HA_URL)` to the German lang file alongside the other new keys
- **Files modified:** langs/de_DE/wallboxbilling.lang
- **Verification:** Key present in lang file, referenced in admin.php unconfigured state branch
- **Committed in:** 1f6f227 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary for correct display when HA_URL not configured. No scope creep.

## Issues Encountered

None — plan executed cleanly. All 15 acceptance criteria grep checks pass.

## Known Stubs

None — all data is fetched live from HA-Addon /dead-letter/list via cURL. No hardcoded placeholder data.

## Threat Flags

No new threat surface introduced beyond what was analyzed in the plan's STRIDE threat register (T-08-01 through T-08-06). All mitigations implemented:

- T-08-01: `GETPOST('dead_letter_id', 'int')` + `$dead_letter_id > 0` check
- T-08-02: `checkToken()` in handler + `newToken()` in each form
- T-08-03: rfid_hash never printed (grep confirmed 0 instances)
- T-08-04: `htmlspecialchars(mb_substr($err_raw, 0, 80), ENT_QUOTES, 'UTF-8')` on error_msg
- T-08-06: cURL URL sourced from `getDolGlobalString('WALLBOXBILLING_HA_URL', '')` — admin-configured, not user input

## User Setup Required

None — this plan extends existing admin.php. The HA_URL configuration from Phase 6 is sufficient.

## Next Phase Readiness

- Dolibarr side of RET-02 complete
- Requires Plan 08-01 (HA-Addon dead_letter table + Python methods) and Plan 08-02 (HA-Addon HTTP endpoints /session/retry and /dead-letter/list) for end-to-end operation
- Ready for integration testing once Plans 08-01 and 08-02 are merged

---

## Self-Check: PASSED

- `Dolibarr/htdocs/custom/wallboxbilling/admin.php` — FOUND (modified)
- `Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang` — FOUND (modified)
- Commit `1f6f227` — FOUND

---
*Phase: 08-retry-dead-letter*
*Completed: 2026-06-23*
