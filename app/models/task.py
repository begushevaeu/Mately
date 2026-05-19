from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import CreatedAtMixin


class Task(CreatedAtMixin, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        CheckConstraint(
            "status in ('OPEN', 'ASSIGNED', 'COMPLETED', 'OVERDUE', 'ARCHIVED')",
            name="task_status",
        ),
        CheckConstraint(
            "recurrence_type is null or recurrence_type in ('DAILY', 'WEEKLY', 'MONTHLY', 'CUSTOM')",
            name="task_recurrence_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=false())
    recurrence_type: Mapped[str | None] = mapped_column(String(32))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="OPEN", index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    history_events: Mapped[list["TaskHistory"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class TaskHistory(Base):
    __tablename__ = "task_history"
    __table_args__ = (
        CheckConstraint(
            "event_type in ('CREATED', 'ASSIGNED', 'COMPLETED', 'OVERDUE', 'ARCHIVED', 'UPDATED', 'RECURRENCE_CREATED')",
            name="task_history_event_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    details: Mapped[str | None] = mapped_column(Text)

    task: Mapped["Task"] = relationship(back_populates="history_events")
