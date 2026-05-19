from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from app.models import Couple, CoupleMember, Task, User
from app.services.tasks import (
    AssignmentType,
    RecurrenceType,
    TaskCreationInput,
    TaskService,
    TaskServiceError,
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

    async def get_by_id(self, task_id: int) -> Task | None:
        return self.tasks.get(task_id)

    async def list_active_for_users(self, user_ids: list[int]) -> list[Task]:
        return [
            task
            for task in self.tasks.values()
            if task.status in {"OPEN", "ASSIGNED", "OVERDUE"}
            and (task.created_by in user_ids or task.assigned_to in user_ids)
        ]

    async def list_assigned_to_user(self, user_id: int) -> list[Task]:
        return [
            task
            for task in self.tasks.values()
            if task.status in {"OPEN", "ASSIGNED", "OVERDUE"} and task.assigned_to == user_id
        ]

    async def list_pool_for_users(self, user_ids: list[int]) -> list[Task]:
        return [
            task
            for task in self.tasks.values()
            if task.status == "OPEN" and task.assigned_to is None and task.created_by in user_ids
        ]

    async def add_history(self, *, task_id: int, event_type: str, actor_id: int, details: str | None = None) -> None:
        self.history.append((task_id, event_type, actor_id))

    async def assign(self, task: Task, user_id: int) -> Task:
        task.assigned_to = user_id
        task.status = "ASSIGNED"
        return task

    async def complete(self, task: Task) -> Task:
        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        return task


def build_service() -> tuple[TaskService, User, User, FakeTaskRepository]:
    creator = User(id=1, telegram_id=100, username="one", first_name="One")
    partner = User(id=2, telegram_id=200, username="two", first_name="Two")
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")
    task_repository = FakeTaskRepository()
    service = TaskService(
        couples=FakeCoupleRepository(couple=couple, members=[creator, partner]),
        tasks=task_repository,
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
    assert completed.task.status == "COMPLETED"


@pytest.mark.asyncio
async def test_task_from_another_couple_is_not_available() -> None:
    service, creator, _, task_repository = build_service()
    task_repository.tasks[99] = Task(id=99, title="Чужая задача", created_by=999, status="OPEN")

    with pytest.raises(TaskServiceError):
        await service.complete_task(creator, 99)


def test_parse_task_deadline_understands_common_inputs() -> None:
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")

    assert parse_task_deadline("без срока", couple) is None
    assert parse_task_deadline("21.05.2026", couple) is not None
