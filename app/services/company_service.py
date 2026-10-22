"""Company enrichment service interfacing between Forager and HubSpot."""

import json
from typing import Any

from app.clients.forager_client import ForagerClient, ForagerCreditCosts
from app.clients.hubspot_client import HubSpotClient
from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import EnrichmentLog
from app.logging_config import setup_logging
from app.services.credit_guard import CreditGuard
from app.services.mapper import DataMapper

settings = get_settings()
logger = setup_logging(settings.log_level)


class CompanyService:
    """Orchestrates company firmographic retrieval, validation, and CRM synchronization."""

    def __init__(
        self,
        forager_client: ForagerClient | None = None,
        hubspot_client: HubSpotClient | None = None,
        credit_guard: CreditGuard | None = None,
    ):
        self.forager = forager_client or ForagerClient()
        self.hubspot = hubspot_client or HubSpotClient()
        self.credit_guard = credit_guard or CreditGuard()

    async def enrich_company(
        self,
        domain: str,
        hubspot_company_id: str | None = None,
        force: bool = False,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Enrich a company by domain, safely updating HubSpot records with full firmographics."""
        clean_domain = domain.lower().strip()
        logger.info("Starting company enrichment for domain '%s' (HubSpot ID: %s)", clean_domain, hubspot_company_id)

        # 1. Idempotency Check against HubSpot record
        target_company_id = hubspot_company_id
        if target_company_id and not force:
            hs_record = await self.hubspot.get_company(target_company_id)
            if hs_record:
                status = hs_record.get("properties", {}).get("forager_status")
                if status == "enriched":
                    logger.info("Company %s already marked 'enriched'. Skipping (idempotent).", clean_domain)
                    self._record_log("company", target_company_id, clean_domain, "SKIPPED", "Already enriched")
                    return {
                        "success": True,
                        "status": "SKIPPED",
                        "message": "Company already enriched in HubSpot",
                        "company_id": target_company_id,
                        "domain": clean_domain,
                    }

        # If no company ID provided, try finding existing by domain
        if not target_company_id:
            existing = await self.hubspot.search_company_by_domain(clean_domain)
            if existing and existing.get("id"):
                target_company_id = existing["id"]
                if not force and existing.get("properties", {}).get("forager_status") == "enriched":
                    logger.info("Found existing enriched company %s (id=%s). Skipping.", clean_domain, target_company_id)
                    return {
                        "success": True,
                        "status": "SKIPPED",
                        "message": "Company already enriched in HubSpot",
                        "company_id": target_company_id,
                        "domain": clean_domain,
                    }

        # 2. Check Credit Budget (incorporating cache hit awareness)
        is_cached = self.forager.is_organization_cached(clean_domain)
        credits_needed = 0 if is_cached else ForagerCreditCosts.ORGANIZATION_SEARCH

        self.credit_guard.check_and_deduct(
            operation="company_enrich",
            target=clean_domain,
            credits_needed=credits_needed,
            run_id=run_id,
            is_cache_hit=is_cached,
        )

        # 3. Fetch Firmographics from Forager
        raw_company = await self.forager.search_organization(clean_domain)
        if not raw_company:
            logger.warning("No Forager data found for company domain '%s'", clean_domain)
            self._record_log("company", target_company_id, clean_domain, "NOT_FOUND", "No record in Forager")
            return {
                "success": False,
                "status": "NOT_FOUND",
                "message": f"No Forager company data found for {clean_domain}",
                "domain": clean_domain,
            }

        # 4. Normalize and Map to HubSpot properties
        normalized_data = DataMapper.forager_to_normalized_company(raw_company)
        hubspot_props = DataMapper.company_to_hubspot_properties(normalized_data)
        if self.forager.dry_run:
            hubspot_props["forager_status"] = "mock_demo"

        # 5. Persist to HubSpot (Create or Update non-destructively)
        if target_company_id:
            logger.info("Updating existing HubSpot company %s with %d properties", target_company_id, len(hubspot_props))
            await self.hubspot.update_company(target_company_id, hubspot_props)
        else:
            logger.info("Creating new HubSpot company for domain %s with %d properties", clean_domain, len(hubspot_props))
            create_res = await self.hubspot.create_company(hubspot_props)
            target_company_id = create_res.get("id")

        self._record_log(
            "company",
            target_company_id,
            clean_domain,
            "SUCCESS",
            f"Successfully enriched company with {len(hubspot_props)} properties",
            details={"updated_properties": list(hubspot_props.keys())},
        )

        return {
            "success": True,
            "status": "SUCCESS",
            "company_id": target_company_id,
            "domain": clean_domain,
            "properties_updated": hubspot_props,
            "normalized": normalized_data.model_dump(),
        }

    def _record_log(
        self,
        entity_type: str,
        entity_id: str | None,
        identifier: str,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Write an audit entry into SQLite."""
        try:
            with SessionLocal() as db:
                entry = EnrichmentLog(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    identifier=identifier,
                    status=status,
                    message=message,
                    details_json=json.dumps(details or {}),
                )
                db.add(entry)
                db.commit()
        except Exception as e:
            logger.error("Failed to write enrichment log: %s", str(e))
