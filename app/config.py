"""Application configuration using Pydantic Settings.

Loads environment variables from `.env` file or environment with type validation,
fallbacks, and helper properties.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Forager x HubSpot Enrichment Automation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Forager API Configuration
    forager_api_key: str = Field(default="", description="Forager API Key")
    forager_account_id: str = Field(default="", description="Forager Account ID")
    forager_base_url: str = Field(
        default="https://api-v2.forager.ai",
        description="Forager API base URL",
    )

    # HubSpot API & Webhook Configuration
    hubspot_access_token: str = Field(
        default="", description="HubSpot Private App Access Token"
    )
    hubspot_client_secret: str = Field(
        default="", description="HubSpot App Client Secret for v3 signature verification"
    )
    verify_webhook_signature: bool = Field(
        default=False,
        description="Whether to strictly verify X-HubSpot-Signature-v3 on webhooks",
    )

    # Deployment / Network
    public_base_url: str = Field(
        default="http://localhost:8000",
        description="Publicly accessible base URL of the service",
    )
    cors_origins: str = Field(
        default="",
        description="Comma-separated list of allowed CORS origins. If empty, defaults to public_base_url and localhost",
    )

    # Guardrails & Operational Flags
    dry_run: bool = Field(
        default=True,
        description="When True, uses mock JSON data and makes 0 real paid API calls",
    )
    max_credits_per_run: int = Field(
        default=30,
        description="Maximum credit consumption allowed in a single execution flow",
    )
    default_contact_limit: int = Field(
        default=5,
        description="Default number of contacts to find for a company",
    )
    default_title_filters: str = Field(
        default="CEO,CTO,VP,Head of,Director,Founder,Co-Founder,President",
        description="Comma-separated list of job title keywords to filter discovered contacts",
    )
    enable_email_phone_reveal: bool = Field(
        default=False,
        description="Controls whether high-cost work email and mobile phone reveals are executed in live mode",
    )

    # Dashboard Authentication
    dashboard_username: str = Field(
        default="admin", description="HTTP Basic Auth username for manual API & dashboard"
    )
    dashboard_password: str = Field(
        default="changeme", description="HTTP Basic Auth password for manual API & dashboard"
    )

    # Logging and Database
    log_level: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR)")
    database_url: str = Field(
        default="sqlite:///./enrichment.db",
        description="SQLAlchemy database connection string",
    )

    @property
    def title_filters_list(self) -> list[str]:
        """Parse comma-separated DEFAULT_TITLE_FILTERS into a cleaned list."""
        if not self.default_title_filters:
            return []
        return [t.strip() for t in self.default_title_filters.split(",") if t.strip()]

    def is_configured_for_live_hubspot(self) -> bool:
        """Check if HubSpot credentials are provided."""
        return bool(self.hubspot_access_token and self.hubspot_access_token.strip() and not self.hubspot_access_token.startswith("your_"))

    def is_configured_for_live_forager(self) -> bool:
        """Check if Forager credentials are provided."""
        return bool(self.forager_api_key and self.forager_api_key.strip() and not self.forager_api_key.startswith("your_"))


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
