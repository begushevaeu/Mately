from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_env_example_contains_required_runtime_settings() -> None:
    env_example = (PROJECT_ROOT / ".env.example").read_text(encoding="utf-8")

    for variable in (
        "BOT_TOKEN=",
        "DATABASE_URL=",
        "OPENAI_API_KEY=",
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
