"""Unit and integration tests for HubSpot webhook processing, signature validation, and loop avoidance."""

import base64
import hashlib
import hmac
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.orchestrator import OrchestrationService
from app.webhooks.security import verify_hubspot_v3_signature


def test_signature_v3_validation():
    secret = "sample-hubspot-secret-key"
    method = "POST"
    url = "https://example.com/webhooks/hubspot"
    raw_body = b'{"eventId": 123}'
    timestamp = str(int(time.time() * 1000))

    source = f"{method}{url}{raw_body.decode('utf-8')}{timestamp}"
    valid_sig = base64.b64encode(hmac.new(secret.encode(), source.encode(), hashlib.sha256).digest()).decode()

    # Valid signature
    assert verify_hubspot_v3_signature(method, url, raw_body, timestamp, valid_sig, secret) is True
    # Tampered signature
    assert verify_hubspot_v3_signature(method, url, raw_body, timestamp, "invalid", secret) is False
    # Expired timestamp (older than 5 minutes)
    expired_ts = str(int((time.time() - 350) * 1000))
    assert verify_hubspot_v3_signature(method, url, raw_body, expired_ts, valid_sig, secret) is False


@pytest.mark.asyncio
async def test_webhook_deduplication():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        unique_event_id = f"test_ev_{int(time.time() * 1000)}"
        payload = [{"eventId": unique_event_id, "subscriptionType": "company.creation", "objectId": "comp_1001"}]

        # First request: accepted
        res1 = await client.post("/webhooks/hubspot", json=payload)
        assert res1.status_code == 200
        assert res1.json()["events_accepted"] == 1

        # Second request with same eventId: duplicate ignored
        res2 = await client.post("/webhooks/hubspot", json=payload)
        assert res2.status_code == 200
        assert res2.json()["duplicates_ignored"] == 1


@pytest.mark.asyncio
async def test_contact_webhook_loop_prevention():
    """Verify ISSUE-11: Webhook loop prevention explicitly returns status == 'LOOP_PREVENTED'."""
    from unittest.mock import AsyncMock

    from app.clients.hubspot_client import HubSpotClient

    # Scenario A: Using mocked HubSpot client with forager_status='discovered'
    mock_hubspot = AsyncMock(spec=HubSpotClient)
    mock_hubspot.get_contact.return_value = {
        "id": "discovered_cont_999",
        "properties": {
            "firstname": "Sam",
            "lastname": "Altman",
            "email": "sam@openai.com",
            "forager_status": "discovered",
        },
    }
    orchestrator = OrchestrationService(hubspot_client=mock_hubspot)
    res = await orchestrator.handle_contact_webhook(contact_id="discovered_cont_999")

    assert res.get("success") is True
    assert res.get("status") == "LOOP_PREVENTED"
    assert "loop avoided" in res.get("message", "").lower()

    # Scenario B: Using live simulated client registry
    client = HubSpotClient()
    client._simulated_contacts["sim_loop_101"] = {
        "id": "sim_loop_101",
        "properties": {
            "firstname": "Greg",
            "lastname": "Brockman",
            "forager_status": "discovered",
        },
    }
    orch_sim = OrchestrationService(hubspot_client=client)
    res_sim = await orch_sim.handle_contact_webhook(contact_id="sim_loop_101")
    assert res_sim.get("success") is True
    assert res_sim.get("status") == "LOOP_PREVENTED"
