from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.models import Comment, ContentItem, Couple, CoupleMember, PartnerAlias, Rating, User
from app.notifications.cats import CatNotificationType
from app.services.content import (
    ContentCategory,
    ContentListFilter,
    ContentService,
    ContentServiceError,
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
    comments: list[Comment] = field(default_factory=list)
    next_id: int = 1
    next_rating_id: int = 1
    next_comment_id: int = 1

    async def create(self, *, couple_id: int, title: str, category: str, added_by: int) -> ContentItem:
        item = ContentItem(
            id=self.next_id,
            couple_id=couple_id,
            title=title,
            category=category,
            added_by=added_by,
            status="NOT_COMPLETED",
        )
        self.next_id += 1
        self.items[item.id] = item
        return item

    async def get_by_id(self, content_id: int, couple_id: int) -> ContentItem | None:
        item = self.items.get(content_id)
        if item is not None and item.couple_id != couple_id:
            return None
        if item is not None:
            item.ratings = [rating for rating in self.ratings if rating.content_id == item.id]
            item.comments = [comment for comment in self.comments if comment.content_id == item.id]
        return item

    async def list_for_couple(self, couple_id: int) -> list[ContentItem]:
        items = [item for item in self.items.values() if item.couple_id == couple_id]
        for item in items:
            item.ratings = [rating for rating in self.ratings if rating.content_id == item.id]
            item.comments = [comment for comment in self.comments if comment.content_id == item.id]
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
                response="RATED",
            )
            self.next_rating_id += 1
            self.ratings.append(rating)
        else:
            rating.score = score
            rating.emoji = emoji
            rating.response = "RATED"
        return rating

    async def upsert_not_acquainted(self, *, content_id: int, user_id: int) -> Rating:
        rating = next(
            (rating for rating in self.ratings if rating.content_id == content_id and rating.user_id == user_id),
            None,
        )
        if rating is None:
            rating = Rating(
                id=self.next_rating_id,
                content_id=content_id,
                user_id=user_id,
                score=None,
                emoji=None,
                response="NOT_ACQUAINTED",
            )
            self.next_rating_id += 1
            self.ratings.append(rating)
        else:
            rating.score = None
            rating.emoji = None
            rating.response = "NOT_ACQUAINTED"
        return rating

    async def add_comment(self, *, content_id: int, user_id: int, text: str) -> Comment:
        comment = Comment(
            id=self.next_comment_id,
            content_id=content_id,
            user_id=user_id,
            text=text,
            created_at=datetime(2026, 5, 19, 10, self.next_comment_id, tzinfo=timezone.utc),
        )
        self.next_comment_id += 1
        self.comments.append(comment)
        return comment


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
    assert (
        completed.notification_text
        == "Two отметил(а) <tg-spoiler>Интерстеллар</tg-spoiler> как завершённое. Хочешь поставить оценку?"
    )
    assert completed.cat_notification_type is CatNotificationType.COMPLETED
    assert rating.score == 10
    assert rating.emoji == "🔥"
    assert items == [item]
    assert average_rating(items[0]) == 10


@pytest.mark.asyncio
async def test_content_not_acquainted_response_skips_numeric_rating_and_average() -> None:
    service, creator, partner, _ = build_service()
    item = await service.add_item(creator, category=ContentCategory.MOVIE, title="Интерстеллар")
    await service.complete_item(creator, item.id)

    response = await service.save_not_acquainted(partner, content_id=item.id)
    context, items = await service.list_items(creator)
    card = await service.build_content_card(context, items[0])

    assert response.response == "NOT_ACQUAINTED"
    assert response.score is None
    assert response.emoji is None
    assert average_rating(items[0]) is None
    assert "🎬 Фильм <tg-spoiler>Интерстеллар</tg-spoiler>" in card
    assert "Не знаком(а): Two" in card


@pytest.mark.asyncio
async def test_content_numeric_rating_replaces_not_acquainted_response() -> None:
    service, creator, partner, _ = build_service()
    item = await service.add_item(creator, category=ContentCategory.MOVIE, title="Интерстеллар")
    await service.complete_item(creator, item.id)

    await service.save_not_acquainted(partner, content_id=item.id)
    rating = await service.save_rating(partner, content_id=item.id, score=8, emoji="🔥")

    assert rating.response == "RATED"
    assert rating.score == 8
    assert rating.emoji == "🔥"


@pytest.mark.asyncio
async def test_both_partners_can_comment_and_card_shows_chronological_comments() -> None:
    service, creator, partner, _ = build_service()
    item = await service.add_item(creator, category=ContentCategory.MOVIE, title="Интерстеллар")

    first_comment = await service.add_comment(creator, content_id=item.id, text=" Очень красиво ")
    second_comment = await service.add_comment(partner, content_id=item.id, text="И музыка <3")
    context, items = await service.list_items(creator)
    card = await service.build_content_card(context, items[0])

    assert first_comment.text == "Очень красиво"
    assert second_comment.text == "И музыка <3"
    assert "Комментарии:" in card
    assert card.index("• ты: Очень красиво") < card.index("• Two: И музыка &lt;3")


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


@pytest.mark.asyncio
async def test_content_item_from_another_couple_is_hidden() -> None:
    service, creator, _, content_repository = build_service()
    content_repository.items[99] = ContentItem(
        id=99,
        couple_id=2,
        title="Foreign content",
        category=ContentCategory.MOVIE,
        added_by=999,
        status="NOT_COMPLETED",
    )

    _, items = await service.list_items(creator)

    assert items == []
    with pytest.raises(ContentServiceError):
        await service.complete_item(creator, 99)


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


def test_content_average_ignores_not_acquainted_responses() -> None:
    item = ContentItem(id=1, title="A", category="MOVIE", added_by=1, status="COMPLETED")
    item.ratings = [
        Rating(content_id=1, user_id=1, score=8, emoji=None, response="RATED"),
        Rating(content_id=1, user_id=2, score=None, emoji=None, response="NOT_ACQUAINTED"),
    ]

    assert average_rating(item) == 8
