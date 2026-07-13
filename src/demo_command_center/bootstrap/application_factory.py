from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from demo_command_center.api.errors.taxonomy import ServiceError
from demo_command_center.api.middleware.correlation import CorrelationMiddleware
from demo_command_center.api.middleware.security import (
    RequestSafetyMiddleware,
    SecurityHeadersMiddleware,
)
from demo_command_center.api.routes import health_router, internal_router, provider_router
from demo_command_center.bootstrap.lifecycle import application_lifespan
from demo_command_center.config.settings import Settings, get_settings
from demo_command_center.observability.logging.redaction import configure_logging
from demo_command_center.observability.tracing import configure_tracing


def create_application(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    configure_logging(resolved.log_level)
    app = FastAPI(
        title="NXTutors Demo Command Center Agent",
        version=resolved.app_version,
        docs_url="/docs" if not resolved.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not resolved.is_production else None,
        lifespan=application_lifespan(resolved),
        debug=resolved.app_debug,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=resolved.allowed_hosts)
    if resolved.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_allowed_origins,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=[
                "Content-Type",
                "X-Correlation-Id",
                "X-NXTutors-Key-Id",
                "X-NXTutors-Timestamp",
                "X-NXTutors-Nonce",
                "X-NXTutors-Source",
                "X-NXTutors-Issuer",
                "X-NXTutors-Audience",
                "X-NXTutors-Scopes",
                "X-NXTutors-Signature",
            ],
        )
    app.add_middleware(RequestSafetyMiddleware, maximum_body_bytes=resolved.max_request_body_bytes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.include_router(health_router)
    app.include_router(internal_router)
    app.include_router(provider_router)
    configure_tracing(app, service_name=resolved.app_name, service_version=resolved.app_version)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError) -> JSONResponse:
        correlation_id = getattr(request.state, "correlation_id", "unavailable")
        return JSONResponse(
            status_code=503,
            content={
                "code": str(exc.code),
                "message": exc.safe_message,
                "correlation_id": correlation_id,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        del exc
        correlation_id = getattr(request.state, "correlation_id", "unavailable")
        return JSONResponse(
            status_code=500,
            content={
                "code": "DCC_INTERNAL_ERROR",
                "message": "An internal error occurred",
                "correlation_id": correlation_id,
            },
        )

    return app
