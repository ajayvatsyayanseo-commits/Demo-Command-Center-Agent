# Onboarding contract

After website activation is confirmed and the post-conversion feature is enabled, Demo Command
Center durably emits `onboarding.paid-user.requested.v1` through the canonical HMAC event gateway
with opaque demo/user/activation/payment references, approved plan reference, locale, consent refs,
and requested onboarding flow. It does not include payment payload, Cashfree secret/data, raw
contact data, or welcome copy. When the feature is disabled, onboarding inbox/outbox work remains
durably queued without consuming retry attempts.

Onboarding durably responds with:

- `onboarding.handoff.accepted.v1`: inbox reference, flow/capability version;
- `onboarding.completed.v1`: onboarding reference, canonical website user ref, completion status;
- `onboarding.failed.v1`: stable reason/retryability/human-ticket ref.

The request idempotency key is stable per activation, and Onboarding must enforce durable uniqueness
beyond cache TTL. Its synchronous `accepted`/`duplicate` response must echo the exact request event
ID and represent a durable inbox acknowledgement; a mismatched event ID fails closed. Demo state
remains `PAID` until that acknowledgement or the canonical accepted event, then
`ONBOARDING_HANDOFF`, then `CONVERTED` only on validated completion. Current lookup fails closed if
more than one payment order matches the tenant/demo/user tuple, but a future contract revision should
bind callbacks directly to the outbound request event or causation ID.

The failed-event/human-ticket branch remains a target contract and is not yet implemented in this
service. Payment is never reversed merely because onboarding is unavailable.

The inspected external Onboarding deployment exposes only the synchronous `{status, reply_text}`
shared-secret compatibility contract. It is **UNVERIFIED for paid handoff correctness** and lacks the
canonical envelope/durable internal inbox endpoint targeted by this implementation. The compatibility
adapter cannot claim completion without an authoritative event.
