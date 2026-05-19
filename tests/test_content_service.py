from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.models import ContentItem, Couple, CoupleMember, PartnerAlias, Rating, User
from app.services.content import (
    ContentCategory,
    ContentListFilter,
    ContentService,
    apply_content_filter,
    average_rating,
    completed_since_for_period,
    content_summary_counts,
)


@dataclass(slots=True)
class FakeCoupleRepository:
    couple: Couple
    members: list[User]

    async def get_membership(self, user_id: int) -> CoupleMember | None:
        if user_id not in [member.id for member in self.members]:
            return None

        membership = CoupleMember(id=user_id, user_id=user_id, couple_id=self.couple.id)
        membership.couple = self.couple
        return membership

    async def get_users_for_couple(self, couple_id: int) -> list[User]:
        if couple_id != self.couple.id:
            return []
        return self.members


@dataclass(slots=True)
class FakeContentRepository:
    items: dict[int, ContentItem] = field(default_factory=dict)
    ratings: list[Rating] = field(default_factory=list)
    next_id: int = 1
    next_rating_id: int = 1

    async def create(self, *, title: str, category: str, added_by: int) -> ContentItem:
        item = ContentItem(id=self.next_id, title=title, category=category, added_by=added_by, status="NOT_COMPLETED")
        self.next_id += 1
        self.items[item.id] = item
        return item

    async def get_by_id(self, content_id: int) -> ContentItem | None:
        item = self.items.get(content_id)
        if item is not None:
            item.ratings = [rating for rating in self.ratings if rating.content_id == item.id]
        return item

    async def list_for_users(self, user_ids: list[int]) -> list[ContentItem]:
        items = [item for item in self.items.values() if item.added_by in user_ids]
        for item in items:
            item.ratings = [rating for rating in self.ratings if rating.content_id == item.id]
        return items

    async def mark_completed(self, item: ContentItem, *, completed_at: datetime) -> ContentItem:
        item.status = "COMPLETED"
        item.completed_at = completed_at
        return item

    async def upsert_rating(self, *, content_id: int, user_id: int, score: int, emoji: str | None) -> Rating:
        rating = next(
            (rating for rating in self.ratings if rating.content_id == content_id and rating.user_id == user_id),
            None,
        )
        if rating is None:
            rating = Rating(
                id=self.next_rating_id,
                content_id=content_id,
                user_id=user_id,
                score=score,
                emoji=emoji,
            )
            self.next_rating_id += 1
            self.ratings.append(rating)
        else:
            rating.score = score
            rating.emoji = emoji
        return rating


@dataclass(slots=True)
class FakePartnerAliasRepository:
    aliases: dict[tuple[int, int], PartnerAlias] = field(default_factory=dict)

    async def get(self, owner_user_id: int, partner_user_id: int):
        return self.aliases.get((owner_user_id, partner_user_id))


def build_service() -> tuple[ContentService, User, User, FakeContentRepository]:
    creator = User(id=1, telegram_id=100, username="one", first_name="One")
    partner = User(id=2, telegram_id=200, username="two", first_name="Two")
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")
    content_repository = FakeContentRepository()
    service = ContentService(
        couples=FakeCoupleRepository(couple=couple, members=[creator, partner]),
        content=content_repository,
        aliases=FakePartnerAliasRepository(),
    )
    return service, creator, partner, content_repository


@pytest.mark.asyncio
async def test_content_can_be_added_completed_and_rated() -> None:
    service, creator, partner, _ = build_service()

    item = await service.add_item(creator, category=ContentCategory.MOVIE, title=" Интерстеллар ")
    completed = await service.complete_item(partner, item.id)
    rating = await service.save_rating(partner, content_id=item.id, score=10, emoji="🔥")
    _, items = await service.list_items(creator)

    assert item.title == "Интерстеллар"
    assert completed.item.status == "COMPLETED"
    assert completed.notification_user is creator
    assert completed.notification_text == "Two отметил(а) «Интерстеллар» как завершённое. Хочешь поставить оценку?"
    assert rating.score == 10
    assert rating.emoji == "🔥"
    assert items == [item]
    assert average_rating(items[0]) == 10


@pytest.mark.asyncio
async def test_content_filters_by_status_category_and_rating() -> None:
    service, creator, partner, content_repository = build_service()
    movie = await service.add_item(creator, category=ContentCategory.MOVIE, title="Фильм")
    book = await service.add_item(partner, category=ContentCategory.BOOK, title="Книга")
    game = await service.add_item(creator, category=ContentCategory.GAME, title="Игра")
    movie.status = "COMPLETED"
    movie.completed_at = datetime(2026, 5, 19, 10, 0, tzinfo=timezone.utc)
    book.status = "COMPLETED"
    book.completed_at = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
    await content_repository.upsert_rating(content_id=movie.id, user_id=creator.id, score=9, emoji="🔥")
    await content_repository.upsert_rating(content_id=book.id, user_id=creator.id, score=6, emoji="😍")

    _, completed_items = await service.list_items(creator, ContentListFilter(status="COMPLETED"))
    _, movie_items = await service.list_items(creator, ContentListFilter(category=ContentCategory.MOVIE))
    _, high_rated_items = await service.list_items(creator, ContentListFilter(min_rating=8))

    assert completed_items == [book, movie]
    assert movie_items == [movie]
    assert high_rated_items == [movie]
    assert content_summary_counts([movie, book, game]) == (1, 2)


def test_content_date_filter_uses_couple_timezone() -> None:
    cutoff = completed_since_for_period(
        "Europe/Moscow",
        "today",
        now=datetime(2026, 5, 19, 21, 5, tzinfo=timezone.utc),
    )

    assert cutoff == datetime(2026, 5, 19, 21, 0, tzinfo=timezone.utc)


def test_apply_content_filter_excludes_unrated_items_from_rating_filters() -> None:
    rated = ContentItem(id=1, title="A", category="MOVIE", added_by=1, status="COMPLETED")
    unrated = ContentItem(id=2, title="B", category="MOVIE", added_by=1, status="COMPLETED")
    rated.ratings = [Rating(content_id=1, user_id=1, score=8, emoji=None)]

    assert apply_content_filter([rated, unrated], ContentListFilter(min_rating=8)) == [rated]
