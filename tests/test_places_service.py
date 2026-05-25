from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.models import Couple, CoupleMember, PartnerAlias, PlaceComment, PlaceItem, PlaceRating, User
from app.notifications.cats import CatNotificationType
from app.ai.cozy import CozyMessageTheme
from app.services.places import (
    PlaceCategory,
    PlaceListFilter,
    PlaceService,
    PlaceServiceError,
    apply_place_filter,
    average_rating,
    place_summary_counts,
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
class FakePlaceRepository:
    items: dict[int, PlaceItem] = field(default_factory=dict)
    ratings: list[PlaceRating] = field(default_factory=list)
    comments: list[PlaceComment] = field(default_factory=list)
    next_id: int = 1
    next_rating_id: int = 1
    next_comment_id: int = 1

    async def create(self, *, couple_id: int, title: str, category: str, added_by: int) -> PlaceItem:
        item = PlaceItem(
            id=self.next_id,
            couple_id=couple_id,
            title=title,
            category=category,
            added_by=added_by,
            status="NOT_VISITED",
        )
        self.next_id += 1
        self.items[item.id] = item
        return item

    async def get_by_id(self, place_id: int, couple_id: int) -> PlaceItem | None:
        item = self.items.get(place_id)
        if item is not None and item.couple_id != couple_id:
            return None
        if item is not None:
            item.ratings = [rating for rating in self.ratings if rating.place_id == item.id]
            item.comments = [comment for comment in self.comments if comment.place_id == item.id]
        return item

    async def list_for_couple(self, couple_id: int) -> list[PlaceItem]:
        items = [item for item in self.items.values() if item.couple_id == couple_id]
        for item in items:
            item.ratings = [rating for rating in self.ratings if rating.place_id == item.id]
            item.comments = [comment for comment in self.comments if comment.place_id == item.id]
        return items

    async def mark_visited(self, item: PlaceItem, *, visited_by: int, visited_at: datetime) -> PlaceItem:
        item.status = "VISITED"
        item.visited_by = visited_by
        item.visited_at = visited_at
        return item

    async def upsert_rating(self, *, place_id: int, user_id: int, score: int) -> PlaceRating:
        rating = next(
            (rating for rating in self.ratings if rating.place_id == place_id and rating.user_id == user_id),
            None,
        )
        if rating is None:
            rating = PlaceRating(
                id=self.next_rating_id,
                place_id=place_id,
                user_id=user_id,
                score=score,
                response="RATED",
            )
            self.next_rating_id += 1
            self.ratings.append(rating)
        else:
            rating.score = score
            rating.response = "RATED"
        return rating

    async def upsert_not_acquainted(self, *, place_id: int, user_id: int) -> PlaceRating:
        rating = next(
            (rating for rating in self.ratings if rating.place_id == place_id and rating.user_id == user_id),
            None,
        )
        if rating is None:
            rating = PlaceRating(
                id=self.next_rating_id,
                place_id=place_id,
                user_id=user_id,
                score=None,
                response="NOT_ACQUAINTED",
            )
            self.next_rating_id += 1
            self.ratings.append(rating)
        else:
            rating.score = None
            rating.response = "NOT_ACQUAINTED"
        return rating

    async def add_comment(self, *, place_id: int, user_id: int, text: str) -> PlaceComment:
        comment = PlaceComment(
            id=self.next_comment_id,
            place_id=place_id,
            user_id=user_id,
            text=text,
            created_at=datetime(2026, 5, 20, 10, self.next_comment_id, tzinfo=timezone.utc),
        )
        self.next_comment_id += 1
        self.comments.append(comment)
        return comment


@dataclass(slots=True)
class FakePartnerAliasRepository:
    aliases: dict[tuple[int, int], PartnerAlias] = field(default_factory=dict)

    async def get(self, owner_user_id: int, partner_user_id: int):
        return self.aliases.get((owner_user_id, partner_user_id))

    async def upsert(self, **kwargs):
        alias = PartnerAlias(**kwargs)
        self.aliases[(kwargs["owner_user_id"], kwargs["partner_user_id"])] = alias
        return alias


def build_service(
    alias_repository: FakePartnerAliasRepository | None = None,
) -> tuple[PlaceService, User, User, FakePlaceRepository]:
    creator = User(id=1, telegram_id=100, username="one", first_name="One")
    partner = User(id=2, telegram_id=200, username="two", first_name="Two")
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")
    place_repository = FakePlaceRepository()
    service = PlaceService(
        couples=FakeCoupleRepository(couple=couple, members=[creator, partner]),
        places=place_repository,
        aliases=alias_repository or FakePartnerAliasRepository(),
    )
    return service, creator, partner, place_repository


@pytest.mark.asyncio
async def test_place_can_be_added_visited_rated_and_commented() -> None:
    service, creator, partner, _ = build_service()

    item = await service.add_item(creator, category=PlaceCategory.RESTAURANT, title="  Sage <3  ")
    visited_result = await service.visit_item(partner, item.id)
    visited = visited_result.item
    rating = await service.save_rating(partner, place_id=item.id, score=9)
    comment = await service.add_comment(partner, place_id=item.id, text=" Очень вкусно ")
    context, items = await service.list_items(creator)
    card = await service.build_place_card(context, items[0])

    assert item.title == "Sage <3"
    assert visited.status == "VISITED"
    assert visited.visited_by == partner.id
    assert visited_result.notification_user is creator
    assert (
        visited_result.notification_text
        == "Two отметил(а) <tg-spoiler>Sage &lt;3</tg-spoiler> как посещённое. "
        "Поставь оценку или нажми «Не был(а)»."
    )
    assert visited_result.cozy_theme is CozyMessageTheme.PLACE_VISITED
    assert visited_result.cat_notification_type is CatNotificationType.COMPLETED
    assert rating.score == 9
    assert comment.text == "Очень вкусно"
    assert average_rating(items[0]) == 9
    assert "🍽️ Ресторан <tg-spoiler>Sage &lt;3</tg-spoiler>" in card
    assert "Комментарии:" in card


@pytest.mark.asyncio
async def test_place_not_acquainted_response_skips_numeric_rating_and_average() -> None:
    service, creator, partner, _ = build_service()
    item = await service.add_item(creator, category=PlaceCategory.RESTAURANT, title="Sage")
    await service.visit_item(creator, item.id)

    response = await service.save_not_acquainted(partner, place_id=item.id)
    context, items = await service.list_items(creator)
    card = await service.build_place_card(context, items[0])

    assert response.response == "NOT_ACQUAINTED"
    assert response.score is None
    assert average_rating(items[0]) is None
    assert "Не был(а): Two" in card


@pytest.mark.asyncio
async def test_place_numeric_rating_replaces_not_acquainted_response() -> None:
    service, creator, partner, _ = build_service()
    item = await service.add_item(creator, category=PlaceCategory.RESTAURANT, title="Sage")
    await service.visit_item(creator, item.id)

    await service.save_not_acquainted(partner, place_id=item.id)
    rating = await service.save_rating(partner, place_id=item.id, score=7)

    assert rating.response == "RATED"
    assert rating.score == 7


@pytest.mark.asyncio
async def test_partner_aliases_are_used_in_place_visit_notifications() -> None:
    aliases = FakePartnerAliasRepository()
    service, creator, partner, _ = build_service(aliases)
    await aliases.upsert(
        owner_user_id=creator.id,
        partner_user_id=partner.id,
        emoji="🥒",
        nominative="Огурчик",
        genitive="Огурчика",
        dative="Огурчику",
    )
    item = await service.add_item(creator, category=PlaceCategory.PARK, title="Парк")

    result = await service.visit_item(partner, item.id)

    assert result.notification_user is creator
    assert (
        result.notification_text
        == "🥒Огурчик отметил(а) <tg-spoiler>Парк</tg-spoiler> как посещённое. "
        "Поставь оценку или нажми «Не был(а)»."
    )


@pytest.mark.asyncio
async def test_place_comment_and_rating_require_visit() -> None:
    service, creator, _, _ = build_service()
    item = await service.add_item(creator, category=PlaceCategory.CAFE, title="Кофейня")

    with pytest.raises(PlaceServiceError):
        await service.save_rating(creator, place_id=item.id, score=8)

    with pytest.raises(PlaceServiceError):
        await service.add_comment(creator, place_id=item.id, text="Хочу сюда")

    with pytest.raises(PlaceServiceError):
        await service.save_not_acquainted(creator, place_id=item.id)


@pytest.mark.asyncio
async def test_place_filters_by_visit_status() -> None:
    service, creator, partner, _ = build_service()
    restaurant = await service.add_item(creator, category=PlaceCategory.RESTAURANT, title="Ресторан")
    park = await service.add_item(partner, category=PlaceCategory.PARK, title="Парк")
    await service.visit_item(creator, park.id)

    _, planned_items = await service.list_items(creator, PlaceListFilter(status="NOT_VISITED"))
    _, visited_items = await service.list_items(creator, PlaceListFilter(status="VISITED"))

    assert planned_items == [restaurant]
    assert visited_items == [park]
    assert place_summary_counts([restaurant, park]) == (1, 1)
    assert apply_place_filter([park, restaurant], PlaceListFilter(status="VISITED")) == [park]


@pytest.mark.asyncio
async def test_place_from_another_couple_is_hidden() -> None:
    service, creator, _, place_repository = build_service()
    place_repository.items[99] = PlaceItem(
        id=99,
        couple_id=2,
        title="Foreign place",
        category=PlaceCategory.CAFE,
        added_by=999,
        status="NOT_VISITED",
    )

    _, items = await service.list_items(creator)

    assert items == []
    with pytest.raises(PlaceServiceError):
        await service.visit_item(creator, 99)


def test_place_average_ignores_not_acquainted_responses() -> None:
    item = PlaceItem(id=1, title="A", category="CAFE", added_by=1, status="VISITED")
    item.ratings = [
        PlaceRating(place_id=1, user_id=1, score=9, response="RATED"),
        PlaceRating(place_id=1, user_id=2, score=None, response="NOT_ACQUAINTED"),
    ]

    assert average_rating(item) == 9
