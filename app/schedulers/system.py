from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.ai.cozy import CozyMessageTheme, append_cozy_suffix
from app.models import Couple, CoupleReminderSettings, Task, User
from app.notifications.cats import CatNotificationType
from app.notifications.delivery import send_user_notification
from app.repositories.chat_blocks import ChatBlockRepository
from app.repositories.couples import CoupleRepository
from app.repositories.notifications import NotificationRepository
from app.repositories.reminder_settings import ReminderSettingsRepository
from app.repositories.tasks import TaskRepository
from app.schedulers.shopping import archive_expired_shopping_items
from app.services.chat_blocks import BOT_MANAGED_BLOCK_KEY_SUFFIX
from app.services.tasks import CoupleTaskContext, TaskService
from app.utils.dates import get_timezone

logger = logging.getLogger(__name__)

MORNING_REMINDER_TIME = time(hour=9, minute=0)
EVENING_REMINDER_TIME = time(hour=21, minute=0)
RECAP_TIME = time(hour=10, minute=0)
MORNING_DIGEST_TASK_LIMIT = 5


@dataclass(slots=True)
class CoupleScheduleContext:
    couple: Couple
    members: list[User]
    local_now: datetime
    now: datetime

    @property
    def member_ids(self) -> list[int]:
        return [member.id for member in self.members]


@dataclass(slots=True)
class DueNotification:
    notification_type: str
    text: str
    cat_type: CatNotificationType | None
    scheduled_time: time


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
        if is_same_local_minute(context.local_now, MORNING_REMINDER_TIME):
            await cleanup_stale_bot_messages_for_context(session, bot, context)

        for notification in await build_due_notifications(session, context):
            scheduled_at = local_schedule_datetime(context.local_now, notification.scheduled_time)
            for member in members:
                delivered = await send_scheduled_notification_once(
                    session=session,
                    bot=bot,
                    couple_id=couple.id,
                    user=member,
                    notification_type=notification.notification_type,
                    text=notification.text,
                    scheduled_at=scheduled_at,
                    dedupe_key=build_dedupe_key(couple, member, notification.notification_type, context.local_now),
                    cat_notification_type=notification.cat_type,
                )
                sent_count += int(delivered)

    return sent_count


async def cleanup_stale_bot_messages_for_context(
    session: AsyncSession,
    bot: Bot,
    context: CoupleScheduleContext,
) -> int:
    local_day_start = datetime.combine(context.local_now.date(), time.min, tzinfo=context.local_now.tzinfo)
    updated_before = local_day_start.astimezone(timezone.utc)
    blocks = ChatBlockRepository(session)
    stale_blocks = await blocks.list_stale_blocks_for_users(
        user_ids=context.member_ids,
        block_key_suffix=BOT_MANAGED_BLOCK_KEY_SUFFIX,
        updated_before=updated_before,
    )
    deleted_count = 0
    for block in stale_blocks:
        for message_id in block.message_ids:
            try:
                await bot.delete_message(chat_id=block.chat_id, message_id=message_id)
                deleted_count += 1
            except TelegramAPIError:
                logger.debug("Failed to delete stale morning cleanup message", exc_info=True)

        await blocks.clear(user_id=block.user_id, chat_id=block.chat_id, block_key=block.block_key)

    return deleted_count


async def build_due_notifications(
    session: AsyncSession,
    context: CoupleScheduleContext,
) -> list[DueNotification]:
    settings = await ReminderSettingsRepository(session).get_or_create(context.couple.id)
    notifications: list[DueNotification] = []
    for notification_type in due_reminder_types(settings, context.local_now):
        if notification_type == "morning_reminder":
            text, cat_type = await build_morning_reminder_text(session, context)
            subject = "утренний дайджест"
        else:
            text, cat_type = await build_evening_reminder_text(session, context)
            subject = "вечерняя сверка"

        text = await append_cozy_suffix(text, theme=CozyMessageTheme.RECAP, subject=subject)
        notifications.append(
            DueNotification(
                notification_type=notification_type,
                text=text,
                cat_type=cat_type,
                scheduled_time=schedule_time_for_type(notification_type, settings),
            )
        )

    return notifications


