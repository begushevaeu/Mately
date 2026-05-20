from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.blocks import (
    CLOSE_BLOCK_CALLBACK_PREFIX,
    build_close_block_keyboard,
    parse_close_block_callback,
)
from app.bot.keyboards.main_menu import (
    SETTINGS_BUTTON,
    STATISTICS_BUTTON,
    build_main_menu,
)
from app.bot.keyboards.settings import build_settings_keyboard
from app.services.chat_blocks import (
    MAIN_MENU_BLOCK_KEYS,
    SETTINGS_BLOCK_KEY,
    STATISTICS_BLOCK_KEY,
    ChatBlockService,
)
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile

router = Router()


async def ensure_main_menu_access(message: Message, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return None

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return None

    return result


async def get_current_result_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult:
    profile = TelegramUserProfile(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    return await CoupleService(session).start_for_profile(profile)


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


@router.callback_query(F.data.startswith(CLOSE_BLOCK_CALLBACK_PREFIX))
async def handle_close_block(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await callback.answer()
    if callback.message is None or callback.data is None:
        return

    block_key = parse_close_block_callback(callback.data)
    if block_key not in MAIN_MENU_BLOCK_KEYS:
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE:
        return

    await state.clear()
    await ChatBlockService(session).reset_block(
        bot=bot,
        user=result.user,
        chat_id=callback.message.chat.id,
        block_key=block_key,
    )
    try:
        await bot.delete_message(chat_id=callback.message.chat.id, message_id=callback.message.message_id)
    except TelegramAPIError:
        pass


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
        reply_markup=build_close_block_keyboard(STATISTICS_BLOCK_KEY),
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
