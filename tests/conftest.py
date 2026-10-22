"""Pytest configuration and global test fixtures.

Ensures that unit tests run in offline mock mode by default, preventing unintended
network calls to HubSpot or Forager unless specifically testing operational flags.
"""

import os
import pytest
from app.config import get_settings


@pytest.fixture(autouse=True)
def default_mock_environment(monkeypatch):
    """Ensure all tests run with mock dry-run defaults unless explicitly overridden."""
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("FORAGER_DRY_RUN", "true")
    monkeypatch.setenv("HUBSPOT_DRY_RUN", "true")
    # Clear settings cache so get_settings() reflects mock mode
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
