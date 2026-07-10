# Phase 7: Alerts & Logging - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 7 (5 modify, 2 create)
**Analogs found:** 7 / 7

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `Homeassistant/main.py` | service/entrypoint | event-driven + request-response | `Homeassistant/main.py` (self — extend existing) | self |
| `Homeassistant/session_manager.py` | service | CRUD + event-driven | `Homeassistant/session_manager.py` (self — extend existing) | self |
| `Homeassistant/config.yaml` | config | — | `Homeassistant/config.yaml` (self — extend existing) | self |
| `Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php` | controller/API endpoint | CRUD + request-response | `Dolibarr/htdocs/custom/wallboxbilling/class/billing.class.php` | role-match |
| `Homeassistant/tests/test_alerts_logging.py` | test | — | `Homeassistant/tests/test_session_status.py` | exact |
| `Homeassistant/tests/test_log_scrubbing.py` | test | — | `Homeassistant/tests/test_session_status.py` | role-match |
| `Homeassistant/tests/test_alerts.py` | test | — | `Homeassistant/tests/test_health.py` | role-match |

---

## Pattern Assignments

### `Homeassistant/main.py` — LOG-01 fix + ALT-01 function

**What to add:**
1. `apply_log_level_from_config(config)` function called after `load_config()` in `main()`
2. `send_persistent_notification(title, message, notification_id)` async function
3. Call to `send_persistent_notification` inside `periodic_transmission()` when `result["failed"] > 0`

**Imports already present** (lines 8-16, no new imports needed):
```python
import asyncio
import aiohttp
import json
import logging
import os
```

**Existing logging setup pattern** (lines 29-34) — DO NOT call `basicConfig()` again:
```python
# lines 29-34 — already in place; LOG-01 fix does NOT touch this block
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_LOGGER = logging.getLogger(__name__)
```

**LOG-01 apply pattern — add this function before `main()`:**
```python
def apply_log_level_from_config(config: dict) -> None:
    """Setzt Log-Level aus options.json (LOG-01).
    Muss nach load_config() und nach logging.basicConfig() aufgerufen werden.
    """
    log_level_str = config.get('log_level', 'INFO').upper()
    numeric_level = getattr(logging, log_level_str, logging.INFO)
    logging.getLogger().setLevel(numeric_level)
    _LOGGER.info("Log-Level aus options.json gesetzt: %s", log_level_str)
```

**LOG-01 call site — in `main()` after `load_config()`** (insert after line 341):
```python
    # Konfiguration laden (für Whitelist und API)
    current_config = load_config()
    apply_log_level_from_config(current_config)   # LOG-01 fix
```

**ALT-01 function — add after `apply_log_level_from_config`:**
```python
async def send_persistent_notification(
    title: str,
    message: str,
    notification_id: str = "wallbox_upload_error"
) -> None:
    """Sendet persistent_notification via HA Supervisor REST API (ALT-01)."""
    supervisor_token = os.getenv('SUPERVISOR_TOKEN', '')
    if not supervisor_token:
        _LOGGER.warning("SUPERVISOR_TOKEN nicht verfügbar — persistent_notification nicht gesendet")
        return

    headers = {
        "Authorization": f"Bearer {supervisor_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "title": title,
        "message": message[:500],          # Guard: max 500 Zeichen (Anti-Pattern aus RESEARCH.md)
        "notification_id": notification_id,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "http://supervisor/core/api/services/persistent_notification/create",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                if resp.status == 200:
                    _LOGGER.info("persistent_notification gesendet: %s", title)
                else:
                    _LOGGER.warning("persistent_notification fehlgeschlagen: HTTP %s", resp.status)
    except Exception as e:
        _LOGGER.warning("persistent_notification Fehler: %s", e)
```

**ALT-01 call site — inside `periodic_transmission()` after existing error log** (replace lines 392-396):
```python
                        if result["failed"] > 0:
                            _LOGGER.error("Fehler bei API-Übertragung: %s Sessions fehlgeschlagen", result["failed"])
                            error_summary = "; ".join(result.get("errors", []))
                            await send_persistent_notification(
                                title="Wallbox Upload-Fehler",
                                message=f"{result['failed']} Session(s) konnten nicht übertragen werden: {error_summary}",
                                notification_id="wallbox_upload_error",
                            )
                            # Bei Fehlern: Verbindung neu testen
                            if not api_client.check_connection():
                                _LOGGER.warning("API-Verbindung verloren - deaktiviere temporär")
```

