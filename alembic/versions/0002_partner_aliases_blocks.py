"""Partner aliases and chat blocks.

Revision ID: 0002_partner_aliases_blocks
Revises: 0001_initial_schema
Create Date: 2026-05-19 17:15:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_partner_aliases_blocks"
down_revision: str | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "partner_aliases",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("partner_user_id", sa.Integer(), nullable=False),
        sa.Column("emoji", sa.String(length=16), nullable=False),
        sa.Column("nominative", sa.String(length=64), nullable=False),
        sa.Column("genitive", sa.String(length=64), nullable=False),
        sa.Column("dative", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_partner_aliases_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["partner_user_id"],
            ["users.id"],
            name=op.f("fk_partner_aliases_partner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_partner_aliases")),
        sa.UniqueConstraint("owner_user_id", "partner_user_id", name="uq_partner_aliases_owner_partner"),
    )
    op.create_index(op.f("ix_partner_aliases_owner_user_id"), "partner_aliases", ["owner_user_id"], unique=False)
    op.create_index(op.f("ix_partner_aliases_partner_user_id"), "partner_aliases", ["partner_user_id"], unique=False)

    op.create_table(
        "chat_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("block_key", sa.String(length=64), nullable=False),
        sa.Column("message_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_chat_blocks_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chat_blocks")),
        sa.UniqueConstraint("user_id", "chat_id", "block_key", name="uq_chat_blocks_user_chat_block"),
    )
    op.create_index(op.f("ix_chat_blocks_user_id"), "chat_blocks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_chat_blocks_user_id"), table_name="chat_blocks")
    op.drop_table("chat_blocks")
    op.drop_index(op.f("ix_partner_aliases_partner_user_id"), table_name="partner_aliases")
    op.drop_index(op.f("ix_partner_aliases_owner_user_id"), table_name="partner_aliases")
    op.drop_table("partner_aliases")
