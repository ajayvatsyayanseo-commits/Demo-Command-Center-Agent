from __future__ import annotations

from dataclasses import asdict
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from demo_command_center.api.dependencies.auth import require_internal_scopes
from demo_command_center.api.dependencies.container import get_container
from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.api.schemas.ingress import IngressReceipt, IngressStatus
from demo_command_center.api.schemas.payments import (
    PaymentOrderCreateRequest,
    PaymentOrderJobResponse,
)
from demo_command_center.bootstrap.dependency_container import DependencyContainer
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.payments import (
    PaymentOrderCommand,
    PaymentOrderJobService,
)
from demo_command_center.security.authentication import InternalIdentity

router = APIRouter(prefix="/v1/internal", tags=["internal"])


def _payment_service(container: DependencyContainer) -> PaymentOrderJobService:
    service = container.payment_order_jobs
    if (
        service is None
        or not container.settings.demo_payments_enabled
        or not container.settings.cashfree_order_enabled
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cashfree order creation is disabled or not configured",
        )
    return service


def _raise_payment_error(exc: ServiceError) -> NoReturn:
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    if exc.code is ErrorCode.IDEMPOTENCY_CONFLICT:
        status_code = status.HTTP_409_CONFLICT
    elif exc.code in {
        ErrorCode.POLICY_REJECTED,
        ErrorCode.PAYMENT_MISMATCH,
        ErrorCode.INVALID_TRANSITION,
    }:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    raise HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.safe_message},
    ) from exc


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
    if event.source_agent in {"cashfree", "meta-whatsapp-direct"} or event.event_type.startswith(
        ("cashfree.", "meta.")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Provider events must use their signature-verified webhook route",
        )
    valid_targets = {container.settings.app_name, "demo-command-center"}
    if event.target_agent not in valid_targets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
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
    dependencies=[Depends(require_internal_scopes("events:write"))],
)
async def ingest_event(
    event: AgentEventEnvelope,
    request: Request,
    container: DependencyContainer = Depends(get_container),
) -> IngressReceipt:
    identity: InternalIdentity = request.state.internal_identity
    _validate_route_identity(event, identity, container)
    return await _accept(event, container)


@router.post(
    "/whatsapp/handoffs",
    response_model=IngressReceipt,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_scopes("handoffs:write"))],
)
async def ingest_whatsapp_handoff(
    event: AgentEventEnvelope,
    request: Request,
    container: DependencyContainer = Depends(get_container),
) -> IngressReceipt:
    identity: InternalIdentity = request.state.internal_identity
    _validate_route_identity(event, identity, container)
    if not event.event_type.startswith("whatsapp.handoff."):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="WhatsApp handoff route requires a whatsapp.handoff.* event",
        )
    return await _accept(event, container)


@router.get(
    "/events/{event_id}",
    response_model=IngressStatus,
    dependencies=[Depends(require_internal_scopes("events:read"))],
)
async def get_event_status(
    event_id: UUID,
    request: Request,
    container: DependencyContainer = Depends(get_container),
) -> IngressStatus:
    del request
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


@router.post(
    "/payments/orders",
    response_model=PaymentOrderJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_internal_scopes("payments:write"))],
)
async def request_payment_order(
    body: PaymentOrderCreateRequest,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    container: DependencyContainer = Depends(get_container),
) -> PaymentOrderJobResponse:
    if idempotency_key != str(body.request_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Idempotency-Key must equal the signed request_id",
        )
    service = _payment_service(container)
    try:
        job = await service.request(
            PaymentOrderCommand(
                request_id=body.request_id,
                demo_ref=body.demo_ref,
                website_user_ref=body.website_user_ref,
                plan_ref=body.plan_ref,
                customer_phone=body.customer_phone.get_secret_value(),
            ),
            correlation_id=request.state.correlation_id,
        )
    except ServiceError as exc:
        _raise_payment_error(exc)
    return PaymentOrderJobResponse.model_validate(asdict(job))


@router.get(
    "/payments/orders/{request_id}",
    response_model=PaymentOrderJobResponse,
    dependencies=[Depends(require_internal_scopes("payments:read"))],
)
async def get_payment_order(
    request_id: UUID,
    request: Request,
    container: DependencyContainer = Depends(get_container),
) -> PaymentOrderJobResponse:
    del request
    service = _payment_service(container)
    try:
        job = await service.status(request_id)
    except ServiceError as exc:
        _raise_payment_error(exc)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment request not found"
        )
    return PaymentOrderJobResponse.model_validate(asdict(job))
