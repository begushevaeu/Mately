"""Add non-numeric rating responses.

Revision ID: 0008_rating_responses
Revises: 0007_reminder_settings
Create Date: 2026-05-25 23:30:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_rating_responses"
down_revision: str | None = "0007_reminder_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_ratings_rating_score_range"), "ratings", type_="check")
    op.drop_constraint(op.f("ck_place_ratings_place_rating_score_range"), "place_ratings", type_="check")

    op.add_column("ratings", sa.Column("response", sa.String(length=32), server_default="RATED", nullable=False))
    op.add_column(
        "place_ratings",
        sa.Column("response", sa.String(length=32), server_default="RATED", nullable=False),
    )
    op.alter_column("ratings", "score", existing_type=sa.Integer(), nullable=True)
    op.alter_column("place_ratings", "score", existing_type=sa.Integer(), nullable=True)

    op.create_check_constraint(
        op.f("ck_ratings_rating_response"),
        "ratings",
        "response in ('RATED', 'NOT_ACQUAINTED')",
    )
    op.create_check_constraint(
        op.f("ck_ratings_rating_response_score"),
        "ratings",
        "(response = 'RATED' and score between 1 and 10) "
        "or (response = 'NOT_ACQUAINTED' and score is null and emoji is null)",
    )
    op.create_check_constraint(
        op.f("ck_place_ratings_place_rating_response"),
        "place_ratings",
        "response in ('RATED', 'NOT_ACQUAINTED')",
    )
    op.create_check_constraint(
        op.f("ck_place_ratings_place_rating_response_score"),
        "place_ratings",
        "(response = 'RATED' and score between 1 and 10) "
        "or (response = 'NOT_ACQUAINTED' and score is null)",
    )


def downgrade() -> None:
    op.execute("delete from ratings where response = 'NOT_ACQUAINTED'")
    op.execute("delete from place_ratings where response = 'NOT_ACQUAINTED'")

    op.drop_constraint(op.f("ck_place_ratings_place_rating_response_score"), "place_ratings", type_="check")
    op.drop_constraint(op.f("ck_place_ratings_place_rating_response"), "place_ratings", type_="check")
    op.drop_constraint(op.f("ck_ratings_rating_response_score"), "ratings", type_="check")
    op.drop_constraint(op.f("ck_ratings_rating_response"), "ratings", type_="check")

    op.alter_column("place_ratings", "score", existing_type=sa.Integer(), nullable=False)
    op.alter_column("ratings", "score", existing_type=sa.Integer(), nullable=False)
    op.drop_column("place_ratings", "response")
    op.drop_column("ratings", "response")

    op.create_check_constraint(
        op.f("ck_place_ratings_place_rating_score_range"),
        "place_ratings",
        "score between 1 and 10",
    )
    op.create_check_constraint(op.f("ck_ratings_rating_score_range"), "ratings", "score between 1 and 10")
