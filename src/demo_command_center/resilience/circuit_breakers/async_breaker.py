from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


class CircuitOpenError(RuntimeError):
    """Raised while provider calls are blocked by the open circuit."""


@dataclass(slots=True)
class AsyncCircuitBreaker:
    failure_threshold: int
    recovery_seconds: float
    _failures: int = 0
    _opened_at: float | None = None
    _lock: asyncio.Lock = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.failure_threshold < 1 or self.recovery_seconds <= 0:
            raise ValueError("circuit-breaker thresholds must be positive")
        self._lock = asyncio.Lock()

    async def allow(self) -> None:
        async with self._lock:
            if self._opened_at is None:
                return
            if time.monotonic() - self._opened_at < self.recovery_seconds:
                raise CircuitOpenError("provider circuit is open")
            self._opened_at = None
            self._failures = 0

    async def success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._opened_at = None

    async def failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
