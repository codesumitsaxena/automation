"""Application configuration using Pydantic Settings.

Loads environment variables from `.env` file or environment with type validation,
fallbacks, and helper properties.
"""

from functools import lru_cache

from pydantic import Field, model_validator
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
        description="Master dry run flag. When True, both Forager and HubSpot default to mock mode",
    )
    forager_dry_run: bool | None = Field(
        default=None,
        description="Explicit toggle for Forager mock mode. Defaults to value of DRY_RUN if None",
    )
    hubspot_dry_run: bool | None = Field(
        default=None,
        description="Explicit toggle for HubSpot mock mode. Defaults to value of DRY_RUN if None",
    )
    save_raw_responses: bool = Field(
        default=False,
        description="When True, saves every real Forager API response into raw_responses/ directory",
    )
    raw_responses_dir: str = Field(
        default="raw_responses",
        description="Directory path for saving raw API responses",
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
    enable_email_reveal: bool = Field(
        default=False,
        description="Controls whether work email reveals (5 credits/contact) are executed in live mode",
    )
    enable_phone_reveal: bool = Field(
        default=False,
        description="Controls whether mobile/direct phone reveals (15 credits/contact) are executed in live mode",
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

    @property
    def enable_email_phone_reveal(self) -> bool:
        """Backwards compatibility for legacy combined reveal flag."""
        return self.enable_email_reveal or self.enable_phone_reveal

    @model_validator(mode="after")
    def resolve_dry_runs(self) -> "Settings":
        """Resolve split dry run flags from master dry_run toggle if not explicitly provided."""
        if self.forager_dry_run is None:
            self.forager_dry_run = self.dry_run
        if self.hubspot_dry_run is None:
            self.hubspot_dry_run = self.dry_run
        return self

    @property
    def mode_badge(self) -> str:
        """Formatted environment badge string for console and dashboard."""
        f_mode = "MOCK" if self.forager_dry_run else "LIVE"
        h_mode = "MOCK" if self.hubspot_dry_run else "LIVE"
        return f"FORAGER: {f_mode} | HUBSPOT: {h_mode}"


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of Settings."""
    return Settings()
