# Conversion forecasting design

Numeric conversion probability comes from a deterministic versioned model, never an LLM. Begin only after a data-quality/privacy/fairness review and minimum labeled sample policy are satisfied.

Training rows use a point-in-time demo snapshot and a conversion label observed only after the prediction cutoff. Candidate features: requirement completeness, scheduling latency, reschedule/no-show evidence, attendance, rubric quality, explicit feedback categories, approved objection categories, prior consented relationship signals, mode, coarse region with sufficient sample, and operational reliability. Exclude raw text/contacts, child demographics, protected traits/proxies, post-outcome/payment leakage, tutor identity memorization, and future aggregates.

Baseline: regularized logistic regression with preprocessing fit inside time/group-aware cross-validation, class weighting only when justified, and Platt/isotonic calibration evaluated out of fold. Compare a constrained tree/boosting model only when it materially improves time-split calibration/discrimination without unacceptable stability/explainability/fairness cost.

Registry records dataset/feature/code/model/calibration versions, cutoff, metrics (log loss, Brier, calibration error/slope/intercept, ROC/PR), subgroup/coarse-region diagnostics with suppression, thresholds and decision purpose, approvers, artifact hash, and rollback model. Thresholds choose a next-best-action intensity, never deny service or authorize discount.

If data is insufficient, an explicitly labeled deterministic rules score may prioritize human follow-up but must not be presented as calibrated probability. Shadow evaluation precedes promotion. Online predictions store immutable features/explanations/uncertainty and model version.
