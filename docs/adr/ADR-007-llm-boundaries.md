# ADR-007: LLM boundaries

- Status: Accepted
- Date: 2026-07-13

## Context

Language models help with language but are probabilistic, vulnerable to prompt injection, and unsuitable as payment, availability, or policy authorities.

## Decision

LLMs may perform redacted structured objection extraction, summarization, controlled drafting, bounded classification, and offline evaluation. Strict schemas, versioned prompts, confidence, token/cost budgets, output policy, and deterministic fallback are required. LLM output cannot mutate state, call a provider, send messages, authorize discounts, establish availability/payment, execute SQL, or create URLs.

## Consequences

Application policy mediates every result and preserves evidence/version. Provider failure degrades language quality, not core scheduling/payment truth. Prompt/schema evaluation and injection tests become release gates; restricted content is never placed in model telemetry.
