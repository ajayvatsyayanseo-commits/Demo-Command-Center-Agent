# Model, prompt, or extraction rollback

Use for calibration/drift failure, objection grounding/PII regression, schema/fallback spike,
guardrail violation, subgroup harm, or unexpected model cost.

## Contain

1. Disable the affected forecast, objection, drafting, or OpenAI feature. Keep deterministic
   lifecycle and policy functions running; route low-confidence cases to human review.
2. Record application/model/prompt/feature-registry/schema/policy versions and sanitized evaluation
   window. Do not retain raw production text as incident evidence.
3. Prevent new recommendations from using the suspect output. Do not rewrite historical audit facts.

## Roll back and validate

- Select a previously approved compatible artifact/configuration or the deterministic fallback.
- Re-run time-aware offline evaluation, leakage, calibration, grounding, PII, injection, schema,
  cost, and minimum-cohort/subgroup gates.
- Deploy in shadow mode, compare against the approved baseline, then canary after named approval.
- Verify no model result directly changed availability, a send, a discount, paid state, or lifecycle
  state.

Resume only after recovery criteria remain satisfied for the configured window. Model promotion and
rollback thresholds require product, ML, privacy/fairness, and operations approval.

