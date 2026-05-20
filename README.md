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

## Required Environment Variables

- `BOT_TOKEN` - Telegram bot token from BotFather.
- `DATABASE_URL` - SQLAlchemy async PostgreSQL URL. Use `127.0.0.1` for local Docker on Windows.
- `OPENAI_API_KEY` - optional for the cozy AI layer.
- `LOG_LEVEL` - application log level.
- `SQL_ECHO` - SQLAlchemy query logging toggle.
- `DEFAULT_TIMEZONE` - fallback timezone for couple reminders.
- `INVITE_CODE_TTL_HOURS` - invite code lifetime in hours.
- `RUN_MIGRATIONS` - run Alembic migrations before starting the bot container.

## Deployment Notes

The MVP is deployment-ready as a single polling bot process with PostgreSQL:

- Railway/Render: deploy from the Dockerfile, attach a PostgreSQL database, set the env vars above, and keep `RUN_MIGRATIONS=true`.
- VPS: use Docker Compose, keep `.env` outside Git, and run `docker compose up -d --build`.
- Do not run more than one polling bot instance for the same token at the same time.

## Architecture Guardrails

The code is intentionally kept in the `handlers -> services -> repositories` shape:

- handlers own Telegram UX only;
- services own business rules;
- repositories own database access;
- schedulers and notifications call services instead of embedding SQL.

Mately should stay small: short flows, clear buttons, and calm shared-household behavior over deep menus or heavy forms.
