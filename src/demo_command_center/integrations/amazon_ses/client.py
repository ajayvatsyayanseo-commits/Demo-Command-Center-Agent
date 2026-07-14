from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Mapping
from typing import Any

import boto3

from demo_command_center.api.errors.taxonomy import ErrorCode, ServiceError
from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey


class SesEmailGateway:
    def __init__(self, *, region: str, from_address: str, client: object | None = None) -> None:
        if not region or not from_address:
            raise ValueError("SES region and verified sender are required")
        self._from_address = from_address
        self._client: Any = client or boto3.client("ses", region_name=region)

    async def send_templated(
        self,
        recipient_ref: str,
        template_ref: str,
        variables: Mapping[str, str],
        idempotency_key: IdempotencyKey,
    ) -> str:
        idempotency_hash = hashlib.sha256(str(idempotency_key).encode()).hexdigest()[:32]
        try:
            response = await asyncio.to_thread(
                self._client.send_templated_email,
                Source=self._from_address,
                Destination={"ToAddresses": [recipient_ref]},
                Template=template_ref,
                TemplateData=json.dumps(dict(variables), sort_keys=True),
                Tags=[{"Name": "DccIdempotency", "Value": idempotency_hash}],
            )
        except Exception as exc:
            raise ServiceError(
                ErrorCode.PROVIDER_UNAVAILABLE,
                "Email delivery is temporarily unavailable",
            ) from exc
        message_id = response.get("MessageId") if isinstance(response, dict) else None
        if not isinstance(message_id, str) or not message_id:
            raise ServiceError(
                ErrorCode.PROVIDER_RESPONSE_INVALID,
                "SES returned an invalid delivery acknowledgement",
            )
        return message_id
