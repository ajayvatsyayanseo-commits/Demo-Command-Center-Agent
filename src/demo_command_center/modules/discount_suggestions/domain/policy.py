from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from hashlib import sha256

from demo_command_center.modules.demo_core.domain.identifiers import DemoId, UserId
from demo_command_center.modules.demo_core.domain.money import Money


class ApprovalLevel(StrEnum):
    AUTOMATIC = "automatic"
    OPERATIONS = "operations"
    FINANCE = "finance"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class ApprovalTier:
    maximum_discount_basis_points: int
    level: ApprovalLevel


@dataclass(frozen=True, slots=True)
class DiscountPolicy:
    version: str
    recommendation_minimum_basis_points: int
    recommendation_maximum_basis_points: int
    absolute_maximum_basis_points: int
    approval_tiers: tuple[ApprovalTier, ...]
    offer_ttl: timedelta
    maximum_active_offers: int
    offer_cooldown: timedelta
    allow_coupon_stacking: bool
    offers_are_reusable: bool

    def __post_init__(self) -> None:
        values = (
            self.recommendation_minimum_basis_points,
            self.recommendation_maximum_basis_points,
            self.absolute_maximum_basis_points,
        )
        if not self.version.strip() or any(not 0 <= value <= 10_000 for value in values):
            raise ValueError("discount version or basis-point limits are invalid")
        if not (
            self.recommendation_minimum_basis_points
            <= self.recommendation_maximum_basis_points
            <= self.absolute_maximum_basis_points
        ):
            raise ValueError("discount bands must be ordered")
        if self.offer_ttl <= timedelta(0) or self.offer_cooldown < timedelta(0):
            raise ValueError("offer timing policy is invalid")
        if self.maximum_active_offers <= 0 or not self.approval_tiers:
            raise ValueError("offer limit and approval tiers are required")
        maxima = [tier.maximum_discount_basis_points for tier in self.approval_tiers]
        if maxima != sorted(maxima) or len(maxima) != len(set(maxima)):
            raise ValueError("approval tiers must be unique and ascending")


@dataclass(frozen=True, slots=True)
class DiscountContext:
    demo_id: DemoId
    user_id: UserId
    plan_ref: str
    list_price: Money
    minimum_permitted_price: Money
    requested_discount_basis_points: int
    active_offer_count: int
    latest_offer_created_at: datetime | None
    overlapping_coupon: bool
    eligible: bool


@dataclass(frozen=True, slots=True)
class DiscountDecision:
    approved: bool
    list_price: Money
    minimum_permitted_price: Money
    maximum_permitted_discount_basis_points: int
    recommended_band_basis_points: tuple[int, int]
    selected_price: Money | None
    selected_discount_basis_points: int | None
    expires_at: datetime | None
    reusable: bool
    approval_level: ApprovalLevel
    reason_codes: tuple[str, ...]
    policy_version: str


@dataclass(frozen=True, slots=True)
class OfferBinding:
    offer_id: str
    demo_id: DemoId
    user_id: UserId
    plan_ref: str
    selected_price: Money
    expires_at: datetime
    reusable: bool
    redemption_count: int
    policy_version: str


def _price_floor_maximum_discount(list_price: Money, minimum_price: Money) -> int:
    list_price.require_same_currency(minimum_price)
    if minimum_price.amount_minor > list_price.amount_minor:
        raise ValueError("minimum price cannot exceed list price")
    if list_price.amount_minor == 0:
        return 0
    discount_minor = list_price.amount_minor - minimum_price.amount_minor
    return (discount_minor * 10_000) // list_price.amount_minor


def decide_discount(
    context: DiscountContext, policy: DiscountPolicy, *, now: datetime
) -> DiscountDecision:
    if now.tzinfo is None:
        raise ValueError("discount decision time must be timezone-aware")
    floor_max = _price_floor_maximum_discount(context.list_price, context.minimum_permitted_price)
    maximum = min(floor_max, policy.absolute_maximum_basis_points)
    reasons: list[str] = []
    if not context.eligible:
        reasons.append("learner_not_eligible")
    if context.active_offer_count >= policy.maximum_active_offers:
        reasons.append("active_offer_limit_reached")
    if (
        context.latest_offer_created_at is not None
        and now < context.latest_offer_created_at + policy.offer_cooldown
    ):
        reasons.append("offer_cooldown_active")
    if context.overlapping_coupon and not policy.allow_coupon_stacking:
        reasons.append("overlapping_discount")
    if not 0 <= context.requested_discount_basis_points <= maximum:
        reasons.append("requested_discount_outside_policy")
    approval = ApprovalLevel.REJECTED
    for tier in policy.approval_tiers:
        if context.requested_discount_basis_points <= tier.maximum_discount_basis_points:
            approval = tier.level
            break
    if approval is ApprovalLevel.REJECTED:
        reasons.append("step_up_approval_unavailable")
    if reasons:
        return DiscountDecision(
            False,
            context.list_price,
            context.minimum_permitted_price,
            maximum,
            (
                min(policy.recommendation_minimum_basis_points, maximum),
                min(policy.recommendation_maximum_basis_points, maximum),
            ),
            None,
            None,
            None,
            policy.offers_are_reusable,
            ApprovalLevel.REJECTED,
            tuple(reasons),
            policy.version,
        )
    selected = context.list_price.discounted_by_basis_points(
        context.requested_discount_basis_points
    )
    if selected.amount_minor < context.minimum_permitted_price.amount_minor:
        raise RuntimeError("discount calculation crossed the configured price floor")
    return DiscountDecision(
        True,
        context.list_price,
        context.minimum_permitted_price,
        maximum,
        (
            min(policy.recommendation_minimum_basis_points, maximum),
            min(policy.recommendation_maximum_basis_points, maximum),
        ),
        selected,
        context.requested_discount_basis_points,
        now + policy.offer_ttl,
        policy.offers_are_reusable,
        approval,
        ("policy_approved",),
        policy.version,
    )


def bind_offer(context: DiscountContext, decision: DiscountDecision) -> OfferBinding:
    if not decision.approved or decision.selected_price is None or decision.expires_at is None:
        raise ValueError("only an approved discount decision can become an offer")
    material = "|".join(
        (
            str(context.demo_id),
            str(context.user_id),
            context.plan_ref,
            str(decision.selected_price.amount_minor),
            decision.selected_price.currency,
            decision.expires_at.isoformat(),
            decision.policy_version,
        )
    )
    return OfferBinding(
        sha256(material.encode()).hexdigest(),
        context.demo_id,
        context.user_id,
        context.plan_ref,
        decision.selected_price,
        decision.expires_at,
        decision.reusable,
        0,
        decision.policy_version,
    )


def validate_offer_redemption(
    offer: OfferBinding,
    *,
    demo_id: DemoId,
    user_id: UserId,
    plan_ref: str,
    currency: str,
    now: datetime,
) -> tuple[bool, str]:
    if now >= offer.expires_at:
        return False, "offer_expired"
    if (
        offer.demo_id != demo_id
        or offer.user_id != user_id
        or offer.plan_ref != plan_ref
        or offer.selected_price.currency != currency.upper()
    ):
        return False, "offer_binding_mismatch"
    if offer.redemption_count > 0 and not offer.reusable:
        return False, "offer_already_redeemed"
    return True, "offer_valid"
