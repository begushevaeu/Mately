from __future__ import annotations

from datetime import datetime

from sqlalchemy import case, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ShoppingItem

VISIBLE_SHOPPING_STATUSES = ("ACTIVE", "BOUGHT")


class ShoppingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, couple_id: int, title: str, added_by: int) -> ShoppingItem:
        item = ShoppingItem(couple_id=couple_id, title=title, added_by=added_by, status="ACTIVE")
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_id(self, item_id: int, couple_id: int) -> ShoppingItem | None:
        result = await self.session.execute(
            select(ShoppingItem).where(ShoppingItem.id == item_id, ShoppingItem.couple_id == couple_id)
        )
        return result.scalar_one_or_none()

    async def list_visible_for_couple(self, couple_id: int) -> list[ShoppingItem]:
        result = await self.session.execute(
            select(ShoppingItem)
            .where(
                ShoppingItem.couple_id == couple_id,
                ShoppingItem.status.in_(VISIBLE_SHOPPING_STATUSES),
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

    async def list_for_couple(self, couple_id: int) -> list[ShoppingItem]:
        result = await self.session.execute(
            select(ShoppingItem)
            .where(ShoppingItem.couple_id == couple_id)
            .order_by(ShoppingItem.completed_at, ShoppingItem.created_at, ShoppingItem.id)
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
        couple_id: int,
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
                ShoppingItem.couple_id == couple_id,
            )
            .values(status="ARCHIVED", archived_at=archived_at)
        )
        await self.session.flush()
        return result.rowcount or 0
