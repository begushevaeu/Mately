from __future__ import annotations

from datetime import time

from sqlalchemy import Boolean, ForeignKey, Time, UniqueConstraint, false, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import CreatedAtMixin, UpdatedAtMixin


class CoupleReminderSettings(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "couple_reminder_settings"
    __table_args__ = (
        UniqueConstraint("couple_id", name="uq_couple_reminder_settings_couple_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"), nullable=False, index=True)
    morning_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    morning_time: Mapped[time] = mapped_column(Time(), nullable=False, default=time(9, 0), server_default="09:00:00")
    evening_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    evening_time: Mapped[time] = mapped_column(Time(), nullable=False, default=time(21, 0), server_default="21:00:00")
    reminders_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=false())
