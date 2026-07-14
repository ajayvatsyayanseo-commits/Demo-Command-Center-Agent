from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import boto3

from demo_command_center.modules.demo_core.domain.identifiers import IdempotencyKey


@dataclass(frozen=True, slots=True)
class QueueMessage:
    message_id: str
    receipt_handle: str
    payload: Mapping[str, Any]
    receive_count: int


class SqsQueueGateway:
    def __init__(self, *, region: str, client: object | None = None) -> None:
        if not region:
            raise ValueError("AWS region is required")
        self._client: Any = client or boto3.client("sqs", region_name=region)

    async def publish(
        self,
        queue_name: str,
        payload: Mapping[str, Any],
        idempotency_key: IdempotencyKey,
    ) -> str:
        body = json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))
        arguments: dict[str, Any] = {
            "QueueUrl": queue_name,
            "MessageBody": body,
            "MessageAttributes": {
                "idempotency_key": {
                    "DataType": "String",
                    "StringValue": str(idempotency_key),
                }
            },
        }
        if queue_name.endswith(".fifo"):
            arguments["MessageGroupId"] = "demo-command-center"
            arguments["MessageDeduplicationId"] = str(idempotency_key)[:128]
        response = await asyncio.to_thread(self._client.send_message, **arguments)
        message_id = response.get("MessageId") if isinstance(response, dict) else None
        if not isinstance(message_id, str):
            raise RuntimeError("SQS did not return a message ID")
        return message_id

    async def receive(
        self,
        queue_url: str,
        *,
        maximum_messages: int = 10,
        wait_seconds: int = 20,
        visibility_timeout: int = 60,
    ) -> Sequence[QueueMessage]:
        if not 1 <= maximum_messages <= 10 or not 0 <= wait_seconds <= 20:
            raise ValueError("SQS receive bounds are invalid")
        response = await asyncio.to_thread(
            self._client.receive_message,
            QueueUrl=queue_url,
            MaxNumberOfMessages=maximum_messages,
            WaitTimeSeconds=wait_seconds,
            VisibilityTimeout=visibility_timeout,
            AttributeNames=["ApproximateReceiveCount"],
        )
        raw_messages = response.get("Messages", []) if isinstance(response, dict) else []
        result: list[QueueMessage] = []
        for raw in raw_messages:
            if not isinstance(raw, dict):
                continue
            try:
                payload = json.loads(str(raw["Body"]))
                attributes = raw.get("Attributes", {})
                receive_count = int(attributes.get("ApproximateReceiveCount", "1"))
                if not isinstance(payload, dict):
                    continue
                result.append(
                    QueueMessage(
                        message_id=str(raw["MessageId"]),
                        receipt_handle=str(raw["ReceiptHandle"]),
                        payload=payload,
                        receive_count=receive_count,
                    )
                )
            except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                continue
        return result

    async def delete(self, queue_url: str, receipt_handle: str) -> None:
        await asyncio.to_thread(
            self._client.delete_message,
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
        )

    async def extend_visibility(
        self, queue_url: str, receipt_handle: str, visibility_timeout: int
    ) -> None:
        await asyncio.to_thread(
            self._client.change_message_visibility,
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=visibility_timeout,
        )

    async def start_redrive(
        self,
        *,
        source_dlq_arn: str,
        destination_queue_arn: str,
        maximum_messages_per_second: int,
    ) -> str:
        if not 1 <= maximum_messages_per_second <= 500:
            raise ValueError("redrive rate must be between 1 and 500 messages per second")
        response = await asyncio.to_thread(
            self._client.start_message_move_task,
            SourceArn=source_dlq_arn,
            DestinationArn=destination_queue_arn,
            MaxNumberOfMessagesPerSecond=maximum_messages_per_second,
        )
        task_handle = response.get("TaskHandle") if isinstance(response, dict) else None
        if not isinstance(task_handle, str) or not task_handle:
            raise RuntimeError("SQS did not return a message-move task handle")
        return task_handle
