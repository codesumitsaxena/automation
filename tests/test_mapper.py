"""Unit tests for DataMapper service and property normalization."""

from app.services.mapper import DataMapper


def test_mapper_company_normalization():
    raw_forager_company = {
        "name": "OpenAI",
        "domain": "openai.com",
        "website_url": "https://openai.com",
        "description": "AI research company",
        "headcount": 770,
        "estimated_annual_revenue": 3400000000,
        "industry": "Artificial Intelligence",
        "linkedin_url": "https://linkedin.com/company/openai",
        "phone": "+1-415-555-0199",
        "founded_year": 2015,
        "location": {
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
        },
        "technologies": ["Python", "Kubernetes", "PyTorch"],
        "funding": {"total_funding_usd": 11300000000},
    }

    normalized = DataMapper.forager_to_normalized_company(raw_forager_company)
    assert normalized.name == "OpenAI"
    assert normalized.domain == "openai.com"
    assert normalized.numberofemployees == "770"
    assert normalized.annualrevenue == "3400000000"
    assert "Python" in normalized.forager_tech_stack
    assert "$11,300,000,000" in normalized.forager_funding_total

    # Test conversion to HubSpot properties (non-destructive)
    props = DataMapper.company_to_hubspot_properties(normalized)
    assert props["domain"] == "openai.com"
    assert props["forager_status"] == "enriched"
    assert "name" in props


def test_mapper_contact_normalization():
    raw_forager_person = {
        "first_name": "Sam",
        "last_name": "Altman",
        "role_title": "CEO",
        "email": "sam@openai.com",
        "phone": "+1-415-555-0101",
        "linkedin_url": "https://linkedin.com/in/samaltman",
        "location": {"city": "San Francisco", "state": "CA", "country": "USA"},
        "organization": {
            "name": "OpenAI",
            "domain": "openai.com",
            "linkedin_url": "https://linkedin.com/company/openai",
        },
        "headline": "CEO at OpenAI",
        "about": "Leading safe AGI research.",
        "skills": ["AI Strategy", "Executive Leadership"],
        "seniority": "c_level",
    }

    normalized = DataMapper.forager_to_normalized_contact(raw_forager_person)
    assert normalized.firstname == "Sam"
    assert normalized.lastname == "Altman"
    assert normalized.jobtitle == "CEO"
    assert normalized.email == "sam@openai.com"
    assert normalized.phone == "+1-415-555-0101"
    assert normalized.company_domain == "openai.com"
    assert normalized.person_linkedin_url == "https://linkedin.com/in/samaltman"
    assert normalized.city == "San Francisco"

    props = DataMapper.contact_to_hubspot_properties(normalized)
    assert props["firstname"] == "Sam"
    assert props["email"] == "sam@openai.com"
    assert props["forager_status"] == "enriched"


def test_mapper_revenue_range_parsing_and_custom_property():
    """Verify ISSUE-06: ranges like '$1B to $5B' store numeric midpoint in annualrevenue and raw text in forager_revenue_range."""
    # Scenario A: Forager provides revenue_range string only
    raw_range_only = {
        "name": "Big Corp",
        "domain": "bigcorp.com",
        "revenue_range": "$1B to $5B",
    }
    comp_a = DataMapper.forager_to_normalized_company(raw_range_only)
    assert comp_a.annualrevenue == "3000000000", "Midpoint of 1B and 5B should be 3,000,000,000"
    assert comp_a.forager_revenue_range == "$1B to $5B"

    props_a = DataMapper.company_to_hubspot_properties(comp_a)
    assert props_a["annualrevenue"] == "3000000000"
    assert props_a["forager_revenue_range"] == "$1B to $5B"

    # Scenario B: Forager provides range in millions: "$100M - $500M"
    raw_millions = {
        "name": "Mid Corp",
        "domain": "midcorp.com",
        "revenue_range": "$100M - $500M",
    }
    comp_b = DataMapper.forager_to_normalized_company(raw_millions)
    assert comp_b.annualrevenue == "300000000", "Midpoint of 100M and 500M should be 300,000,000"
    assert comp_b.forager_revenue_range == "$100M - $500M"

    # Scenario C: Both numeric estimate and text range provided
    raw_both = {
        "name": "OpenAI",
        "domain": "openai.com",
        "estimated_annual_revenue": 3400000000,
        "revenue_range": "$1B to $5B",
    }
    comp_c = DataMapper.forager_to_normalized_company(raw_both)
    assert comp_c.annualrevenue == "3400000000"
    assert comp_c.forager_revenue_range == "$1B to $5B"

    props_c = DataMapper.company_to_hubspot_properties(comp_c)
    assert props_c["annualrevenue"] == "3400000000"
    assert props_c["forager_revenue_range"] == "$1B to $5B"

