#!/bin/sh
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
  python -m alembic upgrade head
fi

exec "$@"
