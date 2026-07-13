from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from demo_command_center.modules.communications.domain.message_policy import Channel, MessageClass
from demo_command_center.modules.demo_core.domain.identifiers import DemoId, UserId
from demo_command_center.modules.demo_core.domain.money import Money
from demo_command_center.modules.discount_suggestions.application.use_cases import (
    DiscountDecisionUseCase,
)
from demo_command_center.modules.discount_suggestions.domain.policy import (
    ApprovalLevel,
    ApprovalTier,
    DiscountContext,
    DiscountPolicy,
    bind_offer,
    validate_offer_redemption,
)
from demo_command_center.modules.paid_transition.application.use_cases import (
    PaymentVerificationUseCase,
)
from demo_command_center.modules.paid_transition.domain.verification import (
    EvidenceSource,
    PaymentDecisionKind,
    PaymentEvidence,
    PaymentOrderBinding,
    PaymentVerificationPolicy,
)
from demo_command_center.modules.post_demo_conversion.application.use_cases import (
    NextBestActionUseCase,
)
from demo_command_center.modules.post_demo_conversion.domain.policy import (
    ConversionContext,
    ConversionPolicy,
    DemoOutcome,
    DraftClaim,
    FollowUpRule,
    OfferApproval,
    validate_draft,
)

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


def _conversion_policy() -> ConversionPolicy:
    return ConversionPolicy(
        "conversion-v2",
        (
            FollowUpRule(
                "completed-approved",
                frozenset({DemoOutcome.COMPLETED}),
                timedelta(hours=1),
                Channel.WHATSAPP,
                MessageClass.MARKETING,
                "followup-approved-v1",
                frozenset({"plan:basic", "benefit:verified"}),
                frozenset({OfferApproval.NONE, OfferApproval.APPROVED}),
                False,
            ),
        ),
        frozenset({MessageClass.TRANSACTIONAL}),
        frozenset(
            {
                "invented_testimonial",
                "false_scarcity",
                "outcome_guarantee",
                "unapproved_discount",
            }
        ),
    )


def _discount_policy() -> DiscountPolicy:
    return DiscountPolicy(
        "discount-v7",
        200,
        1000,
        2500,
        (
            ApprovalTier(1000, ApprovalLevel.AUTOMATIC),
            ApprovalTier(2000, ApprovalLevel.OPERATIONS),
            ApprovalTier(2500, ApprovalLevel.FINANCE),
        ),
        timedelta(hours=24),
        2,
        timedelta(hours=1),
        False,
        False,
    )


def _discount_context(**changes: object) -> DiscountContext:
    values: dict[str, object] = {
        "demo_id": DemoId("demo-1"),
        "user_id": UserId("user-1"),
        "plan_ref": "plan-basic-v3",
        "list_price": Money(10000, "INR"),
        "minimum_permitted_price": Money(8000, "INR"),
        "requested_discount_basis_points": 1000,
        "active_offer_count": 0,
        "latest_offer_created_at": None,
        "overlapping_coupon": False,
        "eligible": True,
    }
    values.update(changes)
    return DiscountContext(**values)  # type: ignore[arg-type]


def _payment_policy() -> PaymentVerificationPolicy:
    return PaymentVerificationPolicy(
        "payment-v4",
        frozenset({"SUCCESS"}),
        frozenset({"FAILED", "USER_DROPPED"}),
        frozenset({"EXPIRED"}),
        frozenset({"REFUNDED", "DISPUTED", "PARTIALLY_PAID"}),
    )


def _order() -> PaymentOrderBinding:
    return PaymentOrderBinding(
        "domain-order-1",
        "cashfree-order-1",
        DemoId("demo-1"),
        UserId("user-1"),
        "customer-opaque-1",
        "plan-basic-v3",
        "offer-1",
        Money(9000, "INR"),
        "demo_conversion",
        "sandbox",
        NOW + timedelta(hours=1),
    )


