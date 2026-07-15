# Production readiness report

Date: 2026-07-14 (Asia/Calcutta)  
Decision: **NO-GO for production at this evidence point**

## 2026-07-15 continuation evidence

Disposition remains **NO-GO for production**, but two code-controlled safety blockers and one Dev
deployment workflow blocker were closed:

- Demo Command Center now always rejects `META_DIRECT_WEBHOOK_ENABLED=true`, preserving Lead Intake
  as the canonical public Meta ingress.
- Demo Command Center now rejects active direct Meta outbound mode when unpaused; outbound delivery
  must go through the canonical Lead Intake gateway.
- `.github/workflows/deploy-dev.yml` now skips push-to-main deployment unless
  `DEPLOY_DEV_ENABLED=true`; manual dispatch and enabled push deployments run a preflight job that
  validates required config names without printing secret values.

Validation evidence from this pass:

- `make check` could not start because `make` is not installed on this Windows shell.
- Equivalent local gate via `.venv\Scripts\python.exe` passed: Ruff format/check, MyPy, contracts,
  workflow validation, production hygiene, migrations and pytest.
- Full pytest after the Meta safety fix: **184 passed, 2 warnings, 82.90% coverage**.
- Focused settings/security tests after the fix: **26 passed, 1 warning**.
- `scripts/production_check.py`: **15 passed, 0 failed, 9 skipped**, strict exit `2`, overall
  **INCOMPLETE**.
- `scripts/production_check.py --allow-skips`: **15 passed, 0 failed, 9 skipped**, exit `0`, overall
  **PARTIAL**.
- Laravel adapter tests inside the production gate: **20 tests, 95 assertions**.
- Workflow validation after the Dev preflight edit: **7 workflows, 3 composite actions, 51 job
  steps**.

Skipped production evidence remains release-blocking: Docker build/runtime/scan/SBOM, Gitleaks,
tflint, Checkov/tfsec, PostgreSQL live round-trip, load smoke, deployed smoke, AWS deployment,
provider sandbox calls, and rollback drill. The detailed traceability for this continuation is in
[`production-closure-traceability.md`](production-closure-traceability.md).

## 2026-07-14 gate evidence

The final local gate run is stronger than the historical evidence below, but it still does not
approve production.

Passed local evidence:

- `.venv\Scripts\uv.exe lock --check`: 145 packages resolved.
- `.venv\Scripts\python -m pip_audit`: no known vulnerabilities found; local package skipped because
  it is not published to PyPI.
- Ruff format/check over `src tests scripts`: passed.
- Strict typing via `python -m mypy src tests`: passed over 178 files.
- Contracts: 10 schemas, 12 JSON files, 2 YAML files, 21 OpenAPI operations.
- Workflows: 7 workflows, 3 composite actions, 50 job steps.
- Production hygiene: 148 Python files inspected.
- Migrations: 3 Alembic revisions, head `20260713_000003`, offline upgrade/downgrade SQL generated.
- Python tests: 184 passed, 83.24% coverage; two dependency warnings were observed
  (Starlette/httpx TestClient deprecation and Mangum event-loop deprecation).
- Laravel adapter: 20 PHPUnit tests, 95 assertions.
- Terraform: fmt plus dev/staging/prod init/validate passed locally.

Production-check result:

- `scripts/production_check.py --allow-skips`: 15 passed, 0 failed, 9 skipped, overall PARTIAL.
- `scripts/production_check.py`: 15 passed, 0 failed, 9 skipped, strict mode exited nonzero with
  overall INCOMPLETE.

Skipped release evidence and current NO-GO blockers:

- `tflint`, Checkov/tfsec, Docker, container scan/SBOM, Gitleaks, real PostgreSQL round-trip, load
  smoke, and deployed smoke were not available/configured.
- No AWS plan/apply, GitHub workflow execution, provider sandbox/live call, or target Laravel/MySQL
  installation was performed.
- The inspected Lead Intake service still lacks the required canonical outbound WhatsApp endpoint;
  Onboarding remains externally unverified for the durable canonical event contract.
- The new teacher-first scheduling path is implemented and locally tested, but live Google
  Workspace/Meet credentials and an authoritative tutor availability source are still absent.
- The new Lambda handler is API-only and locally smoke-tested; it is not evidence that queue
  workers, reminders, reconciliation, or model-evaluation workloads are production-ready on Lambda.

The repository now contains a substantial fail-closed implementation: deterministic domain policies,
46 operational PostgreSQL tables, durable ingress/inbox processing, security primitives, provider
clients, a private Laravel gateway package, AWS Terraform, delivery workflows, and operational
runbooks. It is not yet justified to call the complete cross-system demo journey production-ready.
The decision is based on evidence, not code volume: Docker/PostgreSQL were unavailable locally; no
provider or AWS credentials were supplied; the Terraform stack was not planned/applied in an AWS
account; workflows were not executed on GitHub; and required external Lead Intake/Onboarding
contracts are not deployed.

