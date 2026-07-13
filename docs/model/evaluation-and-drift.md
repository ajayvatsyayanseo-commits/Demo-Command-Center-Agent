# Model evaluation and drift

Evaluation runs in an isolated optional worker from immutable, versioned datasets. It has no production write credentials except model/drift result ports and cannot promote itself.

Forecast monitoring compares feature missingness/distribution (PSI/KS or suitable categorical distance), prediction distribution, delayed outcome calibration/Brier/log loss, threshold action rates, regional/subgroup metrics with minimum samples, and data freshness. Objection/drafting monitoring tracks schema validity, unsupported evidence, reviewer disagreement, fallback, latency, tokens/cost, and injection/adversarial failures.

Alert rules require configurable window, baseline, minimum sample, confidence/practical significance, consecutive breach or severity, suppression/dedup, owner, acknowledgement, resolution, and escalation. Sparse cohorts are suppressed, not interpreted.

Promotion requires offline gates, privacy/fairness review, artifact/schema compatibility, shadow/canary results, named approval, and rollback target. Calibration failure, protected-slice harm, leakage discovery, schema/fallback spike, or unexpected cost disables the affected model capability. Core demo service continues with deterministic fallback/human review.
