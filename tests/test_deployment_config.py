from pathlib import Path

from app.core.config import Settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_env_example_contains_required_runtime_settings() -> None:
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    for variable in (
        "BOT_TOKEN=",
        "DATABASE_URL=",
        "OPENAI_API_KEY=",
        "OPENAI_MODEL=",
        "OPENAI_TIMEOUT_SECONDS=",
        "OPENAI_MAX_TOKENS=",
        "OPENAI_TEMPERATURE=",
        "LOG_LEVEL=",
        "SQL_ECHO=",
        "DEFAULT_TIMEZONE=",
        "INVITE_CODE_TTL_HOURS=",
        "RUN_MIGRATIONS=",
    ):
        assert variable in env_example


def test_docker_entrypoint_runs_migrations_before_bot() -> None:
    dockerfile = (PROJECT_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    entrypoint = (PROJECT_ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")

    assert 'ENTRYPOINT ["./docker/entrypoint.sh"]' in dockerfile
    assert "python -m alembic upgrade head" in entrypoint
    assert 'CMD ["python", "-m", "app.main"]' in dockerfile


def test_compose_waits_for_database_health() -> None:
    compose = (PROJECT_ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "condition: service_healthy" in compose
    assert "pg_isready -U mately -d mately" in compose


def test_production_compose_keeps_database_private() -> None:
    compose = (PROJECT_ROOT / "docker-compose.prod.yml").read_text(encoding="utf-8")

    assert "docker/Dockerfile" in compose
    assert "POSTGRES_PASSWORD is required" in compose
    assert "postgres_data:/var/lib/postgresql/data" in compose
    assert "5432:5432" not in compose


def test_operations_runbook_documents_backup_restore_and_export_without_secrets() -> None:
    runbook = (PROJECT_ROOT / "OPERATIONS.md").read_text(encoding="utf-8")
    deployment = (PROJECT_ROOT / "DEPLOYMENT.md").read_text(encoding="utf-8")
    gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")

    assert "pg_dump" in runbook
    assert "--format=custom" in runbook
    assert "pg_restore" in runbook
    assert "mately_restore" in runbook
    assert "content.csv" in runbook
    assert "places.csv" in runbook
    assert "OPERATIONS.md" in deployment
    assert "backups/" in gitignore
    assert "exports/" in gitignore
    assert "*.dump" in gitignore
    assert "BOT_TOKEN=" not in runbook
    assert "OPENAI_API_KEY=" not in runbook
    assert "POSTGRES_PASSWORD=" not in runbook


def test_managed_postgres_url_is_normalized_for_async_sqlalchemy() -> None:
    settings = Settings.model_validate(
        {"DATABASE_URL": "postgresql://user:password@example.internal:5432/mately"}
    )

    assert settings.database_url == "postgresql+asyncpg://user:password@example.internal:5432/mately"


def test_ai_runtime_settings_are_configurable_and_bounded() -> None:
    settings = Settings.model_validate(
        {
            "OPENAI_MODEL": " custom-model ",
            "OPENAI_TIMEOUT_SECONDS": 45,
            "OPENAI_MAX_TOKENS": 500,
            "OPENAI_TEMPERATURE": 2,
        }
    )

    assert settings.openai_model == "custom-model"
    assert settings.openai_timeout_seconds == 30
    assert settings.openai_max_tokens == 200
    assert settings.openai_temperature == 1.2
