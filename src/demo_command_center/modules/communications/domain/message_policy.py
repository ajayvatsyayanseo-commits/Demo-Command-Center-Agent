from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class Channel(StrEnum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"


class MessageClass(StrEnum):
    MARKETING = "marketing"
    UTILITY = "utility"
    TRANSACTIONAL = "transactional"


@dataclass(frozen=True, slots=True)
class QuietHours:
    starts_at: time
    ends_at: time

    def contains(self, local_time: time) -> bool:
        if self.starts_at == self.ends_at:
            return False
        if self.starts_at < self.ends_at:
            return self.starts_at <= local_time < self.ends_at
        return local_time >= self.starts_at or local_time < self.ends_at


@dataclass(frozen=True, slots=True)
class CommunicationPreference:
    timezone: str
    preferred_channels: tuple[Channel, ...]
    opted_out_at: datetime | None = None

    def __post_init__(self) -> None:
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("communication timezone must be a valid IANA zone") from exc
        if not self.preferred_channels:
            raise ValueError("at least one preferred channel is required")
        if self.opted_out_at is not None and self.opted_out_at.tzinfo is None:
            raise ValueError("opt-out time must be timezone-aware")


@dataclass(frozen=True, slots=True)
class MessageRequest:
    message_class: MessageClass
    available_channels: frozenset[Channel]
    template_ref: str | None
    meta_service_window_open: bool
    expected_cost_minor: int


@dataclass(frozen=True, slots=True)
class MessagePolicy:
    version: str
    quiet_hours: QuietHours
    allowed_after_opt_out: frozenset[MessageClass]
    whatsapp_template_required_outside_window: bool
    provider_retry_limit: int
    maximum_cost_minor: int
    opt_out_keywords: frozenset[str]

    def __post_init__(self) -> None:
        if not self.version.strip():
            raise ValueError("message policy version is required")
        if self.provider_retry_limit < 0 or self.maximum_cost_minor < 0:
            raise ValueError("retry and cost limits cannot be negative")
        if any(not keyword.strip() for keyword in self.opt_out_keywords):
            raise ValueError("opt-out keywords cannot be blank")


@dataclass(frozen=True, slots=True)
class MessageDecision:
    allowed: bool
    channel: Channel | None
    template_ref: str | None
    not_before: datetime
    reason: str
    policy_version: str
    provider_retry_limit: int


def record_opt_out(
    preference: CommunicationPreference,
    inbound_text: str,
    policy: MessagePolicy,
    *,
    now: datetime,
) -> CommunicationPreference:
    normalized = inbound_text.strip().casefold()
    keywords = {keyword.strip().casefold() for keyword in policy.opt_out_keywords}
    if normalized in keywords:
        return replace(preference, opted_out_at=now)
    return preference


def _after_quiet_hours(
    now: datetime, preference: CommunicationPreference, quiet: QuietHours
) -> datetime:
    zone = ZoneInfo(preference.timezone)
    local = now.astimezone(zone)
    if not quiet.contains(local.timetz().replace(tzinfo=None)):
        return now
    next_date = local.date()
    if quiet.starts_at > quiet.ends_at and local.timetz().replace(tzinfo=None) >= quiet.starts_at:
        next_date += timedelta(days=1)
    local_end = datetime.combine(next_date, quiet.ends_at, tzinfo=zone)
    return local_end.astimezone(UTC)


def evaluate_message(
    request: MessageRequest,
    preference: CommunicationPreference,
    policy: MessagePolicy,
    *,
    now: datetime,
) -> MessageDecision:
    if now.tzinfo is None:
        raise ValueError("message decision time must be timezone-aware")
    if (
        preference.opted_out_at is not None
        and request.message_class not in policy.allowed_after_opt_out
    ):
        return MessageDecision(
            False,
            None,
            None,
            now,
            "recipient_opted_out",
            policy.version,
            policy.provider_retry_limit,
        )
    if request.expected_cost_minor < 0 or request.expected_cost_minor > policy.maximum_cost_minor:
        return MessageDecision(
            False,
            None,
            None,
            now,
            "cost_limit_exceeded",
            policy.version,
            policy.provider_retry_limit,
        )
    chosen = next(
        (
            channel
            for channel in preference.preferred_channels
            if channel in request.available_channels
        ),
        None,
    )
    if chosen is None:
        return MessageDecision(
            False,
            None,
            None,
            now,
            "no_permitted_channel",
            policy.version,
            policy.provider_retry_limit,
        )
    if (
        chosen is Channel.WHATSAPP
        and not request.meta_service_window_open
        and policy.whatsapp_template_required_outside_window
        and not request.template_ref
    ):
        return MessageDecision(
            False,
            None,
            None,
            now,
            "approved_template_required",
            policy.version,
            policy.provider_retry_limit,
        )
    not_before = _after_quiet_hours(now, preference, policy.quiet_hours)
    return MessageDecision(
        True,
        chosen,
        request.template_ref,
        not_before,
        "permitted",
        policy.version,
        policy.provider_retry_limit,
    )
