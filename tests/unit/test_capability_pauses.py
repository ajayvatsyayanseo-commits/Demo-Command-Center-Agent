from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.infrastructure.inbox.processor import DurableInboxProcessor
from demo_command_center.infrastructure.outbox.publisher import DurableOutboxPublisher
from demo_command_center.security.encryption import PayloadCipher


class _EmptyScalars:
    def all(self) -> list[object]:
        return []


class _CaptureSession:
    def __init__(self) -> None:
        self.statement: object | None = None

    async def __aenter__(self) -> _CaptureSession:
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    async def scalar(self, statement: object) -> None:
        self.statement = statement

    async def scalars(self, statement: object) -> _EmptyScalars:
        self.statement = statement
        return _EmptyScalars()

    async def commit(self) -> None:
        return None


class _SessionFactory:
    def __init__(self, session: _CaptureSession) -> None:
        self.session = session

    def __call__(self) -> _CaptureSession:
        return self.session


class _UnusedHandler:
    async def handle(self, event: object, session: AsyncSession) -> None:
        del event, session
        raise AssertionError("blocked-event selection returned an unexpected row")


class _UnusedTransport:
    async def publish(
        self,
        *,
        target: str,
        payload: Mapping[str, Any],
        idempotency_key: str,
        correlation_id: str,
    ) -> str:
        del target, payload, idempotency_key, correlation_id
        raise AssertionError("blocked-target selection returned an unexpected row")


def _sessions(session: _CaptureSession) -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], _SessionFactory(session))


def _cipher() -> PayloadCipher:
    return PayloadCipher.from_encoded_key("hex:" + "11" * 32)


@pytest.mark.asyncio
async def test_outbox_pause_excludes_targets_before_claiming_rows() -> None:
    session = _CaptureSession()
    publisher = DurableOutboxPublisher(
        sessions=_sessions(session),
        cipher=_cipher(),
        transport=_UnusedTransport(),
        blocked_targets=frozenset({"lead-intake", "lead-intake-agent"}),
    )

    result = await publisher.publish_batch()

    assert result.published == 0 and result.failed == 0
    assert session.statement is not None
    assert "agent_outbox_events.target_agent NOT IN" in str(session.statement)


@pytest.mark.asyncio
async def test_inbox_pause_excludes_event_types_before_claiming_rows() -> None:
    session = _CaptureSession()
    processor = DurableInboxProcessor(
        sessions=_sessions(session),
        cipher=_cipher(),
        handler=cast(Any, _UnusedHandler()),
        blocked_event_types=frozenset(
            {"onboarding.handoff.accepted.v1", "onboarding.completed.v1"}
        ),
    )

    result = await processor.process_batch()

    assert result.processed == 0 and result.failed == 0
    assert session.statement is not None
    assert "agent_inbox_events.event_type NOT IN" in str(session.statement)
