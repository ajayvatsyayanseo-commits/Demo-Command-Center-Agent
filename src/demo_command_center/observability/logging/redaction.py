from __future__ import annotations

import hashlib
import logging
import re
from collections.abc import MutableMapping
from typing import Any

import structlog

_RESTRICTED_KEYS = {
    "access_token",
    "authorization",
    "email",
    "meeting_link",
    "message_body",
    "message_text",
    "password",
    "payment_payload",
    "phone",
    "raw_body",
    "raw_payload",
    "secret",
    "token",
}
_SECRET_SHAPE = re.compile(r"(?i)(bearer\s+\S+|-----BEGIN [A-Z ]+PRIVATE KEY-----)")


def _digest(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def redact_event(
    _logger: object, _method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key in list(event_dict):
        normalized = key.lower()
        value = event_dict[key]
        if any(restricted in normalized for restricted in _RESTRICTED_KEYS):
            event_dict[key] = f"[REDACTED:{_digest(value)}]"
        elif isinstance(value, str) and _SECRET_SHAPE.search(value):
            event_dict[key] = "[REDACTED]"
    return event_dict


def configure_logging(level: str) -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(message)s")
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            redact_event,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
