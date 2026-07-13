# Container and component model

One image supports distinct ECS process types:

| Process | Responsibility | Scaling signal |
|---|---|---|
| API | Internal handoffs, provider webhook boundaries, admin queries, health | ALB request/latency and CPU |
| Worker | Inbox processing, scheduling, outbound, payment, analytics | SQS oldest-message age/depth |
| Evaluation worker | Training/evaluation/drift batch | Dedicated queue/schedule |
| Scheduled task | EventBridge one-shot reminders and maintenance commands | Invoked on demand |
| Admin task | Alembic, doctor, reconciliation, DLQ redrive, retention | Manually approved ECS task |

```mermaid
flowchart TB
    API[FastAPI transport] --> APP[Application commands/queries]
    WORK[Queue workers] --> APP
    CLI[CLI / scheduled tasks] --> APP
    APP --> DOMAIN[Domain modules + state machine]
    APP --> PORTS[Typed ports]
    ADAPTERS[SQLAlchemy / SQS / Redis / HTTP provider adapters] --> PORTS
    ADAPTERS --> EXT[(PostgreSQL / AWS / providers)]
```

The API does not call providers directly. Commands write state plus outbox in one database transaction. Dispatchers claim outbox rows with bounded leases and publish idempotently.
