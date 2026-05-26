from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentItem, Couple, PlaceItem, ShoppingItem, Task
from app.repositories.content import ContentRepository
from app.repositories.couples import CoupleRepository
from app.repositories.places import PlaceRepository
from app.repositories.shopping import ShoppingRepository
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
    bought_shopping_count: int
    visited_places_count: int
    average_rating: float | None
    average_place_rating: float | None
    place_memory_title: str | None
    place_memory_rating: float | None
    overdue_tasks_count: int

    @property
    def total_activity(self) -> int:
        return (
            self.completed_tasks_count
            + self.completed_content_count
            + self.bought_shopping_count
            + self.visited_places_count
        )


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.couples = CoupleRepository(session)
        self.tasks = TaskRepository(session)
        self.content = ContentRepository(session)
        self.shopping = ShoppingRepository(session)
        self.places = PlaceRepository(session)

    async def build_recap_text_for_couple(self, *, couple: Couple, local_now: datetime, period: str) -> str:
        return await self.build_recap_text(
            couple_id=couple.id,
            local_now=local_now,
            period=period,
        )

    async def build_recap_text(self, *, couple_id: int, local_now: datetime, period: str) -> str:
        tasks = await self.tasks.list_for_couple(couple_id)
        content_items = await self.content.list_for_couple(couple_id)
        shopping_items = await self.shopping.list_for_couple(couple_id)
        place_items = await self.places.list_for_couple(couple_id)
        stats = collect_recap_stats(
            tasks,
            content_items,
            shopping_items,
            place_items,
            local_now=local_now,
            period=period,
        )
        if period == "month":
            return build_monthly_recap_text(stats)
        return build_weekly_recap_text(stats)


def collect_recap_stats(
    tasks: list[Task],
    content_items: list[ContentItem],
    shopping_items: list[ShoppingItem] | None = None,
    place_items: list[PlaceItem] | None = None,
    *,
    local_now: datetime,
    period: str,
) -> RecapStats:
    recap_period = build_recap_period(local_now, period)
    shopping_items = shopping_items or []
    place_items = place_items or []
    completed_tasks = [task for task in tasks if is_in_period(task.completed_at, recap_period)]
    completed_content = [item for item in content_items if is_in_period(item.completed_at, recap_period)]
    bought_shopping = [
        item
        for item in shopping_items
        if item.status in {"BOUGHT", "ARCHIVED"} and is_in_period(item.completed_at, recap_period)
    ]
    visited_places = [
        item
        for item in place_items
        if item.status == "VISITED" and is_in_period(item.visited_at, recap_period)
    ]
    ratings = [rating.score for item in completed_content for rating in item.ratings if rating.score is not None]
    place_ratings = [rating.score for item in visited_places for rating in item.ratings if rating.score is not None]
    top_place = select_top_place_memory(visited_places)
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
        bought_shopping_count=len(bought_shopping),
        visited_places_count=len(visited_places),
        average_rating=sum(ratings) / len(ratings) if ratings else None,
        average_place_rating=sum(place_ratings) / len(place_ratings) if place_ratings else None,
        place_memory_title=top_place.title if top_place is not None else None,
        place_memory_rating=average_place_rating(top_place) if top_place is not None else None,
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
        f"Куплено из списка: {stats.bought_shopping_count}\n"
        f"Завершено контента: {stats.completed_content_count}\n"
        f"Средняя оценка: {format_average_rating(stats.average_rating)}\n"
        f"Посещено мест: {stats.visited_places_count}\n"
        f"Средняя оценка мест: {format_average_rating(stats.average_place_rating)}\n"
        f"{format_place_memory_line(stats)}"
        f"Просроченных задач сейчас: {stats.overdue_tasks_count}\n\n"
        f"{build_cozy_summary(stats)}"
    )


def build_monthly_recap_text(stats: RecapStats) -> str:
    title = build_monthly_couple_title(stats)
    return (
        "📊 <b>Месячная сводка</b>\n\n"
        f"Ваш {stats.period.label}: «{title}»\n"
        f"Закрыто задач: {stats.completed_tasks_count}\n"
        f"Куплено из списка: {stats.bought_shopping_count}\n"
        f"Завершено контента: {stats.completed_content_count}\n"
        f"Средняя оценка: {format_average_rating(stats.average_rating)}\n"
        f"Посещено мест: {stats.visited_places_count}\n"
        f"Средняя оценка мест: {format_average_rating(stats.average_place_rating)}\n"
        f"{format_place_memory_line(stats)}"
        f"Просроченных задач сейчас: {stats.overdue_tasks_count}\n\n"
        f"{build_cozy_summary(stats)}"
    )


def format_average_rating(value: float | None) -> str:
    if value is None:
        return "нет оценок"
    return f"{value:.1f}/10"


def format_place_memory_line(stats: RecapStats) -> str:
    if not stats.place_memory_title:
        return ""

    rating = ""
    if stats.place_memory_rating is not None:
        rating = f", {format_average_rating(stats.place_memory_rating)}"
    return f"Место периода: {escape(stats.place_memory_title)}{rating}\n"


def build_monthly_couple_title(stats: RecapStats) -> str:
    if stats.total_activity == 0:
        return "Тихий режим накопления сил"
    if stats.visited_places_count >= 4 and stats.average_place_rating is not None and stats.average_place_rating >= 8:
        return "Коллекционеры хороших мест"
    if stats.bought_shopping_count >= 20 and stats.completed_tasks_count >= 10:
        return "Домашние логисты спокойной жизни"
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
    if stats.bought_shopping_count and stats.visited_places_count:
        return "В периоде было и полезное, и живое: покупки закрывались, места добавляли общих воспоминаний."
    if stats.visited_places_count:
        return "Общая карта пополнилась новыми точками, и это уже маленький архив хороших выходов."
    if stats.bought_shopping_count:
        return "Бытовая логистика звучит бодро: нужное появлялось дома без лишней драмы."
    if stats.completed_tasks_count and stats.completed_content_count:
        return "Быт двигался, культурная полка пополнялась, котики ставят аккуратную галочку."
    if stats.completed_tasks_count:
        return "Домашние дела заметно сдвинулись. Котики одобрительно делают вид, что всё было под их контролем."
    return "Культурная часть месяца звучит уютно. Пледовая комиссия довольна."


def average_place_rating(item: PlaceItem | None) -> float | None:
    if item is None:
        return None
    scores = [rating.score for rating in item.ratings if rating.score is not None]
    if not scores:
        return None
    return sum(scores) / len(scores)


def select_top_place_memory(items: list[PlaceItem]) -> PlaceItem | None:
    if not items:
        return None

    return max(
        items,
        key=lambda item: (
            average_place_rating(item) or 0,
            item.visited_at or datetime.min.replace(tzinfo=timezone.utc),
            item.id or 0,
        ),
    )
