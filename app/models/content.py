from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.mixins import CreatedAtMixin


class ContentItem(CreatedAtMixin, Base):
    __tablename__ = "content_items"
    __table_args__ = (
        CheckConstraint(
            "category in ('BOOK', 'ANIME', 'MOVIE', 'CARTOON', 'SERIES', 'THEATRE', 'MUSICAL', 'GAME')",
            name="content_item_category",
        ),
        CheckConstraint("status in ('NOT_COMPLETED', 'COMPLETED')", name="content_item_status"),
        Index("ix_content_items_couple_status_category", "couple_id", "status", "category"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    couple_id: Mapped[int] = mapped_column(ForeignKey("couples.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="NOT_COMPLETED", index=True)
    added_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    ratings: Mapped[list["Rating"]] = relationship(
        back_populates="content_item",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["Comment"]] = relationship(
        back_populates="content_item",
        cascade="all, delete-orphan",
    )


class Rating(CreatedAtMixin, Base):
    __tablename__ = "ratings"
    __table_args__ = (
        CheckConstraint("response in ('RATED', 'NOT_ACQUAINTED')", name="rating_response"),
        CheckConstraint(
            "(response = 'RATED' and score between 1 and 10) "
            "or (response = 'NOT_ACQUAINTED' and score is null and emoji is null)",
            name="rating_response_score",
        ),
        UniqueConstraint("content_id", "user_id", name="uq_ratings_content_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    score: Mapped[int | None] = mapped_column(Integer)
    emoji: Mapped[str | None] = mapped_column(String(32))
    response: Mapped[str] = mapped_column(String(32), nullable=False, default="RATED", server_default="RATED")

    content_item: Mapped["ContentItem"] = relationship(back_populates="ratings")


class Comment(CreatedAtMixin, Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(ForeignKey("content_items.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    content_item: Mapped["ContentItem"] = relationship(back_populates="comments")
