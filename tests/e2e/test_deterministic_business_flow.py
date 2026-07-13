from __future__ import annotations

from datetime import UTC, datetime, timedelta

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, UserId
from demo_command_center.modules.demo_core.domain.money import Money
from demo_command_center.modules.discount_suggestions.domain.policy import (
    ApprovalLevel,
    ApprovalTier,
    DiscountContext,
    DiscountPolicy,
    bind_offer,
    decide_discount,
)
from demo_command_center.modules.paid_transition.domain.verification import (
    EvidenceSource,
    PaymentDecisionKind,
    PaymentEvidence,
    PaymentOrderBinding,
    PaymentVerificationPolicy,
    verify_payment,
)


def test_approved_offer_to_verified_payment_and_duplicate_replay() -> None:
    """A pure end-to-end decision path proves commercial invariants without provider fakes."""

    now = datetime(2026, 7, 13, 12, tzinfo=UTC)
    context = DiscountContext(
        DemoId("demo-e2e"),
        UserId("user-e2e"),
        "plan-v1",
        Money(10000, "INR"),
        Money(8500, "INR"),
        1000,
        0,
        None,
        False,
        True,
    )
    discount = decide_discount(
        context,
        DiscountPolicy(
            "discount-v1",
            0,
            1000,
            1500,
            (ApprovalTier(1500, ApprovalLevel.AUTOMATIC),),
            timedelta(hours=1),
            1,
            timedelta(0),
            False,
            False,
        ),
        now=now,
    )
    offer = bind_offer(context, discount)
    order = PaymentOrderBinding(
        "order-e2e",
        "provider-order-e2e",
        context.demo_id,
        context.user_id,
        "customer-e2e",
        context.plan_ref,
        offer.offer_id,
        offer.selected_price,
        "demo_conversion",
        "sandbox",
        offer.expires_at,
    )
    evidence = PaymentEvidence(
        "provider-event-e2e",
        order.provider_order_id,
        EvidenceSource.SIGNED_WEBHOOK,
        "SUCCESS",
        order.amount,
        order.customer_ref,
        order.purpose,
        order.environment,
        now,
        True,
        True,
        False,
    )
    policy = PaymentVerificationPolicy(
        "payment-v1",
        frozenset({"SUCCESS"}),
        frozenset({"FAILED"}),
        frozenset({"EXPIRED"}),
        frozenset({"DISPUTED"}),
    )
    paid = verify_payment(
        order,
        evidence,
        policy,
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=now,
    )
    replay = verify_payment(
        order,
        evidence,
        policy,
        processed_event_ids=frozenset({evidence.provider_event_id}),
        paid_activation_already_applied=True,
        now=now,
    )
    assert paid.kind is PaymentDecisionKind.TRANSITION_PAID
    assert paid.should_transition_paid
    assert replay.kind is PaymentDecisionKind.DUPLICATE
    assert not replay.should_transition_paid
