"""Unit tests for ISSUE-09: Domain syntax validation and URL normalization."""

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    CompanyEnrichRequest,
    ContactDiscoveryRequest,
)


def test_domain_validation_valid_domains():
    """Verify standard domains and multi-level subdomains are accepted."""
    req1 = CompanyEnrichRequest(domain="openai.com")
    assert req1.domain == "openai.com"

    req2 = CompanyEnrichRequest(domain="sub.example.co.uk")
    assert req2.domain == "sub.example.co.uk"

    req3 = ContactDiscoveryRequest(company_domain="deepmind.google")
    assert req3.company_domain == "deepmind.google"


def test_domain_validation_normalization():
    """Verify schemes, www prefixes, and trailing paths are normalized cleanly."""
    req_http = CompanyEnrichRequest(domain="http://openai.com")
    assert req_http.domain == "openai.com"

    req_https_www = CompanyEnrichRequest(domain="https://www.openai.com/")
    assert req_https_www.domain == "openai.com"

    req_path = CompanyEnrichRequest(domain="http://www.sub.example.co.uk/about?ref=test")
    assert req_path.domain == "sub.example.co.uk"


def test_domain_validation_rejects_invalid_inputs():
    """Verify empty strings, whitespace, and non-domain strings are rejected with ValidationError."""
    # Empty string
    with pytest.raises(ValidationError):
        CompanyEnrichRequest(domain="")

    # Whitespace only
    with pytest.raises(ValidationError):
        CompanyEnrichRequest(domain="   ")

    # Not a domain (spaces, no TLD)
    with pytest.raises(ValidationError):
        CompanyEnrichRequest(domain="not a domain")

    # Single word without TLD
    with pytest.raises(ValidationError):
        CompanyEnrichRequest(domain="openai")

    # Invalid characters
    with pytest.raises(ValidationError):
        CompanyEnrichRequest(domain="openai..com")
