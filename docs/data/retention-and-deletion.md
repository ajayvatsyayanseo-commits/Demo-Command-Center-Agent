# Retention and deletion

Retention durations are policy records/configuration, not source constants. Each class has legal purpose, owner, review date, hold behavior, deletion/anonymization method, and downstream propagation.

| Class | Default design behavior |
|---|---|
| Raw provider webhook/body | Encrypted, shortest operational retry/audit window, then deleted |
| Message content/meeting links | Encrypted and purpose-limited; removed earlier than delivery metadata |
| Conversation summaries | Redacted; retain only while lifecycle/support purpose remains |
| Holds/cache/locks | Expire operationally; Redis never satisfies deletion by itself |
| Demo/outcome records | Minimized after lifecycle/contractual purpose ends |
| Payment/subscription evidence | Retain lawful financial fields; delete unnecessary contact/provider payload |
| Audit/security records | Tamper-evident minimal metadata under approved compliance period |
| Model features | Point-in-time, pseudonymized, approved feature allowlist; purge protected/raw content |

Deletion requests are authenticated, scope-resolved, approved where required, and tracked as a saga across Demo DB, website gateway, Lead Intake, Onboarding, S3 exports, and caches. Legal hold pauses eligible deletion with audited reason. Backups expire through lifecycle rather than selective mutation; deleted data is not restored into live use.
