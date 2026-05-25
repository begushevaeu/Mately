from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.chat_blocks import BOT_MANAGED_BLOCK_KEY_SUFFIX
from app.models import Couple, CoupleReminderSettings, Task, User
from app.schedulers.system import (
    EVENING_REMINDER_TIME,
    MORNING_REMINDER_TIME,
    CoupleScheduleContext,
    build_morning_task_digest_text,
    build_dedupe_key,
    cleanup_stale_bot_messages_for_context,
    due_reminder_types,
    is_same_local_minute,
    local_schedule_datetime,
    overdue_tasks,
    schedule_time_for_type,
    tasks_due_on_local_date,
)


def test_scheduler_matches_couple_local_minute() -> None:
    local_now = datetime(2026, 5, 20, 9, 0, 30, tzinfo=timezone.utc)

    assert is_same_local_minute(local_now, MORNING_REMINDER_TIME) is True
    assert is_same_local_minute(local_now, EVENING_REMINDER_TIME) is False


def test_scheduler_dedupe_keys_use_local_periods() -> None:
    couple = Couple(id=10, invite_code="ABC12345", timezone="Europe/Moscow")
    user = User(id=20, telegram_id=200, username=None, first_name=None)
    monday = datetime(2026, 5, 18, 10, 0, tzinfo=timezone.utc)
    first_day = datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc)

    assert build_dedupe_key(couple, user, "morning_reminder", monday) == "morning_reminder:couple:10:user:20:2026-05-18"
    assert build_dedupe_key(couple, user, "weekly_recap", monday) == "weekly_recap:couple:10:user:20:2026-W21"
    assert build_dedupe_key(couple, user, "monthly_recap", monday) == "monthly_recap:couple:10:user:20:2026-05"
    assert build_dedupe_key(couple, user, "monthly_recap", first_day) == "monthly_recap:couple:10:user:20:2026-05"


def test_scheduler_records_local_scheduled_time_in_utc() -> None:
    local_now = datetime(2026, 5, 20, 9, 15, tzinfo=timezone.utc)

    assert local_schedule_datetime(local_now, time(hour=9, minute=0)) == datetime(
        2026,
        5,
        20,
        9,
        0,
        tzinfo=timezone.utc,
    )
    assert schedule_time_for_type("evening_reminder") is EVENING_REMINDER_TIME


def test_scheduler_uses_custom_reminder_times() -> None:
    settings = CoupleReminderSettings(
        couple_id=1,
        morning_enabled=True,
        morning_time=time(hour=8, minute=30),
        evening_enabled=True,
        evening_time=time(hour=22, minute=15),
        reminders_paused=False,
    )

    assert due_reminder_types(settings, datetime(2026, 5, 20, 8, 30, tzinfo=timezone.utc)) == ["morning_reminder"]
    assert due_reminder_types(settings, datetime(2026, 5, 20, 22, 15, tzinfo=timezone.utc)) == ["evening_reminder"]
    assert schedule_time_for_type("morning_reminder", settings) == time(hour=8, minute=30)


def test_scheduler_skips_disabled_and_paused_reminders() -> None:
    settings = CoupleReminderSettings(
        couple_id=1,
        morning_enabled=False,
        morning_time=time(hour=9),
        evening_enabled=True,
        evening_time=time(hour=21),
        reminders_paused=False,
    )

    assert due_reminder_types(settings, datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)) == []

    settings.reminders_paused = True

    assert due_reminder_types(settings, datetime(2026, 5, 20, 21, 0, tzinfo=timezone.utc)) == []


def test_scheduler_task_filters_use_deadlines() -> None:
    now = datetime(2026, 5, 20, 12, 0, tzinfo=timezone.utc)
    due_today = Task(id=1, title="A", created_by=1, assigned_to=2, status="ASSIGNED", deadline=now)
    overdue = Task(
        id=2,
        title="B",
        created_by=1,
        assigned_to=2,
        status="ASSIGNED",
        deadline=datetime(2026, 5, 19, 12, 0, tzinfo=timezone.utc),
    )
    later = Task(
        id=3,
        title="C",
        created_by=1,
        assigned_to=2,
        status="ASSIGNED",
        deadline=datetime(2026, 5, 21, 12, 0, tzinfo=timezone.utc),
    )

    assert tasks_due_on_local_date([due_today, overdue, later], now) == [due_today]
    assert overdue_tasks([due_today, overdue, later], now) == [due_today, overdue]


def test_morning_digest_lists_unfinished_tasks_and_empty_state() -> None:
    now = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)
    yesterday = datetime(2026, 5, 19, 18, 0, tzinfo=timezone.utc)
    active = Task(id=1, couple_id=1, title="Полить цветы", created_by=1, status="ASSIGNED", deadline=now)
    overdue = Task(id=2, couple_id=1, title="Купить корм", created_by=1, status="OVERDUE", deadline=yesterday)
    completed = Task(id=3, couple_id=1, title="Собрать сумку", created_by=1, status="COMPLETED", deadline=now)

    text = build_morning_task_digest_text([active, overdue, completed], local_now=now, now=now)
    empty_text = build_morning_task_digest_text([], local_now=now, now=now)

    assert "Незавершённые задачи" in text
    assert "Полить цветы (просрочена)" in text
    assert "Купить корм (просрочена)" in text
    assert "Собрать сумку" not in text
    assert "Просроченных: 2." in text
    assert "Незавершённых задач нет" in empty_text


@pytest.mark.asyncio
async def test_morning_cleanup_deletes_only_stale_bot_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    stale_block = SimpleNamespace(user_id=20, chat_id=2000, block_key="tasks:bot", message_ids=[101, 102])

    class FakeChatBlockRepository:
        calls: list[dict] = []
        cleared: list[tuple[int, int, str]] = []

        def __init__(self, _session) -> None:
            pass

        async def list_stale_blocks_for_users(self, **kwargs):
            self.__class__.calls.append(kwargs)
            return [stale_block]

        async def clear(self, *, user_id: int, chat_id: int, block_key: str) -> None:
            self.__class__.cleared.append((user_id, chat_id, block_key))

    class FakeBot:
        deleted_messages: list[tuple[int, int]]

        def __init__(self) -> None:
            self.deleted_messages = []

        async def delete_message(self, *, chat_id: int, message_id: int) -> None:
            self.deleted_messages.append((chat_id, message_id))

    monkeypatch.setattr("app.schedulers.system.ChatBlockRepository", FakeChatBlockRepository)
    context = CoupleScheduleContext(
        couple=Couple(id=10, invite_code="ABC12345", timezone="Europe/Moscow"),
        members=[
            User(id=20, telegram_id=200, username=None, first_name=None),
            User(id=21, telegram_id=201, username=None, first_name=None),
        ],
        local_now=datetime(2026, 5, 20, 9, 0, tzinfo=timezone(timedelta(hours=3))),
        now=datetime(2026, 5, 20, 6, 0, tzinfo=timezone.utc),
    )
    bot = FakeBot()

    deleted_count = await cleanup_stale_bot_messages_for_context(object(), bot, context)

    assert deleted_count == 2
    assert bot.deleted_messages == [(2000, 101), (2000, 102)]
    assert FakeChatBlockRepository.cleared == [(20, 2000, "tasks:bot")]
    assert FakeChatBlockRepository.calls == [
        {
            "user_ids": [20, 21],
            "block_key_suffix": BOT_MANAGED_BLOCK_KEY_SUFFIX,
            "updated_before": datetime(2026, 5, 19, 21, 0, tzinfo=timezone.utc),
        }
    ]
