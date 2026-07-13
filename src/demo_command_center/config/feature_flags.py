from __future__ import annotations

from dataclasses import dataclass

from demo_command_center.config.settings import Settings


@dataclass(frozen=True, slots=True)
class FeatureFlags:
    command_center: bool
    scheduling: bool
    reminders: bool
    forecasting: bool
    objection_extraction: bool
    post_conversion: bool
    discounts: bool
    payments: bool
    outbound_paused: bool
    new_bookings_paused: bool

    @classmethod
    def from_settings(cls, settings: Settings) -> FeatureFlags:
        return cls(
            command_center=settings.demo_command_center_enabled,
            scheduling=settings.demo_scheduling_enabled,
            reminders=settings.demo_reminders_enabled,
            forecasting=settings.demo_forecasting_enabled,
            objection_extraction=settings.demo_objection_extraction_enabled,
            post_conversion=settings.demo_post_conversion_enabled,
            discounts=settings.demo_discounts_enabled,
            payments=settings.demo_payments_enabled,
            outbound_paused=settings.demo_outbound_paused,
            new_bookings_paused=settings.demo_new_bookings_paused,
        )
