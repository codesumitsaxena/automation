"""Unit tests for split dry run modes (FORAGER_DRY_RUN / HUBSPOT_DRY_RUN) and SAVE_RAW_RESPONSES."""

import os
import json
from app.config import get_settings
from app.clients.forager_client import ForagerClient
from app.clients.hubspot_client import HubSpotClient

settings = get_settings()


def test_split_dry_run_flags_forager_mock_hubspot_live(monkeypatch):
    """Verify that FORAGER_DRY_RUN=True and HUBSPOT_DRY_RUN=False configures

    Forager to use mocks and HubSpot to use live CRM calls.
    """
    monkeypatch.setattr(settings, "forager_dry_run", True)
    monkeypatch.setattr(settings, "hubspot_dry_run", False)
    monkeypatch.setattr(settings, "hubspot_access_token", "pat-na1-test-token-12345")

    forager = ForagerClient()
    hubspot = HubSpotClient()

    assert forager.dry_run is True
    assert hubspot.is_live is True
    assert settings.mode_badge == "FORAGER: MOCK | HUBSPOT: LIVE"


def test_split_dry_run_flags_both_mock(monkeypatch):
    """Verify that when both dry run flags are True, both clients run in mock mode."""
    monkeypatch.setattr(settings, "forager_dry_run", True)
    monkeypatch.setattr(settings, "hubspot_dry_run", True)

    forager = ForagerClient()
    hubspot = HubSpotClient()

    assert forager.dry_run is True
    assert hubspot.is_live is False
    assert settings.mode_badge == "FORAGER: MOCK | HUBSPOT: MOCK"


def test_save_raw_responses_creates_file(monkeypatch, tmp_path):
    """Verify that SAVE_RAW_RESPONSES=True persists sanitized response files."""
    test_raw_dir = str(tmp_path / "raw_responses")
    monkeypatch.setattr(settings, "save_raw_responses", True)
    monkeypatch.setattr(settings, "raw_responses_dir", test_raw_dir)

    forager = ForagerClient()
    endpoint = "/api/test_account/datastorage/organization_search/"
    payload = {"domains": ["testcorp.com"]}
    response = {"data": [{"name": "TestCorp", "domain": "testcorp.com"}]}

    forager._save_raw_response(endpoint, payload, response)

    files = os.listdir(test_raw_dir)
    assert len(files) == 1
    assert "testcorp_com" in files[0]

    with open(os.path.join(test_raw_dir, files[0]), "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["payload"]["domains"] == ["testcorp.com"]
    assert data["response"]["data"][0]["name"] == "TestCorp"
