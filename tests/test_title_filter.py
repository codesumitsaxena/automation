"""Unit tests for dual-layer job title filtering and executive acronym matching."""

from app.services.discovery_service import matches_title_filter


def test_title_filter_exact_and_substring_matches():
    approved = ["CEO", "CTO", "VP", "Head of", "Director"]

    # Valid matches
    assert matches_title_filter("CEO", approved) is True
    assert matches_title_filter("Chief Executive Officer", approved) is True
    assert matches_title_filter("Chief Technology Officer", approved) is True
    assert matches_title_filter("VP of Engineering", approved) is True
    assert matches_title_filter("Senior Vice President of Research", approved) is True
    assert matches_title_filter("Head of Developer Relations", approved) is True
    assert matches_title_filter("Director of Product Management", approved) is True
    assert matches_title_filter("Managing Director", approved) is True

    # Invalid matches that must be excluded (partial word boundary regression tests)
    assert matches_title_filter("VPN Engineer", approved) is False
    assert matches_title_filter("Vpn Network Administrator", approved) is False
    assert matches_title_filter("Redirector of Traffic", approved) is False
    assert matches_title_filter("Ahead of Schedule Coordinator", approved) is False
    assert matches_title_filter("Junior Data Annotator Intern", approved) is False
    assert matches_title_filter("Software Engineer Level 2", approved) is False
    assert matches_title_filter("Customer Support Associate", approved) is False
    assert matches_title_filter("HR Specialist", approved) is False



def test_title_filter_edge_cases():
    approved = ["CEO", "President"]

    # Case insensitivity
    assert matches_title_filter("ceo", approved) is True
    assert matches_title_filter("president & co-founder", approved) is True

    # Empty inputs
    assert matches_title_filter(None, approved) is False
    assert matches_title_filter("", approved) is False
    assert matches_title_filter("Any Title", []) is True
