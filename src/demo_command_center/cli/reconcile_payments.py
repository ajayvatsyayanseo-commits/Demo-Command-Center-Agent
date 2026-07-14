from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from demo_command_center.config.settings import Settings, get_settings
from demo_command_center.infrastructure.audit import append_audit_event
from demo_command_center.infrastructure.database.models import (
    PaymentOrder,
    PaymentReconciliation,
)
from demo_command_center.infrastructure.database.session import build_database_resources
from demo_command_center.integrations.cashfree import CashfreePaymentGateway
from demo_command_center.modules.demo_core.ports.gateways import ProviderPaymentStatus


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    inspected: int
    pending: int
    expired: int
    review: int
    failed_requests: int


def _snapshot_hash(status: ProviderPaymentStatus) -> str:
    raw = json.dumps(
        {
            "provider_order_id": status.provider_order_id,
            "status": status.status.upper(),
            "amount_minor": status.amount_minor,
            "currency": status.currency.upper(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(raw).hexdigest()


async def _reserve_order(
    sessions: async_sessionmaker[AsyncSession],
    *,
    tenant_id: str,
    now: datetime,
    stale_after: timedelta,
) -> tuple[UUID, str] | None:
    async with sessions() as session, session.begin():
        order = await session.scalar(
            select(PaymentOrder)
            .where(
                PaymentOrder.tenant_id == tenant_id,
                PaymentOrder.provider == "cashfree",
                PaymentOrder.provider_order_id.is_not(None),
                or_(
                    PaymentOrder.status.in_(
                        {"pending", "reconciliation_required", "payment_review"}
                    ),
                    (
                        (PaymentOrder.status == "reconciling")
                        & (PaymentOrder.updated_at <= now - stale_after)
                    ),
                ),
                or_(
                    PaymentOrder.reconcile_after.is_(None),
                    PaymentOrder.reconcile_after <= now,
                ),
            )
            .order_by(PaymentOrder.reconcile_after, PaymentOrder.created_at)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if order is None:
            return None
        previous_status = order.status
        order.status = "reconciling"
        return order.id, previous_status


async def _record_provider_failure(
    sessions: async_sessionmaker[AsyncSession],
    *,
    order_id: UUID,
    next_attempt: datetime,
) -> None:
    async with sessions() as session, session.begin():
        order = await session.get(PaymentOrder, order_id, with_for_update=True)
        if order is not None:
            order.status = "reconciliation_required"
            order.reconcile_after = next_attempt


async def _apply_snapshot(
    sessions: async_sessionmaker[AsyncSession],
    *,
    order_id: UUID,
    previous_status: str,
    provider_status: ProviderPaymentStatus,
    now: datetime,
    next_attempt: datetime,
) -> str:
    snapshot_hash = _snapshot_hash(provider_status)
    async with sessions() as session, session.begin():
        order = await session.get(PaymentOrder, order_id, with_for_update=True)
        if order is None or order.provider_order_id is None:
            raise LookupError("payment order disappeared during reconciliation")
        mismatches: list[str] = []
        if provider_status.provider_order_id != order.provider_order_id:
            mismatches.append("provider_order_mismatch")
        if provider_status.amount_minor != order.amount_minor:
            mismatches.append("amount_mismatch")
        if provider_status.currency.upper() != order.currency.upper():
            mismatches.append("currency_mismatch")
        status = provider_status.status.upper()
        if mismatches:
            result = "review"
            order.status = "payment_review"
        elif status == "PAID":
            # Order-level status lacks a provider payment ID and cannot satisfy ADR-005.
            mismatches.append("payment_evidence_required")
            result = "review"
            order.status = "payment_review"
        elif status == "EXPIRED":
            result = "expired"
            order.status = "expired"
        elif status == "ACTIVE":
            result = "pending"
            order.status = "pending"
            order.reconcile_after = next_attempt
        else:
            result = "review"
            mismatches.append("unknown_provider_status")
            order.status = "reconciliation_required"
            order.reconcile_after = next_attempt
        existing = await session.scalar(
            select(PaymentReconciliation.id).where(
                PaymentReconciliation.payment_order_id == order.id,
                PaymentReconciliation.provider_snapshot_hash == snapshot_hash,
            )
        )
        if existing is None:
            session.add(
                PaymentReconciliation(
                    payment_order_id=order.id,
                    provider_snapshot_hash=snapshot_hash,
                    local_status_before=previous_status,
                    verified_provider_status=status,
                    result=result,
                    mismatch_codes=mismatches,
                    reconciled_at=now,
                )
            )
        return result


async def reconcile_payment_batch(
    sessions: async_sessionmaker[AsyncSession],
    gateway: CashfreePaymentGateway,
    *,
    tenant_id: str,
    batch_size: int,
    retry_delay: timedelta,
    policy_reference: str,
    audit_hash_key: str,
    now: datetime | None = None,
) -> ReconciliationResult:
    if not 1 <= batch_size <= 1_000 or retry_delay <= timedelta(0):
        raise ValueError("reconciliation batch and retry delay are invalid")
    effective_now = now or datetime.now(UTC)
    if effective_now.tzinfo is None:
        raise ValueError("reconciliation timestamp must be timezone-aware")
    counts = {"inspected": 0, "pending": 0, "expired": 0, "review": 0, "failed": 0}
    for _ in range(batch_size):
        reservation = await _reserve_order(
            sessions,
            tenant_id=tenant_id,
            now=effective_now,
            stale_after=retry_delay,
        )
        if reservation is None:
            break
        order_id, previous_status = reservation
        counts["inspected"] += 1
        async with sessions() as read_session:
            domain_order_id = await read_session.scalar(
                select(PaymentOrder.domain_order_id).where(PaymentOrder.id == order_id)
            )
        if domain_order_id is None:
            counts["failed"] += 1
            continue
        try:
            provider_status = await gateway.fetch_verified_status(domain_order_id)
        except Exception:
            await _record_provider_failure(
                sessions,
                order_id=order_id,
                next_attempt=effective_now + retry_delay,
            )
            counts["failed"] += 1
            continue
        result = await _apply_snapshot(
            sessions,
            order_id=order_id,
            previous_status=previous_status,
            provider_status=provider_status,
            now=effective_now,
            next_attempt=effective_now + retry_delay,
        )
        counts[result] += 1
    summary = ReconciliationResult(
        inspected=counts["inspected"],
        pending=counts["pending"],
        expired=counts["expired"],
        review=counts["review"],
        failed_requests=counts["failed"],
    )
    async with sessions() as session, session.begin():
        await append_audit_event(
            session,
            tenant_id=tenant_id,
            event_type="payments.reconciliation.batch.completed.v1",
            actor_type="scheduled_task",
            actor_ref="payment-reconciliation",
            correlation_id=str(uuid4()),
            details={**asdict(summary), "policy_reference": policy_reference},
            hash_key=audit_hash_key,
            occurred_at=effective_now,
        )
    return summary


async def _run(settings: Settings, batch_size: int) -> ReconciliationResult:
    tenant_id = settings.tenant_id
    retry_seconds = settings.payment_reconcile_delay_seconds
    timeout = settings.cashfree_timeout_seconds
    policy_reference = settings.payment_reconciliation_policy_reference
    audit_hash_key = settings.audit_hash_key.get_secret_value()
    if (
        settings.provider_profile != "real"
        or not settings.payment_reconciliation_enabled
        or not tenant_id
        or retry_seconds is None
        or timeout is None
        or not audit_hash_key
        or settings.cashfree_env is None
        or settings.cashfree_api_version is None
        or policy_reference is None
    ):
        raise RuntimeError("payment reconciliation is disabled or incompletely configured")
    app_id = settings.cashfree_app_id.get_secret_value()
    secret = settings.cashfree_secret_key.get_secret_value()
    gateway = CashfreePaymentGateway(
        environment=settings.cashfree_env,
        app_id=app_id,
        secret_key=secret,
        api_version=settings.cashfree_api_version,
        timeout_seconds=timeout,
    )
    database = build_database_resources(settings)
    try:
        return await reconcile_payment_batch(
            database.sessions,
            gateway,
            tenant_id=tenant_id,
            batch_size=batch_size,
            retry_delay=timedelta(seconds=retry_seconds),
            policy_reference=policy_reference,
            audit_hash_key=audit_hash_key,
        )
    finally:
        await gateway.close()
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile bound Cashfree demo orders")
    parser.add_argument("--batch-size", type=int, default=100)
    result = asyncio.run(_run(get_settings(), parser.parse_args().batch_size))
    print(json.dumps(asdict(result), sort_keys=True))


if __name__ == "__main__":
    main()
