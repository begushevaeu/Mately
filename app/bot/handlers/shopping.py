import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.main_menu import SHOPPING_BUTTON
from app.bot.keyboards.shopping import (
    ADD_SHOPPING_ITEM_CALLBACK,
    SHOPPING_CANCEL_CALLBACK,
    build_shopping_cancel_keyboard,
    build_shopping_keyboard,
)
from app.bot.states.shopping import ShoppingStates
from app.services.chat_blocks import SHOPPING_BLOCK_KEY, ChatBlockService
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile
from app.services.shopping import ShoppingService, ShoppingServiceError, build_shopping_panel_text

router = Router()
logger = logging.getLogger(__name__)


async def get_current_result_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult:
    profile = TelegramUserProfile(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    return await CoupleService(session).start_for_profile(profile)


async def ensure_shopping_access_for_message(message: Message, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return None

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return None

    return result


async def ensure_shopping_access_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE:
        if callback.message is not None:
            await answer_for_onboarding_state(callback.message, result)
        await callback.answer()
        return None

    return result


async def delete_user_message(bot: Bot, message: Message) -> None:
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except TelegramAPIError:
        logger.debug("Failed to delete user shopping flow message", exc_info=True)


async def add_shopping_block_messages(session: AsyncSession, user, chat_id: int, messages: list[Message]) -> None:
    await ChatBlockService(session).add_messages(
        user=user,
        chat_id=chat_id,
        block_key=SHOPPING_BLOCK_KEY,
        messages=messages,
    )


async def remember_shopping_panel_in_state(state: FSMContext, message: Message) -> None:
    await state.update_data(shopping_panel_chat_id=message.chat.id, shopping_panel_message_id=message.message_id)


async def edit_shopping_panel(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except TelegramAPIError:
        logger.exception("Failed to edit shopping panel")


async def edit_shopping_panel_from_state(bot: Bot, state: FSMContext, text: str, reply_markup=None) -> None:
    data = await state.get_data()
    chat_id = data.get("shopping_panel_chat_id")
    message_id = data.get("shopping_panel_message_id")
    if chat_id is None or message_id is None:
        return

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
    except TelegramAPIError:
        logger.exception("Failed to edit shopping panel from state")


async def build_shopping_panel(session: AsyncSession, user) -> tuple[str, object]:
    _, items = await ShoppingService(session).list_items(user)
    return build_shopping_panel_text(items), build_shopping_keyboard(items)


async def show_shopping_root_panel(callback: CallbackQuery, session: AsyncSession, result: OnboardingResult) -> None:
    if callback.message is None:
        return

    text, keyboard = await build_shopping_panel(session, result.user)
    await edit_shopping_panel(callback.message, text, keyboard)


async def reset_and_show_shopping_menu(
    message: Message,
    session: AsyncSession,
    bot: Bot,
    result: OnboardingResult,
    *,
    trigger_message: Message | None = None,
) -> None:
    blocks = ChatBlockService(session)
    await blocks.reset_other_blocks(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        current_block_key=SHOPPING_BLOCK_KEY,
    )
    await blocks.reset_block(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        block_key=SHOPPING_BLOCK_KEY,
    )
    text, keyboard = await build_shopping_panel(session, result.user)
    panel_message = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    messages_to_remember = [panel_message]
    if trigger_message is not None:
        messages_to_remember.insert(0, trigger_message)

    await blocks.remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=SHOPPING_BLOCK_KEY,
        messages=messages_to_remember,
    )


@router.message(F.text == SHOPPING_BUTTON)
async def handle_shopping_menu(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_shopping_access_for_message(message, session)
    if result is None:
        return

    await state.clear()
    await reset_and_show_shopping_menu(message, session, bot, result, trigger_message=message)


@router.callback_query(F.data == ADD_SHOPPING_ITEM_CALLBACK)
async def handle_add_shopping_item(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await ensure_shopping_access_for_callback(callback, session) is None:
        return

    await state.set_state(ShoppingStates.waiting_for_title)
    if callback.message is not None:
        await remember_shopping_panel_in_state(state, callback.message)
        await edit_shopping_panel(
            callback.message,
            "🛒 <b>Добавить покупку</b>\n\nНапиши название одним сообщением.",
            build_shopping_cancel_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == SHOPPING_CANCEL_CALLBACK)
async def handle_shopping_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_shopping_access_for_callback(callback, session)
    if result is None:
        return

    await state.clear()
    await show_shopping_root_panel(callback, session, result)
    await callback.answer()


@router.message(ShoppingStates.waiting_for_title)
async def handle_shopping_title(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_shopping_access_for_message(message, session)
    if result is None:
        return

    await add_shopping_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    title = (message.text or "").strip()
    try:
        item = await ShoppingService(session).add_item(result.user, title)
    except ShoppingServiceError as error:
        await edit_shopping_panel_from_state(
            bot,
            state,
            f"🛒 <b>Добавить покупку</b>\n\n{escape(str(error))}. Напиши название ещё раз.",
            build_shopping_cancel_keyboard(),
        )
        return

    text, keyboard = await build_shopping_panel(session, result.user)
    await edit_shopping_panel_from_state(
        bot,
        state,
        f"✅ <b>Добавлено:</b> {escape(item.title)}\n\n{text}",
        keyboard,
    )
    await state.clear()


@router.callback_query(F.data.startswith("shopping:bought:"))
async def handle_mark_shopping_bought(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await ensure_shopping_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        item_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Не смогла понять покупку.", show_alert=True)
        return

    try:
        item = await ShoppingService(session).mark_bought(result.user, item_id)
    except ShoppingServiceError as error:
        await callback.answer(str(error), show_alert=True)
        return

    text, keyboard = await build_shopping_panel(session, result.user)
    await edit_shopping_panel(
        callback.message,
        f"✅ <b>Куплено:</b> {escape(item.title)}\n\n{text}",
        keyboard,
    )
    await callback.answer()
