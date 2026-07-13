from __future__ import annotations

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider


def configure_tracing(app: FastAPI, *, service_name: str, service_version: str) -> None:
    current = trace.get_tracer_provider()
    if not isinstance(current, TracerProvider):
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": service_name,
                    "service.version": service_version,
                }
            )
        )
        trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
