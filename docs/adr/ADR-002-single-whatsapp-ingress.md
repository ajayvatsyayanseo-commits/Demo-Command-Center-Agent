# ADR-002: Single WhatsApp ingress and outbound owner

- Status: Accepted
- Date: 2026-07-13

## Context

Lead Intake already owns the Meta callback and sends Onboarding replies. Multiple subscribed services can duplicate responses and break deduplication/window policy.

## Decision

Lead Intake is the only public Meta ingress and outbound Meta sender for the shared number. It routes signed, minimized canonical events. Demo Command Center and Onboarding request outbound delivery through its gateway/outbox. Direct Meta routes in this service stay disabled and fail closed.

## Consequences

One message has one send decision and one service-window/template authority. Lead Intake becomes a critical dependency, so requests queue durably and its SLO/circuit breaker are monitored. Existing Onboarding Meta/send compatibility paths must remain unsubscribed.
