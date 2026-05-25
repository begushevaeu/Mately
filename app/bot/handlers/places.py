import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.main_menu import PLACES_BUTTON
from app.bot.keyboards.places import (
    ADD_PLACE_CALLBACK,
    PLACES_CANCEL_CALLBACK,
    PLACES_MENU_CALLBACK,
    PLACES_PLANNED_CALLBACK,
    PLACES_VISITED_CALLBACK,
    build_place_cancel_keyboard,
    build_place_category_keyboard,
    build_place_list_keyboard,
    build_place_rating_keyboard,
    build_places_menu,
)
from app.bot.states.places import PlaceStates
from app.services.chat_blocks import PLACES_BLOCK_KEY, ChatBlockService
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile
from app.services.places import (
    CATEGORY_LABELS,
    PlaceCategory,
    PlaceListFilter,
    PlaceService,
    PlaceServiceError,
    place_summary_counts,
)

router = Router()
logger = logging.getLogger(__name__)


async def get_current_result_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult:
    profile = TelegramUserProfile(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    return await CoupleService(session).start_for_profile(profile)


async def ensure_places_access_for_message(message: Message, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return None

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return None

    return result


async def ensure_places_access_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult | None:
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
        logger.debug("Failed to delete user places flow message", exc_info=True)


async def add_places_block_messages(session: AsyncSession, user, chat_id: int, messages: list[Message]) -> None:
    await ChatBlockService(session).add_messages(
        user=user,
        chat_id=chat_id,
        block_key=PLACES_BLOCK_KEY,
        messages=messages,
    )


async def remember_places_panel_in_state(state: FSMContext, message: Message) -> None:
    await state.update_data(places_panel_chat_id=message.chat.id, places_panel_message_id=message.message_id)


async def edit_places_panel(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except TelegramAPIError:
        logger.exception("Failed to edit places panel")


async def edit_places_panel_from_state(bot: Bot, state: FSMContext, text: str, reply_markup=None) -> None:
    data = await state.get_data()
    chat_id = data.get("places_panel_chat_id")
    message_id = data.get("places_panel_message_id")
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
        logger.exception("Failed to edit places panel from state")


async def build_places_root_panel(session: AsyncSession, user) -> tuple[str, object]:
    _, items = await PlaceService(session).list_items(user)
    planned_count, visited_count = place_summary_counts(items)
    text = (
        "📍 <b>Места</b>\n\n"
        f"В планах: {planned_count}\n"
        f"Посещено: {visited_count}"
    )
    return text, build_places_menu()


async def render_places_list_panel(
    service: PlaceService,
    context,
    items,
    *,
    title: str,
    empty_text: str,
) -> str:
    if not items:
        return f"📍 <b>{title}</b>\n\n{empty_text}"

    blocks = [f"📍 <b>{title}</b>"]
    for index, item in enumerate(items, start=1):
        blocks.append(f"{index}. {await service.build_place_card(context, item)}")

    return "\n\n".join(blocks)


async def show_places_root_panel(callback: CallbackQuery, session: AsyncSession, result: OnboardingResult) -> None:
    if callback.message is None:
        return

    text, keyboard = await build_places_root_panel(session, result.user)
    await edit_places_panel(callback.message, text, keyboard)


async def reset_and_show_places_menu(
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
        current_block_key=PLACES_BLOCK_KEY,
    )
    await blocks.reset_block(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        block_key=PLACES_BLOCK_KEY,
    )
    text, keyboard = await build_places_root_panel(session, result.user)
    panel_message = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    messages_to_remember = [panel_message]
    if trigger_message is not None:
        messages_to_remember.insert(0, trigger_message)

    await blocks.remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=PLACES_BLOCK_KEY,
        messages=messages_to_remember,
    )


@router.message(F.text == PLACES_BUTTON)
async def handle_places_menu(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_places_access_for_message(message, session)
    if result is None:
        return

    await state.clear()
    await reset_and_show_places_menu(message, session, bot, result, trigger_message=message)


@router.callback_query(F.data == PLACES_MENU_CALLBACK)
async def handle_places_menu_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_places_access_for_callback(callback, session)
    if result is None:
        return

    await state.clear()
    await show_places_root_panel(callback, session, result)
    await callback.answer()


@router.callback_query(F.data == ADD_PLACE_CALLBACK)
async def handle_add_place(callback: CallbackQuery, session: AsyncSession) -> None:
    if await ensure_places_access_for_callback(callback, session) is None:
        return
    if callback.message is not None:
        await edit_places_panel(
            callback.message,
            "📍 <b>Добавить место</b>\n\nВыбери категорию.",
            build_place_category_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == PLACES_CANCEL_CALLBACK)
async def handle_places_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_places_access_for_callback(callback, session)
    if result is None:
        return

    await state.clear()
    await show_places_root_panel(callback, session, result)
    await callback.answer()


@router.callback_query(F.data.startswith("places:create:category:"))
async def handle_place_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await ensure_places_access_for_callback(callback, session) is None:
        return
    if callback.message is None or callback.data is None:
        return

    try:
        category = PlaceCategory(callback.data.rsplit(":", maxsplit=1)[-1].upper())
    except ValueError:
        await callback.answer("Не смогла понять категорию.", show_alert=True)
        return

    await remember_places_panel_in_state(state, callback.message)
    await state.update_data(category=category.value)
    await state.set_state(PlaceStates.waiting_for_title)
    await edit_places_panel(
        callback.message,
        f"📍 <b>Добавить {CATEGORY_LABELS[category]}</b>\n\nНапиши название одним сообщением.",
        build_place_cancel_keyboard(),
    )
    await callback.answer()


@router.message(PlaceStates.waiting_for_title)
async def handle_place_title(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_places_access_for_message(message, session)
    if result is None:
        return

    await add_places_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    data = await state.get_data()
    try:
        category = PlaceCategory(data["category"])
        item = await PlaceService(session).add_item(result.user, category=category, title=message.text or "")
    except (KeyError, ValueError, PlaceServiceError) as error:
        await edit_places_panel_from_state(
            bot,
            state,
            f"📍 <b>Добавить место</b>\n\n{escape(str(error))}. Напиши название ещё раз.",
            build_place_cancel_keyboard(),
        )
        return

    text, keyboard = await build_places_root_panel(session, result.user)
    await edit_places_panel_from_state(
        bot,
        state,
        f"✅ <b>Добавлено:</b> {escape(item.title)}\n\n{text}",
        keyboard,
    )
    await state.clear()


@router.callback_query(F.data.in_({PLACES_PLANNED_CALLBACK, PLACES_VISITED_CALLBACK}))
async def handle_places_status_list(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await ensure_places_access_for_callback(callback, session)
    if result is None or callback.message is None:
        return

    status = "NOT_VISITED" if callback.data == PLACES_PLANNED_CALLBACK else "VISITED"
    title = "В планах" if status == "NOT_VISITED" else "Посещённые"
    empty_text = "Пока пусто."
    service = PlaceService(session)
    context, items = await service.list_items(result.user, PlaceListFilter(status=status))
    await edit_places_panel(
        callback.message,
        await render_places_list_panel(service, context, items, title=title, empty_text=empty_text),
        build_place_list_keyboard(items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("places:visit:"))
async def handle_visit_place(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_places_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        place_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
        item = await PlaceService(session).visit_item(result.user, place_id)
    except (ValueError, PlaceServiceError) as error:
        await callback.answer(str(error), show_alert=True)
        return

    await remember_places_panel_in_state(state, callback.message)
    await state.update_data(place_id=item.id)
    await state.set_state(PlaceStates.choosing_rating)
    await edit_places_panel(
        callback.message,
        f"✅ <b>Посетили:</b> {escape(item.title)}\n\nПоставь оценку от 1 до 10.",
        build_place_rating_keyboard(item.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("places:rate:"))
async def handle_start_place_rating(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_places_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        place_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Не смогла понять место.", show_alert=True)
        return

    await remember_places_panel_in_state(state, callback.message)
    await state.update_data(place_id=place_id)
    await state.set_state(PlaceStates.choosing_rating)
    await edit_places_panel(
        callback.message,
        "📍 <b>Оценка</b>\n\nПоставь оценку от 1 до 10.",
        build_place_rating_keyboard(place_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("places:score:"))
async def handle_place_score(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_places_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    data = await state.get_data()
    place_id = data.get("place_id")
    try:
        score = int(callback.data.rsplit(":", maxsplit=1)[-1])
        if place_id is None:
            raise ValueError
        await PlaceService(session).save_rating(result.user, place_id=place_id, score=score)
    except (ValueError, PlaceServiceError) as error:
        await callback.answer(str(error), show_alert=True)
        return

    text, keyboard = await build_places_root_panel(session, result.user)
    await edit_places_panel(
        callback.message,
        f"✅ <b>Оценка сохранена:</b> {score}/10\n\n{text}",
        keyboard,
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data.startswith("places:comment:"))
async def handle_start_place_comment(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_places_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        place_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Не смогла понять место.", show_alert=True)
        return

    await remember_places_panel_in_state(state, callback.message)
    await state.update_data(place_id=place_id)
    await state.set_state(PlaceStates.waiting_for_comment)
    await edit_places_panel(
        callback.message,
        "📍 <b>Комментарий</b>\n\nНапиши комментарий одним сообщением.",
        build_place_cancel_keyboard(),
    )
    await callback.answer()


@router.message(PlaceStates.waiting_for_comment)
async def handle_place_comment(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_places_access_for_message(message, session)
    if result is None:
        return

    await add_places_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    data = await state.get_data()
    place_id = data.get("place_id")
    try:
        if place_id is None:
            raise ValueError
        service = PlaceService(session)
        await service.add_comment(result.user, place_id=place_id, text=message.text or "")
        context, items = await service.list_items(result.user)
        item = next((item for item in items if item.id == place_id), None)
        if item is None:
            raise PlaceServiceError("Место не найдено")
    except (ValueError, PlaceServiceError) as error:
        await edit_places_panel_from_state(
            bot,
            state,
            f"📍 <b>Комментарий</b>\n\n{escape(str(error))}. Напиши комментарий ещё раз.",
            build_place_cancel_keyboard(),
        )
        return

    await edit_places_panel_from_state(
        bot,
        state,
        f"✅ <b>Комментарий добавлен</b>\n\n{await service.build_place_card(context, item)}",
        build_place_list_keyboard([item]),
    )
    await state.clear()


@router.message(PlaceStates.choosing_rating)
async def handle_place_rating_text(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_places_access_for_message(message, session)
    if result is None:
        return

    await delete_user_message(bot, message)
    await edit_places_panel_from_state(
        bot,
        state,
        "📍 <b>Оценка</b>\n\nВыбери оценку кнопкой в панели.",
        build_place_rating_keyboard(),
    )
