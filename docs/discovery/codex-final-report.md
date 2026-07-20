# Codex architecture-phase final report

Date: 2026-07-14 (Asia/Calcutta). Scope: historical discovery plus continued local implementation
inside the standalone Demo Command Center Agent repository. This report does not claim production
readiness or live-provider validation.

## 2026-07-20 WhatsApp demo requirement collection addendum

Scope: Demo Command Center internal `whatsapp.handoff.demo.v1` handling after Lead Intake hands off
a demo conversation. The change keeps Lead Intake as the only public Meta ingress/outbound WhatsApp
sender.

Implemented:

- Existing WhatsApp demo conversations are now continued by `tenant_id` + `conversation_id` instead
  of creating a new demo case for every later handoff event.
- Demo requirements are deterministically extracted from text for class, subject/skill, city,
  mode, and preferred time.
- Subject corrections overwrite or clear earlier subjects. In particular, "not Mathematics" no
  longer leaves Mathematics in the durable requirement summary; a replacement such as skating is
  accepted when present.
- Every Demo reply is still emitted as a durable encrypted `outbound.delivery.requested.v1` outbox
  event to Lead Intake, with an event-derived `demo-reply:{event_id}` idempotency key.
- The Makefile type target now runs `uv run python -m mypy src tests`, which avoids a Windows `uv`
  script-path canonicalization failure in this workspace path.

Local evidence from 2026-07-20:

- `uv run ruff format --check src tests scripts`: 185 files formatted.
- `uv run ruff check src tests scripts`: all checks passed.
- `uv run python -m mypy src tests`: success over 180 source files.
- `uv run python scripts/validate_contracts.py`: contracts valid, 10 schemas, 12 JSON files, 2 YAML
  files, 21 OpenAPI operations.
- `uv run python scripts/validate_workflows.py`: workflows valid, 7 workflows, 3 actions, 51 job
  steps.
- `uv run python scripts/validate_production_hygiene.py`: production hygiene valid, 148 Python files
  inspected.
- `uv run python scripts/validate_migrations.py`: migrations valid, 3 revisions, head
  `20260713_000003`.
- `uv run pytest --cov=demo_command_center --cov-report=term-missing`: 189 passed, 82.99% coverage.

Notes:

- The Windows host does not have `make` installed, so the Makefile-equivalent commands were run
  manually in order.
- The repository `.env` contains dev/live capability flags; it was temporarily hidden during the
  settings/test gate and restored afterward so default settings tests were not polluted by local
  dev configuration.
- No live AWS/provider deployment was performed in this local implementation pass.
- No Git commit, tag, push, or history change was made.

## Implementation continuation addendum

The remainder of this file is the historical architecture-phase snapshot, including its original
tree, 27-test result, and then-outstanding implementation list. It must not be read as the final state
of the continued implementation.

The continued work added deterministic capability policies, expanded the PostgreSQL metadata to 46
owned tables and a second Alembic revision, durable authenticated/encrypted ingress processing,
server-side inbound HMAC key/source/scope grants, provider clients, a canonical paid-to-Onboarding
request/accepted/completed slice with non-consuming pause controls, a substantially complete private
Laravel adapter package, AWS Terraform and workflow definitions, production runbooks, and on
2026-07-14 a safe Laravel `register.phone` recipient-resolution contract plus teacher-first Google
Meet scheduling coordinator. The final continuation also added adapter-scoped NXTutor MySQL
placeholder env names, configurable Laravel legacy table mappings, and an API-only Lambda HTTP
handler for FastAPI.

Final local evidence from 2026-07-14:

- 184 Python tests passed with 83.24% coverage.
- Strict mypy passed over 178 files.
- Contracts valid: 10 schemas, 12 JSON files, 2 YAML files, 21 OpenAPI operations.
- Workflows valid: 7 workflows, 3 composite actions, 50 job steps.
- Production hygiene valid: 148 Python files inspected.
- Migrations valid: 3 revisions, head `20260713_000003`.
- Laravel adapter PHPUnit passed 20 tests and 95 assertions.
- Terraform fmt plus dev/staging/prod local init/validate passed.
- `production_check.py --allow-skips` reported 15 passed, 0 failed, 9 skipped, overall PARTIAL.
- Strict `production_check.py` reported the same 15/0/9 summary and exited nonzero as INCOMPLETE.

Current evidence and disposition are maintained in:

- [`codex-database-config-correction-report.md`](codex-database-config-correction-report.md) for the
  Laravel/MySQL `register` ownership and safe gateway projection;
- [`../operations/requirement-traceability-matrix.md`](../operations/requirement-traceability-matrix.md)
  for loops 0-23 and gates A-J;
- [`../operations/production-readiness-report.md`](../operations/production-readiness-report.md) for
  the no-go/closure decision;
- [`../operations/codex-final-implementation-report.md`](../operations/codex-final-implementation-report.md)
  for the implementation handoff.

