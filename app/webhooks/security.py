"""HubSpot v3 request signature verification for webhook security."""

import base64
import hashlib
import hmac
import time

from fastapi import Header, HTTPException, Request, status

from app.config import get_settings
from app.logging_config import setup_logging

settings = get_settings()
logger = setup_logging(settings.log_level)


def verify_hubspot_v3_signature(
    method: str,
    url: str,
    raw_body: bytes,
    timestamp_header: str | None,
    signature_header: str | None,
    client_secret: str,
) -> bool:
    """Validate HubSpot v3 signature using HMAC SHA-256 with timestamp verification.

    Formula: Base64( HMAC-SHA256( secret, method + url + body + timestamp ) )
    """
    if not signature_header or not timestamp_header:
        logger.warning("Missing HubSpot signature or timestamp headers")
        return False

    # 1. Replay attack prevention: reject requests older than 5 minutes (300,000 ms)
    try:
        req_timestamp = int(timestamp_header)
    except ValueError:
        logger.warning("Invalid timestamp header format: %s", timestamp_header)
        return False

    current_timestamp = int(time.time() * 1000)
    if abs(current_timestamp - req_timestamp) > 300000:
        logger.warning(
            "Rejected expired webhook request. Difference: %d ms (threshold: 300000 ms)",
            abs(current_timestamp - req_timestamp),
        )
        return False

    # 2. Reconstruct the source string: method + url + body + timestamp
    # Note: method must be uppercase, url must match exact requested URL
    decoded_body = raw_body.decode("utf-8") if raw_body else ""
    source_string = f"{method.upper()}{url}{decoded_body}{timestamp_header}"

    # 3. Compute HMAC-SHA256
    computed_hash = hmac.new(
        key=client_secret.encode("utf-8"),
        msg=source_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    computed_signature = base64.b64encode(computed_hash).decode("utf-8")

    # 4. Constant-time comparison
    is_valid = hmac.compare_digest(computed_signature, signature_header)
    if not is_valid:
        logger.warning("HubSpot v3 signature mismatch")
    return is_valid


async def require_hubspot_signature(
    request: Request,
    x_hubspot_signature_v3: str | None = Header(None, alias="X-HubSpot-Signature-v3"),
    x_hubspot_request_timestamp: str | None = Header(None, alias="X-HubSpot-Request-Timestamp"),
) -> None:
    """FastAPI dependency enforcing HubSpot v3 signature validation when enabled."""
    if not settings.verify_webhook_signature:
        # Signature validation disabled for local testing / development
        return

    client_secret = settings.hubspot_client_secret
    if not client_secret or client_secret.startswith("your_"):
        logger.error("VERIFY_WEBHOOK_SIGNATURE is True, but HUBSPOT_CLIENT_SECRET is not configured!")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server webhook signature verification misconfigured",
        )

    raw_body = await request.body()

    # Reconstruct the target URL as seen by HubSpot.
    # Behind reverse proxies (e.g. Railway, Cloudflare), request.url scheme may be 'http'
    # whereas HubSpot signs the public 'https' target URL.
    proto = request.headers.get("x-forwarded-proto")
    host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    query_str = f"?{request.url.query}" if request.url.query else ""

    if settings.public_base_url and not settings.public_base_url.startswith("http://localhost") and not settings.public_base_url.startswith("http://127.0.0.1"):
        base = settings.public_base_url.rstrip("/")
        url = f"{base}{request.url.path}{query_str}"
    elif proto and host:
        url = f"{proto}://{host}{request.url.path}{query_str}"
    else:
        url = str(request.url)

    is_valid = verify_hubspot_v3_signature(
        method=request.method,
        url=url,
        raw_body=raw_body,
        timestamp_header=x_hubspot_request_timestamp,
        signature_header=x_hubspot_signature_v3,
        client_secret=client_secret,
    )

    # Fallback to local raw URL if public URL didn't match (for local test client compatibility)
    if not is_valid and url != str(request.url):
        is_valid = verify_hubspot_v3_signature(
            method=request.method,
            url=str(request.url),
            raw_body=raw_body,
            timestamp_header=x_hubspot_request_timestamp,
            signature_header=x_hubspot_signature_v3,
            client_secret=client_secret,
        )


    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid HubSpot v3 request signature",
        )
