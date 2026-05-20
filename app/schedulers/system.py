from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.analytics import AnalyticsService
from app.models import Couple, Task, User
from app.notifications.cats import CatNotificationType
from app.notifications.delivery import send_user_notification
from app.repositories.couples import CoupleRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.shopping import ShoppingRepository
from app.repositories.tasks import TaskRepository
from app.schedulers.shopping import archive_expired_shopping_items
from app.services.tasks import CoupleTaskContext, TaskService
from app.utils.dates import get_timezone

logger = logging.getLogger(__name__)

MORNING_REMINDER_TIME = time(hour=9, minute=0)
EVENING_REMINDER_TIME = time(hour=21, minute=0)
RECAP_TIME = time(hour=10, minute=0)


@dataclass(slots=True)
class CoupleScheduleContext:
    couple: Couple
    members: list[User]
    local_now: datetime
    now: datetime

    @property
    def member_ids(self) -> list[int]:
        return [member.id for member in self.members]


def setup_application_scheduler(
    session_maker: async_sessionmaker[AsyncSession],
    bot: Bot,
) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        archive_expired_shopping_items,
        "interval",
        minutes=1,
        args=[session_maker],
        id="shopping_midnight_cleanup",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        regenerate_due_recurring_tasks,
        "interval",
        minutes=1,
        args=[session_maker],
        id="recurring_task_regeneration",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.add_job(
        send_due_couple_notifications,
        "interval",
        minutes=1,
        args=[session_maker, bot],
        id="couple_local_reminders",
        max_instances=1,
        coalesce=True,
        replace_existing=True,
    )
    scheduler.start()
    return scheduler