Production remains unapproved at this evidence point. Docker/PostgreSQL and live credentials were
unavailable; no provider/AWS live validation occurred; the inspected Lead Intake service does not
implement the internal outbound WhatsApp endpoint targeted by this client; Onboarding remains on a
legacy compatibility contract; and the Laravel adapter is not installed in the website deployment.
The original no-commit/no-push instruction remains binding.

## Repositories inspected

| System | Detected Git root | Branch | Inspected commit | Final local status |
|---|---|---|---|---|
| NXTutors website | `E:\NX Tutor\Nxtutors Website\public` | `main` | `61b3db6be534fa16fa12dbb6745bd4bd5482cca2` | Clean |
| Lead Intake Agent | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\nxtutors-lead-intake-agent` | `main` | `c52950198d6ced38e37ab8f0f81976c04770b7a9` | Clean |
| WhatsApp Onboarding Agent | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\Onbording agent` | `main` | `8e867531f768a916cb9df33c7a10f2b10e3aa4c1` | Clean |
| New architecture repository | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\Demo Command Center Agent\demo-command-center-agent` | Not initialized | Not applicable | No Git repository created |

The website root is genuinely the folder named `public`: it contains `artisan`, `composer.json`, `app/`, `routes/`, `database/`, and `config/`; its actual web document root is the nested `public/`. The new service is outside it. The editor's second displayed attachment under `a0c63cf0-3425-4b47-9bd1-4acd3d095e6c` was absent and is `UNVERIFIED`.

## Verified findings

- The website uses PHP `^8.2`, Laravel `^12`, Spatie permissions, MySQL in its example configuration, database queue/cache defaults, a legacy `register` identity path, and current roles including `super_admin` and `sub_admin`. No region-membership model was found.
- `POST /demo-lead/store` is a capture-only website flow. The page exposes plural board/class/subject selections while its serializer/controller expects singular fields, creating a verified data-loss mismatch. The subsequent `wa.me` browser action is not a durable handoff.
- Website tutor/course data is split across incompatible models and no authoritative working-hours, leave, exception, or bookable-availability model was found. A displayed availability score is a placeholder, not scheduling authority.
- The current website Cashfree return handler performs server status lookup and can activate a subscription; the signed webhook only logs. Durable webhook deduplication, canonical payment records, replay protection, and exactly-once activation were not found.
- Lead Intake owns the public Meta webhook and outbound WhatsApp sending. It verifies signatures when configured, deduplicates Meta message IDs in PostgreSQL, and uses cache send suppression. Its onboarding handoff is a shared-secret, flat, versionless payload with raw PII and no canonical tenant/actor/correlation/idempotency envelope.
- No durable, authoritative implementation for Meta's 24-hour service window or template selection was found in Lead Intake.
- Onboarding has a deterministic Laravel state machine, queue/cache/privacy/health scaffolding, and a shared-secret internal route that returns `reply_text`. That internal controller does not establish a durable canonical inbox or prove execution of the full persisted orchestration before replying. Its separate Meta compatibility path must remain unsubscribed for the shared number.
- No live credentials, provider endpoints, deployed commit, AWS account, or production data were exercised.

Detailed evidence is in the other files under `docs/discovery/`.

## Architecture decisions delivered

- A single Python 3.12 FastAPI modular monolith with clean/hexagonal boundaries and separate API, worker, scheduled/evaluation, and CLI process types; not eight microservices.
- Lead Intake remains the only public Meta ingress and outbound decision owner. Demo Command Center accepts authenticated, idempotent internal handoffs; Onboarding receives a paid/approved canonical handoff.
- Laravel/MySQL remains authoritative for existing users, tutors, plans, orders, and subscriptions. Demo lifecycle state belongs to Aurora PostgreSQL. Cross-system changes use a thin authenticated Laravel gateway and outbox, not arbitrary MySQL writes.
- Deterministic state transitions, PostgreSQL constraints, durable inbox/outbox, scoped idempotency, EventBridge scheduling, SQS/DLQs, Redis as a non-authoritative accelerator, and explicit saga compensations.
- Demo-conversion payment orchestration is owned here; only a verified Cashfree callback or authenticated reconciliation can transition to paid. Website activation is an idempotent gateway operation. Browser return and WhatsApp claims are non-authoritative.
- Google Calendar uses an NXTutors-controlled organizer, least scopes, stable operation IDs, unique conference request IDs, and one Meet conference per unrelated demo.
- LLM work is optional, redacted, schema-bound, budgeted, policy-validated data processing. It cannot authorize state, sends, slots, calendar actions, payments, discounts, SQL, or URLs.
- Production configuration rejects local/fake provider profiles, missing core dependencies, unsafe automatic discounts, and enabled capabilities without their required credentials/policies. Provider callbacks fail closed until durable adapters exist. Production docs/OpenAPI are not mounted.
- AWS modules cover network, ALB/WAF/DNS/ACM, ECR/ECS, API/worker/evaluation tasks and autoscaling, Aurora/RDS Proxy, Redis, queues/DLQs, EventBridge Scheduler, S3, SES, Secrets Manager/KMS/IAM/OIDC, observability, and Glue/Athena. Values and thresholds remain environment inputs.
- Immutable-image GitHub workflow scaffolds build once, promote by digest, run migrations, update ECS, smoke test, and restore previous task definitions on failure.

The twelve binding decisions are recorded in `docs/adr/ADR-001` through `ADR-012`.

## Exact repository tree

The following tree excludes generated/ignored local state (`.venv`, Python/tool caches, coverage files, and Terraform `.terraform` provider cache) but includes every source-controlled blueprint file.

```text
demo-command-center-agent/
|-- .github/
|   |-- actions/
|   |   |-- build-image/
|   |   |   `-- action.yml
|   |   |-- ecs-deploy/
|   |   |   `-- action.yml
|   |   `-- setup-python/
|   |       `-- action.yml
|   `-- workflows/
|       |-- ci.yml
|       |-- deploy-dev.yml
|       |-- deploy-prod.yml
|       |-- deploy-staging.yml
|       |-- rollback.yml
|       |-- security.yml
|       `-- terraform-plan.yml
|-- contracts/
|   |-- cashfree/
|   |   `-- payment-webhook-normalized.v1.schema.json
|   |-- events/
|   |   |-- agent-event-envelope.v1.schema.json
|   |   |-- example.whatsapp-handoff-demo.v1.json
|   |   |-- onboarding-paid-user-requested.v1.schema.json
|   |   `-- whatsapp-handoff-demo.v1.schema.json
|   |-- google_calendar/
|   |   `-- calendar-operation.v1.schema.json
|   |-- lead_intake/
|   |   `-- legacy-handoff-v0.schema.json
|   |-- meta/
|   |   `-- README.md
|   |-- onboarding/
|   |   `-- handoff-acknowledgement.v1.schema.json
|   |-- openapi/
|   |   `-- internal-api.v1.yaml
|   `-- website/
|       `-- website-gateway.v1.yaml
|-- docs/
|   |-- adr/
|   |   |-- ADR-001-modular-monolith.md
|   |   |-- ADR-002-single-whatsapp-ingress.md
|   |   |-- ADR-003-database-and-data-ownership.md
|   |   |-- ADR-004-inbox-outbox-idempotency.md
|   |   |-- ADR-005-payment-ownership.md
|   |   |-- ADR-006-google-calendar-identity.md
|   |   |-- ADR-007-llm-boundaries.md
|   |   |-- ADR-008-state-machine-and-sagas.md
|   |   |-- ADR-009-cache-and-locking.md
|   |   |-- ADR-010-analytics-and-pii.md
|   |   |-- ADR-011-aws-runtime.md
|   |   `-- ADR-012-deployment-and-rollback.md
|   |-- api/
|   |   `-- README.md
|   |-- architecture/
|   |   |-- agent-harmony.md
|   |   |-- capability-map.md
|   |   |-- container-and-component-model.md
|   |   |-- demo-state-machine.md
|   |   |-- deployment-topology.md
|   |   |-- failure-modes.md
|   |   |-- module-dependency-rules.md
|   |   |-- payment-saga.md
|   |   |-- problem-definition.md
|   |   |-- README.md
|   |   |-- scheduling-saga.md
|   |   `-- system-context.md
|   |-- compliance/
|   |   `-- README.md
|   |-- cost/
|   |   |-- aws-cost-controls.md
|   |   |-- capacity-model.md
|   |   `-- token-and-provider-budgets.md
|   |-- data/
|   |   |-- analytics-data-contract.md
|   |   |-- canonical-data-model.md
|   |   |-- data-ownership.md
|   |   |-- identity-mapping.md
|   |   `-- retention-and-deletion.md
|   |-- discovery/
|   |   |-- assumptions-and-unverified-items.md
|   |   |-- codex-final-report.md
|   |   |-- current-system-inventory.md
|   |   |-- integration-gaps.md
|   |   |-- lead-intake-findings.md
|   |   |-- onboarding-findings.md
|   |   |-- repository-tree.txt
|   |   |-- website-data-model.md
|   |   `-- website-demo-flow.md
|   |-- integration/
|   |   |-- cashfree.md
|   |   |-- email.md
|   |   |-- event-envelope.md
|   |   |-- google-calendar-meet.md
|   |   |-- lead-intake-contract.md
|   |   |-- meta-whatsapp.md
|   |   |-- onboarding-contract.md
|   |   `-- website-gateway.md
|   |-- model/
|   |   |-- evaluation-and-drift.md
|   |   |-- forecasting-design.md
|   |   `-- objection-extraction-design.md
|   |-- operations/
|   |   |-- feature-flags-and-kill-switches.md
|   |   |-- observability.md
|   |   |-- rollback-triggers.md
|   |   `-- slos-and-slas.md
|   |-- privacy/
|   |   |-- consent-model.md
|   |   |-- logging-and-redaction.md
|   |   `-- pii-data-map.md
|   |-- prompts/
|   |   `-- README.md
|   |-- runbooks/
|   |   `-- README.md
|   |-- security/
|   |   |-- abuse-and-rate-limiting.md
|   |   |-- authorization-model.md
|   |   |-- incident-response.md
|   |   |-- secrets-and-key-rotation.md
|   |   |-- threat-model.md
|   |   `-- trust-boundaries.md
|   `-- testing/
|       `-- README.md
|-- infra/
|   |-- alarms/
|   |   `-- README.md
|   |-- dashboards/
|   |   `-- README.md
|   |-- glue/
|   |   `-- README.md
|   `-- terraform/
|       |-- environments/
|       |   |-- dev/
|       |   |   `-- README.md
|       |   |-- prod/
|       |   |   `-- README.md
|       |   `-- staging/
|       |       `-- README.md
|       |-- modules/
|       |   |-- alb/
|       |   |   `-- main.tf
|       |   |-- aurora/
|       |   |   `-- main.tf
|       |   |-- dns_acm/
|       |   |   `-- main.tf
|       |   |-- ecr/
|       |   |   `-- main.tf
|       |   |-- ecs/
|       |   |   `-- main.tf
|       |   |-- eventbridge/
|       |   |   `-- main.tf
|       |   |-- github_oidc/
|       |   |   `-- main.tf
|       |   |-- glue_athena/
|       |   |   `-- main.tf
|       |   |-- iam/
|       |   |   `-- main.tf
|       |   |-- kms/
|       |   |   `-- main.tf
|       |   |-- network/
|       |   |   `-- main.tf
|       |   |-- observability/
|       |   |   `-- main.tf
|       |   |-- rds_proxy/
|       |   |   `-- main.tf
|       |   |-- redis/
|       |   |   `-- main.tf
|       |   |-- s3/
|       |   |   `-- main.tf
|       |   |-- secrets/
|       |   |   `-- main.tf
|       |   |-- ses/
|       |   |   `-- main.tf
|       |   |-- sqs/
|       |   |   `-- main.tf
|       |   |-- waf/
|       |   |   `-- main.tf
|       |   `-- README.md
|       |-- .terraform.lock.hcl
|       |-- main.tf
|       |-- README.md
|       |-- variables.tf
|       `-- versions.tf
|-- integrations/
|   `-- nxtutors-laravel-adapter/
|       |-- app/
|       |   `-- Http/
|       |       |-- Controllers/
|       |       |   |-- PlanQuoteController.php
|       |       |   `-- SubscriptionActivationController.php
|       |       `-- Middleware/
|       |           `-- VerifyInternalService.php
|       |-- config/
|       |   `-- demo_command_center.php
|       |-- database/
|       |   `-- migrations/
|       |       `-- 2026_07_13_000001_create_demo_integration_tables.php
|       |-- routes/
|       |   `-- api.php
|       |-- tests/
|       |   `-- Feature/
|       |       `-- GatewayFailsClosedTest.php
|       |-- composer.json
|       `-- README.md
|-- migrations/
|   |-- versions/
|   |   `-- 20260713_000001_initial_operational_core.py
|   |-- env.py
|   |-- README.md
|   `-- script.py.mako
|-- scripts/
|   |-- README.md
|   |-- validate_contracts.py
|   `-- validate_workflows.py
|-- src/
|   `-- demo_command_center/
|       |-- analytics/
|       |   |-- events/
|       |   |   `-- README.md
|       |   |-- exports/
|       |   |   `-- README.md
|       |   |-- quality/
|       |   |   `-- README.md
|       |   `-- regional/
|       |       `-- README.md
|       |-- api/
|       |   |-- dependencies/
|       |   |   |-- __init__.py
|       |   |   |-- auth.py
|       |   |   `-- container.py
|       |   |-- errors/
|       |   |   |-- __init__.py
|       |   |   `-- taxonomy.py
|       |   |-- middleware/
|       |   |   |-- __init__.py
|       |   |   `-- correlation.py
|       |   |-- openapi/
|       |   |   `-- README.md
|       |   |-- routes/
|       |   |   |-- __init__.py
|       |   |   |-- health.py
|       |   |   |-- internal.py
|       |   |   `-- providers.py
|       |   |-- schemas/
|       |   |   |-- __init__.py
|       |   |   `-- ingress.py
|       |   `-- __init__.py
|       |-- bootstrap/
|       |   |-- __init__.py
|       |   |-- application_factory.py
|       |   |-- dependency_container.py
|       |   `-- lifecycle.py
|       |-- cache/
|       |   |-- circuit_breakers/
|       |   |   `-- README.md
|       |   |-- keys/
|       |   |   |-- __init__.py
|       |   |   `-- policy.py
|       |   |-- locks/
|       |   |   `-- README.md
|       |   |-- rate_limits/
|       |   |   `-- README.md
|       |   `-- redis/
|       |       `-- README.md
|       |-- cli/
|       |   |-- __init__.py
|       |   |-- doctor.py
|       |   |-- evaluate_drift.py
|       |   |-- reconcile_payments.py
|       |   |-- redrive_dlq.py
|       |   |-- replay_event.py
|       |   `-- retention_cleanup.py
|       |-- compliance/
|       |   |-- audit/
|       |   |   `-- README.md
|       |   |-- business/
|       |   |   `-- README.md
|       |   |-- communications/
|       |   |   `-- README.md
|       |   `-- meta/
|       |       `-- README.md
|       |-- config/
|       |   |-- feature_flags.py
|       |   |-- policy_loader.py
|       |   |-- settings.py
|       |   `-- validation.py
|       |-- cost_control/
|       |   |-- budgets/
|       |   |   |-- __init__.py
|       |   |   `-- port.py
|       |   |-- circuit_breakers/
|       |   |   `-- README.md
|       |   |-- provider_usage/
|       |   |   `-- README.md
|       |   `-- token_usage/
|       |       `-- README.md
|       |-- evaluation/
|       |   |-- drift/
|       |   |   `-- README.md
|       |   |-- models/
|       |   |   `-- README.md
|       |   |-- performance/
|       |   |   `-- README.md
|       |   `-- prompts/
|       |       `-- README.md
|       |-- glue/
|       |   |-- envelopes/
|       |   |   |-- __init__.py
|       |   |   `-- agent_event.py
|       |   |-- lead_intake/
|       |   |   `-- README.md
|       |   |-- onboarding/
|       |   |   `-- README.md
|       |   |-- outbound_gateway/
|       |   |   `-- README.md
|       |   |-- routing/
|       |   |   `-- README.md
|       |   |-- website/
|       |   |   `-- README.md
|       |   `-- __init__.py
|       |-- guardrails/
|       |   |-- business_policy/
|       |   |   `-- README.md
|       |   |-- input/
|       |   |   `-- README.md
|       |   |-- output/
|       |   |   `-- README.md
|       |   `-- tool_policy/
|       |       `-- README.md
|       |-- infrastructure/
|       |   |-- database/
|       |   |   |-- migrations_support/
|       |   |   |   `-- README.md
|       |   |   |-- models/
|       |   |   |   |-- __init__.py
|       |   |   |   `-- operational.py
|       |   |   |-- repositories/
|       |   |   |   `-- README.md
|       |   |   |-- unit_of_work/
|       |   |   |   `-- README.md
|       |   |   |-- __init__.py
|       |   |   `-- base.py
|       |   |-- idempotency/
|       |   |   `-- README.md
|       |   |-- inbox/
|       |   |   `-- README.md
|       |   |-- outbox/
|       |   |   `-- README.md
|       |   |-- queues/
|       |   |   `-- README.md
|       |   |-- scheduler/
|       |   |   `-- README.md
|       |   |-- secrets/
|       |   |   `-- README.md
|       |   |-- storage/
|       |   |   `-- README.md
|       |   `-- __init__.py
|       |-- integrations/
|       |   |-- amazon_ses/
|       |   |   `-- README.md
|       |   |-- aws/
|       |   |   `-- README.md
|       |   |-- cashfree/
|       |   |   `-- README.md
|       |   |-- google_calendar/
|       |   |   `-- README.md
|       |   |-- lead_intake/
|       |   |   `-- README.md
|       |   |-- meta_whatsapp/
|       |   |   `-- README.md
|       |   |-- nxtutors_website/
|       |   |   `-- README.md
|       |   |-- onboarding/
|       |   |   `-- README.md
|       |   `-- openai/
|       |       `-- README.md
|       |-- memory/
|       |   |-- conversation/
|       |   |   `-- README.md
|       |   |-- retention/
|       |   |   `-- README.md
|       |   |-- retrieval/
|       |   |   `-- README.md
|       |   `-- summaries/
|       |       `-- README.md
|       |-- modules/
|       |   |-- communications/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- demo_core/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   |-- __init__.py
|       |   |   |   `-- identifiers.py
|       |   |   |-- ports/
|       |   |   |   |-- __init__.py
|       |   |   |   `-- gateways.py
|       |   |   `-- __init__.py
|       |   |-- discount_suggestions/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- human_handoff/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- objection_extraction/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- paid_transition/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- post_demo_conversion/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- regional_monitoring/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- reminders/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- scheduling/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- success_forecasting/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   |-- tutor_matching/
|       |   |   |-- application/
|       |   |   |   `-- README.md
|       |   |   |-- domain/
|       |   |   |   `-- README.md
|       |   |   |-- ports/
|       |   |   |   `-- README.md
|       |   |   `-- __init__.py
|       |   `-- __init__.py
|       |-- observability/
|       |   |-- health/
|       |   |   `-- README.md
|       |   |-- logging/
|       |   |   |-- __init__.py
|       |   |   `-- redaction.py
|       |   |-- metrics/
|       |   |   `-- README.md
|       |   `-- tracing/
|       |       `-- README.md
|       |-- privacy/
|       |   |-- analytics_sanitization/
|       |   |   `-- README.md
|       |   |-- consent/
|       |   |   `-- README.md
|       |   |-- deletion/
|       |   |   `-- README.md
|       |   |-- pii/
|       |   |   `-- README.md
|       |   `-- retention/
|       |       `-- README.md
|       |-- resilience/
|       |   |-- bulkheads/
|       |   |   `-- README.md
|       |   |-- circuit_breakers/
|       |   |   |-- __init__.py
|       |   |   `-- port.py
|       |   |-- fallbacks/
|       |   |   `-- README.md
|       |   |-- retries/
|       |   |   `-- README.md
|       |   `-- timeouts/
|       |       `-- README.md
|       |-- security/
|       |   |-- abuse_controls/
|       |   |   `-- README.md
|       |   |-- authentication/
|       |   |   `-- README.md
|       |   |-- authorization/
|       |   |   `-- README.md
|       |   |-- encryption/
|       |   |   `-- README.md
|       |   |-- replay_protection/
|       |   |   `-- README.md
|       |   `-- signatures/
|       |       |-- __init__.py
|       |       `-- webhook.py
|       |-- state/
|       |   |-- guards/
|       |   |   `-- README.md
|       |   |-- machine/
|       |   |   |-- __init__.py
|       |   |   `-- demo_state.py
|       |   |-- persistence/
|       |   |   `-- README.md
|       |   |-- transitions/
|       |   |   |-- __init__.py
|       |   |   |-- README.md
|       |   |   `-- table.py
|       |   `-- __init__.py
|       |-- workers/
|       |   |-- analytics/
|       |   |   `-- README.md
|       |   |-- human_handoff/
|       |   |   `-- README.md
|       |   |-- inbound/
|       |   |   `-- README.md
|       |   |-- model_evaluation/
|       |   |   `-- README.md
|       |   |-- outbound/
|       |   |   `-- README.md
|       |   |-- payments/
|       |   |   `-- README.md
|       |   |-- reminders/
|       |   |   `-- README.md
|       |   |-- scheduling/
|       |   |   `-- README.md
|       |   |-- __init__.py
|       |   `-- __main__.py
|       |-- __init__.py
|       `-- main.py
|-- tests/
|   |-- architecture/
|   |   |-- test_database_metadata.py
|   |   |-- test_dependency_rules.py
|   |   `-- test_route_boundaries.py
|   |-- chaos/
|   |   `-- README.md
|   |-- contract/
|   |   `-- test_event_example.py
|   |-- e2e/
|   |   `-- README.md
|   |-- fakes/
|   |   `-- README.md
|   |-- fixtures/
|   |   `-- README.md
|   |-- integration/
|   |   `-- test_application_health.py
|   |-- load/
|   |   `-- locustfile.py
|   |-- property/
|   |   `-- README.md
|   |-- security/
|   |   `-- test_webhook_signatures.py
|   |-- unit/
|   |   |-- test_cache_keys.py
|   |   |-- test_doctor.py
|   |   |-- test_event_envelope.py
|   |   |-- test_settings.py
|   |   `-- test_state_transitions.py
|   `-- conftest.py
|-- tools/
|   `-- README.md
|-- .dockerignore
|-- .editorconfig
|-- .env.example
|-- .gitignore
|-- .pre-commit-config.yaml
|-- AGENTS.md
|-- alembic.ini
|-- CHANGELOG.md
|-- CODEOWNERS
|-- CONTRIBUTING.md
|-- docker-compose.local.yml
|-- Dockerfile
|-- LICENSE
|-- Makefile
|-- pyproject.toml
|-- README.md
|-- SECURITY.md
`-- uv.lock
```

