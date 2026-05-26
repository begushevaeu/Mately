# Mately Scheduling Decision

Last updated: 2026-05-26.

## Decision

Keep APScheduler inside the single polling bot process for the current product
stage. Do not add Redis, Celery, or a separate queue worker until production
reliability data shows a concrete scheduling problem that the current design
cannot handle.

This matches the MVP deployment shape: one bot container, one PostgreSQL
database, no public HTTP server, and no extra worker fleet.

## Current Scheduled Jobs

The application scheduler starts from `app.schedulers.system` and runs three
short interval jobs every minute:

- `shopping_midnight_cleanup`: archives bought shopping items after the
  couple's local midnight.
- `recurring_task_regeneration`: creates the next occurrence for due recurring
  tasks.
- `couple_local_reminders`: sends enabled morning and evening couple reminders
  at each couple's local time.

Statistics recaps are currently available on request from the Statistics block.
Proactive weekly or monthly recap sends remain disabled or gated by the
notification matrix. If proactive recaps are reintroduced, they should follow
the same dedupe and catch-up requirements as reminders.

## Reliability Requirements

Reminder and recap scheduling should satisfy these requirements before any
queue technology is considered successful:

- send at most one notification per couple, user, notification type, and local
  period;
- keep the bot useful after restarts by deriving due work from database state;
- keep job bodies short enough that a one-minute scan interval does not create
  backlog;
- roll back failed database work and retry on a later scheduler tick;
- keep reminder and recap text generation failure-tolerant through deterministic
  fallbacks;
- keep production deployment to exactly one polling bot process for one
  Telegram token.

The current reminder implementation uses database dedupe keys for duplicate
protection. Its main reliability limitation is wall-clock downtime: if the bot
is stopped during the exact local reminder minute, that daily reminder can be
missed until the next day. If production usage shows this matters, improve the
database due-notification model and catch-up window before adding a queue.

## Tradeoffs

| Option | Benefits | Costs | Fit now |
| --- | --- | --- | --- |
| APScheduler in bot | Minimal infrastructure, easy local-time scans, simple logs, already covered by tests | No durable distributed queue, depends on one running bot process, exact-minute jobs can miss downtime windows | Best fit |
| Redis-backed queue | Adds a broker for retryable work and possible delayed jobs | Extra service to deploy, monitor, back up, and secure; still needs careful Telegram dedupe | Defer |
| Celery workers | Mature retry, routing, and worker tooling for heavier background work | Broker plus result backend decisions, worker deployment, beat scheduling, more operational surface | Avoid until jobs become heavy |

## Revisit Triggers

Reopen the Redis/Celery decision only if one or more of these become true:

- daily reminders or proactive recaps need guaranteed catch-up after bot
  downtime;
- scheduled work regularly takes longer than the one-minute interval;
- exports, photo processing, AI batches, or analytics ingestion become long
  background jobs;
- the deployment moves from one polling bot process to webhooks or multiple
  application replicas;
- production support needs per-job admin retry, visibility, or dead-letter
  handling beyond logs and database status.

## Recommendation

Keep APScheduler for now. The next scheduling improvement, if needed, should be
a PostgreSQL-backed due-notification scan with `PENDING`, `SENT`, and `FAILED`
states plus a bounded catch-up window. Add Redis or Celery only after that
simpler database-backed model is not enough.
