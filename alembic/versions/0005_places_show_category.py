"""Rename places walk category to show.

Revision ID: 0005_places_show_category
Revises: 0004_places
Create Date: 2026-05-20 16:35:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0005_places_show_category"
down_revision: str | None = "0004_places"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_CATEGORY_CHECK = (
    "category in ('RESTAURANT', 'CAFE', 'CINEMA', 'THEATRE', 'PARK', 'MUSEUM', "
    "'BAR', 'CONCERT', 'EXHIBITION', 'WALK', 'TRIP', 'OTHER')"
)
NEW_CATEGORY_CHECK = (
    "category in ('RESTAURANT', 'CAFE', 'CINEMA', 'THEATRE', 'PARK', 'MUSEUM', "
    "'BAR', 'CONCERT', 'EXHIBITION', 'SHOW', 'TRIP', 'OTHER')"
)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_place_items_place_item_category"), "place_items", type_="check")
    op.execute("update place_items set category = 'SHOW' where category = 'WALK'")
    op.create_check_constraint(
        op.f("ck_place_items_place_item_category"),
        "place_items",
        NEW_CATEGORY_CHECK,
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_place_items_place_item_category"), "place_items", type_="check")
    op.execute("update place_items set category = 'WALK' where category = 'SHOW'")
    op.create_check_constraint(
        op.f("ck_place_items_place_item_category"),
        "place_items",
        OLD_CATEGORY_CHECK,
    )
