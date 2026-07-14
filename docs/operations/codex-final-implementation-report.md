# Codex final implementation report

Date: 2026-07-14 (Asia/Calcutta)  
Repository: `Demo Command Center Agent`  
Production disposition: **not approved; see the production-readiness report**

## 2026-07-14 final evidence addendum

This continuation added the NXTutor `register` read path and teacher-first Google Meet scheduling
flow without giving Demo Command Center direct MySQL credentials:

- Laravel adapter shape-only `.env.example` documents the website-side MySQL variables with empty
  placeholders plus reviewed `DEMO_COMMAND_CENTER_TABLE_*` mappings for legacy table names.
- The Demo service `.env.example` now also includes adapter-scoped `NXTUTORS_WEBSITE_DB_*`
  placeholders for deployment checklists, but Python code still uses only the signed
  `NXTUTORS_WEBSITE_INTERNAL_BASE_URL` gateway.
- The Laravel adapter resolves `register.phone` only through purpose-bound
  `/profiles/{register}/phone-resolve` and `/tutors/{tutor}/phone-resolve` endpoints. Responses
  contain `register:{id}:phone` recipient references and masked phone values, not raw phone numbers.
- The Python website client and `TutorFirstSchedulingCoordinator` implement the required order:
  ask the selected tutor first through Lead Intake, require recorded tutor acceptance, create one
  Google Meet operation, then request Lead Intake delivery of the meeting link to the tutor and the
  student/guardian. If Google returns no meeting URI yet, link delivery is skipped as
  `conference_pending`.
- An API-only Lambda handler was added at `demo_command_center.lambda_handler.handler` with a
  Mangum smoke test. It is a FastAPI HTTP deployment convenience only; ECS/SQS remains the accepted
  worker/runtime model.

Final local evidence from this working tree:

| Gate | Evidence |
|---|---|
| Lock/audit | `.venv\Scripts\uv.exe lock --check` resolved 145 packages; `.venv\Scripts\python -m pip_audit` found no known vulnerabilities, with the expected local-package skip for `demo-command-center-agent`. |
| Lint/type | `ruff format --check src tests scripts`, `ruff check src tests scripts`, and `python -m mypy src tests` passed; mypy covered 178 files. |
| Tests | `pytest --cov=demo_command_center --cov-report=term-missing` passed 184 tests with 83.24% coverage and two dependency warnings: Starlette/httpx TestClient deprecation and Mangum event-loop deprecation. |
| Contracts/workflows/hygiene/migrations | Contracts valid: 10 schemas, 12 JSON files, 2 YAML files, 21 OpenAPI operations. Workflows valid: 7 workflows, 3 actions, 50 steps. Hygiene valid: 148 Python files. Migrations valid: 3 revisions, head `20260713_000003`. |
| Laravel adapter | `php -d extension=pdo_sqlite -d extension=sqlite3 vendor/bin/phpunit --colors=never` passed 20 tests, 95 assertions. |
| Terraform | `terraform fmt -check -recursive infra/terraform` passed; dev/staging/prod `init -backend=false` and `validate` passed. |
| Production check | `scripts/production_check.py --allow-skips` reported 15 passed, 0 failed, 9 skipped, overall PARTIAL. Strict `scripts/production_check.py` exited nonzero with the same 15/0/9 summary and overall INCOMPLETE. |

`make` was not installed on this Windows shell, so the `make check` target commands were executed
directly via `.venv\Scripts\uv.exe run`. The `uv run mypy` console-script shim failed on Windows,
so the equivalent `uv run python -m mypy src tests` command was used and passed.

Production remains **NO-GO** because release evidence is still absent for Docker build/runtime,
container vulnerability scan/SBOM, Gitleaks, Terraform security scan, real PostgreSQL round-trip,
load smoke, deployed smoke, AWS plan/apply, and live/sandbox provider compatibility. Lead Intake and
Onboarding external contract deployment also remain blockers.

## Outcome

The architecture scaffold was advanced into an implementation with deterministic business modules,
expanded persistence, durable authenticated ingress, provider adapters, a Laravel/MySQL gateway
package, AWS infrastructure definitions, CI/CD definitions, and operational runbooks. The service
still has material integration and evidence gaps, so this report intentionally does not describe it
as a completed live production system.

