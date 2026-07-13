from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from demo_command_center.glue.envelopes.agent_event import ActorType
from demo_command_center.state.machine.demo_state import DemoState


class TransitionCommand(StrEnum):
    START_QUALIFICATION = "START_QUALIFICATION"
    COMPLETE_QUALIFICATION = "COMPLETE_QUALIFICATION"
    COMPLETE_MATCHING = "COMPLETE_MATCHING"
    ACCEPT_SHORTLIST = "ACCEPT_SHORTLIST"
    HOLD_SLOT = "HOLD_SLOT"
    REQUEST_CONFIRMATIONS = "REQUEST_CONFIRMATIONS"
    CONFIRM_ALL = "CONFIRM_ALL"
    ACTIVATE_REMINDERS = "ACTIVATE_REMINDERS"
    MARK_READY = "MARK_READY"
    START_DEMO = "START_DEMO"
    COMPLETE_DEMO = "COMPLETE_DEMO"
    QUEUE_ANALYSIS = "QUEUE_ANALYSIS"
    COMPLETE_ANALYSIS = "COMPLETE_ANALYSIS"
    START_CONVERSION = "START_CONVERSION"
    PROPOSE_OFFER = "PROPOSE_OFFER"
    REQUEST_PAYMENT = "REQUEST_PAYMENT"
    VERIFY_PAYMENT = "VERIFY_PAYMENT"
    HANDOFF_ONBOARDING = "HANDOFF_ONBOARDING"
    COMPLETE_ONBOARDING = "COMPLETE_ONBOARDING"
    REQUEST_RESCHEDULE = "REQUEST_RESCHEDULE"
    REOPEN_NEGOTIATION = "REOPEN_NEGOTIATION"
    EXPIRE_SLOT = "EXPIRE_SLOT"
    REPORT_USER_NO_SHOW = "REPORT_USER_NO_SHOW"
    REPORT_TUTOR_NO_SHOW = "REPORT_TUTOR_NO_SHOW"
    REPORT_TECHNICAL_FAILURE = "REPORT_TECHNICAL_FAILURE"
    REPORT_PAYMENT_FAILURE = "REPORT_PAYMENT_FAILURE"
    EXPIRE_PAYMENT = "EXPIRE_PAYMENT"
    REVIEW_PAYMENT = "REVIEW_PAYMENT"
    RETRY_PAYMENT = "RETRY_PAYMENT"
    CANCEL_BY_USER = "CANCEL_BY_USER"
    CANCEL_BY_TUTOR = "CANCEL_BY_TUTOR"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    FAIL = "FAIL"


@dataclass(frozen=True, slots=True)
class TransitionRule:
    before: DemoState
    command: TransitionCommand
    after: DemoState
    allowed_actors: frozenset[ActorType]
    guards: tuple[str, ...] = ()
    side_effects: tuple[str, ...] = ()
    compensation: str | None = None


SYSTEM = frozenset({ActorType.SYSTEM, ActorType.ADMIN})
USER = frozenset({ActorType.USER, ActorType.ADMIN})
TUTOR = frozenset({ActorType.TUTOR, ActorType.ADMIN})
PROVIDER = frozenset({ActorType.PROVIDER, ActorType.SYSTEM})
ANY_BUSINESS_ACTOR = frozenset({ActorType.USER, ActorType.TUTOR, ActorType.ADMIN, ActorType.SYSTEM})


def _r(
    before: DemoState,
    command: TransitionCommand,
    after: DemoState,
    actors: frozenset[ActorType] = SYSTEM,
    guards: tuple[str, ...] = (),
    side_effects: tuple[str, ...] = (),
    compensation: str | None = None,
) -> TransitionRule:
    return TransitionRule(before, command, after, actors, guards, side_effects, compensation)


