from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Literal

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, IdempotencyKey
from demo_command_center.modules.demo_core.ports.gateways import (
    CalendarEventResult,
    CalendarPort,
    MessagingPort,
    OutboundMessageRequest,
    WebsiteGatewayPort,
    WebsitePhoneRecipient,
)
from demo_command_center.modules.scheduling.domain.policy import (
    Confirmation,
    ConfirmationDecision,
    SchedulingPolicy,
    SlotHold,
    SlotOption,
    create_hold,
    evaluate_confirmations,
)


@dataclass(frozen=True, slots=True)
class SchedulingDecisionService:
    policy: SchedulingPolicy

    def hold(self, demo_id: DemoId, option: SlotOption, *, now: datetime) -> SlotHold:
        return create_hold(demo_id, option, self.policy, now=now)

    def confirm(
        self,
        hold: SlotHold,
        confirmations: tuple[Confirmation, ...],
        *,
        now: datetime,
    ) -> ConfirmationDecision:
        return evaluate_confirmations(hold, confirmations, self.policy, now=now)


@dataclass(frozen=True, slots=True)
class TutorAcceptanceRequest:
    demo_id: DemoId
    tutor_ref: str
    learner_register_ref: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    service_window_expires_at: datetime
    correlation_id: str
    template_ref: str = "demo.tutor_acceptance.v1"
    variables: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TutorAcceptanceResult:
    tutor_recipient: WebsitePhoneRecipient
    delivery_ref: str
    idempotency_key: IdempotencyKey


@dataclass(frozen=True, slots=True)
class ScheduleAfterTutorAcceptanceRequest:
    demo_id: DemoId
    tutor_ref: str
    learner_register_ref: str
    starts_at: datetime
    ends_at: datetime
    timezone: str
    service_window_expires_at: datetime
    correlation_id: str
    tutor_acceptance_confirmed: bool
    tutor_acceptance_evidence_ref: str
    calendar_attendee_refs: tuple[str, ...] = field(default_factory=tuple)
    tutor_template_ref: str = "demo.tutor_session_link.v1"
    learner_template_ref: str = "demo.learner_session_link.v1"


@dataclass(frozen=True, slots=True)
class ScheduledMeetingResult:
    calendar_event: CalendarEventResult
    status: Literal["scheduled", "conference_pending"]
    tutor_recipient: WebsitePhoneRecipient
    learner_recipient: WebsitePhoneRecipient
    tutor_delivery_ref: str | None
    learner_delivery_ref: str | None
    conference_request_id: str