async def send_scheduled_notification_once(
    *,
    session: AsyncSession,
    bot: Bot,
    couple_id: int,
    user: User,
    notification_type: str,
    text: str,
    scheduled_at: datetime,
    dedupe_key: str,
    cat_notification_type: CatNotificationType | None,
) -> bool:
    notifications = NotificationRepository(session)
    existing = await notifications.get_by_dedupe_key(dedupe_key, couple_id)
    if existing is not None:
        return False

    notification = await notifications.create_pending(
        couple_id=couple_id,
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
    tasks = await TaskRepository(session).list_active_for_couple(context.couple.id)
    text = build_morning_task_digest_text(tasks, local_now=context.local_now, now=context.now)
    cat_type = CatNotificationType.OVERDUE if overdue_tasks(tasks, context.now) else CatNotificationType.RECAP
    return text, cat_type


async def build_evening_reminder_text(
    session: AsyncSession,
    context: CoupleScheduleContext,
) -> tuple[str, CatNotificationType | None]:
    tasks = await TaskRepository(session).list_active_for_couple(context.couple.id)
    overdue = overdue_tasks(tasks, context.now)
    active_tasks = len([task for task in tasks if task.status in {"OPEN", "ASSIGNED", "OVERDUE"}])
    cat_type = CatNotificationType.OVERDUE if overdue else CatNotificationType.SLEEPY
    text = f"Вечерняя сверка: активных задач {active_tasks}."
    if overdue:
        text = f"{text} Просроченных: {len(overdue)}."
    return f"{text} Можно закрыть маленький хвостик и выдохнуть.", cat_type


def build_morning_task_digest_text(
    tasks: list[Task],
    *,
    local_now: datetime,
    now: datetime,
) -> str:
    unfinished = [task for task in tasks if task.status in {"OPEN", "ASSIGNED", "OVERDUE"}]
    if not unfinished:
        return "Доброе утро. Незавершённых задач нет. Пусть день начнётся спокойно."

    overdue = set(overdue_tasks(unfinished, now))
    due_today = set(tasks_due_on_local_date(unfinished, local_now))
    lines = ["Доброе утро. Незавершённые задачи:"]
    for task in unfinished[:MORNING_DIGEST_TASK_LIMIT]:
        note = morning_task_note(task, overdue=overdue, due_today=due_today)
        lines.append(f"• {format_morning_task_title(task)}{note}")

    remaining_count = len(unfinished) - MORNING_DIGEST_TASK_LIMIT
    if remaining_count > 0:
        lines.append(f"И ещё {remaining_count}.")
    if overdue:
        lines.append(f"Просроченных: {len(overdue)}.")
    lines.append("Хорошего дня, двигаемся мягко.")
    return "\n".join(lines)


def morning_task_note(task: Task, *, overdue: set[Task], due_today: set[Task]) -> str:
    if task in overdue:
        return " (просрочена)"
    if task in due_today:
        return " (сегодня)"
    return ""


def format_morning_task_title(task: Task) -> str:
    title = " ".join(task.title.split())
    if len(title) <= 80:
        return title
    return f"{title[:77]}..."


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


def due_reminder_types(settings: CoupleReminderSettings, local_now: datetime) -> list[str]:
    if settings.reminders_paused:
        return []

    due_types = []
    if settings.morning_enabled and is_same_local_minute(local_now, settings.morning_time):
        due_types.append("morning_reminder")
    if settings.evening_enabled and is_same_local_minute(local_now, settings.evening_time):
        due_types.append("evening_reminder")
    return due_types


def schedule_time_for_type(notification_type: str, settings: CoupleReminderSettings | None = None) -> time:
    if notification_type == "morning_reminder":
        return settings.morning_time if settings is not None else MORNING_REMINDER_TIME
    if notification_type == "evening_reminder":
        return settings.evening_time if settings is not None else EVENING_REMINDER_TIME
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