## Validation commands and final results

| Check | Command or method | Result |
|---|---|---|
| Repository identity | `git rev-parse`, `git branch --show-current`, `git rev-parse HEAD`, `git status --short`, `git remote get-url origin` in each source | Roots/SHAs above; all three source worktrees clean |
| Runtime | `python --version`; `python -m uv --version` | Python 3.12.10; uv 0.5.18 |
| Reproducible lock | `python -m uv lock --check`; `uv sync --frozen --all-extras` | 144-package lock current; environment synchronized |
| Import/start boundary | Import `demo_command_center.main`; application health tests with lifespan | Imported; local app and three health routes passed |
| Format/lint | `ruff format --check src tests scripts`; `ruff check src tests scripts` | 88 files formatted; all checks passed |
| Strict typing | `mypy src tests` | Success, 86 source files |
| Tests/coverage | `pytest --cov=demo_command_center --cov-report=term-missing` | 27 passed; 85.86% branch-aware coverage; required 80% met |
| Contracts | `python scripts/validate_contracts.py` | JSON Schemas structurally valid; canonical example passes JSON Schema and Pydantic; OpenAPI/YAML parses |
| GitHub YAML | `python scripts/validate_workflows.py` | 7 workflows and 3 composite actions parse and meet structural requirements |
| Migrations | `alembic history`; `alembic heads`; `alembic upgrade head --sql` | One head (`20260713_000001`); PostgreSQL offline SQL generation succeeded |
| Terraform | `terraform fmt -check -recursive`; `terraform validate` at root; standalone init/validate for all 19 child modules using the locked provider mirror | Formatted; root and every child module valid with Terraform 1.15.2; no apply performed |
| Provider status | `demo-command-doctor` | All nine dependency/provider checks report configuration=false, connection=false, sandbox=false, live=false; no false success |
| Secret/readiness scan | `rg` patterns for AWS/session tokens, private keys, account IDs, and unfinished-work markers | No matches outside the dependency lock/cache exclusions |
| Docker | `Get-Command docker` | Docker command unavailable; image and Compose builds were not run |
| Existing-source mutation | Final `git status --short` in all inspected repositories | Clean; no accidental code under the Laravel repository/webroot |