_TRANSITIONS = (
    _r(
        DemoState.NEW,
        TransitionCommand.START_QUALIFICATION,
        DemoState.QUALIFYING,
        ANY_BUSINESS_ACTOR,
    ),
    _r(
        DemoState.QUALIFYING,
        TransitionCommand.COMPLETE_QUALIFICATION,
        DemoState.TUTOR_MATCHING,
        SYSTEM,
        ("requirements_complete",),
        ("request_tutor_candidates",),
    ),
    _r(
        DemoState.TUTOR_MATCHING,
        TransitionCommand.COMPLETE_MATCHING,
        DemoState.TUTOR_SHORTLISTED,
        SYSTEM,
        ("authoritative_candidates_present",),
    ),
    _r(
        DemoState.TUTOR_SHORTLISTED,
        TransitionCommand.ACCEPT_SHORTLIST,
        DemoState.SLOT_NEGOTIATING,
        USER,
    ),
    _r(
        DemoState.SLOT_NEGOTIATING,
        TransitionCommand.HOLD_SLOT,
        DemoState.SLOT_HELD,
        SYSTEM,
        ("slot_still_available", "hold_policy_loaded"),
        ("create_atomic_hold",),
        "release_slot_hold",
    ),
    _r(
        DemoState.SLOT_HELD,
        TransitionCommand.REQUEST_CONFIRMATIONS,
        DemoState.AWAITING_CONFIRMATIONS,
        SYSTEM,
        ("active_hold_exists",),
        ("request_participant_confirmations",),
    ),
    _r(
        DemoState.SLOT_HELD,
        TransitionCommand.EXPIRE_SLOT,
        DemoState.SLOT_EXPIRED,
        SYSTEM,
        ("hold_expired",),
        ("release_slot_hold",),
    ),
    _r(
        DemoState.AWAITING_CONFIRMATIONS,
        TransitionCommand.CONFIRM_ALL,
        DemoState.SCHEDULED,
        SYSTEM,
        ("all_required_confirmed", "active_hold_exists"),
        ("create_calendar_event",),
        "cancel_calendar_and_release_hold",
    ),
    _r(
        DemoState.SCHEDULED,
        TransitionCommand.ACTIVATE_REMINDERS,
        DemoState.REMINDERS_ACTIVE,
        SYSTEM,
        ("calendar_event_confirmed",),
        ("schedule_durable_reminders",),
        "cancel_reminders",
    ),
    _r(
        DemoState.REMINDERS_ACTIVE,
        TransitionCommand.MARK_READY,
        DemoState.READY,
        SYSTEM,
        ("start_window_reached",),
    ),
    _r(DemoState.READY, TransitionCommand.START_DEMO, DemoState.IN_PROGRESS, ANY_BUSINESS_ACTOR),
    _r(
        DemoState.IN_PROGRESS,
        TransitionCommand.COMPLETE_DEMO,
        DemoState.COMPLETED,
        ANY_BUSINESS_ACTOR,
        ("outcome_evidence_present",),
    ),
    _r(
        DemoState.COMPLETED,
        TransitionCommand.QUEUE_ANALYSIS,
        DemoState.ANALYSIS_PENDING,
        SYSTEM,
        side_effects=("enqueue_analysis",),
    ),
    _r(
        DemoState.ANALYSIS_PENDING,
        TransitionCommand.COMPLETE_ANALYSIS,
        DemoState.ANALYZED,
        SYSTEM,
        ("analysis_schema_valid",),
    ),
    _r(
        DemoState.ANALYZED,
        TransitionCommand.START_CONVERSION,
        DemoState.CONVERSION_FOLLOW_UP,
        SYSTEM,
        ("conversion_policy_loaded",),
    ),
    _r(
        DemoState.CONVERSION_FOLLOW_UP,
        TransitionCommand.PROPOSE_OFFER,
        DemoState.OFFER_PENDING,
        SYSTEM,
        ("offer_policy_valid",),
        ("request_offer_approval",),
    ),
    _r(
        DemoState.CONVERSION_FOLLOW_UP,
        TransitionCommand.REQUEST_PAYMENT,
        DemoState.PAYMENT_PENDING,
        USER,
        ("canonical_quote_verified",),
        ("create_payment_order",),
    ),
    _r(
        DemoState.OFFER_PENDING,
        TransitionCommand.REQUEST_PAYMENT,
        DemoState.PAYMENT_PENDING,
        USER,
        ("offer_approved", "canonical_quote_verified"),
        ("create_payment_order",),
    ),
    _r(
        DemoState.PAYMENT_PENDING,
        TransitionCommand.VERIFY_PAYMENT,
        DemoState.PAID,
        PROVIDER,
        (
            "cashfree_signature_verified",
            "amount_currency_binding_verified",
            "activation_not_previously_applied",
        ),
        ("activate_website_subscription",),
        "open_payment_review",
    ),
    _r(
        DemoState.PAYMENT_PENDING,
        TransitionCommand.REPORT_PAYMENT_FAILURE,
        DemoState.PAYMENT_FAILED,
        PROVIDER,
    ),
    _r(
        DemoState.PAYMENT_PENDING,
        TransitionCommand.EXPIRE_PAYMENT,
        DemoState.PAYMENT_EXPIRED,
        SYSTEM,
        ("payment_expired",),
    ),
    _r(
        DemoState.PAYMENT_PENDING,
        TransitionCommand.REVIEW_PAYMENT,
        DemoState.PAYMENT_REVIEW,
        SYSTEM,
    ),
    _r(
        DemoState.PAYMENT_FAILED,
        TransitionCommand.RETRY_PAYMENT,
        DemoState.PAYMENT_PENDING,
        USER,
        ("retry_allowed",),
    ),
    _r(
        DemoState.PAYMENT_EXPIRED,
        TransitionCommand.RETRY_PAYMENT,
        DemoState.PAYMENT_PENDING,
        USER,
        ("new_quote_verified",),
    ),
    _r(
        DemoState.PAYMENT_REVIEW,
        TransitionCommand.VERIFY_PAYMENT,
        DemoState.PAID,
        PROVIDER,
        ("manual_reconciliation_verified", "activation_not_previously_applied"),
        ("activate_website_subscription",),
    ),
    _r(
        DemoState.PAID,
        TransitionCommand.HANDOFF_ONBOARDING,
        DemoState.ONBOARDING_HANDOFF,
        SYSTEM,
        ("website_activation_confirmed",),
        ("publish_onboarding_handoff",),
    ),
    _r(
        DemoState.ONBOARDING_HANDOFF,
        TransitionCommand.COMPLETE_ONBOARDING,
        DemoState.CONVERTED,
        SYSTEM,
        ("onboarding_acknowledged",),
        ("request_welcome_delivery",),
    ),
    _r(
        DemoState.SCHEDULED,
        TransitionCommand.REQUEST_RESCHEDULE,
        DemoState.RESCHEDULE_REQUESTED,
        ANY_BUSINESS_ACTOR,
        side_effects=("cancel_reminders",),
    ),
    _r(
        DemoState.REMINDERS_ACTIVE,
        TransitionCommand.REQUEST_RESCHEDULE,
        DemoState.RESCHEDULE_REQUESTED,
        ANY_BUSINESS_ACTOR,
        side_effects=("cancel_reminders",),
    ),
    _r(
        DemoState.RESCHEDULE_REQUESTED,
        TransitionCommand.REOPEN_NEGOTIATION,
        DemoState.SLOT_NEGOTIATING,
        SYSTEM,
        side_effects=("cancel_calendar_event", "release_slot_hold"),
    ),
    _r(
        DemoState.SLOT_EXPIRED,
        TransitionCommand.REOPEN_NEGOTIATION,
        DemoState.SLOT_NEGOTIATING,
        ANY_BUSINESS_ACTOR,
    ),
    _r(
        DemoState.READY,
        TransitionCommand.REPORT_USER_NO_SHOW,
        DemoState.NO_SHOW_USER,
        SYSTEM,
        ("attendance_evidence_present",),
    ),
    _r(
        DemoState.READY,
        TransitionCommand.REPORT_TUTOR_NO_SHOW,
        DemoState.NO_SHOW_TUTOR,
        SYSTEM,
        ("attendance_evidence_present",),
    ),
    _r(
        DemoState.IN_PROGRESS,
        TransitionCommand.REPORT_TECHNICAL_FAILURE,
        DemoState.TECHNICAL_FAILURE,
        ANY_BUSINESS_ACTOR,
    ),
    _r(
        DemoState.NO_SHOW_USER,
        TransitionCommand.REQUEST_RESCHEDULE,
        DemoState.RESCHEDULE_REQUESTED,
        USER,
    ),
    _r(
        DemoState.NO_SHOW_TUTOR,
        TransitionCommand.REQUEST_RESCHEDULE,
        DemoState.RESCHEDULE_REQUESTED,
        USER,
    ),
    _r(
        DemoState.TECHNICAL_FAILURE,
        TransitionCommand.REQUEST_RESCHEDULE,
        DemoState.RESCHEDULE_REQUESTED,
        ANY_BUSINESS_ACTOR,
    ),
)

