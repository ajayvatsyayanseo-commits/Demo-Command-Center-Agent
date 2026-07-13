from datetime import timedelta
from enum import StrEnum
from typing import Protocol


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerPort(Protocol):
    async def permit(self, provider: str, operation: str) -> bool: ...

    async def record_success(self, provider: str, operation: str) -> None: ...

    async def record_failure(
        self, provider: str, operation: str, retry_after: timedelta | None = None
    ) -> None: ...

    async def state(self, provider: str, operation: str) -> CircuitState: ...