The checks validate a compileable architecture scaffold, not implemented business behavior or provider connectivity. GitHub Actions were syntax-checked locally but not executed by GitHub. Terraform was validated but not planned against an AWS account.

## Remaining implementation work for Claude

1. Implement each application use case and full normalized SQLAlchemy model/migration set described in `docs/data/canonical-data-model.md`, including exclusion/partial indexes, encryption/blind indexes, retention, deletion, and concurrency tests.
2. Implement PostgreSQL repositories/unit of work, transaction inbox/outbox dispatchers, SQS consumers with visibility extension/poison handling, EventBridge scheduling, Redis locks/rate limits/circuits, graceful worker shutdown, audit hash chaining, and redrive/replay CLIs.
3. Implement short-lived JWT or key-ID HMAC service authentication, nonce/replay storage, request size/content-type controls, fixed provider URL allowlists, scoped authorization, and approved regional membership mapping.
4. Implement the Laravel gateway package in the actual website repository after review: tutor search/snapshots, quotes, idempotent activation, signed events/outbox, authorization claims, CSRF for browser paths, and compatibility tests. Do not copy it into the nested public document directory.
5. Upgrade Lead Intake to emit/accept the canonical envelope, classify demo intent, preserve its single Meta subscription, durably own the service window/template decision, and route all outbound sends through exactly-once operations.
6. Upgrade Onboarding to consume the paid-user event through a durable inbox and execute its persisted flow while returning replies through Lead Intake; disable its direct Meta subscription/sender for the shared number.
7. Implement Google free/busy/event/Meet, SES, Cashfree, website, onboarding, Meta gateway, OpenAI, and AWS adapters behind the ports, with retries only for safe operations, reconciliation, sandbox contract tests, and explicit provider-version fixtures.
8. Implement scheduling/matching/reminders/outcomes/objections/conversion/offers/payments/human tickets and their saga compensations. Populate approved policies, content, consent, quiet hours, templates, discounts, pricing, SLAs, and retention only after owner approval.
9. Build the point-in-time training pipeline, calibrated baseline, registry/promotion, fairness review, shadow evaluation, drift monitoring, rollback, and deterministic score fallback. No numeric forecast may come from free-form LLM output.
10. Compose stateful dev/staging/prod Terraform backends and approved values, add queue-depth/age scaling policies from measured load, plan in the target AWS account, pass Checkov, establish DNS/certificates/SES/alarms/budgets/backups, and exercise restore/rollback.
11. Run Linux container/Compose builds, vulnerability/SBOM/license checks, PostgreSQL/Redis/LocalStack integration tests, Laravel contract tests, provider sandboxes, end-to-end/property/concurrency/load/chaos tests, and GitHub environment promotion/rollback drills.
12. Write and exercise operational runbooks, data-access/deletion flows, credential rotation, payment reconciliation, PII incident response, DLQ triage, model rollback, and named on-call/escalation ownership.

