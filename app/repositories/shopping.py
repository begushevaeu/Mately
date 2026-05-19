from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ShoppingItem

VISIBLE_SHOPPING_STATUSES = ("ACTIVE", "BOUGHT")


class ShoppingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, title: str, added_by: int) -> ShoppingItem:
        item = ShoppingItem(title=title, added_by=added_by, status="ACTIVE")
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_id(self, item_id: int) -> ShoppingItem | None:
        result = await self.session.execute(select(ShoppingItem).where(ShoppingItem.id == item_id))
        return result.scalar_one_or_none()

    async def list_visible_for_users(self, user_ids: list[int]) -> list[ShoppingItem]:
        result = await self.session.execute(
            select(ShoppingItem)
            .where(
                ShoppingItem.status.in_(VISIBLE_SHOPPING_STATUSES),
                self._scope_filter(user_ids),
            )
            .order_by(
                case(
                    (ShoppingItem.status == "ACTIVE", 0),
                    (ShoppingItem.status == "BOUGHT", 1),
                    else_=2,
                ),
                ShoppingItem.created_at,
                ShoppingItem.id,
            )
        )
        return list(result.scalars().all())

    async def mark_bought(self, item: ShoppingItem, *, completed_by: int, completed_at: datetime) -> ShoppingItem:
        item.status = "BOUGHT"
        item.completed_by = completed_by
        item.completed_at = completed_at
        item.archived_at = None
        await self.session.flush()
        return item

    async def archive_bought_before(
        self,
        *,
        user_ids: list[int],
        cutoff: datetime,
        archived_at: datetime,
    ) -> int:
        result = await self.session.execute(
            update(ShoppingItem)
            .where(
                ShoppingItem.status == "BOUGHT",
                ShoppingItem.archived_at.is_(None),
                ShoppingItem.completed_at.is_not(None),
                ShoppingItem.completed_at < cutoff,
                self._scope_filter(user_ids),
            )
            .values(status="ARCHIVED", archived_at=archived_at)
        )
        await self.session.flush()
        return result.rowcount or 0

    def _scope_filter(self, user_ids: list[int]):
        return or_(
            ShoppingItem.added_by.in_(user_ids),
            ShoppingItem.completed_by.in_(user_ids),
        )
