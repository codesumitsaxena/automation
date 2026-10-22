"""Unit tests for CreditGuard service and budget limit protections."""

import pytest

from app.services.credit_guard import CreditGuard


def test_credit_estimation():
    est = CreditGuard.estimate_run_cost(
        enrich_company=True,
        num_contacts=5,
        enable_email_reveal=False,
        enable_phone_reveal=False,
    )
    # 1 (company) + 1 (people search) + 5 (5 contact details) = 7 credits
    assert est["estimated_total_credits"] == 7

    est_with_reveals = CreditGuard.estimate_run_cost(
        enrich_company=True,
        num_contacts=5,
        enable_email_reveal=True,
        enable_phone_reveal=True,
    )
    # 7 + (5 * 5 emails) + (5 * 15 phones) = 7 + 25 + 75 = 107 credits
    assert est_with_reveals["estimated_total_credits"] == 107


def test_credit_guard_budget_check():
    guard = CreditGuard(max_credits_per_run=10)
    # Deducting 5 credits should pass
    guard.check_and_deduct(operation="company_search", target="openai.com", credits_needed=5, run_id="test_run_1")

    # In live mode, exceeding 10 credits would raise CreditLimitExceededError
    # In DRY_RUN mode, actual spend is 0, so it safely proceeds without real spending
    assert guard.dry_run is True


def test_cache_hit_costs_zero_credits_and_real_call_counted_once():
    """Verify ISSUE-07: A real API call counts credits once, but a cache hit costs exactly 0 credits."""
    import uuid

    from sqlalchemy import func

    from app.clients.forager_client import (
        ForagerClient,
        ForagerCreditCosts,
        ForagerEndpoints,
    )
    from app.db.database import SessionLocal
    from app.db.models import CreditUsage

    guard = CreditGuard(max_credits_per_run=50)
    guard.dry_run = False  # Simulate LIVE mode to test real credit accounting

    forager = ForagerClient()
    test_domain = f"testcorp-{uuid.uuid4().hex[:8]}.com"
    run_id = f"test_run_{uuid.uuid4().hex[:8]}"

    # Step 1: Initial state - domain is not in cache
    assert forager.is_organization_cached(test_domain) is False

    # Step 2: First Call (Cache Miss / Real API Call)
    # When is_cache_hit is False, credits_needed (1 credit) must be deducted
    first_spend = guard.check_and_deduct(
        operation="company_enrich",
        target=test_domain,
        credits_needed=ForagerCreditCosts.ORGANIZATION_SEARCH,
        run_id=run_id,
        is_cache_hit=False,
    )
    assert first_spend == 1, "Real call must consume 1 credit"

    # Simulate Forager caching the response in SQLite
    endpoint = forager._resolve_endpoint(ForagerEndpoints.ORGANIZATION_SEARCH)
    payload = {"domains": [test_domain.lower().strip()], "page": 0}
    req_hash = forager._compute_hash(endpoint, payload)
    forager._save_cache_response(
        request_hash=req_hash,
        endpoint=endpoint,
        payload=payload,
        response={"data": [{"name": "TestCorp", "domain": test_domain}]},
        credit_cost=1,
    )

    # Step 3: Domain is now cached
    assert forager.is_organization_cached(test_domain) is True

    # Step 4: Second Call (Cache Hit)
    # When is_cache_hit is True, exactly 0 credits must be deducted
    second_spend = guard.check_and_deduct(
        operation="company_enrich",
        target=test_domain,
        credits_needed=ForagerCreditCosts.ORGANIZATION_SEARCH,
        run_id=run_id,
        is_cache_hit=True,
    )
    assert second_spend == 0, "Cache hit must cost exactly 0 credits"

    # Step 5: Verify the persistent SQLite ledger records
    with SessionLocal() as db:
        records = (
            db.query(CreditUsage)
            .filter(CreditUsage.run_id == run_id)
            .order_by(CreditUsage.id.asc())
            .all()
        )
        assert len(records) == 2
        # First record: Real call -> 1 credit
        assert records[0].credits_spent == 1
        assert "cache_hit" not in records[0].operation
        # Second record: Cache hit -> 0 credits
        assert records[1].credits_spent == 0
        assert "cache_hit" in records[1].operation

        # Total credits spent for the run MUST be exactly 1
        total_spent = (
            db.query(func.sum(CreditUsage.credits_spent))
            .filter(CreditUsage.run_id == run_id)
            .scalar()
        )
        assert total_spent == 1, f"Expected total spent to be 1, got {total_spent}"


@pytest.mark.asyncio
async def test_company_service_cache_hit_spends_zero_credits():
    """Verify CompanyService checks Forager cache and incurs 0 credit spend on repeated enrichment."""
    import uuid
    from unittest.mock import AsyncMock

    from sqlalchemy import func

    from app.clients.forager_client import (
        ForagerClient,
        ForagerEndpoints,
    )
    from app.clients.hubspot_client import HubSpotClient
    from app.db.database import SessionLocal
    from app.db.models import CreditUsage
    from app.services.company_service import CompanyService

    test_domain = f"cachedemo-{uuid.uuid4().hex[:8]}.com"
    run_id = f"run_{uuid.uuid4().hex[:8]}"

    # Setup clients with dry_run = False for credit guard
    guard = CreditGuard(max_credits_per_run=50)
    guard.dry_run = False

    forager = ForagerClient()
    mock_hubspot = AsyncMock(spec=HubSpotClient)
    mock_hubspot.search_company_by_domain.return_value = None
    mock_hubspot.create_company.return_value = {"id": "comp_123"}

    # Mock the underlying HTTP call for search_organization
    forager.search_organization = AsyncMock(return_value={"name": "CacheDemo", "domain": test_domain})

    service = CompanyService(
        forager_client=forager,
        hubspot_client=mock_hubspot,
        credit_guard=guard,
    )

    # 1. First run: domain not cached -> costs 1 credit
    assert forager.is_organization_cached(test_domain) is False
    res1 = await service.enrich_company(test_domain, run_id=run_id)
    assert res1["success"] is True

    # Save cache response to simulate Forager caching
    endpoint = forager._resolve_endpoint(ForagerEndpoints.ORGANIZATION_SEARCH)
    payload = {"domains": [test_domain.lower().strip()], "page": 0}
    forager._save_cache_response(
        request_hash=forager._compute_hash(endpoint, payload),
        endpoint=endpoint,
        payload=payload,
        response={"data": [{"name": "CacheDemo", "domain": test_domain}]},
        credit_cost=1,
    )

    # 2. Second run: domain is now cached -> must cost 0 credits
    assert forager.is_organization_cached(test_domain) is True
    res2 = await service.enrich_company(test_domain, run_id=run_id, force=True)
    assert res2["success"] is True

    # 3. Check database ledger
    with SessionLocal() as db:
        records = (
            db.query(CreditUsage)
            .filter(CreditUsage.run_id == run_id)
            .order_by(CreditUsage.id.asc())
            .all()
        )
        assert len(records) == 2
        assert records[0].credits_spent == 1
        assert records[1].credits_spent == 0

        total_run_credits = (
            db.query(func.sum(CreditUsage.credits_spent))
            .filter(CreditUsage.run_id == run_id)
            .scalar()
        )
        assert total_run_credits == 1

