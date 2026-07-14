# Database configuration correction report

Date: 2026-07-13. This report corrects the integration boundary after confirmation that the existing
NXTutors website is Laravel with MySQL and that learner/tutor profiles are represented by the legacy
`register` table. It records a code/data boundary; it does not claim access to, migration of, or
validation against the production database.

## Correct ownership

- Laravel/MySQL remains authoritative for website identities, learner/tutor profiles, tutor-course
  projections, reviews/social proof, plans, orders, and subscriptions.
- Demo Command Center owns its normalized lifecycle in Aurora PostgreSQL. Its two Alembic revisions
  register 45 service-owned tables covering cases, transitions, inbox/outbox, scheduling,
  communications, outcomes, models, discounts, payments, onboarding, consent, audit, flags, and
  regional aggregates.
- Python receives no MySQL credentials and performs no arbitrary MySQL read or write. It calls the
  versioned Laravel gateway under `/internal/api/v1/demo-command-center`.
- Website mutations are limited to reviewed gateway operations. Subscription activation uses a
  MySQL idempotency ledger, unique provider/demo/evidence bindings, and a transactional website
  outbox.
- There is no cross-database transaction. Payment activation and website projection are idempotent
  sagas with reconciliation.

The website Git root happens to be the folder named `public` at
`E:\NX Tutor\Nxtutors Website\public`; its actual web document directory is the nested Laravel
`public/`. The adapter in this repository belongs at the Laravel root or in a private Composer
package, never in that nested document directory.

## Legacy `register` table treatment

The user-supplied schema contains identity/contact, address, role, qualification, uploaded document,
authentication, and profile fields in one legacy row. Column types and constraints must still be
verified per target environment; the supplied excerpt does not prove primary-key/auto-increment,
index, timestamp, or foreign-key behavior.

The gateway applies explicit projections rather than serializing the model:

| Use | Allowlisted fields/effect |
|---|---|
| Resolve/minimum profile | `id`, `user_id`, `name`, `status`, `user_type`, `join_as`, `for_class`, `class_type`, `budget`, `city`, `district`, `state`, `pincode` |
| Resolve lookup only | `email` or `phone` may be an exact lookup input; neither is returned by the minimum identity projection |
| Tutor candidate | The preceding safe identity/location fields plus `experience`, `education`, `other_education`, and bounded `profile`/`profile_desc`/`pro_desc`; related course and explicitly approved review projections are normalized separately |
| Tutor email | `email` is returned only by the scoped, purpose-bound tutor contact endpoint for server-side notification and must not be exposed to a learner |
| Availability | Always `unknown` until a reviewed authoritative schedule/exception model exists; the website's placeholder score is not booking evidence |

Excluded from general projections are `password`, `c_password`, `otp`, `otp_status`, document
number/type, `frount_image`, `back_image`, `degree`, avatar, raw uploaded files, date of birth, gender,
full address, and unrestricted email/phone. These fields are not required to rank or schedule a demo
and several are credentials, identity documents, or high-risk personal data. Uploaded paths must
never be treated as public integration URLs.

## Gateway evidence in this repository

The Laravel adapter contains HMAC authentication with key ID, timestamp, nonce replay store,
source/audience, sorted scopes, raw-body hash and constant-time signature; strict requests; rate
limits; allowlisted query repositories; audit records; idempotent demo projection/onboarding status;
and exactly-once subscription activation. Its migration creates only integration-owned ledger,
projection, outbox, replay, idempotency, and audit tables; it does not duplicate the Demo lifecycle
in MySQL.

Implemented route groups include identity/minimum profile, tutor candidates/profile/contact,
reference catalog/regions, social proof, plans/quotes, subscription/order state, verified
activation, and demo/onboarding projections. They are disabled until installed and configured in the
actual Laravel application.

## Required closure checks

1. Install the adapter at the real Laravel root, review its service provider/middleware registration,
   and run migrations in a reviewed window. Do not write into the nested web document directory.
2. Run its feature tests and contract tests against a sanitized schema clone representative of the
   deployed MySQL version and legacy column variants.
3. Revalidate the signed scope vocabulary end to end. The Python client now requests Laravel's exact
   `demo:tutors:read`, `demo:plans:read`, and `demo:subscription:write` scopes; an installed-host
   contract test must prove the HMAC key allowlist and route middleware accept them.
4. Configure active/paid/subscription status values, default currency, HMAC source/audience/keys,
   audit hash key, allowed scopes, rate limits, and private routing from approved environment values.
5. Validate ambiguous identity handling, both tutor-course table shapes, explicit review approval,
   plan/version/amount conversion, existing subscription state, and activation collision behavior
   with production-like data.
6. Establish an authoritative tutor availability model before enabling automatic booking and a
   reviewed region-membership source before enabling regional administration.

No website data was migrated to PostgreSQL, no direct MySQL access was added to Python, no external
repository was modified by this documentation task, and no production data or credentials were
read.
