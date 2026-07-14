from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.config.settings import Settings, get_settings
from demo_command_center.infrastructure.audit import append_audit_event
from demo_command_center.infrastructure.database.models import ProviderRequest
from demo_command_center.infrastructure.database.session import build_database_resources
from demo_command_center.infrastructure.queues import SqsQueueGateway

_REASON_CODE = re.compile(r"^[A-Z0-9][A-Z0-9_:-]{2,99}$")


@dataclass(frozen=True, slots=True)
class RedriveResult:
    operation_key: str
    task_handle: str
    status: str


async def redrive_dlq(
    sessions: async_sessionmaker[AsyncSession],
    queue: SqsQueueGateway,
    *,
    tenant_id: str,
    source_dlq_arn: str,
    destination_queue_arn: str,
    maximum_messages_per_second: int,
    operation_key: str,
    reason_code: str,
    operator_ref: str,
    confirmation: str,
    audit_hash_key: str,
) -> RedriveResult:
    if confirmation != source_dlq_arn:
        raise ValueError("confirmation must exactly match the source DLQ ARN")
    if not _REASON_CODE.fullmatch(reason_code):
        raise ValueError("reason code must be a controlled uppercase code")
    if not 8 <= len(operation_key) <= 255 or not operator_ref:
        raise ValueError("a stable operation key and operator reference are required")
    request_material = json.dumps(
        {
            "source": source_dlq_arn,
            "destination": destination_queue_arn,
            "rate": maximum_messages_per_second,
            "reason_code": reason_code,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    request_hash = hashlib.sha256(request_material).hexdigest()
    correlation_id = str(uuid4())
    request_id: UUID
    async with sessions() as session, session.begin():
        existing = await session.scalar(
            select(ProviderRequest).where(
                ProviderRequest.tenant_id == tenant_id,
                ProviderRequest.provider == "aws-sqs",
                ProviderRequest.idempotency_key == operation_key,
            )
        )
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ValueError("operation key is already bound to a different redrive")
            if existing.status == "succeeded" and existing.provider_reference:
                return RedriveResult(operation_key, existing.provider_reference, "duplicate")
            raise RuntimeError("redrive state is uncertain; reconcile the existing AWS task")
        request = ProviderRequest(
            tenant_id=tenant_id,
            provider="aws-sqs",
            operation="start_message_move_task",
            idempotency_key=operation_key,
            correlation_id=correlation_id,
            request_hash=request_hash,
            status="reserved",
            attempt_count=0,
        )
        session.add(request)
        await session.flush()
        request_id = request.id
    try:
        task_handle = await queue.start_redrive(
            source_dlq_arn=source_dlq_arn,
            destination_queue_arn=destination_queue_arn,
            maximum_messages_per_second=maximum_messages_per_second,
        )
    except Exception:
        async with sessions() as session, session.begin():
            failed = await session.get(ProviderRequest, request_id, with_for_update=True)
            if failed is not None:
                failed.status = "failed"
                failed.attempt_count += 1
                failed.safe_error_code = "DCC_SQS_REDRIVE_START_FAILED"
                await append_audit_event(
                    session,
                    tenant_id=tenant_id,
                    event_type="operations.dlq.redrive.failed.v1",
                    actor_type="operator",
                    actor_ref=operator_ref,
                    correlation_id=correlation_id,
                    details={"operation_key": operation_key, "reason_code": reason_code},
                    hash_key=audit_hash_key,
                )
        raise
    async with sessions() as session, session.begin():
        completed = await session.get(ProviderRequest, request_id, with_for_update=True)
        if completed is None:
            raise RuntimeError("durable redrive reservation disappeared")
        completed.status = "succeeded"
        completed.provider_reference = task_handle
        completed.attempt_count += 1
        await append_audit_event(
            session,
            tenant_id=tenant_id,
            event_type="operations.dlq.redrive.started.v1",
            actor_type="operator",
            actor_ref=operator_ref,
            correlation_id=correlation_id,
            details={
                "operation_key": operation_key,
                "reason_code": reason_code,
                "maximum_messages_per_second": maximum_messages_per_second,
            },
            hash_key=audit_hash_key,
        )
    return RedriveResult(operation_key, task_handle, "started")


async def _run(settings: Settings, arguments: argparse.Namespace) -> RedriveResult:
    tenant_id = settings.tenant_id
    region = settings.aws_region
    audit_hash_key = settings.audit_hash_key.get_secret_value()
    if (
        settings.provider_profile != "real"
        or not settings.dlq_redrive_enabled
        or not tenant_id
        or not region
        or not audit_hash_key
    ):
        raise RuntimeError("DLQ redrive is disabled or its durable AWS configuration is missing")
    arn_prefix = f"arn:aws:sqs:{region}:"
    if not arguments.source_dlq_arn.startswith(
        arn_prefix
    ) or not arguments.destination_arn.startswith(arn_prefix):
        raise ValueError("source and destination must be SQS ARNs in the configured region")
    database = build_database_resources(settings)
    try:
        return await redrive_dlq(
            database.sessions,
            SqsQueueGateway(region=region),
            tenant_id=tenant_id,
            source_dlq_arn=arguments.source_dlq_arn,
            destination_queue_arn=arguments.destination_arn,
            maximum_messages_per_second=arguments.max_per_second,
            operation_key=arguments.operation_key,
            reason_code=arguments.reason_code,
            operator_ref=arguments.operator_ref,
            confirmation=arguments.confirm,
            audit_hash_key=audit_hash_key,
        )
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Start one inspected, rate-limited DLQ redrive")
    parser.add_argument("--source-dlq-arn", required=True)
    parser.add_argument("--destination-arn", required=True)
    parser.add_argument("--max-per-second", type=int, required=True)
    parser.add_argument("--operation-key", required=True)
    parser.add_argument("--reason-code", required=True)
    parser.add_argument("--operator-ref", required=True)
    parser.add_argument("--confirm", required=True, help="Exact source DLQ ARN")
    result = asyncio.run(_run(get_settings(), parser.parse_args()))
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
