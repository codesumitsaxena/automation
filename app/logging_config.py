"""Structured logging configuration with automatic secret masking.

Ensures sensitive API keys, tokens, and credentials are never leaked to logs or stdout.
"""

import logging
import re
import sys
from typing import Any, ClassVar


class SecretMaskingFilter(logging.Filter):
    """Filter that intercepts log records and redacts detected secrets and API keys."""

    # Patterns matching typical secret formats and environment variable values
    SECRET_PATTERNS: ClassVar[list[re.Pattern]] = [
        re.compile(r"(pat-[a-zA-Z0-9_\-]+)", re.IGNORECASE),
        re.compile(r"((?:bearer|token|apikey|api_key|secret|password)[\s:=]+['\"]?)([a-zA-Z0-9_\-]{8,})(['\"]?)", re.IGNORECASE),
        re.compile(r"(X-API-KEY[\s:=]+['\"]?)([a-zA-Z0-9_\-]{8,})(['\"]?)", re.IGNORECASE),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._mask_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._mask_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._mask_value(v) for v in record.args)
        return True

    def _mask_string(self, text: str) -> str:
        masked = text
        for pattern in self.SECRET_PATTERNS:
            def replace_match(m: re.Match) -> str:
                if len(m.groups()) == 1:
                    val = m.group(1)
                    if len(val) > 8:
                        return f"{val[:4]}...{val[-4:]}"
                    return "***REDACTED***"
                prefix, secret, suffix = m.group(1), m.group(2), m.group(3)
                if len(secret) > 8:
                    masked_val = f"{secret[:3]}...{secret[-3:]}"
                else:
                    masked_val = "***"
                return f"{prefix}{masked_val}{suffix}"

            masked = pattern.sub(replace_match, masked)
        return masked

    def _mask_value(self, val: Any) -> Any:
        if isinstance(val, str):
            return self._mask_string(val)
        return val


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure root and application loggers with timestamps and masking filters."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    # Clean existing handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | [%(name)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(SecretMaskingFilter())

    root_logger.addHandler(handler)

    # Silence noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

    logger = logging.getLogger("forager_hubspot")
    logger.setLevel(numeric_level)
    return logger