The authoritative readiness decision and gate details are in
[`production-readiness-report.md`](production-readiness-report.md). Requirement-by-requirement
evidence is in [`requirement-traceability-matrix.md`](requirement-traceability-matrix.md).

## Implemented capabilities

- Explicit demo lifecycle/state registry with guarded transitions and optimistic version intent.
- Deterministic tutor matching with hard/preference separation, stale-data handling, explainable
  ranking, explicit tutor selection, and no-match relaxation/human handoff.
- Timezone/DST-safe slot proposal and hold/confirmation collision policies.
- Reminder, quiet-hours/service-window communication, opt-out, no-show, quality, objection,
  forecasting/evaluation, next-best-action, discount/offer, payment verification, and regional alert/
  authorization policies.
- Typed, fail-closed configuration; local/real runtime profiles; startup validation; request size,
  host/CORS/security-header and correlation/tracing middleware; PII-safe logging.
- HMAC service authentication with server-side key-to-source/scope grants, audience binding,
  timestamp/nonce replay protection, rotation overlap, and constant-time signature comparison.
- Raw-body Meta and Cashfree signature verification; provider webhooks enter durable ingress before
  asynchronous processing. Direct Meta mode is off by default.
- AES-GCM encrypted inbox/outbox/provider payload storage with associated data and key references.
- SQLAlchemy unit of work, durable inbox processor, generic durable outbox publisher, SQS long-poll
  adapter/worker, and deterministic demo-handoff/Cashfree processing slices.
- Guarded, audited CLIs for retention cleanup, one-event inbox replay, inspected SQS DLQ redrive,
  bounded Cashfree reconciliation, and persisted forecasting calibration/drift evaluation.
- Real-code clients for Laravel, Lead Intake outbound, canonical and compatibility Onboarding,
  Cashfree, Google Calendar/Meet, SES, SQS, and advisory OpenAI. They return safe failures rather
  than fake success.
- Private Laravel gateway package with HMAC/replay/scope/rate/audit middleware; allowlisted identity,
  tutor, catalog, region, social-proof, plan/quote and subscription-state projections; idempotent demo/
  onboarding projections; and exactly-once activation ledger plus transactional outbox.
- Terraform target topology for isolated dev/staging/prod AWS environments and OIDC/digest-based
  GitHub build, deploy, security, plan, and rollback workflows.

## Architecture and ADR status

ADRs 001-012 remain accepted and were not superseded: modular monolith, sole WhatsApp ownership in
Lead Intake, Laravel/MySQL ownership, inbox/outbox idempotency, payment ownership, controlled Google
identity, LLM boundaries, explicit sagas, non-authoritative Redis, PII-safe analytics, AWS runtime,
and immutable deployment/rollback. No material architecture change requiring a new ADR was made.

The implementation preserves the dependency direction `transport/workers/CLI -> application ->
domain`, with concrete infrastructure depending on application ports/domain types. Domain modules do
not import FastAPI, SQLAlchemy, provider SDKs, or test fakes.

## Database migrations

| Revision | Purpose | Evidence/status |
|---|---|---|
| `20260713_000001` | Operational core: demo case/transitions, inbox/outbox, idempotency, handoff, audit | Offline SQL generation last known successful; no clean PostgreSQL runtime upgrade/downgrade in this environment. |
| `20260713_000002` | Remaining lifecycle/scheduling/communication/outcome/model/evaluation/discount/payment/onboarding/consent/region tables plus retention/legal-hold columns | Metadata registers the expanded owned table set. Imports live ORM metadata, which needs migration immutability review and real PostgreSQL downgrade/re-upgrade proof. |
| `20260713_000003` | Encrypted restricted Cashfree checkout sessions | Offline SQL generation passed; real PostgreSQL downgrade/re-upgrade proof remains required. |

Critical uniqueness/index evidence covers inbox events, outbox operations/messages, active slot holds,
provider events/payment attempts, paid transitions/activation keys, and open handoff reasons. Redis is
not a durability or uniqueness authority.

