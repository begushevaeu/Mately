FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY assets ./assets
COPY alembic.ini ./
COPY alembic ./alembic
COPY docker/entrypoint.sh ./docker/entrypoint.sh
RUN chmod +x ./docker/entrypoint.sh
RUN pip install --no-cache-dir .

ENTRYPOINT ["./docker/entrypoint.sh"]
CMD ["python", "-m", "app.main"]
