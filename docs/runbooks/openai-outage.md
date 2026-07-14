# OpenAI outage or advisory-model incident

Use for timeout/429/5xx, circuit opening, schema failure, injection/grounding regression, token-cost
spike, or inappropriate output.

## Contain

1. Set the OpenAI feature/affected task off. Core state, matching, scheduling, conversion score,
   discounts, payment, and outbound authorization continue deterministically or hand off.
2. Quarantine the prompt/model/schema version when a privacy or guardrail regression is suspected.
   Do not copy raw prompts or messages into the incident.
3. Preserve only redacted request metadata, idempotency reference, token/cost counts, schema outcome,
   and policy decision.

## Recover

- Confirm the fault is provider availability, budget, circuit, schema compatibility, or content
  policy rather than application state.
- Exercise deterministic objection/summary/message fallback and human-review routing.
- Evaluate the candidate model/prompt on the approved offline set, including injection, grounding,
  PII, schema, and cost gates.
- Canary in shadow/advisory mode. Resume only after named model/product/privacy approval.

An LLM result never authorizes availability, a send, a discount, payment, or lifecycle state, even
during recovery.

