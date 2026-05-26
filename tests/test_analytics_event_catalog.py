from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_analytics_event_catalog_covers_required_domains_and_privacy_rules() -> None:
    catalog = (PROJECT_ROOT / "ANALYTICS_EVENTS.md").read_text(encoding="utf-8")

    for heading in (
        "## Product Questions",
        "## Privacy Boundaries",
        "## Event Table",
        "## Ingestion Plan",
    ):
        assert heading in catalog

    for event_name in (
        "onboarding_started",
        "task_completed",
        "shopping_item_bought",
        "content_completed",
        "place_visited",
        "notification_delivered",
        "bot_error_shown",
    ):
        assert f"`{event_name}`" in catalog

    for forbidden_detail in (
        "Raw Telegram user IDs",
        "invite codes",
        "task titles",
        "shopping item names",
        "content titles",
        "place names",
        "comments",
        "AI prompts",
        "AI responses",
    ):
        assert forbidden_detail in catalog


def test_analytics_event_table_rows_have_owner_trigger_properties_and_privacy_notes() -> None:
    catalog = (PROJECT_ROOT / "ANALYTICS_EVENTS.md").read_text(encoding="utf-8")
    event_table = catalog.split("## Event Table", maxsplit=1)[1].split("## Property Buckets", maxsplit=1)[0]
    table_lines = [
        line
        for line in event_table.splitlines()
        if line.startswith("| `") and not line.startswith("| ---")
    ]

    assert len(table_lines) >= 30
    for line in table_lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        assert len(cells) == 5
        assert all(cells)