@dataclass(frozen=True, slots=True)
class TutorFirstSchedulingCoordinator:
    """Coordinates teacher approval before a Google Meet link is sent."""

    website: WebsiteGatewayPort
    messaging: MessagingPort
    calendar: CalendarPort

    async def request_tutor_acceptance(
        self, request: TutorAcceptanceRequest, *, idempotency_key: IdempotencyKey
    ) -> TutorAcceptanceResult:
        _validate_window(request.starts_at, request.ends_at)
        _require_aware(request.service_window_expires_at, "service_window_expires_at")
        tutor = await self.website.resolve_tutor_phone_recipient(
            request.tutor_ref,
            demo_ref=str(request.demo_id),
            purpose="demo_tutor_acceptance",
        )
        send_key = _operation_key("tutor-acceptance", str(request.demo_id), str(idempotency_key))
        delivery_ref = await self.messaging.request_delivery(
            OutboundMessageRequest(
                demo_id=request.demo_id,
                recipient_ref=tutor.recipient_ref,
                template_or_message_ref=request.template_ref,
                variables={
                    **_slot_variables(request.starts_at, request.ends_at, request.timezone),
                    **dict(request.variables),
                    "tutor_ref": request.tutor_ref,
                    "learner_register_ref": request.learner_register_ref,
                },
                message_category="utility",
                service_window_expires_at=request.service_window_expires_at,
                correlation_id=request.correlation_id,
            ),
            IdempotencyKey(send_key),
        )

        return TutorAcceptanceResult(
            tutor_recipient=tutor,
            delivery_ref=delivery_ref,
            idempotency_key=IdempotencyKey(send_key),
        )

    async def finalize_after_tutor_acceptance(
        self,
        request: ScheduleAfterTutorAcceptanceRequest,
        *,
        idempotency_key: IdempotencyKey,
    ) -> ScheduledMeetingResult:
        if not request.tutor_acceptance_confirmed:
            raise ValueError("a tutor acceptance is required before scheduling Google Meet")
        if not request.tutor_acceptance_evidence_ref:
            raise ValueError("tutor acceptance evidence is required")
        _validate_window(request.starts_at, request.ends_at)
        _require_aware(request.service_window_expires_at, "service_window_expires_at")
        tutor = await self.website.resolve_tutor_phone_recipient(
            request.tutor_ref,
            demo_ref=str(request.demo_id),
            purpose="demo_session_link",
        )
        learner = await self.website.resolve_profile_phone_recipient(
            request.learner_register_ref,
            demo_ref=str(request.demo_id),
            purpose="demo_session_link",
        )
        conference_request_id = _operation_key(
            "google-meet",
            str(request.demo_id),
            request.tutor_acceptance_evidence_ref,
            str(idempotency_key),
        )
        calendar_event = await self.calendar.create_demo_event(
            request.demo_id,
            request.starts_at,
            request.ends_at,
            request.calendar_attendee_refs,
            conference_request_id,
            IdempotencyKey(conference_request_id),
        )
        if not calendar_event.meeting_uri:
            return ScheduledMeetingResult(
                calendar_event=calendar_event,
                status="conference_pending",
                tutor_recipient=tutor,
                learner_recipient=learner,
                tutor_delivery_ref=None,
                learner_delivery_ref=None,
                conference_request_id=conference_request_id,
            )

        variables = {
            **_slot_variables(request.starts_at, request.ends_at, request.timezone),
            "meeting_url": calendar_event.meeting_uri,
            "provider_event_id": calendar_event.provider_event_id,
        }
        tutor_delivery = await self.messaging.request_delivery(
            OutboundMessageRequest(
                demo_id=request.demo_id,
                recipient_ref=tutor.recipient_ref,
                template_or_message_ref=request.tutor_template_ref,
                variables=variables,
                message_category="utility",
                service_window_expires_at=request.service_window_expires_at,
                correlation_id=request.correlation_id,
            ),
            IdempotencyKey(
                _operation_key("session-link-tutor", str(request.demo_id), conference_request_id)
            ),
        )
        learner_delivery = await self.messaging.request_delivery(
            OutboundMessageRequest(
                demo_id=request.demo_id,
                recipient_ref=learner.recipient_ref,
                template_or_message_ref=request.learner_template_ref,
                variables=variables,
                message_category="utility",
                service_window_expires_at=request.service_window_expires_at,
                correlation_id=request.correlation_id,
            ),
            IdempotencyKey(
                _operation_key("session-link-learner", str(request.demo_id), conference_request_id)
            ),
        )

        return ScheduledMeetingResult(
            calendar_event=calendar_event,
            status="scheduled",
            tutor_recipient=tutor,
            learner_recipient=learner,
            tutor_delivery_ref=tutor_delivery,
            learner_delivery_ref=learner_delivery,
            conference_request_id=conference_request_id,
        )


def _validate_window(starts_at: datetime, ends_at: datetime) -> None:
    _require_aware(starts_at, "starts_at")
    _require_aware(ends_at, "ends_at")
    if ends_at <= starts_at:
        raise ValueError("schedule window must have positive duration")


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _slot_variables(starts_at: datetime, ends_at: datetime, timezone: str) -> dict[str, str]:
    return {
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "timezone": timezone,
    }


def _operation_key(prefix: str, *parts: str) -> str:
    material = "|".join(parts)
    return f"{prefix}:{sha256(material.encode()).hexdigest()}"
