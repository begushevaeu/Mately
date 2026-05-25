from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.models import Base


EXPECTED_TABLES = {
    "chat_blocks",
    "users",
    "couples",
    "couple_members",
    "couple_reminder_settings",
    "partner_aliases",
    "tasks",
    "task_history",
    "shopping_items",
    "content_items",
    "ratings",
    "comments",
    "place_items",
    "place_ratings",
    "place_comments",
    "notifications",
}


def constraint_names(table_name: str, constraint_type: type) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, constraint_type) and constraint.name is not None
    }


def index_names(table_name: str) -> set[str]:
    return {index.name for index in Base.metadata.tables[table_name].indexes}


def test_core_tables_are_registered() -> None:
    assert set(Base.metadata.tables) == EXPECTED_TABLES


def test_shared_tables_are_explicitly_scoped_to_couples() -> None:
    scoped_tables = {
        "tasks": "ix_tasks_couple_status_deadline",
        "shopping_items": "ix_shopping_items_couple_status_created",
        "content_items": "ix_content_items_couple_status_category",
        "place_items": "ix_place_items_couple_status_category",
        "notifications": "ix_notifications_couple_status_scheduled",
    }

    for table_name, index_name in scoped_tables.items():
        table = Base.metadata.tables[table_name]
        assert "couple_id" in table.columns
        assert table.columns["couple_id"].nullable is False
        assert index_name in index_names(table_name)
        assert any(
            isinstance(constraint, ForeignKeyConstraint)
            and any(element.column.table.name == "couples" for element in constraint.elements)
            for constraint in table.constraints
        )


def test_core_uniqueness_constraints_are_declared() -> None:
    assert "uq_users_telegram_id" in constraint_names("users", UniqueConstraint)
    assert "uq_couples_invite_code" in constraint_names("couples", UniqueConstraint)
    assert "uq_couple_members_user_id" in constraint_names("couple_members", UniqueConstraint)
    assert "uq_couple_reminder_settings_couple_id" in constraint_names("couple_reminder_settings", UniqueConstraint)
    assert "uq_partner_aliases_owner_partner" in constraint_names("partner_aliases", UniqueConstraint)
    assert "uq_chat_blocks_user_chat_block" in constraint_names("chat_blocks", UniqueConstraint)
    assert "uq_ratings_content_user" in constraint_names("ratings", UniqueConstraint)
    assert "uq_place_ratings_place_user" in constraint_names("place_ratings", UniqueConstraint)
    assert "uq_notifications_dedupe_key" in constraint_names("notifications", UniqueConstraint)


def test_status_and_rating_check_constraints_are_declared() -> None:
    assert "ck_tasks_task_status" in constraint_names("tasks", CheckConstraint)
    assert "ck_tasks_task_recurrence_interval_days_positive" in constraint_names("tasks", CheckConstraint)
    assert "ck_shopping_items_shopping_item_status" in constraint_names("shopping_items", CheckConstraint)
    assert "ck_content_items_content_item_status" in constraint_names("content_items", CheckConstraint)
    assert "ck_ratings_rating_response" in constraint_names("ratings", CheckConstraint)
    assert "ck_ratings_rating_response_score" in constraint_names("ratings", CheckConstraint)
    assert "ck_place_items_place_item_status" in constraint_names("place_items", CheckConstraint)
    assert "ck_place_ratings_place_rating_response" in constraint_names("place_ratings", CheckConstraint)
    assert "ck_place_ratings_place_rating_response_score" in constraint_names("place_ratings", CheckConstraint)
    assert "ck_notifications_notification_status" in constraint_names("notifications", CheckConstraint)


def test_foreign_keys_have_explicit_ondelete_rules() -> None:
    for table_name in EXPECTED_TABLES - {"users", "couples"}:
        for constraint in Base.metadata.tables[table_name].constraints:
            if isinstance(constraint, ForeignKeyConstraint):
                assert constraint.name is not None
                assert constraint.ondelete is not None


def test_shopping_and_notification_fields_support_required_flows() -> None:
    shopping_columns = Base.metadata.tables["shopping_items"].columns
    notification_columns = Base.metadata.tables["notifications"].columns
    task_columns = Base.metadata.tables["tasks"].columns

    assert "recurrence_interval_days" in task_columns
    assert {"status", "completed_at", "archived_at"}.issubset(shopping_columns.keys())
    assert {"status", "scheduled_at", "delivered_at", "dedupe_key"}.issubset(notification_columns.keys())
    assert "ix_shopping_items_archived_at" in index_names("shopping_items")
    assert "ix_notifications_scheduled_at" in index_names("notifications")


def test_rating_response_columns_allow_non_numeric_responses() -> None:
    rating_columns = Base.metadata.tables["ratings"].columns
    place_rating_columns = Base.metadata.tables["place_ratings"].columns

    assert "response" in rating_columns
    assert rating_columns["response"].nullable is False
    assert rating_columns["score"].nullable is True
    assert "response" in place_rating_columns
    assert place_rating_columns["response"].nullable is False
    assert place_rating_columns["score"].nullable is True


def test_couple_reminder_settings_support_scheduler_controls() -> None:
    columns = Base.metadata.tables["couple_reminder_settings"].columns

    assert {
        "couple_id",
        "morning_enabled",
        "morning_time",
        "evening_enabled",
        "evening_time",
        "reminders_paused",
    }.issubset(columns.keys())
    assert columns["couple_id"].nullable is False
    assert "ix_couple_reminder_settings_couple_id" in index_names("couple_reminder_settings")
