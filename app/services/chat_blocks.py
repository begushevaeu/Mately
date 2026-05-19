import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.chat_blocks import ChatBlockRepository

logger = logging.getLogger(__name__)

TASKS_BLOCK_KEY = "tasks"


class ChatBlockService:
    def __init__(
        self,
        session: AsyncSession | None = None,
        blocks: ChatBlockRepository | None = None,
    ) -> None:
        if session is None and blocks is None:
            raise ValueError("session is required when repository is not provided")
        self.blocks = blocks or ChatBlockRepository(session)  # type: ignore[arg-type]

    async def reset_block(self, *, bot: Bot, user: User, chat_id: int, block_key: str) -> None:
        block = await self.blocks.get(user_id=user.id, chat_id=chat_id, block_key=block_key)
        if block is None:
            return

        for message_id in block.message_ids:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except TelegramAPIError:
                logger.debug("Failed to delete stale block message", exc_info=True)

        await self.blocks.clear(user_id=user.id, chat_id=chat_id, block_key=block_key)

    async def remember_messages(self, *, user: User, chat_id: int, block_key: str, messages: list[Message]) -> None:
        message_ids = [message.message_id for message in messages]
        await self.blocks.set_message_ids(
            user_id=user.id,
            chat_id=chat_id,
            block_key=block_key,
            message_ids=message_ids,
        )

    async def add_messages(self, *, user: User, chat_id: int, block_key: str, messages: list[Message]) -> None:
        message_ids = [message.message_id for message in messages]
        await self.blocks.add_message_ids(
            user_id=user.id,
            chat_id=chat_id,
            block_key=block_key,
            message_ids=message_ids,
        )
