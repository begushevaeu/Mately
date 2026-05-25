from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.cozy import CozyMessageTheme
from app.models import Comment, ContentItem, Couple, Rating, User
from app.notifications.cats import CatNotificationType
from app.repositories.content import ContentRepository
from app.repositories.couples import CoupleRepository
from app.repositories.partner_aliases import PartnerAliasRepository
from app.services.partner_aliases import DisplayName, PartnerAliasService
from app.utils.dates import get_timezone


class ContentServiceError(ValueError):
    pass


class ContentCategory(StrEnum):
    BOOK = "BOOK"
    ANIME = "ANIME"
    MOVIE = "MOVIE"
    CARTOON = "CARTOON"
    SERIES = "SERIES"
    THEATRE = "THEATRE"
    MUSICAL = "MUSICAL"
    GAME = "GAME"


CATEGORY_LABELS = {
    ContentCategory.BOOK: "📚 Книга",
    ContentCategory.ANIME: "🍙 Аниме",
    ContentCategory.MOVIE: "🎬 Фильм",
    ContentCategory.CARTOON: "🧸 Мультфильм",
    ContentCategory.SERIES: "📺 Сериал",
    ContentCategory.THEATRE: "🎭 Театр",
    ContentCategory.MUSICAL: "🎼 Мюзикл",
    ContentCategory.GAME: "🎮 Игра",
}

CONTENT_REACTIONS = {
    "heart": "❤️",
    "starstruck": "🤩",
    "clown": "🤡",
    "poop": "💩",
    "fire": "🔥",
    "cry": "😭",
    "woozy": "🥴",
    "thumbs_up": "👍🏻",
    "thumbs_down": "👎🏻",
}


@dataclass(slots=True)
class ContentContext:
    couple: Couple
    current_user: User
    members: list[User]

    @property
    def member_ids(self) -> list[int]:
        return [member.id for member in self.members]

    @property
    def partner(self) -> User | None:
        return next((member for member in self.members if member.id != self.current_user.id), None)

    def user_by_id(self, user_id: int | None) -> User | None:
        if user_id is None:
            return None
        return next((member for member in self.members if member.id == user_id), None)


@dataclass(slots=True)
class ContentListFilter:
    status: str | None = None
    category: ContentCategory | None = None
    min_rating: int | None = None
    max_rating: int | None = None
    completed_since: datetime | None = None


@dataclass(slots=True)
class ContentMutationResult:
    item: ContentItem
    notification_user: User | None = None
    notification_text: str | None = None
    cozy_theme: CozyMessageTheme | None = None
    cozy_subject: str | None = None
    cat_notification_type: CatNotificationType | None = None


NOT_ACQUAINTED_RESPONSE = "NOT_ACQUAINTED"
RATED_RESPONSE = "RATED"


def format_content_title_quote(item: ContentItem, *, prefix: str | None = None) -> str:
    prefix_text = f"{escape(prefix)} " if prefix else ""
    return f"<blockquote>{prefix_text}{escape(item.title)}</blockquote>"


