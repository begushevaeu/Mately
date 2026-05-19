from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Couple, Task, User
from app.repositories.couples import CoupleRepository
from app.repositories.partner_aliases import PartnerAliasRepository
from app.repositories.tasks import TaskRepository
from app.services.partner_aliases import DisplayName, PartnerAliasService
from app.utils.dates import format_deadline, parse_deadline

TASK_TITLE_EMOJI = "🧹"


class TaskServiceError(ValueError):
    pass


class AssignmentType(StrEnum):
    SELF = "SELF"
    PARTNER = "PARTNER"
    POOL = "POOL"


class RecurrenceType(StrEnum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    CUSTOM = "CUSTOM"


@dataclass(slots=True)
class TaskCreationInput:
    title: str
    is_recurring: bool
    recurrence_type: RecurrenceType | None
    assignment_type: AssignmentType
    deadline: datetime | None


@dataclass(slots=True)
class TaskMutationResult:
    task: Task
    notification_user: User | None = None
    notification_text: str | None = None


@dataclass(slots=True)
class CoupleTaskContext:
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


def parse_task_deadline(value: str, couple: Couple) -> datetime | None:
    return parse_deadline(value=value, timezone_name=couple.timezone)


def build_task_summary(task: Task, timezone_name: str) -> str:
    status_label = {
        "OPEN": "в ярмарке",
        "ASSIGNED": "назначена",
        "OVERDUE": "просрочена",
        "COMPLETED": "выполнена",
        "ARCHIVED": "в архиве",
    }.get(task.status, task.status)
    recurring_label = ""
    if task.is_recurring and task.recurrence_type is not None:
        recurring_label = f"\nПовтор: {task.recurrence_type.lower()}"

    return (
        f"{TASK_TITLE_EMOJI} <b>{escape(task.title)}</b>\n"
        f"Статус: {status_label}\n"
        f"Срок: {format_deadline(task.deadline, timezone_name)}"
        f"{recurring_label}"
    )


class TaskService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        couples: CoupleRepository | None = None,
        tasks: TaskRepository | None = None,
        aliases: PartnerAliasRepository | None = None,
    ) -> None:
        if session is None and (couples is None or tasks is None):
            raise ValueError("session is required when repositories are not provided")

        self.couples = couples or CoupleRepository(session)  # type: ignore[arg-type]
        self.tasks = tasks or TaskRepository(session)  # type: ignore[arg-type]
        self.aliases = PartnerAliasService(session=session, aliases=aliases)  # type: ignore[arg-type]

    async def get_context(self, current_user: User) -> CoupleTaskContext:
        membership = await self.couples.get_membership(current_user.id)
        if membership is None:
            raise TaskServiceError("User is not in a couple")

        members = await self.couples.get_users_for_couple(membership.couple_id)
        if len(members) < 2:
            raise TaskServiceError("Couple is not ready")

        return CoupleTaskContext(couple=membership.couple, current_user=current_user, members=members)

    async def create_task(self, current_user: User, creation_input: TaskCreationInput) -> TaskMutationResult:
        context = await self.get_context(current_user)
        partner = context.partner
        assigned_to = self._resolve_assignee(context, creation_input.assignment_type)
        status = "ASSIGNED" if assigned_to is not None else "OPEN"
        assigned_at = datetime.now(timezone.utc) if assigned_to is not None else None
        task = await self.tasks.create(
            title=creation_input.title,
            created_by=current_user.id,
            assigned_to=assigned_to,
            is_recurring=creation_input.is_recurring,
            recurrence_type=creation_input.recurrence_type.value if creation_input.recurrence_type else None,
            deadline=creation_input.deadline,
            status=status,
            assigned_at=assigned_at,
        )
        await self.tasks.add_history(task_id=task.id, event_type="CREATED", actor_id=current_user.id)
        if assigned_to is not None:
            await self.tasks.add_history(task_id=task.id, event_type="ASSIGNED", actor_id=current_user.id)

        if creation_input.assignment_type is AssignmentType.PARTNER and partner is not None:
            actor_label = await self.aliases.get_display_for(owner=partner, partner=current_user)
            return TaskMutationResult(
                task=task,
                notification_user=partner,
                notification_text=f"От {actor_label.genitive_with_emoji}: тебе назначили задачу «{task.title}».",
            )

        if creation_input.assignment_type is AssignmentType.POOL and partner is not None:
            actor_label = await self.aliases.get_display_for(owner=partner, partner=current_user)
            return TaskMutationResult(
                task=task,
                notification_user=partner,
                notification_text=f"От {actor_label.genitive_with_emoji}: в ярмарке задач появилась «{task.title}».",
            )

        return TaskMutationResult(task=task)

    async def list_all_active(self, current_user: User) -> tuple[CoupleTaskContext, list[Task]]:
        context = await self.get_context(current_user)
        return context, await self.tasks.list_active_for_users(context.member_ids)

    async def list_my_tasks(self, current_user: User) -> tuple[CoupleTaskContext, list[Task]]:
        context = await self.get_context(current_user)
        return context, await self.tasks.list_assigned_to_user(current_user.id)

    async def list_pool(self, current_user: User) -> tuple[CoupleTaskContext, list[Task]]:
        context = await self.get_context(current_user)
        return context, await self.tasks.list_pool_for_users(context.member_ids)

    async def claim_task(self, current_user: User, task_id: int) -> TaskMutationResult:
        context = await self.get_context(current_user)
        task = await self._get_scoped_task(context, task_id)
        if task.status != "OPEN" or task.assigned_to is not None:
            raise TaskServiceError("Task is not available in pool")

        task = await self.tasks.assign(task, current_user.id)
        await self.tasks.add_history(task_id=task.id, event_type="ASSIGNED", actor_id=current_user.id)
        partner = context.partner
        actor_label = await self._display_for_partner_or_fallback(owner=partner, partner=current_user)
        notification_text = f"{actor_label.nominative_with_emoji} взял(а) задачу «{task.title}»."
        return TaskMutationResult(task=task, notification_user=partner, notification_text=notification_text)

    async def complete_task(self, current_user: User, task_id: int) -> TaskMutationResult:
        context = await self.get_context(current_user)
        task = await self._get_scoped_task(context, task_id)
        if task.status in {"COMPLETED", "ARCHIVED"}:
            raise TaskServiceError("Task is already closed")

        task = await self.tasks.complete(task)
        await self.tasks.add_history(task_id=task.id, event_type="COMPLETED", actor_id=current_user.id)
        partner = context.partner
        actor_label = await self._display_for_partner_or_fallback(owner=partner, partner=current_user)
        notification_text = f"{actor_label.nominative_with_emoji} выполнил(а) задачу «{task.title}»."
        return TaskMutationResult(task=task, notification_user=partner, notification_text=notification_text)

    async def build_task_card(self, context: CoupleTaskContext, task: Task, *, show_ownership: bool = False) -> str:
        card = build_task_summary(task, context.couple.timezone)
        if not show_ownership:
            return card

        owner_label = await self._actor_line(context, task.created_by, case="genitive")
        assignee_label = await self._assignee_line(context, task.assigned_to)
        return f"{card}\nОт: {owner_label}\nКому: {assignee_label}"

    def _resolve_assignee(self, context: CoupleTaskContext, assignment_type: AssignmentType) -> int | None:
        if assignment_type is AssignmentType.SELF:
            return context.current_user.id

        if assignment_type is AssignmentType.PARTNER:
            partner = context.partner
            if partner is None:
                raise TaskServiceError("Partner not found")
            return partner.id

        return None

    async def _get_scoped_task(self, context: CoupleTaskContext, task_id: int) -> Task:
        task = await self.tasks.get_by_id(task_id)
        if task is None:
            raise TaskServiceError("Task not found")

        belongs_to_couple = task.created_by in context.member_ids or task.assigned_to in context.member_ids
        if not belongs_to_couple:
            raise TaskServiceError("Task not found")

        return task

    async def _actor_line(self, context: CoupleTaskContext, user_id: int, *, case: str) -> str:
        if user_id == context.current_user.id:
            return "тебя" if case == "genitive" else "ты"

        user = context.user_by_id(user_id)
        if user is None:
            return "партнера"

        display = await self.aliases.get_display_for(owner=context.current_user, partner=user)
        return display.genitive_with_emoji if case == "genitive" else display.nominative_with_emoji

    async def _assignee_line(self, context: CoupleTaskContext, user_id: int | None) -> str:
        if user_id is None:
            return "ярмарка задач"

        if user_id == context.current_user.id:
            return "тебе"

        user = context.user_by_id(user_id)
        if user is None:
            return "партнеру"

        display = await self.aliases.get_display_for(owner=context.current_user, partner=user)
        return display.dative_with_emoji

    async def _display_for_partner_or_fallback(self, *, owner: User | None, partner: User) -> DisplayName:
        if owner is None:
            return DisplayName(emoji="", nominative="Партнер", genitive="партнера", dative="партнеру")

        return await self.aliases.get_display_for(owner=owner, partner=partner)
