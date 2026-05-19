from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import CreatedAtMixin, UpdatedAtMixin


class PartnerAlias(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "partner_aliases"
    __table_args__ = (
        UniqueConstraint("owner_user_id", "partner_user_id", name="uq_partner_aliases_owner_partner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    partner_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    emoji: Mapped[str] = mapped_column(String(16), nullable=False)
    nominative: Mapped[str] = mapped_column(String(64), nullable=False)
    genitive: Mapped[str] = mapped_column(String(64), nullable=False)
    dative: Mapped[str] = mapped_column(String(64), nullable=False)