class ContentService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        couples: CoupleRepository | None = None,
        content: ContentRepository | None = None,
        aliases: PartnerAliasRepository | None = None,
    ) -> None:
        if session is None and (couples is None or content is None):
            raise ValueError("session is required when repositories are not provided")

        self.couples = couples or CoupleRepository(session)  # type: ignore[arg-type]
        self.content = content or ContentRepository(session)  # type: ignore[arg-type]
        self.aliases = PartnerAliasService(session=session, aliases=aliases)  # type: ignore[arg-type]

    async def get_context(self, current_user: User) -> ContentContext:
        membership = await self.couples.get_membership(current_user.id)
        if membership is None:
            raise ContentServiceError("User is not in a couple")

        members = await self.couples.get_users_for_couple(membership.couple_id)
        if len(members) < 2:
            raise ContentServiceError("Couple is not ready")

        return ContentContext(couple=membership.couple, current_user=current_user, members=members)

    async def list_items(
        self,
        current_user: User,
        content_filter: ContentListFilter | None = None,
    ) -> tuple[ContentContext, list[ContentItem]]:
        context = await self.get_context(current_user)
        items = await self.content.list_for_couple(context.couple.id)
        return context, apply_content_filter(items, content_filter)

    async def add_item(self, current_user: User, *, category: ContentCategory, title: str) -> ContentItem:
        title = " ".join(title.strip().split())
        if not title:
            raise ContentServiceError("Название не должно быть пустым")
        if len(title) > 255:
            raise ContentServiceError("Название получилось слишком длинным")

        context = await self.get_context(current_user)
        return await self.content.create(
            couple_id=context.couple.id,
            title=title,
            category=category.value,
            added_by=current_user.id,
        )

    async def complete_item(self, current_user: User, content_id: int) -> ContentMutationResult:
        context = await self.get_context(current_user)
        item = await self._get_scoped_item(context, content_id)
        if item.status == "COMPLETED":
            raise ContentServiceError("Контент уже отмечен завершённым")

        item = await self.content.mark_completed(item, completed_at=datetime.now(timezone.utc))
        partner = context.partner
        actor_label = await self._display_for_partner_or_fallback(owner=partner, partner=current_user)
        return ContentMutationResult(
            item=item,
            notification_user=partner,
            notification_text=(
                f"{escape(actor_label.nominative_with_emoji)} отметил(а) контент как завершённое.\n\n"
                f"{format_content_title_quote(item)}\n\n"
                "Хочешь поставить оценку?"
            ),
            cozy_theme=CozyMessageTheme.CONTENT_COMPLETED,
            cozy_subject=item.title,
            cat_notification_type=CatNotificationType.COMPLETED,
        )

    async def save_rating(
        self,
        current_user: User,
        *,
        content_id: int,
        score: int,
        emoji: str | None,
    ) -> Rating:
        if score < 1 or score > 10:
            raise ContentServiceError("Оценка должна быть от 1 до 10")

        context = await self.get_context(current_user)
        item = await self._get_scoped_item(context, content_id)
        if item.status != "COMPLETED":
            raise ContentServiceError("Оценка доступна только после завершения")

        return await self.content.upsert_rating(
            content_id=item.id,
            user_id=current_user.id,
            score=score,
            emoji=emoji,
        )

    async def save_not_acquainted(self, current_user: User, *, content_id: int) -> Rating:
        context = await self.get_context(current_user)
        item = await self._get_scoped_item(context, content_id)
        if item.status != "COMPLETED":
            raise ContentServiceError("Ответ доступен только после завершения")

        return await self.content.upsert_not_acquainted(content_id=item.id, user_id=current_user.id)

    async def add_comment(self, current_user: User, *, content_id: int, text: str) -> Comment:
        text = normalize_comment_text(text)
        context = await self.get_context(current_user)
        item = await self._get_scoped_item(context, content_id)
        return await self.content.add_comment(content_id=item.id, user_id=current_user.id, text=text)

    async def build_content_card(
        self,
        context: ContentContext,
        item: ContentItem,
        *,
        list_index: int | None = None,
    ) -> str:
        owner_label = await self._actor_line(context, item.added_by)
        quote_prefix = f"{list_index}." if list_index is not None else None
        lines = [
            format_content_title_quote(item, prefix=quote_prefix),
            f"Категория: {category_label(item.category)}",
            f"Статус: {status_label(item)}",
            f"Добавил(а): {owner_label}",
            f"Средняя оценка: {format_average_rating(item)}",
        ]
        if item.completed_at is not None:
            lines.append(f"Завершено: {format_completed_at(item.completed_at, context.couple.timezone)}")

        not_acquainted_line = await self._not_acquainted_line(context, item)
        if not_acquainted_line:
            lines.append(not_acquainted_line)

        reaction_line = format_reactions(item)
        if reaction_line:
            lines.append(f"Реакции: {reaction_line}")

        comment_lines = await self._comment_lines(context, item)
        if comment_lines:
            lines.append("Комментарии:")
            lines.extend(comment_lines)

        return "\n".join(lines)

    async def _get_scoped_item(self, context: ContentContext, content_id: int) -> ContentItem:
        item = await self.content.get_by_id(content_id, context.couple.id)
        if item is None:
            raise ContentServiceError("Контент не найден")
        return item

    async def _actor_line(self, context: ContentContext, user_id: int) -> str:
        if user_id == context.current_user.id:
            return "ты"

        user = context.user_by_id(user_id)
        if user is None:
            return "партнёр"

        display = await self.aliases.get_display_for(owner=context.current_user, partner=user)
        return display.nominative_with_emoji

    async def _comment_lines(self, context: ContentContext, item: ContentItem) -> list[str]:
        comments = sorted_comments(item)
        lines = []
        for comment in comments:
            author = await self._actor_line(context, comment.user_id)
            lines.append(f"• {author}: {escape(comment.text)}")
        return lines

    async def _not_acquainted_line(self, context: ContentContext, item: ContentItem) -> str | None:
        ratings = [rating for rating in item.ratings if rating.response == NOT_ACQUAINTED_RESPONSE]
        if not ratings:
            return None

        names = [await self._actor_line(context, rating.user_id) for rating in ratings]
        return f"Не знаком(а): {', '.join(names)}"

    async def _display_for_partner_or_fallback(self, *, owner: User | None, partner: User) -> DisplayName:
        if owner is None:
            return DisplayName(emoji="", nominative="Партнёр", genitive="партнёра", dative="партнёру")

        return await self.aliases.get_display_for(owner=owner, partner=partner)


