from __future__ import annotations

import argparse
import asyncio
import signal

from pydantic import ValidationError
from structlog import get_logger

from demo_command_center.bootstrap.dependency_container import DependencyContainer
from demo_command_center.config.settings import get_settings
from demo_command_center.glue.envelopes.agent_event import AgentEventEnvelope
from demo_command_center.infrastructure.queues import SqsQueueGateway
from demo_command_center.observability.logging.redaction import configure_logging

logger = get_logger(__name__)


async def run_worker(*, once: bool) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    if settings.provider_profile != "real":
        raise RuntimeError("workers require the real durable provider profile")
    queue_url = settings.sqs_inbound_queue_url
    if not settings.aws_region or not queue_url:
        raise RuntimeError("AWS_REGION and SQS_INBOUND_QUEUE_URL are required")
    container = DependencyContainer.build(settings)
    queue = SqsQueueGateway(region=settings.aws_region)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signal_name, stop.set)
        except NotImplementedError:  # Windows event loops do not expose signal handlers
            logger.debug("signal_handler_unavailable", signal=signal_name.name)
    processed = 0
    try:
        while not stop.is_set():
            if container.inbox_processor is None:
                raise RuntimeError("durable inbox processor is not configured")
            inbox_result = await container.inbox_processor.process_batch(batch_size=10)
            processed += inbox_result.processed
            if container.outbox_publisher is None:
                raise RuntimeError("durable outbox publisher is not configured")
            outbox_result = await container.outbox_publisher.publish_batch(batch_size=10)
            processed += outbox_result.published
            messages = await queue.receive(queue_url, wait_seconds=1 if once else 20)
            for message in messages:
                try:
                    event = AgentEventEnvelope.model_validate(message.payload)
                    receipt = await container.event_ingress.accept(event)
                    await queue.delete(queue_url, message.receipt_handle)
                    processed += 1
                    await logger.ainfo(
                        "inbound_event_persisted",
                        event_id=str(receipt.event_id),
                        status=receipt.status,
                        receive_count=message.receive_count,
                    )
                except ValidationError:
                    await logger.awarning(
                        "poison_event_rejected",
                        message_id=message.message_id,
                        receive_count=message.receive_count,
                    )
                except Exception:
                    await logger.aexception(
                        "inbound_event_processing_failed",
                        message_id=message.message_id,
                        receive_count=message.receive_count,
                    )
            if once:
                break
    finally:
        await container.close()
    return processed


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the durable Demo Command Center worker")
    parser.add_argument("--once", action="store_true", help="Process at most one received batch")
    arguments = parser.parse_args()
    asyncio.run(run_worker(once=arguments.once))


if __name__ == "__main__":
    main()
