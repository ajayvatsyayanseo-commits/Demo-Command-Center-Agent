# Capability map

| Module | Owns | Does not own |
|---|---|---|
| `demo_core` | Canonical case, requirements, participants, lifecycle transitions | Provider calls |
| `tutor_matching` | Candidate normalization/ranking and evidence | Tutor source-of-truth data |
| `scheduling` | Proposals, holds, confirmations, session/calendar saga | Calendar truth or tutor profile edits |
| `reminders` | Durable reminder plans/executions and no-show escalation | In-process timers or direct sends |
| `regional_monitoring` | Sanitized aggregates, statistically gated alerts | Raw PII analytics |
| `success_forecasting` | Feature snapshots, model versions, calibrated probability, drift | LLM numeric guesses or service denial |
| `objection_extraction` | Evidence-linked structured objections | Invented or unsupported objections |
| `post_demo_conversion` | Policy-checked strategy and message draft | Direct sends or fabricated claims |
| `discount_suggestions` | Deterministic eligibility/approval workflow | Autonomous financial authorization |
| `paid_transition` | Order orchestration, webhook/reconciliation, activation, onboarding saga | Browser-return payment truth |
| `communications` | Channel policy and delivery requests | Multiple outbound Meta senders |
| `human_handoff` | Redacted ticket, SLA, assignment, audit | Silent failure queues |

Cross-cutting infrastructure supplies inbox/outbox, idempotency, persistence, queues, scheduler, security, privacy, resilience, observability, cost budgets, and feature flags through ports.
