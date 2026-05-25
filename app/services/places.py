from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Couple, PlaceComment, PlaceItem, PlaceRating, User
from app.repositories.couples import CoupleRepository
from app.repositories.partner_aliases import PartnerAliasRepository
from app.repositories.places import PlaceRepository
from app.services.partner_aliases import PartnerAliasService
from app.utils.dates import get_timezone


class PlaceServiceError(ValueError):
    pass


class PlaceCategory(StrEnum):
    RESTAURANT = "RESTAURANT"
    CAFE = "CAFE"
    CINEMA = "CINEMA"
    THEATRE = "THEATRE"
    PARK = "PARK"
    MUSEUM = "MUSEUM"
    BAR = "BAR"
    CONCERT = "CONCERT"
    EXHIBITION = "EXHIBITION"
    SHOW = "SHOW"
    TRIP = "TRIP"
    OTHER = "OTHER"


CATEGORY_LABELS = {
    PlaceCategory.RESTAURANT: "🍽️ Ресторан",
    PlaceCategory.CAFE: "☕ Кафе",
    PlaceCategory.CINEMA: "🎬 Кино",
    PlaceCategory.THEATRE: "🎭 Театр",
    PlaceCategory.PARK: "🌳 Парк",
    PlaceCategory.MUSEUM: "🏛️ Музей",
    PlaceCategory.BAR: "🍸 Бар",
    PlaceCategory.CONCERT: "🎵 Концерт",
    PlaceCategory.EXHIBITION: "🖼️ Выставка",
    PlaceCategory.SHOW: "🎟️ Шоу",
    PlaceCategory.TRIP: "🚆 Поездка",
    PlaceCategory.OTHER: "✨ Другое",
}


@dataclass(slots=True)
class PlaceContext:
    couple: Couple
    current_user: User
    members: list[User]

    @property
    def member_ids(self) -> list[int]:
        return [member.id for member in self.members]

    def user_by_id(self, user_id: int | None) -> User | None:
        if user_id is None:
            return None
        return next((member for member in self.members if member.id == user_id), None)


@dataclass(slots=True)
class PlaceListFilter:
    status: str | None = None


