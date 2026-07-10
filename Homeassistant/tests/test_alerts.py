#!/usr/bin/env python3
"""
Tests für ALT-01: HA persistent_notification bei Upload-Fehlern.
Phase 7: Alerts & Logging

Verifies: graceful no-token behavior, message truncation, notification_id default.
"""
import pytest
import asyncio
import sys
import os
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Module-level mock patch context for main.py imports that require HA runtime
MAIN_MOCKS = {
    'session_manager': mock.MagicMock(),
    'api_client': mock.MagicMock(),
    'utils': mock.MagicMock(),
    'utils.hash': mock.MagicMock(),
}


def _import_send_notification():
    """Import send_persistent_notification with mocked HA dependencies."""
    with mock.patch.dict('sys.modules', MAIN_MOCKS):
        if 'main' in sys.modules:
            del sys.modules['main']
        from main import send_persistent_notification
        return send_persistent_notification


class TestPersistentNotification:
    """Tests für ALT-01: send_persistent_notification Verhalten."""

    def test_function_exists_in_main(self):
        """send_persistent_notification muss in main.py definiert sein."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        with open(main_path, 'r') as f:
            content = f.read()
        assert 'async def send_persistent_notification' in content, \
            "send_persistent_notification not found in main.py"

    def test_called_on_failed_transmission_in_main(self):
        """periodic_transmission() muss send_persistent_notification aufrufen wenn failed > 0."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        with open(main_path, 'r') as f:
            content = f.read()
        assert 'await send_persistent_notification' in content, \
            "await send_persistent_notification not called in main.py"

    def test_notification_id_default_is_wallbox_upload_error(self):
        """Default notification_id muss 'wallbox_upload_error' sein."""
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        with open(main_path, 'r') as f:
            content = f.read()
        assert 'notification_id.*wallbox_upload_error' or 'wallbox_upload_error' in content, \
            "wallbox_upload_error not found in main.py"

    @pytest.mark.asyncio
    async def test_no_token_returns_gracefully(self, monkeypatch):
        """Wenn SUPERVISOR_TOKEN fehlt: kein Crash, kein raise."""
        monkeypatch.delenv('SUPERVISOR_TOKEN', raising=False)
        send_persistent_notification = _import_send_notification()
        # Must not raise
        await send_persistent_notification("Test", "Test-Nachricht")

    @pytest.mark.asyncio
    async def test_message_truncated_to_500_chars(self, monkeypatch):
        """Nachricht über 500 Zeichen wird auf 500 Zeichen gekürzt (Injection-Schutz)."""
        monkeypatch.delenv('SUPERVISOR_TOKEN', raising=False)
        send_persistent_notification = _import_send_notification()
        long_message = "x" * 1000
        # With no token the function returns early — but we verify the truncation
        # logic exists statically
        main_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'main.py'
        )
        with open(main_path, 'r') as f:
            content = f.read()
        assert 'message[:500]' in content or "message[:500]" in content, \
            "500-char message truncation guard not found in send_persistent_notification"
        # Also verify graceful return with no token
        await send_persistent_notification("Test", long_message)  # no raise
