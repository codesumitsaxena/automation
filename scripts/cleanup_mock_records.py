"""Cleanup script for removing mock evaluation records from HubSpot CRM.

Finds and deletes ONLY companies and contacts where forager_status="mock_demo".
Provides a safe dry-run preview first and requires explicit user confirmation.
"""

import argparse
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


async def main():
    parser = argparse.ArgumentParser(description="Clean up mock evaluation records from HubSpot CRM")
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip interactive confirmation and proceed with deletion",
    )
    args = parser.parse_args()

    client = HubSpotClient()

    print("=" * 80)
    print("      HUBSPOT CRM CLEANUP TOOL - MOCK EVALUATION RECORDS")
    print("=" * 80)
    print(f"HubSpot Client Mode : {'LIVE CRM' if client.is_live else 'MOCK / SIMULATED'}")
    print("Filter Target       : forager_status == 'mock_demo'\n")

    # 1. Search for mock companies
    print("[1/3] Scanning HubSpot CRM for mock companies (forager_status='mock_demo')...")
    companies = await client.search_companies_by_property("forager_status", "mock_demo")

    # 2. Search for mock contacts
    print("[2/3] Scanning HubSpot CRM for mock contacts (forager_status='mock_demo')...")
    contacts = await client.search_contacts_by_property("forager_status", "mock_demo")

    # 3. Dry Preview
    print("\n--------------------------------------------------------------------------------")
    print("                              DRY RUN PREVIEW")
    print("--------------------------------------------------------------------------------")
    print(f"Total Companies to Delete: {len(companies)}")
    for comp in companies:
        cid = comp.get("id")
        name = comp.get("properties", {}).get("name", "N/A")
        domain = comp.get("properties", {}).get("domain", "N/A")
        print(f"  - [Company ID: {cid}] {name} ({domain})")

    print(f"\nTotal Contacts to Delete : {len(contacts)}")
    for cont in contacts:
        cid = cont.get("id")
        fname = cont.get("properties", {}).get("firstname", "")
        lname = cont.get("properties", {}).get("lastname", "")
        email = cont.get("properties", {}).get("email", "N/A")
        title = cont.get("properties", {}).get("jobtitle", "N/A")
        print(f"  - [Contact ID: {cid}] {fname} {lname} <{email}> ({title})")
    print("--------------------------------------------------------------------------------\n")

    if not companies and not contacts:
        print("[OK] No mock evaluation records found in HubSpot. Nothing to delete.")
        return

    # 4. Confirmation Prompt
    if not args.yes:
        confirm = input("Type 'YES' to permanently delete the above records from HubSpot: ").strip()
        if confirm != "YES":
            print("[ABORTED] Deletion cancelled by user. Zero records were deleted.")
            return

    # 5. Execution
    print("\n[3/3] Proceeding with deletion...")
    deleted_companies = 0
    for comp in companies:
        cid = comp.get("id")
        name = comp.get("properties", {}).get("name", "N/A")
        try:
            await client.delete_company(cid)
            deleted_companies += 1
            print(f"  [DELETED] Company {name} (ID: {cid})")
        except Exception as e:
            print(f"  [ERROR] Failed to delete company {cid}: {e!s}")

    deleted_contacts = 0
    for cont in contacts:
        cid = cont.get("id")
        email = cont.get("properties", {}).get("email", "N/A")
        try:
            await client.delete_contact(cid)
            deleted_contacts += 1
            print(f"  [DELETED] Contact {email} (ID: {cid})")
        except Exception as e:
            print(f"  [ERROR] Failed to delete contact {cid}: {e!s}")

    print("\n" + "=" * 80)
    print(f"CLEANUP COMPLETE: Deleted {deleted_companies} companies and {deleted_contacts} contacts.")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
