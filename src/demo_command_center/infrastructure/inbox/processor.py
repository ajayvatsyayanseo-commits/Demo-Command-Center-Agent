from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import ClassVar, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.database.models import (
    AgentInboxEvent,
    AgentOutboxEvent,
    CommunicationMessage,
    ConversationState,
    DemoCase,
    DemoRequirement,
    DemoStateTransition,
    ExternalIdentityMapping,
    OnboardingHandoff,
    PaidTransition,
    PaymentAttempt,
    PaymentOrder,
    ProviderWebhookEvent,
)
from demo_command_center.modules.demo_core.domain.identifiers import DemoId, UserId
from demo_command_center.modules.demo_core.domain.money import Money
from demo_command_center.modules.paid_transition.domain.verification import (
    EvidenceSource,
    PaymentDecisionKind,
    PaymentEvidence,
    PaymentOrderBinding,
    PaymentVerificationPolicy,
    verify_payment,
)
from demo_command_center.security.encryption import PayloadCipher
from demo_command_center.state.machine.demo_state import DemoState
from demo_command_center.state.transitions.table import TransitionCommand


class UnsupportedEventError(ValueError):
    """Raised when no versioned inbox handler is registered for an event."""


class HandoffMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(pattern=r"^(text|interactive|unknown)$")
    text: str | None = Field(default=None, max_length=4096)


class ServiceWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    last_user_message_at: datetime
    expires_at: datetime


class DemoHandoffPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_message_ref: str = Field(min_length=1, max_length=255)
    intent: str = Field(pattern=r"^demo_request$")
    lead_ref: str | None = Field(default=None, max_length=255)
    user_ref: str | None = Field(default=None, max_length=255)
    message: HandoffMessage
    service_window: ServiceWindow
    consent_refs: list[str] = Field(max_length=20)


class OnboardingAcceptedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    demo_ref: str = Field(min_length=1, max_length=255)
    user_ref: str = Field(min_length=1, max_length=255)
    onboarding_ref: str = Field(min_length=1, max_length=255)
    inbox_ref: str = Field(min_length=1, max_length=255)
    capability_version: str = Field(min_length=1, max_length=64)


class OnboardingCompletedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    demo_ref: str = Field(min_length=1, max_length=255)
    user_ref: str = Field(min_length=1, max_length=255)
    onboarding_ref: str = Field(min_length=1, max_length=255)
    completion_status: str = Field(pattern=r"^completed$")


REQUIRED_DEMO_FIELDS: tuple[str, ...] = (
    "class_level",
    "subject",
    "location_region",
    "mode",
    "preferred_times",
)

SUBJECT_ALIASES: dict[str, str] = {
    "math": "Mathematics",
    "maths": "Mathematics",
    "mathematics": "Mathematics",
    "science": "Science",
    "physics": "Physics",
    "chemistry": "Chemistry",
    "biology": "Biology",
    "english": "English",
    "hindi": "Hindi",
    "accounts": "Accounts",
    "accountancy": "Accountancy",
    "economics": "Economics",
    "business studies": "Business Studies",
    "computer": "Computer Science",
    "computer science": "Computer Science",
    "coding": "Coding",
    "programming": "Programming",
    "skating": "Skating",
}

CITY_ALIASES: dict[str, str] = {
    "gurgaon": "Gurugram",
    "gurugram": "Gurugram",
    "delhi": "Delhi",
    "new delhi": "New Delhi",
    "noida": "Noida",
    "faridabad": "Faridabad",
    "ghaziabad": "Ghaziabad",
    "mumbai": "Mumbai",
    "bangalore": "Bengaluru",
    "bengaluru": "Bengaluru",
    "pune": "Pune",
    "hyderabad": "Hyderabad",
    "chennai": "Chennai",
    "kolkata": "Kolkata",
}

BOARD_ALIASES: dict[str, str] = {
    "cbse": "CBSE",
    "icse": "ICSE",
    "ib": "IB",
    "igcse": "IGCSE",
    "state board": "State Board",
}

MODE_ALIASES: dict[str, str] = {
    "home": "home",
    "home tuition": "home",
    "offline": "home",
    "online": "online",
    "online classes": "online",
    "either": "either",
}

TIME_ALIASES: dict[str, str] = {
    "morning": "morning",
    "afternoon": "afternoon",
    "evening": "evening",
    "weekend": "weekend",
}


class InboxEventHandler(Protocol):
    async def handle(self, event: AgentEventEnvelope, session: AsyncSession) -> None: ...


def _normalise_text(text: str | None) -> str:
    if not text:
        return ""
    value = text.lower()
    value = value.replace("don't", "dont")
    value = value.replace("feom", "from")
    value = value.replace("sgart", "start")
    return re.sub(r"\s+", " ", value).strip()


def _contains_negation(text: str) -> bool:
    return any(
        phrase in text
        for phrase in (
            " no ",
            "no ",
            " not ",
            "dont want",
            "do not want",
            "wrong",
            "change",
            "instead",
        )
    )


