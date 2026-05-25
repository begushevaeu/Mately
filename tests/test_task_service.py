from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.models import Couple, CoupleMember, PartnerAlias, Task, User
from app.notifications.cats import CatNotificationType
from app.services.tasks import (
    AssignmentType,
    RecurrenceType,
    TaskCreationInput,
    TaskService,
    TaskServiceError,
    build_task_summary,
    calculate_next_recurrence_deadline,
    format_recurrence_label,
    parse_task_deadline,
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
class FakeTaskRepository:
    tasks: dict[int, Task] = field(default_factory=dict)
    history: list[tuple[int, str, int]] = field(default_factory=list)
    next_id: int = 1

    async def create(self, **kwargs) -> Task:
        task = Task(id=self.next_id, **kwargs)
        self.next_id += 1
        self.tasks[task.id] = task
        return task

    async def get_by_id(self, task_id: int, couple_id: int) -> Task | None:
        task = self.tasks.get(task_id)
        if task is None or task.couple_id != couple_id:
            return None
        return task

    async def list_active_for_couple(self, couple_id: int) -> list[Task]:
        return [
            task
            for task in self.tasks.values()
            if task.couple_id == couple_id and task.status in {"OPEN", "ASSIGNED", "OVERDUE"}
        ]

    async def list_for_couple(self, couple_id: int) -> list[Task]:
        return [task for task in self.tasks.values() if task.couple_id == couple_id]

    async def list_assigned_to_user(self, couple_id: int, user_id: int) -> list[Task]:
        return [
            task
            for task in self.tasks.values()
            if task.couple_id == couple_id and task.status in {"OPEN", "ASSIGNED", "OVERDUE"} and task.assigned_to == user_id
        ]

    async def list_pool_for_couple(self, couple_id: int) -> list[Task]:
        return [
            task
            for task in self.tasks.values()
            if task.couple_id == couple_id and task.status == "OPEN" and task.assigned_to is None
        ]

    async def add_history(self, *, task_id: int, event_type: str, actor_id: int, details: str | None = None) -> None:
        self.history.append((task_id, event_type, actor_id))

    async def has_generated_recurrence(self, task_id: int) -> bool:
        return any(
            history_task_id == task_id and event_type == "RECURRENCE_CREATED"
            for history_task_id, event_type, _actor_id in self.history
        )

    async def assign(self, task: Task, user_id: int) -> Task:
        task.assigned_to = user_id
        task.status = "ASSIGNED"
        return task

    async def complete(self, task: Task) -> Task:
        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        return task

    async def archive(self, task: Task) -> Task:
        task.status = "ARCHIVED"
        return task

    async def mark_overdue(self, task: Task) -> Task:
        task.status = "OVERDUE"
        return task


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
) -> tuple[TaskService, User, User, FakeTaskRepository]:
    creator = User(id=1, telegram_id=100, username="one", first_name="One")
    partner = User(id=2, telegram_id=200, username="two", first_name="Two")
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")
    task_repository = FakeTaskRepository()
    service = TaskService(
        couples=FakeCoupleRepository(couple=couple, members=[creator, partner]),
        tasks=task_repository,
        aliases=alias_repository or FakePartnerAliasRepository(),
    )
    return service, creator, partner, task_repository


@pytest.mark.asyncio
async def test_create_task_assigned_to_partner_notifies_partner() -> None:
    service, creator, partner, task_repository = build_service()

    result = await service.create_task(
        creator,
        TaskCreationInput(
            title="Помыть пол",
            is_recurring=True,
            recurrence_type=RecurrenceType.WEEKLY,
            assignment_type=AssignmentType.PARTNER,
            deadline=None,
        ),
    )

    assert result.task.assigned_to == partner.id
    assert result.task.status == "ASSIGNED"
    assert result.notification_user is partner
    assert result.notification_message_kind == "assignment"
    assert task_repository.history == [(result.task.id, "CREATED", creator.id), (result.task.id, "ASSIGNED", creator.id)]


@pytest.mark.asyncio
async def test_pool_task_can_be_claimed_and_completed() -> None:
    service, creator, partner, _ = build_service()
    created = await service.create_task(
        creator,
        TaskCreationInput(
            title="Купить молоко",
            is_recurring=False,
            recurrence_type=None,
            assignment_type=AssignmentType.POOL,
            deadline=None,
        ),
    )

    claimed = await service.claim_task(partner, created.task.id)
    completed = await service.complete_task(partner, created.task.id)

    assert claimed.task.assigned_to == partner.id
    assert claimed.notification_message_kind == "assignment"
    assert completed.task.status == "COMPLETED"
    assert completed.notification_message_kind == "completed"


