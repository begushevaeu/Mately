from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentItem, Couple, Task
from app.repositories.content import ContentRepository
from app.repositories.couples import CoupleRepository
from app.repositories.tasks import TaskRepository

ACTIVE_TASK_STATUSES = {"OPEN", "ASSIGNED", "OVERDUE"}
MONTH_NAMES = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}


@dataclass(frozen=True, slots=True)
class RecapPeriod:
    key: str
    label: str
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class RecapStats:
    period: RecapPeriod
    completed_tasks_count: int
    completed_content_count: int
    average_rating: float | None
    overdue_tasks_count: int

    @property
    def total_activity(self) -> int:
        return self.completed_tasks_count + self.completed_content_count


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.couples = CoupleRepository(session)
        self.tasks = TaskRepository(session)
        self.content = ContentRepository(session)

    async def build_recap_text_for_couple(self, *, couple: Couple, local_now: datetime, period: str) -> str:
        return await self.build_recap_text(
            couple_id=couple.id,
            local_now=local_now,
            period=period,
        )

    async def build_recap_text(self, *, couple_id: int, local_now: datetime, period: str) -> str:
        tasks = await self.tasks.list_for_couple(couple_id)
        content_items = await self.content.list_for_couple(couple_id)
        stats = collect_recap_stats(tasks, content_items, local_now=local_now, period=period)
        if period == "month":
            return build_monthly_recap_text(stats)
        return build_weekly_recap_text(stats)


def collect_recap_stats(
    tasks: list[Task],
    content_items: list[ContentItem],
    *,
    local_now: datetime,
    period: str,
) -> RecapStats:
    recap_period = build_recap_period(local_now, period)
    completed_tasks = [task for task in tasks if is_in_period(task.completed_at, recap_period)]
    completed_content = [item for item in content_items if is_in_period(item.completed_at, recap_period)]
    ratings = [rating.score for item in completed_content for rating in item.ratings if rating.score is not None]
    now_utc = local_now.astimezone(timezone.utc)
    overdue_count = len(
        [
            task
            for task in tasks
            if task.deadline is not None and task.deadline <= now_utc and task.status in ACTIVE_TASK_STATUSES
        ]
    )
    return RecapStats(
        period=recap_period,
        completed_tasks_count=len(completed_tasks),
        completed_content_count=len(completed_content),
        average_rating=sum(ratings) / len(ratings) if ratings else None,
        overdue_tasks_count=overdue_count,
    )


def build_recap_period(local_now: datetime, period: str) -> RecapPeriod:
    local_end = local_now
    local_day_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        local_start = local_day_start - timedelta(days=7)
        return RecapPeriod(
            key="week",
            label="последние 7 дней",
            start=local_start.astimezone(timezone.utc),
            end=local_end.astimezone(timezone.utc),
        )

    local_month_start = local_day_start.replace(day=1)
    if local_now.day == 1:
        local_end = local_month_start
        previous_month_day = local_month_start - timedelta(days=1)
        local_start = previous_month_day.replace(day=1)
    else:
        local_start = local_month_start

    return RecapPeriod(
        key="month",
        label=MONTH_NAMES.get(local_start.month, "месяц"),
        start=local_start.astimezone(timezone.utc),
        end=local_end.astimezone(timezone.utc),
    )


def is_in_period(value: datetime | None, period: RecapPeriod) -> bool:
    if value is None:
        return False
    value_utc = value.astimezone(timezone.utc)
    return period.start <= value_utc < period.end


def build_weekly_recap_text(stats: RecapStats) -> str:
    return (
        "📊 <b>Недельная сводка</b>\n\n"
        f"Закрыто задач: {stats.completed_tasks_count}\n"
        f"Завершено контента: {stats.completed_content_count}\n"
        f"Средняя оценка: {format_average_rating(stats.average_rating)}\n"
        f"Просроченных задач сейчас: {stats.overdue_tasks_count}\n\n"
        f"{build_cozy_summary(stats)}"
    )


def build_monthly_recap_text(stats: RecapStats) -> str:
    title = build_monthly_couple_title(stats)
    return (
        "📊 <b>Месячная сводка</b>\n\n"
        f"Ваш {stats.period.label}: «{title}»\n"
        f"Закрыто задач: {stats.completed_tasks_count}\n"
        f"Завершено контента: {stats.completed_content_count}\n"
        f"Средняя оценка: {format_average_rating(stats.average_rating)}\n"
        f"Просроченных задач сейчас: {stats.overdue_tasks_count}\n\n"
        f"{build_cozy_summary(stats)}"
    )


def format_average_rating(value: float | None) -> str:
    if value is None:
        return "нет оценок"
    return f"{value:.1f}/10"


def build_monthly_couple_title(stats: RecapStats) -> str:
    if stats.total_activity == 0:
        return "Тихий режим накопления сил"
    if stats.completed_tasks_count >= 30 and stats.completed_content_count >= 5:
        return "Домашние стратеги с культурным бонусом"
    if stats.completed_tasks_count >= 15:
        return "Бытовой спецотряд мягкой силы"
    if stats.completed_content_count > stats.completed_tasks_count:
        return "Пледовые кураторы культурной программы"
    if stats.average_rating is not None and stats.average_rating >= 8:
        return "Эксперты хорошего вкуса"
    return "Тихие герои общего быта"


def build_cozy_summary(stats: RecapStats) -> str:
    if stats.total_activity == 0:
        return "Похоже, период был больше про выдох и сохранение сил. Такое тоже считается заботой о системе."
    if stats.overdue_tasks_count:
        return "Движение есть, а хвостики видно отдельно. Можно выбрать один маленький и снять его без героизма."
    if stats.completed_tasks_count and stats.completed_content_count:
        return "Быт двигался, культурная полка пополнялась, котики ставят аккуратную галочку."
    if stats.completed_tasks_count:
        return "Домашние дела заметно сдвинулись. Котики одобрительно делают вид, что всё было под их контролем."
    return "Культурная часть месяца звучит уютно. Пледовая комиссия довольна."
