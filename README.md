# Mately

Mately is a minimal Telegram bot for couples who want a calm shared space for household tasks, content tracking, reminders, and cozy recaps.

## Current Status

The repository is initialized with the project structure from `docs/mately_step_by_step.md.txt`:

- aiogram application package under `app/`
- separated bot handlers, keyboards, states, filters, services, repositories, analytics, AI, notifications, and schedulers
- PostgreSQL and Docker Compose scaffolding
- Alembic scaffolding
- local cat asset folders under `assets/cats/`

## Local Setup

1. Create a virtual environment with Python 3.12+.
2. Install the project dependencies:

   ```bash
   pip install -e .
   ```

   For local development with tests and TaskOS:

   ```bash
   pip install -e ".[dev]"
   ```

3. Copy `.env.example` values into `.env` and fill `BOT_TOKEN`.
4. Start PostgreSQL with Docker Compose:

   ```bash
   docker compose up db
   ```

5. Start the bot:

   ```bash
   python -m app.main
   ```

To apply database migrations locally:

```bash
python -m alembic upgrade head
```

If local Windows networking blocks direct Python access to the Docker-published database port, run migrations inside Docker instead:

```bash
docker compose run --rm bot python -m alembic upgrade head
```

The Docker bot container runs migrations automatically on startup when `RUN_MIGRATIONS=true`.

## TaskOS Workflow

This repository includes Codex TaskOS for implementation planning. `tasks.json` is the source of truth, `progress.txt` keeps the work log, and the generated views live in `docs/kanban.md` and `docs/task-board.html`.
The human-readable roadmap lives in `ROADMAP.md`.

Useful commands:

```bash
taskos doctor
taskos ready
taskos claim
taskos done TASK-001 --summary "Implemented the task." --check "python -m pytest"
taskos sync
```

Do not edit the generated kanban or dashboard directly; change `tasks.json` or use the TaskOS commands and run `taskos sync`.

## Required Environment Variables

- `BOT_TOKEN` - Telegram bot token from BotFather.
- `DATABASE_URL` - SQLAlchemy async PostgreSQL URL. Use `127.0.0.1` for local Docker on Windows.
- `OPENAI_API_KEY` - optional for the cozy AI layer.
- `OPENAI_MODEL` - OpenAI chat model for cozy notification copy.
- `OPENAI_TIMEOUT_SECONDS` - AI request timeout before using deterministic fallback copy.
- `OPENAI_MAX_TOKENS` - maximum token budget for one cozy message.
- `OPENAI_TEMPERATURE` - generation temperature for short warm copy.
- `LOG_LEVEL` - application log level.
- `SQL_ECHO` - SQLAlchemy query logging toggle.
- `DEFAULT_TIMEZONE` - fallback timezone for couple reminders.
- `INVITE_CODE_TTL_HOURS` - invite code lifetime in hours.
- `RUN_MIGRATIONS` - run Alembic migrations before starting the bot container.

## Deployment Notes

The MVP is deployment-ready as a single polling bot process with PostgreSQL:

- VPS: use `docker-compose.prod.yml`, keep `.env.production` outside Git, and run `docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build`.
- Full checklist: see `DEPLOYMENT.md`.
- Backup and export runbook: see `OPERATIONS.md`.
- Analytics event catalog: see `ANALYTICS_EVENTS.md`.
- Do not run more than one polling bot instance for the same token at the same time.

## Architecture Guardrails

The code is intentionally kept in the `handlers -> services -> repositories` shape:

- handlers own Telegram UX only;
- services own business rules;
- repositories own database access;
- schedulers and notifications call services instead of embedding SQL.

Mately should stay small: short flows, clear buttons, and calm shared-household behavior over deep menus or heavy forms.
