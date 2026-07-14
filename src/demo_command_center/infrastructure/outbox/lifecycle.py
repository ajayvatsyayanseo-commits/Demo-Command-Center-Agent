from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from demo_command_center.glue.envelopes.agent_event import (
    ActorType,
    AgentEventEnvelope,
    EventActor,
    EventSubject,
    PiiClassification,
)
from demo_command_center.infrastructure.database.models import (
    AgentOutboxEvent,
    ConsentRecord,
    DemoCase,
    DemoStateTransition,
    OnboardingHandoff,
    PaidTransition,
    PaymentOrder,
)
from demo_command_center.security.encryption import PayloadCipher
from demo_command_center.state.machine.demo_state import DemoState
from demo_command_center.state.transitions.table import TransitionCommand


@dataclass(frozen=True, slots=True)
class LifecycleOutboxDeliveryRecorder:
    """Persists saga progress and follow-up effects in the outbox transaction."""

    cipher: PayloadCipher
    source_agent: str
    onboarding_locale: str
    onboarding_policy_reference: str

    async def record(
        self,
        *,
        row: AgentOutboxEvent,
        payload: Mapping[str, Any],
        provider_reference: str,
        restricted_details: Mapping[str, Any],
        session: AsyncSession,
    ) -> None:
        del restricted_details
        if row.event_type == "demo.payment.verified.v1":
            await self._queue_onboarding(
                row=row,
                payload=payload,
                activation_ref=provider_reference,
                session=session,
            )
        elif row.event_type == "onboarding.paid-user.requested.v1":
            await self._record_onboarding_acceptance(
                row=row,
                acknowledgement_ref=provider_reference,
                session=session,
            )

    async def _queue_onboarding(
        self,
        *,
        row: AgentOutboxEvent,
        payload: Mapping[str, Any],
        activation_ref: str,
        session: AsyncSession,
    ) -> None:
        provider_order_ref = _required_text(payload, "provider_order_ref")
        payment_ref = _required_text(payload, "payment_evidence_ref")
        demo_ref = _required_text(payload, "demo_ref")
        demo_id = UUID(demo_ref)
        order = await session.scalar(
            select(PaymentOrder)
            .where(
                PaymentOrder.tenant_id == row.tenant_id,
                PaymentOrder.provider_order_id == provider_order_ref,
                PaymentOrder.demo_case_id == demo_id,
            )
            .with_for_update()
        )
        if order is None:
            raise ValueError("website activation has no bound payment order")
        paid_transition = await session.scalar(
            select(PaidTransition).where(PaidTransition.payment_order_id == order.id)
        )
        if paid_transition is None:
            raise ValueError("website activation preceded the durable paid transition")
        operation_key = f"onboarding-paid:{paid_transition.id}"
        existing = await session.scalar(
            select(OnboardingHandoff.id).where(
                OnboardingHandoff.tenant_id == row.tenant_id,
                OnboardingHandoff.idempotency_key == operation_key,
            )
        )
        if existing is not None:
            return
        demo = await session.get(DemoCase, order.demo_case_id)
        if demo is None or demo.state != DemoState.PAID.value:
            raise ValueError("onboarding can only be queued from PAID")
        consent_refs = list(
            (
                await session.scalars(
                    select(ConsentRecord.evidence_ref).where(
                        ConsentRecord.tenant_id == row.tenant_id,
                        ConsentRecord.subject_ref == order.user_ref,
                        ConsentRecord.status == "granted",
                    )
                )
            ).all()
        )[:20]
        event_id = uuid5(NAMESPACE_URL, f"nxtutors:{operation_key}")
        event = AgentEventEnvelope(
            event_id=event_id,
            event_type="onboarding.paid-user.requested.v1",
            occurred_at=datetime.now(UTC),
            source_agent=self.source_agent,
            target_agent="onboarding-agent",
            tenant_id=row.tenant_id,
            region_id=demo.region_id,
            correlation_id=row.correlation_id,
            causation_id=str(row.event_id),
            conversation_id=demo.conversation_id,
            actor=EventActor(type=ActorType.SYSTEM, id=self.source_agent),
            subject=EventSubject(user_id=order.user_ref, demo_id=str(demo.id)),
            idempotency_key=operation_key,
            pii_classification=PiiClassification.LOW,
            payload={
                "demo_ref": str(demo.id),
                "user_ref": order.user_ref,
                "activation_ref": activation_ref,
                "payment_ref": payment_ref,
                "plan_ref": order.plan_ref,
                "locale": self.onboarding_locale,
                "consent_refs": consent_refs,
                "requested_flow": "existing_account",
            },
        )
        session.add(
            OnboardingHandoff(
                tenant_id=row.tenant_id,
                paid_transition_id=paid_transition.id,
                idempotency_key=operation_key,
                onboarding_required=True,
                status="pending",
                attempt_count=0,
            )
        )
        raw = json.dumps(
            event.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        associated_data = f"{row.tenant_id}:onboarding-agent:{event_id}".encode()
        session.add(
            AgentOutboxEvent(
                event_id=event_id,
                event_type=event.event_type,
                schema_version=event.schema_version,
                tenant_id=row.tenant_id,
                target_agent=event.target_agent,
                idempotency_key=operation_key,
                correlation_id=row.correlation_id,
                payload_ciphertext=self.cipher.encrypt(raw, associated_data=associated_data),
                available_at=datetime.now(UTC),
                attempts=0,
            )
        )

    async def _record_onboarding_acceptance(
        self,
        *,
        row: AgentOutboxEvent,
        acknowledgement_ref: str,
        session: AsyncSession,
    ) -> None:
        handoff = await session.scalar(
            select(OnboardingHandoff)
            .where(
                OnboardingHandoff.tenant_id == row.tenant_id,
                OnboardingHandoff.idempotency_key == row.idempotency_key,
            )
            .with_for_update()
        )
        if handoff is None:
            raise ValueError("onboarding acknowledgement has no durable handoff")
        paid_transition = await session.get(PaidTransition, handoff.paid_transition_id)
        if paid_transition is None:
            raise ValueError("onboarding handoff lost its paid transition")
        order = await session.get(PaymentOrder, paid_transition.payment_order_id)
        if order is None:
            raise ValueError("onboarding handoff lost its payment order")
        demo = await session.get(DemoCase, order.demo_case_id, with_for_update=True)
        if demo is None:
            raise ValueError("onboarding handoff lost its demo")
        handoff.status = "accepted"
        handoff.acknowledgement_ref = acknowledgement_ref[:255]
        handoff.attempt_count += 1
        handoff.acknowledged_at = datetime.now(UTC)
        if demo.state == DemoState.ONBOARDING_HANDOFF.value:
            return
        if demo.state != DemoState.PAID.value:
            raise ValueError("onboarding acknowledgement arrived in an invalid demo state")
        before = demo.state
        demo.state = DemoState.ONBOARDING_HANDOFF.value
        demo.version += 1
        session.add(
            DemoStateTransition(
                demo_case_id=demo.id,
                state_before=before,
                state_after=DemoState.ONBOARDING_HANDOFF.value,
                command=TransitionCommand.HANDOFF_ONBOARDING.value,
                actor_type=ActorType.SYSTEM.value,
                actor_ref=self.source_agent,
                reason_code="ONBOARDING_DURABLY_ACCEPTED",
                occurred_at=datetime.now(UTC),
                correlation_id=row.correlation_id,
                idempotency_key=f"onboarding-accepted:{handoff.id}",
                flow_version=demo.flow_version,
                policy_version=self.onboarding_policy_reference,
                side_effects_requested=["await_onboarding_completion"],
                side_effects_completed=["publish_onboarding_handoff"],
            )
        )


def _required_text(payload: Mapping[str, Any], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"outbox payload is missing {field_name}")
    return value
