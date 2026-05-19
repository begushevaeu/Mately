import logging
from html import escape

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.main_menu import TASKS_BUTTON
from app.bot.keyboards.tasks import (
    ADD_TASK_CALLBACK,
    ALL_TASKS_CALLBACK,
    MY_TASKS_CALLBACK,
    TASK_POOL_CALLBACK,
    TASK_CREATE_ASSIGN_PARTNER_CALLBACK,
    TASK_CREATE_ASSIGN_POOL_CALLBACK,
    TASK_CREATE_ASSIGN_SELF_CALLBACK,
    TASK_CREATE_CANCEL_CALLBACK,
    TASK_CREATE_CUSTOM_CALLBACK,
    TASK_CREATE_DAILY_CALLBACK,
    TASK_CREATE_DEADLINE_NONE_CALLBACK,
    TASK_CREATE_DEADLINE_TODAY_CALLBACK,
    TASK_CREATE_DEADLINE_TOMORROW_CALLBACK,
    TASK_CREATE_MONTHLY_CALLBACK,
    TASK_CREATE_ONE_TIME_CALLBACK,
    TASK_CREATE_RECURRING_CALLBACK,
    TASK_CREATE_WEEKLY_CALLBACK,
    TASKS_MENU_CALLBACK,
    build_assignment_keyboard,
    build_deadline_keyboard,
    build_recurrence_keyboard,
    build_recurring_choice_keyboard,
    build_task_creation_cancel_keyboard,
    build_task_list_keyboard,
    build_tasks_menu,
)
from app.bot.states.tasks import TaskCreationStates
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile
from app.services.chat_blocks import TASKS_BLOCK_KEY, ChatBlockService
from app.services.partner_aliases import PartnerAliasService
from app.services.tasks import (
    AssignmentType,
    RecurrenceType,
    TaskCreationInput,
    TaskMutationResult,
    TaskService,
    TaskServiceError,
    parse_task_deadline,
)
from app.utils.dates import DeadlineParseError

router = Router()
logger = logging.getLogger(__name__)

RECURRENCE_BY_CALLBACK = {
    TASK_CREATE_DAILY_CALLBACK: RecurrenceType.DAILY,
    TASK_CREATE_WEEKLY_CALLBACK: RecurrenceType.WEEKLY,
    TASK_CREATE_MONTHLY_CALLBACK: RecurrenceType.MONTHLY,
    TASK_CREATE_CUSTOM_CALLBACK: RecurrenceType.CUSTOM,
}

ASSIGNMENT_BY_CALLBACK = {
    TASK_CREATE_ASSIGN_SELF_CALLBACK: AssignmentType.SELF,
    TASK_CREATE_ASSIGN_PARTNER_CALLBACK: AssignmentType.PARTNER,
    TASK_CREATE_ASSIGN_POOL_CALLBACK: AssignmentType.POOL,
}

DEADLINE_BY_CALLBACK = {
    TASK_CREATE_DEADLINE_TODAY_CALLBACK: "сегодня",
    TASK_CREATE_DEADLINE_TOMORROW_CALLBACK: "завтра",
    TASK_CREATE_DEADLINE_NONE_CALLBACK: "без срока",
}


async def get_current_result_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult:
    profile = TelegramUserProfile(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        first_name=callback.from_user.first_name,
    )
    return await CoupleService(session).start_for_profile(profile)


