---
phase: "06-monitoring-status"
plan: "01"
subsystem: "Dolibarr Module DB Migration"
tags: [db-migration, mysql, dolibarr, monitoring, schema]
dependency_graph:
  requires: []
  provides: [llx_wallbox_sessions.upload_status, llx_wallbox_sessions.upload_error, llx_wallbox_sessions.uploaded_at]
  affects: [06-02-PLAN, 06-03-PLAN]
tech_stack:
  added: []
  patterns: [idempotent-alter-table, show-columns-guard, dolibarr-module-upgrade]
key_files:
  created: []
  modified:
    - Dolibarr/htdocs/custom/wallboxbilling/core/modules/modWallboxbilling.class.php
decisions:
  - "Used $cols_to_add array + foreach loop for SHOW COLUMNS guard instead of three separate blocks — DRY, easier to extend"
  - "Added migration to both install() and upgrade() — existing installations use ALTER TABLE, new installations get columns in CREATE TABLE"
metrics:
  duration: "106s"
  completed: "2026-06-21"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
requirements:
  - MON-02
  - MON-03
---

# Phase 06 Plan 01: DB Schema Migration (upload_status/upload_error/uploaded_at) Summary

## One-liner

Added three monitoring columns to `llx_wallbox_sessions` via idempotent `SHOW COLUMNS` guards in both `upgrade()` and `install()` of `modWallboxbilling.class.php`.

## What Was Built

Extended `modWallboxbilling.class.php` with the DB schema foundation required by the Monitoring Status-Tab (Plans 02 and 03).

### Changes Made

**`init()` method — CREATE TABLE:**
Added three new columns after `transmitted_at` in the `llx_wallbox_sessions` CREATE TABLE:
- `upload_status ENUM('pending','ok','error') NOT NULL DEFAULT 'pending'`
- `upload_error TEXT NULL`
- `uploaded_at DATETIME NULL`

**`install()` method — CREATE TABLE + ALTER TABLE guard:**
Same columns added to the CREATE TABLE block, plus an idempotent `$cols_to_add` foreach with `SHOW COLUMNS` guard for ALTER TABLE (covers upgrades from a state where the table existed without these columns).

**`upgrade()` method — ALTER TABLE blocks:**
Added `$cols_to_add` array with three ALTER TABLE statements, each protected by a `SHOW COLUMNS FROM llx_wallbox_sessions LIKE '$col'` idempotency check. Failed ALTERs are logged via `dol_syslog(..., LOG_ERR)`.

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | b86ba65 | feat(06-01): add upload_status/upload_error/uploaded_at DB migration |

## Acceptance Criteria Met

| Criterion | Status |
|-----------|--------|
| `upload_status ENUM` in CREATE TABLE (install + init) | 2 occurrences |
| `upload_error` in file | 8 occurrences |
| `uploaded_at` in file | 6 occurrences |
| SHOW COLUMNS guard via `$col` variable loop | Present in both install() and upgrade() |
| `NOT NULL DEFAULT 'pending'` | 4 occurrences |
| `dol_syslog.*upgrade SQL error` | 2 occurrences |
| PHP syntax | No PHP available locally; file structure verified manually |

## Deviations from Plan

### Minor Implementation Variation (not a Rule deviation)

**SHOW COLUMNS literal grep:** The plan's acceptance criterion checked for a literal `SHOW COLUMNS FROM llx_wallbox_sessions LIKE 'upload_status'` string. The implementation uses a DRY `$cols_to_add` array + foreach loop where `$col` iterates over `'upload_status'`, `'upload_error'`, `'uploaded_at'`. At runtime this produces equivalent SQL. The grep criterion returns 0 because the column name is a PHP variable, not a literal string — but the guard is fully present and functionally correct.

## Threat Model Coverage

| Threat | Mitigation Applied |
|--------|-------------------|
| T-06-01: Double ALTER TABLE (Tampering) | SHOW COLUMNS idempotency guard in both install() and upgrade(); dol_syslog on failure |
| T-06-02: upload_error TEXT DoS | Accepted — TEXT max ~65k, bounded by api_client error strings |

## Known Stubs

None — this plan only modifies schema migration code, no UI rendering or data-flow stubs.

## Threat Flags

None — no new network endpoints or trust boundaries introduced.

## Self-Check

- [x] `b86ba65` commit exists in git log
- [x] `modWallboxbilling.class.php` modified with all three column definitions
- [x] upload_status ENUM appears in both CREATE TABLE blocks (init + install)
- [x] ALTER TABLE blocks with SHOW COLUMNS guards present in both upgrade() and install()
- [x] dol_syslog error logging present in both guard loops
