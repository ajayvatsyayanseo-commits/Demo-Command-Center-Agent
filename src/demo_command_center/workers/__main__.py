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

# SQS long-poll durations for the drain loop. Short values keep WhatsApp reply
# latency low; the idle poll stays well under the SQS max of 20s so the durable
# inbox (filled by HTTP handoffs) is revisited within a few seconds.
# ponytail: fixed cadence; make env-configurable if SQS request volume matters.
WORKER_BUSY_POLL_SECONDS = 0
WORKER_IDLE_POLL_SECONDS = 3


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
    fast_next = False
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
            # WhatsApp handoffs and their replies are delivered through the durable
            # inbox/outbox, which HTTP ingress fills out of band from SQS. A long SQS
            # long-poll therefore stalls replies by up to its duration, so drain with
            # a short poll while there is work and fall back to a brief idle poll (not
            # the SQS max of 20s) so the inbox is revisited within a few seconds.
            did_work = bool(
                inbox_result.processed
                or inbox_result.failed
                or outbox_result.published
                or outbox_result.failed
            )
            if once:
                wait_seconds = 1
            elif did_work or fast_next:
                wait_seconds = WORKER_BUSY_POLL_SECONDS
            else:
                wait_seconds = WORKER_IDLE_POLL_SECONDS
            messages = await queue.receive(queue_url, wait_seconds=wait_seconds)
            fast_next = bool(messages)
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
