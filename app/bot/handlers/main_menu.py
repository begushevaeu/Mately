import logging
from datetime import datetime, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import AnalyticsService
from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.additional import (
    ADDITIONAL_EXPORT_CALLBACK,
    ADDITIONAL_MENU_CALLBACK,
    ADDITIONAL_SETTINGS_CALLBACK,
    ADDITIONAL_STATISTICS_CALLBACK,
    build_additional_keyboard,
)
from app.bot.keyboards.blocks import (
    CLOSE_BLOCK_CALLBACK_PREFIX,
    parse_close_block_callback,
)
from app.bot.keyboards.main_menu import (
    ADDITIONAL_BUTTON,
    build_main_menu,
)
from app.bot.keyboards.settings import (
    SET_EVENING_REMINDER_TIME_CALLBACK,
    SET_MORNING_REMINDER_TIME_CALLBACK,
    TOGGLE_EVENING_REMINDER_CALLBACK,
    TOGGLE_MORNING_REMINDER_CALLBACK,
    TOGGLE_REMINDERS_PAUSE_CALLBACK,
    build_settings_keyboard,
)
from app.bot.keyboards.statistics import (
    STATISTICS_MONTH_CALLBACK,
    STATISTICS_WEEK_CALLBACK,
    build_statistics_keyboard,
)
from app.bot.states.settings import ReminderSettingsStates
from app.services.chat_blocks import (
    ADDITIONAL_BLOCK_KEY,
    MAIN_MENU_BLOCK_KEYS,
    MENU_HINT_BLOCK_KEY,
    ChatBlockService,
)
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile
from app.services.exports import CoupleExportService
from app.services.reminder_settings import (
    ReminderSettingsService,
    ReminderSettingsServiceError,
    format_reminder_time,
    parse_reminder_time,
)
from app.utils.dates import get_timezone

router = Router()
logger = logging.getLogger(__name__)


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


async def delete_irrelevant_user_message(bot: Bot, message: Message) -> bool:
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except TelegramAPIError:
        logger.debug("Failed to delete irrelevant user message", exc_info=True)
        return False

    return True


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


async def show_menu_hint_for_irrelevant_message(
    *,
    message: Message,
    session: AsyncSession,
    bot: Bot,
    result: OnboardingResult,
) -> None:
    blocks = ChatBlockService(session)
    await blocks.reset_block(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        block_key=MENU_HINT_BLOCK_KEY,
    )
    deleted = await delete_irrelevant_user_message(bot, message)
    sent_message = await message.answer(
        "Выбери раздел кнопкой ниже или нажми /menu.",
        reply_markup=build_main_menu(),
    )
    messages_to_remember = [sent_message] if deleted else [message, sent_message]
    await blocks.remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=MENU_HINT_BLOCK_KEY,
        messages=messages_to_remember,
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


def build_additional_panel_text() -> str:
    return "✨ <b>Дополнительно</b>\n\nЗдесь живут настройки, статистика и экспорт."


def build_legacy_settings_panel_text(result: OnboardingResult) -> str:
    timezone_name = result.couple.timezone if result.couple is not None else "Europe/Moscow"
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"Часовой пояс пары: {timezone_name}\n"
        "Доступные команды: /menu, /cancel, /help"
    )


def build_settings_panel_text(result: OnboardingResult, settings) -> str:
    timezone_name = result.couple.timezone if result.couple is not None else "Europe/Moscow"
    morning_status = "включен" if settings.morning_enabled else "выключен"
    evening_status = "включена" if settings.evening_enabled else "выключена"
    pause_status = "включена" if settings.reminders_paused else "нет"
    return (
        "⚙️ <b>Настройки</b>\n\n"
        f"Часовой пояс пары: {escape(timezone_name)}\n\n"
        "<b>Напоминания</b>\n"
        f"Утренний дайджест: {morning_status}, {format_reminder_time(settings.morning_time)}\n"
        f"Вечерняя сверка: {evening_status}, {format_reminder_time(settings.evening_time)}\n"
        f"Пауза: {pause_status}\n\n"
        "Доступные команды: /menu, /cancel, /help"
    )


async def build_settings_panel(session: AsyncSession, result: OnboardingResult) -> tuple[str, object]:
    if result.couple is None:
        return "⚙️ <b>Настройки</b>\n\nПара пока не найдена.", build_settings_keyboard()

    settings = await ReminderSettingsService(session).get_for_couple(result.couple)
    return build_settings_panel_text(result, settings), build_settings_keyboard(settings)


async def edit_settings_panel_from_state(bot: Bot, state: FSMContext, session: AsyncSession, result: OnboardingResult) -> None:
    data = await state.get_data()
    chat_id = data.get("settings_panel_chat_id")
    message_id = data.get("settings_panel_message_id")
    if chat_id is None or message_id is None:
        return

    text, keyboard = await build_settings_panel(session, result)
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup=keyboard,
        parse_mode="HTML",
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