def _extract_alias(text: str, aliases: dict[str, str]) -> str | None:
    for raw, canonical in sorted(aliases.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"(?<![a-z0-9]){re.escape(raw)}(?![a-z0-9])", text):
            return canonical
    return None


def _subject_from_free_text(text: str) -> str | None:
    match = re.search(
        r"(?:for|subject is|subject|want(?: to do)?|need(?: tutor for)?)\s+([a-z][a-z &+-]{2,40})",
        text,
    )
    if match is not None:
        candidate = match.group(1).strip(" .,!?:;-")
        if not any(token in candidate for token in (" it ", "begin", "start", "from start")):
            aliased_candidate = _extract_alias(candidate, SUBJECT_ALIASES)
            if aliased_candidate is not None:
                return aliased_candidate
            if candidate not in {"demo", "teacher", "tutor", "classes", "online", "home"}:
                return candidate.title()
    return _extract_alias(text, SUBJECT_ALIASES)


def _extract_requirement_updates(
    text: str | None,
    *,
    current_step: str,
    current_subject: str | None = None,
) -> dict[str, object]:
    normalised = _normalise_text(text)
    updates: dict[str, object] = {}
    if not normalised:
        return updates

    negated_current_subject = False
    if current_subject and _contains_negation(f" {normalised} "):
        current = _normalise_text(current_subject)
        if current in normalised or _extract_alias(normalised, SUBJECT_ALIASES) == current_subject:
            updates["subject"] = None
            negated_current_subject = True

    class_match = re.search(r"(?:class|grade|std|standard)\s*([0-9]{1,2}|[a-z]+)", normalised)
    if class_match is not None:
        updates["class_level"] = f"Class {class_match.group(1).upper()}"

    board = _extract_alias(normalised, BOARD_ALIASES)
    if board is not None:
        updates["board"] = board

    city = _extract_alias(normalised, CITY_ALIASES)
    if city is not None:
        updates["location_region"] = city

    subject_text = normalised
    if negated_current_subject and " want " in f" {normalised} ":
        subject_text = normalised.rsplit(" want ", maxsplit=1)[-1]
    elif negated_current_subject and " instead " in f" {normalised} ":
        subject_text = normalised.rsplit(" instead ", maxsplit=1)[-1]
    elif negated_current_subject and " change " in f" {normalised} ":
        subject_text = normalised.rsplit(" change ", maxsplit=1)[-1]
    subject = _subject_from_free_text(subject_text)
    if subject is not None:
        if not (negated_current_subject and subject == current_subject):
            updates["subject"] = subject

    mode = _mode_from_text(normalised, current_step=current_step)
    if mode is not None:
        updates["mode"] = mode

    preferred_time = _preferred_time_from_text(normalised, current_step=current_step)
    if preferred_time is not None:
        updates["preferred_times"] = [{"label": preferred_time}]

    if "beginning" in normalised or "from start" in normalised or "starting" in normalised:
        updates["learning_goal"] = "Start from the beginning"

    return updates


def _mode_from_text(text: str, *, current_step: str) -> str | None:
    if current_step == "collect_mode":
        if text == "1":
            return "home"
        if text == "2":
            return "online"
        if text == "3":
            return "either"
    return _extract_alias(text, MODE_ALIASES)


def _preferred_time_from_text(text: str, *, current_step: str) -> str | None:
    if current_step == "collect_preferred_times":
        by_number = {"1": "morning", "2": "afternoon", "3": "evening", "4": "weekend"}
        if text in by_number:
            return by_number[text]
    return _extract_alias(text, TIME_ALIASES)


def _apply_requirement_updates(
    requirement: DemoRequirement, updates: dict[str, object]
) -> frozenset[str]:
    changed: set[str] = set()
    for field_name, value in updates.items():
        if getattr(requirement, field_name) != value:
            setattr(requirement, field_name, value)
            changed.add(field_name)
    return frozenset(changed)


def _missing_requirement_fields(requirement: DemoRequirement) -> list[str]:
    missing: list[str] = []
    if not requirement.class_level:
        missing.append("class_level")
    if not requirement.subject:
        missing.append("subject")
    if not requirement.location_region:
        missing.append("location_region")
    if not requirement.mode:
        missing.append("mode")
    if not requirement.preferred_times:
        missing.append("preferred_times")
    return missing


def _next_requirement_step(missing_fields: list[str]) -> str:
    if "class_level" in missing_fields or "location_region" in missing_fields:
        return "collect_class_city"
    if "subject" in missing_fields:
        return "collect_subject"
    if "mode" in missing_fields:
        return "collect_mode"
    if "preferred_times" in missing_fields:
        return "collect_preferred_times"
    return "requirements_complete"


def _safe_requirement_summary(requirement: DemoRequirement) -> str:
    values = [
        requirement.class_level,
        requirement.subject,
        requirement.location_region,
        requirement.mode,
        _preferred_time_label(requirement),
    ]
    summary = " | ".join(value for value in values if value)
    return summary or "Demo requested; requirements pending."


