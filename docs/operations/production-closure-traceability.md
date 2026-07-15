# Production closure traceability

Date: 2026-07-15 (Asia/Calcutta)  
Repository: Demo Command Center Agent  
Phase: Phase 0 truth baseline plus first code-controlled safety fixes  
Disposition: **NO-GO for production until external staging/provider evidence is complete**

This file records the current implementation evidence without treating source-code presence as live
production proof.

## Repositories inspected

| Repository | Local root | Branch | HEAD | Working tree at inspection |
|---|---|---:|---|---|
| Demo Command Center Agent | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\Demo Command Center Agent` | `main` | `ba0b594f05673672cc22ab0fc8b78ce714c04354` | Modified by this pass: settings, Meta safety test, dev deploy workflow, operations docs |
| NXTutors website | `E:\NX Tutor\Nxtutors Website\public` | `main` | `61b3db6be534fa16fa12dbb6745bd4bd5482cca2` | Not modified |
| Lead Intake Agent | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\nxtutors-lead-intake-agent` | `main` | `c52950198d6ced38e37ab8f0f81976c04770b7a9` | Not modified |
| WhatsApp Onboarding Agent | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\Onbording agent` | `main` | `8e867531f768a916cb9df33c7a10f2b10e3aa4c1` | Pre-existing dirty state observed: `D nx-whatsapp-onboarding-agent/.env1`, `?? .gitignore`; not modified |

## Commands run in this pass

| Command | Result |
|---|---|
| `make check` | Failed to start: `make` is not installed on this Windows shell |
| `.venv\Scripts\python.exe -m ruff format --check src tests scripts` | Passed; 183 files already formatted |
| `.venv\Scripts\python.exe -m ruff check src tests scripts` | Passed |
| `.venv\Scripts\python.exe -m mypy src tests` | Passed; 178 source files |
| `.venv\Scripts\python.exe scripts\validate_contracts.py` | Passed; 10 schemas, 12 JSON files, 2 YAML files, 21 OpenAPI operations |
| `.venv\Scripts\python.exe scripts\validate_workflows.py` before workflow edit | Passed; 7 workflows, 3 actions, 50 job steps |
| `.venv\Scripts\python.exe scripts\validate_workflows.py` after workflow edit | Passed; 7 workflows, 3 actions, 51 job steps |
| `.venv\Scripts\python.exe scripts\validate_production_hygiene.py` | Passed; 148 Python files inspected |
| `.venv\Scripts\python.exe scripts\validate_migrations.py` | Passed; 3 revisions, head `20260713_000003`, offline upgrade/downgrade SQL generated |
| `.venv\Scripts\python.exe -m pytest --cov=demo_command_center --cov-report=term-missing` baseline | Failed before fix: 182 passed, 2 failed, 2 warnings; failures were unsafe Meta fail-closed settings tests |
| Focused tests after fix | Passed; 26 passed, 1 warning |
| Full tests after fix | Passed; 184 passed, 2 warnings, coverage 82.90% direct run / 82.93% through production gate |
| `.venv\Scripts\python.exe scripts\production_check.py` | 15 passed, 0 failed, 9 skipped; strict exit 2; overall INCOMPLETE |
| `.venv\Scripts\python.exe scripts\production_check.py --allow-skips` | 15 passed, 0 failed, 9 skipped; exit 0; overall PARTIAL, not production approval |

## Code-controlled blockers closed

| Blocker | Evidence | Status |
|---|---|---|
| Demo Command Center could be configured as a direct Meta webhook when `.env` contained Meta credentials | `src/demo_command_center/config/settings.py` now always rejects `META_DIRECT_WEBHOOK_ENABLED=true`; `tests/security/test_signed_routes_and_provider_ingress.py` verifies rejection | Closed locally |
| Demo Command Center could activate direct Meta outbound when unpaused and credentials existed | `src/demo_command_center/config/settings.py` now rejects active direct Meta outbound and requires the canonical Lead Intake gateway path | Closed locally |
| Dev deployment auto-ran on push even when AWS/ECS configuration was incomplete | `.github/workflows/deploy-dev.yml` now skips push deployment unless `DEPLOY_DEV_ENABLED=true`; manual dispatch still runs preflight; preflight validates required config names without printing values | Closed locally |

## Requirement traceability

| Requirement area | Owning repo | Owning module/file | Migration/contract | Test/evidence | Current status | Blocker |
|---|---|---|---|---|---|---|
| Modular-monolith / dependency boundaries | Demo Command Center | `docs/architecture/module-dependency-rules.md`, `src/demo_command_center/modules/*` | N/A | Architecture tests passed | Complete locally | Re-run after further implementation |
| Single WhatsApp owner | Lead Intake + Demo Command Center | `docs/adr/ADR-002-single-whatsapp-ingress.md`, `src/demo_command_center/config/settings.py` | `contracts/lead_intake/outbound-delivery-requested.v1.schema.json` | Meta direct webhook/outbound fail-closed tests passed | Complete locally for Demo Command Center | Lead Intake canonical outbound endpoint remains externally unverified |
| Durable ingress/inbox | Demo Command Center | `src/demo_command_center/infrastructure/inbox/*` | `migrations/versions/20260713_000001_initial_operational_core.py` | Unit/security tests passed | Partial | Needs real PostgreSQL crash/retry and SQS duplicate/out-of-order tests |
| Durable outbox/side effects | Demo Command Center | `src/demo_command_center/infrastructure/outbox/*`, `src/demo_command_center/integrations/outbox_router.py` | Operational tables in Alembic migrations | Unit tests passed | Partial | Needs worker restart/provider acknowledgement evidence |
| Website authority / Laravel gateway | Website + Demo Command Center | `integrations/nxtutors-laravel-adapter/*`, `src/demo_command_center/integrations/nxtutors_website/client.py` | `contracts/website/website-gateway.v1.yaml` | Adapter package tests passed locally; not installed in actual website | Partial | Must install/test in real Laravel root against MySQL clone |
| Tutor availability | Website + Demo Command Center | Adapter tutor projection and scheduling policy files | Availability snapshot/slot tables | Domain tests passed | Partial | Website authoritative availability source still unverified |
| Teacher-first scheduling | Demo Command Center | `src/demo_command_center/modules/scheduling/application/use_cases.py` | Google calendar operation contract | `tests/unit/test_teacher_first_scheduling.py` passed | Partial | Needs live Google Workspace/Meet sandbox validation |
| Google Calendar/Meet | Demo Command Center | `src/demo_command_center/integrations/google_calendar/client.py` | `contracts/google_calendar/calendar-operation.v1.schema.json` | Code present; no live call in this pass | External | Requires Google Workspace service account, delegated user, calendar and test Meet creation |
| Reminders | Demo Command Center | `src/demo_command_center/modules/reminders/domain/policy.py` | Reminder jobs table | Unit tests passed | Partial | Needs EventBridge/SQS execution evidence |
| Objection extraction | Demo Command Center | `src/demo_command_center/modules/objection_extraction/*`, `src/demo_command_center/integrations/openai/client.py` | Prompt/evaluation docs | Unit tests passed | Partial | Needs approved golden set and provider sandbox evaluation |
| Forecasting | Demo Command Center | `src/demo_command_center/modules/success_forecasting/*` | Model docs/tables | Unit tests passed | Partial | Needs historical dataset, calibration, drift and promotion evidence |
| Discounts | Demo Command Center | `src/demo_command_center/modules/discount_suggestions/domain/policy.py` | Discount tables | Unit tests passed | Partial | Needs approval workflow and business policy approval |
| Cashfree paid transition | Demo Command Center + Website + Onboarding | `src/demo_command_center/infrastructure/payments/*`, `src/demo_command_center/integrations/cashfree/client.py` | `contracts/cashfree/payment-webhook-normalized.v1.schema.json` | Unit/security tests passed | Partial | Needs Cashfree sandbox order/link/webhook/reconciliation and website activation proof |
| Onboarding handoff | Onboarding + Demo Command Center | `src/demo_command_center/integrations/onboarding/*` | `contracts/events/onboarding-*.schema.json` | Client/contract tests passed locally | Partial | Onboarding repo durable canonical event endpoint not verified |
| Regional monitoring | Demo Command Center | `src/demo_command_center/modules/regional_monitoring/domain/policy.py` | Regional tables | Unit tests passed | Partial | Needs admin API integration, authorization enforcement and dashboard evidence |
| Security scans | Demo Command Center | `scripts/production_check.py`, workflows | N/A | pip-audit passed; hygiene passed | Partial | Gitleaks, tflint, Checkov/tfsec, Docker scan and SBOM skipped because tools/Docker unavailable |
| AWS runtime | Demo Command Center | `infra/terraform/*`, `.github/workflows/deploy-dev.yml` | Terraform modules | Terraform fmt/init/validate passed; dev deploy preflight added | Partial | No AWS plan/apply, ECS deploy, smoke test or rollback drill in this pass |
| Load/cost | Demo Command Center | `tests/load/locustfile.py`, `docs/cost/*` | N/A | No measured load run | External | Needs deployed environment and load target |

## Remaining external release blockers

- Docker is not installed locally, so image build, non-root runtime verification, container scan and SBOM remain skipped.
- `gitleaks`, `tflint`, Checkov/tfsec are not installed locally, so those scans remain skipped.
- `PRODUCTION_CHECK_POSTGRES_URL` was not configured for the production gate, so live PostgreSQL round-trip evidence is absent in this run.
- No deployed `PRODUCTION_CHECK_SMOKE_BASE_URL` or load target was configured, so deployed smoke and load evidence are absent.
- No GitHub Actions run, AWS ECS deployment, migration ECS task, staging provider sandbox call, or rollback drill was executed.
- Google Calendar/Meet, SES, Cashfree, Lead Intake outbound and Onboarding durable contract remain unvalidated externally.

## Git statement

No commit, tag, branch, remote, push, amend, squash or history operation was performed.
