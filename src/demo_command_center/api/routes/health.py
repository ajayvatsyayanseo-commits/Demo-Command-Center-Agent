from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Response, status

from demo_command_center.api.dependencies.auth import require_internal_scopes
from demo_command_center.api.dependencies.container import get_container
from demo_command_center.bootstrap.dependency_container import (
    DependencyContainer,
    LocalEventIngress,
)
from demo_command_center.security.authentication import InternalIdentity

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def live(container: DependencyContainer = Depends(get_container)) -> dict[str, str]:
    return {
        "status": "live",
        "service": container.settings.app_name,
        "version": container.settings.app_version,
    }


@router.get("/health/ready")
async def ready(
    response: Response, container: DependencyContainer = Depends(get_container)
) -> dict[str, Any]:
    settings = container.settings
    auth_configured = container.internal_auth.configured or bool(
        settings.internal_legacy_shared_secret_enabled
        and settings.lead_intake_shared_secret.get_secret_value()
    )
    dependency_checks = await container.dependency_health()
    ingress_configured = dependency_checks["durable_ingress"]
    dependencies_ready = all(dependency_checks.values())
    is_ready = (
        container.feature_flags.command_center
        and auth_configured
        and ingress_configured
        and dependencies_ready
    )
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if is_ready else "not_ready",
        "checks": {
            "command_center_enabled": container.feature_flags.command_center,
            "internal_auth_configured": auth_configured,
            "ingress_configured": ingress_configured,
            "runtime_dependencies": dependencies_ready,
        },
    }


@router.get("/health/dependencies")
async def dependencies(
    identity: InternalIdentity = Depends(require_internal_scopes("health:read")),
    container: DependencyContainer = Depends(get_container),
) -> dict[str, Any]:
    del identity
    checks = await container.dependency_health()
    all_healthy = all(checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "dependencies": {name: "healthy" if value else "unavailable" for name, value in checks.items()},
    }
