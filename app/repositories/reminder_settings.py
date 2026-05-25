from __future__ import annotations

from datetime import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CoupleReminderSettings


class ReminderSettingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_couple_id(self, couple_id: int) -> CoupleReminderSettings | None:
        result = await self.session.execute(
            select(CoupleReminderSettings).where(CoupleReminderSettings.couple_id == couple_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, couple_id: int) -> CoupleReminderSettings:
        settings = await self.get_by_couple_id(couple_id)
        if settings is not None:
            return settings

        settings = CoupleReminderSettings(
            couple_id=couple_id,
            morning_enabled=True,
            morning_time=time(hour=9),
            evening_enabled=True,
            evening_time=time(hour=21),
            reminders_paused=False,
        )
        self.session.add(settings)
        await self.session.flush()
        return settings

    async def save(self, settings: CoupleReminderSettings) -> CoupleReminderSettings:
        await self.session.flush()
        return settings
