import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.content import (
    ADD_CONTENT_CALLBACK,
    CONTENT_CANCEL_CALLBACK,
    CONTENT_COMPLETED_CALLBACK,
    CONTENT_EMOJI_SKIP_CALLBACK,
    CONTENT_FILTER_CATEGORIES_CALLBACK,
    CONTENT_FILTER_MONTH_CALLBACK,
    CONTENT_FILTER_RATING_HIGH_CALLBACK,
    CONTENT_FILTER_RATING_LOW_CALLBACK,
    CONTENT_FILTER_RATING_MID_CALLBACK,
    CONTENT_FILTER_TODAY_CALLBACK,
    CONTENT_FILTER_WEEK_CALLBACK,
    CONTENT_FILTERS_CALLBACK,
    CONTENT_MENU_CALLBACK,
    CONTENT_PLANNED_CALLBACK,
    build_content_category_keyboard,
    build_content_cancel_keyboard,
    build_content_filters_keyboard,
    build_content_list_keyboard,
    build_content_menu,
    build_content_notification_keyboard,
    build_content_rating_keyboard,
    build_content_reaction_keyboard,
)
from app.bot.keyboards.main_menu import CONTENT_BUTTON
from app.bot.states.content import ContentStates
from app.services.chat_blocks import CONTENT_BLOCK_KEY, ChatBlockService
from app.services.content import (
    CONTENT_REACTIONS,
    ContentCategory,
    ContentListFilter,
    ContentMutationResult,
    ContentService,
    ContentServiceError,
    completed_since_for_period,
    content_summary_counts,
)
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile

router = Router()
logger = logging.getLogger(__name__)


