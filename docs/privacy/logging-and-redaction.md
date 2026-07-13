# Logging and redaction

Logs are structured allowlists. Required context may include trace/correlation/causation, hashed conversation reference, demo ID, event type, before/after state, provider, operation, latency, retry, result/error code, app/flow/policy/model version. Restricted content is forbidden.

Never log raw phone/email/name/address, message/feedback/evidence, child detail, tutor private contact, calendar attendee/meeting URI, payment/provider body, authorization/cookie/signature, credential/secret, encryption material, or arbitrary exception request content.

The scaffold redaction processor is defense in depth, not permission to pass raw values. Application log calls use explicit safe fields. CI tests inject canary phone/email/token/private-key shapes and scan captured logs. Production uses access-controlled CloudWatch groups with configured retention; analytics logs are not a backdoor data export. A redaction failure triggers outbound/affected capability pause and the incident runbook.
