from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from mangum import Mangum

from demo_command_center.bootstrap.application_factory import create_application

_cached_handler: Mangum | None = None


def build_lambda_handler(app: FastAPI | None = None) -> Mangum:
    """Build the HTTP Lambda adapter for the FastAPI API surface.

    This is intentionally API-only. Queue workers, migration jobs, scheduled reconciliation, and
    long-running operational tasks still use their dedicated process types unless a future ADR
    replaces the runtime model.
    """

    return Mangum(app or create_application(), lifespan="auto")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """AWS Lambda entrypoint for API Gateway v2 / Lambda Function URL events."""

    global _cached_handler
    if _cached_handler is None:
        _cached_handler = build_lambda_handler()
    response = _cached_handler(event, context)
    if not isinstance(response, dict):
        raise RuntimeError("Lambda adapter returned an invalid response")
    return response
