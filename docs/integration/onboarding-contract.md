# Onboarding contract

After website activation is confirmed, Demo Command Center emits `onboarding.paid-user.requested.v1` with opaque demo/user/activation/payment references, approved plan reference, locale, consent refs, and requested onboarding flow. It does not include payment payload, Cashfree secret/data, raw contact data, or welcome copy.

Onboarding durably responds with:

- `onboarding.handoff.accepted.v1`: inbox reference, flow/capability version;
- `onboarding.completed.v1`: onboarding reference, canonical website user ref, completion status;
- `onboarding.failed.v1`: stable reason/retryability/human-ticket ref.

The request idempotency key is stable per activation, and Onboarding must enforce durable uniqueness beyond cache TTL. Demo state remains `PAID` until accepted, then `ONBOARDING_HANDOFF`, then `CONVERTED` only on validated completion. Failure/retry exhaustion opens a ticket; payment is never reversed merely because onboarding is unavailable.

The inspected Onboarding synchronous `{status, reply_text}` shared-secret contract is **UNVERIFIED for paid handoff correctness** and lacks the canonical envelope/durable internal inbox. A compatibility adapter may translate acknowledgements but cannot claim completion without an authoritative event.