## Known risks

- The inspected commits may differ from deployed production revisions; live infrastructure and provider settings are `UNVERIFIED`.
- Website demo-form field loss, absent authoritative availability, incompatible tutor-course models, and missing region membership block safe automated matching/scheduling and regional authorization.
- Existing website payment activation is not durably webhook-led; enabling Demo Command Center payments before canonical ownership and exactly-once gateway activation would risk mismatch or duplicate subscription effects.
- Lead Intake's current flat handoff contains raw PII and lacks the canonical version/idempotency context. Its cache suppression is not proof of exactly-once outbound delivery.
- Onboarding's internal reply path does not yet prove durable completion; direct Meta compatibility code creates duplicate-response risk if subscribed.
- Child/guardian consent, approved messages/templates/social proof, price/margin/discount rules, payment disputes/refunds, retention, regional alert policy, and operational ownership are not approved in inspected code.
- Terraform modules have not been planned/applied in a real AWS environment, workflows have not run on GitHub, and Docker was unavailable locally.
- Empty adapter directories are intentionally represented by ownership READMEs; provider-backed operations return disabled/not-found or unavailable, never fake success.

## Configuration and evidence required later

- Application identity/version, tenant and environment references, HTTPS public/internal URLs, timezone policy, and approved feature-flag owners.
- Aurora/RDS Proxy and Redis secret references/pool/timeouts; AWS region/account deployment variable; VPC/DNS/ACM/subnets; queue/bucket/schedule/log/OTel references; KMS/Secrets Manager/IAM/OIDC; backup/retention/cost tags.
- Lead Intake, Onboarding, outbound gateway, and website internal endpoints; auth mode, issuer/audience/key IDs, rotated secret/key references, replay window, scopes, and identity/region mapping.
- Meta app/number ownership, app secret/token references, API version, permitted templates/languages/categories, service-window source, opt-out policy, and verified webhook routing.
- NXTutors Google Workspace organizer/delegated identity, calendar ownership, least scopes, credential federation/secret reference, external-attendee policy, Meet licensing, retention, and rotation.
- Cashfree environment/app secret references, pinned API version, webhook configuration/replay window, order purpose/expiry, currency/amount/plan/offer binding, refunds/disputes, and reconciliation ownership.
- SES verified identities/domain, production access, suppression/bounce/complaint routing, consent policy, and sender configuration.
- OpenAI approved models supplied by environment, task allowlist, prompt registry/evaluation versions, redaction, token/retry/depth limits, daily/monthly/tenant budgets, and fallback policy.
- Authoritative tutor schedules/exceptions/buffers, learner/tutor timezone rules, reminder/quiet-hour/confirmation/hold policies, pricing/margins/discount approval bands, approved content, minimum samples, alert thresholds/owners, SLOs, retention/deletion, and human-ticket SLAs.

