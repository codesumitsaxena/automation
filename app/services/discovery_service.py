"""Contact discovery service with dual-layer job-title filtering and CRM association."""

import json
import re

from app.clients.forager_client import ForagerClient, ForagerCreditCosts
from app.clients.hubspot_client import HubSpotClient
from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import EnrichmentLog
from app.logging_config import setup_logging
from app.models.schemas import NormalizedContactData
from app.services.credit_guard import CreditGuard
from app.services.mapper import DataMapper

settings = get_settings()
logger = setup_logging(settings.log_level)


ACRONYM_EXPANSIONS = {
    "ceo": ["chief executive officer", "ceo"],
    "cto": ["chief technology officer", "cto"],
    "coo": ["chief operating officer", "coo"],
    "cfo": ["chief financial officer", "cfo"],
    "cmo": ["chief marketing officer", "cmo"],
    "cro": ["chief revenue officer", "cro"],
    "cio": ["chief information officer", "cio"],
    "cso": ["chief strategy officer", "chief security officer", "cso"],
    "vp": ["vice president", "vp", "svp", "evp", "avp"],
    "head": ["head of", "head"],
    "director": ["director", "dir"],
    "founder": ["founder", "co-founder"],
    "president": ["president"],
}


def matches_title_filter(title: str | None, approved_keywords: list[str]) -> bool:
    """Evaluate whether a job title matches any of the approved filter keywords.

    Performs case-insensitive keyword matching with boundary awareness and
    executive acronym expansion (e.g. CEO matches Chief Executive Officer, VP matches Vice President).
    """
    if not title:
        return False
    if not approved_keywords:
        return True

    title_normalized = title.lower().strip()

    # Build comprehensive search tokens including acronym expansions
    search_tokens = set()
    for kw in approved_keywords:
        kw_norm = kw.lower().strip()
        if not kw_norm:
            continue
        search_tokens.add(kw_norm)
        # Add expansions if keyword is a known abbreviation
        if kw_norm in ACRONYM_EXPANSIONS:
            search_tokens.update(ACRONYM_EXPANSIONS[kw_norm])
        # Also check reverse (e.g. if keyword is 'chief executive officer', add 'ceo')
        for acr, syns in ACRONYM_EXPANSIONS.items():
            if kw_norm in syns:
                search_tokens.add(acr)
                search_tokens.update(syns)

    for token in search_tokens:
        # Strictly enforce word boundaries so 'VP' does not match 'VPN Engineer',
        # and 'Director' does not match 'Redirector'
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, title_normalized):
            return True

    return False




