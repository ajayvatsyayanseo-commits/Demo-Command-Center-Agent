from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, IdempotencyKey
from demo_command_center.modules.demo_core.ports.gateways import (
    CalendarEventResult,
    OutboundMessageRequest,
    TutorSearchQuery,
    VerifiedSubscriptionActivation,
    WebsitePhoneRecipient,
)
from demo_command_center.modules.scheduling.application.use_cases import (
    ScheduleAfterTutorAcceptanceRequest,
    TutorAcceptanceRequest,
    TutorFirstSchedulingCoordinator,
)


def _recipient(*, register_ref: str, purpose: str, demo_ref: str) -> WebsitePhoneRecipient:
    return WebsitePhoneRecipient(
        register_ref=register_ref,
        tutor_ref=register_ref if register_ref == "2" else None,
        user_ref=f"user-{register_ref}",
        recipient_ref=f"register:{register_ref}:phone",
        phone_reference=f"register:{register_ref}:phone",
        masked_phone=f"*********000{register_ref}",
        channel="whatsapp",
        purpose=purpose,
        demo_ref=demo_ref,
        source_version=f"version-{register_ref}",
    )


@dataclass(slots=True)
class FakeWebsite:
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    async def search_tutor_candidates(self, query: TutorSearchQuery) -> Sequence[Mapping[str, Any]]:
        del query
        return []

    async def resolve_tutor_phone_recipient(
        self, tutor_ref: str, *, demo_ref: str, purpose: str
    ) -> WebsitePhoneRecipient:
        self.calls.append(("tutor", tutor_ref, purpose))
        return _recipient(register_ref=tutor_ref, purpose=purpose, demo_ref=demo_ref)

    async def resolve_profile_phone_recipient(
        self, register_ref: str, *, demo_ref: str, purpose: str
    ) -> WebsitePhoneRecipient:
        self.calls.append(("profile", register_ref, purpose))
        return _recipient(register_ref=register_ref, purpose=purpose, demo_ref=demo_ref)

    async def get_plan_quote(self, plan_ref: str, customer_ref: str) -> Mapping[str, Any]:
        del plan_ref, customer_ref
        return {}

    async def activate_verified_subscription(
        self,
        activation: VerifiedSubscriptionActivation,
        idempotency_key: IdempotencyKey,
    ) -> Mapping[str, Any]:
        del activation, idempotency_key
        return {}


@dataclass(slots=True)
class FakeMessaging:
    sent: list[tuple[OutboundMessageRequest, str]] = field(default_factory=list)

    async def request_delivery(
        self, request: OutboundMessageRequest, idempotency_key: IdempotencyKey
    ) -> str:
        self.sent.append((request, str(idempotency_key)))
        return f"message-{len(self.sent)}"


@dataclass(slots=True)
class FakeCalendar:
    meeting_uri: str | None = "https://meet.google.com/demo-link"
    created: list[dict[str, Any]] = field(default_factory=list)

    async def create_demo_event(
        self,
        demo_id: DemoId,
        starts_at: datetime,
        ends_at: datetime,
        attendee_refs: Sequence[str],
        conference_request_id: str,
        idempotency_key: IdempotencyKey,
    ) -> CalendarEventResult:
        self.created.append(
            {
                "demo_id": str(demo_id),
                "starts_at": starts_at,
                "ends_at": ends_at,
                "attendee_refs": tuple(attendee_refs),
                "conference_request_id": conference_request_id,
                "idempotency_key": str(idempotency_key),
            }
        )
        return CalendarEventResult(
            provider_event_id="google-event-1",
            provider_etag="etag-1",
            conference_status="success",
            meeting_uri=self.meeting_uri,
        )

    async def free_busy(
        self,
        calendar_refs: Sequence[str],
        starts_at: datetime,
        ends_at: datetime,
    ) -> Mapping[str, Sequence[tuple[datetime, datetime]]]:
        del starts_at, ends_at
        return {calendar_ref: () for calendar_ref in calendar_refs}

    async def cancel_event(self, event_ref: str, idempotency_key: IdempotencyKey) -> None:
        del event_ref, idempotency_key