def _evidence(
    *,
    source: EvidenceSource = EvidenceSource.SIGNED_WEBHOOK,
    status: str = "SUCCESS",
    event_id: str = "event-1",
    amount: Money | None = None,
    order_id: str = "cashfree-order-1",
    signature: bool = True,
    replay: bool = True,
    provider_auth: bool = False,
) -> PaymentEvidence:
    return PaymentEvidence(
        event_id,
        order_id,
        source,
        status,
        amount or Money(9000, "INR"),
        "customer-opaque-1",
        "demo_conversion",
        "sandbox",
        NOW,
        signature,
        replay,
        provider_auth,
    )


def test_next_best_action_requires_verified_outcome_facts_offer_and_opt_in() -> None:
    use_case = NextBestActionUseCase(_conversion_policy())
    context = ConversionContext(
        DemoOutcome.COMPLETED,
        True,
        frozenset({"plan:basic", "benefit:verified"}),
        OfferApproval.APPROVED,
        False,
        True,
        False,
    )
    action = use_case.execute(context, now=NOW)
    assert action.follow_up
    assert action.execute_at == NOW + timedelta(hours=1)
    assert action.template_ref == "followup-approved-v1"

    unverified = use_case.execute(
        ConversionContext(
            DemoOutcome.COMPLETED,
            False,
            context.available_fact_refs,
            OfferApproval.APPROVED,
            False,
            True,
            False,
        ),
        now=NOW,
    )
    assert not unverified.follow_up and unverified.requires_human_review
    opted_out = use_case.execute(
        ConversionContext(
            DemoOutcome.COMPLETED,
            True,
            context.available_fact_refs,
            OfferApproval.APPROVED,
            True,
            True,
            False,
        ),
        now=NOW,
    )
    assert opted_out.reason == "recipient_opted_out"


def test_draft_claims_must_be_approved_grounded_and_nonprohibited() -> None:
    valid = validate_draft(
        (DraftClaim("Approved benefit", "benefit", "benefit:verified"),),
        frozenset({"benefit:verified"}),
        _conversion_policy(),
    )
    assert valid.approved
    invalid = validate_draft(
        (
            DraftClaim("Guaranteed results", "outcome_guarantee", "benefit:verified"),
            DraftClaim("Only one seat", "false_scarcity", None),
        ),
        frozenset({"benefit:verified"}),
        _conversion_policy(),
    )
    assert not invalid.approved
    assert "prohibited_claim:outcome_guarantee" in invalid.violations
    assert "ungrounded_claim:false_scarcity" in invalid.violations


def test_discount_engine_calculates_floor_band_approval_and_stable_binding() -> None:
    use_case = DiscountDecisionUseCase(_discount_policy())
    decision = use_case.execute(_discount_context(), now=NOW)
    assert decision.approved
    assert decision.selected_price == Money(9000, "INR")
    assert decision.maximum_permitted_discount_basis_points == 2000
    assert decision.recommended_band_basis_points == (200, 1000)
    assert decision.approval_level is ApprovalLevel.AUTOMATIC
    offer = bind_offer(_discount_context(), decision)
    repeated = bind_offer(_discount_context(), decision)
    assert offer == repeated
    assert validate_offer_redemption(
        offer,
        demo_id=DemoId("demo-1"),
        user_id=UserId("user-1"),
        plan_ref="plan-basic-v3",
        currency="inr",
        now=NOW,
    ) == (True, "offer_valid")


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"eligible": False}, "learner_not_eligible"),
        ({"active_offer_count": 2}, "active_offer_limit_reached"),
        ({"latest_offer_created_at": NOW}, "offer_cooldown_active"),
        ({"overlapping_coupon": True}, "overlapping_discount"),
        ({"requested_discount_basis_points": 2001}, "requested_discount_outside_policy"),
    ],
)
def test_discount_anti_abuse_denials(changes: dict[str, object], reason: str) -> None:
    decision = DiscountDecisionUseCase(_discount_policy()).execute(
        _discount_context(**changes), now=NOW
    )
    assert not decision.approved
    assert reason in decision.reason_codes
    assert decision.selected_price is None


