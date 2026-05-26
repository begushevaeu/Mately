# Mately Operations Runbook

This runbook covers the simple backup and export path for the VPS deployment.
It intentionally keeps secrets out of commands, logs, and Git. Production
values stay in `/opt/mately/.env.production`.

## Database Backup

Run on the VPS from `/opt/mately`:

```bash
cd /opt/mately
mkdir -p backups
BACKUP_FILE="backups/mately-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner --no-acl' > "$BACKUP_FILE"
test -s "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE"
ls -lh "$BACKUP_FILE"
```

The output is a PostgreSQL custom-format dump. It is suitable for `pg_restore`
and should be copied to a private location outside the repository after it is
created.

## Local Restore Check

Use a restore check before trusting a backup. The commands below restore into a
separate local database named `mately_restore`, so the normal local `mately`
database is not overwritten.

```bash
docker compose up -d db
docker compose cp backups/mately-YYYYMMDDTHHMMSSZ.dump db:/tmp/mately.dump
docker compose exec -T db sh -c 'dropdb -U mately --if-exists mately_restore'
docker compose exec -T db sh -c 'createdb -U mately mately_restore'
docker compose exec -T db sh -c 'pg_restore -U mately -d mately_restore --clean --if-exists /tmp/mately.dump'
docker compose exec -T db sh -c 'psql -U mately -d mately_restore -c "select count(*) as users_count from users;"'
```

To inspect the restored app locally, point a temporary local environment at
`postgresql+asyncpg://mately:mately@127.0.0.1:5432/mately_restore` and start the
bot with a test token.

## Production Restore Outline

Production restore is intentionally manual:

1. Confirm the target dump is private and recent.
2. Stop the bot service so polling and writes are paused.
3. Copy the dump into the database container with `docker compose cp`.
4. Restore with `pg_restore --clean --if-exists` into the configured production database.
5. Start the bot service and check logs.

Do not run production restore while another bot instance is polling the same
Telegram token.

## Minimal Export Format

For operational backups, use the PostgreSQL dump above. It preserves all tables,
constraints, and IDs.

For user-facing exports, the current fallback format is a ZIP archive delivered
by the bot from **Дополнительно -> Экспорт**. The archive contains UTF-8 CSV
files scoped to one couple only:

- `content.csv`: title, category, status, completed_at, average_rating, reactions, comments_count.
- `places.csv`: title, category, status, visited_at, average_rating, comments_count, not_acquainted_count.

Do not include bot tokens, OpenAI keys, database URLs, invite codes, raw
Telegram IDs, or cross-couple rows in user-facing exports. Google Sheets can be
added later as a delivery option when credentials and sharing rules are decided,
but CSV remains the safe fallback.
