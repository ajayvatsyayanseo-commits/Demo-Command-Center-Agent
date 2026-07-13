# SLOs and SLAs

Exact objectives require product/operations approval and measured baselines; they are configuration/runbook values, not hardcoded here.

Define SLIs/SLOs for: signed webhook durable acceptance, internal handoff durable acceptance, first response request, tutor-match latency, scheduling completion, reminder enqueue timeliness, provider delivery, payment webhook processing and activation, onboarding handoff, API availability/latency, queue oldest age, and human ticket acknowledgement/resolution by severity.

Correctness SLOs are stricter than latency: duplicate booking rate, duplicate outbound business effect, payment double activation, amount mismatch escaped, invalid signature accepted, and restricted-PII log occurrence target zero. Availability excludes deliberate security rejection but not misconfiguration.

Error budgets control release pace and automation. A breach pauses risky releases/automation, invokes owner runbook, and requires review. External provider SLAs are dependencies, not our SLO exclusions; user-facing commitments include safe queue/fallback and honest status.