async def ensure_task_access_for_message(message: Message, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return None

    if result.status is not OnboardingStatus.IN_COUPLE:
        await answer_for_onboarding_state(message, result)
        return None

    return result


async def ensure_task_access_for_callback(callback: CallbackQuery, session: AsyncSession) -> OnboardingResult | None:
    result = await get_current_result_for_callback(callback, session)
    if result.status is not OnboardingStatus.IN_COUPLE:
        if callback.message is not None:
            await answer_for_onboarding_state(callback.message, result)
        await callback.answer()
        return None

    return result


async def send_task_notification(bot: Bot, result: TaskMutationResult) -> None:
    if result.notification_user is None or result.notification_text is None:
        return

    try:
        await bot.send_message(result.notification_user.telegram_id, result.notification_text)
    except TelegramAPIError:
        logger.exception("Failed to send task notification")


async def build_tasks_menu_for_user(session: AsyncSession, user) -> object:
    _, pool_tasks = await TaskService(session).list_pool(user)
    return build_tasks_menu(has_pool_tasks=bool(pool_tasks))


async def build_tasks_panel_text(session: AsyncSession, user) -> str:
    _, pool_tasks = await TaskService(session).list_pool(user)
    pool_line = f"\n\nВ ярмарке: {len(pool_tasks)}" if pool_tasks else ""
    return f"📋 <b>Задачи</b>{pool_line}"


async def add_task_block_messages(session: AsyncSession, user, chat_id: int, messages: list[Message]) -> None:
    await ChatBlockService(session).add_messages(
        user=user,
        chat_id=chat_id,
        block_key=TASKS_BLOCK_KEY,
        messages=messages,
    )


async def delete_user_message(bot: Bot, message: Message) -> None:
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except TelegramAPIError:
        logger.debug("Failed to delete user task flow message", exc_info=True)


async def edit_task_panel_message(message: Message, text: str, reply_markup: object | None = None) -> None:
    try:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
    except TelegramAPIError:
        logger.exception("Failed to edit task panel")


async def edit_task_panel_from_state(bot: Bot, state: FSMContext, text: str, reply_markup: object | None = None) -> None:
    data = await state.get_data()
    chat_id = data.get("task_panel_chat_id")
    message_id = data.get("task_panel_message_id")
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
        logger.exception("Failed to edit task panel from state")


async def remember_task_panel_in_state(state: FSMContext, message: Message) -> None:
    await state.update_data(task_panel_chat_id=message.chat.id, task_panel_message_id=message.message_id)


async def reset_and_show_tasks_menu(
    message: Message,
    session: AsyncSession,
    bot: Bot,
    result: OnboardingResult,
    *,
    trigger_message: Message | None = None,
) -> None:
    await ChatBlockService(session).reset_block(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        block_key=TASKS_BLOCK_KEY,
    )
    keyboard = await build_tasks_menu_for_user(session, result.user)
    panel_message = await message.answer(
        await build_tasks_panel_text(session, result.user),
        reply_markup=keyboard,
        parse_mode="HTML",
    )
    messages_to_remember = [panel_message]
    if trigger_message is not None:
        messages_to_remember.insert(0, trigger_message)

    await ChatBlockService(session).remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=TASKS_BLOCK_KEY,
        messages=messages_to_remember,
    )


async def get_partner_assignment_button(session: AsyncSession, result: OnboardingResult) -> str:
    context = await TaskService(session).get_context(result.user)
    if context.partner is None:
        return "Партнеру"

    display = await PartnerAliasService(session).get_display_for(owner=result.user, partner=context.partner)
    return display.dative_with_emoji


async def render_task_list_panel(
    service: TaskService,
    context,
    tasks,
    *,
    title: str,
    empty_text: str,
    show_ownership: bool,
) -> str:
    if not tasks:
        return f"📋 <b>{title}</b>\n\n{empty_text}"

    blocks = [f"📋 <b>{title}</b>"]
    for index, task in enumerate(tasks, start=1):
        card = await service.build_task_card(context, task, show_ownership=show_ownership)
        blocks.append(f"{index}. {card}")

    return "\n\n".join(blocks)


async def show_tasks_root_panel(callback: CallbackQuery, session: AsyncSession, result: OnboardingResult) -> None:
    if callback.message is None:
        return

    await edit_task_panel_message(
        callback.message,
        await build_tasks_panel_text(session, result.user),
        await build_tasks_menu_for_user(session, result.user),
    )


async def finish_task_creation(
    *,
    bot: Bot,
    state: FSMContext,
    session: AsyncSession,
    result: OnboardingResult,
    creation_input: TaskCreationInput,
) -> None:
    mutation_result = await TaskService(session).create_task(result.user, creation_input)
    await send_task_notification(bot, mutation_result)
    service = TaskService(session)
    context = await service.get_context(result.user)
    card = await service.build_task_card(context, mutation_result.task, show_ownership=True)
    keyboard = await build_tasks_menu_for_user(session, result.user)
    await edit_task_panel_from_state(
        bot,
        state,
        f"✅ <b>Задача создана</b>\n\n{card}",
        keyboard,
    )
    await state.clear()


