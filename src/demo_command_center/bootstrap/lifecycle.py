from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager

from fastapi import FastAPI
from structlog import get_logger

from demo_command_center.bootstrap.dependency_container import DependencyContainer
from demo_command_center.config.settings import Settings

logger = get_logger(__name__)


def application_lifespan(
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        container = DependencyContainer.build(settings)
        app.state.container = container
        await logger.ainfo(
            "application_started",
            app_name=settings.app_name,
            app_version=settings.app_version,
            app_env=settings.app_env,
            provider_profile=settings.provider_profile,
        )
        try:
            yield
        finally:
            await container.close()
            await logger.ainfo("application_stopped", app_name=settings.app_name)

    return lifespan
