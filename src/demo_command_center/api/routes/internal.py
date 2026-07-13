from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from demo_command_center.api.dependencies.auth import require_internal_scopes
from demo_command_center.api.dependencies.container import get_container
from demo_command_center.api.errors.taxonomy import ServiceError
from demo_command_center.api.schemas.ingress import IngressReceipt, IngressStatus
from demo_command_center.bootstrap.dependency_container import DependencyContainer
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.security.authentication import InternalIdentity

router = APIRouter(prefix="/v1/internal", tags=["internal"])


async def _accept(event: AgentEventEnvelope, container: DependencyContainer) -> IngressReceipt:
    try:
        return await container.event_ingress.accept(event)
    except ServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": exc.safe_message},
        ) from exc


def _validate_route_identity(
    event: AgentEventEnvelope,
    identity: InternalIdentity,
    container: DependencyContainer,
) -> None:
    valid_targets = {container.settings.app_name, "demo-command-center"}
    if event.target_agent not in valid_targets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Event target is not this service",
        )
    if not identity.legacy and event.source_agent != identity.source:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Signed source does not match the event source",
        )


@router.post(
    "/events",
    response_model=IngressReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_event(
    event: AgentEventEnvelope,
    identity: InternalIdentity = Depends(require_internal_scopes("events:write")),
    container: DependencyContainer = Depends(get_container),
) -> IngressReceipt:
    _validate_route_identity(event, identity, container)
    return await _accept(event, container)


@router.post(
    "/whatsapp/handoffs",
    response_model=IngressReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_whatsapp_handoff(
    event: AgentEventEnvelope,
    identity: InternalIdentity = Depends(require_internal_scopes("handoffs:write")),
    container: DependencyContainer = Depends(get_container),
) -> IngressReceipt:
    _validate_route_identity(event, identity, container)
    if not event.event_type.startswith("whatsapp.handoff."):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="WhatsApp handoff route requires a whatsapp.handoff.* event",
        )
    return await _accept(event, container)


@router.get("/events/{event_id}", response_model=IngressStatus)
async def get_event_status(
    event_id: UUID,
    identity: InternalIdentity = Depends(require_internal_scopes("events:read")),
    container: DependencyContainer = Depends(get_container),
) -> IngressStatus:
    del identity
    try:
        result = await container.event_ingress.status(event_id)
    except ServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": exc.safe_message},
        ) from exc
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return result
