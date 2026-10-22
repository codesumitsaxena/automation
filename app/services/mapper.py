"""Data normalization and bidirectional mapping between Forager API payloads and HubSpot properties.

Implements non-destructive update rules: only maps non-empty values, never overwrites
existing data with empty or null fields.
"""

import re
from datetime import UTC, datetime
from typing import Any

from app.config import get_settings
from app.logging_config import setup_logging
from app.models.schemas import NormalizedCompanyData, NormalizedContactData

settings = get_settings()
logger = setup_logging(settings.log_level)


def _clean_str(val: Any) -> str | None:
    """Convert value to stripped string if non-empty, otherwise None."""
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _parse_revenue(estimated_val: Any, range_val: Any) -> tuple[str | None, str | None]:
    """Parse revenue into numeric string for HubSpot annualrevenue and retain raw range string.
    
    If given a range like '$1B to $5B', calculates the numeric midpoint (e.g. '3000000000')
    and stores the original range text for custom property 'forager_revenue_range'.
    """
    raw_range = _clean_str(range_val)

    # 1. If estimated_val is numeric int/float
    if isinstance(estimated_val, (int, float)):
        return str(int(estimated_val)), raw_range

    # 2. If estimated_val is a string of pure digits
    est_str = _clean_str(estimated_val)
    if est_str and est_str.isdigit():
        return est_str, raw_range

    # 3. Check if est_str or raw_range contains currency or range notation
    target_str = raw_range or est_str
    if not target_str:
        return None, None

    if not raw_range and any(k in target_str.lower() for k in ["-", "to", "b", "m", "k", "billion", "million"]):
        raw_range = target_str

    # Extract all numbers and multipliers: e.g. "$1B to $5B", "$100M - $500M", "$50M+"
    matches = re.findall(
        r"([0-9]+(?:\.[0-9]+)?)\s*([KkMmBbTt]|thousand|million|billion|trillion)?",
        target_str,
        re.IGNORECASE,
    )

    multipliers = {
        "k": 1_000,
        "thousand": 1_000,
        "m": 1_000_000,
        "million": 1_000_000,
        "b": 1_000_000_000,
        "billion": 1_000_000_000,
        "t": 1_000_000_000_000,
        "trillion": 1_000_000_000_000,
    }

    parsed_values = []
    for num_str, suffix in matches:
        if not num_str:
            continue
        try:
            val = float(num_str)
            mult = multipliers.get(suffix.lower(), 1) if suffix else 1
            parsed_values.append(val * mult)
        except ValueError:
            continue

    if not parsed_values:
        return None, raw_range

    if len(parsed_values) >= 2:
        midpoint = int((parsed_values[0] + parsed_values[1]) / 2)
        return str(midpoint), raw_range
    else:
        return str(int(parsed_values[0])), raw_range


