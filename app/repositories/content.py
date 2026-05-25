from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Comment, ContentItem, Rating


class ContentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, couple_id: int, title: str, category: str, added_by: int) -> ContentItem:
        item = ContentItem(
            couple_id=couple_id,
            title=title,
            category=category,
            added_by=added_by,
            status="NOT_COMPLETED",
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_id(self, content_id: int, couple_id: int) -> ContentItem | None:
        result = await self.session.execute(
            select(ContentItem)
            .where(ContentItem.id == content_id, ContentItem.couple_id == couple_id)
            .options(selectinload(ContentItem.ratings), selectinload(ContentItem.comments))
        )
        return result.scalar_one_or_none()

    async def list_for_couple(self, couple_id: int) -> list[ContentItem]:
        result = await self.session.execute(
            select(ContentItem)
            .where(ContentItem.couple_id == couple_id)
            .options(selectinload(ContentItem.ratings), selectinload(ContentItem.comments))
            .order_by(ContentItem.status, ContentItem.category, ContentItem.title, ContentItem.id)
        )
        return list(result.scalars().all())

    async def mark_completed(self, item: ContentItem, *, completed_at: datetime) -> ContentItem:
        item.status = "COMPLETED"
        item.completed_at = completed_at
        await self.session.flush()
        return item

    async def upsert_rating(
        self,
        *,
        content_id: int,
        user_id: int,
        score: int,
        emoji: str | None,
    ) -> Rating:
        result = await self.session.execute(
            select(Rating).where(Rating.content_id == content_id, Rating.user_id == user_id)
        )
        rating = result.scalar_one_or_none()
        if rating is None:
            rating = Rating(content_id=content_id, user_id=user_id, score=score, emoji=emoji, response="RATED")
            self.session.add(rating)
        else:
            rating.score = score
            rating.emoji = emoji
            rating.response = "RATED"

        await self.session.flush()
        return rating

    async def upsert_not_acquainted(self, *, content_id: int, user_id: int) -> Rating:
        result = await self.session.execute(
            select(Rating).where(Rating.content_id == content_id, Rating.user_id == user_id)
        )
        rating = result.scalar_one_or_none()
        if rating is None:
            rating = Rating(
                content_id=content_id,
                user_id=user_id,
                score=None,
                emoji=None,
                response="NOT_ACQUAINTED",
            )
            self.session.add(rating)
        else:
            rating.score = None
            rating.emoji = None
            rating.response = "NOT_ACQUAINTED"

        await self.session.flush()
        return rating

    async def add_comment(self, *, content_id: int, user_id: int, text: str) -> Comment:
        comment = Comment(content_id=content_id, user_id=user_id, text=text)
        self.session.add(comment)
        await self.session.flush()
        return comment
