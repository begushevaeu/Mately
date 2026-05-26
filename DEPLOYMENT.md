# Mately Deployment

Last updated: 2026-05-25.

## Target

The first production target is a VPS.

Server:

- IP: `185.103.103.129`
- SSH user: `root`

Do not commit server passwords or production `.env` files. After first access, prefer SSH keys over password login.

## Production Shape

Run exactly one bot process for one Telegram bot token.

Services:

- `bot`: Docker image built from `docker/Dockerfile`.
- `db`: private PostgreSQL container.

The bot uses long polling, not a public HTTP server. Do not add extra replicas unless the bot is converted away from single-process polling.
Background scheduling also runs inside this single bot process with
APScheduler. See `SCHEDULING_DECISION.md` before adding Redis, Celery, or
separate workers.

## Required Variables

Create `.env.production` on the VPS from `.env.production.example`:

```text
BOT_TOKEN=<token from BotFather>
OPENAI_API_KEY=<optional>
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT_SECONDS=6
OPENAI_MAX_TOKENS=90
OPENAI_TEMPERATURE=0.55
LOG_LEVEL=INFO
SQL_ECHO=false
DEFAULT_TIMEZONE=Europe/Moscow
INVITE_CODE_TTL_HOURS=168
RUN_MIGRATIONS=true
POSTGRES_DB=mately
POSTGRES_USER=mately
POSTGRES_PASSWORD=<long random password>
```

`docker-compose.prod.yml` builds the internal `DATABASE_URL` from `POSTGRES_*` values and does not publish PostgreSQL to the internet.

## VPS Setup Checklist

1. Add an SSH key for root access.
2. Install Docker Engine and the Docker Compose plugin if they are missing.
3. Create `/opt/mately`.
4. Copy the repository files to `/opt/mately`.
5. Create `/opt/mately/.env.production` from `.env.production.example`.
6. Fill `BOT_TOKEN` and `POSTGRES_PASSWORD`.
7. Run `docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build`.
8. Confirm startup logs show Alembic migrations running.
9. Confirm there is only one active bot polling the Telegram token.
10. Create and restore-check a first database backup using `OPERATIONS.md`.

Useful commands:

```bash
cd /opt/mately
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.production -f docker-compose.prod.yml logs -f bot
docker compose --env-file .env.production -f docker-compose.prod.yml ps
```

## Backup And Export

Use `OPERATIONS.md` for the production backup command, local restore check, and
minimal export format decision. Backups are PostgreSQL custom-format dumps kept
outside Git; user-facing exports should use couple-scoped UTF-8 CSV files until
Google Sheets delivery is implemented.

## Smoke Test

After deployment:

1. Send `/start` to the bot.
2. Confirm onboarding opens for a fresh user.
3. Create a couple invite code.
4. Join from the partner account or test account.
5. Open the main menu.
6. Create one test task.
7. Restart the VPS bot service.
8. Confirm the task still exists after restart.
9. Confirm logs do not show migration, database, or Telegram polling errors.

## Rollback

If deployment fails:

1. Stop the VPS bot service.
2. Keep the PostgreSQL database intact.
3. Fix environment variables or build errors.
4. Redeploy with one bot replica.

Do not run the local bot and VPS bot with the same token at the same time.
