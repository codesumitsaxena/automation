import re
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
)


def validate_and_normalize_domain(value: Any) -> str:
    """Validate domain syntax and normalize by stripping scheme, www, and trailing paths.
    
    Accepts: 'openai.com', 'sub.example.co.uk', 'http://openai.com' (normalized to 'openai.com')
    Rejects: '', '   ', 'not a domain', 'invalid..com'
    """
    if value is None:
        raise ValueError("Domain cannot be None.")
    s = str(value).strip()
    if not s:
        raise ValueError("Domain cannot be empty or blank.")

    # Lowercase
    clean = s.lower()
    # Strip protocol if present
    clean = re.sub(r"^https?://", "", clean)
    # Strip www. prefix
    clean = re.sub(r"^www\.", "", clean)
    # Strip trailing path, port, or query string
    clean = clean.split("/")[0].split(":")[0].split("?")[0]

    if not DOMAIN_REGEX.match(clean):
        raise ValueError(
            f"Invalid domain format: '{value}'. Expected standard domain like 'openai.com' or 'sub.example.co.uk'."
        )

    return clean


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------

class CompanyEnrichRequest(BaseModel):
    """Payload to trigger enrichment for a company by domain."""
    domain: str = Field(..., description="Target company domain, e.g. openai.com")
    company_name: str | None = Field(default=None, description="Optional company name")
    hubspot_company_id: str | None = Field(
        default=None, description="HubSpot company ID if already existing"
    )

    @field_validator("domain")
    @classmethod
    def validate_domain(cls, v: str) -> str:
        return validate_and_normalize_domain(v)


class ContactEnrichRequest(BaseModel):
    """Payload to trigger enrichment for an individual contact."""
    email: str | None = Field(default=None, description="Work or personal email")
    linkedin_url: str | None = Field(default=None, description="Personal LinkedIn profile URL")
    first_name: str | None = Field(default=None, description="First name")
    last_name: str | None = Field(default=None, description="Last name")
    company_domain: str | None = Field(default=None, description="Domain of employer")
    hubspot_contact_id: str | None = Field(
        default=None, description="HubSpot contact ID if already existing"
    )

    @field_validator("company_domain")
    @classmethod
    def validate_opt_domain(cls, v: str | None) -> str | None:
        if v is None or not str(v).strip():
            return None
        return validate_and_normalize_domain(v)


class ContactDiscoveryRequest(BaseModel):
    """Payload to discover and optionally enrich contacts at a company with title filtering."""
    company_domain: str = Field(..., description="Domain of target company, e.g. openai.com")
    job_titles: list[str] | None = Field(
        default=None,
        description="List of target job titles (e.g. ['CEO', 'CTO', 'VP', 'Head of'])",
    )
    seniority: list[str] | None = Field(
        default=None,
        description="Optional seniority levels (e.g. ['c_level', 'vp', 'director'])",
    )
    limit: int = Field(default=5, ge=1, le=25, description="Number of contacts to return")
    hubspot_company_id: str | None = Field(
        default=None, description="HubSpot company ID to associate discovered contacts with"
    )
    add_to_hubspot: bool = Field(
        default=True,
        description="Whether to immediately create and associate records in HubSpot",
    )

    @field_validator("company_domain")
    @classmethod
    def validate_company_domain(cls, v: str) -> str:
        return validate_and_normalize_domain(v)


# -----------------------------------------------------------------------------
# Normalized Domain Models (Bridge between Forager and HubSpot)
# -----------------------------------------------------------------------------

class NormalizedCompanyData(BaseModel):
    """Clean, normalized company record ready for HubSpot insertion or updates."""
    name: str | None = None
    domain: str
    website: str | None = None
    description: str | None = None
    numberofemployees: str | None = None
    annualrevenue: str | None = None
    industry: str | None = None
    linkedin_company_page: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    founded_year: str | None = None
    forager_tech_stack: str | None = None
    forager_funding_total: str | None = None
    forager_revenue_range: str | None = None
    forager_status: str = "enriched"
    forager_enriched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    raw_forager_data: dict[str, Any] | None = None


class NormalizedContactData(BaseModel):
    """Clean, normalized person/contact record ready for HubSpot insertion or updates."""
    firstname: str | None = None
    lastname: str | None = None
    jobtitle: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    hubspot_id: str | None = None
    company: str | None = None
    company_domain: str | None = None
    company_linkedin_url: str | None = None
    person_linkedin_url: str | None = None
    # Nice-to-have extra fields for discussion
    forager_headline: str | None = None
    forager_about: str | None = None
    forager_skills: str | None = None
    forager_seniority: str | None = None
    forager_source_id: str | None = None
    forager_status: str = "enriched"
    forager_enriched_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    )
    raw_forager_data: dict[str, Any] | None = None


# -----------------------------------------------------------------------------
# Webhook Schemas
# -----------------------------------------------------------------------------

class HubSpotWebhookItem(BaseModel):
    """Individual event item inside a HubSpot webhook request batch."""
    eventId: int | str
    subscriptionType: str  # e.g. "company.creation", "contact.creation"
    portalId: int | None = None
    appId: int | None = None
    occurredAt: int | None = None
    objectId: int | str
    propertyName: str | None = None
    propertyValue: str | None = None
    changeFlag: str | None = None


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------

class ApiResponse(BaseModel):
    """Standard unified response wrapper."""
    success: bool
    message: str
    data: Any | None = None
    errors: list[str] | None = None


class StatsResponse(BaseModel):
    """Operational statistics for UI Dashboard."""
    dry_run: bool
    credits_remaining: int
    credits_used: int
    companies_enriched: int
    contacts_enriched: int
    webhooks_received: int
    recent_logs: list[dict[str, Any]]
