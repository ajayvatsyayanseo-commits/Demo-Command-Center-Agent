from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256

from demo_command_center.modules.demo_core.domain.identifiers import RegionId, TenantId


class RegionalRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    OPERATIONS_SUB_ADMIN = "operations_sub_admin"
    ANALYST = "analyst"


@dataclass(frozen=True, slots=True)
class PrincipalScope:
    principal_ref: str
    tenant_id: TenantId
    role: RegionalRole
    assigned_regions: frozenset[RegionId]
    global_scope_granted: bool


@dataclass(frozen=True, slots=True)
class ScopeRequest:
    tenant_id: TenantId
    requested_regions: frozenset[RegionId]
    export_requested: bool


@dataclass(frozen=True, slots=True)
class RegionalAuthorizationPolicy:
    version: str
    global_roles: frozenset[RegionalRole]
    export_roles: frozenset[RegionalRole]


@dataclass(frozen=True, slots=True)
class ScopeDecision:
    authorized: bool
    tenant_id: TenantId
    effective_regions: frozenset[RegionId]
    reason: str
    audit_required: bool
    policy_version: str


def authorize_scope(
    principal: PrincipalScope,
    request: ScopeRequest,
    policy: RegionalAuthorizationPolicy,
) -> ScopeDecision:
    if principal.tenant_id != request.tenant_id:
        return ScopeDecision(
            False,
            request.tenant_id,
            frozenset(),
            "tenant_scope_denied",
            True,
            policy.version,
        )
    if request.export_requested and principal.role not in policy.export_roles:
        return ScopeDecision(
            False,
            request.tenant_id,
            frozenset(),
            "export_scope_denied",
            True,
            policy.version,
        )
    global_access = principal.global_scope_granted and principal.role in policy.global_roles
    if global_access:
        return ScopeDecision(
            True,
            request.tenant_id,
            request.requested_regions,
            "global_scope_authorized",
            True,
            policy.version,
        )
    if not request.requested_regions or not request.requested_regions.issubset(
        principal.assigned_regions
    ):
        return ScopeDecision(
            False,
            request.tenant_id,
            frozenset(),
            "region_scope_denied",
            True,
            policy.version,
        )
    return ScopeDecision(
        True,
        request.tenant_id,
        request.requested_regions,
        "assigned_region_authorized",
        True,
        policy.version,
    )


class AlertSeverity(StrEnum):
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True, slots=True)
class UnderperformancePolicy:
    version: str
    minimum_cohort_size: int
    minimum_baseline_size: int
    minimum_absolute_decline: Decimal
    minimum_relative_decline: Decimal
    critical_relative_decline: Decimal
    suppression_period: timedelta
    owner_ref: str

    def __post_init__(self) -> None:
        if self.minimum_cohort_size <= 0 or self.minimum_baseline_size <= 0:
            raise ValueError("alert sample thresholds must be positive")
        values = (
            self.minimum_absolute_decline,
            self.minimum_relative_decline,
            self.critical_relative_decline,
        )
        if any(value < 0 for value in values):
            raise ValueError("alert decline thresholds cannot be negative")
        if self.critical_relative_decline < self.minimum_relative_decline:
            raise ValueError("critical threshold must not be lower than warning threshold")
        if self.suppression_period < timedelta(0) or not self.owner_ref.strip():
            raise ValueError("alert suppression and owner policy are invalid")


@dataclass(frozen=True, slots=True)
class MetricCohort:
    tenant_id: TenantId
    region_id: RegionId
    metric_name: str
    cohort_definition: str
    window_ends_at: datetime
    sample_size: int
    value: Decimal
    baseline_sample_size: int
    baseline_value: Decimal


@dataclass(frozen=True, slots=True)
class RegionalAlertDecision:
    create_alert: bool
    deduplication_key: str | None
    severity: AlertSeverity | None
    owner_ref: str | None
    reason: str
    absolute_decline: Decimal | None
    relative_decline: Decimal | None
    policy_version: str


def evaluate_underperformance(
    cohort: MetricCohort,
    policy: UnderperformancePolicy,
    *,
    last_alert_at: datetime | None,
    now: datetime,
) -> RegionalAlertDecision:
    if cohort.window_ends_at.tzinfo is None or now.tzinfo is None:
        raise ValueError("regional alert times must be timezone-aware")
    if (
        cohort.sample_size < policy.minimum_cohort_size
        or cohort.baseline_sample_size < policy.minimum_baseline_size
    ):
        return RegionalAlertDecision(
            False, None, None, None, "sample_suppressed", None, None, policy.version
        )
    if last_alert_at is not None and now < last_alert_at + policy.suppression_period:
        return RegionalAlertDecision(
            False, None, None, None, "alert_suppressed", None, None, policy.version
        )
    absolute = cohort.baseline_value - cohort.value
    relative = Decimal(0) if cohort.baseline_value == 0 else absolute / abs(cohort.baseline_value)
    if absolute < policy.minimum_absolute_decline or relative < policy.minimum_relative_decline:
        return RegionalAlertDecision(
            False,
            None,
            None,
            None,
            "practical_significance_not_met",
            absolute,
            relative,
            policy.version,
        )
    severity = (
        AlertSeverity.CRITICAL
        if relative >= policy.critical_relative_decline
        else AlertSeverity.WARNING
    )
    material = "|".join(
        (
            str(cohort.tenant_id),
            str(cohort.region_id),
            cohort.metric_name,
            cohort.cohort_definition,
            policy.version,
        )
    )
    return RegionalAlertDecision(
        True,
        sha256(material.encode()).hexdigest(),
        severity,
        policy.owner_ref,
        "underperformance_detected",
        absolute,
        relative,
        policy.version,
    )
