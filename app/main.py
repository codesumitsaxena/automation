"""Main FastAPI application entrypoint with router registrations, dashboard UI, and lifecycle handlers."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import authenticate_api_user
from app.api.routes import router as api_router
from app.config import get_settings
from app.db.database import SessionLocal, init_db
from app.db.models import EnrichmentLog, WebhookEvent
from app.logging_config import setup_logging
from app.services.credit_guard import CreditGuard
from app.webhooks.routes import router as webhook_router

settings = get_settings()
logger = setup_logging(settings.log_level)


# Static and Templates Directory Paths
UI_DIR = os.path.join(os.path.dirname(__file__), "ui")
STATIC_DIR = os.path.join(UI_DIR, "static")
TEMPLATES_DIR = os.path.join(UI_DIR, "templates")

templates = Jinja2Templates(directory=TEMPLATES_DIR)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown events."""
    logger.info("Initializing SQLite database tables...")
    init_db()
    logger.info(
        "Application startup complete. DRY_RUN=%s, BASE_URL=%s",
        settings.dry_run,
        settings.public_base_url,
    )
    yield
    logger.info("Application shutdown.")


app = FastAPI(
    title="Forager x HubSpot Enrichment Automation",
    description="Production-grade custom data enrichment bridge connecting Forager.ai with HubSpot CRM.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS with explicit origins (prevent wildcard with credentials vulnerability)
cors_origins_list = [
    origin.strip().rstrip("/")
    for origin in settings.cors_origins.split(",")
    if origin.strip()
] if settings.cors_origins else [
    settings.public_base_url.rstrip("/"),
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Mount Static Assets
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Include API and Webhook Routers
app.include_router(webhook_router, prefix="/webhooks", tags=["Webhooks"])
app.include_router(api_router, prefix="/api", tags=["Manual API"])


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
async def render_dashboard(request: Request, user: str = Depends(authenticate_api_user)):
    """Render the interactive Blue & White HTML dashboard."""

    credit_info = CreditGuard.get_ledger_summary()

    with SessionLocal() as db:
        comp_count = (
            db.query(EnrichmentLog)
            .filter(EnrichmentLog.entity_type == "company", EnrichmentLog.status == "SUCCESS")
            .count()
        )
        cont_count = (
            db.query(EnrichmentLog)
            .filter(EnrichmentLog.entity_type == "contact", EnrichmentLog.status.in_(["SUCCESS", "DISCOVERED"]))
            .count()
        )
        wh_count = db.query(WebhookEvent).count()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "dry_run": settings.dry_run,
            "forager_dry_run": settings.forager_dry_run,
            "hubspot_dry_run": settings.hubspot_dry_run,
            "mode_badge": settings.mode_badge,
            "credits_remaining": credit_info["credits_remaining"],
            "credits_used": credit_info["total_real_credits_used"],
            "companies_count": comp_count,
            "contacts_count": cont_count,
            "webhooks_count": wh_count,
        },
    )


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint used by Railway, load balancers, and monitoring."""
    return {
        "status": "healthy",
        "service": "forager-hubspot-enrichment",
        "version": "1.0.0",
        "dry_run": settings.dry_run,
        "forager_dry_run": settings.forager_dry_run,
        "hubspot_dry_run": settings.hubspot_dry_run,
        "mode_badge": settings.mode_badge,
        "database": "connected",
    }
