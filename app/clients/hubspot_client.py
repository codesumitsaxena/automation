"""HubSpot CRM API v3 client for companies, contacts, associations, and schema management."""

from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.logging_config import setup_logging

settings = get_settings()
logger = setup_logging(settings.log_level)


def is_hubspot_transient_error(exc: BaseException) -> bool:
    """Detect rate limits (429) or transient 5xx HubSpot errors."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class HubSpotClient:
    """Async client interfacing with HubSpot CRM v3 REST APIs."""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, access_token: str | None = None):
        self.access_token = access_token or settings.hubspot_access_token
        # Respect HUBSPOT_DRY_RUN: Only go live if hubspot_dry_run is False and token is configured
        if not settings.hubspot_dry_run:
            if settings.is_configured_for_live_hubspot():
                self.is_live = True
                logger.info("[HUBSPOT LIVE] Real HubSpot CRM connection active.")
            else:
                logger.warning(
                    "HUBSPOT_DRY_RUN is False, but HUBSPOT_ACCESS_TOKEN is not configured! "
                    "Falling back to mock HubSpot mode."
                )
                self.is_live = False
        else:
            self.is_live = False
        self._simulated_counter = 1000
        # In-memory registry for DRY_RUN only (preserves state across demo re-runs)
        self._simulated_contacts: dict[str, dict[str, Any]] = {}
        self._simulated_companies: dict[str, dict[str, Any]] = {}

    def _get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    @retry(
        retry=retry_if_exception(is_hubspot_transient_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an authenticated HTTP request to HubSpot API."""
        url = f"{self.BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                params=params,
                json=json_body,
            )
            if response.status_code == 404:
                return {}
            response.raise_for_status()
            if response.status_code == 204:
                return {}
            return response.json()

    # -------------------------------------------------------------------------
    # Companies API
    # -------------------------------------------------------------------------

    async def get_company(self, company_id: str, properties: list[str] | None = None) -> dict[str, Any] | None:
        """Fetch company by HubSpot ID."""
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] get_company id=%s", company_id)
            if company_id in self._simulated_companies:
                return self._simulated_companies[company_id]
            return {
                "id": company_id,
                "properties": {
                    "name": "OpenAI",
                    "domain": "openai.com",
                    "forager_status": "pending",
                },
            }

        props = properties or [
            "name", "domain", "website", "description", "numberofemployees",
            "annualrevenue", "industry", "linkedin_company_page", "forager_status",
            "forager_enriched_at"
        ]
        params = {"properties": ",".join(props)}
        res = await self._request("GET", f"/crm/v3/objects/companies/{company_id}", params=params)
        return res if res.get("id") else None

    async def search_company_by_domain(self, domain: str) -> dict[str, Any] | None:
        """Search for existing company by domain property."""
        clean_domain = domain.strip().lower()
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] search_company_by_domain domain=%s", clean_domain)
            for comp in self._simulated_companies.values():
                if comp.get("properties", {}).get("domain", "").lower() == clean_domain:
                    return comp
            if "openai" in clean_domain:
                record = {
                    "id": "mock_company_openai_001",
                    "properties": {"domain": clean_domain, "name": "OpenAI"},
                }
                self._simulated_companies["mock_company_openai_001"] = record
                return record
            return None

        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "domain",
                            "operator": "EQ",
                            "value": clean_domain,
                        }
                    ]
                }
            ],
            "properties": ["name", "domain", "forager_status", "forager_enriched_at"],
            "limit": 1,
        }
        res = await self._request("POST", "/crm/v3/objects/companies/search", json_body=body)
        results = res.get("results", [])
        return results[0] if results else None

    async def create_company(self, properties: dict[str, Any]) -> dict[str, Any]:
        """Create a new company in HubSpot."""
        if not self.is_live:
            self._simulated_counter += 1
            cid = f"sim_comp_{self._simulated_counter}"
            record = {"id": cid, "properties": dict(properties)}
            self._simulated_companies[cid] = record
            logger.info("[MOCK HUBSPOT] Created company %s with %d properties", cid, len(properties))
            return record

        body = {"properties": properties}
        return await self._request("POST", "/crm/v3/objects/companies", json_body=body)

    async def update_company(self, company_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Update properties on an existing company."""
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] Updated company %s with %d properties", company_id, len(properties))
            if company_id in self._simulated_companies:
                self._simulated_companies[company_id]["properties"].update(properties)
                return self._simulated_companies[company_id]
            return {"id": company_id, "properties": properties}

        body = {"properties": properties}
        return await self._request("PATCH", f"/crm/v3/objects/companies/{company_id}", json_body=body)

    # -------------------------------------------------------------------------
    # Contacts API
    # -------------------------------------------------------------------------

    async def get_contact(self, contact_id: str, properties: list[str] | None = None) -> dict[str, Any] | None:
        """Fetch contact by HubSpot ID."""
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] get_contact id=%s", contact_id)
            if contact_id in self._simulated_contacts:
                return self._simulated_contacts[contact_id]
            return {
                "id": contact_id,
                "properties": {
                    "firstname": "Sam",
                    "lastname": "Altman",
                    "email": "sam@openai.com",
                    "company": "OpenAI",
                    "jobtitle": "CEO",
                },
            }

        props = properties or [
            "firstname", "lastname", "email", "phone", "jobtitle", "company",
            "city", "state", "country", "forager_status", "forager_enriched_at",
            "person_linkedin_url"
        ]
        params = {"properties": ",".join(props)}
        res = await self._request("GET", f"/crm/v3/objects/contacts/{contact_id}", params=params)
        return res if res.get("id") else None

    async def search_contact_by_email(self, email: str) -> dict[str, Any] | None:
        """Search for contact by email address."""
        clean_email = email.strip().lower()
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] search_contact_by_email email=%s", clean_email)
            for cont in self._simulated_contacts.values():
                if cont.get("properties", {}).get("email", "").lower() == clean_email:
                    return cont
            return None

        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "email",
                            "operator": "EQ",
                            "value": clean_email,
                        }
                    ]
                }
            ],
            "properties": ["firstname", "lastname", "email", "jobtitle", "person_linkedin_url", "forager_status"],
            "limit": 1,
        }
        res = await self._request("POST", "/crm/v3/objects/contacts/search", json_body=body)
        results = res.get("results", [])
        return results[0] if results else None

    async def search_contact_by_linkedin_url(self, linkedin_url: str) -> dict[str, Any] | None:
        """Search for contact by LinkedIn URL (checks person_linkedin_url or hs_linkedin_url)."""
        clean_url = linkedin_url.strip().lower().rstrip("/")
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] search_contact_by_linkedin_url url=%s", clean_url)
            for cont in self._simulated_contacts.values():
                props = cont.get("properties", {})
                p_url = str(props.get("person_linkedin_url") or props.get("hs_linkedin_url") or "").lower().rstrip("/")
                if p_url and p_url == clean_url:
                    return cont
            return None

        body = {
            "filterGroups": [
                {
                    "filters": [
                        {
                            "propertyName": "person_linkedin_url",
                            "operator": "EQ",
                            "value": linkedin_url.strip(),
                        }
                    ]
                },
                {
                    "filters": [
                        {
                            "propertyName": "hs_linkedin_url",
                            "operator": "EQ",
                            "value": linkedin_url.strip(),
                        }
                    ]
                }
            ],
            "properties": ["firstname", "lastname", "email", "jobtitle", "person_linkedin_url", "forager_status"],
            "limit": 1,
        }
        res = await self._request("POST", "/crm/v3/objects/contacts/search", json_body=body)
        results = res.get("results", [])
        return results[0] if results else None

    async def create_contact(self, properties: dict[str, Any]) -> dict[str, Any]:
        """Create a new contact in HubSpot."""
        if not self.is_live:
            self._simulated_counter += 1
            cid = f"sim_cont_{self._simulated_counter}"
            record = {"id": cid, "properties": dict(properties)}
            self._simulated_contacts[cid] = record
            logger.info("[MOCK HUBSPOT] Created contact %s (%s)", cid, properties.get("email"))
            return record

        body = {"properties": properties}
        return await self._request("POST", "/crm/v3/objects/contacts", json_body=body)

    async def update_contact(self, contact_id: str, properties: dict[str, Any]) -> dict[str, Any]:
        """Update properties on an existing contact."""
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] Updated contact %s with %d properties", contact_id, len(properties))
            if contact_id in self._simulated_contacts:
                self._simulated_contacts[contact_id]["properties"].update(properties)
                return self._simulated_contacts[contact_id]
            return {"id": contact_id, "properties": properties}

        body = {"properties": properties}
        return await self._request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", json_body=body)


    # -------------------------------------------------------------------------
    # Associations API
    # -------------------------------------------------------------------------

    async def associate_contact_to_company(self, contact_id: str, company_id: str) -> bool:
        """Associate contact with company using standard association type."""
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] Associated contact %s -> company %s", contact_id, company_id)
            return True

        url = f"/crm/v3/objects/contacts/{contact_id}/associations/companies/{company_id}/contact_to_company"
        try:
            await self._request("PUT", url)
            return True
        except Exception as e:
            logger.error("Failed to associate contact %s with company %s: %s", contact_id, company_id, str(e))
            return False

    async def get_associated_contacts_for_company(self, company_id: str) -> list[dict[str, Any]]:
        """Get all contact IDs associated with a company."""
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] get_associated_contacts_for_company id=%s", company_id)
            return []

        url = f"/crm/v3/objects/companies/{company_id}/associations/contacts"
        res = await self._request("GET", url)
        return res.get("results", [])

    # -------------------------------------------------------------------------
    # Custom Schema & Property Management
    # -------------------------------------------------------------------------

    async def create_property_group(self, object_type: str, name: str, label: str) -> dict[str, Any]:
        """Create a custom property group (e.g. Forager Enrichment)."""
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] create_property_group %s -> %s", object_type, label)
            return {"name": name, "label": label}

        body = {"name": name, "label": label}
        try:
            return await self._request("POST", f"/crm/v3/properties/{object_type}/groups", json_body=body)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:  # Already exists
                logger.debug("Property group %s already exists for %s", name, object_type)
                return {"name": name, "label": label}
            raise

    async def create_property(self, object_type: str, property_def: dict[str, Any]) -> dict[str, Any]:
        """Create a custom property for companies or contacts."""
        prop_name = property_def.get("name")
        if not self.is_live:
            logger.info("[MOCK HUBSPOT] create_property %s.%s", object_type, prop_name)
            return property_def

        try:
            return await self._request("POST", f"/crm/v3/properties/{object_type}", json_body=property_def)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:  # Already exists
                logger.debug("Property %s.%s already exists", object_type, prop_name)
                return property_def
            raise
