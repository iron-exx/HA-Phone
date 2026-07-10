#!/usr/bin/env python3
"""
Tests für Log-Level-Konfiguration (LOG-01) und persistent_notification (ALT-01).
Phase 7: Alerts & Logging — Plan 07-01

TDD RED phase: these tests define the expected behavior BEFORE implementation.
"""
import pytest
import logging
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# LOG-01: apply_log_level_from_config()
# ---------------------------------------------------------------------------

class TestApplyLogLevelFromConfig:
    """Tests für LOG-01: options.json log_level wird auf Root-Logger angewendet."""

    def test_debug_level_sets_root_logger(self):
        """apply_log_level_from_config({'log_level': 'DEBUG'}) → root level == DEBUG"""
        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({'log_level': 'DEBUG'})
            assert logging.getLogger().level == logging.DEBUG
            # Cleanup
            logging.getLogger().setLevel(logging.INFO)

    def test_warning_level_sets_root_logger(self):
        """apply_log_level_from_config({'log_level': 'WARNING'}) → root level == WARNING"""
        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({'log_level': 'WARNING'})
            assert logging.getLogger().level == logging.WARNING
            # Cleanup
            logging.getLogger().setLevel(logging.INFO)

    def test_invalid_level_falls_back_to_info(self):
        """apply_log_level_from_config({'log_level': 'INVALID'}) → fallback to INFO"""
        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({'log_level': 'INVALID'})
            assert logging.getLogger().level == logging.INFO

    def test_missing_key_falls_back_to_info(self):
        """apply_log_level_from_config({}) → fallback to INFO"""
        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({})
            assert logging.getLogger().level == logging.INFO

    def test_function_exists_in_main_py(self):
        """apply_log_level_from_config must be defined in main.py"""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')) as f:
            content = f.read()
        assert 'def apply_log_level_from_config' in content

    def test_called_after_load_config_in_main(self):
        """apply_log_level_from_config(current_config) call must appear after load_config() in main()"""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')) as f:
            content = f.read()
        assert 'apply_log_level_from_config(current_config)' in content

    def test_no_new_basicconfig_call(self):
        """Only one actual basicConfig() call in main.py (the original module-level one).
        Comments and docstrings mentioning basicConfig are acceptable.
        """
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')) as f:
            content = f.read()
        # Count only actual call lines (starts with 'logging.basicConfig(' after stripping)
        actual_call_lines = [
            l for l in content.splitlines()
            if 'basicConfig(' in l
            and not l.strip().startswith('#')
            and not l.strip().startswith('"""')
            and not l.strip().startswith("'")
            # exclude docstring/comment lines that describe but don't call basicConfig
            and not l.strip().startswith('logging.basicConfig() kann')
        ]
        assert len(actual_call_lines) == 1, f"Expected 1 basicConfig call, found: {actual_call_lines}"


# ---------------------------------------------------------------------------
# ALT-01: send_persistent_notification()
# ---------------------------------------------------------------------------

class TestSendPersistentNotification:
    """Tests für ALT-01: send_persistent_notification via HA Supervisor REST API."""

    @pytest.mark.asyncio
    async def test_no_token_returns_gracefully(self, monkeypatch):
        """When SUPERVISOR_TOKEN is absent → function returns None without raising."""
        monkeypatch.delenv('SUPERVISOR_TOKEN', raising=False)
        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import send_persistent_notification
            result = await send_persistent_notification("Test Title", "Test Message")
            assert result is None  # graceful return

    @pytest.mark.asyncio
    async def test_message_truncated_to_500_chars(self, monkeypatch):
        """Message longer than 500 chars must be truncated to exactly 500 chars."""
        monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-token')
        long_message = "x" * 1000

        captured_payload = {}

        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = mock.AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = mock.AsyncMock(return_value=False)

        def capturing_post(url, **kwargs):
            captured_payload['json'] = kwargs.get('json', {})
            return mock_resp

        mock_session_instance = mock.MagicMock()
        mock_session_instance.post = mock.MagicMock(side_effect=capturing_post)
        mock_session_instance.__aenter__ = mock.AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = mock.AsyncMock(return_value=False)

        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            with mock.patch('aiohttp.ClientSession', return_value=mock_session_instance):
                from main import send_persistent_notification
                await send_persistent_notification("Title", long_message)

        assert len(captured_payload.get('json', {}).get('message', '')) <= 500

    @pytest.mark.asyncio
    async def test_uses_default_notification_id(self, monkeypatch):
        """Default notification_id must be 'wallbox_upload_error'."""
        monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-token')
        captured_payload = {}

        # Build a proper async context manager mock for session.post
        mock_resp = mock.MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = mock.AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = mock.AsyncMock(return_value=False)

        def capturing_post(url, **kwargs):
            captured_payload['json'] = kwargs.get('json', {})
            return mock_resp

        mock_session_instance = mock.MagicMock()
        mock_session_instance.post = mock.MagicMock(side_effect=capturing_post)
        mock_session_instance.__aenter__ = mock.AsyncMock(return_value=mock_session_instance)
        mock_session_instance.__aexit__ = mock.AsyncMock(return_value=False)

        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            with mock.patch('aiohttp.ClientSession', return_value=mock_session_instance):
                from main import send_persistent_notification
                await send_persistent_notification("Title", "Message")  # no notification_id

        assert captured_payload.get('json', {}).get('notification_id') == 'wallbox_upload_error'

    @pytest.mark.asyncio
    async def test_posts_to_supervisor_endpoint(self, monkeypatch):
        """Must POST to http://supervisor/core/api/services/persistent_notification/create"""
        monkeypatch.setenv('SUPERVISOR_TOKEN', 'test-token')
        posted_urls = []

        def mock_post_fn(url, **kwargs):
            posted_urls.append(url)
            cm = mock.MagicMock()
            cm.__aenter__ = mock.AsyncMock(return_value=mock.AsyncMock(status=200))
            cm.__aexit__ = mock.AsyncMock(return_value=False)
            return cm

        mock_session_instance = mock.AsyncMock()
        mock_session_instance.post = mock.MagicMock(side_effect=mock_post_fn)

        mock_session_cm = mock.MagicMock()
        mock_session_cm.__aenter__ = mock.AsyncMock(return_value=mock_session_instance)
        mock_session_cm.__aexit__ = mock.AsyncMock(return_value=False)

        with mock.patch.dict('sys.modules', {
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            with mock.patch('aiohttp.ClientSession', return_value=mock_session_cm):
                from main import send_persistent_notification
                await send_persistent_notification("Title", "Message")

        assert any('persistent_notification/create' in url for url in posted_urls)

    def test_function_exists_in_main_py(self):
        """send_persistent_notification must be defined in main.py"""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')) as f:
            content = f.read()
        assert 'async def send_persistent_notification' in content

    def test_called_in_periodic_transmission(self):
        """await send_persistent_notification must appear inside periodic_transmission"""
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')) as f:
            content = f.read()
        assert 'await send_persistent_notification' in content