async def get_current_result_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult:
    profile = TelegramUserProfile(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    return await CoupleService(session).start_for_profile(profile)


async def ensure_content_access_for_message(message: Message, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return None

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return None

    return result


async def ensure_content_access_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult | None:
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
        logger.debug("Failed to delete user content flow message", exc_info=True)


async def add_content_block_messages(session: AsyncSession, user, chat_id: int, messages: list[Message]) -> None:
    await ChatBlockService(session).add_messages(
        user=user,
        chat_id=chat_id,
        block_key=CONTENT_BLOCK_KEY,
        messages=messages,
    )


async def remember_content_panel_in_state(state: FSMContext, message: Message) -> None:
    await state.update_data(content_panel_chat_id=message.chat.id, content_panel_message_id=message.message_id)


async def edit_content_panel(message: Message, text: str, reply_markup=None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except TelegramAPIError:
        logger.exception("Failed to edit content panel")


async def edit_content_panel_from_state(bot: Bot, state: FSMContext, text: str, reply_markup=None) -> None:
    data = await state.get_data()
    chat_id = data.get("content_panel_chat_id")
    message_id = data.get("content_panel_message_id")
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
        logger.exception("Failed to edit content panel from state")


async def send_content_notification(bot: Bot, result: ContentMutationResult) -> None:
    if result.notification_user is None or result.notification_text is None:
        return

    try:
        await bot.send_message(
            result.notification_user.telegram_id,
            result.notification_text,
            reply_markup=build_content_notification_keyboard(result.item.id),
        )
    except TelegramAPIError:
        logger.exception("Failed to send content notification")


async def build_content_root_panel(session: AsyncSession, user) -> tuple[str, object]:
    _, items = await ContentService(session).list_items(user)
    planned_count, completed_count = content_summary_counts(items)
    text = (
        "🎬 <b>Контент</b>\n\n"
        f"В планах: {planned_count}\n"
        f"Завершено: {completed_count}"
    )
    return text, build_content_menu()


async def render_content_list_panel(
    service: ContentService,
    context,
    items,
    *,
    title: str,
    empty_text: str,
) -> str:
    if not items:
        return f"🎬 <b>{title}</b>\n\n{empty_text}"

    blocks = [f"🎬 <b>{title}</b>"]
    for index, item in enumerate(items, start=1):
        blocks.append(f"{index}. {await service.build_content_card(context, item)}")

    return "\n\n".join(blocks)


async def show_content_root_panel(callback: CallbackQuery, session: AsyncSession, result: OnboardingResult) -> None:
    if callback.message is None:
        return

    text, keyboard = await build_content_root_panel(session, result.user)
    await edit_content_panel(callback.message, text, keyboard)


async def reset_and_show_content_menu(
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
        current_block_key=CONTENT_BLOCK_KEY,
    )
    await blocks.reset_block(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        block_key=CONTENT_BLOCK_KEY,
    )
    text, keyboard = await build_content_root_panel(session, result.user)
    panel_message = await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
    messages_to_remember = [panel_message]
    if trigger_message is not None:
        messages_to_remember.insert(0, trigger_message)

    await blocks.remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=CONTENT_BLOCK_KEY,
        messages=messages_to_remember,
    )


@router.message(F.text == CONTENT_BUTTON)
async def handle_content_menu(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_content_access_for_message(message, session)
    if result is None:
        return

    await state.clear()
    await reset_and_show_content_menu(message, session, bot, result, trigger_message=message)


@router.callback_query(F.data == CONTENT_MENU_CALLBACK)
async def handle_content_menu_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None:
        return

    await state.clear()
    await show_content_root_panel(callback, session, result)
    await callback.answer()


@router.callback_query(F.data == ADD_CONTENT_CALLBACK)
async def handle_add_content(callback: CallbackQuery, session: AsyncSession) -> None:
    if await ensure_content_access_for_callback(callback, session) is None:
        return
    if callback.message is not None:
        await edit_content_panel(
            callback.message,
            "🎬 <b>Добавить контент</b>\n\nВыбери категорию.",
            build_content_category_keyboard(mode="create"),
        )
    await callback.answer()


@router.callback_query(F.data == CONTENT_CANCEL_CALLBACK)
async def handle_content_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None:
        return

    await state.clear()
    await show_content_root_panel(callback, session, result)
    await callback.answer()


@router.callback_query(F.data.startswith("content:create:category:"))
async def handle_content_category(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await ensure_content_access_for_callback(callback, session) is None:
        return
    if callback.message is None or callback.data is None:
        return

    try:
        category = ContentCategory(callback.data.rsplit(":", maxsplit=1)[-1].upper())
    except ValueError:
        await callback.answer("Не смогла понять категорию.", show_alert=True)
        return

    await remember_content_panel_in_state(state, callback.message)
    await state.update_data(category=category.value)
    await state.set_state(ContentStates.waiting_for_title)
    await edit_content_panel(
        callback.message,
        "🎬 <b>Добавить контент</b>\n\nНапиши название одним сообщением.",
        build_content_cancel_keyboard(),
    )
    await callback.answer()


@router.message(ContentStates.waiting_for_title)
async def handle_content_title(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_content_access_for_message(message, session)
    if result is None:
        return

    await add_content_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    data = await state.get_data()
    try:
        category = ContentCategory(data["category"])
        item = await ContentService(session).add_item(result.user, category=category, title=message.text or "")
    except (KeyError, ValueError, ContentServiceError) as error:
        await edit_content_panel_from_state(
            bot,
            state,
            f"🎬 <b>Добавить контент</b>\n\n{escape(str(error))}. Напиши название ещё раз.",
            build_content_cancel_keyboard(),
        )
        return

    text, keyboard = await build_content_root_panel(session, result.user)
    await edit_content_panel_from_state(
        bot,
        state,
        f"✅ <b>Добавлено:</b> {escape(item.title)}\n\n{text}",
        keyboard,
    )
    await state.clear()


@router.callback_query(F.data.in_({CONTENT_PLANNED_CALLBACK, CONTENT_COMPLETED_CALLBACK}))
async def handle_content_status_list(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or callback.message is None:
        return

    status = "NOT_COMPLETED" if callback.data == CONTENT_PLANNED_CALLBACK else "COMPLETED"
    title = "В планах" if status == "NOT_COMPLETED" else "Завершённое"
    empty_text = "Пока пусто."
    service = ContentService(session)
    context, items = await service.list_items(result.user, ContentListFilter(status=status))
    await edit_content_panel(
        callback.message,
        await render_content_list_panel(service, context, items, title=title, empty_text=empty_text),
        build_content_list_keyboard(items),
    )
    await callback.answer()


@router.callback_query(F.data == CONTENT_FILTERS_CALLBACK)
async def handle_content_filters(callback: CallbackQuery, session: AsyncSession) -> None:
    if await ensure_content_access_for_callback(callback, session) is None:
        return
    if callback.message is not None:
        await edit_content_panel(
            callback.message,
            "🎬 <b>Фильтры</b>",
            build_content_filters_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data == CONTENT_FILTER_CATEGORIES_CALLBACK)
async def handle_content_filter_categories(callback: CallbackQuery, session: AsyncSession) -> None:
    if await ensure_content_access_for_callback(callback, session) is None:
        return
    if callback.message is not None:
        await edit_content_panel(
            callback.message,
            "🎬 <b>Фильтр по категории</b>",
            build_content_category_keyboard(mode="filter"),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("content:filter:category:"))
async def handle_content_category_filter(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        category = ContentCategory(callback.data.rsplit(":", maxsplit=1)[-1].upper())
    except ValueError:
        await callback.answer("Не смогла понять категорию.", show_alert=True)
        return

    service = ContentService(session)
    context, items = await service.list_items(result.user, ContentListFilter(category=category))
    await edit_content_panel(
        callback.message,
        await render_content_list_panel(
            service,
            context,
            items,
            title=f"Категория: {category.value}",
            empty_text="В этой категории пока пусто.",
        ),
        build_content_list_keyboard(items),
    )
    await callback.answer()


@router.callback_query(
    F.data.in_(
        {
            CONTENT_FILTER_RATING_HIGH_CALLBACK,
            CONTENT_FILTER_RATING_MID_CALLBACK,
            CONTENT_FILTER_RATING_LOW_CALLBACK,
            CONTENT_FILTER_TODAY_CALLBACK,
            CONTENT_FILTER_WEEK_CALLBACK,
            CONTENT_FILTER_MONTH_CALLBACK,
        }
    )
)
async def handle_content_quick_filter(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or result.couple is None or callback.message is None:
        return

    title = "Фильтр"
    content_filter = ContentListFilter()
    if callback.data == CONTENT_FILTER_RATING_HIGH_CALLBACK:
        title = "Оценка 8-10"
        content_filter = ContentListFilter(min_rating=8)
    elif callback.data == CONTENT_FILTER_RATING_MID_CALLBACK:
        title = "Оценка 5-7"
        content_filter = ContentListFilter(min_rating=5, max_rating=7)
    elif callback.data == CONTENT_FILTER_RATING_LOW_CALLBACK:
        title = "Оценка 1-4"
        content_filter = ContentListFilter(max_rating=4)
    else:
        period_by_callback = {
            CONTENT_FILTER_TODAY_CALLBACK: ("Завершено сегодня", "today"),
            CONTENT_FILTER_WEEK_CALLBACK: ("Завершено за 7 дней", "week"),
            CONTENT_FILTER_MONTH_CALLBACK: ("Завершено за 30 дней", "month"),
        }
        title, period = period_by_callback[callback.data or ""]
        content_filter = ContentListFilter(
            status="COMPLETED",
            completed_since=completed_since_for_period(result.couple.timezone, period),
        )

    service = ContentService(session)
    context, items = await service.list_items(result.user, content_filter)
    await edit_content_panel(
        callback.message,
        await render_content_list_panel(service, context, items, title=title, empty_text="Ничего не нашлось."),
        build_content_list_keyboard(items),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:complete:"))
async def handle_complete_content(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        content_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
        mutation_result = await ContentService(session).complete_item(result.user, content_id)
    except (ValueError, ContentServiceError) as error:
        await callback.answer(str(error), show_alert=True)
        return

    await send_content_notification(bot, mutation_result)
    await remember_content_panel_in_state(state, callback.message)
    await state.update_data(content_id=mutation_result.item.id)
    await state.set_state(ContentStates.choosing_rating)
    await edit_content_panel(
        callback.message,
        f"✅ <b>Завершено:</b> {escape(mutation_result.item.title)}\n\nПоставь оценку от 1 до 10.",
        build_content_rating_keyboard(mutation_result.item.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:comment:"))
async def handle_start_content_comment(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        content_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Не смогла понять контент.", show_alert=True)
        return

    await remember_content_panel_in_state(state, callback.message)
    await state.update_data(content_id=content_id)
    await state.set_state(ContentStates.waiting_for_comment)
    await edit_content_panel(
        callback.message,
        "🎬 <b>Комментарий</b>\n\nНапиши комментарий одним сообщением.",
        build_content_cancel_keyboard(),
    )
    await callback.answer()


@router.message(ContentStates.waiting_for_comment)
async def handle_content_comment(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_content_access_for_message(message, session)
    if result is None:
        return

    await add_content_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    data = await state.get_data()
    content_id = data.get("content_id")
    try:
        if content_id is None:
            raise ValueError
        service = ContentService(session)
        await service.add_comment(result.user, content_id=content_id, text=message.text or "")
        context, items = await service.list_items(result.user)
        item = next((item for item in items if item.id == content_id), None)
        if item is None:
            raise ContentServiceError("Контент не найден")
    except (ValueError, ContentServiceError) as error:
        await edit_content_panel_from_state(
            bot,
            state,
            f"🎬 <b>Комментарий</b>\n\n{escape(str(error))}. Напиши комментарий ещё раз.",
            build_content_cancel_keyboard(),
        )
        return

    await edit_content_panel_from_state(
        bot,
        state,
        f"✅ <b>Комментарий добавлен</b>\n\n{await service.build_content_card(context, item)}",
        build_content_list_keyboard([item]),
    )
    await state.clear()


@router.callback_query(F.data.startswith("content:rate:"))
async def handle_start_content_rating(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    try:
        content_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Не смогла понять контент.", show_alert=True)
        return

    await remember_content_panel_in_state(state, callback.message)
    await state.update_data(content_id=content_id)
    await state.set_state(ContentStates.choosing_rating)
    await edit_content_panel(
        callback.message,
        "🎬 <b>Оценка</b>\n\nПоставь оценку от 1 до 10.",
        build_content_rating_keyboard(content_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:score:"))
async def handle_content_score(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    data = await state.get_data()
    content_id = data.get("content_id")
    try:
        score = int(callback.data.rsplit(":", maxsplit=1)[-1])
        if content_id is None:
            raise ValueError
        await ContentService(session).save_rating(result.user, content_id=content_id, score=score, emoji=None)
    except (ValueError, ContentServiceError) as error:
        await callback.answer(str(error), show_alert=True)
        return

    await state.update_data(score=score)
    await state.set_state(ContentStates.choosing_reaction)
    await edit_content_panel(
        callback.message,
        f"🎬 <b>Оценка сохранена:</b> {score}/10\n\nВыбери эмодзи-реакцию.",
        build_content_reaction_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("content:emoji:"))
async def handle_content_reaction(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_content_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    data = await state.get_data()
    content_id = data.get("content_id")
    score = data.get("score")
    reaction_key = callback.data.rsplit(":", maxsplit=1)[-1]
    emoji = None if callback.data == CONTENT_EMOJI_SKIP_CALLBACK else CONTENT_REACTIONS.get(reaction_key)
    if reaction_key != "skip" and emoji is None:
        await callback.answer("Не смогла понять реакцию.", show_alert=True)
        return

    try:
        if content_id is None or score is None:
            raise ValueError
        await ContentService(session).save_rating(result.user, content_id=content_id, score=score, emoji=emoji)
    except (ValueError, ContentServiceError) as error:
        await callback.answer(str(error), show_alert=True)
        return

    text, keyboard = await build_content_root_panel(session, result.user)
    await edit_content_panel(
        callback.message,
        f"✅ <b>Оценка сохранена</b>\n\n{text}",
        keyboard,
    )
    await state.clear()
    await callback.answer()


@router.message(ContentStates.choosing_rating)
@router.message(ContentStates.choosing_reaction)
async def handle_content_inline_step_text(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_content_access_for_message(message, session)
    if result is None:
        return

    await delete_user_message(bot, message)
    current_state = await state.get_state()
    if current_state == ContentStates.choosing_rating.state:
        await edit_content_panel_from_state(
            bot,
            state,
            "🎬 <b>Оценка</b>\n\nВыбери оценку кнопкой в панели.",
            build_content_rating_keyboard(),
        )
    else:
        await edit_content_panel_from_state(
            bot,
            state,
            "🎬 <b>Реакция</b>\n\nВыбери эмодзи кнопкой в панели.",
            build_content_reaction_keyboard(),
        )
