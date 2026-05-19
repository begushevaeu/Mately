from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.main_menu import (
    SETTINGS_BUTTON,
    STATISTICS_BUTTON,
    build_main_menu,
)
from app.bot.keyboards.settings import build_settings_keyboard
from app.services.chat_blocks import (
    SETTINGS_BLOCK_KEY,
    STATISTICS_BLOCK_KEY,
    ChatBlockService,
)
from app.services.couples import OnboardingResult, OnboardingStatus

router = Router()


async def ensure_main_menu_access(message: Message, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return None

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return None

    return result


async def show_main_menu_block(
    *,
    message: Message,
    session: AsyncSession,
    bot: Bot,
    result: OnboardingResult,
    block_key: str,
    text: str,
    reply_markup,
) -> None:
    blocks = ChatBlockService(session)
    await blocks.reset_other_blocks(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        current_block_key=block_key,
    )
    await blocks.reset_block(bot=bot, user=result.user, chat_id=message.chat.id, block_key=block_key)
    sent_message = await message.answer(text, reply_markup=reply_markup)
    await blocks.remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=block_key,
        messages=[message, sent_message],
    )


@router.message(F.text == STATISTICS_BUTTON)
async def handle_statistics_menu(message: Message, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_main_menu_access(message, session)
    if result is None:
        return

    await show_main_menu_block(
        message=message,
        session=session,
        bot=bot,
        result=result,
        block_key=STATISTICS_BLOCK_KEY,
        text="Статистика появится после первых задач и отметок контента. Пока тут будет тихий уголок ожидания.",
        reply_markup=build_main_menu(),
    )


@router.message(F.text == SETTINGS_BUTTON)
async def handle_settings_menu(message: Message, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_main_menu_access(message, session)
    if result is None:
        return

    timezone = result.couple.timezone if result.couple is not None else "Europe/Moscow"
    await show_main_menu_block(
        message=message,
        session=session,
        bot=bot,
        result=result,
        block_key=SETTINGS_BLOCK_KEY,
        text=(
            "Настройки Mately\n\n"
            f"Часовой пояс пары: {timezone}\n"
            "Доступные команды: /menu, /cancel, /help"
        ),
        reply_markup=build_settings_keyboard(),
    )


@router.message(F.text)
async def handle_unknown_menu_text(message: Message, session: AsyncSession) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return

    await message.answer(
        "Я пока не знаю такую команду. Выберите раздел из меню.",
        reply_markup=build_main_menu(),
    )
