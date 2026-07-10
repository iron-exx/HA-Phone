"""
Shared pytest fixtures for Homeassistant test suite.
Phase 6: Monitoring & Status (MON-01, MON-02, MON-03)
"""
import pytest
import sqlite3
import sys
import os

# Ensure Homeassistant/ is on the import path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def in_memory_session_manager(tmp_path):
    """SessionManager backed by a temporary file SQLite database.
    Uses tmp_path (pytest fixture) for isolation — file removed after test.
    (:memory: does not work with multiple connections per method call.)
    """
    try:
        from session_manager import SessionManager
        db_file = str(tmp_path / "test_sessions.db")
        sm = SessionManager(db_path=db_file)
        yield sm
    except ImportError:
        pytest.skip("session_manager module not importable in this environment")


@pytest.fixture
def mock_api_client_success():
    """Stub api_client that always reports successful upload."""
    class MockApiClient:
        def transmit_session(self, session):
            return (True, "")
    return MockApiClient()


@pytest.fixture
def mock_api_client_failure():
    """Stub api_client that always reports failed upload with error message."""
    class MockApiClient:
        def transmit_session(self, session):
            return (False, "HTTP 503: Service Unavailable")
    return MockApiClient()


@pytest.fixture
async def health_app():
    """aiohttp Application with /health and /session/stop routes wired up.
    Only available after Wave 1 implements start_health_server in main.py.
    """
    try:
        from aiohttp import web
        from aiohttp.test_utils import TestClient, TestServer
        # Import will fail until Wave 1 implements these handlers
        from main import handle_health, handle_session_stop
        app = web.Application()
        app.router.add_get('/health', handle_health)
        app.router.add_post('/session/stop', handle_session_stop)
        return app
    except ImportError:
        pytest.skip("main.py handlers not yet implemented (Wave 1 pending)")
