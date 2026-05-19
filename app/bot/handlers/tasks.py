import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.onboarding import answer_for_onboarding_state, get_current_onboarding_result
from app.bot.keyboards.main_menu import TASKS_BUTTON, build_main_menu
from app.bot.keyboards.onboarding import build_cancel_menu
from app.bot.keyboards.tasks import (
    ADD_TASK_CALLBACK,
    ALL_TASKS_CALLBACK,
    ASSIGN_PARTNER_BUTTON,
    ASSIGN_POOL_BUTTON,
    ASSIGN_SELF_BUTTON,
    CUSTOM_RECURRENCE_BUTTON,
    DAILY_RECURRENCE_BUTTON,
    MONTHLY_RECURRENCE_BUTTON,
    MY_TASKS_CALLBACK,
    NO_DEADLINE_BUTTON,
    ONE_TIME_TASK_BUTTON,
    RECURRING_TASK_BUTTON,
    TASK_POOL_CALLBACK,
    TASKS_MENU_CALLBACK,
    TODAY_DEADLINE_BUTTON,
    TOMORROW_DEADLINE_BUTTON,
    WEEKLY_RECURRENCE_BUTTON,
    build_assignment_keyboard,
    build_deadline_keyboard,
    build_recurrence_keyboard,
    build_recurring_choice_keyboard,
    build_task_actions,
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

RECURRENCE_BY_BUTTON = {
    DAILY_RECURRENCE_BUTTON: RecurrenceType.DAILY,
    WEEKLY_RECURRENCE_BUTTON: RecurrenceType.WEEKLY,
    MONTHLY_RECURRENCE_BUTTON: RecurrenceType.MONTHLY,
    CUSTOM_RECURRENCE_BUTTON: RecurrenceType.CUSTOM,
}

ASSIGNMENT_BY_BUTTON = {
    ASSIGN_SELF_BUTTON: AssignmentType.SELF,
    ASSIGN_PARTNER_BUTTON: AssignmentType.PARTNER,
    ASSIGN_POOL_BUTTON: AssignmentType.POOL,
}

DEADLINE_BY_BUTTON = {
    TODAY_DEADLINE_BUTTON: "сегодня",
    TOMORROW_DEADLINE_BUTTON: "завтра",
    NO_DEADLINE_BUTTON: "без срока",
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


async def add_task_block_messages(session: AsyncSession, user, chat_id: int, messages: list[Message]) -> None:
    await ChatBlockService(session).add_messages(
        user=user,
        chat_id=chat_id,
        block_key=TASKS_BLOCK_KEY,
        messages=messages,
    )


async def reset_and_show_tasks_menu(message: Message, session: AsyncSession, bot: Bot, result: OnboardingResult) -> None:
    await ChatBlockService(session).reset_block(
        bot=bot,
        user=result.user,
        chat_id=message.chat.id,
        block_key=TASKS_BLOCK_KEY,
    )
    keyboard = await build_tasks_menu_for_user(session, result.user)
    sent_messages = [
        await message.answer("Задачи", reply_markup=build_main_menu()),
        await message.answer("Что делаем?", reply_markup=keyboard),
    ]
    await ChatBlockService(session).remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=TASKS_BLOCK_KEY,
        messages=sent_messages,
    )


async def get_partner_assignment_button(session: AsyncSession, result: OnboardingResult) -> str:
    context = await TaskService(session).get_context(result.user)
    if context.partner is None:
        return ASSIGN_PARTNER_BUTTON

    display = await PartnerAliasService(session).get_display_for(owner=result.user, partner=context.partner)
    return display.dative_with_emoji


@router.message(F.text == TASKS_BUTTON)
async def handle_tasks_menu(message: Message, session: AsyncSession, bot: Bot) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    await reset_and_show_tasks_menu(message, session, bot, result)


@router.callback_query(F.data == TASKS_MENU_CALLBACK)
async def handle_tasks_menu_callback(callback: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if await ensure_task_access_for_callback(callback, session) is None:
        return

    if callback.message is not None:
        result = await get_current_result_for_callback(callback, session)
        await reset_and_show_tasks_menu(callback.message, session, bot, result)
    await callback.answer()


@router.callback_query(F.data == ADD_TASK_CALLBACK)
async def handle_add_task(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    if await ensure_task_access_for_callback(callback, session) is None:
        return

    await state.set_state(TaskCreationStates.waiting_for_title)
    if callback.message is not None:
        result = await get_current_result_for_callback(callback, session)
        sent_message = await callback.message.answer("Как назовем задачу?", reply_markup=build_cancel_menu())
        await add_task_block_messages(session, result.user, callback.message.chat.id, [sent_message])
    await callback.answer()


@router.message(TaskCreationStates.waiting_for_title)
async def handle_task_title(message: Message, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    title = (message.text or "").strip()
    if not title:
        sent_message = await message.answer("Название не должно быть пустым. Напиши задачу коротко и понятно.")
        await add_task_block_messages(session, result.user, message.chat.id, [sent_message])
        return

    if len(title) > 255:
        sent_message = await message.answer("Название получилось слишком длинным. Давай уложимся в 255 символов.")
        await add_task_block_messages(session, result.user, message.chat.id, [sent_message])
        return

    await state.update_data(title=title)
    await state.set_state(TaskCreationStates.choosing_recurring)
    sent_message = await message.answer("Это разовая или регулярная задача?", reply_markup=build_recurring_choice_keyboard())
    await add_task_block_messages(session, result.user, message.chat.id, [sent_message])


@router.message(TaskCreationStates.choosing_recurring)
async def handle_task_recurring_choice(message: Message, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    text = message.text or ""
    if text == ONE_TIME_TASK_BUTTON:
        await state.update_data(is_recurring=False, recurrence_type=None)
        await state.set_state(TaskCreationStates.choosing_assignment)
        partner_button = await get_partner_assignment_button(session, result)
        await state.update_data(partner_assignment_button=partner_button)
        sent_message = await message.answer("Кому назначить задачу?", reply_markup=build_assignment_keyboard(partner_button))
        await add_task_block_messages(session, result.user, message.chat.id, [sent_message])
        return

    if text == RECURRING_TASK_BUTTON:
        await state.update_data(is_recurring=True)
        await state.set_state(TaskCreationStates.choosing_recurrence)
        sent_message = await message.answer("Как часто повторять?", reply_markup=build_recurrence_keyboard())
        await add_task_block_messages(session, result.user, message.chat.id, [sent_message])
        return

    sent_message = await message.answer("Выбери вариант кнопкой: разовая или регулярная.")
    await add_task_block_messages(session, result.user, message.chat.id, [sent_message])


@router.message(TaskCreationStates.choosing_recurrence)
async def handle_task_recurrence(message: Message, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    recurrence_type = RECURRENCE_BY_BUTTON.get(message.text or "")
    if recurrence_type is None:
        sent_message = await message.answer("Выбери периодичность кнопкой.")
        await add_task_block_messages(session, result.user, message.chat.id, [sent_message])
        return

    await state.update_data(recurrence_type=recurrence_type.value)
    await state.set_state(TaskCreationStates.choosing_assignment)
    partner_button = await get_partner_assignment_button(session, result)
    await state.update_data(partner_assignment_button=partner_button)
    sent_message = await message.answer("Кому назначить задачу?", reply_markup=build_assignment_keyboard(partner_button))
    await add_task_block_messages(session, result.user, message.chat.id, [sent_message])


@router.message(TaskCreationStates.choosing_assignment)
async def handle_task_assignment(message: Message, state: FSMContext, session: AsyncSession) -> None:
    result = await ensure_task_access_for_message(message, session)
    if result is None:
        return

    data = await state.get_data()
    assignment_type = ASSIGNMENT_BY_BUTTON.get(message.text or "")
    if assignment_type is None and message.text == data.get("partner_assignment_button"):
        assignment_type = AssignmentType.PARTNER
    if assignment_type is None:
        sent_message = await message.answer("Выбери назначение кнопкой.")
        await add_task_block_messages(session, result.user, message.chat.id, [sent_message])
        return

    await state.update_data(assignment_type=assignment_type.value)
    await state.set_state(TaskCreationStates.waiting_for_deadline)
    sent_message = await message.answer(
        "Когда выполнить? Можно нажать кнопку или написать дату в формате ДД.ММ.ГГГГ.",
        reply_markup=build_deadline_keyboard(),
    )
    await add_task_block_messages(session, result.user, message.chat.id, [sent_message])


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

    deadline_text = DEADLINE_BY_BUTTON.get(message.text or "", message.text or "")
    try:
        deadline = parse_task_deadline(deadline_text, result.couple)
    except DeadlineParseError:
        sent_message = await message.answer("Не поняла дату. Напиши, например, 21.05.2026 или выбери кнопку.")
        await add_task_block_messages(session, result.user, message.chat.id, [sent_message])
        return

    data = await state.get_data()
    creation_input = TaskCreationInput(
        title=data["title"],
        is_recurring=data["is_recurring"],
        recurrence_type=RecurrenceType(data["recurrence_type"]) if data.get("recurrence_type") else None,
        assignment_type=AssignmentType(data["assignment_type"]),
        deadline=deadline,
    )
    mutation_result = await TaskService(session).create_task(result.user, creation_input)
    await state.clear()
    await send_task_notification(bot, mutation_result)
    keyboard = await build_tasks_menu_for_user(session, result.user)
    context = await TaskService(session).get_context(result.user)
    card = await TaskService(session).build_task_card(context, mutation_result.task, show_ownership=True)
    sent_messages = [
        await message.answer("Задача создана.", reply_markup=build_main_menu()),
        await message.answer(
            card,
            reply_markup=keyboard,
            parse_mode="HTML",
        ),
    ]
    await add_task_block_messages(session, result.user, message.chat.id, sent_messages)


@router.callback_query(F.data.in_({MY_TASKS_CALLBACK, TASK_POOL_CALLBACK, ALL_TASKS_CALLBACK}))
async def handle_task_list(callback: CallbackQuery, session: AsyncSession) -> None:
    result = await ensure_task_access_for_callback(callback, session)
    if result is None or result.couple is None or callback.message is None:
        return

    service = TaskService(session)
    if callback.data == MY_TASKS_CALLBACK:
        context, tasks = await service.list_my_tasks(result.user)
        empty_text = "У тебя пока нет назначенных задач."
    elif callback.data == TASK_POOL_CALLBACK:
        context, tasks = await service.list_pool(result.user)
        empty_text = "В ярмарке задач пока пусто."
    else:
        context, tasks = await service.list_all_active(result.user)
        empty_text = "Активных задач пока нет."

    if not tasks:
        keyboard = await build_tasks_menu_for_user(session, result.user)
        sent_message = await callback.message.answer(empty_text, reply_markup=keyboard)
        await add_task_block_messages(session, result.user, callback.message.chat.id, [sent_message])
        await callback.answer()
        return

    sent_messages = [await callback.message.answer("Вот что нашлось:")]
    for task in tasks:
        sent_messages.append(await callback.message.answer(
            await service.build_task_card(context, task, show_ownership=callback.data == ALL_TASKS_CALLBACK),
            reply_markup=build_task_actions(task.id, can_claim=task.assigned_to is None),
            parse_mode="HTML",
        ))
    keyboard = await build_tasks_menu_for_user(session, result.user)
    sent_messages.append(await callback.message.answer("Меню задач", reply_markup=keyboard))
    await add_task_block_messages(session, result.user, callback.message.chat.id, sent_messages)
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
    context = await TaskService(session).get_context(result.user)
    keyboard = await build_tasks_menu_for_user(session, result.user)
    sent_messages = [
        await callback.message.answer(
            answer_text,
            reply_markup=build_main_menu(),
        ),
        await callback.message.answer(
            await TaskService(session).build_task_card(context, mutation_result.task, show_ownership=True),
            reply_markup=keyboard,
            parse_mode="HTML",
        ),
    ]
    await add_task_block_messages(session, result.user, callback.message.chat.id, sent_messages)
    await callback.answer()
