#!/usr/bin/env python3
"""
Tests für LOG-01: Log-Level aus options.json wird angewendet.
Phase 7: Alerts & Logging

Verifies that apply_log_level_from_config() correctly sets the Python root logger
level from the options.json config dict without calling logging.basicConfig() again.
"""
import pytest
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestLogLevelConfig:
    """Tests für LOG-01: options.json log_level wird auf Root-Logger angewendet."""

    def test_apply_log_level_debug(self):
        """apply_log_level_from_config({'log_level': 'DEBUG'}) setzt Root-Logger auf DEBUG."""
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({'log_level': 'DEBUG'})
            assert logging.getLogger().level == logging.DEBUG
            # Cleanup: reset to INFO to avoid polluting other tests
            logging.getLogger().setLevel(logging.INFO)

    def test_apply_log_level_warning(self):
        """apply_log_level_from_config({'log_level': 'WARNING'}) setzt Root-Logger auf WARNING."""
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({'log_level': 'WARNING'})
            assert logging.getLogger().level == logging.WARNING
            logging.getLogger().setLevel(logging.INFO)

    def test_apply_log_level_invalid_falls_back_to_info(self):
        """Ungültiger log_level ('INVALID') fällt zurück auf INFO."""
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({'log_level': 'INVALID'})
            assert logging.getLogger().level == logging.INFO

    def test_apply_log_level_missing_key_falls_back_to_info(self):
        """Fehlender log_level Key im Config-Dict fällt zurück auf INFO."""
        import unittest.mock as mock
        with mock.patch.dict('sys.modules', {
            'session_manager': mock.MagicMock(),
            'api_client': mock.MagicMock(),
            'utils': mock.MagicMock(),
            'utils.hash': mock.MagicMock(),
        }):
            if 'main' in sys.modules:
                del sys.modules['main']
            from main import apply_log_level_from_config
            apply_log_level_from_config({})
            assert logging.getLogger().level == logging.INFO

    def test_apply_log_level_function_exists_in_main(self):
        """apply_log_level_from_config muss in main.py als Funktion definiert sein."""
        main_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'main.py')
        with open(main_path, 'r') as f:
            content = f.read()
        assert 'def apply_log_level_from_config' in content, \
            "apply_log_level_from_config function not found in main.py"
        assert 'apply_log_level_from_config(current_config)' in content, \
            "apply_log_level_from_config not called with current_config in main()"
