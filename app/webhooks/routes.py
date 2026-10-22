"""HubSpot incoming webhook routes with event deduplication and background task dispatch."""

import json
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status

from app.db.database import SessionLocal
from app.db.models import WebhookEvent
from app.logging_config import setup_logging
from app.services.orchestrator import OrchestrationService
from app.webhooks.security import require_hubspot_signature

router = APIRouter()
logger = setup_logging()
orchestrator = OrchestrationService()


async def process_webhook_event_in_background(
    event_id: str,
    subscription_type: str,
    object_id: str,
) -> None:
    """Asynchronous background worker processing individual webhook actions."""
    logger.info("Background processing webhook event %s: type=%s, objectId=%s", event_id, subscription_type, object_id)

    err_msg = None
    try:
        if subscription_type in ("company.creation", "object.creation.company"):
            await orchestrator.handle_company_webhook(object_id)
        elif subscription_type in ("contact.creation", "object.creation.contact"):
            await orchestrator.handle_contact_webhook(object_id)
        else:
            logger.info("Ignoring unsupported webhook subscription type: %s", subscription_type)
    except Exception as e:
        err_msg = str(e)
        logger.exception("Error processing webhook %s: %s", event_id, err_msg)

    # Update event status in SQLite
    try:
        with SessionLocal() as db:
            event_record = db.query(WebhookEvent).filter(WebhookEvent.event_id == str(event_id)).first()
            if event_record:
                event_record.status = "FAILED" if err_msg else "PROCESSED"
                event_record.error_message = err_msg
                event_record.processed_at = datetime.now(UTC)
                db.commit()
    except Exception as db_err:
        logger.error("Failed to update webhook event status in DB: %s", str(db_err))


@router.post(
    "/hubspot",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_hubspot_signature)],
    summary="Receive HubSpot Webhooks",
    description="Accepts batched or single webhook events for company.creation and contact.creation",
)
async def handle_hubspot_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: list[dict[str, Any]] | dict[str, Any],
):
    """Receive HubSpot webhook events, deduplicate by eventId, and process in background."""
    raw_events = payload if isinstance(payload, list) else [payload]
    logger.info("Received HubSpot webhook batch containing %d event(s)", len(raw_events))

    accepted_count = 0
    duplicate_count = 0

    with SessionLocal() as db:
        for item in raw_events:
            event_id = str(item.get("eventId") or item.get("id") or f"gen_{datetime.now().timestamp()}")
            sub_type = str(item.get("subscriptionType", "unknown"))
            object_id = str(item.get("objectId", ""))
            portal_id = item.get("portalId")

            # Check for duplicate eventId
            existing = db.query(WebhookEvent).filter(WebhookEvent.event_id == event_id).first()
            if existing:
                logger.info("Duplicate webhook event %s detected. Skipping.", event_id)
                duplicate_count += 1
                continue

            # Store new event in DB
            event_entry = WebhookEvent(
                event_id=event_id,
                subscription_type=sub_type,
                object_id=object_id,
                portal_id=portal_id,
                raw_payload=json.dumps(item),
                status="RECEIVED",
            )
            db.add(event_entry)
            accepted_count += 1

            # Dispatch processing to BackgroundTasks
            background_tasks.add_task(
                process_webhook_event_in_background,
                event_id=event_id,
                subscription_type=sub_type,
                object_id=object_id,
            )

        db.commit()

    return {
        "status": "success",
        "events_received": len(raw_events),
        "events_accepted": accepted_count,
        "duplicates_ignored": duplicate_count,
    }