def apply_content_filter(
    items: list[ContentItem],
    content_filter: ContentListFilter | None,
) -> list[ContentItem]:
    if content_filter is None:
        return sorted_content_items(items)

    filtered_items = []
    for item in items:
        if content_filter.status is not None and item.status != content_filter.status:
            continue
        if content_filter.category is not None and item.category != content_filter.category:
            continue
        average = average_rating(item)
        if content_filter.min_rating is not None and (average is None or average < content_filter.min_rating):
            continue
        if content_filter.max_rating is not None and (average is None or average > content_filter.max_rating):
            continue
        if content_filter.completed_since is not None:
            if item.completed_at is None or item.completed_at < content_filter.completed_since:
                continue
        filtered_items.append(item)

    return sorted_content_items(filtered_items)


def normalize_comment_text(value: str) -> str:
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ContentServiceError("Комментарий не должен быть пустым")
    if len(normalized) > 1000:
        raise ContentServiceError("Комментарий получился слишком длинным")
    return normalized


def sorted_comments(item: ContentItem) -> list[Comment]:
    return sorted(
        item.comments,
        key=lambda comment: (
            comment.created_at or datetime.min.replace(tzinfo=timezone.utc),
            comment.id or 0,
        ),
    )


def sorted_content_items(items: list[ContentItem]) -> list[ContentItem]:
    status_order = {"NOT_COMPLETED": 0, "COMPLETED": 1}
    return sorted(items, key=lambda item: (status_order.get(item.status, 2), item.category, item.title, item.id or 0))


def category_label(category: str) -> str:
    try:
        return CATEGORY_LABELS[ContentCategory(category)]
    except ValueError:
        return category


def status_label(item: ContentItem) -> str:
    if item.status != "COMPLETED":
        return "в планах"
    if item.category == ContentCategory.BOOK:
        return "прочитано"
    if item.category == ContentCategory.GAME:
        return "пройдено"
    return "просмотрено"


def average_rating(item: ContentItem) -> float | None:
    scores = [rating.score for rating in item.ratings if rating.score is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def format_average_rating(item: ContentItem) -> str:
    average = average_rating(item)
    if average is None:
        return "нет"
    return f"{average:.1f}/10"


def format_reactions(item: ContentItem) -> str:
    reactions = [rating.emoji for rating in item.ratings if rating.score is not None and rating.emoji]
    return " ".join(reactions)


def format_completed_at(value: datetime, timezone_name: str) -> str:
    return value.astimezone(get_timezone(timezone_name)).strftime("%d.%m.%Y")


def completed_since_for_period(timezone_name: str, period: str, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    local_now = now.astimezone(get_timezone(timezone_name))
    if period == "today":
        local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        local_start = local_now - timedelta(days=7)
    else:
        local_start = local_now - timedelta(days=30)
    return local_start.astimezone(timezone.utc)


def content_summary_counts(items: list[ContentItem]) -> tuple[int, int]:
    planned = len([item for item in items if item.status == "NOT_COMPLETED"])
    completed = len([item for item in items if item.status == "COMPLETED"])
    return planned, completed
