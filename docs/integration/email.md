# Email integration

The Demo service sends through an Amazon SES port; website mail configuration is not assumed. The inspected website defaults to the log mailer and merely defines SES support, so actual SES identity, region, production access, quotas, bounce/complaint topics, and credentials are **UNVERIFIED**.

Recipients are resolved through authoritative participant/tutor references. Tutor email is used server-to-server and is not exposed to the learner. Learner/guardian email is optional and requires purpose-specific consent. Every send uses an approved template/version, stable idempotency key, SES configuration set, tenant/region metadata without PII, and stored provider message reference.

Bounce/complaint events enter a signed AWS event/SNS-to-SQS boundary, update delivery/suppression status, and prevent blind retry. Meeting links and personal content are encrypted in operational storage and excluded from logs/analytics. SES outage queues safely; it does not invalidate a confirmed booking, and a human ticket opens when confirmation cannot be delivered within policy SLA.
