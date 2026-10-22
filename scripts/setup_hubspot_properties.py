"""Automated setup script creating custom property groups and fields in HubSpot CRM.

Creates the 'Forager Enrichment' property group and all required custom fields
for Companies and Contacts using HubSpot's CRM Schemas API v3.
"""

import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.clients.hubspot_client import HubSpotClient
from app.config import get_settings
from app.logging_config import setup_logging

settings = get_settings()
logger = setup_logging(settings.log_level)


# Property Group Definition
PROPERTY_GROUP_NAME = "forager_enrichment"
PROPERTY_GROUP_LABEL = "Forager Enrichment"

# Custom Properties for Contacts
CONTACT_PROPERTIES = [
    {
        "name": "person_linkedin_url",
        "label": "Person LinkedIn URL",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Public LinkedIn profile URL discovered via Forager",
    },
    {
        "name": "company_domain",
        "label": "Employer Company Domain",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Primary domain of the employer company",
    },
    {
        "name": "company_linkedin_url",
        "label": "Employer LinkedIn URL",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Company LinkedIn page URL",
    },
    {
        "name": "forager_headline",
        "label": "Professional Headline",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Professional headline from LinkedIn profile",
    },
    {
        "name": "forager_about",
        "label": "Profile Summary / About",
        "type": "string",
        "fieldType": "textarea",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Profile summary or bio from LinkedIn",
    },
    {
        "name": "forager_skills",
        "label": "Skills & Expertise",
        "type": "string",
        "fieldType": "textarea",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Comma-separated list of professional skills",
    },
    {
        "name": "forager_seniority",
        "label": "Seniority Level",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Normalized seniority level (c_level, vp, director, manager, etc.)",
    },
    {
        "name": "forager_status",
        "label": "Forager Enrichment Status",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Status of enrichment ('enriched', 'discovered', 'pending')",
    },
    {
        "name": "forager_enriched_at",
        "label": "Forager Enriched Timestamp",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "UTC timestamp of the latest enrichment update",
    },
    {
        "name": "forager_source_id",
        "label": "Forager Record ID",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Unique identifier from Forager database",
    },
]

# Custom Properties for Companies
COMPANY_PROPERTIES = [
    {
        "name": "founded_year",
        "label": "Founded Year",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Year the company was founded",
    },
    {
        "name": "forager_tech_stack",
        "label": "Technologies & Tech Stack",
        "type": "string",
        "fieldType": "textarea",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Technologies and web tools detected at this company",
    },
    {
        "name": "forager_funding_total",
        "label": "Total Funding Raised",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Total funding raised formatted in USD",
    },
    {
        "name": "forager_status",
        "label": "Forager Enrichment Status",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Status of company enrichment ('enriched', 'pending')",
    },
    {
        "name": "forager_revenue_range",
        "label": "Forager Revenue Range",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "Original raw revenue range text reported by Forager (e.g. '$1B to $5B')",
    },
    {
        "name": "forager_enriched_at",
        "label": "Forager Enriched Timestamp",
        "type": "string",
        "fieldType": "text",
        "groupName": PROPERTY_GROUP_NAME,
        "description": "UTC timestamp of company enrichment",
    },
]


async def setup_properties():
    """Create property groups and custom properties in HubSpot CRM."""
    client = HubSpotClient()

    print("=" * 70)
    print("FORAGER x HUBSPOT CRM PROPERTY SETUP")
    print("=" * 70)
    print(f"HubSpot Client Mode: {'LIVE API' if client.is_live else 'MOCK / SIMULATED'}")
    print(f"Property Group: '{PROPERTY_GROUP_LABEL}' ({PROPERTY_GROUP_NAME})\n")

    # 1. Create Property Groups for Companies and Contacts
    for obj_type in ["companies", "contacts"]:
        print(f"[*] Ensuring property group '{PROPERTY_GROUP_NAME}' exists on {obj_type}...")
        try:
            await client.create_property_group(
                object_type=obj_type,
                name=PROPERTY_GROUP_NAME,
                label=PROPERTY_GROUP_LABEL,
            )
            print(f"    [OK] Property group verified on {obj_type}")
        except Exception as e:
            print(f"    ! Note: {e!s}")

    # 2. Create Custom Company Properties
    print("\n[*] Provisioning Custom Company Properties...")
    for prop in COMPANY_PROPERTIES:
        try:
            await client.create_property("companies", prop)
            print(f"    [OK] Company property: {prop['name']} ({prop['label']})")
        except Exception as e:
            print(f"    ! Error on {prop['name']}: {e!s}")

    # 3. Create Custom Contact Properties
    print("\n[*] Provisioning Custom Contact Properties...")
    for prop in CONTACT_PROPERTIES:
        try:
            await client.create_property("contacts", prop)
            print(f"    [OK] Contact property: {prop['name']} ({prop['label']})")

        except Exception as e:
            print(f"    ! Error on {prop['name']}: {e!s}")

    print("\n" + "=" * 70)
    print("PROPERTIES SETUP COMPLETE! All custom fields are ready in HubSpot.")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(setup_properties())
