"""Contact enrichment service interfacing between Forager and HubSpot."""

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


class ContactService:
    """Orchestrates individual professional contact lookup, validation, and CRM synchronization."""

    def __init__(
        self,
        forager_client: ForagerClient | None = None,
        hubspot_client: HubSpotClient | None = None,
        credit_guard: CreditGuard | None = None,
    ):
        self.forager = forager_client or ForagerClient()
        self.hubspot = hubspot_client or HubSpotClient()
        self.credit_guard = credit_guard or CreditGuard()

    async def enrich_contact(
        self,
        email: str | None = None,
        linkedin_url: str | None = None,
        hubspot_contact_id: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        company_domain: str | None = None,
        force: bool = False,
        run_id: str | None = None,
    ) -> dict[str, Any]:
        """Enrich a contact record in HubSpot with complete professional details."""
        target_contact_id = hubspot_contact_id
        target_email = email.lower().strip() if email else None
        target_identifier = target_email or linkedin_url or f"{first_name}_{last_name}"

        logger.info(
            "Starting contact enrichment for identifier='%s' (HubSpot ID: %s)",
            target_identifier,
            target_contact_id,
        )

        # 1. Idempotency Check in HubSpot
        if target_contact_id:
            hs_record = await self.hubspot.get_contact(target_contact_id)
            if hs_record:
                status = hs_record.get("properties", {}).get("forager_status")
                # If already enriched, skip
                if status == "enriched" and not force:
                    logger.info("Contact %s already marked 'enriched'. Skipping (idempotent).", target_identifier)
                    self._record_log("contact", target_contact_id, target_identifier, "SKIPPED", "Already enriched")
                    return {
                        "success": True,
                        "status": "SKIPPED",
                        "message": "Contact already enriched in HubSpot",
                        "contact_id": target_contact_id,
                    }
                # Extract missing identifiers from HubSpot if not supplied in args
                props = hs_record.get("properties", {})
                if not target_email and props.get("email"):
                    target_email = props["email"].lower().strip()
                if not linkedin_url and props.get("person_linkedin_url"):
                    linkedin_url = props["person_linkedin_url"]
                if not company_domain and props.get("company_domain"):
                    company_domain = props["company_domain"]

        # If still no contact ID, check if exists in HubSpot by email
        if not target_contact_id and target_email:
            existing = await self.hubspot.search_contact_by_email(target_email)
            if existing and existing.get("id"):
                target_contact_id = existing["id"]
                if existing.get("properties", {}).get("forager_status") == "enriched" and not force:
                    logger.info("Existing contact %s is already enriched. Skipping.", target_email)
                    return {
                        "success": True,
                        "status": "SKIPPED",
                        "message": "Contact already enriched in HubSpot",
                        "contact_id": target_contact_id,
                    }

        # If still no contact ID, check if exists in HubSpot by LinkedIn URL
        if not target_contact_id and linkedin_url:
            existing = await self.hubspot.search_contact_by_linkedin_url(linkedin_url)
            if existing and existing.get("id"):
                target_contact_id = existing["id"]
                if existing.get("properties", {}).get("forager_status") == "enriched" and not force:
                    logger.info("Existing contact %s is already enriched. Skipping.", linkedin_url)
                    return {
                        "success": True,
                        "status": "SKIPPED",
                        "message": "Contact already enriched in HubSpot",
                        "contact_id": target_contact_id,
                    }


        # 2. Check Credit Budget (cache-hit aware)
        is_cached = False
        if target_email:
            is_cached = self.forager.is_email_lookup_cached(target_email)
        elif linkedin_url:
            slug = linkedin_url.rstrip("/").split("/")[-1]
            is_cached = self.forager.is_person_details_cached(linkedin_public_identifier=slug)
        elif company_domain:
            is_cached = self.forager.is_people_search_cached(company_domain)

        credits_needed = 0 if is_cached else ForagerCreditCosts.PERSON_DETAIL_LOOKUP

        self.credit_guard.check_and_deduct(
            operation="person_lookup",
            target=target_identifier,
            credits_needed=credits_needed,
            run_id=run_id,
            is_cache_hit=is_cached,
        )

        # 3. Fetch Person Record from Forager
        raw_person = None
        if target_email:
            raw_person = await self.forager.reverse_lookup_by_email(target_email)

        if not raw_person and linkedin_url:
            slug = linkedin_url.rstrip("/").split("/")[-1]
            raw_person = await self.forager.get_person_details(
                linkedin_public_identifier=slug,
                reveal_emails=settings.enable_email_reveal,
                reveal_phones=settings.enable_phone_reveal,
            )

        if not raw_person and company_domain:
            people = await self.forager.search_people_by_company(domain=company_domain)
            if people:
                # Find matching person by name if possible
                for p in people:
                    if first_name and p.get("first_name", "").lower() == first_name.lower():
                        raw_person = p
                        break
                if not raw_person:
                    raw_person = people[0]

        if not raw_person:
            logger.warning("No Forager record found for contact '%s'", target_identifier)
            self._record_log("contact", target_contact_id, target_identifier, "NOT_FOUND", "Profile not found in Forager")
            return {
                "success": False,
                "status": "NOT_FOUND",
                "message": f"Profile not found in Forager for {target_identifier}",
            }

        # 4. Normalize and Map to HubSpot properties
        normalized_contact = DataMapper.forager_to_normalized_contact(raw_person)
        hubspot_props = DataMapper.contact_to_hubspot_properties(normalized_contact)
        hubspot_props["forager_status"] = "enriched"

        # 5. Persist to HubSpot (Create or Update non-destructively)
        if target_contact_id:
            logger.info("Updating existing HubSpot contact %s with %d properties", target_contact_id, len(hubspot_props))
            await self.hubspot.update_contact(target_contact_id, hubspot_props)
        else:
            logger.info("Creating new HubSpot contact for %s with %d properties", target_identifier, len(hubspot_props))
            create_res = await self.hubspot.create_contact(hubspot_props)
            target_contact_id = create_res.get("id")

        self._record_log(
            "contact",
            target_contact_id,
            target_identifier,
            "SUCCESS",
            f"Successfully enriched contact with {len(hubspot_props)} properties",
            details={"email": normalized_contact.email, "title": normalized_contact.jobtitle},
        )

        return {
            "success": True,
            "status": "SUCCESS",
            "contact_id": target_contact_id,
            "identifier": target_identifier,
            "properties_updated": hubspot_props,
            "normalized": normalized_contact.model_dump(),
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
            logger.error("Failed to write contact enrichment log: %s", str(e))
