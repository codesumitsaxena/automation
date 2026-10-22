"""Forager.ai API client with credit accounting, retry backoff, and mock fallback."""

import hashlib
import json
import os
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.db.database import SessionLocal
from app.db.models import EnrichmentCache
from app.logging_config import setup_logging

settings = get_settings()
logger = setup_logging(settings.log_level)


# =============================================================================
# FORAGER API ENDPOINT CONSTANTS & CREDIT PRICING
# =============================================================================

class ForagerEndpoints:
    """Canonical registry of Forager API endpoints."""
    ORGANIZATION_SEARCH = "/api/{account_id}/datastorage/organization_search/"
    WEBSITE_DETAIL = "/api/{account_id}/datastorage/website_detail_lookup/"
    PERSON_ROLE_SEARCH = "/api/{account_id}/datastorage/person_role_search/"
    PERSON_DETAIL_LOOKUP = "/api/{account_id}/datastorage/person_detail_lookup/"
    PERSON_REVERSE_EMAIL = "/api/{account_id}/datastorage/person_detail_reverse_lookup/by_email/"
    PERSON_REVERSE_PHONE = "/api/{account_id}/datastorage/person_detail_reverse_lookup/by_phone_number/"
    CONTACT_WORK_EMAIL = "/api/{account_id}/datastorage/person_contacts_lookup/work_emails/"
    CONTACT_PHONE = "/api/{account_id}/datastorage/person_contacts_lookup/phone_numbers/"
    CREDITS_BALANCE = "/api/{account_id}/subscription/credits/"


class ForagerCreditCosts:
    """Official credit costs per Forager lookup operation."""
    ORGANIZATION_SEARCH = 1
    WEBSITE_DETAIL = 1
    PERSON_ROLE_SEARCH = 1
    PERSON_DETAIL_LOOKUP = 1
    PERSON_REVERSE_LOOKUP = 1
    WORK_EMAIL_REVEAL = 5
    PHONE_NUMBER_REVEAL = 15