## Git statement

No Git commit, amend, squash, tag, push, branch, remote, credential, or history change was made. The three inspected repositories remained clean. The new folder was intentionally not initialized as a Git repository, so no commit exists for this phase.

## 2026-07-20 deployment-response addendum

- Fixed the Demo Command Center WhatsApp reply recipient selection so Lead Intake receives a WhatsApp-addressable actor phone when available, while conversation_id remains the durable session key.
- Evidence: uff check src tests scripts passed; full pytest -q passed with 190 tests.
- make check could not run in this Windows shell because make is not installed; the underlying lint and test commands were executed directly.

## 2026-07-20 tutor-shortlist addendum

- Wired completed WhatsApp demo requirements to the configured NXTutors website gateway so the worker fetches authoritative tutor candidates, stores durable shortlist rows, transitions the demo state to tutor matching/shortlisted, and replies with safe tutor options instead of stopping at “verify suitable tutor options.”
- Fixed the website gateway client to accept the Laravel adapter’s paginated `data.items` candidate response shape.
- Added regression coverage for Laravel candidate projection parsing and the requirement-complete WhatsApp shortlist path.
- Evidence: `.venv\Scripts\python.exe -m ruff check src tests scripts` passed; `.venv\Scripts\python.exe -m pytest -q` passed with 192 tests.
- `make check` still could not run in this Windows shell because `make` is not installed; the equivalent lint and test commands were executed directly.

