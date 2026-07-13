from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from demo_command_center.glue.envelopes.agent_event import ActorType
from demo_command_center.state.machine.demo_state import DemoState
from demo_command_center.state.transitions.table import (
    TERMINAL_STATES,
    TransitionCommand,
    registered_transitions,
    resolve_transition,
)


def test_every_nonterminal_state_has_registered_exit() -> None:
    source_states = {rule.before for rule in registered_transitions()}
    assert set(DemoState) == source_states | set(TERMINAL_STATES)


def test_state_and_command_pairs_are_unique() -> None:
    pairs = [(rule.before, rule.command) for rule in registered_transitions()]
    assert len(pairs) == len(set(pairs))


def test_payment_verification_requires_provider_actor() -> None:
    with pytest.raises(PermissionError):
        resolve_transition(
            DemoState.PAYMENT_PENDING,
            TransitionCommand.VERIFY_PAYMENT,
            ActorType.USER,
        )


@given(st.sampled_from(list(TERMINAL_STATES)), st.sampled_from(list(TransitionCommand)))
def test_terminal_states_have_no_transition(state: DemoState, command: TransitionCommand) -> None:
    with pytest.raises(ValueError):
        resolve_transition(state, command, ActorType.SYSTEM)