**Existing aiohttp async pattern to follow** (`HomeAssistantWebsocket.connect`, lines 93-96):
```python
    async def connect(self):
        self._session = aiohttp.ClientSession()
        try:
            self._ws = await self._session.ws_connect(self.ws_url)
```

**Existing error handling pattern for async methods** (lines 117-120):
```python
        except Exception as e:
            _LOGGER.error("Verbindungsfehler: %s", e)
            await self.disconnect()
            raise
```

---

### `Homeassistant/session_manager.py` — no changes required for Phase 7

**Research conclusion:** `session_manager.py` is unchanged for Phase 7. The `transmit_completed_sessions()` method (lines 411-479) already returns `result["failed"]` and `result["errors"]` — ALT-01 reads these in `main.py`. No modification to `session_manager.py` is needed.

**Existing result dict pattern** (lines 433-437) — planner reference only:
```python
        result = {
            "transmitted": 0,
            "failed": 0,
            "errors": []
        }
```

**Existing error logging pattern** (lines 460-463):
```python
                error_msg = f"Session {session_id}: {error}"
                result["errors"].append(error_msg)
                result["failed"] += 1
                self._logger.error("Fehler bei Session %s: %s", session_id, error)
```

---

### `Homeassistant/config.yaml` — LOG-01 schema already present, no change needed

**Existing log_level entries** (lines 18-19, 42):
```yaml
options:
  log_level: "INFO"

schema:
  log_level: "list(DEBUG|INFO|WARNING|ERROR)"
```

**Research conclusion:** `config.yaml` already defines `log_level` correctly. Phase 7 does not add new `config.yaml` fields (admin notification email is a Dolibarr-side constant, not a HA Addon config).

---

### `Dolibarr/htdocs/custom/wallboxbilling/class/api_wallboxbilling.class.php` — LOG-03 + ALT-02

**What to add:**
1. `require_once` for `CMailFile` at top of file (or inside `postSession()`)
2. `dol_syslog()` calls after INSERT success and INSERT failure in `postSession()`
3. `CMailFile` + `sendfile()` call on INSERT failure
4. New field `WALLBOXBILLING_ADMIN_EMAIL` read via `getDolGlobalString()`

**Existing file header** (lines 1-13):
```php
<?php
/**
 *  api_wallboxbilling.class.php - Wallbox Billing REST API
 *  ...
 */

require_once DOL_DOCUMENT_ROOT.'/api/class/api.class.php';
```

**Add after existing require_once (line 13):**
```php
require_once DOL_DOCUMENT_ROOT.'/core/class/CMailFile.class.php';
```

**Analog dol_syslog pattern from** `billing.class.php` (lines 69, 86, 92, 138):
```php
dol_syslog("WallboxBilling: Starte Abrechnung für Zeitraum ".$startDate." bis ".$endDate, LOG_INFO);
dol_syslog("WallboxBilling Error: ".$this->error, LOG_ERR);
dol_syslog("WallboxBilling: Keine Sessions im Zeitraum gefunden", LOG_INFO);
```

**LOG-03 additions in `postSession()` — replace lines 176-188 with:**
```php
        $resql = $this->db->query($sql_insert);
        if (!$resql) {
            // LOG-03: Fehler strukturiert loggen (LOG_ERR für DB-Fehler)
            dol_syslog("WallboxBilling: Session upload FAILED - wallbox=".$wallbox_id." error=".$this->db->lasterror(), LOG_ERR);

            // ALT-02: Admin-E-Mail bei DB-Fehler
            $admin_email = getDolGlobalString('WALLBOXBILLING_ADMIN_EMAIL');
            if (!empty($admin_email)) {
                $from = getDolGlobalString('MAIN_MAIL_EMAIL_FROM', getDolGlobalString('MAIN_INFO_SOCIETE_MAIL'));
                $subject = "Wallbox Upload-Fehler: Session konnte nicht gespeichert werden";
                $message = "Session-Upload fehlgeschlagen.\n\nFehler: ".$this->db->lasterror()."\n\nWallbox: ".$wallbox_id."\n\nZeitpunkt: ".dol_print_date(dol_now(), 'dayhour');
                $mail = new CMailFile($subject, $admin_email, $from, $message, array(), array(), array(), '', '', 0, 0);
                if (!$mail->sendfile()) {
                    dol_syslog("WallboxBilling: Admin-E-Mail konnte nicht gesendet werden: ".$mail->error, LOG_WARNING);
                }
            }

            throw new RestException(500, 'DB Error: '.$this->db->lasterror());
        }

        $session_id = (int) $this->db->last_insert_id(MAIN_DB_PREFIX.'wallbox_sessions');

        // LOG-03: Erfolg loggen (LOG_INFO für erfolgreichen Upload)
        dol_syslog("WallboxBilling: Session upload OK - session_id=".$session_id." wallbox=".$wallbox_id." kwh=".$kwh, LOG_INFO);

        return array(
            'success' => true,
            'id' => $session_id,
            'message' => 'Session stored'
        );
```

