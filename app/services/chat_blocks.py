import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories.chat_blocks import ChatBlockRepository

logger = logging.getLogger(__name__)

TASKS_BLOCK_KEY = "tasks"
CONTENT_BLOCK_KEY = "content"
SHOPPING_BLOCK_KEY = "shopping"
PLACES_BLOCK_KEY = "places"
ADDITIONAL_BLOCK_KEY = "additional"
MENU_HINT_BLOCK_KEY = "menu_hint"
STATISTICS_BLOCK_KEY = "statistics"
SETTINGS_BLOCK_KEY = "settings"
PARTNER_ALIAS_BLOCK_KEY = "partner_alias"
ONBOARDING_BLOCK_KEY = "onboarding"
BOT_MANAGED_BLOCK_KEY_SUFFIX = ":bot"
MAIN_MENU_BLOCK_KEYS = (
    TASKS_BLOCK_KEY,
    CONTENT_BLOCK_KEY,
    SHOPPING_BLOCK_KEY,
    PLACES_BLOCK_KEY,
    ADDITIONAL_BLOCK_KEY,
    MENU_HINT_BLOCK_KEY,
    STATISTICS_BLOCK_KEY,
    SETTINGS_BLOCK_KEY,
)


def bot_managed_block_key(block_key: str) -> str:
    return f"{block_key}{BOT_MANAGED_BLOCK_KEY_SUFFIX}"


def is_bot_managed_message(message: Message) -> bool:
    from_user = getattr(message, "from_user", None)
    if from_user is None:
        return True

    return bool(getattr(from_user, "is_bot", False))


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
        attempted_message_ids: set[int] = set()
        for current_block_key in (block_key, bot_managed_block_key(block_key)):
            block = await self.blocks.get(user_id=user.id, chat_id=chat_id, block_key=current_block_key)
            if block is None:
                continue

            for message_id in block.message_ids:
                if message_id in attempted_message_ids:
                    continue

                attempted_message_ids.add(message_id)
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=message_id)
                except TelegramAPIError:
                    logger.debug("Failed to delete stale block message", exc_info=True)

            await self.blocks.clear(user_id=user.id, chat_id=chat_id, block_key=current_block_key)

    async def reset_blocks(self, *, bot: Bot, user: User, chat_id: int, block_keys: tuple[str, ...]) -> None:
        for block_key in block_keys:
            await self.reset_block(bot=bot, user=user, chat_id=chat_id, block_key=block_key)

    async def reset_other_blocks(self, *, bot: Bot, user: User, chat_id: int, current_block_key: str) -> None:
        await self.reset_blocks(
            bot=bot,
            user=user,
            chat_id=chat_id,
            block_keys=tuple(block_key for block_key in MAIN_MENU_BLOCK_KEYS if block_key != current_block_key),
        )

    async def remember_messages(self, *, user: User, chat_id: int, block_key: str, messages: list[Message]) -> None:
        message_ids = [message.message_id for message in messages]
        await self.blocks.set_message_ids(
            user_id=user.id,
            chat_id=chat_id,
            block_key=block_key,
            message_ids=message_ids,
        )
        bot_message_ids = [message.message_id for message in messages if is_bot_managed_message(message)]
        if bot_message_ids:
            await self.blocks.set_message_ids(
                user_id=user.id,
                chat_id=chat_id,
                block_key=bot_managed_block_key(block_key),
                message_ids=bot_message_ids,
            )
        else:
            await self.blocks.clear(user_id=user.id, chat_id=chat_id, block_key=bot_managed_block_key(block_key))

    async def add_messages(self, *, user: User, chat_id: int, block_key: str, messages: list[Message]) -> None:
        message_ids = [message.message_id for message in messages]
        await self.blocks.add_message_ids(
            user_id=user.id,
            chat_id=chat_id,
            block_key=block_key,
            message_ids=message_ids,
        )
        bot_message_ids = [message.message_id for message in messages if is_bot_managed_message(message)]
        if bot_message_ids:
            await self.blocks.add_message_ids(
                user_id=user.id,
                chat_id=chat_id,
                block_key=bot_managed_block_key(block_key),
                message_ids=bot_message_ids,
            )
