from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint

from app.models import Base


EXPECTED_TABLES = {
    "users",
    "couples",
    "couple_members",
    "tasks",
    "task_history",
    "shopping_items",
    "content_items",
    "ratings",
    "comments",
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


def test_mvp_shared_tables_do_not_have_direct_couple_id_yet() -> None:
    deferred_tables = {"tasks", "shopping_items", "content_items", "notifications"}

    for table_name in deferred_tables:
        assert "couple_id" not in Base.metadata.tables[table_name].columns


def test_core_uniqueness_constraints_are_declared() -> None:
    assert "uq_users_telegram_id" in constraint_names("users", UniqueConstraint)
    assert "uq_couples_invite_code" in constraint_names("couples", UniqueConstraint)
    assert "uq_couple_members_user_id" in constraint_names("couple_members", UniqueConstraint)
    assert "uq_ratings_content_user" in constraint_names("ratings", UniqueConstraint)
    assert "uq_notifications_dedupe_key" in constraint_names("notifications", UniqueConstraint)


def test_status_and_rating_check_constraints_are_declared() -> None:
    assert "ck_tasks_task_status" in constraint_names("tasks", CheckConstraint)
    assert "ck_shopping_items_shopping_item_status" in constraint_names("shopping_items", CheckConstraint)
    assert "ck_content_items_content_item_status" in constraint_names("content_items", CheckConstraint)
    assert "ck_ratings_rating_score_range" in constraint_names("ratings", CheckConstraint)
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

    assert {"status", "completed_at", "archived_at"}.issubset(shopping_columns.keys())
    assert {"status", "scheduled_at", "delivered_at", "dedupe_key"}.issubset(notification_columns.keys())
    assert "ix_shopping_items_archived_at" in index_names("shopping_items")
    assert "ix_notifications_scheduled_at" in index_names("notifications")