class DataMapper:
    """Utility class translating raw Forager entities into normalized HubSpot dictionaries."""

    @staticmethod
    def forager_to_normalized_company(raw: dict[str, Any]) -> NormalizedCompanyData:
        """Parse raw Forager organization dictionary into NormalizedCompanyData."""
        if not isinstance(raw, dict):
            logger.warning("forager_to_normalized_company received non-dict payload: %s", type(raw))
            raw = {}

        # Log defensive warning for missing expected company fields
        expected_fields = [
            "name",
            "domain",
            "description",
            "headcount",
            "estimated_annual_revenue",
            "industry",
            "linkedin_url",
            "location",
            "founded_year",
        ]
        missing = []
        for f in expected_fields:
            if f == "headcount" and not (raw.get("headcount") or raw.get("employees_range")):
                missing.append("headcount")
            elif f == "estimated_annual_revenue" and not (
                raw.get("estimated_annual_revenue") or raw.get("revenue_range")
            ):
                missing.append("estimated_annual_revenue")
            elif f == "description" and not (raw.get("description") or raw.get("short_description")):
                missing.append("description")
            elif f not in ("headcount", "estimated_annual_revenue", "description") and not raw.get(f):
                missing.append(f)

        if missing:
            company_id = raw.get("domain") or raw.get("name") or "unknown_company"
            logger.warning(
                "Forager company response for '%s' is missing expected fields: %s",
                company_id,
                ", ".join(missing),
            )

        loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
        tech_list = raw.get("technologies") or []
        tech_str = ", ".join(tech_list[:25]) if isinstance(tech_list, list) else _clean_str(tech_list)

        funding = raw.get("funding") if isinstance(raw.get("funding"), dict) else {}
        total_funding = funding.get("total_funding_usd") or raw.get("total_funding")
        funding_str = f"${int(total_funding):,}" if isinstance(total_funding, (int, float)) else _clean_str(total_funding)

        num_revenue, rev_range = _parse_revenue(
            raw.get("estimated_annual_revenue"),
            raw.get("revenue_range"),
        )

        return NormalizedCompanyData(
            name=_clean_str(raw.get("name")),
            domain=_clean_str(raw.get("domain")) or "",
            website=_clean_str(raw.get("website_url") or raw.get("website")),
            description=_clean_str(raw.get("description") or raw.get("short_description")),
            numberofemployees=_clean_str(raw.get("headcount") or raw.get("employees_range")),
            annualrevenue=num_revenue,
            forager_revenue_range=rev_range,
            industry=_clean_str(raw.get("industry")),
            linkedin_company_page=_clean_str(raw.get("linkedin_url")),
            phone=_clean_str(raw.get("phone")),
            city=_clean_str(loc.get("city")),
            state=_clean_str(loc.get("state") or loc.get("state_code")),
            country=_clean_str(loc.get("country") or loc.get("country_code")),
            founded_year=_clean_str(raw.get("founded_year")),
            forager_tech_stack=tech_str,
            forager_funding_total=funding_str,
            forager_status="enriched",
            forager_enriched_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            raw_forager_data=raw,
        )

    @staticmethod
    def forager_to_normalized_contact(raw: dict[str, Any]) -> NormalizedContactData:
        """Parse raw Forager person dictionary into NormalizedContactData."""
        if not isinstance(raw, dict):
            logger.warning("forager_to_normalized_contact received non-dict payload: %s", type(raw))
            raw = {}

        # Log defensive warning for missing expected contact fields
        expected_contact_fields = [
            "first_name",
            "last_name",
            "role_title",
            "email",
            "phone",
            "location",
            "linkedin_url",
            "organization",
        ]
        missing_contact = []
        if not raw.get("first_name"):
            missing_contact.append("first_name")
        if not raw.get("last_name"):
            missing_contact.append("last_name")
        if not (raw.get("role_title") or raw.get("title") or raw.get("normalized_title")):
            missing_contact.append("role_title")
        if not (raw.get("email") or raw.get("emails")):
            missing_contact.append("email")
        if not (raw.get("phone") or raw.get("phones")):
            missing_contact.append("phone")
        if not (raw.get("linkedin_url") or raw.get("linkedin_public_identifier")):
            missing_contact.append("linkedin_url")
        if not raw.get("location"):
            missing_contact.append("location")
        if not raw.get("organization"):
            missing_contact.append("organization")

        if missing_contact:
            candidate_name = f"{raw.get('first_name', '')} {raw.get('last_name', '')}".strip() or "unnamed_candidate"
            logger.warning(
                "Forager contact response for candidate '%s' is missing expected fields: %s",
                candidate_name,
                ", ".join(missing_contact),
            )

        org = raw.get("organization") if isinstance(raw.get("organization"), dict) else {}
        loc = raw.get("location") if isinstance(raw.get("location"), dict) else {}
        skills = raw.get("skills") or []
        skills_str = ", ".join(skills[:20]) if isinstance(skills, list) else _clean_str(skills)

        # Handle multiple possible email / phone shapes
        email = _clean_str(raw.get("email"))
        if not email and raw.get("emails"):
            emails_list = raw.get("emails")
            if isinstance(emails_list, list) and len(emails_list) > 0:
                email = _clean_str(emails_list[0])

        phone = _clean_str(raw.get("phone"))
        if not phone and raw.get("phones"):
            phones_list = raw.get("phones")
            if isinstance(phones_list, list) and len(phones_list) > 0:
                phone = _clean_str(phones_list[0])

        linkedin_url = _clean_str(raw.get("linkedin_url"))
        if not linkedin_url and raw.get("linkedin_public_identifier"):
            slug = raw.get("linkedin_public_identifier")
            linkedin_url = f"https://www.linkedin.com/in/{slug}"

        company_name = _clean_str(org.get("name") or raw.get("company_name"))
        company_domain = _clean_str(org.get("domain") or raw.get("company_domain"))
        company_linkedin = _clean_str(org.get("linkedin_url") or raw.get("company_linkedin_url"))

        return NormalizedContactData(
            firstname=_clean_str(raw.get("first_name")),
            lastname=_clean_str(raw.get("last_name")),
            jobtitle=_clean_str(raw.get("role_title") or raw.get("title") or raw.get("normalized_title")),
            email=email,
            phone=phone,
            city=_clean_str(loc.get("city")),
            state=_clean_str(loc.get("state") or loc.get("state_code")),
            country=_clean_str(loc.get("country") or loc.get("country_code")),
            company=company_name,
            company_domain=company_domain,
            company_linkedin_url=company_linkedin,
            person_linkedin_url=linkedin_url,
            forager_headline=_clean_str(raw.get("headline")),
            forager_about=_clean_str(raw.get("about") or raw.get("summary")),
            forager_skills=skills_str,
            forager_seniority=_clean_str(raw.get("seniority")),
            forager_source_id=_clean_str(raw.get("id") or raw.get("person_id")),
            forager_status="enriched",
            forager_enriched_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
            raw_forager_data=raw,
        )

    HUBSPOT_ALLOWED_INDUSTRIES = {
        "ACCOUNTING", "AIRLINES_AVIATION", "ALTERNATIVE_DISPUTE_RESOLUTION", "ALTERNATIVE_MEDICINE",
        "ANIMATION", "APPAREL_FASHION", "ARCHITECTURE_PLANNING", "ARTS_AND_CRAFTS", "AUTOMOTIVE",
        "AVIATION_AEROSPACE", "BANKING", "BIOTECHNOLOGY", "BROADCAST_MEDIA", "BUILDING_MATERIALS",
        "BUSINESS_SUPPLIES_AND_EQUIPMENT", "CAPITAL_MARKETS", "CHEMICALS", "CIVIC_SOCIAL_ORGANIZATION",
        "CIVIL_ENGINEERING", "COMMERCIAL_REAL_ESTATE", "COMPUTER_NETWORK_SECURITY", "COMPUTER_GAMES",
        "COMPUTER_HARDWARE", "COMPUTER_NETWORKING", "COMPUTER_SOFTWARE", "INTERNET", "CONSTRUCTION",
        "CONSUMER_ELECTRONICS", "CONSUMER_GOODS", "CONSUMER_SERVICES", "COSMETICS", "DAIRY",
        "DEFENSE_SPACE", "DESIGN", "EDUCATION_MANAGEMENT", "E_LEARNING",
        "ELECTRICAL_ELECTRONIC_MANUFACTURING", "ENTERTAINMENT", "ENVIRONMENTAL_SERVICES",
        "EVENTS_SERVICES", "EXECUTIVE_OFFICE", "FACILITIES_SERVICES", "FARMING", "FINANCIAL_SERVICES",
        "FINE_ART", "FISHERY", "FOOD_BEVERAGES", "FOOD_PRODUCTION", "FUND_RAISING", "FURNITURE",
        "GAMBLING_CASINOS", "GLASS_CERAMICS_CONCRETE", "GOVERNMENT_ADMINISTRATION",
        "GOVERNMENT_RELATIONS", "GRAPHIC_DESIGN", "HEALTH_WELLNESS_AND_FITNESS", "HIGHER_EDUCATION",
        "HOSPITAL_HEALTH_CARE", "HOSPITALITY", "HUMAN_RESOURCES", "IMPORT_AND_EXPORT",
        "INDIVIDUAL_FAMILY_SERVICES", "INDUSTRIAL_AUTOMATION", "INFORMATION_SERVICES",
        "INFORMATION_TECHNOLOGY_AND_SERVICES", "INSURANCE", "INTERNATIONAL_AFFAIRS",
        "INTERNATIONAL_TRADE_AND_DEVELOPMENT", "INVESTMENT_BANKING", "INVESTMENT_MANAGEMENT",
        "JUDICIARY", "LAW_ENFORCEMENT", "LAW_PRACTICE", "LEGAL_SERVICES", "LEGISLATIVE_OFFICE",
        "LEISURE_TRAVEL_TOURISM", "LIBRARIES", "LOGISTICS_AND_SUPPLY_CHAIN", "LUXURY_GOODS_JEWELRY",
        "MACHINERY", "MANAGEMENT_CONSULTING", "MARITIME", "MARKET_RESEARCH",
        "MARKETING_AND_ADVERTISING", "MECHANICAL_OR_INDUSTRIAL_ENGINEERING", "MEDIA_PRODUCTION",
        "MEDICAL_DEVICES", "MEDICAL_PRACTICE", "MENTAL_HEALTH_CARE", "MILITARY", "MINING_METALS",
        "MOTION_PICTURES_AND_FILM", "MUSEUMS_AND_INSTITUTIONS", "MUSIC", "NANOTECHNOLOGY", "NEWSPAPERS",
        "NON_PROFIT_ORGANIZATION_MANAGEMENT", "OIL_ENERGY", "ONLINE_MEDIA", "OUTSOURCING_OFFSHORING",
        "PACKAGE_FREIGHT_DELIVERY", "PACKAGING_AND_CONTAINERS", "PAPER_FOREST_PRODUCTS",
        "PERFORMING_ARTS", "PHARMACEUTICALS", "PHILANTHROPY", "PHOTOGRAPHY", "PLASTICS",
        "POLITICAL_ORGANIZATION", "PRIMARY_SECONDARY_EDUCATION", "PRINTING",
        "PROFESSIONAL_TRAINING_COACHING", "PROGRAM_DEVELOPMENT", "PUBLIC_POLICY",
        "PUBLIC_RELATIONS_AND_COMMUNICATIONS", "PUBLIC_SAFETY", "PUBLISHING", "RAILROAD_MANUFACTURE",
        "RANCHING", "REAL_ESTATE", "RECREATIONAL_FACILITIES_AND_SERVICES", "RELIGIOUS_INSTITUTIONS",
        "RENEWABLES_ENVIRONMENT", "RESEARCH", "RESTAURANTS", "RETAIL", "SECURITY_AND_INVESTIGATIONS",
        "SEMICONDUCTORS", "SHIPBUILDING", "SPORTING_GOODS", "SPORTS", "STAFFING_AND_RECRUITING",
        "SUPERMARKETS", "TELECOMMUNICATIONS", "TEXTILES", "THINK_TANKS", "TOBACCO",
        "TRANSLATION_AND_LOCALIZATION", "TRANSPORTATION_TRUCKING_RAILROAD", "UTILITIES",
        "VENTURE_CAPITAL_PRIVATE_EQUITY", "VETERINARY", "WAREHOUSING", "WHOLESALE", "WINE_AND_SPIRITS",
        "WIRELESS", "WRITING_AND_EDITING", "MOBILE_GAMES"
    }

    @classmethod
    def normalize_hubspot_industry(cls, raw_industry: str | None) -> str | None:
        """Map raw industry string to a valid HubSpot enumeration option or None."""
        if not raw_industry:
            return None
        candidate = raw_industry.strip().upper().replace(" ", "_").replace("-", "_")
        if candidate in cls.HUBSPOT_ALLOWED_INDUSTRIES:
            return candidate

        # Common tech / AI synonyms
        if any(term in candidate for term in ("ARTIFICIAL_INTELLIGENCE", "AI", "MACHINE_LEARNING", "SOFTWARE", "SAAS")):
            return "COMPUTER_SOFTWARE"
        if any(term in candidate for term in ("INTERNET", "WEB", "ONLINE")):
            return "INTERNET"
        if any(term in candidate for term in ("TECH", "INFORMATION_TECHNOLOGY", "IT")):
            return "INFORMATION_TECHNOLOGY_AND_SERVICES"
        if "FINTECH" in candidate or "FINANCE" in candidate:
            return "FINANCIAL_SERVICES"
        if "EDTECH" in candidate or "EDUCATION" in candidate:
            return "E_LEARNING"
        if "BIOTECH" in candidate:
            return "BIOTECHNOLOGY"

        logger.debug("Raw industry '%s' does not match HubSpot allowed options; omitting to prevent 400 rejection.", raw_industry)
        return None

    @classmethod
    def company_to_hubspot_properties(cls, company: NormalizedCompanyData) -> dict[str, Any]:
        """Convert NormalizedCompanyData to HubSpot property payload (non-destructive)."""
        normalized_industry = cls.normalize_hubspot_industry(company.industry)
        prop_map = {
            "name": company.name,
            "domain": company.domain,
            "website": company.website,
            "description": company.description,
            "numberofemployees": company.numberofemployees,
            "annualrevenue": company.annualrevenue,
            "forager_revenue_range": company.forager_revenue_range,
            "industry": normalized_industry,
            "linkedin_company_page": company.linkedin_company_page,
            "phone": company.phone,
            "city": company.city,
            "state": company.state,
            "country": company.country,
            "founded_year": company.founded_year,
            "forager_tech_stack": company.forager_tech_stack,
            "forager_funding_total": company.forager_funding_total,
            "forager_status": company.forager_status,
            "forager_enriched_at": company.forager_enriched_at,
        }
        # Filter out keys with None or empty string to ensure non-destructive updates
        return {k: str(v) for k, v in prop_map.items() if v is not None and str(v).strip() != ""}

    @classmethod
    def contact_to_hubspot_properties(cls, contact: NormalizedContactData) -> dict[str, Any]:
        """Convert NormalizedContactData to HubSpot property payload (non-destructive)."""
        prop_map = {
            "firstname": contact.firstname,
            "lastname": contact.lastname,
            "jobtitle": contact.jobtitle,
            "email": contact.email,
            "phone": contact.phone,
            "city": contact.city,
            "state": contact.state,
            "country": contact.country,
            "company": contact.company,
            "company_domain": contact.company_domain,
            "company_linkedin_url": contact.company_linkedin_url,
            "person_linkedin_url": contact.person_linkedin_url,
            "hs_linkedin_url": contact.person_linkedin_url,
            "forager_headline": contact.forager_headline,
            "forager_about": contact.forager_about,
            "forager_skills": contact.forager_skills,
            "forager_seniority": contact.forager_seniority,
            "forager_source_id": contact.forager_source_id,
            "forager_status": contact.forager_status,
            "forager_enriched_at": contact.forager_enriched_at,
        }
        # Non-destructive filter
        return {k: str(v) for k, v in prop_map.items() if v is not None and str(v).strip() != ""}
