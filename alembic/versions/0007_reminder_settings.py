"""Add couple reminder settings.

Revision ID: 0007_reminder_settings
Revises: 0006_couple_scope
Create Date: 2026-05-25 21:10:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_reminder_settings"
down_revision: str | None = "0006_couple_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "couple_reminder_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("couple_id", sa.Integer(), nullable=False),
        sa.Column("morning_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("morning_time", sa.Time(), server_default=sa.text("'09:00:00'"), nullable=False),
        sa.Column("evening_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("evening_time", sa.Time(), server_default=sa.text("'21:00:00'"), nullable=False),
        sa.Column("reminders_paused", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["couple_id"],
            ["couples.id"],
            name=op.f("fk_couple_reminder_settings_couple_id_couples"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_couple_reminder_settings")),
        sa.UniqueConstraint("couple_id", name="uq_couple_reminder_settings_couple_id"),
    )
    op.create_index(
        op.f("ix_couple_reminder_settings_couple_id"),
        "couple_reminder_settings",
        ["couple_id"],
        unique=False,
    )
    op.execute(
        """
        insert into couple_reminder_settings (couple_id)
        select id from couples
        on conflict do nothing
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_couple_reminder_settings_couple_id"), table_name="couple_reminder_settings")
    op.drop_table("couple_reminder_settings")