The website remains MySQL. The correction and safe `register` projection are documented in
[`../discovery/codex-database-config-correction-report.md`](../discovery/codex-database-config-correction-report.md).

## Demo Command Center HTTP boundaries

| Method/path | Authentication/purpose |
|---|---|
| `GET /health/live` | Public liveness; service/version only |
| `GET /health/ready` | Public readiness with non-sensitive aggregate checks |
| `GET /health/dependencies` | HMAC `health:read`; protected dependency status |
| `POST /v1/internal/events` | HMAC `events:write`; canonical non-provider event ingress |
| `POST /v1/internal/whatsapp/handoffs` | HMAC `handoffs:write`; canonical WhatsApp handoff only |
| `GET /v1/internal/events/{event_id}` | HMAC `events:read`; durable processing status |
| `GET/POST /v1/provider/meta/whatsapp` | Direct-mode verification/ingress; disabled by default and not a second active responder |
| `POST /v1/provider/cashfree` | Raw-body Cashfree signature/timestamp verification and durable acceptance; hidden while payments are disabled |

Interactive docs/OpenAPI are not mounted in production. The checked-in contract under
`contracts/openapi/` remains the versioned integration artifact and must be revalidated against the
final runtime.

## Laravel gateway endpoints

All are under `/internal/api/v1/demo-command-center` and require HMAC, replay protection, an exact
`demo:*` scope, rate limiting, and audit middleware:

- identity resolve and minimum profile;
- tutor candidates, tutor profile, and purpose-bound contact resolution;
- reference catalog, region mappings, and approved social proof;
- approved plans, bound plan quote, and subscription/order state;
- verified subscription activation;
- demo projection and onboarding-status projection.

The package has not been installed in the actual website deployment. Python now requests the exact
Laravel `demo:*` scopes; an installed-host contract test must still prove its configured key allowlist,
HMAC canonicalization, route middleware, and legacy schema behavior.

## Event and side-effect contracts

- Canonical `agent-event-envelope.v1` carries schema version, event/idempotency/correlation/causation,
  source/target, tenant/region, actor/subject, PII classification, occurred time, and typed payload.
- `whatsapp.handoff.demo.v1` is the inbound Lead contract; duplicate delivery is a normal durable
  acknowledgement.
- A valid new handoff creates `QUALIFYING` state plus requirement/conversation/identity/transition
  records and an encrypted `outbound.delivery.requested.v1` missing-requirements request atomically.
- Cashfree events are normalized behind the signed provider route and checked against a stored order
  binding before a paid decision.
- Verified paid processing records one paid transition and emits an encrypted website activation
  operation. Website activation writes its own unique ledger and MySQL outbox.
- When post-conversion is enabled, website activation acknowledgement transactionally queues the
  canonical paid-to-Onboarding request. Exact event-ID inbox acknowledgement advances `PAID` to
  `ONBOARDING_HANDOFF`; validated accepted/completed events are idempotent, and completion queues one
  welcome request to Lead Intake. Disabled onboarding/outbound targets remain queued without burning
  retry attempts. The inspected external Onboarding deployment does not implement this durable target
  contract, and the failed-event/human-ticket branch remains incomplete.
- Outbound WhatsApp requests are designed for Lead Intake only. The required external endpoint is
  missing in the inspected Lead repository, so outbound remains an integration blocker.

## Provider integration status

| Dependency | Code status | Sandbox/live status |
|---|---|---|
| Laravel/MySQL gateway | Python client and private Laravel adapter package present; exact `demo:*` scopes aligned in source | Not installed or tested against target Laravel/MySQL/HMAC configuration |
| Lead Intake/Meta outbound | HMAC client targets `/v1/internal/outbound/whatsapp` | Endpoint absent in inspected Lead code; no live compatibility |
| Direct Meta ingress | Raw-body verification and durable route present, safe-off default | Must remain disabled in normal topology; no live validation |
| Onboarding | Canonical HMAC event client/outbox recorder/routing, exact acknowledgement check, accepted/completed handlers, welcome outbox, schemas, and shared-secret compatibility client present | External deployment exposes only the legacy endpoint; durable paid-handoff semantics are not live compatible or validated |
| Google Calendar/Meet | Workspace Secrets Manager/delegation client, free/busy/create/cancel/reconcile code present | No Workspace domain, organizer, scopes, license, secret, or sandbox/live call validated |
| SES | Templated-send adapter present | Identity, production access, quotas, events, bounce/complaint processing unvalidated |
| Cashfree | Server order/status client and signed webhook/payment policy present | No sandbox/live credentials/calls; complete order/reconcile/website activation saga not exercised |
| OpenAI | Structured advisory client with budgets/circuit/schema validation present | No live call or approved production model/prompt/evaluation |
| AWS | SQS clients and Terraform target architecture present | No account plan/apply or service connectivity validation |

