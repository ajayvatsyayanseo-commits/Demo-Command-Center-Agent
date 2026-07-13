# ADR-006: Google Calendar and Meet identity

- Status: Accepted
- Date: 2026-07-13

## Context

No verified calendar ownership exists. Personal tutor calendars or reusable links create privacy, continuity, and offboarding risk.

## Decision

Use an NXTutors-controlled organizer calendar. Prefer Workspace domain-wide delegation to a configured organizational user; otherwise use reviewed OAuth with least Calendar scopes. Credentials are referenced from Secrets Manager and rotated. Each online demo requests one unique Meet conference with a deterministic per-operation request ID and private extended `demo_id`. External attendees receive product-approved visibility only.

## Consequences

NXTutors can reconcile/update/cancel events independent of individual staff accounts. Conference creation may be asynchronous and must be polled/reconciled. Meeting links are encrypted, excluded from logs/analytics, and retained only per policy. The feature stays disabled until domain, delegated user, calendar ID, scopes, and rotation are verified.
