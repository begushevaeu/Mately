from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import pytest

from app.models import Couple, CoupleReminderSettings
from app.services.reminder_settings import (
    ReminderSettingsService,
    ReminderSettingsServiceError,
    format_reminder_time,
    parse_reminder_time,
)


@dataclass(slots=True)
class FakeReminderSettingsRepository:
    settings_by_couple: dict[int, CoupleReminderSettings] = field(default_factory=dict)

    async def get_or_create(self, couple_id: int) -> CoupleReminderSettings:
        settings = self.settings_by_couple.get(couple_id)
        if settings is None:
            settings = CoupleReminderSettings(
                couple_id=couple_id,
                morning_enabled=True,
                morning_time=time(hour=9),
                evening_enabled=True,
                evening_time=time(hour=21),
                reminders_paused=False,
            )
            self.settings_by_couple[couple_id] = settings
        return settings

    async def save(self, settings: CoupleReminderSettings) -> CoupleReminderSettings:
        self.settings_by_couple[settings.couple_id] = settings
        return settings


@pytest.mark.asyncio
async def test_reminder_settings_can_toggle_and_update_times() -> None:
    couple = Couple(id=1, invite_code="ABC12345", timezone="Europe/Moscow")
    repository = FakeReminderSettingsRepository()
    service = ReminderSettingsService(settings=repository)

    settings = await service.toggle_morning(couple)
    await service.set_evening_time(couple, time(hour=22, minute=15))
    await service.toggle_pause(couple)

    assert settings.morning_enabled is False
    assert repository.settings_by_couple[couple.id].evening_time == time(hour=22, minute=15)
    assert repository.settings_by_couple[couple.id].evening_enabled is True
    assert repository.settings_by_couple[couple.id].reminders_paused is True


def test_parse_reminder_time_accepts_compact_inputs() -> None:
    assert parse_reminder_time("9").value == time(hour=9)
    assert parse_reminder_time("09:30").value == time(hour=9, minute=30)
    assert parse_reminder_time("21.05").value == time(hour=21, minute=5)
    assert format_reminder_time(time(hour=7, minute=5)) == "07:05"


def test_parse_reminder_time_rejects_invalid_values() -> None:
    with pytest.raises(ReminderSettingsServiceError):
        parse_reminder_time("25:00")
