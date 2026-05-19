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

## Required Environment Variables

- `BOT_TOKEN` - Telegram bot token from BotFather.
- `DATABASE_URL` - SQLAlchemy async PostgreSQL URL. Use `127.0.0.1` for local Docker on Windows.
- `OPENAI_API_KEY` - optional for the cozy AI layer.
- `LOG_LEVEL` - application log level.
- `SQL_ECHO` - SQLAlchemy query logging toggle.
- `DEFAULT_TIMEZONE` - fallback timezone for couple reminders.
