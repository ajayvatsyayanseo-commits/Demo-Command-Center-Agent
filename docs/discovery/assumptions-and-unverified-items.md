# Assumptions and unverified items

`UNVERIFIED` means the code or configuration was absent, inaccessible, ambiguous, or not exercised with valid credentials. It does not mean false.

## Safe architecture assumptions

- A single NXTutors tenant is expected initially, but tenant IDs remain mandatory for isolation.
- `Asia/Kolkata` is a fallback display timezone only; persisted instants are UTC and participant IANA zones are retained.
- Aurora PostgreSQL, ElastiCache Redis, SQS, EventBridge Scheduler, ECS Fargate, and AWS Secrets Manager are the target AWS services.
- The website can host a thin authenticated integration gateway outside its nested web document directory.
- Lead Intake can add demo intent routing and canonical envelope signing without changing its public Meta subscription.
- A single NXTutors-controlled Google organizer calendar is preferred, with delegated Workspace identity when available.

## UNVERIFIED

- Production database schema/data quality, legacy table indexes, and exact foreign-key integrity.
- Current deployed commit for any inspected repository.
- Live Meta app/number ownership, templates, quality rating, service-window tracking, and message permissions.
- Cashfree account/API version, webhook delivery settings, refunds/disputes process, and sandbox/live credentials.
- Google Workspace domain, delegated user, calendar ID, API scopes, and Meet licensing.
- SES verified identities, suppression handling, sending limits, and production access.
- AWS account/VPC/subnets, Route 53 zones, ACM certificates, WAF rules, quotas, and current Terraform state.
- Live Lead Intake/Onboarding base URLs, shared-secret rotation, queue/cache durability, and retry behavior.
- Authoritative tutor working hours, exceptions, leave, travel buffers, or calendar permissions.
- Region definitions, admin-region membership, regional baselines, and escalation ownership.
- Approved pricing, margin, discount bands, social proof, reminder policy, quiet hours, retention periods, SLOs, and legal consent text.
- Historical labeled demo/conversion dataset size, quality, leakage risk, and fairness review.
- Second IDE attachment referenced by the editor was not present at its displayed path and could not be inspected.

Every item above is configuration- or contract-gated. Automated scheduling, outbound messaging, discounts, payments, and onboarding remain disabled until their corresponding evidence and approvals exist.
