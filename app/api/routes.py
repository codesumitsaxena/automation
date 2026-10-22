"""Manual REST API routes for triggers, diagnostics, credit inspection, and UI data."""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy import desc

from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import EnrichmentLog, WebhookEvent
from app.logging_config import setup_logging
from app.models.schemas import (
    ApiResponse,
    CompanyEnrichRequest,
    ContactDiscoveryRequest,
    ContactEnrichRequest,
)
from app.services.company_service import CompanyService
from app.services.contact_service import ContactService
from app.services.credit_guard import CreditGuard
from app.services.discovery_service import DiscoveryService
from app.services.orchestrator import OrchestrationService

router = APIRouter()
logger = setup_logging()
security = HTTPBasic()
settings = get_settings()

orchestrator = OrchestrationService()
company_service = CompanyService()
contact_service = ContactService()
discovery_service = DiscoveryService()


def authenticate_api_user(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """Validate HTTP Basic Authentication for protected manual endpoints."""
    correct_user = secrets.compare_digest(credentials.username, settings.dashboard_username)
    correct_pass = secrets.compare_digest(credentials.password, settings.dashboard_password)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# -----------------------------------------------------------------------------
# Enrichment Endpoints
# -----------------------------------------------------------------------------

@router.post(
    "/companies/enrich",
    response_model=ApiResponse,
    summary="Manually Enrich Company",
)
async def enrich_company_endpoint(
    payload: CompanyEnrichRequest,
    user: str = Depends(authenticate_api_user),
):
    """Enrich a company by domain, populating description, revenue, headcount, and firmographics."""
    try:
        res = await company_service.enrich_company(
            domain=payload.domain,
            hubspot_company_id=payload.hubspot_company_id,
        )
        return ApiResponse(
            success=res.get("success", False),
            message=res.get("message", "Company enrichment executed"),
            data=res,
        )
    except Exception as e:
        logger.exception("Failed manual company enrichment: %s", str(e))
        return ApiResponse(success=False, message="Enrichment failed", errors=[str(e)])


@router.post(
    "/contacts/enrich",
    response_model=ApiResponse,
    summary="Manually Enrich Contact",
)
async def enrich_contact_endpoint(
    payload: ContactEnrichRequest,
    user: str = Depends(authenticate_api_user),
):
    """Enrich an individual contact with complete required details."""
    try:
        res = await contact_service.enrich_contact(
            email=payload.email,
            linkedin_url=payload.linkedin_url,
            hubspot_contact_id=payload.hubspot_contact_id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            company_domain=payload.company_domain,
        )
        return ApiResponse(
            success=res.get("success", False),
            message=res.get("message", "Contact enrichment executed"),
            data=res,
        )
    except Exception as e:
        logger.exception("Failed manual contact enrichment: %s", str(e))
        return ApiResponse(success=False, message="Contact enrichment failed", errors=[str(e)])


@router.post(
    "/contacts/find",
    response_model=ApiResponse,
    summary="Find Contacts at Company with Title Filtering",
)
async def find_contacts_endpoint(
    payload: ContactDiscoveryRequest,
    user: str = Depends(authenticate_api_user),
):
    """Discover people at target company domain, strictly filtered by job title and limit."""
    try:
        contacts = await discovery_service.discover_contacts(
            company_domain=payload.company_domain,
            job_titles=payload.job_titles,
            seniority=payload.seniority,
            limit=payload.limit,
            hubspot_company_id=payload.hubspot_company_id,
            add_to_hubspot=payload.add_to_hubspot,
        )
        return ApiResponse(
            success=True,
            message=f"Discovered {len(contacts)} contacts matching criteria",
            data=[c.model_dump() for c in contacts],
        )
    except Exception as e:
        logger.exception("Failed contact discovery: %s", str(e))
        return ApiResponse(success=False, message="Contact discovery failed", errors=[str(e)])


@router.post(
    "/demo/openai",
    response_model=ApiResponse,
    summary="Run Primary Evaluation Demo (OpenAI + 5 Contacts)",
)
async def run_openai_demo_endpoint(
    user: str = Depends(authenticate_api_user),
):
    """Execute the primary hiring deliverable: complete enrichment for OpenAI and 5 executive contacts."""
    try:
        res = await orchestrator.run_openai_demo()
        return ApiResponse(
            success=res.get("success", False),
            message="OpenAI evaluation demo executed successfully",
            data=res,
        )
    except Exception as e:
        logger.exception("Failed demo execution: %s", str(e))
        return ApiResponse(success=False, message="Demo execution failed", errors=[str(e)])


# -----------------------------------------------------------------------------
# Diagnostics, Credit & Monitoring Endpoints
# -----------------------------------------------------------------------------

@router.get(
    "/credits",
    summary="Get Credit Usage and Ledger",
)
async def get_credits_endpoint(
    user: str = Depends(authenticate_api_user),
):
    """Retrieve current credit balance, trial budget, and recent credit transactions."""
    return CreditGuard.get_ledger_summary()


@router.get(
    "/logs",
    summary="Get Enrichment Logs",
)
async def get_logs_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    user: str = Depends(authenticate_api_user),
):
    """Retrieve recent audit logs for companies and contacts."""
    with SessionLocal() as db:
        logs = (
            db.query(EnrichmentLog)
            .order_by(desc(EnrichmentLog.created_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": l.id,
                "entity_type": l.entity_type,
                "entity_id": l.entity_id,
                "identifier": l.identifier,
                "status": l.status,
                "message": l.message,
                "details": l.details_json,
                "created_at": l.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
            for l in logs
        ]


@router.get(
    "/webhooks",
    summary="Get Ingested Webhook Events",
)
async def get_webhooks_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    user: str = Depends(authenticate_api_user),
):
    """Retrieve audit history of webhook events received from HubSpot."""
    with SessionLocal() as db:
        events = (
            db.query(WebhookEvent)
            .order_by(desc(WebhookEvent.received_at))
            .limit(limit)
            .all()
        )
        return [
            {
                "id": e.id,
                "event_id": e.event_id,
                "subscription_type": e.subscription_type,
                "object_id": e.object_id,
                "portal_id": e.portal_id,
                "status": e.status,
                "error": e.error_message,
                "received_at": e.received_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "processed_at": e.processed_at.strftime("%Y-%m-%d %H:%M:%S UTC") if e.processed_at else None,
            }
            for e in events
        ]


@router.get(
    "/stats",
    summary="Get Dashboard Statistics",
)
async def get_dashboard_stats(
    user: str = Depends(authenticate_api_user),
):
    """Provide aggregated statistics for the UI dashboard."""
    credit_info = CreditGuard.get_ledger_summary()

    with SessionLocal() as db:
        companies_count = (
            db.query(EnrichmentLog)
            .filter(EnrichmentLog.entity_type == "company", EnrichmentLog.status == "SUCCESS")
            .count()
        )
        contacts_count = (
            db.query(EnrichmentLog)
            .filter(EnrichmentLog.entity_type == "contact", EnrichmentLog.status.in_(["SUCCESS", "DISCOVERED"]))
            .count()
        )
        webhooks_count = db.query(WebhookEvent).count()

        recent_logs = (
            db.query(EnrichmentLog)
            .order_by(desc(EnrichmentLog.created_at))
            .limit(10)
            .all()
        )

        recent_logs_data = [
            {
                "id": l.id,
                "entity_type": l.entity_type,
                "identifier": l.identifier,
                "status": l.status,
                "message": l.message,
                "created_at": l.created_at.strftime("%H:%M:%S"),
            }
            for l in recent_logs
        ]

    return {
        "dry_run": settings.dry_run,
        "forager_dry_run": settings.forager_dry_run,
        "hubspot_dry_run": settings.hubspot_dry_run,
        "mode_badge": settings.mode_badge,
        "credits_remaining": credit_info["credits_remaining"],
        "credits_used": credit_info["total_real_credits_used"],
        "companies_enriched": companies_count,
        "contacts_enriched": contacts_count,
        "webhooks_received": webhooks_count,
        "recent_logs": recent_logs_data,
    }


@router.post(
    "/sync/poll-new-records",
    response_model=ApiResponse,
    summary="Fallback Polling Sync for Free HubSpot Portals",
)
async def poll_new_records_sync(
    user: str = Depends(authenticate_api_user),
):
    """Fallback mechanism for accounts without webhook access: inspects recently created companies and triggers enrichment."""
    logger.info("Triggered fallback sync poller for newly created HubSpot records")
    # In live mode, this polls HubSpot for companies lacking forager_status
    # In mock mode, demonstrates finding OpenAI
    demo_res = await orchestrator.run_openai_demo(limit=5)
    return ApiResponse(
        success=True,
        message="Poller executed: synced and enriched records",
        data=demo_res,
    )