## Test and validation evidence

Final local evidence was 184 Python tests, 83.24% coverage, and strict mypy success over 178 files.
This is local repository evidence only, not live production proof.

The Laravel package test command with the locally installed but default-disabled SQLite extensions
passed 20 tests and 95 assertions. Contract validation reported 21 OpenAPI operations. That proves
the standalone package's SQLite feature suite and checked-in contract, not its installation in the
real Laravel/MySQL application.

The single strict, non-deploying validation entry point is `make production-check`. Missing release
evidence produces a non-success incomplete status. `make production-check-local` permits explicit
local skips for diagnostics only and cannot authorize release.

### Final validation evidence — closure owner must update

Recorded exact local command outputs in the 2026-07-14 addendum above. Remaining release closure must
still add artifacts for:

- dependency lock, Ruff format/lint, strict mypy;
- Python unit/property/architecture/security/integration/contract/E2E tests and coverage;
- contract/OpenAPI/workflow validation;
- Alembic history/head/offline SQL and real PostgreSQL upgrade/downgrade/re-upgrade;
- Laravel adapter PHPUnit results;
- secret/dependency/SAST/Terraform/container scans and SBOM;
- Docker build/run/non-root/health;
- Terraform fmt/init/validate/security/plan disposition;
- load smoke environment, task/hardware, p50/p95/p99, error rate, queue age, DB pool, and cost;
- final hygiene/diff/status and no-commit evidence.

Docker/PostgreSQL/live provider checks were unavailable in this local environment. They must remain
blocked/skipped until genuinely executed.

## Security scan results

Repository tests exercise HMAC signature/body binding, timestamp/nonce replay, server-side
key/source/scope grants and signed-claim escalation rejection, key rotation overlap, Meta/Cashfree
raw-body signatures, AES-GCM payloads, route boundaries, production setting rejection, request-body
limits, provider URL allowlisting, and architecture import rules. Final `pip-audit`, SAST, secret
scan, PII-log canary scan, Checkov, container vulnerability scan, SBOM and license inventory results
have not yet been captured from the final working tree. Nothing in this report converts those missing
executions into a pass.

## Docker, Terraform, and workflow validation

- Docker was unavailable locally. The multi-stage image definition is non-root and the Compose app
  profile requests a read-only filesystem, dropped capabilities and bounded resources, but build,
  health, runtime user and vulnerability checks were not executed.
- Terraform was last known to format/validate before later infrastructure edits. The final root and
  environment/module validation and security scan are pending; no target-account plan or apply was
  performed.
- Seven workflows and three composite actions had been structurally parsed during the architecture
  phase, but continued edits require a final validator run. No workflow was executed by GitHub and no
  protected environment/OIDC role was exercised.

## Load-test result and environment

No load test was executed in this environment. `tests/load/locustfile.py` is a test definition, not a
result. There is therefore no evidenced p50/p95/p99, sustained/burst RPS, error rate, queue recovery,
DB pool saturation, ECS task sizing, or cost measurement. Registered-user design capacity is not a
concurrency claim.

## Required secret and account configuration names

Values must be held in approved environment/Secrets Manager configuration, never this report:

- `DATABASE_URL`, `REDIS_URL`, `FIELD_ENCRYPTION_KEY`, `FIELD_ENCRYPTION_KEY_REFERENCE`,
  `AUDIT_HASH_KEY`, `AUDIT_HASH_KEY_REFERENCE`;
