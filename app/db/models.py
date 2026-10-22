"""SQLAlchemy database models for persistence, idempotency, and audit trails."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text

from app.db.database import Base


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(UTC)


class EnrichmentCache(Base):
    """Cache of all Forager API requests and responses to prevent double-spending credits."""

    __tablename__ = "enrichment_cache"

    id = Column(Integer, primary_key=True, index=True)
    request_hash = Column(String(64), unique=True, index=True, nullable=False)
    endpoint = Column(String(255), nullable=False)
    request_payload = Column(Text, nullable=False)
    response_payload = Column(Text, nullable=False)
    credit_cost = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_cache_endpoint_hash", "endpoint", "request_hash"),
    )


class EnrichmentLog(Base):
    """Audit log of all company and contact enrichment actions."""

    __tablename__ = "enrichment_log"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(50), nullable=False)  # "company", "contact"
    entity_id = Column(String(100), nullable=True)    # HubSpot Object ID
    identifier = Column(String(255), nullable=False)  # Domain or Email
    status = Column(String(50), nullable=False)       # "SUCCESS", "SKIPPED", "ERROR", "DISCOVERED"
    message = Column(Text, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    __table_args__ = (
        Index("idx_log_entity_created", "entity_type", "created_at"),
    )


class CreditUsage(Base):
    """Ledger of credit expenditure across runs and operations."""

    __tablename__ = "credit_usage"

    id = Column(Integer, primary_key=True, index=True)
    operation = Column(String(100), nullable=False)  # "company_enrich", "people_search", "person_lookup", "email_reveal", "phone_reveal"
    target = Column(String(255), nullable=False)     # "openai.com", "Sam Altman"
    credits_spent = Column(Integer, nullable=False)
    is_mock = Column(Boolean, default=False, nullable=False)
    run_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class WebhookEvent(Base):
    """Deduplication and processing tracking table for incoming HubSpot webhook events."""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(100), unique=True, index=True, nullable=False)
    subscription_type = Column(String(100), nullable=False)  # "company.creation", "contact.creation"
    object_id = Column(String(100), nullable=False)
    portal_id = Column(Integer, nullable=True)
    raw_payload = Column(Text, nullable=False)
    status = Column(String(50), default="RECEIVED", nullable=False)  # "RECEIVED", "PROCESSING", "PROCESSED", "IGNORED", "FAILED"
    error_message = Column(Text, nullable=True)
    received_at = Column(DateTime, default=utc_now, nullable=False)
    processed_at = Column(DateTime, nullable=True)