def _preferred_time_label(requirement: DemoRequirement) -> str | None:
    if not requirement.preferred_times:
        return None
    first = requirement.preferred_times[0]
    label = first.get("label") if isinstance(first, dict) else None
    return label if isinstance(label, str) else None


def _reply_variables(
    requirement: DemoRequirement, *, changed_fields: frozenset[str]
) -> dict[str, str]:
    missing = requirement.missing_fields
    body = _reply_body(requirement, changed_fields=changed_fields)
    return {
        "body": body,
        "missing_fields": ",".join(missing),
        "summary": _safe_requirement_summary(requirement),
        "current_step": _next_requirement_step(missing),
    }


def _reply_body(requirement: DemoRequirement, *, changed_fields: frozenset[str]) -> str:
    summary = _safe_requirement_summary(requirement)
    missing = requirement.missing_fields
    if "subject" in changed_fields and requirement.subject is None:
        return (
            "Got it — I removed the earlier subject. Which subject or skill should we arrange "
            "the tutor/demo for?"
        )
    if "class_level" in missing or "location_region" in missing:
        return "Got it. Which class is the student in, and which city should we arrange this in?"
    if "subject" in missing:
        return f"Got it. I have noted {summary}. Which subject or skill is this for?"
    if "mode" in missing:
        return (
            f"Got it. I have noted {summary}. Do you prefer home tuition or online classes?\n\n"
            "1. Home tuition\n2. Online classes\n3. Either is fine\n4. Talk to counsellor"
        )
    if "preferred_times" in missing:
        return (
            f"Got it. I have noted {summary}. What timing works best? How soon would you like "
            "to start?\n\n1. Morning\n2. Afternoon\n3. Evening\n4. Weekend\n5. Type custom time"
        )
    return (
        f"Perfect, I have the key details for {summary}. I will verify suitable tutor options "
        "and move this ahead."
    )


