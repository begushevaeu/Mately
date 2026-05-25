"""Add explicit couple scope to shared entities.

Revision ID: 0006_couple_scope
Revises: 0005_places_show_category
Create Date: 2026-05-25 19:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_couple_scope"
down_revision: str | None = "0005_places_show_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES = ("tasks", "shopping_items", "content_items", "place_items", "notifications")


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("couple_id", sa.Integer(), nullable=True))

    op.execute(
        """
        update tasks
        set couple_id = couple_members.couple_id
        from couple_members
        where tasks.created_by = couple_members.user_id
        """
    )
    op.execute(
        """
        update shopping_items
        set couple_id = couple_members.couple_id
        from couple_members
        where shopping_items.added_by = couple_members.user_id
        """
    )
    op.execute(
        """
        update content_items
        set couple_id = couple_members.couple_id
        from couple_members
        where content_items.added_by = couple_members.user_id
        """
    )
    op.execute(
        """
        update place_items
        set couple_id = couple_members.couple_id
        from couple_members
        where place_items.added_by = couple_members.user_id
        """
    )
    op.execute(
        """
        update notifications
        set couple_id = couple_members.couple_id
        from couple_members
        where notifications.user_id = couple_members.user_id
        """
    )
    op.execute(
        """
        do $$
        begin
          if exists (select 1 from tasks where couple_id is null) then
            raise exception 'cannot backfill tasks.couple_id';
          end if;
          if exists (select 1 from shopping_items where couple_id is null) then
            raise exception 'cannot backfill shopping_items.couple_id';
          end if;
          if exists (select 1 from content_items where couple_id is null) then
            raise exception 'cannot backfill content_items.couple_id';
          end if;
          if exists (select 1 from place_items where couple_id is null) then
            raise exception 'cannot backfill place_items.couple_id';
          end if;
          if exists (select 1 from notifications where couple_id is null) then
            raise exception 'cannot backfill notifications.couple_id';
          end if;
        end $$;
        """
    )

    for table in TABLES:
        op.alter_column(table, "couple_id", nullable=False)
        op.create_foreign_key(
            op.f(f"fk_{table}_couple_id_couples"),
            table,
            "couples",
            ["couple_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_index("ix_tasks_couple_status_deadline", "tasks", ["couple_id", "status", "deadline"])
    op.create_index(
        "ix_shopping_items_couple_status_created",
        "shopping_items",
        ["couple_id", "status", "created_at"],
    )
    op.create_index(
        "ix_content_items_couple_status_category",
        "content_items",
        ["couple_id", "status", "category"],
    )
    op.create_index(
        "ix_place_items_couple_status_category",
        "place_items",
        ["couple_id", "status", "category"],
    )
    op.create_index(
        "ix_notifications_couple_status_scheduled",
        "notifications",
        ["couple_id", "status", "scheduled_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_couple_status_scheduled", table_name="notifications")
    op.drop_index("ix_place_items_couple_status_category", table_name="place_items")
    op.drop_index("ix_content_items_couple_status_category", table_name="content_items")
    op.drop_index("ix_shopping_items_couple_status_created", table_name="shopping_items")
    op.drop_index("ix_tasks_couple_status_deadline", table_name="tasks")

    for table in reversed(TABLES):
        op.drop_constraint(op.f(f"fk_{table}_couple_id_couples"), table, type_="foreignkey")
        op.drop_column(table, "couple_id")