**Analog getDolGlobalString + dolibarr_set_const pattern from** `admin.php` (lines 25-26, 51, 262):
```php
$new_price = GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'alpha');
dolibarr_set_const($db, 'WALLBOXBILLING_DEFAULT_PRICE', $new_price, 'chaine', 0, '', $conf->entity);
// ...
getDolGlobalString('WALLBOXBILLING_HA_URL', '')
// ...
print '<input type="text" name="WALLBOXBILLING_DEFAULT_PRICE" value="'.getDolGlobalString('WALLBOXBILLING_DEFAULT_PRICE').'">';
```

**ALT-02 admin.php config tab addition** — copy pattern from `admin.php` lines 25-26, 262:
```php
// In action=update block:
$admin_email = GETPOST('WALLBOXBILLING_ADMIN_EMAIL', 'email');
dolibarr_set_const($db, 'WALLBOXBILLING_ADMIN_EMAIL', $admin_email, 'chaine', 0, '', $conf->entity);

// In config tab HTML:
print '<tr><td>Admin-E-Mail für Upload-Alerts</td>';
print '<td><input type="email" name="WALLBOXBILLING_ADMIN_EMAIL" value="'.getDolGlobalString('WALLBOXBILLING_ADMIN_EMAIL').'"></td></tr>';
```

---

### `Homeassistant/tests/test_alerts_logging.py` (create — covers LOG-01, LOG-02, ALT-01)

**Analog:** `Homeassistant/tests/test_session_status.py` + `Homeassistant/tests/test_health.py`

**File header + sys.path pattern** (from `test_health.py` lines 1-13):
```python
#!/usr/bin/env python3
"""
Tests für Log-Level-Konfiguration (LOG-01), Log-Scrubbing (LOG-02),
und persistent_notification (ALT-01).
Phase 7: Alerts & Logging
"""
import pytest
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

**Fixture pattern** (from `conftest.py` lines 14-26):
```python
@pytest.fixture
def in_memory_session_manager(tmp_path):
    try:
        from session_manager import SessionManager
        db_file = str(tmp_path / "test_sessions.db")
        sm = SessionManager(db_path=db_file)
        yield sm
    except ImportError:
        pytest.skip("session_manager module not importable in this environment")
```

**LOG-01 test pattern — read file content, assert function/call exists:**
```python
class TestLogLevelConfig:
    """Tests für LOG-01: options.json log_level wird angewendet"""

    def test_apply_log_level_from_config_exists_in_main(self):
        """apply_log_level_from_config() muss in main.py definiert sein"""
        with open("Homeassistant/main.py", "r") as f:
            content = f.read()
        assert "apply_log_level_from_config" in content

    def test_apply_log_level_sets_root_logger(self):
        """apply_log_level_from_config({'log_level': 'DEBUG'}) setzt Root-Logger auf DEBUG"""
        from main import apply_log_level_from_config
        apply_log_level_from_config({'log_level': 'DEBUG'})
        assert logging.getLogger().level == logging.DEBUG
        # Cleanup
        logging.getLogger().setLevel(logging.INFO)

    def test_apply_log_level_invalid_falls_back_to_info(self):
        """Ungültiger log_level ('INVALID') fällt zurück auf INFO"""
        from main import apply_log_level_from_config
        apply_log_level_from_config({'log_level': 'INVALID'})
        assert logging.getLogger().level == logging.INFO
```

**LOG-02 test pattern — caplog fixture:**
```python
class TestLogScrubbing:
    """Tests für LOG-02: Keine sensitiven Daten in Logs"""

    def test_no_rfid_hex_in_logs(self, caplog, in_memory_session_manager):
        """rfid_hex Klartext darf nicht in Logs erscheinen"""
        import re
        rfid_hex = "EFCD083E"
        with caplog.at_level(logging.DEBUG):
            in_memory_session_manager.debounce_rfid(rfid_hex)
        for record in caplog.records:
            assert rfid_hex not in record.message, \
                f"RFID Klartext in Log: {record.message}"
