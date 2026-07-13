from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class PolicyDocument:
    reference: str
    version: str
    values: dict[str, Any]


class PolicyLoader(Protocol):
    async def load(self, reference: str) -> PolicyDocument: ...
