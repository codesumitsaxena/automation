"""Unit and regression tests for ISSUE-04: Contact deduplication before creation in HubSpot."""

from unittest.mock import AsyncMock

import pytest

from app.clients.hubspot_client import HubSpotClient
from app.models.schemas import NormalizedContactData
from app.services.discovery_service import DiscoveryService


@pytest.mark.asyncio
async def test_dry_run_in_memory_registry_prevents_duplicate_creation():
    """Verify that in DRY_RUN / simulated mode, subsequent creations retrieve existing records."""
    client = HubSpotClient()
    assert client.is_live is False, "Test expects simulated mode"

    # 1. Create contact 1
    props_1 = {
        "email": "sam@openai.com",
        "firstname": "Sam",
        "lastname": "Altman",
        "person_linkedin_url": "https://linkedin.com/in/samaltman",
    }
    res_1 = await client.create_contact(props_1)
    cid_1 = res_1["id"]

    # 2. Search by email -> must return the exact same contact
    found_by_email = await client.search_contact_by_email("sam@openai.com")
    assert found_by_email is not None
    assert found_by_email["id"] == cid_1

    # 3. Search by LinkedIn URL -> must also return the exact same contact
    found_by_linkedin = await client.search_contact_by_linkedin_url("https://linkedin.com/in/samaltman")
    assert found_by_linkedin is not None
    assert found_by_linkedin["id"] == cid_1


@pytest.mark.asyncio
async def test_live_mode_checks_email_and_linkedin_before_creating():
    """Verify that in LIVE mode, discovery searches by email AND LinkedIn URL before creating."""
    mock_hubspot = AsyncMock(spec=HubSpotClient)
    mock_hubspot.is_live = True

    # Scenario A: Contact found by email -> calls update_contact, NOT create_contact
    mock_hubspot.search_contact_by_email.return_value = {"id": "hs_live_123", "properties": {}}
    discovery = DiscoveryService(hubspot_client=mock_hubspot)

    contact_with_email = NormalizedContactData(
        firstname="Sam",
        lastname="Altman",
        email="sam@openai.com",
        person_linkedin_url="https://linkedin.com/in/samaltman",
        domain="openai.com",
    )

    await discovery._persist_and_associate_contact(contact_with_email)
    mock_hubspot.search_contact_by_email.assert_awaited_with("sam@openai.com")
    mock_hubspot.update_contact.assert_awaited_once()
    mock_hubspot.create_contact.assert_not_awaited()

    # Scenario B: Contact has NO email, but has LinkedIn URL -> searches by LinkedIn URL and updates
    mock_hubspot.reset_mock()
    mock_hubspot.search_contact_by_email.return_value = None
    mock_hubspot.search_contact_by_linkedin_url.return_value = {"id": "hs_live_456", "properties": {}}

    contact_linkedin_only = NormalizedContactData(
        firstname="Greg",
        lastname="Brockman",
        email=None,
        person_linkedin_url="https://linkedin.com/in/gregbrockman",
        domain="openai.com",
    )

    await discovery._persist_and_associate_contact(contact_linkedin_only)
    mock_hubspot.search_contact_by_linkedin_url.assert_awaited_with("https://linkedin.com/in/gregbrockman")
    mock_hubspot.update_contact.assert_awaited_once()
    mock_hubspot.create_contact.assert_not_awaited()

    # Scenario C: Contact not found by email or LinkedIn -> creates new contact
    mock_hubspot.reset_mock()
    mock_hubspot.search_contact_by_email.return_value = None
    mock_hubspot.search_contact_by_linkedin_url.return_value = None
    mock_hubspot.create_contact.return_value = {"id": "hs_live_new_789"}

    contact_new = NormalizedContactData(
        firstname="Brand",
        lastname="New",
        email="new@openai.com",
        person_linkedin_url="https://linkedin.com/in/brandnew",
        domain="openai.com",
    )

    await discovery._persist_and_associate_contact(contact_new)
    mock_hubspot.search_contact_by_email.assert_awaited_with("new@openai.com")
    mock_hubspot.create_contact.assert_awaited_once()