class PlaceService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        couples: CoupleRepository | None = None,
        places: PlaceRepository | None = None,
        aliases: PartnerAliasRepository | None = None,
    ) -> None:
        if session is None and (couples is None or places is None):
            raise ValueError("session is required when repositories are not provided")

        self.couples = couples or CoupleRepository(session)  # type: ignore[arg-type]
        self.places = places or PlaceRepository(session)  # type: ignore[arg-type]
        self.aliases = PartnerAliasService(session=session, aliases=aliases)  # type: ignore[arg-type]

    async def get_context(self, current_user: User) -> PlaceContext:
        membership = await self.couples.get_membership(current_user.id)
        if membership is None:
            raise PlaceServiceError("User is not in a couple")

        members = await self.couples.get_users_for_couple(membership.couple_id)
        if len(members) < 2:
            raise PlaceServiceError("Couple is not ready")

        return PlaceContext(couple=membership.couple, current_user=current_user, members=members)

    async def list_items(
        self,
        current_user: User,
        place_filter: PlaceListFilter | None = None,
    ) -> tuple[PlaceContext, list[PlaceItem]]:
        context = await self.get_context(current_user)
        items = await self.places.list_for_couple(context.couple.id)
        return context, apply_place_filter(items, place_filter)

    async def add_item(self, current_user: User, *, category: PlaceCategory, title: str) -> PlaceItem:
        title = " ".join(title.strip().split())
        if not title:
            raise PlaceServiceError("Название не должно быть пустым")
        if len(title) > 255:
            raise PlaceServiceError("Название получилось слишком длинным")

        context = await self.get_context(current_user)
        return await self.places.create(
            couple_id=context.couple.id,
            title=title,
            category=category.value,
            added_by=current_user.id,
        )

    async def visit_item(self, current_user: User, place_id: int) -> PlaceItem:
        context = await self.get_context(current_user)
        item = await self._get_scoped_item(context, place_id)
        if item.status == "VISITED":
            raise PlaceServiceError("Место уже отмечено посещенным")

        return await self.places.mark_visited(
            item,
            visited_by=current_user.id,
            visited_at=datetime.now(timezone.utc),
        )

    async def save_rating(self, current_user: User, *, place_id: int, score: int) -> PlaceRating:
        if score < 1 or score > 10:
            raise PlaceServiceError("Оценка должна быть от 1 до 10")

        context = await self.get_context(current_user)
        item = await self._get_scoped_item(context, place_id)
        if item.status != "VISITED":
            raise PlaceServiceError("Оценка доступна только после посещения")

        return await self.places.upsert_rating(place_id=item.id, user_id=current_user.id, score=score)

    async def add_comment(self, current_user: User, *, place_id: int, text: str) -> PlaceComment:
        text = normalize_comment_text(text)
        context = await self.get_context(current_user)
        item = await self._get_scoped_item(context, place_id)
        if item.status != "VISITED":
            raise PlaceServiceError("Комментарий доступен только после посещения")

        return await self.places.add_comment(place_id=item.id, user_id=current_user.id, text=text)

    async def build_place_card(self, context: PlaceContext, item: PlaceItem) -> str:
        owner_label = await self._actor_line(context, item.added_by)
        lines = [
            f"{category_label(item.category)} <b>{escape(item.title)}</b>",
            f"Статус: {status_label(item)}",
            f"Добавил(а): {owner_label}",
            f"Средняя оценка: {format_average_rating(item)}",
        ]
        if item.visited_at is not None:
            visited_by = await self._actor_line(context, item.visited_by)
            lines.append(f"Посетили: {format_visited_at(item.visited_at, context.couple.timezone)}")
            lines.append(f"Отметил(а): {visited_by}")

        comment_lines = await self._comment_lines(context, item)
        if comment_lines:
            lines.append("Комментарии:")
            lines.extend(comment_lines)

        return "\n".join(lines)

    async def _get_scoped_item(self, context: PlaceContext, place_id: int) -> PlaceItem:
        item = await self.places.get_by_id(place_id, context.couple.id)
        if item is None:
            raise PlaceServiceError("Место не найдено")
        return item

    async def _actor_line(self, context: PlaceContext, user_id: int | None) -> str:
        if user_id == context.current_user.id:
            return "ты"

        user = context.user_by_id(user_id)
        if user is None:
            return "партнёр"

        display = await self.aliases.get_display_for(owner=context.current_user, partner=user)
        return display.nominative_with_emoji

    async def _comment_lines(self, context: PlaceContext, item: PlaceItem) -> list[str]:
        lines = []
        for comment in sorted_comments(item):
            author = await self._actor_line(context, comment.user_id)
            lines.append(f"• {author}: {escape(comment.text)}")
        return lines


def apply_place_filter(items: list[PlaceItem], place_filter: PlaceListFilter | None) -> list[PlaceItem]:
    if place_filter is None:
        return sorted_place_items(items)

    filtered_items = []
    for item in items:
        if place_filter.status is not None and item.status != place_filter.status:
            continue
        filtered_items.append(item)

    return sorted_place_items(filtered_items)


def normalize_comment_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise PlaceServiceError("Комментарий не должен быть пустым")
    if len(normalized) > 1000:
        raise PlaceServiceError("Комментарий получился слишком длинным")
    return normalized


def sorted_comments(item: PlaceItem) -> list[PlaceComment]:
    return sorted(
        item.comments,
        key=lambda comment: (
            comment.created_at or datetime.min.replace(tzinfo=timezone.utc),
            comment.id or 0,
        ),
    )


def sorted_place_items(items: list[PlaceItem]) -> list[PlaceItem]:
    status_order = {"NOT_VISITED": 0, "VISITED": 1}
    return sorted(items, key=lambda item: (status_order.get(item.status, 2), item.category, item.title, item.id or 0))


def category_label(category: str) -> str:
    try:
        return CATEGORY_LABELS[PlaceCategory(category)]
    except ValueError:
        return category


def status_label(item: PlaceItem) -> str:
    return "посетили" if item.status == "VISITED" else "в планах"


def average_rating(item: PlaceItem) -> float | None:
    if not item.ratings:
        return None
    return sum(rating.score for rating in item.ratings) / len(item.ratings)


def format_average_rating(item: PlaceItem) -> str:
    average = average_rating(item)
    if average is None:
        return "нет"
    return f"{average:.1f}/10"


def format_visited_at(value: datetime, timezone_name: str) -> str:
    return value.astimezone(get_timezone(timezone_name)).strftime("%d.%m.%Y")


def place_summary_counts(items: list[PlaceItem]) -> tuple[int, int]:
    planned = len([item for item in items if item.status == "NOT_VISITED"])
    visited = len([item for item in items if item.status == "VISITED"])
    return planned, visited
