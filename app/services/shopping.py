from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Couple, ShoppingItem, User
from app.repositories.couples import CoupleRepository
from app.repositories.shopping import ShoppingRepository
from app.utils.dates import get_timezone


class ShoppingServiceError(ValueError):
    pass


@dataclass(slots=True)
class ShoppingContext:
    couple: Couple
    current_user: User
    members: list[User]

    @property
    def member_ids(self) -> list[int]:
        return [member.id for member in self.members]


class ShoppingService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        couples: CoupleRepository | None = None,
        shopping: ShoppingRepository | None = None,
    ) -> None:
        if session is None and (couples is None or shopping is None):
            raise ValueError("session is required when repositories are not provided")

        self.couples = couples or CoupleRepository(session)  # type: ignore[arg-type]
        self.shopping = shopping or ShoppingRepository(session)  # type: ignore[arg-type]

    async def get_context(self, current_user: User) -> ShoppingContext:
        membership = await self.couples.get_membership(current_user.id)
        if membership is None:
            raise ShoppingServiceError("User is not in a couple")

        members = await self.couples.get_users_for_couple(membership.couple_id)
        if len(members) < 2:
            raise ShoppingServiceError("Couple is not ready")

        return ShoppingContext(couple=membership.couple, current_user=current_user, members=members)

    async def list_items(self, current_user: User) -> tuple[ShoppingContext, list[ShoppingItem]]:
        context = await self.get_context(current_user)
        await self.archive_expired_bought_items_for_context(context)
        return context, await self.shopping.list_visible_for_couple(context.couple.id)

    async def add_item(self, current_user: User, title: str) -> ShoppingItem:
        title = title.strip()
        if not title:
            raise ShoppingServiceError("Название покупки не должно быть пустым")
        if len(title) > 255:
            raise ShoppingServiceError("Название покупки получилось слишком длинным")

        context = await self.get_context(current_user)
        return await self.shopping.create(couple_id=context.couple.id, title=title, added_by=current_user.id)

    async def mark_bought(self, current_user: User, item_id: int) -> ShoppingItem:
        context = await self.get_context(current_user)
        await self.archive_expired_bought_items_for_context(context)
        item = await self._get_scoped_item(context, item_id)
        if item.status == "ARCHIVED":
            raise ShoppingServiceError("Эта покупка уже скрыта из списка")
        if item.status == "BOUGHT":
            raise ShoppingServiceError("Эта покупка уже отмечена купленной")

        return await self.shopping.mark_bought(
            item,
            completed_by=current_user.id,
            completed_at=datetime.now(timezone.utc),
        )

    async def archive_expired_bought_items_for_context(
        self,
        context: ShoppingContext,
        *,
        now: datetime | None = None,
    ) -> int:
        now = now or datetime.now(timezone.utc)
        cutoff = start_of_today_utc(context.couple.timezone, now)
        return await self.shopping.archive_bought_before(
            couple_id=context.couple.id,
            cutoff=cutoff,
            archived_at=now,
        )

    async def _get_scoped_item(self, context: ShoppingContext, item_id: int) -> ShoppingItem:
        item = await self.shopping.get_by_id(item_id, context.couple.id)
        if item is None:
            raise ShoppingServiceError("Покупка не найдена")

        belongs_to_couple = True
        if not belongs_to_couple:
            raise ShoppingServiceError("Покупка не найдена")

        return item


def start_of_today_utc(timezone_name: str, now: datetime) -> datetime:
    tz = get_timezone(timezone_name)
    local_now = now.astimezone(tz)
    local_start = datetime.combine(local_now.date(), time.min, tzinfo=tz)
    return local_start.astimezone(timezone.utc)


def build_shopping_panel_text(items: list[ShoppingItem]) -> str:
    active_items = [item for item in items if item.status == "ACTIVE"]
    bought_items = [item for item in items if item.status == "BOUGHT"]
    blocks = ["🛒 <b>Покупки</b>"]

    if active_items:
        active_lines = ["<b>Нужно купить</b>"]
        active_lines.extend(f"{index}. {escape(item.title)}" for index, item in enumerate(active_items, start=1))
        blocks.append("\n".join(active_lines))
    elif bought_items:
        blocks.append("Нужно купить пока нечего.")
    else:
        blocks.append("Список покупок пуст.")

    if bought_items:
        bought_lines = ["<b>Куплено сегодня</b>"]
        bought_lines.extend(f"✓ {escape(item.title)}" for item in bought_items)
        blocks.append("\n".join(bought_lines))

    return "\n\n".join(blocks)
