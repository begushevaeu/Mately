from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HANDLERS_DIR = PROJECT_ROOT / "app" / "bot" / "handlers"


def test_handlers_do_not_import_repositories_or_embed_sql() -> None:
    offenders: list[str] = []
    forbidden_fragments = (
        "from app.repositories",
        "import app.repositories",
        "session.execute",
        "select(",
    )

    for path in HANDLERS_DIR.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        if any(fragment in source for fragment in forbidden_fragments):
            offenders.append(str(path.relative_to(PROJECT_ROOT)))

    assert offenders == []