@pytest.mark.asyncio
async def test_teacher_acceptance_message_goes_to_selected_tutor_before_calendar_creation() -> None:
    website = FakeWebsite()
    messaging = FakeMessaging()
    calendar = FakeCalendar()
    coordinator = TutorFirstSchedulingCoordinator(website, messaging, calendar)
    starts_at = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)

    result = await coordinator.request_tutor_acceptance(
        TutorAcceptanceRequest(
            demo_id=DemoId("demo-0001"),
            tutor_ref="2",
            learner_register_ref="1",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            timezone="Asia/Kolkata",
            service_window_expires_at=starts_at + timedelta(hours=12),
            correlation_id="corr-1",
        ),
        idempotency_key=IdempotencyKey("hold-1"),
    )

    assert result.tutor_recipient.recipient_ref == "register:2:phone"
    assert website.calls == [("tutor", "2", "demo_tutor_acceptance")]
    assert calendar.created == []
    assert len(messaging.sent) == 1
    request, send_key = messaging.sent[0]
    assert request.recipient_ref == "register:2:phone"
    assert request.template_or_message_ref == "demo.tutor_acceptance.v1"
    assert request.variables["tutor_ref"] == "2"
    assert send_key.startswith("tutor-acceptance:")


@pytest.mark.asyncio
async def test_google_meet_after_tutor_acceptance_sends_link_to_tutor_and_student() -> None:
    website = FakeWebsite()
    messaging = FakeMessaging()
    calendar = FakeCalendar()
    coordinator = TutorFirstSchedulingCoordinator(website, messaging, calendar)
    starts_at = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)

    result = await coordinator.finalize_after_tutor_acceptance(
        ScheduleAfterTutorAcceptanceRequest(
            demo_id=DemoId("demo-0001"),
            tutor_ref="2",
            learner_register_ref="1",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            timezone="Asia/Kolkata",
            service_window_expires_at=starts_at + timedelta(hours=12),
            correlation_id="corr-1",
            tutor_acceptance_confirmed=True,
            tutor_acceptance_evidence_ref="message-accept-1",
        ),
        idempotency_key=IdempotencyKey("schedule-1"),
    )

    assert result.status == "scheduled"
    assert website.calls == [
        ("tutor", "2", "demo_session_link"),
        ("profile", "1", "demo_session_link"),
    ]
    assert len(calendar.created) == 1
    assert len(messaging.sent) == 2
    assert [item[0].recipient_ref for item in messaging.sent] == [
        "register:2:phone",
        "register:1:phone",
    ]
    assert all(
        item[0].variables["meeting_url"] == "https://meet.google.com/demo-link"
        for item in messaging.sent
    )
    assert messaging.sent[0][1].startswith("session-link-tutor:")
    assert messaging.sent[1][1].startswith("session-link-learner:")


@pytest.mark.asyncio
async def test_pending_conference_does_not_send_empty_meeting_link() -> None:
    website = FakeWebsite()
    messaging = FakeMessaging()
    calendar = FakeCalendar(meeting_uri=None)
    coordinator = TutorFirstSchedulingCoordinator(website, messaging, calendar)
    starts_at = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)

    result = await coordinator.finalize_after_tutor_acceptance(
        ScheduleAfterTutorAcceptanceRequest(
            demo_id=DemoId("demo-0001"),
            tutor_ref="2",
            learner_register_ref="1",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=1),
            timezone="Asia/Kolkata",
            service_window_expires_at=starts_at + timedelta(hours=12),
            correlation_id="corr-1",
            tutor_acceptance_confirmed=True,
            tutor_acceptance_evidence_ref="message-accept-1",
        ),
        idempotency_key=IdempotencyKey("schedule-1"),
    )

    assert result.status == "conference_pending"
    assert len(calendar.created) == 1
    assert messaging.sent == []


@pytest.mark.asyncio
async def test_google_meet_scheduling_requires_tutor_acceptance() -> None:
    coordinator = TutorFirstSchedulingCoordinator(FakeWebsite(), FakeMessaging(), FakeCalendar())
    starts_at = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="tutor acceptance"):
        await coordinator.finalize_after_tutor_acceptance(
            ScheduleAfterTutorAcceptanceRequest(
                demo_id=DemoId("demo-0001"),
                tutor_ref="2",
                learner_register_ref="1",
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=1),
                timezone="Asia/Kolkata",
                service_window_expires_at=starts_at + timedelta(hours=12),
                correlation_id="corr-1",
                tutor_acceptance_confirmed=False,
                tutor_acceptance_evidence_ref="",
            ),
            idempotency_key=IdempotencyKey("schedule-1"),
        )
