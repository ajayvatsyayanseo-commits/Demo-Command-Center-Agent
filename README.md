# --------Demo Command Center Agent------

Production-oriented architecture and compileable scaffold for the NXTutors demo journey: qualification, tutor matching, scheduling, reminders, outcome analysis, conversion, payment, and onboarding handoff.

The service is a Python 3.12 FastAPI modular monolith. It owns demo lifecycle data in PostgreSQL while the existing Laravel/MySQL website remains authoritative for users, tutors, plans, orders, and subscriptions. Lead Intake remains the single public Meta WhatsApp ingress and outbound sender.

## Quick start

```bash
uv sync --frozen --all-extras
copy .env.example .env
uv run uvicorn demo_command_center.main:app --app-dir src --reload
```

The default local profile exposes health endpoints but keeps all provider-backed capabilities disabled. Internal ingress requires a configured shared secret. Production startup fails closed when a fake adapter or a required capability configuration is selected.

```bash
uv run demo-command-doctor
uv run pytest
```

Start with [the architecture index](docs/architecture/README.md), [the discovery inventory](docs/discovery/current-system-inventory.md), and [the final phase report](docs/discovery/codex-final-report.md).

This phase is an architectural scaffold, not a claim of validated live provider integrations. Provider sandbox/live status is reported explicitly by the doctor command.

