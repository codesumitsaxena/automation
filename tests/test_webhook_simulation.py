"""Integration test verifying full HubSpot webhook lifecycle:
1. Valid v3 signature acceptance
2. Invalid signature rejection (401)
3. Expired timestamp rejection (401)
4. Duplicate eventId deduplication
"""

import base64
import hashlib
import hmac
import time

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import get_settings
from app.main import app

settings = get_settings()


def generate_v3_signature(
    method: str,
    url: str,
    body: bytes,
    timestamp: str,
    client_secret: str,
) -> str:
    """Generate canonical HubSpot v3 HMAC-SHA256 signature."""
    source = f"{method}{url}{body.decode('utf-8')}{timestamp}"
    h = hmac.new(client_secret.encode("utf-8"), source.encode("utf-8"), hashlib.sha256)
    return base64.b64encode(h.digest()).decode("utf-8")


@pytest.mark.asyncio
async def test_webhook_simulation_suite(monkeypatch):
    """Run full simulated webhook verification matrix."""
    test_secret = "test-secret-key-12345"
    public_url = "https://my-app.up.railway.app"
    endpoint_path = "/webhooks/hubspot"
    full_target_url = f"{public_url}{endpoint_path}"

    # Temporarily enforce signature verification and test credentials
    monkeypatch.setattr(settings, "verify_webhook_signature", True)
    monkeypatch.setattr(settings, "hubspot_client_secret", test_secret)
    monkeypatch.setattr(settings, "public_base_url", public_url)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Common headers simulating reverse proxy
        base_headers = {
            "Content-Type": "application/json",
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "my-app.up.railway.app",
        }

        # ---------------------------------------------------------------------
        # Case 1: Valid Signature -> 200 OK and Accepted
        # ---------------------------------------------------------------------
        ev1_id = f"sim_valid_{int(time.time() * 1000)}"
        body_bytes = f'[{{"eventId": "{ev1_id}", "subscriptionType": "company.creation", "objectId": "comp_9001"}}]'.encode()
        now_ts = str(int(time.time() * 1000))
        valid_sig = generate_v3_signature("POST", full_target_url, body_bytes, now_ts, test_secret)

        res_valid = await client.post(
            endpoint_path,
            content=body_bytes,
            headers={
                **base_headers,
                "X-HubSpot-Signature-v3": valid_sig,
                "X-HubSpot-Request-Timestamp": now_ts,
            },
        )
        assert res_valid.status_code == 200, f"Expected 200 for valid signature, got {res_valid.status_code}"
        data_valid = res_valid.json()
        assert data_valid["events_accepted"] == 1
        assert data_valid["duplicates_ignored"] == 0

        # ---------------------------------------------------------------------
        # Case 2: Invalid Signature -> 401 Unauthorized
        # ---------------------------------------------------------------------
        res_invalid = await client.post(
            endpoint_path,
            content=body_bytes,
            headers={
                **base_headers,
                "X-HubSpot-Signature-v3": "tampered_and_invalid_signature_string",
                "X-HubSpot-Request-Timestamp": now_ts,
            },
        )
        assert res_invalid.status_code == 401, f"Expected 401 for invalid signature, got {res_invalid.status_code}"

        # ---------------------------------------------------------------------
        # Case 3: Expired Timestamp (> 300 seconds) -> 401 Unauthorized
        # ---------------------------------------------------------------------
        expired_ts = str(int((time.time() - 350) * 1000))
        expired_sig = generate_v3_signature("POST", full_target_url, body_bytes, expired_ts, test_secret)
        res_expired = await client.post(
            endpoint_path,
            content=body_bytes,
            headers={
                **base_headers,
                "X-HubSpot-Signature-v3": expired_sig,
                "X-HubSpot-Request-Timestamp": expired_ts,
            },
        )
        assert res_expired.status_code == 401, f"Expected 401 for expired timestamp, got {res_expired.status_code}"

        # ---------------------------------------------------------------------
        # Case 4: Duplicate eventId -> Accepted once, ignored second time
        # ---------------------------------------------------------------------
        dup_ev_id = f"sim_dup_{int(time.time() * 1000)}"
        dup_body = f'[{{"eventId": "{dup_ev_id}", "subscriptionType": "company.creation", "objectId": "comp_9002"}}]'.encode()
        dup_ts = str(int(time.time() * 1000))
        dup_sig = generate_v3_signature("POST", full_target_url, dup_body, dup_ts, test_secret)

        # First delivery
        res_dup1 = await client.post(
            endpoint_path,
            content=dup_body,
            headers={
                **base_headers,
                "X-HubSpot-Signature-v3": dup_sig,
                "X-HubSpot-Request-Timestamp": dup_ts,
            },
        )
        assert res_dup1.status_code == 200
        assert res_dup1.json()["events_accepted"] == 1

        # Second delivery (replay with same eventId)
        dup_ts2 = str(int(time.time() * 1000))
        dup_sig2 = generate_v3_signature("POST", full_target_url, dup_body, dup_ts2, test_secret)
        res_dup2 = await client.post(
            endpoint_path,
            content=dup_body,
            headers={
                **base_headers,
                "X-HubSpot-Signature-v3": dup_sig2,
                "X-HubSpot-Request-Timestamp": dup_ts2,
            },
        )
        assert res_dup2.status_code == 200
        data_dup2 = res_dup2.json()
        assert data_dup2["events_accepted"] == 0
        assert data_dup2["duplicates_ignored"] == 1
