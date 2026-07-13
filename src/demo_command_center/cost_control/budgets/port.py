from decimal import Decimal
from typing import Protocol


class CostBudgetPort(Protocol):
    async def reserve(
        self, tenant_id: str, provider: str, estimated_cost: Decimal, operation_id: str
    ) -> bool: ...

    async def settle(self, operation_id: str, actual_cost: Decimal) -> None: ...

    async def release(self, operation_id: str) -> None: ...
