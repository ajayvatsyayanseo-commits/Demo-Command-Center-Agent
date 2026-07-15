# Codex production closure report

Date: 2026-07-15 (Asia/Calcutta)  
Repository: Demo Command Center Agent  
Requested objective: make the current agent production-ready without deleting valid existing work  
Actual disposition: **NO-GO / INCOMPLETE**, because required external staging/provider/deployment
evidence is still missing

## What was implemented in this pass

1. Demo Command Center direct Meta webhook mode was fail-closed.
   - File: `src/demo_command_center/config/settings.py`
   - Reason: Lead Intake must remain the canonical public Meta ingress.

2. Demo Command Center active direct Meta outbound mode was fail-closed.
   - File: `src/demo_command_center/config/settings.py`
   - Reason: WhatsApp outbound must go through the canonical Lead Intake gateway, not a second active
     Meta sender.

3. The Meta provider route security test was corrected to assert the production ownership invariant.
   - File: `tests/security/test_signed_routes_and_provider_ingress.py`

4. The Dev deployment workflow was guarded and given a non-secret-printing preflight.
   - File: `.github/workflows/deploy-dev.yml`
   - Push-to-main deployment now requires `DEPLOY_DEV_ENABLED=true`.
   - Manual dispatch still works but validates required AWS/ECS/GitHub configuration names first.

5. Phase 0 traceability was added.
   - File: `docs/operations/production-closure-traceability.md`

6. The production readiness report was updated with the 2026-07-15 evidence.
   - File: `docs/operations/production-readiness-report.md`

## Repositories changed

Only the Demo Command Center Agent repository was changed in this pass.

No changes were made to:

- NXTutors website repository
- Lead Intake Agent repository
- WhatsApp Onboarding Agent repository

The Onboarding local working tree had pre-existing unrelated dirty state and was left untouched.

## Validation totals

| Gate | Result |
|---|---|
| `make check` | Not executable on this Windows shell because `make` is not installed |
| Equivalent local gate via `.venv\Scripts\python.exe` | Passed |
| Ruff format/check | Passed |
| MyPy | Passed; 178 source files |
| Contracts | Passed; 10 schemas, 12 JSON files, 2 YAML files, 21 OpenAPI operations |
| Workflow validation | Passed; 7 workflows, 3 actions, 51 job steps |
| Production hygiene | Passed; 148 Python files inspected |
| Migration validation | Passed; 3 revisions, head `20260713_000003` |
| Full pytest | 184 passed, 2 warnings |
| Coverage | 82.90% direct run; 82.93% inside production gate |
| Focused settings/security tests | 26 passed, 1 warning |
| Laravel adapter tests in production gate | 20 tests, 95 assertions |
| Strict production check | 15 passed, 0 failed, 9 skipped, exit 2, overall INCOMPLETE |
| Local production check with skips allowed | 15 passed, 0 failed, 9 skipped, exit 0, overall PARTIAL |

## Production blockers closed

- Demo Command Center can no longer be configured as the active direct Meta webhook receiver.
- Demo Command Center can no longer be configured as an active direct Meta outbound sender when
  unpaused.
- Dev deployment no longer auto-fails on push merely because AWS/ECS variables are not yet populated;
  it is guarded by `DEPLOY_DEV_ENABLED=true` and preflight validation.

## Remaining blockers

These remain **not production-ready** until genuine evidence exists:

- Docker build, non-root runtime check, vulnerability scan and SBOM.
- Gitleaks secret scan.
- Terraform lint and security scan (`tflint`, Checkov/tfsec).
- Real PostgreSQL migration round-trip through `PRODUCTION_CHECK_POSTGRES_URL`.
- Redis, SQS/LocalStack, EventBridge and crash/retry integration evidence.
- Laravel gateway installed and tested inside the actual website against MySQL.
- Lead Intake canonical outbound endpoint deployed and contract-tested.
- Onboarding durable canonical event contract deployed and contract-tested.
- Google Calendar/Meet sandbox validation.
- Cashfree sandbox order/link/webhook/reconciliation validation.
- SES test delivery validation.
- AWS ECS deployment, smoke test, alarm check and rollback drill.
- Measured load/cost evidence.

## Deployment status

No deployment was performed in this pass.

## Provider-validation status

No live or sandbox provider call was performed in this pass.

## Git statement

No commit, amend, squash, tag, push, branch, remote or history change was made.
