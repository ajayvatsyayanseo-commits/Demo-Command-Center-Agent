from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from demo_command_center.modules.demo_core.domain.identifiers import RegionId, TenantId
from demo_command_center.modules.regional_monitoring.application.use_cases import (
    RegionalAuthorizationUseCase,
)
from demo_command_center.modules.regional_monitoring.domain.policy import (
    AlertSeverity,
    MetricCohort,
    PrincipalScope,
    RegionalAuthorizationPolicy,
    RegionalRole,
    ScopeRequest,
    UnderperformancePolicy,
    evaluate_underperformance,
)

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)
TENANT = TenantId("nxtutors")
NORTH = RegionId("north")
SOUTH = RegionId("south")


def _authorization_policy() -> RegionalAuthorizationPolicy:
    return RegionalAuthorizationPolicy(
        "regional-auth-v3",
        frozenset({RegionalRole.SUPER_ADMIN}),
        frozenset({RegionalRole.SUPER_ADMIN, RegionalRole.OPERATIONS_SUB_ADMIN}),
    )


def _alert_policy() -> UnderperformancePolicy:
    return UnderperformancePolicy(
        "regional-alert-v2",
        30,
        100,
        Decimal("0.05"),
        Decimal("0.1"),
        Decimal("0.25"),
        timedelta(hours=12),
        "regional-operations",
    )


def _cohort(**changes: object) -> MetricCohort:
    values: dict[str, object] = {
        "tenant_id": TENANT,
        "region_id": NORTH,
        "metric_name": "paid_conversion_rate",
        "cohort_definition": "completed_demo_30d",
        "window_ends_at": NOW,
        "sample_size": 50,
        "value": Decimal("0.30"),
        "baseline_sample_size": 150,
        "baseline_value": Decimal("0.50"),
    }
    values.update(changes)
    return MetricCohort(**values)  # type: ignore[arg-type]


def test_sub_admin_is_restricted_to_assigned_tenant_and_regions() -> None:
    principal = PrincipalScope(
        "admin-opaque",
        TENANT,
        RegionalRole.OPERATIONS_SUB_ADMIN,
        frozenset({NORTH}),
        False,
    )
    use_case = RegionalAuthorizationUseCase(_authorization_policy())
    allowed = use_case.execute(principal, ScopeRequest(TENANT, frozenset({NORTH}), True))
    assert allowed.authorized
    assert allowed.effective_regions == frozenset({NORTH})
    assert allowed.audit_required

    forged_region = use_case.execute(
        principal, ScopeRequest(TENANT, frozenset({NORTH, SOUTH}), False)
    )
    assert not forged_region.authorized
    assert forged_region.effective_regions == frozenset()
    assert forged_region.reason == "region_scope_denied"

    forged_tenant = use_case.execute(
        principal, ScopeRequest(TenantId("other"), frozenset({NORTH}), False)
    )
    assert not forged_tenant.authorized
    assert forged_tenant.reason == "tenant_scope_denied"


def test_global_scope_requires_both_role_and_explicit_grant() -> None:
    use_case = RegionalAuthorizationUseCase(_authorization_policy())
    super_admin = PrincipalScope(
        "super-opaque",
        TENANT,
        RegionalRole.SUPER_ADMIN,
        frozenset(),
        True,
    )
    allowed = use_case.execute(super_admin, ScopeRequest(TENANT, frozenset({NORTH, SOUTH}), True))
    assert allowed.authorized and allowed.reason == "global_scope_authorized"

    analyst = PrincipalScope(
        "analyst-opaque", TENANT, RegionalRole.ANALYST, frozenset({NORTH}), True
    )
    denied = use_case.execute(analyst, ScopeRequest(TENANT, frozenset({NORTH}), True))
    assert not denied.authorized and denied.reason == "export_scope_denied"


def test_alerts_suppress_small_cohorts_and_recent_duplicates() -> None:
    small = evaluate_underperformance(
        _cohort(sample_size=29), _alert_policy(), last_alert_at=None, now=NOW
    )
    assert not small.create_alert and small.reason == "sample_suppressed"
    suppressed = evaluate_underperformance(
        _cohort(),
        _alert_policy(),
        last_alert_at=NOW - timedelta(hours=1),
        now=NOW,
    )
    assert not suppressed.create_alert and suppressed.reason == "alert_suppressed"


def test_underperformance_alert_is_deduplicated_redacted_and_severity_scoped() -> None:
    warning_cohort = _cohort(value=Decimal("0.43"))
    warning = evaluate_underperformance(
        warning_cohort, _alert_policy(), last_alert_at=None, now=NOW
    )
    assert warning.create_alert
    assert warning.severity is AlertSeverity.WARNING
    assert warning.owner_ref == "regional-operations"
    assert warning.deduplication_key
    assert "admin" not in warning.deduplication_key

    critical = evaluate_underperformance(_cohort(), _alert_policy(), last_alert_at=None, now=NOW)
    repeated = evaluate_underperformance(_cohort(), _alert_policy(), last_alert_at=None, now=NOW)
    assert critical.severity is AlertSeverity.CRITICAL
    assert critical.deduplication_key == repeated.deduplication_key


def test_alert_practical_significance_and_time_validation() -> None:
    stable = evaluate_underperformance(
        _cohort(value=Decimal("0.48")), _alert_policy(), last_alert_at=None, now=NOW
    )
    assert not stable.create_alert
    assert stable.reason == "practical_significance_not_met"
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_underperformance(
            _cohort(window_ends_at=datetime(2026, 1, 1)),
            _alert_policy(),
            last_alert_at=None,
            now=NOW,
        )