def is_transient_error(exc: BaseException) -> bool:
    """Determine if an HTTP error is transient (rate limit 429 or server error 5xx)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


class ForagerClient:
    """Production client for Forager.ai B2B prospecting and enrichment API."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, account_id: str | None = None):
        self.base_url = (base_url or settings.forager_base_url).rstrip("/")
        self.api_key = api_key or settings.forager_api_key
        self.account_id = account_id or settings.forager_account_id or "default"
        self.dry_run = settings.forager_dry_run
        self.mocks_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mocks")

    def _get_headers(self) -> dict[str, str]:
        """Generate authentication headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-API-KEY": self.api_key,
        }

    def _resolve_endpoint(self, endpoint_template: str) -> str:
        """Interpolate account_id into endpoint paths."""
        return endpoint_template.format(account_id=self.account_id)

    def _compute_hash(self, endpoint: str, payload: dict[str, Any]) -> str:
        """Create a deterministic SHA-256 hash of endpoint and payload."""
        normalized_json = json.dumps(payload, sort_keys=True)
        raw = f"{endpoint}:{normalized_json}".encode()
        return hashlib.sha256(raw).hexdigest()

    def _get_cached_response(self, request_hash: str) -> dict[str, Any] | None:
        """Look up request hash in SQLite cache table."""
        with SessionLocal() as db:
            cached = db.query(EnrichmentCache).filter(EnrichmentCache.request_hash == request_hash).first()
            if cached:
                logger.debug("Cache hit for hash %s", request_hash[:10])
                return json.loads(cached.response_payload)
        return None

    def _save_cache_response(
        self, request_hash: str, endpoint: str, payload: dict[str, Any], response: dict[str, Any], credit_cost: int
    ) -> None:
        """Persist successful response to SQLite cache."""
        try:
            with SessionLocal() as db:
                entry = EnrichmentCache(
                    request_hash=request_hash,
                    endpoint=endpoint,
                    request_payload=json.dumps(payload),
                    response_payload=json.dumps(response),
                    credit_cost=credit_cost,
                )
                db.add(entry)
                db.commit()
                logger.debug("Cached response for %s with cost %d credits", endpoint, credit_cost)
        except Exception as e:
            logger.warning("Failed to write to SQLite enrichment cache: %s", str(e))

    def _save_raw_response(self, endpoint: str, payload: dict[str, Any], response: dict[str, Any]) -> None:
        """Save raw Forager response to local gitignored directory without secrets."""
        try:
            raw_dir = settings.raw_responses_dir
            os.makedirs(raw_dir, exist_ok=True)
            from datetime import UTC, datetime

            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            clean_endpoint = endpoint.strip("/").replace("/", "_").replace("{", "").replace("}", "")

            target_hint = ""
            if "domains" in payload and isinstance(payload["domains"], list) and payload["domains"]:
                target_hint = f"_{payload['domains'][0].replace('.', '_')}"
            elif (
                "organization_domains" in payload
                and isinstance(payload["organization_domains"], list)
                and payload["organization_domains"]
            ):
                target_hint = f"_{payload['organization_domains'][0].replace('.', '_')}"
            elif "email" in payload:
                target_hint = f"_{payload['email'].replace('@', '_at_').replace('.', '_')}"
            elif "linkedin_public_identifier" in payload:
                target_hint = f"_{payload['linkedin_public_identifier']}"

            filename = f"{ts}_{clean_endpoint}{target_hint}.json"
            filepath = os.path.join(raw_dir, filename)

            # Scrub any accidental secret patterns in payload/response
            output_record = {
                "saved_at": datetime.now(UTC).isoformat(),
                "endpoint": endpoint,
                "payload": payload,
                "response": response,
            }
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(output_record, f, indent=2, ensure_ascii=False)
            logger.info("Saved raw Forager response to %s (SAVE_RAW_RESPONSES=True)", filepath)
        except Exception as exc:
            logger.warning("Failed to save raw Forager response: %s", exc)

    def is_cached(self, endpoint_template: str, payload: dict[str, Any]) -> bool:
        """Check if a specific endpoint and payload already exist in SQLite cache."""
        endpoint = self._resolve_endpoint(endpoint_template)
        req_hash = self._compute_hash(endpoint, payload)
        return self._get_cached_response(req_hash) is not None

    def is_organization_cached(self, domain: str) -> bool:
        """Check if organization firmographics for domain are cached."""
        payload = {"domains": [domain.lower().strip()], "page": 0}
        return self.is_cached(ForagerEndpoints.ORGANIZATION_SEARCH, payload)

    def is_people_search_cached(
        self, domain: str, role_title: str | None = None, page: int = 0
    ) -> bool:
        """Check if people search for domain and role title is cached."""
        payload: dict[str, Any] = {
            "organization_domains": [domain.lower().strip()],
            "role_is_current": True,
            "page": page,
        }
        if role_title:
            payload["role_title"] = role_title
        return self.is_cached(ForagerEndpoints.PERSON_ROLE_SEARCH, payload)

    def is_person_details_cached(
        self,
        linkedin_public_identifier: str | None = None,
        person_id: int | None = None,
        reveal_emails: bool = False,
        reveal_phones: bool = False,
    ) -> bool:
        """Check if person detail lookup is cached."""
        payload: dict[str, Any] = {
            "reveal_work_emails": reveal_emails,
            "reveal_personal_emails": reveal_emails,
            "reveal_phone_numbers": reveal_phones,
            "do_contacts_enrichment": reveal_emails or reveal_phones,
        }
        if person_id:
            payload["person_id"] = person_id
        if linkedin_public_identifier:
            payload["linkedin_public_identifier"] = linkedin_public_identifier
        return self.is_cached(ForagerEndpoints.PERSON_DETAIL_LOOKUP, payload)

    def is_email_lookup_cached(self, email: str) -> bool:
        """Check if reverse email lookup is cached."""
        payload = {"email": email.lower().strip()}
        return self.is_cached(ForagerEndpoints.PERSON_REVERSE_EMAIL, payload)

    def _load_mock_file(self, filename: str) -> dict[str, Any]:
        """Load static mock JSON from mocks/ directory."""
        path = os.path.join(self.mocks_dir, filename)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.error("Mock file not found: %s", path)
        return {}

    @retry(
        retry=retry_if_exception(is_transient_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _post(
        self, endpoint_template: str, payload: dict[str, Any], credit_cost: int, mock_filename: str | None = None
    ) -> dict[str, Any]:
        """Execute POST request with caching, credit counting, and DRY_RUN handling."""
        endpoint = self._resolve_endpoint(endpoint_template)
        req_hash = self._compute_hash(endpoint, payload)

        # 1. Check SQLite Cache First
        cached = self._get_cached_response(req_hash)
        if cached:
            return cached

        # 2. Check DRY_RUN Mode
        if self.dry_run:
            logger.info("[DRY_RUN] Intercepted Forager call to %s. Consumed 0 credits.", endpoint)
            if mock_filename:
                mock_data = self._load_mock_file(mock_filename)
                self._save_cache_response(req_hash, endpoint, payload, mock_data, 0)
                return mock_data
            return {"data": [], "total": 0, "mock": True}

        # 3. Live Request
        url = f"{self.base_url}{endpoint}"
        logger.info("Calling live Forager API: %s (estimated cost: %d credits)", url, credit_cost)

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=self._get_headers(), json=payload)
            response.raise_for_status()
            data = response.json()
            self._save_cache_response(req_hash, endpoint, payload, data, credit_cost)
            if settings.save_raw_responses:
                self._save_raw_response(endpoint, payload, data)
            return data

    # -------------------------------------------------------------------------
    # Public API Methods
    # -------------------------------------------------------------------------

    async def search_organization(self, domain: str) -> dict[str, Any] | None:
        """Find company firmographics by domain name."""
        payload = {
            "domains": [domain.lower().strip()],
            "page": 0,
        }
        res = await self._post(
            ForagerEndpoints.ORGANIZATION_SEARCH,
            payload,
            credit_cost=ForagerCreditCosts.ORGANIZATION_SEARCH,
            mock_filename="forager_organization_openai.json",
        )
        data = res.get("data", [])
        if data:
            return data[0]
        return None

    async def search_people_by_company(
        self,
        domain: str,
        role_title: str | None = None,
        page: int = 0,
    ) -> list[dict[str, Any]]:
        """Find people associated with a company domain, filtered by job role/title."""
        payload: dict[str, Any] = {
            "organization_domains": [domain.lower().strip()],
            "role_is_current": True,
            "page": page,
        }
        if role_title:
            payload["role_title"] = role_title

        res = await self._post(
            ForagerEndpoints.PERSON_ROLE_SEARCH,
            payload,
            credit_cost=ForagerCreditCosts.PERSON_ROLE_SEARCH,
            mock_filename="forager_people_openai.json",
        )
        return res.get("data", [])

    async def get_person_details(
        self,
        person_id: int | None = None,
        linkedin_public_identifier: str | None = None,
        reveal_emails: bool = False,
        reveal_phones: bool = False,
    ) -> dict[str, Any] | None:
        """Fetch full person details, optionally revealing emails and phone numbers."""
        payload: dict[str, Any] = {
            "reveal_work_emails": reveal_emails,
            "reveal_personal_emails": reveal_emails,
            "reveal_phone_numbers": reveal_phones,
            "do_contacts_enrichment": reveal_emails or reveal_phones,
        }
        if person_id:
            payload["person_id"] = person_id
        elif linkedin_public_identifier:
            payload["linkedin_public_identifier"] = linkedin_public_identifier
        else:
            raise ValueError("Either person_id or linkedin_public_identifier must be provided.")

        cost = ForagerCreditCosts.PERSON_DETAIL_LOOKUP
        if reveal_emails:
            cost += ForagerCreditCosts.WORK_EMAIL_REVEAL
        if reveal_phones:
            cost += ForagerCreditCosts.PHONE_NUMBER_REVEAL

        res = await self._post(
            ForagerEndpoints.PERSON_DETAIL_LOOKUP,
            payload,
            credit_cost=cost,
            mock_filename="forager_people_openai.json",
        )
        data = res.get("data", [])
        if data:
            return data[0]
        return None

    async def reverse_lookup_by_email(self, email: str) -> dict[str, Any] | None:
        """Find a person profile given their work or personal email address."""
        payload = {"email": email.lower().strip()}
        res = await self._post(
            ForagerEndpoints.PERSON_REVERSE_EMAIL,
            payload,
            credit_cost=ForagerCreditCosts.PERSON_REVERSE_LOOKUP,
            mock_filename="forager_people_openai.json",
        )
        data = res.get("data", [])
        if data:
            return data[0]
        return None

    async def get_credit_balance(self) -> int:
        """Fetch the active credit balance from Forager API (free metadata endpoint).

        In DRY_RUN mode, returns 50 (or ledger remaining balance).
        In LIVE mode, queries Forager's subscription credits endpoint. If unreachable,
        falls back gracefully to the local database ledger calculation.
        """
        if self.dry_run:
            logger.info("DRY_RUN=True: Using simulated credit balance (50 credits)")
            return 50

        endpoint = self._resolve_endpoint(ForagerEndpoints.CREDITS_BALANCE)
        url = f"{self.base_url}{endpoint}"
        logger.info("Querying live Forager credit balance from: %s", url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=self._get_headers())
                if response.status_code == 200:
                    payload = response.json()
                    if isinstance(payload, dict):
                        balance = (
                            payload.get("credits_remaining")
                            or payload.get("balance")
                            or payload.get("credits")
                            or (payload.get("data", {}).get("credits") if isinstance(payload.get("data"), dict) else None)
                            or (payload.get("data", {}).get("balance") if isinstance(payload.get("data"), dict) else None)
                        )
                        if balance is not None:
                            logger.info("Live Forager API reported active balance: %d credits", int(balance))
                            return int(balance)
        except Exception as exc:
            logger.warning("Could not fetch remote Forager credit balance (%s). Falling back to local ledger.", exc)

        # Fallback to local SQLite ledger
        from app.services.credit_guard import CreditGuard

        ledger = CreditGuard.get_ledger_summary()
        return int(ledger.get("credits_remaining", 50))
