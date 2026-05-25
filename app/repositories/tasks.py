from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task, TaskHistory

ACTIVE_TASK_STATUSES = ("OPEN", "ASSIGNED", "OVERDUE")


class TaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        couple_id: int,
        title: str,
        created_by: int,
        assigned_to: int | None,
        is_recurring: bool,
        recurrence_type: str | None,
        recurrence_interval_days: int | None,
        deadline: datetime | None,
        status: str,
        assigned_at: datetime | None,
    ) -> Task:
        task = Task(
            couple_id=couple_id,
            title=title,
            created_by=created_by,
            assigned_to=assigned_to,
            is_recurring=is_recurring,
            recurrence_type=recurrence_type,
            recurrence_interval_days=recurrence_interval_days,
            deadline=deadline,
            status=status,
            assigned_at=assigned_at,
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_by_id(self, task_id: int, couple_id: int) -> Task | None:
        result = await self.session.execute(select(Task).where(Task.id == task_id, Task.couple_id == couple_id))
        return result.scalar_one_or_none()

    async def list_active_for_couple(self, couple_id: int) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .where(
                Task.couple_id == couple_id,
                Task.status.in_(ACTIVE_TASK_STATUSES),
            )
            .order_by(Task.deadline.is_(None), Task.deadline, Task.id)
        )
        return list(result.scalars().all())

    async def list_for_couple(self, couple_id: int) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.couple_id == couple_id)
            .order_by(Task.deadline.is_(None), Task.deadline, Task.id)
        )
        return list(result.scalars().all())

    async def list_assigned_to_user(self, couple_id: int, user_id: int) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .where(Task.couple_id == couple_id, Task.status.in_(ACTIVE_TASK_STATUSES), Task.assigned_to == user_id)
            .order_by(Task.deadline.is_(None), Task.deadline, Task.id)
        )
        return list(result.scalars().all())

    async def list_pool_for_couple(self, couple_id: int) -> list[Task]:
        result = await self.session.execute(
            select(Task)
            .where(
                Task.couple_id == couple_id,
                Task.status == "OPEN",
                Task.assigned_to.is_(None),
            )
            .order_by(Task.deadline.is_(None), Task.deadline, Task.id)
        )
        return list(result.scalars().all())

    async def add_history(self, *, task_id: int, event_type: str, actor_id: int, details: str | None = None) -> None:
        self.session.add(
            TaskHistory(
                task_id=task_id,
                event_type=event_type,
                actor_id=actor_id,
                timestamp=datetime.now(timezone.utc),
                details=details,
            )
        )
        await self.session.flush()

    async def has_generated_recurrence(self, task_id: int) -> bool:
        result = await self.session.execute(
            select(
                exists().where(
                    TaskHistory.task_id == task_id,
                    TaskHistory.event_type == "RECURRENCE_CREATED",
                    TaskHistory.details.like("next_task_id=%"),
                )
            )
        )
        return result.scalar()

    async def assign(self, task: Task, user_id: int) -> Task:
        task.assigned_to = user_id
        task.assigned_at = datetime.now(timezone.utc)
        task.status = "ASSIGNED"
        await self.session.flush()
        return task

    async def complete(self, task: Task) -> Task:
        task.status = "COMPLETED"
        task.completed_at = datetime.now(timezone.utc)
        await self.session.flush()
        return task

    async def archive(self, task: Task) -> Task:
        task.status = "ARCHIVED"
        await self.session.flush()
        return task

    async def mark_overdue(self, task: Task) -> Task:
        task.status = "OVERDUE"
        await self.session.flush()
        return task