class DiscoveryService:
    """Discovers professionals at target companies, applies job-title filters, and links them in HubSpot."""

    def __init__(
        self,
        forager_client: ForagerClient | None = None,
        hubspot_client: HubSpotClient | None = None,
        credit_guard: CreditGuard | None = None,
    ):
        self.forager = forager_client or ForagerClient()
        self.hubspot = hubspot_client or HubSpotClient()
        self.credit_guard = credit_guard or CreditGuard()

    async def discover_contacts(
        self,
        company_domain: str,
        job_titles: list[str] | None = None,
        seniority: list[str] | None = None,
        limit: int = 5,
        hubspot_company_id: str | None = None,
        add_to_hubspot: bool = True,
        run_id: str | None = None,
    ) -> list[NormalizedContactData]:
        """Find and filter contacts at a target company domain, optionally creating and linking in HubSpot."""
        target_titles = job_titles or settings.title_filters_list
        logger.info(
            "Starting contact discovery for %s with title filters: %s (limit: %d)",
            company_domain,
            target_titles,
            limit,
        )

        # 1. Query Forager (Layer 1 filter: first title keyword or general domain search)
        primary_title_query = target_titles[0] if target_titles else None

        # 2. Deduct credit for search operation (cache-hit aware)
        is_cached = self.forager.is_people_search_cached(company_domain, primary_title_query)
        credits_needed = 0 if is_cached else ForagerCreditCosts.PERSON_ROLE_SEARCH

        self.credit_guard.check_and_deduct(
            operation="people_search",
            target=company_domain,
            credits_needed=credits_needed,
            run_id=run_id,
            is_cache_hit=is_cached,
        )

        raw_people = await self.forager.search_people_by_company(
            domain=company_domain,
            role_title=primary_title_query,
            page=0,
        )

        logger.info("Forager returned %d candidate profiles for %s", len(raw_people), company_domain)

        # 3. Layer 2 Deterministic Filter & Data Completeness Prioritization
        complete_contacts: list[NormalizedContactData] = []
        partial_contacts: list[NormalizedContactData] = []
        seen_identifiers = set()

        for raw_person in raw_people:
            title = raw_person.get("role_title") or raw_person.get("title") or ""
            # Apply strict title match
            if not matches_title_filter(title, target_titles):
                logger.debug("Excluded candidate '%s' with title '%s' (did not match filter)", raw_person.get("full_name"), title)
                continue

            # Check seniority filter if provided
            if seniority:
                person_seniority = str(raw_person.get("seniority", "")).lower()
                if not any(s.lower() in person_seniority for s in seniority):
                    logger.debug("Excluded candidate '%s' due to seniority filter", raw_person.get("full_name"))
                    continue

            # Deduplication by email or linkedin identifier
            identifier = (
                raw_person.get("email")
                or raw_person.get("linkedin_public_identifier")
                or raw_person.get("full_name")
            )
            if identifier in seen_identifiers:
                continue
            seen_identifiers.add(identifier)

            # Normalize contact record
            contact_data = DataMapper.forager_to_normalized_contact(raw_person)

            # Check for contact completeness (email and phone)
            has_email = bool(contact_data.email and contact_data.email.strip())
            has_phone = bool(contact_data.phone and contact_data.phone.strip())

            if has_email and has_phone:
                complete_contacts.append(contact_data)
            else:
                logger.info(
                    "Candidate '%s %s' (%s) missing %s in Forager record. Seeking next candidate...",
                    contact_data.firstname,
                    contact_data.lastname,
                    contact_data.jobtitle,
                    "email and phone" if (not has_email and not has_phone) else ("email" if not has_email else "phone"),
                )
                partial_contacts.append(contact_data)

            if len(complete_contacts) >= limit:
                break

        # Select top candidates, prioritizing complete records
        filtered_contacts = complete_contacts[:limit]
        if len(filtered_contacts) < limit:
            remaining_slots = limit - len(filtered_contacts)
            logger.warning(
                "Only %d fully complete contact(s) found in candidate pool for %s. "
                "Filling remaining %d slot(s) with available candidates and reporting data gaps honestly (zero fake data).",
                len(filtered_contacts),
                company_domain,
                remaining_slots,
            )
            filtered_contacts.extend(partial_contacts[:remaining_slots])

        logger.info(
            "Discovered %d contacts matching job-title criteria for %s (%d complete, %d with data gaps)",
            len(filtered_contacts),
            company_domain,
            len([c for c in filtered_contacts if c.email and c.phone]),
            len([c for c in filtered_contacts if not (c.email and c.phone)]),
        )

        # 4. Create and associate in HubSpot if requested
        if add_to_hubspot:
            for contact in filtered_contacts:
                contact.hubspot_id = await self._persist_and_associate_contact(
                    contact=contact,
                    hubspot_company_id=hubspot_company_id,
                )

        return filtered_contacts

    async def _persist_and_associate_contact(
        self,
        contact: NormalizedContactData,
        hubspot_company_id: str | None = None,
    ) -> str | None:
        """Create or update contact in HubSpot and associate with target company."""
        props = DataMapper.contact_to_hubspot_properties(contact)
        # Mark as mock_demo in mock runs, or discovered in live runs to prevent webhook loop
        props["forager_status"] = "mock_demo" if self.forager.dry_run else "discovered"

        contact_id = None
        email = contact.email
        linkedin_url = contact.person_linkedin_url

        existing = None
        # 1. Check if contact already exists by email
        if email:
            existing = await self.hubspot.search_contact_by_email(email)

        # 2. If not found by email or no email, check by LinkedIn URL
        if not existing and linkedin_url:
            existing = await self.hubspot.search_contact_by_linkedin_url(linkedin_url)

        if existing and existing.get("id"):
            contact_id = existing["id"]
            logger.info("Contact %s already exists in HubSpot (id=%s). Updating.", email or linkedin_url, contact_id)
            await self.hubspot.update_contact(contact_id, props)
        else:
            res = await self.hubspot.create_contact(props)
            contact_id = res.get("id")
            logger.info("Created new HubSpot contact %s (id=%s)", email or linkedin_url or contact.firstname, contact_id)


        # Associate with company if company ID is available
        if contact_id and hubspot_company_id:
            associated = await self.hubspot.associate_contact_to_company(
                contact_id=contact_id,
                company_id=hubspot_company_id,
            )
            logger.info("Association contact %s -> company %s: success=%s", contact_id, hubspot_company_id, associated)

        # Audit log in SQLite
        with SessionLocal() as db:
            log_entry = EnrichmentLog(
                entity_type="contact",
                entity_id=contact_id,
                identifier=email or f"{contact.firstname}_{contact.lastname}",
                status="DISCOVERED",
                message=f"Discovered via title filter for company {contact.company_domain}",
                details_json=json.dumps({"title": contact.jobtitle, "company_id": hubspot_company_id}),
            )
            db.add(log_entry)
            db.commit()

        return contact_id
