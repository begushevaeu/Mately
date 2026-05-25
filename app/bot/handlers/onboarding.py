from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main_menu import build_main_menu
from app.bot.keyboards.onboarding import (
    CANCEL_BUTTON,
    CREATE_COUPLE_BUTTON,
    ENTER_INVITE_CODE_BUTTON,
    REFRESH_STATUS_BUTTON,
    build_cancel_menu,
    build_onboarding_menu,
    build_waiting_for_partner_menu,
)
from app.bot.states.onboarding import JoinCoupleStates
from app.bot.handlers.partner_aliases import maybe_prompt_couple_creator_for_joined_partner, maybe_prompt_partner_alias
from app.services.chat_blocks import (
    MAIN_MENU_BLOCK_KEYS,
    ONBOARDING_BLOCK_KEY,
    PARTNER_ALIAS_BLOCK_KEY,
    ChatBlockService,
)
from app.services.couples import CoupleService, OnboardingResult, OnboardingStatus, TelegramUserProfile

router = Router()
RECOVERABLE_BLOCK_KEYS = MAIN_MENU_BLOCK_KEYS + (ONBOARDING_BLOCK_KEY, PARTNER_ALIAS_BLOCK_KEY)


def profile_from_message(message: Message) -> TelegramUserProfile | None:
    if message.from_user is None:
        return None

    return TelegramUserProfile(
        telegram_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
    )


async def answer_for_onboarding_state(message: Message, result: OnboardingResult) -> None:
    if result.status is OnboardingStatus.NO_COUPLE:
        await message.answer(
            "Привет! Давай создадим ваше пространство Mately или подключимся по коду партнера.",
            reply_markup=build_onboarding_menu(),
        )
        return

    if result.status is OnboardingStatus.WAITING_FOR_PARTNER:
        await message.answer(
            "Пара создана. Отправь партнеру этот код:\n\n"
            f"<b>{escape(result.invite_code or '')}</b>\n\n"
            "Когда партнер введет код у себя в боте, ваше пространство станет общим.",
            reply_markup=build_waiting_for_partner_menu(),
            parse_mode="HTML",
        )
        return

    if result.status is OnboardingStatus.IN_COUPLE:
        await message.answer(
            "Вы уже в общем пространстве Mately. Можно начинать наводить уютный порядок.",
            reply_markup=build_main_menu(),
        )
        return

    if result.status is OnboardingStatus.INVALID_OR_EXPIRED_INVITE:
        await message.answer(
            "Этот код не найден или уже устарел. Проверь код и попробуй еще раз.",
            reply_markup=build_onboarding_menu(),
        )
        return

    if result.status is OnboardingStatus.COUPLE_FULL:
        await message.answer(
            "Эта пара уже заполнена. Один код приглашения подходит только для двух человек.",
            reply_markup=build_onboarding_menu(),
        )


async def get_current_onboarding_result(message: Message, session: AsyncSession) -> OnboardingResult | None:
    profile = profile_from_message(message)
    if profile is None:
        await message.answer("Не смогла определить Telegram-пользователя. Попробуй открыть бота в личном чате.")
        return None

    return await CoupleService(session).start_for_profile(profile)


async def remember_onboarding_messages(
    *,
    session: AsyncSession,
    result: OnboardingResult,
    chat_id: int,
    messages: list[Message],
) -> None:
    await ChatBlockService(session).add_messages(
        user=result.user,
        chat_id=chat_id,
        block_key=ONBOARDING_BLOCK_KEY,
        messages=messages,
    )


async def reset_onboarding_block(*, session: AsyncSession, bot: Bot, result: OnboardingResult, chat_id: int) -> None:
    await ChatBlockService(session).reset_block(
        bot=bot,
        user=result.user,
        chat_id=chat_id,
        block_key=ONBOARDING_BLOCK_KEY,
    )


async def reset_recoverable_blocks(*, session: AsyncSession, bot: Bot, result: OnboardingResult, chat_id: int) -> None:
    await ChatBlockService(session).reset_blocks(
        bot=bot,
        user=result.user,
        chat_id=chat_id,
        block_keys=RECOVERABLE_BLOCK_KEYS,
    )


@router.message(Command("menu"))
async def handle_menu(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await state.clear()
    result = await get_current_onboarding_result(message, session)
    if result is not None:
        await reset_recoverable_blocks(session=session, bot=bot, result=result, chat_id=message.chat.id)
        await answer_for_onboarding_state(message, result)


@router.message(Command("help"))
async def handle_help(message: Message) -> None:
    await message.answer(
        "Команды Mately:\n"
        "/start - начать или проверить состояние пары\n"
        "/menu - вернуться в безопасное меню\n"
        "/cancel - отменить текущий ввод\n"
        "/help - показать эту подсказку"
    )


@router.message(Command("cancel"))
@router.message(F.text == CANCEL_BUTTON)
async def handle_cancel(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await state.clear()
    result = await get_current_onboarding_result(message, session)
    if result is not None:
        await reset_recoverable_blocks(session=session, bot=bot, result=result, chat_id=message.chat.id)
        await message.answer("Ок, остановились здесь.")
        await answer_for_onboarding_state(message, result)


@router.message(F.text == CREATE_COUPLE_BUTTON)
async def handle_create_couple(message: Message, session: AsyncSession) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return

    created_result = await CoupleService(session).create_couple(result.user)
    await answer_for_onboarding_state(message, created_result)


@router.message(F.text == ENTER_INVITE_CODE_BUTTON)
async def handle_enter_invite_code(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return

    await reset_onboarding_block(session=session, bot=bot, result=result, chat_id=message.chat.id)
    await state.set_state(JoinCoupleStates.waiting_for_invite_code)
    sent_message = await message.answer("Введи код приглашения от партнера.", reply_markup=build_cancel_menu())
    await ChatBlockService(session).remember_messages(
        user=result.user,
        chat_id=message.chat.id,
        block_key=ONBOARDING_BLOCK_KEY,
        messages=[message, sent_message],
    )


@router.message(F.text == REFRESH_STATUS_BUTTON)
async def handle_refresh_status(message: Message, session: AsyncSession) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is not None:
        await answer_for_onboarding_state(message, result)


@router.message(JoinCoupleStates.waiting_for_invite_code)
async def handle_invite_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    bot: Bot,
    dispatcher: Dispatcher,
) -> None:
    result = await get_current_onboarding_result(message, session)
    if result is None:
        return

    invite_code = message.text or ""
    await remember_onboarding_messages(
        session=session,
        result=result,
        chat_id=message.chat.id,
        messages=[message],
    )
    joined_result = await CoupleService(session).join_couple(result.user, invite_code)
    await state.clear()
    if joined_result.status is OnboardingStatus.IN_COUPLE:
        await reset_onboarding_block(session=session, bot=bot, result=result, chat_id=message.chat.id)
    await answer_for_onboarding_state(message, joined_result)
    await maybe_prompt_partner_alias(message, joined_result, session, state, bot)
    if result.status is not OnboardingStatus.IN_COUPLE:
        await maybe_prompt_couple_creator_for_joined_partner(
            bot=bot,
            dispatcher=dispatcher,
            session=session,
            result=joined_result,
        )
