from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.models import Couple, CoupleMember, PartnerAlias, ShoppingItem, User
from app.services.shopping import ShoppingService, ShoppingServiceError, build_shopping_panel_text, start_of_today_utc


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
class FakeShoppingRepository:
    items: dict[int, ShoppingItem] = field(default_factory=dict)
    next_id: int = 1

    async def create(self, *, couple_id: int, title: str, added_by: int) -> ShoppingItem:
        item = ShoppingItem(id=self.next_id, couple_id=couple_id, title=title, added_by=added_by, status="ACTIVE")
        self.next_id += 1
        self.items[item.id] = item
        return item

    async def get_by_id(self, item_id: int, couple_id: int) -> ShoppingItem | None:
        item = self.items.get(item_id)
        if item is None or item.couple_id != couple_id:
            return None
        return item

    async def list_visible_for_couple(self, couple_id: int) -> list[ShoppingItem]:
        return [
            item
            for item in sorted(
                self.items.values(),
                key=lambda item: (0 if item.status == "ACTIVE" else 1, item.id),
            )
            if item.status in {"ACTIVE", "BOUGHT"}
            and item.couple_id == couple_id
        ]

    async def mark_bought(self, item: ShoppingItem, *, completed_by: int, completed_at: datetime) -> ShoppingItem:
        item.status = "BOUGHT"
        item.completed_by = completed_by
        item.completed_at = completed_at
        item.archived_at = None
        return item

    async def archive_bought_before(self, *, couple_id: int, cutoff: datetime, archived_at: datetime) -> int:
        archived_count = 0
        for item in self.items.values():
            if (
                item.status == "BOUGHT"
                and item.archived_at is None
                and item.completed_at is not None
                and item.completed_at < cutoff
                and item.couple_id == couple_id
            ):
                item.status = "ARCHIVED"
                item.archived_at = archived_at
                archived_count += 1
        return archived_count


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
) -> tuple[ShoppingService, User, User, FakeShoppingRepository]:
    creator = User(id=1, telegram_id=100, username="one", first_name="One")
    partner = User(id=2, telegram_id=200, username="two", first_name="Two")
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")
    shopping_repository = FakeShoppingRepository()
    service = ShoppingService(
        couples=FakeCoupleRepository(couple=couple, members=[creator, partner]),
        shopping=shopping_repository,
        aliases=alias_repository or FakePartnerAliasRepository(),
    )
    return service, creator, partner, shopping_repository


@pytest.mark.asyncio
async def test_shopping_item_can_be_added_and_marked_bought() -> None:
    service, creator, partner, _ = build_service()

    added = await service.add_item(creator, "Молоко")
    item = added.item
    _, active_items = await service.list_items(partner)
    bought_result = await service.mark_bought(partner, item.id)
    bought = bought_result.item
    _, visible_items = await service.list_items(creator)

    assert active_items == [item]
    assert added.notification_user is partner
    assert added.notification_text == "One добавил(а) в покупки «Молоко»."
    assert bought.status == "BOUGHT"
    assert bought.completed_by == partner.id
    assert bought_result.notification_user is creator
    assert bought_result.notification_text == "Two отметил(а) купленным «Молоко»."
    assert visible_items == [bought]


@pytest.mark.asyncio
async def test_bought_items_are_archived_after_local_midnight() -> None:
    service, creator, partner, shopping_repository = build_service()
    old_item = (await service.add_item(creator, "Хлеб")).item
    fresh_item = (await service.add_item(creator, "Сыр")).item
    old_item.status = "BOUGHT"
    old_item.completed_by = partner.id
    old_item.completed_at = datetime(2026, 5, 19, 18, 0, tzinfo=timezone.utc)
    fresh_item.status = "BOUGHT"
    fresh_item.completed_by = partner.id
    fresh_item.completed_at = datetime(2026, 5, 19, 21, 1, tzinfo=timezone.utc)

    context = await service.get_context(creator)
    archived_count = await service.archive_expired_bought_items_for_context(
        context,
        now=datetime(2026, 5, 19, 21, 5, tzinfo=timezone.utc),
    )
    visible_items = await shopping_repository.list_visible_for_couple(context.couple.id)

    assert archived_count == 1
    assert old_item.status == "ARCHIVED"
    assert fresh_item.status == "BOUGHT"
    assert visible_items == [fresh_item]


@pytest.mark.asyncio
async def test_shopping_item_from_another_couple_is_hidden() -> None:
    service, creator, _, shopping_repository = build_service()
    shopping_repository.items[99] = ShoppingItem(
        id=99,
        couple_id=2,
        title="Foreign item",
        added_by=999,
        status="ACTIVE",
    )

    _, visible_items = await service.list_items(creator)

    assert visible_items == []
    with pytest.raises(ShoppingServiceError):
        await service.mark_bought(creator, 99)


@pytest.mark.asyncio
async def test_partner_aliases_are_used_in_shopping_notifications() -> None:
    aliases = FakePartnerAliasRepository()
    service, creator, partner, _ = build_service(aliases)
    await aliases.upsert(
        owner_user_id=partner.id,
        partner_user_id=creator.id,
        emoji="🐵",
        nominative="Обезьянка",
        genitive="Обезьянки",
        dative="Обезьянке",
    )

    result = await service.add_item(creator, "Кофе")

    assert result.notification_user is partner
    assert result.notification_text == "🐵Обезьянка добавил(а) в покупки «Кофе»."


def test_start_of_today_utc_uses_couple_timezone() -> None:
    assert start_of_today_utc(
        "Europe/Moscow",
        datetime(2026, 5, 19, 21, 5, tzinfo=timezone.utc),
    ) == datetime(2026, 5, 19, 21, 0, tzinfo=timezone.utc)


def test_shopping_panel_shows_active_first_and_escapes_titles() -> None:
    active = ShoppingItem(id=1, title="Молоко <2%>", added_by=1, status="ACTIVE")
    bought = ShoppingItem(id=2, title="Хлеб", added_by=1, completed_by=2, status="BOUGHT")

    text = build_shopping_panel_text([bought, active])

    assert "1. Молоко &lt;2%&gt;" in text
    assert "✓ Хлеб" in text
    assert text.index("Нужно купить") < text.index("Куплено сегодня")
