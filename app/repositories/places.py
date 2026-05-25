from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import PlaceComment, PlaceItem, PlaceRating


class PlaceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, couple_id: int, title: str, category: str, added_by: int) -> PlaceItem:
        item = PlaceItem(
            couple_id=couple_id,
            title=title,
            category=category,
            added_by=added_by,
            status="NOT_VISITED",
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_id(self, place_id: int, couple_id: int) -> PlaceItem | None:
        result = await self.session.execute(
            select(PlaceItem)
            .where(PlaceItem.id == place_id, PlaceItem.couple_id == couple_id)
            .options(selectinload(PlaceItem.ratings), selectinload(PlaceItem.comments))
        )
        return result.scalar_one_or_none()

    async def list_for_couple(self, couple_id: int) -> list[PlaceItem]:
        result = await self.session.execute(
            select(PlaceItem)
            .where(PlaceItem.couple_id == couple_id)
            .options(selectinload(PlaceItem.ratings), selectinload(PlaceItem.comments))
            .order_by(PlaceItem.status, PlaceItem.category, PlaceItem.title, PlaceItem.id)
        )
        return list(result.scalars().all())

    async def mark_visited(self, item: PlaceItem, *, visited_by: int, visited_at: datetime) -> PlaceItem:
        item.status = "VISITED"
        item.visited_by = visited_by
        item.visited_at = visited_at
        await self.session.flush()
        return item

    async def upsert_rating(self, *, place_id: int, user_id: int, score: int) -> PlaceRating:
        result = await self.session.execute(
            select(PlaceRating).where(PlaceRating.place_id == place_id, PlaceRating.user_id == user_id)
        )
        rating = result.scalar_one_or_none()
        if rating is None:
            rating = PlaceRating(place_id=place_id, user_id=user_id, score=score, response="RATED")
            self.session.add(rating)
        else:
            rating.score = score
            rating.response = "RATED"

        await self.session.flush()
        return rating

    async def upsert_not_acquainted(self, *, place_id: int, user_id: int) -> PlaceRating:
        result = await self.session.execute(
            select(PlaceRating).where(PlaceRating.place_id == place_id, PlaceRating.user_id == user_id)
        )
        rating = result.scalar_one_or_none()
        if rating is None:
            rating = PlaceRating(place_id=place_id, user_id=user_id, score=None, response="NOT_ACQUAINTED")
            self.session.add(rating)
        else:
            rating.score = None
            rating.response = "NOT_ACQUAINTED"

        await self.session.flush()
        return rating

    async def add_comment(self, *, place_id: int, user_id: int, text: str) -> PlaceComment:
        comment = PlaceComment(place_id=place_id, user_id=user_id, text=text)
        self.session.add(comment)
        await self.session.flush()
        return comment
