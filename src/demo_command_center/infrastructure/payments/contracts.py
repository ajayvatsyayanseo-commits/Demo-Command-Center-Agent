from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator


class PlanQuoteRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(pattern=r"^payment\.plan-quote\.requested\.v1$")
    request_id: UUID
    demo_ref: UUID
    website_user_ref: str = Field(min_length=1, max_length=255)
    plan_ref: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    customer_phone: SecretStr
    purpose: str = Field(pattern=r"^demo_conversion$")
    correlation_id: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def validate_phone(self) -> PlanQuoteRequestPayload:
        phone = self.customer_phone.get_secret_value()
        if (
            len(phone) < 9
            or len(phone) > 16
            or not phone.startswith("+")
            or not phone[1:].isdigit()
            or phone[1] == "0"
        ):
            raise ValueError("customer_phone must be an E.164 number")
        return self


class AuthoritativePlanQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    name: str | None
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    duration_days: int | None = Field(ge=0)
    eligible: bool
    updated_at: str | None
    plan_version: str = Field(pattern=r"^[a-f0-9]{64}$")
    user_ref: str = Field(min_length=1, max_length=255)
    expires_at: datetime

    @model_validator(mode="after")
    def validate_expiry(self) -> AuthoritativePlanQuote:
        if self.expires_at.tzinfo is None:
            raise ValueError("quote expiry must be timezone-aware")
        return self


class CashfreeOrderPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(pattern=r"^payment\.cashfree-order\.requested\.v1$")
    request_id: UUID
    payment_order_id: UUID
    order_reference: str = Field(min_length=1, max_length=100)
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    customer_ref: str = Field(min_length=1, max_length=255)
    customer_phone: SecretStr
    purpose: str = Field(pattern=r"^demo_conversion$")
    correlation_id: str = Field(min_length=1, max_length=128)
    expires_at: datetime

    @model_validator(mode="after")
    def validate_phone(self) -> CashfreeOrderPayload:
        phone = self.customer_phone.get_secret_value()
        if (
            len(phone) < 9
            or len(phone) > 16
            or not phone.startswith("+")
            or not phone[1:].isdigit()
            or phone[1] == "0"
        ):
            raise ValueError("customer_phone must be an E.164 number")
        if self.expires_at.tzinfo is None:
            raise ValueError("expires_at must be timezone-aware")
        return self


class CashfreeOrderAcknowledgement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_order_id: str = Field(min_length=1, max_length=255)
    payment_session_id: SecretStr
    status: str = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_session(self) -> CashfreeOrderAcknowledgement:
        if not self.payment_session_id.get_secret_value():
            raise ValueError("payment_session_id must not be empty")
        return self