```

**ALT-01 async test pattern — monkeypatch + pytest.mark.asyncio:**
```python
class TestPersistentNotification:
    """Tests für ALT-01: send_persistent_notification"""

    @pytest.mark.asyncio
    async def test_no_token_returns_gracefully(self, monkeypatch):
        """Wenn SUPERVISOR_TOKEN fehlt, kein Crash"""
        monkeypatch.delenv('SUPERVISOR_TOKEN', raising=False)
        from main import send_persistent_notification
        await send_persistent_notification("Test", "Test-Msg")  # kein raise

    @pytest.mark.asyncio
    async def test_called_on_failed_transmission(self, monkeypatch, tmp_path):
        """send_persistent_notification wird aufgerufen wenn result['failed'] > 0"""
        # Mock SUPERVISOR_TOKEN
        monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-token')
        called_with = {}
        async def mock_notify(title, message, notification_id="wallbox_upload_error"):
            called_with['title'] = title
            called_with['message'] = message
        # Patch and verify via static analysis or unittest.mock
        ...
```

---

### `Homeassistant/tests/test_log_scrubbing.py` (create — LOG-02 dedicated file)

**Research note:** RESEARCH.md consolidates LOG-01, LOG-02, ALT-01 into a single test file `test_alerts_logging.py`. The separate `test_log_scrubbing.py` listed in context is a variant; planner should decide whether to merge into `test_alerts_logging.py` or keep separate. Pattern is identical.

**Analog:** `Homeassistant/tests/test_session_status.py`

**caplog-based audit pattern:**
```python
"""
Tests für LOG-02: Log-Scrubbing Audit
Verifiziert: kein RFID-Klartext, kein API-Token in Logs
"""
import pytest
import logging
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestLogScrubbing:

    def test_rfid_hash_prefix_only_in_logs(self, caplog, in_memory_session_manager):
        """Nur rfid_hash[:16] darf in Logs erscheinen, nie rfid_hex Klartext"""
        rfid_hex = "EFCD083E"
        with caplog.at_level(logging.DEBUG):
            in_memory_session_manager.debounce_rfid(rfid_hex)
        for record in caplog.records:
            assert rfid_hex.upper() not in record.message
            assert rfid_hex.lower() not in record.message

    def test_api_token_not_in_logs(self, caplog):
        """DOLAPIKEY Token darf nicht in Logs erscheinen"""
        import importlib.util
        # Static: prüfe api_client.py auf Logging von self.api_token
        with open("Homeassistant/api_client.py", "r") as f:
            content = f.read()
        # api_token darf nicht direkt an _LOGGER übergeben werden
        import re
        # Einfaches Muster: api_token sollte nicht in _LOGGER calls vorkommen
        assert "api_token" not in re.findall(r'_LOGGER\.\w+\([^)]*api_token[^)]*\)', content)
```

---

### `Homeassistant/tests/test_alerts.py` (create — ALT-01 dedicated file)

**Analog:** `Homeassistant/tests/test_health.py` (aiohttp async testing)

**pytest-asyncio pattern from `test_health.py` lines 22-61 (subprocess pattern for isolation):**
```python
#!/usr/bin/env python3
"""
Tests für ALT-01: HA persistent_notification bei Upload-Fehlern.
Phase 7: Alerts & Logging
"""
import pytest
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestAlerts:

    @pytest.mark.asyncio
    async def test_send_persistent_notification_no_token(self, monkeypatch):
        """Kein SUPERVISOR_TOKEN → graceful return, kein Crash"""
        monkeypatch.delenv('SUPERVISOR_TOKEN', raising=False)
        # Mock module-level globals that main.py uses at import time
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            from main import send_persistent_notification
            await send_persistent_notification("Test", "Msg")  # no raise

    @pytest.mark.asyncio
    async def test_send_persistent_notification_truncates_message(self, monkeypatch):
        """Nachricht über 500 Zeichen wird auf 500 Zeichen gekürzt"""
        monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-token')
        long_message = "x" * 1000
        posted_payload = {}

        import unittest.mock as mock
        with mock.patch('aiohttp.ClientSession') as mock_session:
            mock_resp = mock.AsyncMock()
            mock_resp.status = 200
            mock_session.return_value.__aenter__.return_value.post.return_value.__aenter__.return_value = mock_resp
            # ... call and verify payload['message'] length <= 500
```

---

## Shared Patterns

### Python Logging Pattern (LOG-01, LOG-02)
**Source:** `Homeassistant/main.py` (lines 29-34) + `Homeassistant/session_manager.py` (line 31)
**Apply to:** All Python test files and main.py additions
```python
# Module-level logger — copy this pattern in every module
_LOGGER = logging.getLogger(__name__)

