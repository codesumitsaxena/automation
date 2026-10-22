"""End-to-end orchestration uniting Webhooks, Company Enrichment, Contact Discovery, and CRM Associations."""

import uuid
from typing import Any

from app.clients.forager_client import ForagerClient
from app.clients.hubspot_client import HubSpotClient
from app.config import get_settings
from app.logging_config import setup_logging
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService
from app.services.credit_guard import CreditGuard
from app.services.discovery_service import DiscoveryService

settings = get_settings()
logger = setup_logging(settings.log_level)


class OrchestrationService:
    """Coordinates multi-step enrichment workflows and webhook execution."""

    def __init__(
        self,
        forager_client: ForagerClient | None = None,
        hubspot_client: HubSpotClient | None = None,
    ):
        self.forager = forager_client or ForagerClient()
        self.hubspot = hubspot_client or HubSpotClient()
        self.credit_guard = CreditGuard()
        self.company_service = CompanyService(self.forager, self.hubspot, self.credit_guard)
        self.contact_service = ContactService(self.forager, self.hubspot, self.credit_guard)
        self.discovery_service = DiscoveryService(self.forager, self.hubspot, self.credit_guard)

    async def handle_company_webhook(self, company_id: str) -> dict[str, Any]:
        """Execute full Company Webhook Flow.

        1. Fetch company from HubSpot -> extract domain.
        2. Enrich company firmographics.
        3. Check associated contacts:
           - If contacts exist -> enrich each.
           - If no contacts exist -> discover, filter by job titles, create, and associate.
        """
        run_id = f"comp_wh_{company_id}_{str(uuid.uuid4())[:6]}"
        logger.info(">>> [WEBHOOK FLOW] Handling company.creation event for company_id=%s (run=%s)", company_id, run_id)

        # 1. Fetch Company from HubSpot
        company_record = await self.hubspot.get_company(company_id)
        if not company_record:
            logger.error("Company %s not found in HubSpot.", company_id)
            return {"success": False, "error": f"Company {company_id} not found in HubSpot"}

        props = company_record.get("properties", {})
        domain = props.get("domain") or props.get("website")
        if domain:
            # Strip protocol and paths if website was used
            domain = domain.replace("https://", "").replace("http://", "").split("/")[0].strip().lower()

        if not domain:
            logger.warning("Company %s has no domain or website set. Cannot enrich via Forager.", company_id)
            return {"success": False, "error": "Company has no domain property populated"}

        # 2. Enrich Company
        comp_res = await self.company_service.enrich_company(
            domain=domain,
            hubspot_company_id=company_id,
            run_id=run_id,
        )

        # 3. Check Associated Contacts
        associated_contacts = await self.hubspot.get_associated_contacts_for_company(company_id)
        contacts_enriched_count = 0
        contacts_discovered_count = 0

        if associated_contacts and len(associated_contacts) > 0:
            logger.info("Found %d existing contacts associated with company %s. Enriching each.", len(associated_contacts), company_id)
            for assoc in associated_contacts:
                cid = assoc.get("id") or str(assoc.get("toObjectId"))
                if cid:
                    cont_res = await self.contact_service.enrich_contact(
                        hubspot_contact_id=cid,
                        company_domain=domain,
                        run_id=run_id,
                    )
                    if cont_res.get("success") and cont_res.get("status") == "SUCCESS":
                        contacts_enriched_count += 1
        else:
            # 4. No contacts exist: Run Contact Discovery with Title Filters
            logger.info("No associated contacts found for company %s. Initiating discovery at %s.", company_id, domain)
            discovered = await self.discovery_service.discover_contacts(
                company_domain=domain,
                job_titles=settings.title_filters_list,
                limit=settings.default_contact_limit,
                hubspot_company_id=company_id,
                add_to_hubspot=True,
                run_id=run_id,
            )
            contacts_discovered_count = len(discovered)

        logger.info(
            "<<< [WEBHOOK FLOW COMPLETE] Company %s (%s): enriched=%s, existing_contacts_enriched=%d, discovered_contacts=%d",
            company_id,
            domain,
            comp_res.get("success"),
            contacts_enriched_count,
            contacts_discovered_count,
        )

        return {
            "success": True,
            "company_id": company_id,
            "domain": domain,
            "company_result": comp_res,
            "contacts_enriched": contacts_enriched_count,
            "contacts_discovered": contacts_discovered_count,
        }

    async def handle_contact_webhook(self, contact_id: str) -> dict[str, Any]:
        """Execute full Contact Webhook Flow with infinite-loop prevention."""
        run_id = f"cont_wh_{contact_id}_{str(uuid.uuid4())[:6]}"
        logger.info(">>> [WEBHOOK FLOW] Handling contact.creation event for contact_id=%s (run=%s)", contact_id, run_id)

        # Fetch contact from HubSpot to check status
        contact_record = await self.hubspot.get_contact(contact_id)
        if not contact_record:
            logger.error("Contact %s not found in HubSpot.", contact_id)
            return {"success": False, "error": f"Contact {contact_id} not found in HubSpot"}

        props = contact_record.get("properties", {})
        status = props.get("forager_status")

        # Infinite Loop Prevention:
        # If this contact was created by our own discovery step, its status is 'discovered'.
        # We mark it processed and exit to prevent looping.
        if status == "discovered":
            logger.info("Contact %s was created by discovery step. Skipping webhook to prevent loop.", contact_id)
            return {
                "success": True,
                "status": "LOOP_PREVENTED",
                "message": "Contact created by automated discovery; webhook loop avoided",
            }

        # Otherwise, enrich contact
        res = await self.contact_service.enrich_contact(
            hubspot_contact_id=contact_id,
            run_id=run_id,
        )

        logger.info("<<< [WEBHOOK FLOW COMPLETE] Contact %s enrichment status: %s", contact_id, res.get("status"))
        return res

    async def run_openai_demo(
        self,
        domain: str = "openai.com",
        limit: int = 5,
        job_titles: list[str] | None = None,
    ) -> dict[str, Any]:
        """Execute the primary hiring evaluation deliverable: OpenAI + 5 enriched people."""
        demo_run_id = f"demo_openai_{str(uuid.uuid4())[:6]}"
        logger.info("=================================================================")
        logger.info("RUNNING PRIMARY EVALUATION DEMO: %s (limit: %d)", domain, limit)
        logger.info("=================================================================")

        # 1. Enrich OpenAI Company
        comp_res = await self.company_service.enrich_company(
            domain=domain,
            force=True,
            run_id=demo_run_id,
        )
        company_id = comp_res.get("company_id")

        # 2. Discover and Enrich 5 Leadership Contacts
        target_titles = job_titles or settings.title_filters_list
        discovered_people = await self.discovery_service.discover_contacts(
            company_domain=domain,
            job_titles=target_titles,
            limit=limit,
            hubspot_company_id=company_id,
            add_to_hubspot=True,
            run_id=demo_run_id,
        )

        # Format clean summary
        summary_contacts = [
            {
                "name": f"{p.firstname} {p.lastname}",
                "job_title": p.jobtitle,
                "email": p.email,
                "phone": p.phone,
                "location": f"{p.city}, {p.state}, {p.country}",
                "company_domain": p.company_domain or domain,
                "linkedin_url": p.person_linkedin_url,
                "headline": p.forager_headline,
            }
            for p in discovered_people
        ]

        logger.info("Demo execution completed successfully. %d people enriched under OpenAI.", len(summary_contacts))

        return {
            "success": True,
            "company": comp_res.get("normalized"),
            "company_id": company_id,
            "contacts_count": len(summary_contacts),
            "contacts": summary_contacts,
            "run_id": demo_run_id,
            "dry_run": settings.dry_run,
        }
