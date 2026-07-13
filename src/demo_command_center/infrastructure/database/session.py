from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from demo_command_center.config.settings import Settings


@dataclass(frozen=True, slots=True)
class DatabaseResources:
    engine: AsyncEngine
    sessions: async_sessionmaker[AsyncSession]

    async def ping(self) -> bool:
        try:
            async with self.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:  # dependency health intentionally maps all failures to unavailable
            return False

    async def close(self) -> None:
        await self.engine.dispose()


def build_database_resources(settings: Settings) -> DatabaseResources:
    database_url = settings.database_url.get_secret_value()
    if not database_url:
        raise ValueError("DATABASE_URL is required for durable persistence")
    pool_size = settings.db_pool_min or 5
    pool_max = settings.db_pool_max or max(pool_size, 10)
    if pool_size <= 0 or pool_max < pool_size:
        raise ValueError("database pool bounds are invalid")
    engine_options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_size": pool_size,
        "max_overflow": pool_max - pool_size,
        "pool_recycle": 1_800,
    }
    if settings.db_connect_timeout is not None:
        engine_options["connect_args"] = {"timeout": settings.db_connect_timeout}
    if settings.db_statement_timeout is not None and "postgresql" in database_url:
        connect_args = engine_options.setdefault("connect_args", {})
        connect_args["server_settings"] = {
            "statement_timeout": str(settings.db_statement_timeout * 1_000)
        }
    engine = create_async_engine(database_url, **engine_options)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return DatabaseResources(engine=engine, sessions=sessions)
