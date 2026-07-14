from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.infrastructure.database.models import DemoCase
from demo_command_center.modules.demo_core.domain.identifiers import DemoId
from demo_command_center.modules.demo_core.ports.gateways import DemoRecord


class ConcurrentModificationError(RuntimeError):
    """Raised when optimistic concurrency prevents a demo update."""


@runtime_checkable
class PersistableDemoRecord(DemoRecord, Protocol):
    tenant_id: str
    region_id: str | None
    conversation_id: str
    participant_timezone: str
    flow_version: str


@dataclass(slots=True)
class StoredDemoRecord:
    id: DemoId
    state: str
    version: int
    tenant_id: str
    region_id: str | None
    conversation_id: str
    participant_timezone: str
    flow_version: str


class SqlAlchemyDemoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, demo_id: DemoId, *, for_update: bool = False) -> StoredDemoRecord | None:
        statement = select(DemoCase).where(DemoCase.id == UUID(str(demo_id)))
        if for_update:
            statement = statement.with_for_update()
        row = await self._session.scalar(statement)
        if row is None:
            return None
        return StoredDemoRecord(
            id=DemoId(str(row.id)),
            state=row.state,
            version=row.version,
            tenant_id=row.tenant_id,
            region_id=row.region_id,
            conversation_id=row.conversation_id,
            participant_timezone=row.participant_timezone,
            flow_version=row.flow_version,
        )

    async def add(self, demo: DemoRecord) -> None:
        if not isinstance(demo, PersistableDemoRecord):
            raise ValueError("new demo record is missing required persistence fields")
        self._session.add(
            DemoCase(
                id=UUID(str(demo.id)),
                tenant_id=demo.tenant_id,
                region_id=demo.region_id,
                conversation_id=demo.conversation_id,
                state=demo.state,
                participant_timezone=demo.participant_timezone,
                flow_version=demo.flow_version,
                version=demo.version,
            )
        )

    async def save(self, demo: DemoRecord, *, expected_version: int) -> None:
        statement = (
            update(DemoCase)
            .where(DemoCase.id == UUID(str(demo.id)), DemoCase.version == expected_version)
            .values(state=demo.state, version=expected_version + 1)
        )
        result = await self._session.execute(statement)
        if result.rowcount != 1:
            raise ConcurrentModificationError("demo record was modified concurrently")
        demo.version = expected_version + 1


class SqlAlchemyUnitOfWork:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._session: AsyncSession | None = None
        self.demos: SqlAlchemyDemoRepository

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._session = self._sessions()
        self.demos = SqlAlchemyDemoRepository(self._session)
        return self

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("unit of work is not active")
        await self._session.commit()

    async def rollback(self) -> None:
        if self._session is None:
            return
        await self._session.rollback()

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        del exc, traceback
        if self._session is None:
            return
        if exc_type is not None:
            await self._session.rollback()
        await self._session.close()
        self._session = None