@pytest.mark.asyncio
async def test_completing_recurring_task_creates_next_occurrence() -> None:
    service, creator, partner, task_repository = build_service()
    created = await service.create_task(
        creator,
        TaskCreationInput(
            title="Полить цветы",
            is_recurring=True,
            recurrence_type=RecurrenceType.DAILY,
            assignment_type=AssignmentType.PARTNER,
            deadline=datetime(2099, 1, 1, 20, 59, tzinfo=timezone.utc),
        ),
    )

    completed = await service.complete_task(partner, created.task.id)
    next_task = completed.next_task

    assert completed.task.status == "COMPLETED"
    assert completed.cat_notification_type is CatNotificationType.COMPLETED
    assert next_task is not None
    assert next_task.id == 2
    assert next_task.title == "Полить цветы"
    assert next_task.created_by == creator.id
    assert next_task.assigned_to == partner.id
    assert next_task.status == "ASSIGNED"
    assert next_task.is_recurring is True
    assert next_task.recurrence_type == RecurrenceType.DAILY
    assert next_task.deadline == datetime(2099, 1, 2, 20, 59, tzinfo=timezone.utc)
    assert task_repository.history[-5:] == [
        (created.task.id, "COMPLETED", partner.id),
        (next_task.id, "CREATED", partner.id),
        (next_task.id, "ASSIGNED", partner.id),
        (next_task.id, "RECURRENCE_CREATED", partner.id),
        (created.task.id, "RECURRENCE_CREATED", partner.id),
    ]


@pytest.mark.asyncio
async def test_scheduler_regenerates_overdue_recurring_task_once() -> None:
    service, creator, partner, task_repository = build_service()
    created = await service.create_task(
        creator,
        TaskCreationInput(
            title="РџРѕР»РёС‚СЊ С†РІРµС‚С‹",
            is_recurring=True,
            recurrence_type=RecurrenceType.DAILY,
            assignment_type=AssignmentType.PARTNER,
            deadline=datetime(2026, 5, 18, 20, 59, tzinfo=timezone.utc),
        ),
    )
    context = await service.get_context(creator)

    regenerated = await service.regenerate_due_recurring_tasks(
        context,
        now=datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc),
    )

    assert len(regenerated) == 1
    assert regenerated[0].task.status == "OVERDUE"
    assert regenerated[0].next_task is not None
    assert regenerated[0].next_task.id == 2
    assert regenerated[0].next_task.deadline == datetime(2026, 5, 20, 20, 59, tzinfo=timezone.utc)
    completed = await service.complete_task(partner, created.task.id)

    assert completed.next_task is None
    assert task_repository.next_id == 3


@pytest.mark.asyncio
async def test_archive_one_time_task_hides_it_from_active_lists() -> None:
    service, creator, partner, task_repository = build_service()
    created = await service.create_task(
        creator,
        TaskCreationInput(
            title="Разобрать пакеты",
            is_recurring=False,
            recurrence_type=None,
            assignment_type=AssignmentType.PARTNER,
            deadline=None,
        ),
    )

    archived = await service.archive_task(creator, created.task.id)
    _, active_tasks = await service.list_all_active(creator)

    assert archived.task.status == "ARCHIVED"
    assert active_tasks == []
    assert archived.notification_user is partner
    assert archived.notification_text == "One удалил(а) задачу.\n\n<blockquote>🐻 Разобрать пакеты</blockquote>"
    assert task_repository.history[-1] == (created.task.id, "ARCHIVED", creator.id)


@pytest.mark.asyncio
async def test_archiving_recurring_task_stops_future_occurrences() -> None:
    service, creator, partner, task_repository = build_service()
    created = await service.create_task(
        creator,
        TaskCreationInput(
            title="Полить цветы",
            is_recurring=True,
            recurrence_type=RecurrenceType.DAILY,
            assignment_type=AssignmentType.PARTNER,
            deadline=datetime(2099, 1, 1, 20, 59, tzinfo=timezone.utc),
        ),
    )

    archived = await service.archive_task(partner, created.task.id)

    assert archived.task.status == "ARCHIVED"
    assert archived.next_task is None
    assert task_repository.next_id == 2
    assert archived.notification_text == "Two остановил(а) повтор задачи.\n\n<blockquote>🐻 Полить цветы</blockquote>"
    assert task_repository.history[-1] == (created.task.id, "ARCHIVED", partner.id)