- outbound `INTERNAL_SIGNING_KEY_ID`; inbound `INTERNAL_HMAC_KEY_GRANTS` (multiple grants support
  rotation, each binding one key ID/secret to one source and least scopes); issuer, audience, replay
  window;
- AWS region/account deployment variables, SQS URLs, S3 buckets, KMS key, Secrets prefix,
  EventBridge group, OTel endpoint and CloudWatch namespace;
- Lead Intake/outbound base URL, auth/signing key and timeout; Onboarding base URL/shared secret;
  website internal base URL, HMAC key/source/audience/scopes and timeout;
- Google calendar ID, auth mode, delegated user, credential secret ARN and scopes;
- Cashfree environment, app ID, secret key, API version, client timeout, webhook replay window,
  expiry and reconciliation-delay policy;
- SES verified sender/domain and event destinations;
- OpenAI API key, approved model(s), timeouts/retries/token limits and daily/monthly/tenant budgets;
- approved reminder, quiet-hours, hold, confirmation, rate-limit, retry, retention, evaluation/drift,
  discount, consent, content/template, region, alert, SLO, refund/dispute and human-handoff policies.

## Deployment instructions

1. Resolve all no-go items in the readiness report and obtain security/privacy/legal/finance/product/
   operations approval for policy inputs.
2. Install and test the Laravel adapter and aligned scopes at the real Laravel root; deploy canonical
   Lead outbound and Onboarding durable contracts without changing sole Meta ownership.
3. Pass the complete local production gate and stateful dependency/provider sandbox tests.
4. Bootstrap reviewed remote Terraform state/OIDC, populate secrets out-of-band, and produce a
   reviewed target-account plan. Do not apply from this report.
5. Build once, scan/SBOM, push and promote an immutable image digest through protected dev/staging;
   run the one-off migration, health/smoke/synthetic handoff, queue/DB, booking/payment duplicate,
   restore and rollback drills.
6. Implement and verify runtime enforcement for every flag relied on by rollout; several declared
   flags remain configuration-only. Start all external effects off, then canary one capability at a
   time with named approval and monitor correctness, queue, provider, privacy, cost and business
   metrics before production.

## Rollback and disaster recovery

Application rollback uses the protected workflow with a known-good digest and incident reference.
Schema downgrade is not automatic; confirm backward compatibility or deploy a forward fix. Pause the
affected capability and reconcile every potentially accepted remote effect. Procedures are in
[`deployment-rollback.md`](../runbooks/deployment-rollback.md) and
[`disaster-recovery.md`](../runbooks/disaster-recovery.md). Neither procedure has been exercised in a
live environment in this phase.

## Residual risks

- Lead Intake outbound and canonical Onboarding contracts are externally absent/unverified. The
  Onboarding failed-event/human-ticket branch and direct callback-to-request/causation binding remain
  implementation gaps; ambiguous tenant/demo/user order matches now fail closed.
- Website availability and regional membership are not authoritative, blocking automatic scheduling
  and regional operations enablement.
- Cross-system outbox dispatch and payment order/reconciliation need end-to-end PostgreSQL/provider
  proof; aligned Python/Laravel scopes still require installed-host contract evidence.
- Migration `000002` depends on current ORM metadata; later model drift could change historical SQL.
- Runtime abuse controls, complete deletion/subject-request propagation, SES status processing,
  analytics exporter, application metrics, broader model registry/evaluation, and broad failure
  injection remain incomplete or unverified. The guarded operations CLIs are not statefully or
  operationally exercised in this evidence set.
- No Docker image, stateful integration environment, provider sandbox/live account, GitHub workflow,
  AWS plan/apply, backup restore, rollback, DR, or measured load test was executed here.
- Consent, child/guardian safeguards, communications, payment/refund, discounts, retention, regional
  policy, and legal obligations require qualified business/legal review. Code alone is not compliance.

## Git and external-system statement

No Git commit, amend, squash, tag, push, remote, or repository-history change was requested or
performed by this documentation task. No external repository, Laravel deployment, MySQL database,
AWS resource, or provider account was mutated. The closure owner must append the final working-tree
status/diff summary after all implementation edits.
