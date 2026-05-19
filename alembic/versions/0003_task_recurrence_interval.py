"""Task custom recurrence interval.

Revision ID: 0003_task_recurrence_interval
Revises: 0002_partner_aliases_blocks
Create Date: 2026-05-19 18:20:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_task_recurrence_interval"
down_revision: str | None = "0002_partner_aliases_blocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("recurrence_interval_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        op.f("ck_tasks_task_recurrence_interval_days_positive"),
        "tasks",
        "recurrence_interval_days is null or recurrence_interval_days > 0",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_tasks_task_recurrence_interval_days_positive"), "tasks", type_="check")
    op.drop_column("tasks", "recurrence_interval_days")