def test_offer_redemption_rejects_expiry_binding_and_replay() -> None:
    decision = DiscountDecisionUseCase(_discount_policy()).execute(_discount_context(), now=NOW)
    offer = bind_offer(_discount_context(), decision)
    assert (
        validate_offer_redemption(
            offer,
            demo_id=DemoId("demo-1"),
            user_id=UserId("user-1"),
            plan_ref="plan-basic-v3",
            currency="INR",
            now=offer.expires_at,
        )[1]
        == "offer_expired"
    )
    assert (
        validate_offer_redemption(
            offer,
            demo_id=DemoId("forged"),
            user_id=UserId("user-1"),
            plan_ref="plan-basic-v3",
            currency="INR",
            now=NOW,
        )[1]
        == "offer_binding_mismatch"
    )
    replayed = type(offer)(
        offer.offer_id,
        offer.demo_id,
        offer.user_id,
        offer.plan_ref,
        offer.selected_price,
        offer.expires_at,
        False,
        1,
        offer.policy_version,
    )
    assert (
        validate_offer_redemption(
            replayed,
            demo_id=offer.demo_id,
            user_id=offer.user_id,
            plan_ref=offer.plan_ref,
            currency="INR",
            now=NOW,
        )[1]
        == "offer_already_redeemed"
    )


def test_verified_payment_transitions_once_with_stable_operation_keys() -> None:
    use_case = PaymentVerificationUseCase(_payment_policy())
    first = use_case.execute(
        _order(),
        _evidence(),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert first.kind is PaymentDecisionKind.TRANSITION_PAID
    assert first.should_transition_paid
    assert first.activation_key and first.paid_outbox_key
    duplicate_event = use_case.execute(
        _order(),
        _evidence(),
        processed_event_ids=frozenset({"event-1"}),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert duplicate_event.kind is PaymentDecisionKind.DUPLICATE
    duplicate_activation = use_case.execute(
        _order(),
        _evidence(event_id="event-2"),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=True,
        now=NOW,
    )
    assert duplicate_activation.kind is PaymentDecisionKind.DUPLICATE
    assert duplicate_activation.activation_key == first.activation_key


@pytest.mark.parametrize(
    "source",
    [
        EvidenceSource.BROWSER_RETURN,
        EvidenceSource.CLIENT_CALLBACK,
        EvidenceSource.USER_MESSAGE,
    ],
)
def test_non_authoritative_payment_sources_never_mark_paid(source: EvidenceSource) -> None:
    result = PaymentVerificationUseCase(_payment_policy()).execute(
        _order(),
        _evidence(source=source),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert result.kind is PaymentDecisionKind.REJECTED_EVIDENCE
    assert not result.should_transition_paid


def test_payment_signature_replay_and_binding_fail_closed() -> None:
    use_case = PaymentVerificationUseCase(_payment_policy())
    invalid_signature = use_case.execute(
        _order(),
        _evidence(signature=False),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert invalid_signature.kind is PaymentDecisionKind.REJECTED_EVIDENCE
    invalid_replay = use_case.execute(
        _order(),
        _evidence(replay=False),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert invalid_replay.kind is PaymentDecisionKind.REJECTED_EVIDENCE
    mismatch = use_case.execute(
        _order(),
        _evidence(order_id="forged", amount=Money(8999, "USD")),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert mismatch.kind is PaymentDecisionKind.REVIEW
    assert set(mismatch.reason_codes) == {"order_mismatch", "currency_mismatch"}


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        ("FAILED", PaymentDecisionKind.FAILED),
        ("EXPIRED", PaymentDecisionKind.EXPIRED),
        ("REFUNDED", PaymentDecisionKind.REVIEW),
        ("PENDING", PaymentDecisionKind.RECONCILE),
    ],
)
def test_payment_status_decisions(status: str, kind: PaymentDecisionKind) -> None:
    result = PaymentVerificationUseCase(_payment_policy()).execute(
        _order(),
        _evidence(status=status),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert result.kind is kind


def test_authenticated_reconciliation_can_confirm_but_never_bypasses_binding() -> None:
    result = PaymentVerificationUseCase(_payment_policy()).execute(
        _order(),
        _evidence(
            source=EvidenceSource.AUTHENTICATED_RECONCILIATION,
            provider_auth=True,
            signature=False,
            replay=False,
        ),
        processed_event_ids=frozenset(),
        paid_activation_already_applied=False,
        now=NOW,
    )
    assert result.kind is PaymentDecisionKind.TRANSITION_PAID
