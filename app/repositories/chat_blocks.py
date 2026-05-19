from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ChatBlock


class ChatBlockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, *, user_id: int, chat_id: int, block_key: str) -> ChatBlock | None:
        result = await self.session.execute(
            select(ChatBlock).where(
                ChatBlock.user_id == user_id,
                ChatBlock.chat_id == chat_id,
                ChatBlock.block_key == block_key,
            )
        )
        return result.scalar_one_or_none()

    async def set_message_ids(self, *, user_id: int, chat_id: int, block_key: str, message_ids: list[int]) -> ChatBlock:
        block = await self.get(user_id=user_id, chat_id=chat_id, block_key=block_key)
        if block is None:
            block = ChatBlock(
                user_id=user_id,
                chat_id=chat_id,
                block_key=block_key,
                message_ids=message_ids,
            )
            self.session.add(block)
        else:
            block.message_ids = message_ids

        await self.session.flush()
        return block

    async def add_message_ids(self, *, user_id: int, chat_id: int, block_key: str, message_ids: list[int]) -> ChatBlock:
        block = await self.get(user_id=user_id, chat_id=chat_id, block_key=block_key)
        if block is None:
            return await self.set_message_ids(
                user_id=user_id,
                chat_id=chat_id,
                block_key=block_key,
                message_ids=message_ids,
            )

        merged_message_ids = list(dict.fromkeys([*block.message_ids, *message_ids]))
        block.message_ids = merged_message_ids
        await self.session.flush()
        return block

    async def clear(self, *, user_id: int, chat_id: int, block_key: str) -> None:
        block = await self.get(user_id=user_id, chat_id=chat_id, block_key=block_key)
        if block is not None:
            block.message_ids = []
            await self.session.flush()
