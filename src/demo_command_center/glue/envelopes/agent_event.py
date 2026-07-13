from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActorType(StrEnum):
    USER = "user"
    TUTOR = "tutor"
    ADMIN = "admin"
    SYSTEM = "system"
    PROVIDER = "provider"


class PiiClassification(StrEnum):
    NONE = "none"
    LOW = "low"
    RESTRICTED = "restricted"


class EventActor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: ActorType
    id: str = Field(min_length=1, max_length=255)


class EventSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lead_id: str | None = Field(default=None, max_length=255)
    user_id: str | None = Field(default=None, max_length=255)
    tutor_id: str | None = Field(default=None, max_length=255)
    demo_id: str | None = Field(default=None, max_length=255)


class AgentEventEnvelope(BaseModel):
    """Canonical metadata envelope; restricted data belongs only in typed payloads."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_.-]+\.v[1-9][0-9]*$")
    schema_version: Literal["1.0"] = "1.0"
    occurred_at: datetime
    source_agent: str = Field(min_length=1, max_length=100)
    target_agent: str = Field(min_length=1, max_length=100)
    tenant_id: str = Field(min_length=1, max_length=100)
    region_id: str | None = Field(default=None, max_length=100)
    correlation_id: str = Field(min_length=1, max_length=128)
    causation_id: str | None = Field(default=None, max_length=128)
    conversation_id: str = Field(min_length=1, max_length=255)
    actor: EventActor
    subject: EventSubject
    idempotency_key: str = Field(min_length=8, max_length=255)
    traceparent: str | None = Field(default=None, max_length=256)
    pii_classification: PiiClassification
    payload: dict[str, Any]

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_be_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def restricted_payload_is_explicit(self) -> Self:
        if self.pii_classification is PiiClassification.NONE and any(
            key in self.payload for key in {"phone", "email", "message_text", "meeting_link"}
        ):
            raise ValueError("payload contains PII but pii_classification is none")
        return self
