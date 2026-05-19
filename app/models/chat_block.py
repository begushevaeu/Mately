from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import CreatedAtMixin, UpdatedAtMixin


class ChatBlock(CreatedAtMixin, UpdatedAtMixin, Base):
    __tablename__ = "chat_blocks"
    __table_args__ = (
        UniqueConstraint("user_id", "chat_id", "block_key", name="uq_chat_blocks_user_chat_block"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    block_key: Mapped[str] = mapped_column(String(64), nullable=False)
    message_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False, default=list)
