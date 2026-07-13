from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class IngressReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    status: Literal["accepted", "duplicate"]
    correlation_id: str


class IngressStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    status: Literal["pending", "processed", "failed"]
    received_at: datetime
    processed_at: datetime | None
    processing_attempts: int
    error_code: str | None
