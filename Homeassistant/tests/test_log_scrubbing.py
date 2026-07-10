#!/usr/bin/env python3
"""
Tests für LOG-02: Log-Scrubbing — keine sensiblen Daten in Logs.
Phase 7: Alerts & Logging

Verifies: no RFID cleartext, no API tokens appear in log output.
"""
import pytest
import logging
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLogScrubbing:
    """Tests für LOG-02: Kein RFID-Klartext, keine API-Token in Logs."""

    def test_rfid_hex_not_in_debounce_logs(self, caplog, in_memory_session_manager):
        """rfid_hex Klartext darf nach debounce_rfid() nicht in Logs erscheinen."""
        rfid_hex = "EFCD083E"
        with caplog.at_level(logging.DEBUG):
            in_memory_session_manager.debounce_rfid(rfid_hex)
        for record in caplog.records:
            assert rfid_hex.upper() not in record.message, \
                f"RFID Klartext gefunden in Log: {record.message}"
            assert rfid_hex.lower() not in record.message, \
                f"RFID Klartext (lower) gefunden in Log: {record.message}"

    def test_rfid_hex_not_in_session_start_logs(self, caplog, in_memory_session_manager):
        """rfid_hex Klartext darf nach start_session() nicht in Logs erscheinen."""
        rfid_hex = "ABCD1234"
        with caplog.at_level(logging.DEBUG):
            try:
                in_memory_session_manager.start_session(rfid_hex, 100.0)
            except Exception:
                pass  # Start may fail without full setup — we only check log content
        for record in caplog.records:
            assert rfid_hex.upper() not in record.message, \
                f"RFID Klartext in start_session Log: {record.message}"
            assert rfid_hex.lower() not in record.message, \
                f"RFID Klartext (lower) in start_session Log: {record.message}"

    def test_api_token_not_logged_in_api_client(self):
        """DOLAPIKEY api_token darf nicht direkt in _LOGGER-Aufrufen vorkommen (statische Analyse)."""
        api_client_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'api_client.py'
        )
        with open(api_client_path, 'r') as f:
            content = f.read()
        # Find all _LOGGER call lines and check none contain api_token variable directly
        logger_calls = re.findall(r'_LOGGER\.\w+\([^)]*\)', content, re.DOTALL)
        for call in logger_calls:
            assert 'api_token' not in call, \
                f"api_token found in logger call: {call}"

    def test_rfid_hash_prefix_pattern_used_in_main(self):
        """main.py muss rfid_hash[:16] Pattern verwenden, niemals rfid_hex direkt."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        with open(main_path, 'r') as f:
            content = f.read()
        # rfid_hex should not appear in any _LOGGER call
        logger_lines = [line for line in content.splitlines() if '_LOGGER' in line and 'rfid' in line.lower()]
        for line in logger_lines:
            assert 'rfid_hex' not in line, \
                f"rfid_hex (cleartext) found in logger call in main.py: {line}"
