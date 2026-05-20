from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import CreatedAtMixin


class PlaceItem(CreatedAtMixin, Base):
    __tablename__ = "place_items"
    __table_args__ = (
        CheckConstraint(
            "category in ('RESTAURANT', 'CAFE', 'CINEMA', 'THEATRE', 'PARK', 'MUSEUM', 'BAR', 'CONCERT', 'EXHIBITION', 'WALK', 'TRIP', 'OTHER')",
            name="place_item_category",
        ),
        CheckConstraint("status in ('NOT_VISITED', 'VISITED')", name="place_item_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="NOT_VISITED", index=True)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    visited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    visited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    ratings: Mapped[list["PlaceRating"]] = relationship(
        back_populates="place_item",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["PlaceComment"]] = relationship(
        back_populates="place_item",
        cascade="all, delete-orphan",
    )


class PlaceRating(CreatedAtMixin, Base):
    __tablename__ = "place_ratings"
    __table_args__ = (
        CheckConstraint("score between 1 and 10", name="place_rating_score_range"),
        UniqueConstraint("place_id", "user_id", name="uq_place_ratings_place_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("place_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)

    place_item: Mapped["PlaceItem"] = relationship(back_populates="ratings")


class PlaceComment(CreatedAtMixin, Base):
    __tablename__ = "place_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("place_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    place_item: Mapped["PlaceItem"] = relationship(back_populates="comments")