@router.message(F.text == ADDITIONAL_BUTTON)
async def handle_additional_menu(message: Message, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_main_menu_access(message, session)
    if result is None:
        return

    await show_main_menu_block(
        message=message,
        session=session,
        bot=bot,
        result=result,
        block_key=ADDITIONAL_BLOCK_KEY,
        text=build_additional_panel_text(),
        reply_markup=build_additional_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == ADDITIONAL_MENU_CALLBACK)
async def handle_additional_menu_callback(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE:
        await callback.answer()
        return

    await callback.message.edit_text(
        build_additional_panel_text(),
        reply_markup=build_additional_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == ADDITIONAL_STATISTICS_CALLBACK)
async def handle_additional_statistics(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE:
        await callback.answer()
        return

    text = await build_statistics_panel_text(session, result, period="week")
    await callback.message.edit_text(
        text,
        reply_markup=build_statistics_keyboard(current_period="week"),
        parse_mode="HTML",
    )
    await callback.answer()


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
    await callback.message.edit_text(
        text,
        reply_markup=build_statistics_keyboard(current_period=period),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == ADDITIONAL_EXPORT_CALLBACK)
async def handle_additional_export(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if callback.message is None:
        await callback.answer()
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE or result.couple is None:
        await callback.answer("Сначала нужно быть в паре.", show_alert=True)
        return

    couple_export = await CoupleExportService(session).build_export(result.couple)
    document = BufferedInputFile(couple_export.data, filename=couple_export.filename)
    try:
        sent_message = await bot.send_document(
            chat_id=callback.message.chat.id,
            document=document,
            caption=(
                "Готово: экспорт контента и мест в CSV.\n"
                f"Контент: {couple_export.content_rows}, места: {couple_export.place_rows}."
            ),
        )
    except TelegramAPIError:
        logger.exception("Failed to send couple export")
        await callback.answer("Не смогла отправить экспорт. Попробуй ещё раз чуть позже.", show_alert=True)
        return

    await ChatBlockService(session).add_messages(
        user=result.user,
        chat_id=callback.message.chat.id,
        block_key=ADDITIONAL_BLOCK_KEY,
        messages=[sent_message],
    )
    await callback.answer("Экспорт готов")


@router.callback_query(F.data == ADDITIONAL_SETTINGS_CALLBACK)
async def handle_additional_settings(callback: CallbackQuery, session: AsyncSession) -> None:
    if callback.message is None:
        await callback.answer()
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE:
        await callback.answer()
        return

    text, keyboard = await build_settings_panel(session, result)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()


@router.callback_query(
    F.data.in_(
        {
            TOGGLE_MORNING_REMINDER_CALLBACK,
            TOGGLE_EVENING_REMINDER_CALLBACK,
            TOGGLE_REMINDERS_PAUSE_CALLBACK,
        }
    )
)
async def handle_reminder_toggle(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE or result.couple is None:
        await callback.answer("Сначала нужно быть в паре.", show_alert=True)
        return

    service = ReminderSettingsService(session)
    if callback.data == TOGGLE_MORNING_REMINDER_CALLBACK:
        await service.toggle_morning(result.couple)
    elif callback.data == TOGGLE_EVENING_REMINDER_CALLBACK:
        await service.toggle_evening(result.couple)
    else:
        await service.toggle_pause(result.couple)

    await state.clear()
    text, keyboard = await build_settings_panel(session, result)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer("Готово")


@router.callback_query(F.data.in_({SET_MORNING_REMINDER_TIME_CALLBACK, SET_EVENING_REMINDER_TIME_CALLBACK}))
async def handle_reminder_time_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if callback.message is None or callback.data is None:
        await callback.answer()
        return

    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE or result.couple is None:
        await callback.answer("Сначала нужно быть в паре.", show_alert=True)
        return

    settings = await ReminderSettingsService(session).get_for_couple(result.couple)
    await state.update_data(
        settings_panel_chat_id=callback.message.chat.id,
        settings_panel_message_id=callback.message.message_id,
    )
    if callback.data == SET_MORNING_REMINDER_TIME_CALLBACK:
        await state.set_state(ReminderSettingsStates.waiting_for_morning_time)
        current_time = format_reminder_time(settings.morning_time)
        title = "утреннего дайджеста"
    else:
        await state.set_state(ReminderSettingsStates.waiting_for_evening_time)
        current_time = format_reminder_time(settings.evening_time)
        title = "вечерней сверки"

    await callback.message.edit_text(
        f"⚙️ <b>Время {title}</b>\n\nСейчас: {current_time}\nНапиши новое время в формате 09:00.",
        reply_markup=build_settings_keyboard(settings),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(ReminderSettingsStates.waiting_for_morning_time)
async def handle_morning_reminder_time(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await handle_reminder_time_input(message, state, session, bot, time_kind="morning")


@router.message(ReminderSettingsStates.waiting_for_evening_time)
async def handle_evening_reminder_time(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await handle_reminder_time_input(message, state, session, bot, time_kind="evening")


async def handle_reminder_time_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    *,
    time_kind: str,
) -> None:
    result = await ensure_main_menu_access(message, session)
    if result is None or result.couple is None:
        await state.clear()
        return

    await delete_irrelevant_user_message(bot, message)
    try:
        reminder_time = parse_reminder_time(message.text or "").value
    except ReminderSettingsServiceError as error:
        data = await state.get_data()
        chat_id = data.get("settings_panel_chat_id")
        message_id = data.get("settings_panel_message_id")
        if chat_id is not None and message_id is not None:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=f"⚙️ <b>Время напоминания</b>\n\n{escape(str(error))}. Например: 09:00.",
                reply_markup=build_settings_keyboard(await ReminderSettingsService(session).get_for_couple(result.couple)),
                parse_mode="HTML",
            )
        return

    service = ReminderSettingsService(session)
    if time_kind == "morning":
        await service.set_morning_time(result.couple, reminder_time)
    else:
        await service.set_evening_time(result.couple, reminder_time)

    await edit_settings_panel_from_state(bot, state, session, result)
    await state.clear()


@router.message()
async def handle_unknown_menu_text(message: Message, session: AsyncSession, bot: Bot) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return

    await show_menu_hint_for_irrelevant_message(
        message=message,
        session=session,
        bot=bot,
        result=result,
    )