@dataclass(frozen=True, slots=True)
class DefaultInboxEventHandler:
    SUPPORTED_EVENT_TYPES: ClassVar[frozenset[str]] = frozenset(
        {
            "whatsapp.handoff.demo.v1",
            "cashfree.payment.webhook.received.v1",
            "meta.whatsapp.webhook.received.v1",
            "onboarding.handoff.accepted.v1",
            "onboarding.completed.v1",
        }
    )

    default_timezone: str
    cipher: PayloadCipher
    key_reference: str
    cashfree_environment: str = "sandbox"
    onboarding_policy_reference: str | None = None
    message_policy_reference: str | None = None
    welcome_template_reference: str | None = None
    welcome_message_version: str | None = None
    payment_policy_version: str = "cashfree-payment-v1"
    successful_payment_statuses: frozenset[str] = frozenset({"SUCCESS"})
    failed_payment_statuses: frozenset[str] = frozenset({"FAILED", "USER_DROPPED"})
    expired_payment_statuses: frozenset[str] = frozenset({"EXPIRED"})
    review_payment_statuses: frozenset[str] = frozenset(
        {"FLAGGED", "DISPUTED", "REFUNDED", "PARTIALLY_PAID"}
    )

    async def handle(self, event: AgentEventEnvelope, session: AsyncSession) -> None:
        if event.event_type == "whatsapp.handoff.demo.v1":
            await self._start_demo(event, session)
            return
        if event.event_type == "cashfree.payment.webhook.received.v1":
            await self._process_cashfree_event(event, session)
            return
        if event.event_type == "meta.whatsapp.webhook.received.v1":
            await self._record_provider_event(event, session)
            return
        if event.event_type == "onboarding.handoff.accepted.v1":
            await self._accept_onboarding(event, session)
            return
        if event.event_type == "onboarding.completed.v1":
            await self._complete_onboarding(event, session)
            return
        raise UnsupportedEventError(f"unsupported event type: {event.event_type}")

    async def _start_demo(self, event: AgentEventEnvelope, session: AsyncSession) -> None:
        payload = DemoHandoffPayload.model_validate(event.payload)
        existing_conversation = await session.scalar(
            select(ConversationState).where(
                ConversationState.tenant_id == event.tenant_id,
                ConversationState.conversation_id == event.conversation_id,
            )
        )
        if existing_conversation is not None:
            await self._continue_demo(
                event,
                payload,
                session,
                service_window_expires_at=payload.service_window.expires_at,
                conversation=existing_conversation,
            )
            return
        demo_id = uuid5(NAMESPACE_URL, f"nxtutors:demo:{event.event_id}")
        existing = await session.scalar(select(DemoCase.id).where(DemoCase.id == demo_id))
        if existing is not None:
            return
        timezone = self.default_timezone
        initial_requirement = DemoRequirement(
            demo_case_id=demo_id,
            timezone=timezone,
            preferred_times=[],
            missing_fields=list(REQUIRED_DEMO_FIELDS),
            version=1,
        )
        _apply_requirement_updates(
            initial_requirement,
            _extract_requirement_updates(payload.message.text, current_step="collect_requirements"),
        )
        initial_requirement.missing_fields = _missing_requirement_fields(initial_requirement)
        demo = DemoCase(
            id=demo_id,
            tenant_id=event.tenant_id,
            region_id=event.region_id,
            external_lead_id=payload.lead_ref,
            external_user_id=payload.user_ref,
            conversation_id=event.conversation_id,
            state=DemoState.QUALIFYING.value,
            participant_timezone=timezone,
            flow_version="demo-flow-v1",
            version=1,
        )
        session.add(demo)
        # The follow-on requirement, conversation-state, transition, and outbox rows all
        # carry explicit foreign keys to the deterministic demo id.  Flush the parent
        # case first so PostgreSQL never has to rely on implicit unit-of-work ordering.
        await session.flush()
        session.add(initial_requirement)
        session.add(
            ConversationState(
                tenant_id=event.tenant_id,
                demo_case_id=demo_id,
                conversation_id=event.conversation_id,
                current_step=_next_requirement_step(initial_requirement.missing_fields),
                safe_summary=_safe_requirement_summary(initial_requirement),
                flow_version="demo-flow-v1",
                version=1,
            )
        )
        for system, entity_type, external_id in (
            ("lead-intake", "lead", payload.lead_ref),
            ("nxtutors-website", "user", payload.user_ref),
        ):
            if external_id:
                existing_mapping = await session.scalar(
                    select(ExternalIdentityMapping).where(
                        ExternalIdentityMapping.tenant_id == event.tenant_id,
                        ExternalIdentityMapping.system == system,
                        ExternalIdentityMapping.entity_type == entity_type,
                        ExternalIdentityMapping.external_id == external_id,
                    )
                )
                if existing_mapping is None:
                    session.add(
                        ExternalIdentityMapping(
                            tenant_id=event.tenant_id,
                            system=system,
                            entity_type=entity_type,
                            external_id=external_id,
                            internal_id=demo_id,
                            last_verified_at=event.occurred_at,
                        )
                    )
                else:
                    existing_mapping.last_verified_at = event.occurred_at
        session.add(
            DemoStateTransition(
                demo_case_id=demo_id,
                state_before=DemoState.NEW.value,
                state_after=DemoState.QUALIFYING.value,
                command=TransitionCommand.START_QUALIFICATION.value,
                actor_type=event.actor.type.value,
                actor_ref=event.actor.id,
                reason_code="DEMO_HANDOFF_ACCEPTED",
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                idempotency_key=event.idempotency_key,
                flow_version="demo-flow-v1",
                policy_version="handoff-policy-v1",
                side_effects_requested=["request_missing_requirements"],
                side_effects_completed=[],
            )
        )
        self._add_demo_reply_outbox(
            session,
            event=event,
            demo_id=demo_id,
            target_agent=event.source_agent,
            service_window_expires_at=payload.service_window.expires_at,
            template_ref="demo.collect_requirements.v1",
            variables=_reply_variables(initial_requirement, changed_fields=frozenset()),
        )

    async def _continue_demo(
        self,
        event: AgentEventEnvelope,
        payload: DemoHandoffPayload,
        session: AsyncSession,
        *,
        service_window_expires_at: datetime,
        conversation: ConversationState | None = None,
    ) -> None:
        if conversation is None:
            conversation = await session.scalar(
                select(ConversationState).where(
                    ConversationState.tenant_id == event.tenant_id,
                    ConversationState.conversation_id == event.conversation_id,
                )
            )
        if conversation is None or conversation.demo_case_id is None:
            raise ValueError("WhatsApp demo reply has no durable conversation state")
        requirement = await session.scalar(
            select(DemoRequirement).where(DemoRequirement.demo_case_id == conversation.demo_case_id)
        )
        if requirement is None:
            raise ValueError("WhatsApp demo reply has no durable requirements row")

        updates = _extract_requirement_updates(
            payload.message.text,
            current_step=conversation.current_step,
            current_subject=requirement.subject,
        )
        changed_fields = _apply_requirement_updates(requirement, updates)
        requirement.missing_fields = _missing_requirement_fields(requirement)
        requirement.version += 1
        conversation.current_step = _next_requirement_step(requirement.missing_fields)
        conversation.safe_summary = _safe_requirement_summary(requirement)
        conversation.version += 1

        self._add_demo_reply_outbox(
            session,
            event=event,
            demo_id=conversation.demo_case_id,
            target_agent=event.source_agent,
            service_window_expires_at=service_window_expires_at,
            template_ref="demo.collect_requirements.v1",
            variables=_reply_variables(requirement, changed_fields=changed_fields),
        )

    def _add_demo_reply_outbox(
        self,
        session: AsyncSession,
        *,
        event: AgentEventEnvelope,
        demo_id: UUID,
        target_agent: str,
        service_window_expires_at: datetime,
        template_ref: str,
        variables: dict[str, str],
    ) -> None:
        outbox_event_id = uuid5(NAMESPACE_URL, f"nxtutors:demo-reply:{event.event_id}")
        send_key = f"demo-reply:{event.event_id}"
        outbox_payload = {
            "event_id": str(outbox_event_id),
            "event_type": "outbound.delivery.requested.v1",
            "demo_id": str(demo_id),
            "recipient_ref": event.conversation_id,
            "template_or_message_ref": template_ref,
            "variables": variables,
            "message_category": "service",
            "service_window_expires_at": service_window_expires_at.isoformat(),
            "send_key": send_key,
        }
        serialized = json.dumps(outbox_payload, sort_keys=True, separators=(",", ":")).encode()
        associated_data = f"{event.tenant_id}:{event.source_agent}:{outbox_event_id}".encode()
        session.add(
            AgentOutboxEvent(
                event_id=outbox_event_id,
                event_type="outbound.delivery.requested.v1",
                schema_version="1.0",
                tenant_id=event.tenant_id,
                target_agent=target_agent,
                idempotency_key=send_key,
                correlation_id=event.correlation_id,
                payload_ciphertext=self.cipher.encrypt(
                    serialized,
                    associated_data=associated_data,
                ),
                available_at=datetime.now(UTC),
                attempts=0,
            )
        )

    async def _record_provider_event(
        self, event: AgentEventEnvelope, session: AsyncSession
    ) -> None:
        raw = json.dumps(event.payload, sort_keys=True, separators=(",", ":")).encode()
        payload_hash = hashlib.sha256(raw).hexdigest()
        provider = "cashfree" if event.source_agent == "cashfree" else "meta"
        associated_data = f"{provider}:{event.event_id}".encode()
        session.add(
            ProviderWebhookEvent(
                tenant_id=event.tenant_id,
                provider=provider,
                provider_event_id=str(event.event_id),
                event_type=event.event_type,
                payload_hash=payload_hash,
                payload_ciphertext=self.cipher.encrypt(raw, associated_data=associated_data),
                payload_key_reference=self.key_reference,
                occurred_at=event.occurred_at,
                status="recorded",
            )
        )

    async def _accept_onboarding(self, event: AgentEventEnvelope, session: AsyncSession) -> None:
        payload = OnboardingAcceptedPayload.model_validate(event.payload)
        if self.onboarding_policy_reference is None:
            raise ValueError("onboarding handoff policy is not configured")
        handoff, order, demo = await self._load_onboarding_context(
            session,
            tenant_id=event.tenant_id,
            demo_ref=payload.demo_ref,
            user_ref=payload.user_ref,
        )
        handoff.status = "accepted"
        handoff.acknowledgement_ref = payload.onboarding_ref
        handoff.acknowledged_at = event.occurred_at
        if demo.state == DemoState.ONBOARDING_HANDOFF.value:
            return
        if demo.state != DemoState.PAID.value or order.status != "paid":
            raise ValueError("onboarding acceptance arrived before verified payment")
        before = demo.state
        demo.state = DemoState.ONBOARDING_HANDOFF.value
        demo.version += 1
        session.add(
            DemoStateTransition(
                demo_case_id=demo.id,
                state_before=before,
                state_after=DemoState.ONBOARDING_HANDOFF.value,
                command=TransitionCommand.HANDOFF_ONBOARDING.value,
                actor_type=event.actor.type.value,
                actor_ref=event.actor.id,
                reason_code="ONBOARDING_DURABLY_ACCEPTED",
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                idempotency_key=event.idempotency_key,
                flow_version=demo.flow_version,
                policy_version=self.onboarding_policy_reference,
                side_effects_requested=["await_onboarding_completion"],
                side_effects_completed=["publish_onboarding_handoff"],
            )
        )

    async def _complete_onboarding(self, event: AgentEventEnvelope, session: AsyncSession) -> None:
        payload = OnboardingCompletedPayload.model_validate(event.payload)
        if not all(
            [
                self.message_policy_reference,
                self.welcome_template_reference,
                self.welcome_message_version,
            ]
        ):
            raise ValueError("welcome delivery policy is not configured")
        handoff, order, demo = await self._load_onboarding_context(
            session,
            tenant_id=event.tenant_id,
            demo_ref=payload.demo_ref,
            user_ref=payload.user_ref,
        )
        if handoff.status == "completed" and demo.state == DemoState.CONVERTED.value:
            return
        if handoff.status != "accepted" or demo.state != DemoState.ONBOARDING_HANDOFF.value:
            raise ValueError("onboarding completion arrived before durable acceptance")
        before = demo.state
        demo.state = DemoState.CONVERTED.value
        demo.version += 1
        handoff.status = "completed"
        send_key = f"welcome:{handoff.id}"
        message_id = uuid5(NAMESPACE_URL, f"nxtutors:message:{send_key}")
        handoff.welcome_message_id = message_id
        session.add(
            CommunicationMessage(
                id=message_id,
                tenant_id=event.tenant_id,
                demo_case_id=demo.id,
                direction="outbound",
                channel="whatsapp",
                recipient_ref=demo.conversation_id,
                message_category="utility",
                template_ref=self.welcome_template_reference,
                content_source_refs=[payload.onboarding_ref],
                policy_version=self.message_policy_reference,
                message_version=self.welcome_message_version,
                idempotency_key=send_key,
                approved_by="deterministic-policy",
                service_window_ends_at=event.occurred_at,
            )
        )
        session.add(
            DemoStateTransition(
                demo_case_id=demo.id,
                state_before=before,
                state_after=DemoState.CONVERTED.value,
                command=TransitionCommand.COMPLETE_ONBOARDING.value,
                actor_type=event.actor.type.value,
                actor_ref=event.actor.id,
                reason_code="ONBOARDING_COMPLETED",
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                idempotency_key=event.idempotency_key,
                flow_version=demo.flow_version,
                policy_version=self.message_policy_reference,
                side_effects_requested=["request_welcome_delivery"],
                side_effects_completed=["onboarding_completed"],
            )
        )
        outbox_event_id = uuid5(NAMESPACE_URL, f"nxtutors:outbox:{send_key}")
        outbox_payload = {
            "event_id": str(outbox_event_id),
            "event_type": "outbound.delivery.requested.v1",
            "demo_id": str(demo.id),
            "recipient_ref": demo.conversation_id,
            "template_or_message_ref": self.welcome_template_reference,
            "variables": {"onboarding_ref": payload.onboarding_ref},
            "message_category": "utility",
            "service_window_expires_at": event.occurred_at.isoformat(),
            "send_key": send_key,
        }
        raw = json.dumps(outbox_payload, sort_keys=True, separators=(",", ":")).encode()
        associated_data = f"{event.tenant_id}:lead-intake-agent:{outbox_event_id}".encode()
        session.add(
            AgentOutboxEvent(
                event_id=outbox_event_id,
                event_type="outbound.delivery.requested.v1",
                schema_version="1.0",
                tenant_id=event.tenant_id,
                target_agent="lead-intake-agent",
                idempotency_key=send_key,
                correlation_id=event.correlation_id,
                payload_ciphertext=self.cipher.encrypt(raw, associated_data=associated_data),
                available_at=datetime.now(UTC),
                attempts=0,
            )
        )

    @staticmethod
    async def _load_onboarding_context(
        session: AsyncSession,
        *,
        tenant_id: str,
        demo_ref: str,
        user_ref: str,
    ) -> tuple[OnboardingHandoff, PaymentOrder, DemoCase]:
        demo_id = UUID(demo_ref)
        orders = list(
            (
                await session.scalars(
                    select(PaymentOrder)
                    .where(
                        PaymentOrder.tenant_id == tenant_id,
                        PaymentOrder.demo_case_id == demo_id,
                        PaymentOrder.user_ref == user_ref,
                    )
                    .limit(2)
                    .with_for_update()
                )
            ).all()
        )
        if not orders:
            raise ValueError("onboarding event has no bound payment order")
        if len(orders) != 1:
            raise ValueError("onboarding event matches multiple payment orders")
        order = orders[0]
        paid_transition = await session.scalar(
            select(PaidTransition).where(PaidTransition.payment_order_id == order.id)
        )
        if paid_transition is None:
            raise ValueError("onboarding event has no durable paid transition")
        handoff = await session.scalar(
            select(OnboardingHandoff)
            .where(OnboardingHandoff.paid_transition_id == paid_transition.id)
            .with_for_update()
        )
        demo = await session.get(DemoCase, demo_id, with_for_update=True)
        if handoff is None or demo is None:
            raise ValueError("onboarding event has no durable handoff")
        return handoff, order, demo

    async def _process_cashfree_event(
        self, event: AgentEventEnvelope, session: AsyncSession
    ) -> None:
        provider_event = await self._new_provider_event(event, session)
        payload = event.payload
        data = payload.get("data")
        data = data if isinstance(data, dict) else {}
        payment = data.get("payment")
        payment = payment if isinstance(payment, dict) else {}
        provider_order = data.get("order")
        provider_order = provider_order if isinstance(provider_order, dict) else {}
        customer = data.get("customer_details")
        customer = customer if isinstance(customer, dict) else {}
        tags = provider_order.get("order_tags")
        tags = tags if isinstance(tags, dict) else {}
        domain_order_id = _required_string(provider_order.get("order_id"), "order_id")
        evidence_provider_order_id = _required_reference(
            provider_order.get("cf_order_id"), "cf_order_id"
        )
        provider_payment_id = _required_reference(payment.get("cf_payment_id"), "cf_payment_id")
        status = _required_string(payment.get("payment_status"), "payment_status").upper()
        currency = _required_string(payment.get("payment_currency"), "payment_currency").upper()
        order = await session.scalar(
            select(PaymentOrder)
            .where(PaymentOrder.domain_order_id == domain_order_id)
            .with_for_update()
        )
        if order is None or order.provider_order_id is None:
            raise ValueError("Cashfree webhook has no bound local payment order")
        amount_minor = _money_minor(payment.get("payment_amount"))
        session.add(
            PaymentAttempt(
                payment_order_id=order.id,
                provider="cashfree",
                provider_payment_id=provider_payment_id,
                provider_webhook_event_id=provider_event.id,
                status=status,
                amount_minor=amount_minor,
                currency=currency,
                occurred_at=event.occurred_at,
            )
        )
        already_paid = await session.scalar(
            select(PaidTransition.id).where(PaidTransition.payment_order_id == order.id)
        )
        decision = verify_payment(
            PaymentOrderBinding(
                domain_order_id=order.domain_order_id,
                provider_order_id=evidence_provider_order_id,
                demo_id=DemoId(str(order.demo_case_id)),
                user_id=UserId(order.user_ref),
                customer_ref=order.customer_ref,
                plan_ref=order.plan_ref,
                offer_ref=str(order.offer_id) if order.offer_id else None,
                amount=Money(order.amount_minor, order.currency),
                purpose=order.purpose,
                environment=order.provider_environment,
                expires_at=order.expires_at,
            ),
            PaymentEvidence(
                provider_event_id=str(event.event_id),
                provider_order_id=order.provider_order_id,
                source=EvidenceSource.SIGNED_WEBHOOK,
                status=status,
                amount=Money(amount_minor, currency),
                customer_ref=str(customer.get("customer_id", "")),
                purpose=str(tags.get("purpose", "")),
                environment=str(tags.get("environment", self.cashfree_environment)),
                occurred_at=event.occurred_at,
                signature_verified=True,
                replay_window_verified=True,
                provider_authentication_verified=False,
            ),
            PaymentVerificationPolicy(
                version=self.payment_policy_version,
                successful_terminal_statuses=self.successful_payment_statuses,
                failed_terminal_statuses=self.failed_payment_statuses,
                expired_terminal_statuses=self.expired_payment_statuses,
                review_statuses=self.review_payment_statuses,
            ),
            processed_event_ids=frozenset(),
            paid_activation_already_applied=already_paid is not None,
            now=datetime.now(UTC),
        )
        provider_event.status = decision.kind.value
        provider_event.processed_at = datetime.now(UTC)
        if decision.kind is PaymentDecisionKind.TRANSITION_PAID:
            if decision.activation_key is None or decision.paid_outbox_key is None:
                raise ValueError("paid decision omitted exactly-once keys")
            await self._apply_paid_transition(
                event,
                session,
                order,
                provider_payment_id,
                decision.activation_key,
                decision.paid_outbox_key,
            )
        elif decision.kind in {
            PaymentDecisionKind.REVIEW,
            PaymentDecisionKind.REJECTED_EVIDENCE,
        }:
            order.status = "payment_review"
        elif decision.kind is PaymentDecisionKind.FAILED:
            order.status = "failed"
        elif decision.kind is PaymentDecisionKind.EXPIRED:
            order.status = "expired"
        elif decision.kind is PaymentDecisionKind.RECONCILE:
            order.status = "reconciliation_required"

    async def _new_provider_event(
        self, event: AgentEventEnvelope, session: AsyncSession
    ) -> ProviderWebhookEvent:
        raw = json.dumps(event.payload, sort_keys=True, separators=(",", ":")).encode()
        associated_data = f"cashfree:{event.event_id}".encode()
        provider_event = ProviderWebhookEvent(
            tenant_id=event.tenant_id,
            provider="cashfree",
            provider_event_id=str(event.event_id),
            event_type=event.event_type,
            payload_hash=hashlib.sha256(raw).hexdigest(),
            payload_ciphertext=self.cipher.encrypt(raw, associated_data=associated_data),
            payload_key_reference=self.key_reference,
            occurred_at=event.occurred_at,
            status="processing",
        )
        session.add(provider_event)
        await session.flush()
        return provider_event

    async def _apply_paid_transition(
        self,
        event: AgentEventEnvelope,
        session: AsyncSession,
        order: PaymentOrder,
        provider_payment_id: str,
        activation_key: str,
        outbox_key: str,
    ) -> None:
        demo = await session.scalar(
            select(DemoCase).where(DemoCase.id == order.demo_case_id).with_for_update()
        )
        if demo is None or demo.state not in {
            DemoState.PAYMENT_PENDING.value,
            DemoState.PAYMENT_REVIEW.value,
        }:
            order.status = "payment_review"
            return
        before = demo.state
        demo.state = DemoState.PAID.value
        demo.version += 1
        order.status = "paid"
        order.paid_at = event.occurred_at
        order.version += 1
        session.add(
            PaidTransition(
                payment_order_id=order.id,
                provider_payment_id=provider_payment_id,
                website_activation_key=activation_key,
                verified_amount_minor=order.amount_minor,
                verified_currency=order.currency,
                verification_source=EvidenceSource.SIGNED_WEBHOOK.value,
                transitioned_at=event.occurred_at,
            )
        )
        session.add(
            DemoStateTransition(
                demo_case_id=demo.id,
                state_before=before,
                state_after=DemoState.PAID.value,
                command=TransitionCommand.VERIFY_PAYMENT.value,
                actor_type="provider",
                actor_ref="cashfree",
                reason_code="VERIFIED_TERMINAL_SUCCESS",
                occurred_at=event.occurred_at,
                correlation_id=event.correlation_id,
                idempotency_key=event.idempotency_key,
                flow_version=demo.flow_version,
                policy_version=self.payment_policy_version,
                side_effects_requested=["activate_website_subscription"],
                side_effects_completed=[],
            )
        )
        outbox_event_id = uuid5(NAMESPACE_URL, f"nxtutors:paid:{order.id}")
        try:
            plan_id = int(order.plan_ref)
        except ValueError as exc:
            raise ValueError("payment order is not bound to a numeric website plan ID") from exc
        if plan_id <= 0:
            raise ValueError("payment order is not bound to a positive website plan ID")
        payload = {
            "event_type": "demo.payment.verified.v1",
            "demo_ref": str(demo.id),
            "website_user_ref": order.user_ref,
            "plan_id": plan_id,
            "plan_version": order.plan_version,
            "amount_minor": order.amount_minor,
            "currency": order.currency,
            "provider_order_ref": order.provider_order_id,
            "payment_evidence_ref": provider_payment_id,
            "payment_verified_at": event.occurred_at.isoformat(),
            "correlation_id": order.correlation_id,
            "activation_key": activation_key,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        associated_data = f"{order.tenant_id}:nxtutors-website-gateway:{outbox_event_id}".encode()
        session.add(
            AgentOutboxEvent(
                event_id=outbox_event_id,
                event_type="demo.payment.verified.v1",
                schema_version="1.0",
                tenant_id=order.tenant_id,
                target_agent="nxtutors-website-gateway",
                idempotency_key=outbox_key,
                correlation_id=order.correlation_id,
                payload_ciphertext=self.cipher.encrypt(raw, associated_data=associated_data),
                available_at=datetime.now(UTC),
                attempts=0,
            )
        )


def _money_minor(value: object) -> int:
    try:
        amount = Decimal(str(value))
        if amount < 0:
            raise ValueError("payment amount cannot be negative")
        return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("payment amount is invalid") from exc


def _required_string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Cashfree webhook is missing {field_name}")
    return value.strip()


def _required_reference(value: object, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, str | int):
        raise ValueError(f"Cashfree webhook is missing {field_name}")
    reference = str(value).strip()
    if not reference:
        raise ValueError(f"Cashfree webhook is missing {field_name}")
    return reference


@dataclass(frozen=True, slots=True)
class InboxBatchResult:
    processed: int
    failed: int


@dataclass(frozen=True, slots=True)
class DurableInboxProcessor:
    sessions: async_sessionmaker[AsyncSession]
    cipher: PayloadCipher
    handler: InboxEventHandler
    blocked_event_types: frozenset[str] = frozenset()
    maximum_attempts: int = 8

    @staticmethod
    def _associated_data(row: AgentInboxEvent) -> bytes:
        return f"{row.tenant_id}:{row.source_agent}:{row.event_id}".encode()

    async def process_batch(self, *, batch_size: int = 10) -> InboxBatchResult:
        processed = 0
        failed = 0
        for _ in range(batch_size):
            outcome = await self._process_one()
            if outcome is None:
                break
            if outcome:
                processed += 1
            else:
                failed += 1
        return InboxBatchResult(processed=processed, failed=failed)

    async def _process_one(self) -> bool | None:
        event_row_id: int | None = None
        async with self.sessions() as session:
            statement = select(AgentInboxEvent).where(
                AgentInboxEvent.processed_at.is_(None),
                AgentInboxEvent.processing_attempts < self.maximum_attempts,
            )
            if self.blocked_event_types:
                statement = statement.where(
                    AgentInboxEvent.event_type.not_in(self.blocked_event_types)
                )
            row = await session.scalar(
                statement.order_by(AgentInboxEvent.received_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if row is None:
                return None
            event_row_id = row.id
            try:
                plaintext = self.cipher.decrypt(
                    row.payload_ciphertext,
                    associated_data=self._associated_data(row),
                )
                event = AgentEventEnvelope.model_validate_json(plaintext)
                await self.handler.handle(event, session)
                row.processed_at = datetime.now(UTC)
                row.processing_attempts += 1
                row.error_code = None
                await session.commit()
                return True
            except Exception:  # poison events are classified without persisting provider text
                await session.rollback()
        if event_row_id is not None:
            async with self.sessions() as failure_session:
                failed_row = await failure_session.get(AgentInboxEvent, event_row_id)
                if failed_row is not None:
                    failed_row.processing_attempts += 1
                    failed_row.error_code = "DCC_INBOX_PROCESSING_FAILED"
                    await failure_session.commit()
        return False
