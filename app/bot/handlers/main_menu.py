from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import AnalyticsService
from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.blocks import (
    CLOSE_BLOCK_CALLBACK_PREFIX,
    parse_close_block_callback,
)
from app.bot.keyboards.main_menu import (
    SETTINGS_BUTTON,
    STATISTICS_BUTTON,
    build_main_menu,
)
from app.bot.keyboards.settings import build_settings_keyboard
from app.bot.keyboards.statistics import (
    STATISTICS_MONTH_CALLBACK,
    STATISTICS_WEEK_CALLBACK,
    build_statistics_keyboard,
)
from app.services.chat_blocks import (
    MAIN_MENU_BLOCK_KEYS,
    SETTINGS_BLOCK_KEY,
    STATISTICS_BLOCK_KEY,
    ChatBlockService,
)
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile
from app.utils.dates import get_timezone

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
    parse_mode: str | None = None,
) -> None:
    blocks = ChatBlockService(session)
    await blocks.reset_other_blocks(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        current_block_key=block_key,
    )
    await blocks.reset_block(bot=bot, user=result.user, chat_id=message.chat.id, block_key=block_key)
    sent_message = await message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)
    await blocks.remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=block_key,
        messages=[message, sent_message],
    )


async def build_statistics_panel_text(
    session: AsyncSession,
    result: OnboardingResult,
    *,
    period: str,
) -> str:
    if result.couple is None:
        return "📊 <b>Статистика</b>\n\nПара пока не найдена."

    local_now = datetime.now(timezone.utc).astimezone(get_timezone(result.couple.timezone or "Europe/Moscow"))
    return await AnalyticsService(session).build_recap_text_for_couple(
        couple=result.couple,
        local_now=local_now,
        period=period,
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

    text = await build_statistics_panel_text(session, result, period="week")
    await show_main_menu_block(
        message=message,
        session=session,
        bot=bot,
        result=result,
        block_key=STATISTICS_BLOCK_KEY,
        text=text,
        reply_markup=build_statistics_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data.in_({STATISTICS_WEEK_CALLBACK, STATISTICS_MONTH_CALLBACK}))
async def handle_statistics_period(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE:
        await callback.answer()
        return

    period = "month" if callback.data == STATISTICS_MONTH_CALLBACK else "week"
    text = await build_statistics_panel_text(session, result, period=period)
    await callback.message.edit_text(text, reply_markup=build_statistics_keyboard(), parse_mode="HTML")
    await callback.answer()


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
