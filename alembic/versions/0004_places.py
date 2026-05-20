"""Places list, ratings, and comments.

Revision ID: 0004_places
Revises: 0003_task_recurrence_interval
Create Date: 2026-05-20 16:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_places"
down_revision: str | None = "0003_task_recurrence_interval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "place_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'NOT_VISITED'"), nullable=False),
        sa.Column("added_by", sa.Integer(), nullable=False),
        sa.Column("visited_by", sa.Integer(), nullable=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "category in ('RESTAURANT', 'CAFE', 'CINEMA', 'THEATRE', 'PARK', 'MUSEUM', 'BAR', 'CONCERT', 'EXHIBITION', 'WALK', 'TRIP', 'OTHER')",
            name=op.f("ck_place_items_place_item_category"),
        ),
        sa.CheckConstraint(
            "status in ('NOT_VISITED', 'VISITED')",
            name=op.f("ck_place_items_place_item_status"),
        ),
        sa.ForeignKeyConstraint(
            ["added_by"],
            ["users.id"],
            name=op.f("fk_place_items_added_by_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["visited_by"],
            ["users.id"],
            name=op.f("fk_place_items_visited_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_items")),
    )
    op.create_index(op.f("ix_place_items_added_by"), "place_items", ["added_by"], unique=False)
    op.create_index(op.f("ix_place_items_category"), "place_items", ["category"], unique=False)
    op.create_index(op.f("ix_place_items_status"), "place_items", ["status"], unique=False)
    op.create_index(op.f("ix_place_items_visited_at"), "place_items", ["visited_at"], unique=False)
    op.create_index(op.f("ix_place_items_visited_by"), "place_items", ["visited_by"], unique=False)

    op.create_table(
        "place_ratings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("score between 1 and 10", name=op.f("ck_place_ratings_place_rating_score_range")),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["place_items.id"],
            name=op.f("fk_place_ratings_place_id_place_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_place_ratings_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_ratings")),
        sa.UniqueConstraint("place_id", "user_id", name="uq_place_ratings_place_user"),
    )
    op.create_index(op.f("ix_place_ratings_place_id"), "place_ratings", ["place_id"], unique=False)
    op.create_index(op.f("ix_place_ratings_user_id"), "place_ratings", ["user_id"], unique=False)

    op.create_table(
        "place_comments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("place_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["place_id"],
            ["place_items.id"],
            name=op.f("fk_place_comments_place_id_place_items"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_place_comments_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_comments")),
    )
    op.create_index(op.f("ix_place_comments_place_id"), "place_comments", ["place_id"], unique=False)
    op.create_index(op.f("ix_place_comments_user_id"), "place_comments", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_place_comments_user_id"), table_name="place_comments")
    op.drop_index(op.f("ix_place_comments_place_id"), table_name="place_comments")
    op.drop_table("place_comments")

    op.drop_index(op.f("ix_place_ratings_user_id"), table_name="place_ratings")
    op.drop_index(op.f("ix_place_ratings_place_id"), table_name="place_ratings")
    op.drop_table("place_ratings")

    op.drop_index(op.f("ix_place_items_visited_by"), table_name="place_items")
    op.drop_index(op.f("ix_place_items_visited_at"), table_name="place_items")
    op.drop_index(op.f("ix_place_items_status"), table_name="place_items")
    op.drop_index(op.f("ix_place_items_category"), table_name="place_items")
    op.drop_index(op.f("ix_place_items_added_by"), table_name="place_items")
    op.drop_table("place_items")
