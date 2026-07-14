from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr

from demo_command_center.api.errors.taxonomy import ServiceError
from demo_command_center.bootstrap.dependency_container import (
    DependencyContainer,
    LocalEventIngress,
    UnconfiguredEventIngress,
)
from demo_command_center.config.settings import Settings
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.inbox import DefaultInboxEventHandler
from demo_command_center.infrastructure.outbox.lifecycle import LifecycleOutboxDeliveryRecorder
from demo_command_center.infrastructure.payments.outbox_recorder import (
    CompositeOutboxDeliveryRecorder,
)


def _event() -> AgentEventEnvelope:
    return AgentEventEnvelope.model_validate(
        {
            "event_id": str(uuid4()),
            "event_type": "test.runtime.event.v1",
            "occurred_at": datetime.now(UTC),
            "source_agent": "test",
            "target_agent": "demo-command-center-agent",
            "tenant_id": "tenant",
            "correlation_id": "correlation",
            "conversation_id": "conversation",
            "actor": {"type": "system", "id": "test"},
            "subject": {},
            "idempotency_key": "test-runtime-event",
            "pii_classification": "none",
            "payload": {},
        }
    )


@pytest.mark.asyncio
async def test_local_ingress_duplicate_and_status_behavior() -> None:
    ingress = LocalEventIngress()
    event = _event()
    assert (await ingress.accept(event)).status == "accepted"
    assert (await ingress.accept(event)).status == "duplicate"
    assert await ingress.status(event.event_id) is not None
    assert await ingress.status(uuid4()) is None


@pytest.mark.asyncio
async def test_unconfigured_ingress_fails_closed() -> None:
    ingress = UnconfiguredEventIngress()
    with pytest.raises(ServiceError):
        await ingress.accept(_event())
    with pytest.raises(ServiceError):
        await ingress.status(uuid4())


@pytest.mark.asyncio
async def test_local_container_health_and_close() -> None:
    container = DependencyContainer.build(Settings(app_env="test", _env_file=None))
    assert await container.dependency_health() == {
        "postgresql": True,
        "redis": True,
        "durable_ingress": True,
        "durable_outbox": True,
    }
    assert not container.internal_auth.configured
    await container.close()


def _real_profile_settings(*, post_conversion: bool, outbound_paused: bool) -> Settings:
    return Settings(
        app_env="test",
        provider_profile="real",
        database_url=SecretStr("postgresql+asyncpg://dcc:test@127.0.0.1/dcc"),
        redis_url=SecretStr("redis://127.0.0.1:6379/0"),
        field_encryption_key=SecretStr("hex:" + "11" * 32),
        field_encryption_key_reference="test-key-reference",
        demo_post_conversion_enabled=post_conversion,
        demo_outbound_paused=outbound_paused,
        internal_signing_key_id="dcc-v1",
        internal_hmac_key_grants={
            "onboarding-v1": {
                "secret": SecretStr("test-onboarding-secret"),
                "source": "onboarding-agent",
                "scopes": ["events:write"],
            }
        },
        lead_intake_base_url="https://lead.invalid",
        lead_intake_auth_mode="canonical-hmac",
        lead_intake_shared_secret=SecretStr("test-lead-secret"),
        lead_intake_timeout_seconds=2,
        onboarding_agent_base_url="https://onboarding.invalid",
        onboarding_agent_auth_mode="canonical-hmac",
        onboarding_agent_shared_secret=SecretStr("test-onboarding-secret"),
        onboarding_agent_timeout_seconds=2,
        onboarding_handoff_policy_reference="onboarding-policy-v1",
        default_locale="en-IN",
        message_policy_reference="message-policy-v1",
        welcome_template_reference="paid.welcome.v1",
        welcome_message_version="welcome-v1",
        _env_file=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("post_conversion", "outbound_paused"),
    [(False, True), (True, False)],
)
async def test_real_container_wires_non_consuming_capability_pauses(
    post_conversion: bool, outbound_paused: bool
) -> None:
    container = DependencyContainer.build(
        _real_profile_settings(
            post_conversion=post_conversion,
            outbound_paused=outbound_paused,
        )
    )
    assert container.inbox_processor is not None
    assert container.outbox_publisher is not None
    onboarding_events = frozenset({"onboarding.handoff.accepted.v1", "onboarding.completed.v1"})
    lead_targets = frozenset({"lead-intake", "lead-intake-agent"})
    assert "whatsapp.handoff.demo.v1" in container.inbox_processor.blocked_event_types
    assert "cashfree.payment.webhook.received.v1" in container.inbox_processor.blocked_event_types
    if post_conversion:
        assert container.inbox_processor.blocked_event_types.isdisjoint(onboarding_events)
        assert "onboarding-agent" not in container.outbox_publisher.blocked_targets
        assert isinstance(container.outbox_publisher.recorder, CompositeOutboxDeliveryRecorder)
        assert any(
            isinstance(recorder, LifecycleOutboxDeliveryRecorder)
            for recorder in container.outbox_publisher.recorder.recorders
        )
    else:
        assert onboarding_events.issubset(container.inbox_processor.blocked_event_types)
        assert "onboarding-agent" in container.outbox_publisher.blocked_targets
        assert container.outbox_publisher.recorder is None
    if outbound_paused:
        assert lead_targets.issubset(container.outbox_publisher.blocked_targets)
    else:
        assert container.outbox_publisher.blocked_targets.isdisjoint(lead_targets)
    await container.close()


@pytest.mark.asyncio
async def test_disabled_command_center_blocks_every_registered_inbox_handler() -> None:
    settings = _real_profile_settings(post_conversion=False, outbound_paused=True).model_copy(
        update={"demo_command_center_enabled": False}
    )
    container = DependencyContainer.build(settings)
    assert container.inbox_processor is not None
    assert (
        container.inbox_processor.blocked_event_types
        == DefaultInboxEventHandler.SUPPORTED_EVENT_TYPES
    )
    await container.close()
