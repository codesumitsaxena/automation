"""Unit tests for the cleanup_mock_records script."""

import pytest
from app.clients.hubspot_client import HubSpotClient


@pytest.mark.asyncio
async def test_search_and_delete_mock_demo_records():
    """Verify that search_companies_by_property, search_contacts_by_property,

    delete_company, and delete_contact properly manage mock_demo records.
    """
    client = HubSpotClient()
    assert client.is_live is False

    # Simulate creation of mock demo records and non-mock records
    comp_mock = await client.create_company({
        "name": "Test Mock Co",
        "domain": "testmock.com",
        "forager_status": "mock_demo",
    })
    comp_real = await client.create_company({
        "name": "Real Co",
        "domain": "realco.com",
        "forager_status": "enriched",
    })

    cont_mock = await client.create_contact({
        "firstname": "Mock",
        "lastname": "User",
        "email": "mock@testmock.com",
        "forager_status": "mock_demo",
    })
    cont_real = await client.create_contact({
        "firstname": "Real",
        "lastname": "User",
        "email": "real@realco.com",
        "forager_status": "discovered",
    })

    # Search for mock_demo only
    found_comps = await client.search_companies_by_property("forager_status", "mock_demo")
    found_conts = await client.search_contacts_by_property("forager_status", "mock_demo")

    assert len(found_comps) == 1
    assert found_comps[0]["id"] == comp_mock["id"]

    assert len(found_conts) == 1
    assert found_conts[0]["id"] == cont_mock["id"]

    # Delete the mock records
    del_comp = await client.delete_company(comp_mock["id"])
    del_cont = await client.delete_contact(cont_mock["id"])

    assert del_comp is True
    assert del_cont is True

    # Verify they are gone from simulated storage
    remaining_comps = await client.search_companies_by_property("forager_status", "mock_demo")
    remaining_conts = await client.search_contacts_by_property("forager_status", "mock_demo")

    assert len(remaining_comps) == 0
    assert len(remaining_conts) == 0