def test_monthly_recurrence_clamps_deadline_to_last_day() -> None:
    task = Task(
        id=1,
        title="Оплатить счета",
        created_by=1,
        assigned_to=1,
        status="ASSIGNED",
        is_recurring=True,
        recurrence_type=RecurrenceType.MONTHLY,
        recurrence_interval_days=None,
        deadline=datetime(2099, 1, 31, 20, 59, tzinfo=timezone.utc),
    )

    assert calculate_next_recurrence_deadline(task, "Europe/Moscow") == datetime(
        2099,
        2,
        28,
        20,
        59,
        tzinfo=timezone.utc,
    )


def test_custom_recurrence_uses_interval_days() -> None:
    task = Task(
        id=1,
        title="Поменять полотенца",
        created_by=1,
        assigned_to=1,
        status="ASSIGNED",
        is_recurring=True,
        recurrence_type=RecurrenceType.CUSTOM,
        recurrence_interval_days=3,
        deadline=datetime(2099, 1, 1, 20, 59, tzinfo=timezone.utc),
    )

    assert calculate_next_recurrence_deadline(task, "Europe/Moscow") == datetime(
        2099,
        1,
        4,
        20,
        59,
        tzinfo=timezone.utc,
    )


@pytest.mark.asyncio
async def test_task_from_another_couple_is_not_available() -> None:
    service, creator, _, task_repository = build_service()
    task_repository.tasks[99] = Task(id=99, title="Чужая задача", created_by=999, status="OPEN")

    with pytest.raises(TaskServiceError):
        await service.complete_task(creator, 99)


@pytest.mark.asyncio
async def test_partner_aliases_are_used_in_notifications_and_cards() -> None:
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
    await aliases.upsert(
        owner_user_id=partner.id,
        partner_user_id=creator.id,
        emoji="🐵",
        nominative="Обезьянка",
        genitive="Обезьянки",
        dative="Обезьянке",
    )

    result = await service.create_task(
        creator,
        TaskCreationInput(
            title="Помыть пол",
            is_recurring=False,
            recurrence_type=None,
            assignment_type=AssignmentType.PARTNER,
            deadline=None,
        ),
    )
    context = await service.get_context(creator)
    card = await service.build_task_card(context, result.task, show_ownership=True)

    assert result.notification_text == "От 🐵Обезьянки: тебе назначили задачу.\n\n<blockquote>🐻 Помыть пол</blockquote>"
    assert "<blockquote>🐻 Помыть пол</blockquote>" in card
    assert "От: тебя" in card
    assert "Кому: 🥒Огурчику" in card


@pytest.mark.asyncio
async def test_list_task_card_includes_index_inside_quote() -> None:
    service, creator, _, _ = build_service()
    created = await service.create_task(
        creator,
        TaskCreationInput(
            title="Купить молоко",
            is_recurring=False,
            recurrence_type=None,
            assignment_type=AssignmentType.SELF,
            deadline=None,
        ),
    )
    context = await service.get_context(creator)

    card = await service.build_task_card(context, created.task, show_ownership=True, list_index=3)

    assert card.startswith("<blockquote>3. 🐻 Купить молоко</blockquote>\nСтатус: назначена")
    assert "\nОт: тебя\nКому: тебе" in card


def test_task_title_emoji_rotates_by_task_id() -> None:
    for task_id, expected_emoji in [
        (1, "🐻"),
        (2, "🐱"),
        (3, "🐶"),
        (4, "🐭"),
        (5, "🦊"),
        (6, "🐻"),
    ]:
        task = Task(
            id=task_id,
            title=f"Задача {task_id}",
            created_by=1,
            assigned_to=1,
            status="ASSIGNED",
            is_recurring=False,
            recurrence_type=None,
            deadline=None,
        )

        assert build_task_summary(task, "Europe/Moscow").startswith(
            f"<blockquote>{expected_emoji} Задача {task_id}</blockquote>"
        )


def test_recurrence_labels_are_human_readable() -> None:
    assert format_recurrence_label(RecurrenceType.DAILY, None) == "каждый день"
    assert format_recurrence_label(RecurrenceType.WEEKLY, None) == "каждую неделю"
    assert format_recurrence_label(RecurrenceType.MONTHLY, None) == "каждый месяц"
    assert format_recurrence_label(RecurrenceType.CUSTOM, 3) == "каждые 3 дня"
    assert format_recurrence_label(RecurrenceType.CUSTOM, 5) == "каждые 5 дней"


def test_parse_task_deadline_understands_common_inputs() -> None:
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")

    assert parse_task_deadline("без срока", couple) is None
    assert parse_task_deadline("21.05.2026", couple) is not None
