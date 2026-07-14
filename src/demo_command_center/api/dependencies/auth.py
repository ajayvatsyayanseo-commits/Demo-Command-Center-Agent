from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Depends, Header, HTTPException, Request, status

from demo_command_center.api.dependencies.container import get_container
from demo_command_center.bootstrap.dependency_container import DependencyContainer
from demo_command_center.security.authentication import (
    InternalAuthenticationError,
    InternalIdentity,
)


async def _authenticate(
    request: Request,
    container: DependencyContainer,
    legacy_secret: str | None,
    required_scopes: frozenset[str],
) -> InternalIdentity:
    settings = container.settings
    configured_legacy = settings.lead_intake_shared_secret.get_secret_value()
    legacy_configured = settings.internal_legacy_shared_secret_enabled and bool(configured_legacy)
    if legacy_configured and legacy_secret:
        if hmac.compare_digest(configured_legacy.encode(), legacy_secret.encode()):
            identity = InternalIdentity(
                source="legacy-lead-intake",
                audience=settings.internal_auth_audience,
                scopes=required_scopes,
                key_id="legacy",
                legacy=True,
            )
            request.state.internal_identity = identity
            return identity
    if not container.internal_auth.configured and not legacy_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal authentication is not configured",
        )
    if not container.internal_auth.configured:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal authentication failed",
        )
    try:
        identity = await container.internal_auth.verify(
            method=request.method,
            path=request.url.path,
            body=await request.body(),
            headers=request.headers,
            required_scopes=required_scopes,
        )
    except InternalAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Internal authentication failed",
        ) from exc
    request.state.internal_identity = identity
    return identity


def require_internal_scopes(
    *scopes: str,
) -> Callable[..., Awaitable[InternalIdentity]]:
    required = frozenset(scopes)

    async def dependency(
        request: Request,
        x_nxtutors_internal_secret: str | None = Header(
            default=None, alias="X-NXTutors-Internal-Secret"
        ),
        container: DependencyContainer = Depends(get_container),
    ) -> InternalIdentity:
        return await _authenticate(request, container, x_nxtutors_internal_secret, required)

    return dependency


require_internal_auth = require_internal_scopes("events:write")
