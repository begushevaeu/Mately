from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import CreatedAtMixin


class Couple(CreatedAtMixin, Base):
    __tablename__ = "couples"
    __table_args__ = (UniqueConstraint("invite_code", name="uq_couples_invite_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    invite_code: Mapped[str] = mapped_column(String(32), nullable=False)
    invite_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="Europe/Moscow")

    members: Mapped[list["CoupleMember"]] = relationship(
        back_populates="couple",
        cascade="all, delete-orphan",
    )


class CoupleMember(CreatedAtMixin, Base):
    __tablename__ = "couple_members"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_couple_members_user_id"),
        UniqueConstraint("user_id", "couple_id", name="uq_couple_members_user_couple"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    couple_id: Mapped[int] = mapped_column(
        ForeignKey("couples.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="couple_membership")
    couple: Mapped["Couple"] = relationship(back_populates="members")
