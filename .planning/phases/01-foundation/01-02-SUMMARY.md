---
phase: 01-foundation
plan: 02
subsystem: dolibarr, module
tags: [dolibarr, wallboxbilling, php, sql, billing, permissions, german]

# Dependency graph
requires:
  - phase: none
    provides: Foundation for Dolibarr module
provides:
  - Dolibarr module skeleton (wallboxbilling) with descriptor
  - llx_wallboxbilling_sessions database table with indexes
  - Three permissions: wallboxbilling.user, wallboxbilling.admin, wallboxbilling.billing
  - Four frontend pages: admin.php, index.php, card.php, bill.php
  - German language file (de_DE) with 19 translations
affects: [phase-2, phase-4, billing, user-management]

# Tech tracking
tech-stack:
  added: [Dolibarr 21.x-22.x, PHP 8.1+, MariaDB/MySQL]
  patterns: [Dolibarr module descriptor pattern, SQL table with indexes, Permission-based access control]

key-files:
  created:
    - Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php
    - Dolibarr/htdocs/custom/wallboxbilling/sql/llx_wallboxbilling_sessions.sql
    - Dolibarr/htdocs/custom/wallboxbilling/admin.php
    - Dolibarr/htdocs/custom/wallboxbilling/index.php
    - Dolibarr/htdocs/custom/wallboxbilling/card.php
    - Dolibarr/htdocs/custom/wallboxbilling/bill.php
    - Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang
    - Dolibarr/htdocs/custom/wallboxbilling/img/wallbox.png
  modified: []

key-decisions:
  - "Module name: wallboxbilling (not 'wallbox' or 'evcharging') for billing focus"
  - "Three permissions: user (read), admin (manage all), billing (create invoices) following SEC-04"
  - "German language (de_DE) from start following AGENTS.md language requirement"
  - "SHA-256 hash field (rfid_hash VARCHAR(128)) prepared for SEC-02"
  - "Four indexes on sessions table for performance (DB-02 preparation)"

patterns-established:
  - "Dolibarr module descriptor pattern with modWallboxbilling class extending DolibarrModules"
  - "Permission array structure with ID, description, rights, and key"
  - "Frontend pages using llxHeader/llxFooter with language translation"

requirements-completed: [DB-03, SEC-04]

# Metrics
duration: 5 min
completed: 2026-05-04
---

# Phase 1: Foundation - Plan 02: Dolibarr Module Skeleton Summary

**Dolibarr module (wallboxbilling) with descriptor, llx_wallboxbilling_sessions table, 3 permissions (SEC-04), 4 frontend pages, and German language support**

## Performance

- **Duration:** 5 min
- **Started:** 2026-05-04T14:56:03Z
- **Completed:** 2026-05-04T15:01:19Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments

- Dolibarr module descriptor (modWallboxbilling.class.php) with proper constructor and install/uninstall methods
- llx_wallboxbilling_sessions SQL table with all required fields for charging sessions (user_id, rfid_hash, wallbox_id, kWh, price, status)
- Four database indexes for performance (rfid_hash, user_id, start_time, status)
- Three permissions defined: wallboxbilling.user (read own), wallboxbilling.admin (manage all), wallboxbilling.billing (create invoices)
- Four frontend pages created: admin.php (configuration + permissions display), index.php (sessions list skeleton), card.php (user-RFID link skeleton), bill.php (billing preview skeleton)
- German language file (wallboxbilling.lang) with 19 translations
- Wallbox icon placeholder (wallbox.png) in img/ directory

## Task Commits

Each task was committed atomically:

1. **Task 1: Module descriptor and SQL table** - `c20ae30` (feat)
2. **Task 2: Frontend pages, permissions, and German language** - `dddcb25` (feat)

**Plan metadata:** `pending` (orchestrator will commit SUMMARY.md with STATE.md and ROADMAP.md)

_Note: Standard plan with 2 tasks, each with one commit._

## Files Created/Modified

- `Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php` - Module descriptor with permissions
- `Dolibarr/htdocs/custom/wallboxbilling/sql/llx_wallboxbilling_sessions.sql` - Database table with indexes
- `Dolibarr/htdocs/custom/wallboxbilling/admin.php` - Admin configuration page with permission check
- `Dolibarr/htdocs/custom/wallboxbilling/index.php` - Sessions list page (skeleton)
- `Dolibarr/htdocs/custom/wallboxbilling/card.php` - User-RFID link page (skeleton)
- `Dolibarr/htdocs/custom/wallboxbilling/bill.php` - Billing preview page with permission check
- `Dolibarr/htdocs/custom/wallboxbilling/langs/de_DE/wallboxbilling.lang` - German translations
- `Dolibarr/htdocs/custom/wallboxbilling/img/wallbox.png` - Icon placeholder

## Decisions Made

- Module name is "wallboxbilling" to emphasize billing focus (not just "wallbox")
- Three permissions follow SEC-04: .user (read), .admin (manage), .billing (invoices)
- German language (de_DE) implemented from start per AGENTS.md
- rfid_hash field is VARCHAR(128) to accommodate SHA-256 hashes (64 hex chars + margin)
- Table includes wallbox_id field for multi-wallbox extensibility (EXT-01 preparation)
- Four indexes created on sessions table for query performance (DB-02 preparation)
- Frontend pages are skeletons (minimal content) as this is Phase 1 foundation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dolibarr module skeleton is ready for Phase 2 (Session Management & RFID Hashing)
- Database table structure is prepared for DB-01 (session persistence)
- Permission structure is in place for user management (USR-02)
- German language foundation established for all future UI work
- SHA-256 hash field (rfid_hash) ready for SEC-02 implementation

---
*Phase: 01-foundation*
*Completed: 2026-05-04*

## Self-Check: PASSED

All key-files.created exist on disk: ✓
Git commits found for 01-02: ✓ (c20ae30, dddcb25)
Plan verification commands all pass: ✓
