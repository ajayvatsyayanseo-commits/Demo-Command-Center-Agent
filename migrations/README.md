# Database migrations

Alembic migrations own only the Demo Command Center PostgreSQL schema. They must never target the Laravel/MySQL database. Review locks and backwards compatibility before production execution; run migrations as a one-off ECS task before the application rollout.
