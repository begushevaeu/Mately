from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import time

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Couple, CoupleReminderSettings
from app.repositories.reminder_settings import ReminderSettingsRepository


class ReminderSettingsServiceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReminderTimeInput:
    value: time


class ReminderSettingsService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        settings: ReminderSettingsRepository | None = None,
    ) -> None:
        if session is None and settings is None:
            raise ValueError("session is required when repositories are not provided")

        self.settings = settings or ReminderSettingsRepository(session)  # type: ignore[arg-type]

    async def get_for_couple(self, couple: Couple) -> CoupleReminderSettings:
        return await self.settings.get_or_create(couple.id)

    async def toggle_morning(self, couple: Couple) -> CoupleReminderSettings:
        settings = await self.get_for_couple(couple)
        settings.morning_enabled = not settings.morning_enabled
        return await self.settings.save(settings)

    async def toggle_evening(self, couple: Couple) -> CoupleReminderSettings:
        settings = await self.get_for_couple(couple)
        settings.evening_enabled = not settings.evening_enabled
        return await self.settings.save(settings)

    async def toggle_pause(self, couple: Couple) -> CoupleReminderSettings:
        settings = await self.get_for_couple(couple)
        settings.reminders_paused = not settings.reminders_paused
        return await self.settings.save(settings)

    async def set_morning_time(self, couple: Couple, reminder_time: time) -> CoupleReminderSettings:
        settings = await self.get_for_couple(couple)
        settings.morning_time = reminder_time
        settings.morning_enabled = True
        return await self.settings.save(settings)

    async def set_evening_time(self, couple: Couple, reminder_time: time) -> CoupleReminderSettings:
        settings = await self.get_for_couple(couple)
        settings.evening_time = reminder_time
        settings.evening_enabled = True
        return await self.settings.save(settings)


def parse_reminder_time(value: str) -> ReminderTimeInput:
    normalized = value.strip().replace(".", ":").replace(" ", ":")
    match = re.fullmatch(r"([01]?\d|2[0-3])(?::([0-5]\d))?", normalized)
    if match is None:
        raise ReminderSettingsServiceError("Напиши время в формате 09:00")

    hour = int(match.group(1))
    minute = int(match.group(2) or "00")
    return ReminderTimeInput(value=time(hour=hour, minute=minute))


def format_reminder_time(value: time) -> str:
    return value.strftime("%H:%M")
