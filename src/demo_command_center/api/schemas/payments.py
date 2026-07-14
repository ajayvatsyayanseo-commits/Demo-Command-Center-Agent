from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class PaymentOrderCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    demo_ref: UUID
    website_user_ref: str = Field(min_length=1, max_length=255)
    plan_ref: str = Field(pattern=r"^[1-9][0-9]{0,18}$")
    customer_phone: SecretStr = Field(
        json_schema_extra={"format": "password"},
    )

    @field_validator("customer_phone")
    @classmethod
    def validate_customer_phone(cls, value: SecretStr) -> SecretStr:
        phone = value.get_secret_value()
        if (
            len(phone) < 9
            or len(phone) > 16
            or not phone.startswith("+")
            or not phone[1:].isdigit()
            or phone[1] == "0"
        ):
            raise ValueError("customer_phone must be an E.164 number")
        return value


class PaymentOrderJobResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    status: Literal[
        "quote_pending",
        "provider_pending",
        "ready",
        "expired",
        "failed",
        "payment_review",
        "paid",
    ]
    provider_order_ref: str | None = None
    payment_session_id: str | None = None