_CANCELLABLE: set[DemoState] = {
    DemoState.QUALIFYING,
    DemoState.TUTOR_MATCHING,
    DemoState.TUTOR_SHORTLISTED,
    DemoState.SLOT_NEGOTIATING,
    DemoState.SLOT_HELD,
    DemoState.AWAITING_CONFIRMATIONS,
    DemoState.SCHEDULED,
    DemoState.REMINDERS_ACTIVE,
    DemoState.READY,
    DemoState.RESCHEDULE_REQUESTED,
    DemoState.SLOT_EXPIRED,
    DemoState.NO_SHOW_USER,
    DemoState.NO_SHOW_TUTOR,
    DemoState.TECHNICAL_FAILURE,
}
_TERMINAL_SET = set[DemoState](
    {
        DemoState.CONVERTED,
        DemoState.CANCELLED_BY_USER,
        DemoState.CANCELLED_BY_TUTOR,
        DemoState.HUMAN_HANDOFF,
        DemoState.FAILED,
    }
)
_ALL_STATES = cast(set[DemoState], set(DemoState))
_ESCALATABLE: set[DemoState] = _ALL_STATES - _TERMINAL_SET
_FAILABLE: set[DemoState] = _ALL_STATES - _TERMINAL_SET

_ALL_TRANSITIONS = (
    _TRANSITIONS
    + tuple(
        _r(
            state,
            TransitionCommand.CANCEL_BY_USER,
            DemoState.CANCELLED_BY_USER,
            USER,
            side_effects=("cancel_pending_side_effects",),
        )
        for state in sorted(_CANCELLABLE, key=lambda item: item.value)
    )
    + tuple(
        _r(
            state,
            TransitionCommand.CANCEL_BY_TUTOR,
            DemoState.CANCELLED_BY_TUTOR,
            TUTOR,
            side_effects=("cancel_pending_side_effects",),
        )
        for state in sorted(_CANCELLABLE, key=lambda item: item.value)
    )
    + tuple(
        _r(
            state,
            TransitionCommand.ESCALATE_HUMAN,
            DemoState.HUMAN_HANDOFF,
            SYSTEM,
            side_effects=("open_human_handoff_ticket",),
        )
        for state in sorted(_ESCALATABLE, key=lambda item: item.value)
    )
    + tuple(
        _r(
            state,
            TransitionCommand.FAIL,
            DemoState.FAILED,
            SYSTEM,
            side_effects=("record_terminal_failure",),
        )
        for state in sorted(_FAILABLE, key=lambda item: item.value)
    )
)

_INDEX = {(rule.before, rule.command): rule for rule in _ALL_TRANSITIONS}
if len(_INDEX) != len(_ALL_TRANSITIONS):
    raise RuntimeError("duplicate state/command transition registration")

TERMINAL_STATES = frozenset(
    {
        DemoState.CONVERTED,
        DemoState.CANCELLED_BY_USER,
        DemoState.CANCELLED_BY_TUTOR,
        DemoState.HUMAN_HANDOFF,
        DemoState.FAILED,
    }
)


def registered_transitions() -> tuple[TransitionRule, ...]:
    return _ALL_TRANSITIONS


def resolve_transition(
    before: DemoState, command: TransitionCommand, actor: ActorType
) -> TransitionRule:
    try:
        rule = _INDEX[(before, command)]
    except KeyError as exc:
        raise ValueError(f"transition not allowed: {before}/{command}") from exc
    if actor not in rule.allowed_actors:
        raise PermissionError(f"actor {actor} cannot execute {command} from {before}")
    return rule
