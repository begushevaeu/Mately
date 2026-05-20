FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY app ./app
COPY assets ./assets
COPY alembic.ini ./
COPY alembic ./alembic
RUN pip install --no-cache-dir .

CMD ["python", "-m", "app.main"]