@router.message(F.text == TASKS_BUTTON)
async def handle_tasks_menu(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    await state.clear()
    await reset_and_show_tasks_menu(message, session, bot, result, trigger_message=message)


@router.callback_query(F.data == TASKS_MENU_CALLBACK)
async def handle_tasks_menu_callback(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None:
        return

    await state.clear()
    await show_tasks_root_panel(callback, session, result)
    await callback.answer()


@router.callback_query(F.data == ADD_TASK_CALLBACK)
async def handle_add_task(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await ensure_task_access_for_callback(callback, session) is None:
        return

    await state.set_state(TaskCreationStates.waiting_for_title)
    if callback.message is not None:
        await remember_task_panel_in_state(state, callback.message)
        await edit_task_panel_message(
            callback.message,
            "➕ <b>Добавить задачу</b>\n\nНапиши название задачи одним сообщением.",
            build_task_creation_cancel_keyboard(),
        )
    await callback.answer()


@router.message(TaskCreationStates.waiting_for_title)
async def handle_task_title(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    await add_task_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    title = (message.text or "").strip()
    if not title:
        await edit_task_panel_from_state(
            bot,
            state,
            "➕ <b>Добавить задачу</b>\n\nНазвание не должно быть пустым. Напиши задачу коротко и понятно.",
            build_task_creation_cancel_keyboard(),
        )
        return

    if len(title) > 255:
        await edit_task_panel_from_state(
            bot,
            state,
            "➕ <b>Добавить задачу</b>\n\nНазвание получилось слишком длинным. Давай уложимся в 255 символов.",
            build_task_creation_cancel_keyboard(),
        )
        return

    await state.update_data(title=title)
    await state.set_state(TaskCreationStates.choosing_recurring)
    await edit_task_panel_from_state(
        bot,
        state,
        f"➕ <b>{escape(title)}</b>\n\nЭто разовая или регулярная задача?",
        build_recurring_choice_keyboard(),
    )


@router.callback_query(F.data == TASK_CREATE_CANCEL_CALLBACK)
async def handle_task_creation_cancel(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None:
        return

    await state.clear()
    await show_tasks_root_panel(callback, session, result)
    await callback.answer()


@router.callback_query(F.data.in_({TASK_CREATE_ONE_TIME_CALLBACK, TASK_CREATE_RECURRING_CALLBACK}))
async def handle_task_recurring_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None or callback.message is None:
        return

    data = await state.get_data()
    title = data.get("title", "Новая задача")
    await remember_task_panel_in_state(state, callback.message)
    if callback.data == TASK_CREATE_ONE_TIME_CALLBACK:
        await state.update_data(is_recurring=False, recurrence_type=None)
        await state.set_state(TaskCreationStates.choosing_assignment)
        partner_button = await get_partner_assignment_button(session, result)
        await edit_task_panel_message(
            callback.message,
            f"➕ <b>{escape(title)}</b>\n\nКому назначить задачу?",
            build_assignment_keyboard(partner_button),
        )
        await callback.answer()
        return

    await state.update_data(is_recurring=True)
    await state.set_state(TaskCreationStates.choosing_recurrence)
    await edit_task_panel_message(
        callback.message,
        f"➕ <b>{escape(title)}</b>\n\nКак часто повторять?",
        build_recurrence_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_(set(RECURRENCE_BY_CALLBACK)))
async def handle_task_recurrence(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None or callback.message is None or callback.data is None:
        return

    recurrence_type = RECURRENCE_BY_CALLBACK[callback.data]
    data = await state.get_data()
    title = data.get("title", "Новая задача")
    await remember_task_panel_in_state(state, callback.message)
    await state.update_data(recurrence_type=recurrence_type.value)
    await state.set_state(TaskCreationStates.choosing_assignment)
    partner_button = await get_partner_assignment_button(session, result)
    await edit_task_panel_message(
        callback.message,
        f"➕ <b>{escape(title)}</b>\n\nКому назначить задачу?",
        build_assignment_keyboard(partner_button),
    )
    await callback.answer()


@router.callback_query(F.data.in_(set(ASSIGNMENT_BY_CALLBACK)))
async def handle_task_assignment(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await ensure_task_access_for_callback(callback, session) is None:
        return
    if callback.message is None or callback.data is None:
        return

    assignment_type = ASSIGNMENT_BY_CALLBACK[callback.data]
    data = await state.get_data()
    title = data.get("title", "Новая задача")
    await remember_task_panel_in_state(state, callback.message)
    await state.update_data(assignment_type=assignment_type.value)
    await state.set_state(TaskCreationStates.waiting_for_deadline)
    await edit_task_panel_message(
        callback.message,
        f"➕ <b>{escape(title)}</b>\n\nКогда выполнить? Можно выбрать кнопку или написать дату в формате ДД.ММ.ГГГГ.",
        build_deadline_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data.in_(set(DEADLINE_BY_CALLBACK)))
async def handle_task_deadline_choice(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None or result.couple is None or callback.message is None or callback.data is None:
        return

    await remember_task_panel_in_state(state, callback.message)
    deadline = parse_task_deadline(DEADLINE_BY_CALLBACK[callback.data], result.couple)
    data = await state.get_data()
    creation_input = TaskCreationInput(
        title=data["title"],
        is_recurring=data["is_recurring"],
        recurrence_type=RecurrenceType(data["recurrence_type"]) if data.get("recurrence_type") else None,
        assignment_type=AssignmentType(data["assignment_type"]),
        deadline=deadline,
    )
    await finish_task_creation(
        bot=bot,
        state=state,
        session=session,
        result=result,
        creation_input=creation_input,
    )
    await callback.answer()


@router.message(TaskCreationStates.choosing_recurring)
@router.message(TaskCreationStates.choosing_recurrence)
@router.message(TaskCreationStates.choosing_assignment)
async def handle_task_inline_step_text(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    await add_task_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    data = await state.get_data()
    title = data.get("title", "Новая задача")
    current_state = await state.get_state()

    if current_state == TaskCreationStates.choosing_recurring.state:
        text = f"➕ <b>{escape(title)}</b>\n\nВыбери тип задачи кнопкой в панели."
        keyboard = build_recurring_choice_keyboard()
    elif current_state == TaskCreationStates.choosing_recurrence.state:
        text = f"➕ <b>{escape(title)}</b>\n\nВыбери периодичность кнопкой в панели."
        keyboard = build_recurrence_keyboard()
    else:
        partner_button = await get_partner_assignment_button(session, result)
        text = f"➕ <b>{escape(title)}</b>\n\nВыбери назначение кнопкой в панели."
        keyboard = build_assignment_keyboard(partner_button)

    await edit_task_panel_from_state(bot, state, text, keyboard)


@router.message(TaskCreationStates.waiting_for_deadline)
async def handle_task_deadline(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None or result.couple is None:
        return

    await add_task_block_messages(session, result.user, message.chat.id, [message])
    await delete_user_message(bot, message)
    deadline_text = message.text or ""
    try:
        deadline = parse_task_deadline(deadline_text, result.couple)
    except DeadlineParseError:
        await edit_task_panel_from_state(
            bot,
            state,
            "➕ <b>Добавить задачу</b>\n\nНе поняла дату. Напиши, например, 21.05.2026 или выбери кнопку.",
            build_deadline_keyboard(),
        )
        return

    data = await state.get_data()
    creation_input = TaskCreationInput(
        title=data["title"],
        is_recurring=data["is_recurring"],
        recurrence_type=RecurrenceType(data["recurrence_type"]) if data.get("recurrence_type") else None,
        assignment_type=AssignmentType(data["assignment_type"]),
        deadline=deadline,
    )
    await finish_task_creation(
        bot=bot,
        state=state,
        session=session,
        result=result,
        creation_input=creation_input,
    )


@router.callback_query(F.data.in_({MY_TASKS_CALLBACK, TASK_POOL_CALLBACK, ALL_TASKS_CALLBACK}))
async def handle_task_list(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None or result.couple is None or callback.message is None:
        return

    service = TaskService(session)
    if callback.data == MY_TASKS_CALLBACK:
        context, tasks = await service.list_my_tasks(result.user)
        title = "Мои задачи"
        empty_text = "У тебя пока нет назначенных задач."
    elif callback.data == TASK_POOL_CALLBACK:
        context, tasks = await service.list_pool(result.user)
        title = "Ярмарка"
        empty_text = "В ярмарке задач пока пусто."
    else:
        context, tasks = await service.list_all_active(result.user)
        title = "Все активные"
        empty_text = "Активных задач пока нет."

    await edit_task_panel_message(
        callback.message,
        await render_task_list_panel(
            service,
            context,
            tasks,
            title=title,
            empty_text=empty_text,
            show_ownership=callback.data == ALL_TASKS_CALLBACK,
        ),
        build_task_list_keyboard(tasks, view=callback.data or "", current_user_id=result.user.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tasks:claim:"))
async def handle_claim_task(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await handle_task_mutation(callback, session, bot, action="claim")


@router.callback_query(F.data.startswith("tasks:done:"))
async def handle_complete_task(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    await handle_task_mutation(callback, session, bot, action="done")


async def handle_task_mutation(callback: CallbackQuery, session: AsyncSession, bot: Bot, *, action: str) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None or result.couple is None or callback.message is None or callback.data is None:
        return

    try:
        task_id = int(callback.data.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        await callback.answer("Не смогла понять задачу.", show_alert=True)
        return

    try:
        service = TaskService(session)
        if action == "claim":
            mutation_result = await service.claim_task(result.user, task_id)
            answer_text = "Задача теперь твоя."
        else:
            mutation_result = await service.complete_task(result.user, task_id)
            answer_text = "Готово. Маленькая бытовая победа засчитана."
    except TaskServiceError as error:
        await callback.answer(str(error), show_alert=True)
        return

    await send_task_notification(bot, mutation_result)
    service = TaskService(session)
    context = await service.get_context(result.user)
    keyboard = await build_tasks_menu_for_user(session, result.user)
    await edit_task_panel_message(
        callback.message,
        f"✅ <b>{answer_text}</b>\n\n{await service.build_task_card(context, mutation_result.task, show_ownership=True)}",
        keyboard,
    )
    await callback.answer()
