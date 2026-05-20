from aiogram import Bot, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import (
    answer_for_onboarding_state,
    get_current_onboarding_result,
    reset_recoverable_blocks,
)
from app.bot.handlers.partner_aliases import maybe_prompt_partner_alias

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await state.clear()
    result = await get_current_onboarding_result(message, session)
    if result is not None:
        await reset_recoverable_blocks(session=session, bot=bot, result=result, chat_id=message.chat.id)
        await answer_for_onboarding_state(message, result)
        await maybe_prompt_partner_alias(message, result, session, state, bot)