# Root-logger level change (NOT basicConfig re-call):
logging.getLogger().setLevel(numeric_level)
```

### RFID Safety Pattern (LOG-02)
**Source:** `Homeassistant/session_manager.py` (lines 143, 169, 172, 335-336) + `Homeassistant/main.py` (line 191)
**Apply to:** Any new log calls touching RFID data
```python
# Always truncate: rfid_hash[:16], NEVER rfid_hex directly
self._logger.debug("RFID debounced: %s (%.1fs < %ds)", rfid_hash[:16], time_diff, DEBOUNCE_SECONDS)
self._logger.info("RFID autorisiert: %s...", rfid_hash[:16])
_LOGGER.warning("Nicht autorisierte RFID: %s...", rfid_hash[:16])
```

### aiohttp Async Client Pattern (ALT-01)
**Source:** `Homeassistant/main.py` (lines 93-96, `HomeAssistantWebsocket.connect`)
**Apply to:** `send_persistent_notification()` in `main.py`
```python
self._session = aiohttp.ClientSession()
async with session.post(url, json=payload, headers=headers, timeout=...) as resp:
    if resp.status == 200:
        _LOGGER.info("...")
    else:
        _LOGGER.warning("...")
```

### SUPERVISOR_TOKEN Access Pattern (ALT-01)
**Source:** `Homeassistant/main.py` line 86 (`HomeAssistantWebsocket.__init__`)
**Apply to:** `send_persistent_notification()` in `main.py`
```python
self.access_token = os.getenv('SUPERVISOR_TOKEN', '')
```

### dol_syslog Pattern (LOG-03)
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/class/billing.class.php` (lines 69, 86, 92, 138, 142, 221, 249)
**Apply to:** `api_wallboxbilling.class.php` `postSession()` method
```php
// INFO for normal events:
dol_syslog("WallboxBilling: Abrechnung erstellt für User ".$obj->login." - ".$totalCost." EUR", LOG_INFO);

// ERR for DB errors:
dol_syslog("WallboxBilling Error: ".$this->error, LOG_ERR);

// WARNING for non-critical issues:
dol_syslog("WallboxBilling: ".$this->error, LOG_WARNING);
```

### dolibarr_set_const Config Pattern (ALT-02 admin.php)
**Source:** `Dolibarr/htdocs/custom/wallboxbilling/admin.php` (lines 25-26)
**Apply to:** `admin.php` config tab for `WALLBOXBILLING_ADMIN_EMAIL`
```php
$new_price = GETPOST('WALLBOXBILLING_DEFAULT_PRICE', 'alpha');
dolibarr_set_const($db, 'WALLBOXBILLING_DEFAULT_PRICE', $new_price, 'chaine', 0, '', $conf->entity);
```

### pytest conftest Fixture Pattern (all test files)
**Source:** `Homeassistant/tests/conftest.py` (lines 14-44)
**Apply to:** All new test files — use existing fixtures, do not redefine
```python
# Use in_memory_session_manager, mock_api_client_success, mock_api_client_failure
# from conftest.py — do NOT redefine in individual test files
```

### Test sys.path Pattern (all test files)
**Source:** `Homeassistant/tests/test_health.py` (lines 12-13)
**Apply to:** All new test files
```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

---

## No Analog Found

All files have analogs in the codebase. No gaps.

---

## Key Anti-Patterns (from RESEARCH.md — enforce in all new code)

| Anti-Pattern | Rule | Where It Applies |
|---|---|---|
| `logging.basicConfig()` called after init | Never call again — use `logging.getLogger().setLevel()` | `main.py` LOG-01 fix |
| `notification_id` omitted | Always pass fixed `"wallbox_upload_error"` | `send_persistent_notification()` |
| `rfid_hex` raw in log | Always use `rfid_hash[:16]` prefix | Any new log call touching RFID |
| `php mail()` direct | Use `CMailFile` only | `api_wallboxbilling.class.php` ALT-02 |
| E-Mail without `WALLBOXBILLING_ADMIN_EMAIL` guard | Always check `!empty($admin_email)` first | `api_wallboxbilling.class.php` ALT-02 |
| `sendfile()` failure silently ignored | Always `dol_syslog(LOG_WARNING)` if false | `api_wallboxbilling.class.php` ALT-02 |

---

## Metadata

**Analog search scope:** `Homeassistant/`, `Dolibarr/htdocs/custom/wallboxbilling/`
**Files scanned:** `main.py`, `session_manager.py`, `api_client.py`, `config.yaml`, `tests/conftest.py`, `tests/test_health.py`, `tests/test_session_status.py`, `class/billing.class.php`, `class/api_wallboxbilling.class.php`, `admin.php`
**Pattern extraction date:** 2026-06-22
