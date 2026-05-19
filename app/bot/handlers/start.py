from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result

router = Router()


@router.message(CommandStart())
async def handle_start(message: Message, session: AsyncSession) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is not None:
        await answer_for_onboarding_state(message, result)
