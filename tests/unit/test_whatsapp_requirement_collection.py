from __future__ import annotations

from uuid import uuid4

from demo_command_center.infrastructure.database.models import DemoRequirement
from demo_command_center.infrastructure.inbox.processor import (
    REQUIRED_DEMO_FIELDS,
    _apply_requirement_updates,
    _extract_requirement_updates,
    _missing_requirement_fields,
    _next_requirement_step,
    _reply_variables,
)


def _requirement() -> DemoRequirement:
    return DemoRequirement(
        demo_case_id=uuid4(),
        timezone="Asia/Kolkata",
        preferred_times=[],
        missing_fields=list(REQUIRED_DEMO_FIELDS),
        version=1,
    )


def test_whatsapp_requirement_collection_corrects_subject_and_keeps_other_details() -> None:
    requirement = _requirement()

    _apply_requirement_updates(
        requirement,
        _extract_requirement_updates(
            "class 7 Gurgaon mathematics", current_step="collect_requirements"
        ),
    )
    requirement.missing_fields = _missing_requirement_fields(requirement)
    assert requirement.class_level == "Class 7"
    assert requirement.location_region == "Gurugram"
    assert requirement.subject == "Mathematics"
    assert _next_requirement_step(requirement.missing_fields) == "collect_mode"

    _apply_requirement_updates(
        requirement,
        _extract_requirement_updates("2", current_step="collect_mode"),
    )
    requirement.missing_fields = _missing_requirement_fields(requirement)
    assert requirement.mode == "online"
    assert _next_requirement_step(requirement.missing_fields) == "collect_preferred_times"

    _apply_requirement_updates(
        requirement,
        _extract_requirement_updates("1", current_step="collect_preferred_times"),
    )
    requirement.missing_fields = _missing_requirement_fields(requirement)
    assert requirement.preferred_times == [{"label": "morning"}]
    assert _next_requirement_step(requirement.missing_fields) == "requirements_complete"

    changed = _apply_requirement_updates(
        requirement,
        _extract_requirement_updates(
            "no I dont want mathematics I want to do skating",
            current_step="requirements_complete",
            current_subject=requirement.subject,
        ),
    )
    requirement.missing_fields = _missing_requirement_fields(requirement)

    assert "subject" in changed
    assert requirement.subject == "Skating"
    assert requirement.class_level == "Class 7"
    assert requirement.location_region == "Gurugram"
    assert requirement.mode == "online"
    assert requirement.preferred_times == [{"label": "morning"}]
    assert _next_requirement_step(requirement.missing_fields) == "requirements_complete"
    assert "Skating" in _reply_variables(requirement, changed_fields=changed)["body"]


def test_subject_negation_without_replacement_asks_for_subject_again() -> None:
    requirement = _requirement()
    requirement.class_level = "Class 7"
    requirement.location_region = "Gurugram"
    requirement.subject = "Mathematics"
    requirement.mode = "online"
    requirement.preferred_times = [{"label": "morning"}]

    changed = _apply_requirement_updates(
        requirement,
        _extract_requirement_updates(
            "not mathematics",
            current_step="requirements_complete",
            current_subject=requirement.subject,
        ),
    )
    requirement.missing_fields = _missing_requirement_fields(requirement)

    assert changed == frozenset({"subject"})
    assert requirement.subject is None
    assert requirement.missing_fields == ["subject"]
    assert "Which subject or skill" in _reply_variables(requirement, changed_fields=changed)["body"]
