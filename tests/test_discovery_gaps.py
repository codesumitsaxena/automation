"""Unit tests for graceful handling of real data gaps in contact discovery (ISSUE-05 requirement)."""

import pytest
from unittest.mock import AsyncMock
from app.clients.forager_client import ForagerClient
from app.clients.hubspot_client import HubSpotClient
from app.services.credit_guard import CreditGuard
from app.services.discovery_service import DiscoveryService


@pytest.mark.asyncio
async def test_discovery_prioritizes_complete_contacts_and_reports_gaps():
    """Verify that when candidates have data gaps (missing phone/email), discovery prioritizes

    complete profiles and never invents fake data.
    """
    mock_forager = AsyncMock(spec=ForagerClient)
    mock_hubspot = AsyncMock(spec=HubSpotClient)
    mock_guard = AsyncMock(spec=CreditGuard)

    # Cache helper returns False
    mock_forager.is_people_search_cached.return_value = False

    # Candidate 1: Missing phone and email
    cand1_incomplete = {
        "first_name": "Incomplete",
        "last_name": "One",
        "role_title": "Vice President of Marketing",
        "email": None,
        "phone": None,
        "linkedin_public_identifier": "incomplete-one",
        "location": {"city": "New York", "state": "NY", "country": "USA"},
    }

    # Candidate 2: Complete phone and email
    cand2_complete = {
        "first_name": "Complete",
        "last_name": "Two",
        "role_title": "Director of Product",
        "email": "complete.two@target.com",
        "phone": "+1-212-555-0199",
        "linkedin_public_identifier": "complete-two",
        "location": {"city": "New York", "state": "NY", "country": "USA"},
    }

    # Candidate 3: Also complete
    cand3_complete = {
        "first_name": "Complete",
        "last_name": "Three",
        "role_title": "Chief Technology Officer",
        "email": "complete.three@target.com",
        "phone": "+1-212-555-0200",
        "linkedin_public_identifier": "complete-three",
        "location": {"city": "San Francisco", "state": "CA", "country": "USA"},
    }

    mock_forager.search_people_by_company.return_value = [
        cand1_incomplete,
        cand2_complete,
        cand3_complete,
    ]

    discovery = DiscoveryService(
        forager_client=mock_forager,
        hubspot_client=mock_hubspot,
        credit_guard=mock_guard,
    )

    # Request limit=2: Should pick cand2 and cand3 first because they have verified emails/phones
    results = await discovery.discover_contacts(
        company_domain="target.com",
        job_titles=["VP", "Director", "CTO"],
        limit=2,
        add_to_hubspot=False,
    )

    assert len(results) == 2
    # Both selected contacts must be the ones with complete phone & email
    assert results[0].firstname == "Complete"
    assert results[1].firstname == "Complete"
    assert results[0].email is not None and results[0].phone is not None
    assert results[1].email is not None and results[1].phone is not None

    # Request limit=3: Should pick cand2, cand3 AND include cand1 honestly without faking data
    results_all = await discovery.discover_contacts(
        company_domain="target.com",
        job_titles=["VP", "Director", "CTO"],
        limit=3,
        add_to_hubspot=False,
    )
    assert len(results_all) == 3
    # Candidate 3 has None email/phone (reported honestly, not faked)
    assert results_all[2].firstname == "Incomplete"
    assert results_all[2].email is None
    assert results_all[2].phone is None