## 2026-07-20 website-gateway live addendum

- Installed and deployed the Laravel Demo Command Center gateway into the live NXTutors website repository so the AWS Demo Command Center can query the authoritative MySQL website tables through signed internal routes.
- Verified the deployed route exists and is protected: unsigned tutor candidate request returned `401` instead of `404`.
- Verified a signed tutor candidate request against `https://www.nxtutors.com/internal/api/v1/demo-command-center/tutors/candidates` returned `200` from the live website gateway when sent with a stable service User-Agent.
- Fixed the Demo Command Center website gateway client to send `NXtutors-Demo-Command-Center/1.0 (+https://demo.nxtutors.com)` because Cloudflare returned Error 1010 for default programmatic client fingerprints.
- Evidence: website deployment run `29736801498` succeeded; `.venv\Scripts\python.exe -m pytest tests/unit/test_website_gateway_client.py -q` passed with 2 tests.

## 2026-07-20 demo-agent live-flow addendum

- Fixed WhatsApp requirement parsing so messages such as `7th class Gurgaon` are interpreted as `Class 7` plus location `Gurugram`; the city is no longer mistaken for the class value.
- Improved the Laravel website tutor projection used by the signed gateway: tutor discovery now searches `register.city`, `register.district`, and `register.state`; treats `Gurgaon` and `Gurugram` as aliases; normalizes Math/Maths/Mathematics and class/mode values; and can use safe register-table fallback course hints when a teacher has no linked course rows.
- This keeps teacher identity and phone resolution anchored to the website `register` table. The selected tutor reference remains the website `register.id`, so subsequent tutor acceptance/phone lookup targets the chosen teacher row.
- Evidence: `.venv\Scripts\python.exe -m ruff check src tests` passed; `.venv\Scripts\python.exe -m pytest tests\unit -q` passed with 151 tests; `php -l` passed for the Laravel adapter file in both the DCC repository and live website repository; `php artisan route:list --path=internal/api/v1/demo-command-center` shows the protected tutor/phone/profile gateway routes.
- Local Laravel adapter PHPUnit execution is blocked on this workstation because PHP has `pdo_mysql` but not `pdo_sqlite`; the failure is `could not find driver` before any test assertions run.
- `make check` still could not run in this Windows shell because `make` is not installed; the equivalent underlying checks were executed directly.
