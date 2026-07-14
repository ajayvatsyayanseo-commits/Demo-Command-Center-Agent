# Outbound pause and duplicate-message response

Use for duplicate sends, wrong recipient/content/template, opt-out breach, service-window violation,
Meta quality incident, or suspected dispatcher/idempotency failure.

## Contain

1. Pause actual sends at Lead Intake, the canonical outbound owner, and set the Demo Command Center
   outbound pause through controlled configuration. Keep pending outbox rows durable.
2. Stop the affected dispatcher/tenant/template if a narrower action is safe. Do not enable this
   service's direct Meta sender.
3. Preserve send operation keys, message/provider references, delivery states, template/policy
   versions, and recipient hashes. Do not include content or phone numbers in the incident.

## Reconcile

- Establish whether duplicates were requests, provider accepts, or delivered business effects.
- Compare communication uniqueness, outbox attempts, Lead Intake suppression, provider status, and
  worker crash/retry timing.
- Check opt-out, consent, quiet hours, service-window/category/template, and recipient resolution.
- Cancel only provider operations that support a safe authoritative cancellation; otherwise prevent
  further sends and coordinate an approved user remedy.

## Resume

Fix the ownership/idempotency/policy cause, replay tests and a controlled canary with one stable key,
then drain transaction-critical items gradually. Product/communications/privacy approval is required
after a policy or recipient incident.