## Readiness summary

| Area | Status | Evidence | Release blocker / next proof |
|---|---|---|---|
| Architecture boundaries | Ready locally | Accepted ADRs; dependency/cycle/route tests | Re-run final architecture suite after all edits. |
| Configuration/readiness | Ready locally | Typed fail-closed settings; server-side inbound HMAC key/source/scope grants; non-consuming command-center/new-booking/payment/post-conversion/outbound gates; real/local profiles; live/ready/protected health | Exercise the real profile, pause/resume, and grant rotation with PostgreSQL, Redis, SQS, and secret references. |
| Domain policies | Ready for integration | Matching, scheduling, reminders/no-show, quality, objections, forecast, conversion, discounts, payment, regional tests | Persisted cross-module saga and full E2E failure matrix remain incomplete. |
| Database/migrations | Conditional | 46 table metadata registry; three Alembic revisions; offline SQL generation successful | Fresh PostgreSQL upgrade, downgrade/re-upgrade, indexes/query plans, concurrency and crash-recovery tests were not run. Migration `000002` imports current ORM metadata, so immutability/reproducibility needs review. |
| Durable ingress/inbox | Conditional | Encrypted durable ingress, row-locked processor, duplicate constraints, handoff and Cashfree handlers | Exercise against real PostgreSQL and worker crash/retry. Unsupported/max-attempt events need an operational DLQ/ticket path. |
| Durable outbox/side effects | Conditional | Worker invokes the durable publisher; strict routing exists for website activation, Lead outbound, and canonical Onboarding events; paused targets are excluded before row claim | Prove PostgreSQL crash/retry, pause/resume, and provider acknowledgement behavior. The external Lead and Onboarding target endpoints remain absent/incompatible. |
| WhatsApp harmony | Blocked externally | Direct Meta mode defaults off; signed handoff route and Lead outbound client exist | Inspected Lead Intake has no `/v1/internal/outbound/whatsapp`. Do not enable a second Meta sender. Target contract and durable send/status loop must be implemented and tested there. |
| Laravel/MySQL gateway | Conditional | Private package, HMAC/replay/scopes/audit, allowlisted reads, activation ledger/outbox and purpose-bound phone references; 20 adapter tests (95 assertions) passed with local SQLite extensions; Python uses exact `demo:*` scopes | Install/test in actual Laravel root and MySQL clone; validate configured keys, MySQL behavior and legacy schema variants. |
| Scheduling/Calendar/SES | Not ready live | Deterministic policies and real adapter code exist | No authoritative website tutor availability; no Google Workspace/calendar/Meet or SES credentials/sandbox calls; no persisted end-to-end scheduling compensation drill. |
| Cashfree/paid transition | Not ready live | Raw-body signature/replay verification, bound payment policy, payment models, webhook processing, activation adapter | No complete order-originating workflow, real PostgreSQL transaction proof, Cashfree sandbox/live call, reconciliation drill, or deployed Laravel activation. |
| Onboarding | Blocked externally | Canonical HMAC client/outbox routing, exact event-ID acknowledgement check, paid-to-handoff recorder, accepted/completed inbox handlers, welcome outbox, schemas, and compatibility client exist | Inspected endpoint is legacy shared-secret/synchronous/cache-dedupe. Canonical durable handoff is not deployed/live validated; failed-event/human-ticket handling and direct callback-to-request binding remain incomplete. |
| Security/privacy | Conditional | Inbound HMAC keys have server-side source/scope grants plus rotation/replay; provider signatures, AES-GCM payloads, request limits, URL allowlist, headers, redaction, consent/retention metadata | Final dependency/SAST/secret/container/Terraform scans and complete deletion/subject-request/abuse-control flows are not evidenced. Business/legal review is mandatory. |
| AWS infrastructure | Conditional | Terraform definitions for target topology and environment compositions | Final fmt/validate evidence pending; no account plan/apply, IAM simulation, backup restore, alarm delivery, DNS/certificate, SES, quota, or cost validation. |
| Lambda API option | Conditional | `demo_command_center.lambda_handler.handler` and one API Gateway v2 health smoke test | API-only convenience; no Lambda Terraform, VPC/RDS Proxy cold-start/concurrency evidence, worker migration, or production runtime ADR replacement. |
| CI/CD/rollback | Conditional | OIDC/digest deploy/rollback and security workflow definitions | Workflows and protected GitHub environments have not executed. Rollback/migration compatibility and automatic recovery require a drill. |
| Observability/operations | Conditional | OTel setup, safe logging, CloudWatch alarm/dashboard definitions, guarded operations CLIs, runbook set | Application metric emission/queries, real CLI/schedule execution, dashboards/alarms, paging owners/thresholds, and incident/DR drills remain unverified. |
| Load/capacity | Not evidenced | A configurable Locust file and capacity model exist | No load-smoke result, hardware/task sizing, p50/p95/p99, error/queue/pool metrics, or cost result. No million-concurrency claim is made. |