async def regenerate_due_recurring_tasks(
    session_maker: async_sessionmaker[AsyncSession],
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    async with session_maker() as session:
        try:
            regenerated_count = await regenerate_due_recurring_tasks_in_session(session, now=now)
            await session.commit()
            if regenerated_count:
                logger.info("Regenerated %s recurring tasks", regenerated_count)
        except Exception:
            await session.rollback()
            logger.exception("Failed to regenerate recurring tasks")


async def regenerate_due_recurring_tasks_in_session(session: AsyncSession, *, now: datetime) -> int:
    couples = await CoupleRepository(session).list_all()
    regenerated_count = 0
    for couple in couples:
        members = await CoupleRepository(session).get_users_for_couple(couple.id)
        if len(members) < 2:
            continue

        context = CoupleTaskContext(couple=couple, current_user=members[0], members=members)
        results = await TaskService(session).regenerate_due_recurring_tasks(context, now=now)
        regenerated_count += len([result for result in results if result.next_task is not None])

    return regenerated_count


async def send_due_couple_notifications(
    session_maker: async_sessionmaker[AsyncSession],
    bot: Bot,
    *,
    now: datetime | None = None,
) -> None:
    now = now or datetime.now(timezone.utc)
    async with session_maker() as session:
        try:
            sent_count = await send_due_couple_notifications_in_session(session, bot, now=now)
            await session.commit()
            if sent_count:
                logger.info("Sent %s scheduled couple notifications", sent_count)
        except Exception:
            await session.rollback()
            logger.exception("Failed to send scheduled couple notifications")


async def send_due_couple_notifications_in_session(session: AsyncSession, bot: Bot, *, now: datetime) -> int:
    sent_count = 0
    couples = await CoupleRepository(session).list_all()
    for couple in couples:
        members = await CoupleRepository(session).get_users_for_couple(couple.id)
        if len(members) < 2:
            continue

        context = CoupleScheduleContext(
            couple=couple,
            members=members,
            local_now=now.astimezone(get_timezone(couple.timezone or "Europe/Moscow")),
            now=now,
        )
        for notification_type, text, cat_type in await build_due_notifications(session, context):
            scheduled_at = local_schedule_datetime(context.local_now, schedule_time_for_type(notification_type))
            for member in members:
                delivered = await send_scheduled_notification_once(
                    session=session,
                    bot=bot,
                    user=member,
                    notification_type=notification_type,
                    text=text,
                    scheduled_at=scheduled_at,
                    dedupe_key=build_dedupe_key(couple, member, notification_type, context.local_now),
                    cat_notification_type=cat_type,
                )
                sent_count += int(delivered)

    return sent_count


async def build_due_notifications(
    session: AsyncSession,
    context: CoupleScheduleContext,
) -> list[tuple[str, str, CatNotificationType | None]]:
    notifications: list[tuple[str, str, CatNotificationType | None]] = []
    if is_same_local_minute(context.local_now, MORNING_REMINDER_TIME):
        text, cat_type = await build_morning_reminder_text(session, context)
        notifications.append(("morning_reminder", text, cat_type))
    if is_same_local_minute(context.local_now, EVENING_REMINDER_TIME):
        text, cat_type = await build_evening_reminder_text(session, context)
        notifications.append(("evening_reminder", text, cat_type))
    if context.local_now.weekday() == 0 and is_same_local_minute(context.local_now, RECAP_TIME):
        notifications.append(("weekly_recap", await build_recap_text(session, context, period="week"), CatNotificationType.RECAP))
    if context.local_now.day == 1 and is_same_local_minute(context.local_now, RECAP_TIME):
        notifications.append(("monthly_recap", await build_recap_text(session, context, period="month"), CatNotificationType.RECAP))

    return notifications


async def send_scheduled_notification_once(
    *,
    session: AsyncSession,
    bot: Bot,
    user: User,
    notification_type: str,
    text: str,
    scheduled_at: datetime,
    dedupe_key: str,
    cat_notification_type: CatNotificationType | None,
) -> bool:
    notifications = NotificationRepository(session)
    existing = await notifications.get_by_dedupe_key(dedupe_key)
    if existing is not None:
        return False

    notification = await notifications.create_pending(
        user_id=user.id,
        notification_type=notification_type,
        scheduled_at=scheduled_at,
        dedupe_key=dedupe_key,
        payload={"text": text},
    )
    delivery = await send_user_notification(bot, user, text, cat_notification_type=cat_notification_type)
    if delivery.delivered:
        await notifications.mark_sent(notification, delivered_at=datetime.now(timezone.utc))
        return True

    await notifications.mark_failed(notification)
    return False


async def build_morning_reminder_text(
    session: AsyncSession,
    context: CoupleScheduleContext,
) -> tuple[str, CatNotificationType | None]:
    tasks = await TaskRepository(session).list_active_for_users(context.member_ids)
    shopping_items = await ShoppingRepository(session).list_visible_for_users(context.member_ids)
    due_today = tasks_due_on_local_date(tasks, context.local_now)
    overdue = overdue_tasks(tasks, context.now)
    active_shopping_count = len([item for item in shopping_items if item.status == "ACTIVE"])
    cat_type = CatNotificationType.OVERDUE if overdue else CatNotificationType.SLEEPY
    text = (
        "Доброе утро. "
        f"На сегодня: {len(due_today)} задач, в покупках активных пунктов: {active_shopping_count}."
    )
    if overdue:
        text = f"{text} Просроченных задач: {len(overdue)}."
    return f"{text} Мягко собираем день.", cat_type


async def build_evening_reminder_text(
    session: AsyncSession,
    context: CoupleScheduleContext,
) -> tuple[str, CatNotificationType | None]:
    tasks = await TaskRepository(session).list_active_for_users(context.member_ids)
    overdue = overdue_tasks(tasks, context.now)
    active_tasks = len([task for task in tasks if task.status in {"OPEN", "ASSIGNED", "OVERDUE"}])
    cat_type = CatNotificationType.OVERDUE if overdue else CatNotificationType.SLEEPY
    text = f"Вечерняя сверка: активных задач {active_tasks}."
    if overdue:
        text = f"{text} Просроченных: {len(overdue)}."
    return f"{text} Можно закрыть маленький хвостик и выдохнуть.", cat_type


async def build_recap_text(session: AsyncSession, context: CoupleScheduleContext, *, period: str) -> str:
    return await AnalyticsService(session).build_recap_text(
        member_ids=context.member_ids,
        local_now=context.local_now,
        period=period,
    )


def tasks_due_on_local_date(tasks: list[Task], local_now: datetime) -> list[Task]:
    return [
        task
        for task in tasks
        if task.deadline is not None and task.deadline.astimezone(local_now.tzinfo).date() == local_now.date()
    ]


def overdue_tasks(tasks: list[Task], now: datetime) -> list[Task]:
    return [
        task
        for task in tasks
        if task.deadline is not None and task.deadline <= now and task.status in {"ASSIGNED", "OPEN", "OVERDUE"}
    ]


def is_same_local_minute(local_now: datetime, scheduled_time: time) -> bool:
    return local_now.hour == scheduled_time.hour and local_now.minute == scheduled_time.minute


def local_schedule_datetime(local_now: datetime, scheduled_time: time) -> datetime:
    local_scheduled = datetime.combine(local_now.date(), scheduled_time, tzinfo=local_now.tzinfo)
    return local_scheduled.astimezone(timezone.utc)


def schedule_time_for_type(notification_type: str) -> time:
    if notification_type == "morning_reminder":
        return MORNING_REMINDER_TIME
    if notification_type == "evening_reminder":
        return EVENING_REMINDER_TIME
    return RECAP_TIME


def build_dedupe_key(couple: Couple, user: User, notification_type: str, local_now: datetime) -> str:
    if notification_type == "weekly_recap":
        period_key = f"{local_now.isocalendar().year}-W{local_now.isocalendar().week:02d}"
    elif notification_type == "monthly_recap":
        recap_month = local_now.replace(day=1) - timedelta(days=1) if local_now.day == 1 else local_now
        period_key = recap_month.strftime("%Y-%m")
    else:
        period_key = local_now.strftime("%Y-%m-%d")
    return f"{notification_type}:couple:{couple.id}:user:{user.id}:{period_key}"
