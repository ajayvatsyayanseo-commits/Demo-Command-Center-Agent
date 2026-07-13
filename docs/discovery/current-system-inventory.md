# Current-system inventory

Discovery was read-only on 2026-07-13. No provider credentials or live endpoints were exercised.

| System | Local root | Branch / commit | Verified role |
|---|---|---|---|
| NXTutors website | `E:\NX Tutor\Nxtutors Website\public` | `main` / `61b3db6be534fa16fa12dbb6745bd4bd5482cca2` | Laravel website, legacy user/tutor data, plans, subscriptions, Cashfree endpoints, demo form |
| Lead Intake Agent | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\nxtutors-lead-intake-agent` | `main` / `c52950198d6ced38e37ab8f0f81976c04770b7a9` | Canonical public Meta ingress, lead conversation, outbound WhatsApp sender, onboarding router |
| WhatsApp Onboarding Agent | `E:\Nx Tutor Lead Intake Agent\Ready In Production Agents\Onbording agent` | `main` / `8e867531f768a916cb9df33c7a10f2b10e3aa4c1` | Laravel package/service for signup and legacy `register` profile creation |

## Website

- `composer.json` requires PHP `^8.2`, Laravel `^12.0`, and `spatie/laravel-permission ^6.24`.
- The true Laravel root is literally named `public`; it contains `artisan`, `composer.json`, `app/`, `routes/`, `database/`, and `config/`. Its actual public document directory is the nested `public/` folder. This repository is outside both.
- `.env.example` selects MySQL, database-backed cache/queue, log mailer, Cashfree sandbox, and a configurable OpenAI model. Local `.env` keys were checked only for presence/non-emptiness; values were not printed or validated.
- Standard Laravel `User` session authentication and Spatie roles coexist with a legacy `register` model and custom `session('userid')` flows.
- Roles include `super_admin`, `sub_admin`, `institute`, `teacher`, `student`, `lead_manager`, and `lead_partner`. No region-membership model or region-scoped authorization was found.
- Rate limiters exist for public forms/APIs, payments, webhooks, admin generation, and imports. `ProviderCircuitBreaker` and external-call budgets exist for website generation features.
- CloudPanel is the documented deployment target. The workflow intentionally does not apply database migrations during deployment.

## Lead Intake Agent

- FastAPI with Lambda Function URL and ECS artifacts; its documented runtime is Python 3.11.
- Owns `GET/POST /v1/inbound/whatsapp` and aliases under `/webhook/whatsapp`.
- Verifies Meta GET tokens and can verify POST `X-Hub-Signature-256`; production enforcement depends on configuration validation.
- Deduplicates Meta message IDs in PostgreSQL (`whatsapp_messages`) and uses cache suppression for sends.
- Detects signup intent, forwards it to Onboarding, accepts `reply_text`, and remains the sender.
- Supports webhook/SQS/EventBridge integration modes, but existing general lead events are not the canonical envelope defined here.

## Onboarding Agent

- A Laravel package nested under the repository, with deterministic signup state machine, queue jobs, cache policy, privacy masking, health checks, and Terraform/ECS material.
- Accepts `X-NXTUTORS-INTERNAL-SECRET` handoffs and returns `reply_text` without sending on that internal path.
- Also contains a Meta webhook and `MetaMessageSender` compatibility path. It must remain unsubscribed/disabled when the shared number is routed through Lead Intake.
- Writes profiles through a legacy `register` adapter. Its deployment/database mode and host ownership need consolidation before production rollout.

## Repository root decision

The requested canonical repository is created at `Demo Command Center Agent\demo-command-center-agent`. The parent directory was empty and was not a Git repository. No Git repository was initialized and no commit was created.
