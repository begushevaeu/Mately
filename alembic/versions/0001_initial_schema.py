"""Initial database schema.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-05-19 16:50:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_id", name="uq_users_telegram_id"),
    )

    op.create_table(
        "couples",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("invite_code", sa.String(length=32), nullable=False),
        sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("timezone", sa.String(length=64), server_default=sa.text("'Europe/Moscow'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_couples")),
        sa.UniqueConstraint("invite_code", name="uq_couples_invite_code"),
    )

    op.create_table(
        "couple_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("couple_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["couple_id"],
            ["couples.id"],
            name=op.f("fk_couple_members_couple_id_couples"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_couple_members_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_couple_members")),
        sa.UniqueConstraint("user_id", name="uq_couple_members_user_id"),
        sa.UniqueConstraint("user_id", "couple_id", name="uq_couple_members_user_couple"),
    )
    op.create_index(op.f("ix_couple_members_couple_id"), "couple_members", ["couple_id"], unique=False)

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("recurrence_type", sa.String(length=32), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'OPEN'"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "recurrence_type is null or recurrence_type in ('DAILY', 'WEEKLY', 'MONTHLY', 'CUSTOM')",
            name=op.f("ck_tasks_task_recurrence_type"),
        ),
        sa.CheckConstraint(
            "status in ('OPEN', 'ASSIGNED', 'COMPLETED', 'OVERDUE', 'ARCHIVED')",
            name=op.f("ck_tasks_task_status"),
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to"],
            ["users.id"],
            name=op.f("fk_tasks_assigned_to_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_tasks_created_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_assigned_to"), "tasks", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_tasks_created_by"), "tasks", ["created_by"], unique=False)
    op.create_index(op.f("ix_tasks_deadline"), "tasks", ["deadline"], unique=False)
    op.create_index(op.f("ix_tasks_status"), "tasks", ["status"], unique=False)

    op.create_table(
        "task_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "event_type in ('CREATED', 'ASSIGNED', 'COMPLETED', 'OVERDUE', 'ARCHIVED', 'UPDATED', 'RECURRENCE_CREATED')",
            name=op.f("ck_task_history_task_history_event_type"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_task_history_actor_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_task_history_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_history")),
    )
    op.create_index(op.f("ix_task_history_actor_id"), "task_history", ["actor_id"], unique=False)
    op.create_index(op.f("ix_task_history_task_id"), "task_history", ["task_id"], unique=False)

    op.create_table(
        "shopping_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=False),
        sa.Column("completed_by", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status in ('ACTIVE', 'BOUGHT', 'ARCHIVED')",
            name=op.f("ck_shopping_items_shopping_item_status"),
        ),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["users.id"],
            name=op.f("fk_shopping_items_added_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["completed_by"],
            ["users.id"],
            name=op.f("fk_shopping_items_completed_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shopping_items")),
    )
    op.create_index(op.f("ix_shopping_items_added_by"), "shopping_items", ["added_by"], unique=False)
    op.create_index(op.f("ix_shopping_items_archived_at"), "shopping_items", ["archived_at"], unique=False)
    op.create_index(op.f("ix_shopping_items_completed_by"), "shopping_items", ["completed_by"], unique=False)
    op.create_index(op.f("ix_shopping_items_status"), "shopping_items", ["status"], unique=False)

    op.create_table(
        "content_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'NOT_COMPLETED'"), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "category in ('BOOK', 'ANIME', 'MOVIE', 'CARTOON', 'SERIES', 'THEATRE', 'MUSICAL', 'GAME')",
            name=op.f("ck_content_items_content_item_category"),
        ),
        sa.CheckConstraint(
            "status in ('NOT_COMPLETED', 'COMPLETED')",
            name=op.f("ck_content_items_content_item_status"),
        ),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["users.id"],
            name=op.f("fk_content_items_added_by_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_content_items")),
    )
    op.create_index(op.f("ix_content_items_added_by"), "content_items", ["added_by"], unique=False)
    op.create_index(op.f("ix_content_items_category"), "content_items", ["category"], unique=False)
    op.create_index(op.f("ix_content_items_completed_at"), "content_items", ["completed_at"], unique=False)
    op.create_index(op.f("ix_content_items_status"), "content_items", ["status"], unique=False)

    op.create_table(
        "ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("emoji", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score between 1 and 10", name=op.f("ck_ratings_rating_score_range")),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content_items.id"],
            name=op.f("fk_ratings_content_id_content_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ratings_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ratings")),
        sa.UniqueConstraint("content_id", "user_id", name="uq_ratings_content_user"),
    )
    op.create_index(op.f("ix_ratings_content_id"), "ratings", ["content_id"], unique=False)
    op.create_index(op.f("ix_ratings_user_id"), "ratings", ["user_id"], unique=False)

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["content_id"],
            ["content_items.id"],
            name=op.f("fk_comments_content_id_content_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_comments_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_comments")),
    )
    op.create_index(op.f("ix_comments_content_id"), "comments", ["content_id"], unique=False)
    op.create_index(op.f("ix_comments_user_id"), "comments", ["user_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status in ('PENDING', 'SENT', 'FAILED', 'CANCELLED')",
            name=op.f("ck_notifications_notification_status"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_notifications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
    )
    op.create_index(op.f("ix_notifications_scheduled_at"), "notifications", ["scheduled_at"], unique=False)
    op.create_index(op.f("ix_notifications_status"), "notifications", ["status"], unique=False)
    op.create_index(op.f("ix_notifications_type"), "notifications", ["type"], unique=False)
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_type"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_status"), table_name="notifications")
    op.drop_index(op.f("ix_notifications_scheduled_at"), table_name="notifications")
    op.drop_table("notifications")

    op.drop_index(op.f("ix_comments_user_id"), table_name="comments")
    op.drop_index(op.f("ix_comments_content_id"), table_name="comments")
    op.drop_table("comments")

    op.drop_index(op.f("ix_ratings_user_id"), table_name="ratings")
    op.drop_index(op.f("ix_ratings_content_id"), table_name="ratings")
    op.drop_table("ratings")

    op.drop_index(op.f("ix_content_items_status"), table_name="content_items")
    op.drop_index(op.f("ix_content_items_completed_at"), table_name="content_items")
    op.drop_index(op.f("ix_content_items_category"), table_name="content_items")
    op.drop_index(op.f("ix_content_items_added_by"), table_name="content_items")
    op.drop_table("content_items")

    op.drop_index(op.f("ix_shopping_items_status"), table_name="shopping_items")
    op.drop_index(op.f("ix_shopping_items_completed_by"), table_name="shopping_items")
    op.drop_index(op.f("ix_shopping_items_archived_at"), table_name="shopping_items")
    op.drop_index(op.f("ix_shopping_items_added_by"), table_name="shopping_items")
    op.drop_table("shopping_items")

    op.drop_index(op.f("ix_task_history_task_id"), table_name="task_history")
    op.drop_index(op.f("ix_task_history_actor_id"), table_name="task_history")
    op.drop_table("task_history")

    op.drop_index(op.f("ix_tasks_status"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_deadline"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_created_by"), table_name="tasks")
    op.drop_index(op.f("ix_tasks_assigned_to"), table_name="tasks")
    op.drop_table("tasks")

    op.drop_index(op.f("ix_couple_members_couple_id"), table_name="couple_members")
    op.drop_table("couple_members")
    op.drop_table("couples")
    op.drop_table("users")
