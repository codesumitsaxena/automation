"""Integration tests for OrchestrationService and the primary OpenAI deliverable."""

import pytest

from app.services.orchestrator import OrchestrationService


@pytest.mark.asyncio
async def test_openai_demo_deliverable_flow():
    """Verify that the primary deliverable produces 1 enriched company and exactly 5 contacts."""
    orchestrator = OrchestrationService()
    demo_result = await orchestrator.run_openai_demo(domain="openai.com", limit=5)

    assert demo_result["success"] is True
    assert demo_result["company"]["name"] == "OpenAI"
    assert demo_result["company"]["domain"] == "openai.com"
    assert demo_result["company"]["numberofemployees"] == "770"

    contacts = demo_result["contacts"]
    assert len(contacts) == 5, "Must enrich exactly 5 contacts under OpenAI"

    # Verify required contact fields for each person
    for c in contacts:
        assert c["name"], "Contact name must not be empty"
        assert c["job_title"], "Job title must not be empty"
        assert c["email"], "Email must not be empty"
        assert c["phone"], "Phone must not be empty"
        assert c["location"], "Location must not be empty"
        assert "San Francisco" in c["location"]
