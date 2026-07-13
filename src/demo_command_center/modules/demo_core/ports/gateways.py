from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, IdempotencyKey


class DemoRecord(Protocol):
    id: DemoId
    state: str
    version: int


@runtime_checkable
class DemoRepository(Protocol):
    async def get(self, demo_id: DemoId, *, for_update: bool = False) -> DemoRecord | None: ...

    async def add(self, demo: DemoRecord) -> None: ...

    async def save(self, demo: DemoRecord, *, expected_version: int) -> None: ...


class UnitOfWork(AbstractAsyncContextManager["UnitOfWork"], Protocol):
    demos: DemoRepository

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class EventQueuePort(Protocol):
    async def publish(
        self, queue_name: str, payload: Mapping[str, Any], idempotency_key: IdempotencyKey
    ) -> str: ...


class CachePort(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def set(self, key: str, value: bytes, ttl: timedelta) -> None: ...

    async def delete(self, key: str) -> None: ...


class LockLease(Protocol):
    async def release(self) -> None: ...


class LockPort(Protocol):
    async def acquire(self, key: str, ttl: timedelta, owner: str) -> LockLease | None: ...


class SchedulerPort(Protocol):
    async def schedule_once(
        self,
        schedule_id: str,
        run_at: datetime,
        command: Mapping[str, Any],
        idempotency_key: IdempotencyKey,
    ) -> str: ...

    async def cancel(self, schedule_id: str, idempotency_key: IdempotencyKey) -> None: ...


class MessagingPort(Protocol):
    async def request_delivery(
        self,
        recipient_ref: str,
        template_or_message_ref: str,
        variables: Mapping[str, str],
        idempotency_key: IdempotencyKey,
    ) -> str: ...


class EmailPort(Protocol):
    async def send_templated(
        self,
        recipient_ref: str,
        template_ref: str,
        variables: Mapping[str, str],
        idempotency_key: IdempotencyKey,
    ) -> str: ...


class CalendarPort(Protocol):
    async def free_busy(
        self, calendar_refs: Sequence[str], starts_at: datetime, ends_at: datetime
    ) -> Mapping[str, Sequence[tuple[datetime, datetime]]]: ...

    async def create_demo_event(
        self,
        demo_id: DemoId,
        starts_at: datetime,
        ends_at: datetime,
        attendee_refs: Sequence[str],
        conference_request_id: str,
        idempotency_key: IdempotencyKey,
    ) -> str: ...

    async def cancel_event(self, event_ref: str, idempotency_key: IdempotencyKey) -> None: ...


class PaymentPort(Protocol):
    async def create_order(
        self,
        request: PaymentOrderRequest,
        idempotency_key: IdempotencyKey,
    ) -> ProviderOrderResult: ...

    async def fetch_verified_status(self, provider_order_id: str) -> ProviderPaymentStatus: ...


@dataclass(frozen=True, slots=True)
class PaymentOrderRequest:
    order_reference: str
    amount_minor: int
    currency: str
    customer_ref: str
    customer_phone: str
    purpose: str
    correlation_id: str
    return_url: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderOrderResult:
    provider_order_id: str
    payment_session_id: str
    status: str


@dataclass(frozen=True, slots=True)
class ProviderPaymentStatus:
    provider_order_id: str
    status: str
    amount_minor: int
    currency: str


@dataclass(frozen=True, slots=True)
class TutorSearchQuery:
    subject: str | None = None
    board: str | None = None
    class_level: str | None = None
    mode: str | None = None
    city: str | None = None
    district: str | None = None
    state: str | None = None
    class_type: str | None = None
    page: int = 1
    per_page: int = 20


@dataclass(frozen=True, slots=True)
class VerifiedSubscriptionActivation:
    demo_ref: str
    website_user_ref: str
    plan_id: int
    plan_version: str
    amount_minor: int
    currency: str
    provider_order_ref: str
    payment_evidence_ref: str
    payment_verified_at: datetime
    correlation_id: str


class WebsiteGatewayPort(Protocol):
    async def search_tutor_candidates(
        self, query: TutorSearchQuery
    ) -> Sequence[Mapping[str, Any]]: ...

    async def get_plan_quote(self, plan_ref: str, customer_ref: str) -> Mapping[str, Any]: ...

    async def activate_verified_subscription(
        self,
        activation: VerifiedSubscriptionActivation,
        idempotency_key: IdempotencyKey,
    ) -> Mapping[str, Any]: ...


class OnboardingPort(Protocol):
    async def handoff_paid_user(
        self,
        handoff: OnboardingHandoffRequest,
        idempotency_key: IdempotencyKey,
    ) -> Mapping[str, Any]: ...


@dataclass(frozen=True, slots=True)
class OnboardingHandoffRequest:
    demo_id: DemoId
    user_ref: str
    recipient_phone: str
    role: str
    correlation_id: str


class LlmPort(Protocol):
    async def structured_completion(
        self,
        task_name: str,
        redacted_input: Mapping[str, Any],
        output_schema: Mapping[str, Any],
        prompt_version: str,
        idempotency_key: IdempotencyKey,
    ) -> Mapping[str, Any]: ...