## Final local quality evidence

These results are local repository evidence only and are not production approval:

- 184 Python tests passed.
- Coverage was 83.24%.
- Strict mypy passed over 178 files.
- Ruff, contracts, workflows, production hygiene, and Alembic offline SQL passed.
- Laravel adapter PHPUnit passed 20 tests with 95 assertions using explicitly enabled local
  `pdo_sqlite`/`sqlite3`; this is not an in-host MySQL deployment test.

The closure owner must replace this section with the exact final `production-check` transcript/result.
A test or check unavailable because Docker, PostgreSQL, credentials, or a provider account is absent
must be recorded as **blocked/skipped**, never as passed.

The strict, non-deploying closure command is:

```text
make production-check
```

It returns an incomplete status when a release gate is skipped. `make production-check-local` is a
developer convenience that permits skips to return success while still printing `PARTIAL`; it is not
production approval.

## Acceptance gates

### A. Code quality — pending final rerun

Ruff, strict mypy, import direction/cycle tests, and focused module design exist. Final working-tree
results are required.

### B. Tests — partial

Unit/property/security/architecture/contract and a deterministic business-flow E2E cover important
policies. Stateful PostgreSQL/Redis/LocalStack integration, broad provider contracts, full 28-scenario
E2E/chaos suite, Laravel-in-host integration, and measured load thresholds are not demonstrated.

### C. Database — blocked locally

Metadata and offline migration SQL are useful but do not prove a clean upgrade, downgrade/re-upgrade,
locking/exclusion behavior, crash safety, or production query plans. Docker and PostgreSQL were not
available for this work session.

### D. Providers — blocked externally

Real adapter implementations fail closed, but Meta/Lead, Google, Cashfree, SES, OpenAI, website, and
Onboarding were not called with sandbox/live credentials. Live compatibility must remain reported as
unverified.

### E. Security — partial

Signature, timestamp/replay, audience, server-authorized key/source/scope grants, signed-claim
escalation rejection, encryption, oversized-body, route and setting tests exist. Final secret/
dependency/SAST/container/Terraform scans, PII canary log scan, key-rotation drill, and penetration/
abuse tests are required.

### F. Infrastructure — partial

Terraform and hardened non-root/read-only container definitions exist. Final Terraform validation is
pending and Docker was unavailable, so image build/health/non-root runtime and vulnerability/SBOM
checks are unproven locally.

### G. CI/CD — code-present, unexecuted

OIDC-only role assumption, immutable digest promotion, migration task, health/smoke, protected
production environment, and rollback workflows are defined. GitHub execution, environment policies,
role permissions, and automatic rollback behavior are unverified.

### H. Business correctness — partial

Deterministic policy tests defend core invariants, but cross-database/provider exactly-once behavior
requires real transactional and contract tests. Automatic booking is blocked by unknown tutor
availability; payment and onboarding are not end-to-end enabled.

### I. Operations — partial

Code-present payment, post-conversion and outbound startup gates, rollback triggers, Terraform alarms/
dashboards, high-severity runbooks, and guarded retention, replay/redrive, payment reconciliation, and
forecasting-evaluation CLIs exist. Other declared flags still need runtime command/dispatcher wiring;
all controls, metric emission, paging ownership, backups, and DR must be run and evidenced, not merely
configured.

### J. Repository hygiene — pending final scan

Production rejects local adapters and the provider clients do not fake success. Final placeholder,
secret, generated artifact, public-directory placement, diff/status, and no-commit checks are required.

## Required release sequence

1. Install/test the adapter at the actual Laravel root and prove the now-aligned Python/Laravel HMAC
   scope contract against a MySQL schema clone.
2. Implement and deploy the Lead Intake canonical outbound endpoint/durable status events while it
   remains the sole Meta owner; deploy the external durable canonical Onboarding event endpoint and
   accepted/completed callbacks.
3. Exercise the code-present website/Lead/Onboarding outbox routing, exact acknowledgement binding,
   pause/resume and callback handling under PostgreSQL crash/retry; complete the remaining payment
   and Onboarding failure/reconciliation branches.
4. Run clean PostgreSQL/Redis/LocalStack integration and migration upgrade/downgrade/re-upgrade;
   execute concurrency and crash-injection tests.
5. Run the complete local production gate, Docker build/runtime scan, Terraform fmt/validate/security,
   workflow validation, Laravel tests, and load smoke. Record every pass/fail/skip.
6. Validate each provider in an approved sandbox; then configure staging accounts, templates,
   calendar identity, SES events, Cashfree webhook, and gateway networking.
7. Obtain product, finance, security, privacy/legal, safeguarding, communications, and operations
   approvals for policies, consent, child data, discounts, payments/refunds, retention, and messages.
8. Plan Terraform in the target AWS account, review IAM/cost/data changes, deploy dev/staging by
   immutable digest, run smoke/synthetic/restore/rollback drills, then seek production approval.

No AWS apply, production provider call, Git commit, or push is authorized by this report.
